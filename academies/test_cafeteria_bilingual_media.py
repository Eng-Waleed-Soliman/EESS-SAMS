from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import CafeteriaCategoryForm, CafeteriaItemForm
from .models import CafeteriaCategory, CafeteriaItem


PNG_BYTES = (
    b'\x89PNG\r\n\x1a\n'
    b'\x00\x00\x00\rIHDR'
    b'\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00'
)


@override_settings(SECURE_SSL_REDIRECT=False)
class CafeteriaBilingualMediaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='cafeteria-media-admin',
            email='cafeteria-media@example.com',
            password='test-password',
        )
        self.client.force_login(self.user)

    def uploaded_image(self, name='cafe.png'):
        return SimpleUploadedFile(name, PNG_BYTES, content_type='image/png')

    def test_category_form_saves_english_name_and_image_in_database(self):
        form = CafeteriaCategoryForm(
            data={
                'code': 9960,
                'name': 'مشروبات باردة',
                'name_en': 'Cold Drinks',
                'show_in_sales': 'on',
                'notes': '',
            },
            files={'image': self.uploaded_image('category.png')},
        )

        self.assertTrue(form.is_valid(), form.errors.as_json())
        category = form.save()
        category.refresh_from_db()
        self.assertEqual(category.name_en, 'Cold Drinks')
        self.assertEqual(bytes(category.image_data), PNG_BYTES)
        self.assertEqual(category.image_content_type, 'image/png')
        self.assertTrue(category.image_data_uri.startswith('data:image/png;base64,'))

        page = self.client.get(reverse('cafe_category_update', args=[category.pk]))
        self.assertContains(page, 'name="name_en"')
        self.assertContains(page, 'name="image"')
        self.assertContains(page, 'multipart/form-data')
        self.assertContains(page, 'data:image/png;base64,')

    def test_item_form_saves_english_name_and_image_in_database(self):
        category = CafeteriaCategory.objects.create(code=9961, name='وجبات')
        form = CafeteriaItemForm(
            data={
                'category': category.pk,
                'code': 9962,
                'name': 'ساندوتش',
                'name_en': 'Sandwich',
                'item_type': CafeteriaItem.TYPE_COUNT,
                'opening_quantity': 5,
                'purchase_price': 10,
                'sale_price': 20,
                'notes': '',
            },
            files={'image': self.uploaded_image('item.png')},
        )

        self.assertTrue(form.is_valid(), form.errors.as_json())
        item = form.save()
        item.refresh_from_db()
        self.assertEqual(item.name_en, 'Sandwich')
        self.assertEqual(bytes(item.image_data), PNG_BYTES)
        self.assertEqual(item.image_content_type, 'image/png')

        page = self.client.get(reverse('cafe_item_update', args=[item.pk]))
        self.assertContains(page, 'name="name_en"')
        self.assertContains(page, 'name="image"')
        self.assertContains(page, 'multipart/form-data')
        self.assertContains(page, 'data:image/png;base64,')

    def test_sales_page_has_centered_logo_and_collapsible_actions_menu(self):
        response = self.client.get(reverse('cafe_sale_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'academies/images/timeout-cafe-logo.png')
        self.assertContains(response, 'class="cafe-actions-toggle"')
        self.assertContains(response, 'class="cafe-actions-dropdown"')
        for route_name in (
            'cafe_category_list', 'cafe_item_list', 'cafe_purchase_list',
            'cafe_menu', 'cafe_inventory', 'cafe_cash_supply_create',
        ):
            self.assertContains(response, reverse(route_name))