from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import CafeteriaItemForm
from .models import CafeteriaCategory


@override_settings(SECURE_SSL_REDIRECT=False)
class CafeteriaCategoryVisibilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='category-visibility', password='password')
        self.client.force_login(self.user)

    def test_new_empty_category_appears_on_sales_screen(self):
        category = CafeteriaCategory.objects.create(code=900, name='Future category')

        response = self.client.get(reverse('cafe_sale_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-category="{category.id}"')
        self.assertContains(response, category.name)

    def test_item_form_requires_a_category(self):
        form = CafeteriaItemForm(data={
            'code': 901,
            'name': 'Uncategorized item',
            'item_type': 'count',
            'opening_quantity': 1,
            'purchase_price': 1,
            'sale_price': 2,
            'notes': '',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('category', form.errors)
