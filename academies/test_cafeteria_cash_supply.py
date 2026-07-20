from datetime import date

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
