import json
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .constants import OPERATION_PLACE_CHOICES, TIME_CHOICES
from .models import (
    Academy,
    CafeteriaCategory,
    CafeteriaItem,
    CafeteriaPurchase,
    CafeteriaSale,
    DailyBooking,
    DailyBookingCheckout,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class ApplicationFlowsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='test-password')
        self.client.force_login(self.user)

    def test_academy_create_and_edit_keep_browser_date_format(self):
        place = OPERATION_PLACE_CHOICES[0][0]
        start = date.today()
        end = start + timedelta(days=30)
        payload = {
            'name': 'أكاديمية اختبار',
            'sport_activity': 'كرة قدم',
            'company_name': 'شركة اختبار',
            'manager_name': 'مدير اختبار',
            'manager_national_id': '',
            'manager_phone': '01000000000',
            'contract_start_date': start.isoformat(),
            'contract_end_date': end.isoformat(),
            'subscription_type': 'fixed',
            'monthly_subscription': 1000,
            'eess_share_percentage': 0,
            'security_deposit': 500,
            'training_schedule_data': json.dumps([{'place': place}]),
            'operation_place': place,
            'notes': '',
        }
        response = self.client.post(reverse('academy_create'), payload)
        self.assertRedirects(response, reverse('academy_list'))
        academy = Academy.objects.get(name='أكاديمية اختبار')
        response = self.client.get(reverse('academy_update', args=[academy.pk]))
        self.assertContains(response, f'value="{start.isoformat()}"')
        self.assertContains(response, f'value="{end.isoformat()}"')

    def test_cafeteria_sale_uses_configured_price_and_inventory_period(self):
        category = CafeteriaCategory.objects.create(code=1, name='مشروبات')
        item = CafeteriaItem.objects.create(
            category=category, code=1, name='مياه', opening_quantity=2,
            purchase_price=5, sale_price=10,
        )
        CafeteriaPurchase.objects.create(
            item=item, purchase_date=date.today(), quantity=8, unit_price=5,
        )
        response = self.client.post(reverse('cafe_sale_list'), {
            'sale_date': date.today().isoformat(),
            'notes': '',
            'order_items': json.dumps([{'item_id': item.pk, 'quantity': 3, 'unit_price': 999}]),
        })
        self.assertRedirects(response, reverse('cafe_sale_list'))
        sale = CafeteriaSale.objects.get(item=item)
        self.assertEqual(sale.unit_price, 10)
        response = self.client.get(reverse('cafe_inventory'), {'preset': 'today'})
        self.assertContains(response, 'جرد الكافيتريا')
        self.assertContains(response, '<td>8</td>', html=True)
        self.assertContains(response, '<td>3</td>', html=True)
        self.assertContains(response, '<td class="fw-bold">7</td>', html=True)

    def test_daily_booking_checkout_from_operation(self):
        booking = DailyBooking.objects.create(
            venue=OPERATION_PLACE_CHOICES[0][0], booking_date=date.today(),
            start_time=TIME_CHOICES[0][0], end_time=TIME_CHOICES[1][0],
            customer_name='عميل اختبار', customer_phone='01111111111',
            players_count=1, amount=200, advance_payment=50,
            total_amount=200, remaining_amount=150,
        )
        response = self.client.post(reverse('operation_card_action'), {
            'action': 'checkout', 'item_type': 'daily', 'item_id': booking.pk,
            'date': date.today().isoformat(), 'period': 'all',
        })
        self.assertEqual(response.status_code, 302)
        checkout = DailyBookingCheckout.objects.get(booking=booking)
        self.assertEqual(checkout.total_amount, 200)
        self.assertEqual(checkout.remaining_amount, 150)
