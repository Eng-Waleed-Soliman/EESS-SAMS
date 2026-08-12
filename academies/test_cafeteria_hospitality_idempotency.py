import json
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CafeteriaHospitality, CafeteriaItem, CafeteriaSale, Shareholder


@override_settings(SECURE_SSL_REDIRECT=False)
class CafeteriaHospitalityIdempotencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='hospitality-idempotency', password='password')
        self.client.force_login(self.user)

    def test_same_order_token_cannot_be_saved_as_hospitality_then_sale(self):
        member = Shareholder.objects.create(name='Board member', share_percentage=100)
        item = CafeteriaItem.objects.create(
            code=501, name='Ice cream', opening_quantity=20, sale_price=25,
        )
        order = json.dumps([{'item_id': item.id, 'quantity': 8}])
        token = 'one-order-one-result'

        first = self.client.post(reverse('cafe_sale_list'), {
            'order_items': order,
            'order_token': token,
            'checkout_action': 'hospitality',
            'sale_date': date.today().isoformat(),
            'hospitality_board_member': member.id,
            'hospitality_employee_name': 'Employee',
        })
        second = self.client.post(reverse('cafe_sale_list'), {
            'order_items': order,
            'order_token': token,
            'checkout_action': 'sale',
            'sale_date': date.today().isoformat(),
        })

        self.assertRedirects(first, reverse('cafe_sale_list'))
        self.assertRedirects(second, reverse('cafe_sale_list'))
        self.assertEqual(CafeteriaHospitality.objects.count(), 1)
        self.assertFalse(CafeteriaSale.objects.exists())
        self.assertEqual(item.stock_quantity, 12)
