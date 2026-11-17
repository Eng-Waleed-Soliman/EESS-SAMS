from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    Branch,
    CafeteriaCashSupply,
    CafeteriaCategory,
    CafeteriaItem,
    CafeteriaPurchase,
    CafeteriaSale,
    ExpenseCategory,
    FinancialVoucher,
    MonthlyExpense,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class CafeteriaCashSupplyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='cash-test-admin',
            email='cash@example.com',
            password='test-password',
        )
        self.client.force_login(self.user)
        self.branch = Branch.objects.create(name='Cash Test Branch', short_name='CTB')
        session = self.client.session
        session['active_branch_id'] = self.branch.pk
        session.save()
        self.category = CafeteriaCategory.objects.create(code=9901, name='Cash Test Category')
        self.item = CafeteriaItem.objects.create(
            branch=self.branch,
            category=self.category,
            code=9901,
            name='Cash Test Item',
            opening_quantity=20,
            purchase_price=10,
            sale_price=25,
        )
        CafeteriaPurchase.objects.create(
            item=self.item,
            purchase_date=date.today(),
            quantity=5,
            unit_price=10,
        )
        CafeteriaSale.objects.create(
            item=self.item,
            sale_date=date.today(),
            quantity=4,
            unit_price=25,
        )

    def test_cash_supply_is_saved_and_inventory_cash_is_recalculated(self):
        response = self.client.post(reverse('cafe_cash_supply_create'), {
            'supply_date': date.today().isoformat(),
            'amount': 30,
        })
        self.assertRedirects(response, reverse('cafe_inventory'))
        supply = CafeteriaCashSupply.objects.get()
        self.assertEqual(supply.branch, self.branch)
        self.assertEqual(supply.created_by, self.user)

        response = self.client.get(reverse('cafe_inventory'), {'preset': 'today'})
        self.assertEqual(response.context['cafeteria_cash'], 20)
        self.assertContains(response, 'الكاش')
        self.assertContains(response, 'توريد مبلغ مالي')
        self.assertNotContains(response, 'كود الفئة')
        self.assertNotContains(response, 'المتبقي هو رصيد بداية الفترة')

    def test_cash_supply_cannot_exceed_available_cafeteria_cash(self):
        response = self.client.post(reverse('cafe_cash_supply_create'), {
            'supply_date': date.today().isoformat(),
            'amount': 51,
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CafeteriaCashSupply.objects.exists())
        self.assertContains(response, 'مبلغ التوريد أكبر من الكاش المتاح')
        self.assertContains(response, '50')

    def test_cafeteria_report_shows_supplied_total_for_selected_period(self):
        CafeteriaCashSupply.objects.create(
            branch=self.branch,
            supply_date=date.today(),
            amount=30,
            created_by=self.user,
        )
        response = self.client.get(reverse('reports_home'), {
            'report_type': 'cafeteria',
            'range_mode': 'custom',
            'date_from': date.today().isoformat(),
            'date_to': date.today().isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['cafeteria_supplied_total'], 30)
        self.assertContains(response, 'إجمالي المبلغ المورد')

    def test_sales_screen_can_create_supply_and_return_to_sales(self):
        response = self.client.get(reverse('cafe_sale_list'))
        self.assertContains(response, reverse('cafe_cash_supply_create') + '?next=sales')

        response = self.client.post(reverse('cafe_cash_supply_create'), {
            'supply_date': date.today().isoformat(),
            'amount': 45,
            'next': 'sales',
        })
        self.assertRedirects(response, reverse('cafe_sale_list'))
        self.assertEqual(CafeteriaCashSupply.objects.get().amount, 45)

    def test_cafeteria_income_financial_voucher_reduces_cafeteria_cash(self):
        create_url = reverse('financial_voucher_create', args=['supply'])
        response = self.client.post(create_url, {
            'income_source': FinancialVoucher.SOURCE_CAFETERIA,
            'amount': 31,
            'voucher_date': date.today().isoformat(),
        })

        voucher = FinancialVoucher.objects.get(
            voucher_type=FinancialVoucher.TYPE_SUPPLY,
            income_source=FinancialVoucher.SOURCE_CAFETERIA,
        )
        self.assertRedirects(response, reverse('financial_voucher_detail', args=[voucher.pk]))
        self.assertEqual(voucher.branch, self.branch)
        self.assertEqual(self.client.get(reverse('cafe_inventory')).context['cafeteria_cash'], 19)

        voucher.delete()
        self.assertEqual(self.client.get(reverse('cafe_inventory')).context['cafeteria_cash'], 50)

    def test_cafeteria_expense_categories_reduce_cash_and_enter_reports_once(self):
        purchase_category = ExpenseCategory.objects.create(name='مشتروات أصناف الكافيتريا')
        operation_category = ExpenseCategory.objects.create(name='مصاريف تشغيل الكافيتريا')
        for category, amount in ((purchase_category, 15), (operation_category, 5)):
            response = self.client.post(reverse('monthly_expense_create'), {
                'expense_month': date.today().isoformat(),
                'category': category.pk,
                'amount': amount,
                'notes': f'اختبار {category.name}',
            })
            self.assertRedirects(response, reverse('general_expenses_home'))

        expenses = MonthlyExpense.objects.order_by('amount')
        self.assertEqual(expenses.count(), 2)
        self.assertTrue(all(expense.branch == self.branch for expense in expenses))
        inventory = self.client.get(reverse('cafe_inventory'))
        self.assertEqual(inventory.context['cafeteria_cash'], 30)

        month_value = date.today().strftime('%Y-%m')
        expense_report = self.client.get(reverse('reports_home'), {
            'report_type': 'expenses', 'month': month_value,
        })
        self.assertEqual(expense_report.context['monthly_expenses_total'], 20)
        self.assertEqual(expense_report.context['all_expenses_total'], 20)

        income_report = self.client.get(reverse('reports_home'), {
            'report_type': 'monthly_income', 'month': month_value,
        })
        self.assertEqual(income_report.context['income_expenses_total'], 70)
        self.assertEqual(income_report.context['income_net_total'], 30)
        self.assertContains(income_report, purchase_category.name)
        self.assertContains(income_report, operation_category.name)

    def test_cafeteria_operating_expense_category_with_prefix_reduces_cash(self):
        category = ExpenseCategory.objects.create(name='مصروفات تشغيل للكافيتريا')
        response = self.client.post(reverse('monthly_expense_create'), {
            'expense_month': date.today().isoformat(),
            'category': category.pk,
            'amount': 4,
            'notes': 'صيغة الاسم المستخدمة في شاشة المصروفات',
        })

        self.assertRedirects(response, reverse('general_expenses_home'))
        self.assertEqual(MonthlyExpense.objects.get().amount, 4)
        inventory = self.client.get(reverse('cafe_inventory'))
        self.assertEqual(inventory.context['cafeteria_cash'], 46)

    def test_cash_supply_form_shows_newest_supplies_first(self):
        older = CafeteriaCashSupply.objects.create(
            branch=self.branch,
            supply_date=date.today() - timedelta(days=1),
            amount=10,
            created_by=self.user,
        )
        newer = CafeteriaCashSupply.objects.create(
            branch=self.branch,
            supply_date=date.today(),
            amount=20,
            created_by=self.user,
        )

        response = self.client.get(reverse('cafe_cash_supply_create'))
        self.assertContains(response, 'سجل توريدات المبالغ المالية')
        self.assertContains(response, '<th>تاريخ التوريد</th>', html=True)
        self.assertEqual(list(response.context['supplies']), [newer, older])
