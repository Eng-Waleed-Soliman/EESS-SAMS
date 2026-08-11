from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .views import _month_financial_summary

from .models import (
    Branch,
    CafeteriaCategory,
    CafeteriaItem,
    CafeteriaOperatingExpense,
    CafeteriaPurchase,
    CafeteriaSale,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class CafeteriaOperatingExpenseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='cafe-expense-admin',
            email='cafe-expense@example.com',
            password='test-password',
        )
        self.client.force_login(self.user)
        self.branch = Branch.objects.create(name='Cafe Expense Branch', short_name='CEB')
        session = self.client.session
        session['active_branch_id'] = self.branch.pk
        session.save()
        category = CafeteriaCategory.objects.create(code=9801, name='Expense Test Category')
        self.item = CafeteriaItem.objects.create(
            branch=self.branch,
            category=category,
            code=9801,
            name='Expense Test Item',
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

    def test_create_screen_saves_expense_and_deducts_it_from_cafeteria_cash(self):
        inventory = self.client.get(reverse('cafe_inventory'))
        self.assertContains(inventory, reverse('cafe_operating_expense_create'))
        self.assertEqual(inventory.context['cafeteria_cash'], 50)

        form_page = self.client.get(reverse('cafe_operating_expense_create'))
        self.assertContains(form_page, 'تاريخ المصروف')
        self.assertContains(form_page, 'بيان المصروف')
        self.assertContains(form_page, 'قيمة المصروفات')
        self.assertContains(form_page, 'إلغاء')

        response = self.client.post(reverse('cafe_operating_expense_create'), {
            'expense_date': date.today().isoformat(),
            'title': 'صيانة ماكينة القهوة',
            'amount': 20,
        })
        self.assertRedirects(response, reverse('cafe_operating_expense_list'))
        expense = CafeteriaOperatingExpense.objects.get()
        self.assertEqual(expense.branch, self.branch)
        self.assertEqual(expense.created_by, self.user)

        inventory = self.client.get(reverse('cafe_inventory'))
        self.assertEqual(inventory.context['cafeteria_cash'], 30)

    def test_expense_can_be_edited_deleted_and_appears_in_month_or_custom_income_report(self):
        expense = CafeteriaOperatingExpense.objects.create(
            branch=self.branch,
            expense_date=date.today(),
            title='صيانة ماكينة القهوة',
            amount=20,
            created_by=self.user,
        )
        month_value = date.today().strftime('%Y-%m')
        for params in (
            {'report_type': 'monthly_income', 'month': month_value},
            {
                'report_type': 'monthly_income', 'range_mode': 'custom',
                'date_from': date.today().isoformat(), 'date_to': date.today().isoformat(),
            },
        ):
            report = self.client.get(reverse('reports_home'), params)
            self.assertEqual(report.context['income_cafeteria_total'], 100)
            self.assertEqual(report.context['income_expenses_total'], 70)
            self.assertEqual(report.context['income_net_total'], 30)
            self.assertContains(report, 'مصاريف تشغيل الكافيتريا')
            self.assertContains(report, expense.title)

        response = self.client.post(reverse('cafe_operating_expense_update', args=[expense.pk]), {
            'expense_date': date.today().isoformat(),
            'title': 'صيانة معدلة',
            'amount': 15,
        })
        self.assertRedirects(response, reverse('cafe_operating_expense_list'))
        expense.refresh_from_db()
        self.assertEqual(expense.title, 'صيانة معدلة')
        self.assertEqual(expense.amount, 15)
        self.assertEqual(self.client.get(reverse('cafe_inventory')).context['cafeteria_cash'], 35)

        response = self.client.post(reverse('cafe_operating_expense_delete', args=[expense.pk]))
        self.assertRedirects(response, reverse('cafe_operating_expense_list'))
        self.assertFalse(CafeteriaOperatingExpense.objects.exists())
        self.assertEqual(self.client.get(reverse('cafe_inventory')).context['cafeteria_cash'], 50)

    def test_cafeteria_profit_treats_operating_expenses_as_part_of_purchases(self):
        today = date.today()
        CafeteriaOperatingExpense.objects.create(
            branch=self.branch,
            expense_date=today,
            title='Machine maintenance',
            amount=20,
            created_by=self.user,
        )

        report = self.client.get(reverse('reports_home'), {
            'report_type': 'cafeteria',
            'month': today.strftime('%Y-%m'),
        })
        self.assertEqual(report.context['cafeteria_stock_purchase_total'], 50)
        self.assertEqual(report.context['cafeteria_operating_expense_total'], 20)
        self.assertEqual(report.context['cafeteria_purchase_total'], 70)
        self.assertEqual(report.context['cafeteria_sales_total'], 100)
        self.assertEqual(report.context['cafeteria_net_profit'], 30)
        self.assertContains(report, 'المشتريات شاملة مصاريف التشغيل')

        month_start = today.replace(day=1)
        summary = _month_financial_summary(
            today.year, today.month, month_start, today, branch=self.branch,
        )
        self.assertEqual(summary['cafe_stock_purchase_total'], 50)
        self.assertEqual(summary['cafe_operating_expenses'], 20)
        self.assertEqual(summary['cafe_purchase_total'], 70)
        self.assertEqual(summary['total_expenses'], 70)
        self.assertEqual(summary['net_profit'], 30)
