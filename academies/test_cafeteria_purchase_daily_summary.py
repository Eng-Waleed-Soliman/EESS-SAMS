from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CafeteriaItem, CafeteriaPurchase


@override_settings(SECURE_SSL_REDIRECT=False)
class CafeteriaPurchaseDailySummaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='purchase-summary', password='password')
        self.client.force_login(self.user)

    def test_purchase_list_groups_movements_by_day_and_uses_weighted_totals(self):
        selected_date = date(2026, 8, 10)
        count_item = CafeteriaItem.objects.create(
            code=901, name='Count item', item_type=CafeteriaItem.TYPE_COUNT,
        )
        weight_item = CafeteriaItem.objects.create(
            code=902, name='Weight item', item_type=CafeteriaItem.TYPE_WEIGHT,
        )
        CafeteriaPurchase.objects.create(
            item=count_item, purchase_date=selected_date, quantity=5, unit_price=10,
        )
        CafeteriaPurchase.objects.create(
            item=weight_item, purchase_date=selected_date, quantity=500, unit_price=600,
        )
        CafeteriaPurchase.objects.create(
            item=count_item, purchase_date=selected_date - timedelta(days=1), quantity=2, unit_price=10,
        )

        response = self.client.get(reverse('cafe_purchase_list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['daily_groups']), 2)
        first_group = response.context['daily_groups'][0]
        self.assertEqual(first_group['date'], selected_date)
        self.assertEqual(first_group['movement_count'], 2)
        self.assertEqual(first_group['total_amount'], 350)
        self.assertEqual(response.context['grand_total'], 370)
        self.assertContains(response, 'daily-summary-row')
        self.assertContains(response, 'دبل كليك')
        self.assertContains(response, '500 جرام')
