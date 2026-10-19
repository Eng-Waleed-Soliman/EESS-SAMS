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

    def test_item_form_keeps_arabic_and_english_names_without_images(self):
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
        )

        self.assertTrue(form.is_valid(), form.errors.as_json())
        item = form.save()
        item.refresh_from_db()
        self.assertEqual(item.name, 'ساندوتش')
        self.assertEqual(item.name_en, 'Sandwich')
        self.assertIsNone(item.image_data)
        self.assertEqual(item.image_content_type, '')
        self.assertEqual(item.image_name, '')

        page = self.client.get(reverse('cafe_item_update', args=[item.pk]))
        self.assertContains(page, 'name="name"')
        self.assertContains(page, 'name="name_en"')
        self.assertNotContains(page, 'name="image"')
        self.assertNotContains(page, 'multipart/form-data')
    def test_sales_page_has_html_brand_header_and_collapsible_actions_menu(self):
        category = CafeteriaCategory.objects.create(code=9963, name='مخزون منخفض')
        CafeteriaItem.objects.create(
            category=category,
            code=9964,
            name='صنف منخفض المخزون',
            item_type=CafeteriaItem.TYPE_COUNT,
            opening_quantity=8,
            stock_adjustment=-8,
            purchase_price=10,
            sale_price=20,
        )

        response = self.client.get(reverse('cafe_sale_list'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'academies/images/timeout-cafe-logo.png')
        self.assertContains(response, 'class="cafe-brand-banner"')
        self.assertContains(response, 'class="cafe-brand-time">TIME')
        self.assertContains(response, 'class="cafe-brand-out">OUT')
        self.assertContains(response, 'EAT <b>•</b> DRINK <b>•</b> RECHARGE')
        self.assertContains(response, 'class="cafe-screen-title">شاشة البيع')
        self.assertContains(response, 'class="cafe-actions-toggle"')
        self.assertContains(response, 'class="cafe-actions-dropdown"')
        self.assertContains(response, 'class="card sales-summary-card"')
        self.assertContains(response, 'class="sales-summary-value"')
        self.assertContains(response, '.sales-summary-card{position:absolute;top:70px;right:0;width:180px')
        self.assertContains(response, '.sales-summary-card strong{font-weight:900')
        self.assertContains(response, '.cafe-page-header{position:relative;min-height:190px')
        self.assertContains(response, 'class="cafe-category-card__media cafe-category-card__all"')
        self.assertContains(response, 'class="cafe-category-card__label">كل الفئات')
        self.assertContains(response, 'academies/images/cafe-food.webp')
        self.assertContains(response, 'academies/images/cafe-cold-drinks.webp')
        self.assertNotContains(response, '<b>عدد الحركات</b>')
        self.assertNotContains(response, '<b>الربح التقديري</b>')
        self.assertContains(response, 'class="low-stock-table')
        self.assertContains(response, 'صنف منخفض المخزون')
        for route_name in (
            'cafe_category_list', 'cafe_item_list', 'cafe_purchase_list',
            'cafe_menu', 'cafe_inventory', 'cafe_cash_supply_create',
        ):
            self.assertContains(response, reverse(route_name))
