from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CafeteriaCategory


@override_settings(SECURE_SSL_REDIRECT=False)
class CafeteriaOrdersPageTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='cafeteria-orders-admin',
            email='orders@example.com',
            password='test-password',
        )
        self.categories = {
            code: CafeteriaCategory.objects.create(code=code, name=name)
            for code, name in (
                (100, 'مشروبات غازية'),
                (200, 'مشروبات ساخنة'),
                (300, 'عصائر'),
                (400, 'سناكس'),
            )
        }

    def test_orders_page_uses_timeout_header_and_supplied_category_cards(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('cafe_orders'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'academies/cafe_orders.html')
        self.assertContains(response, 'class="orders-brand"')
        self.assertContains(response, 'TIME')
        self.assertContains(response, 'OUT')
        for title, image, code in (
            ('مشروبات غازية', 'cafe-soft-drinks.webp', 100),
            ('مشروبات ساخنة', 'cafe-hot-drinks.webp', 200),
            ('عصائر', 'cafe-juices.webp', 300),
            ('سناكس وآيس كريم', 'cafe-snacks-icecream.webp', 400),
        ):
            self.assertContains(response, title)
            self.assertContains(response, image)
            self.assertContains(
                response,
                f'{reverse("cafe_sale_list")}?category={self.categories[code].pk}',
            )

    def test_orders_link_is_between_menu_and_inventory(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('cafe_sale_list'))
        html = response.content.decode()
        dropdown_start = html.index('class="cafe-actions-dropdown"')
        dropdown_end = html.index('</div>', dropdown_start)
        dropdown = html[dropdown_start:dropdown_end]

        self.assertLess(dropdown.index(reverse('cafe_menu')), dropdown.index(reverse('cafe_orders')))
        self.assertLess(dropdown.index(reverse('cafe_orders')), dropdown.index(reverse('cafe_inventory')))

    def test_cafeteria_specialist_can_open_orders_page(self):
        specialist = User.objects.create_user(
            username='cafeteria_specialist',
            password='test-password',
        )
        self.client.force_login(specialist)

        response = self.client.get(reverse('cafe_orders'))

        self.assertEqual(response.status_code, 200)