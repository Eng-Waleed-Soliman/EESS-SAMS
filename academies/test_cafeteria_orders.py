from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CafeteriaCategory, CafeteriaItem


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
                (100, 'مشروبات ساقعة'),
                (200, 'مشروبات ساخنة'),
                (500, 'مأكولات'),
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
        self.assertContains(response, 'grid-template-columns:repeat(4')
        self.assertContains(response, '@media(max-width:576px)')
        for title, image, code in (
            ('مشروبات ساقعة', 'cafe-cold-drinks.webp', 100),
            ('مشروبات ساخنة', 'cafe-hot-drinks.webp', 200),
            ('مأكولات', 'cafe-food.webp', 500),
            ('سناكس وآيس كريم', 'cafe-snacks-icecream.webp', 400),
        ):
            self.assertContains(response, title)
            self.assertContains(response, image)
            self.assertNotContains(response, 'cafe-juices.webp')
            self.assertContains(
                response,
                reverse('cafe_order_category', args=[self.categories[code].pk]),
            )

    def test_category_card_opens_bilingual_items_and_prices_page(self):
        category = self.categories[100]
        category.name_en = 'Cold Drinks'
        category.save(update_fields=['name_en'])
        item = CafeteriaItem.objects.create(
            category=category,
            code=101,
            name='مياه معدنية',
            name_en='Mineral Water',
            sale_price=15,
            staff_sale_price=10,
        )
        CafeteriaItem.objects.create(
            category=category,
            code=102,
            name='صنف غير نشط',
            name_en='Inactive Item',
            sale_price=20,
            is_active=False,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse('cafe_order_category', args=[category.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'academies/cafe_order_category.html')
        self.assertContains(response, category.name)
        self.assertContains(response, category.name_en)
        self.assertContains(response, 'class="category-menu-brand"')
        self.assertContains(response, 'TIME')
        self.assertContains(response, 'OUT')
        self.assertContains(response, '☕')
        self.assertContains(response, '⚽')
        self.assertContains(response, '🏋')
        self.assertContains(response, '🏊')
        self.assertContains(response, '🥤')
        self.assertContains(response, item.name)
        self.assertContains(response, item.name_en)
        self.assertContains(response, '10 جنيه')
        self.assertNotContains(response, '15 جنيه')
        self.assertNotContains(response, 'صنف غير نشط')
        self.assertNotContains(response, '<th scope="col">الكود</th>', html=True)
        self.assertNotContains(response, '<th scope="col">النوع</th>', html=True)
        self.assertNotContains(response, item.get_item_type_display())
        self.assertContains(response, 'text-align:center')
        self.assertContains(response, '@media(max-width:768px)')

    def test_unknown_category_returns_404(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('cafe_order_category', args=[999999]))

        self.assertEqual(response.status_code, 404)

    def test_orders_link_is_between_menu_and_inventory(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('cafe_sale_list'))
        html = response.content.decode()
        dropdown_start = html.index('class="cafe-actions-dropdown"')
        dropdown_end = html.index('</div>', dropdown_start)
        dropdown = html[dropdown_start:dropdown_end]

        self.assertLess(dropdown.index(reverse('cafe_menu')), dropdown.index(reverse('cafe_orders')))
        self.assertLess(dropdown.index(reverse('cafe_orders')), dropdown.index(reverse('cafe_inventory')))
        self.assertContains(response, 'const minimumMenuVisibilityMs = 1000')
        self.assertContains(response, "cafeActionsMenu.addEventListener('mouseenter'")
        self.assertContains(response, "cafeActionsMenu.addEventListener('mouseleave'")
        self.assertContains(response, 'closeCafeActionsMenuAfterMinimumTime')
        self.assertContains(response, "if(!cafeActionsMenu.contains(event.target))")

    def test_cafeteria_specialist_can_open_orders_page(self):
        specialist = User.objects.create_user(
            username='cafeteria_specialist',
            password='test-password',
        )
        self.client.force_login(specialist)

        response = self.client.get(reverse('cafe_orders'))

        self.assertEqual(response.status_code, 200)
