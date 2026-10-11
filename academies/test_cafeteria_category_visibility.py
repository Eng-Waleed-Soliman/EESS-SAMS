import json
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import CafeteriaCategoryForm, CafeteriaItemForm
from .models import CafeteriaCategory, CafeteriaItem, CafeteriaSale


@override_settings(SECURE_SSL_REDIRECT=False)
class CafeteriaCategoryVisibilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='category-visibility', password='password')
        self.client.force_login(self.user)

    def test_new_category_is_visible_in_sales_by_default(self):
        category = CafeteriaCategory.objects.create(code=900, name='Future category')

        response = self.client.get(reverse('cafe_sale_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-category="{category.id}"')
        self.assertContains(response, category.name)
        self.assertTrue(category.show_in_sales)

    def test_hidden_category_and_its_items_do_not_appear_or_accept_sales(self):
        category = CafeteriaCategory.objects.create(
            code=901, name='Hidden category', show_in_sales=False,
        )
        item = CafeteriaItem.objects.create(
            category=category, code=901, name='Hidden item',
            opening_quantity=10, purchase_price=5, sale_price=10,
        )

        response = self.client.get(reverse('cafe_sale_list'))

        self.assertNotContains(response, f'data-category="{category.id}"')
        self.assertNotContains(response, category.name)
        self.assertNotContains(response, item.name)
        self.assertNotIn(item.pk, [row['id'] for row in response.context['items']])

        sale_response = self.client.post(reverse('cafe_sale_list'), {
            'sale_date': date.today().isoformat(),
            'checkout_action': 'sale',
            'order_items': json.dumps([{'item_id': item.pk, 'quantity': 1}]),
        })
        self.assertRedirects(sale_response, reverse('cafe_sale_list'))
        self.assertFalse(CafeteriaSale.objects.filter(item=item).exists())

    def test_category_form_controls_sales_visibility(self):
        page = self.client.get(reverse('cafe_category_create'))
        self.assertContains(page, 'name="show_in_sales"')
        self.assertContains(page, 'الظهور في حركات البيع')
        self.assertContains(page, 'checked')

        form = CafeteriaCategoryForm(data={
            'code': 902,
            'name': 'Not for sales',
            'notes': '',
        })
        self.assertTrue(form.is_valid(), form.errors.as_json())
        category = form.save()
        self.assertFalse(category.show_in_sales)

    def test_item_form_requires_a_category(self):
        form = CafeteriaItemForm(data={
            'code': 903,
            'name': 'Uncategorized item',
            'item_type': 'count',
            'opening_quantity': 1,
            'purchase_price': 1,
            'sale_price': 2,
            'notes': '',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('category', form.errors)