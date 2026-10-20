import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    CafeteriaCategory,
    CafeteriaItem,
    CafeteriaStaffOrder,
)


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
            image_data=b'item-image',
            image_content_type='image/png',
            image_name='water.png',
            opening_quantity=10,
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
        self.assertTemplateUsed(response, 'academies/cafe_order_mobile.html')
        self.assertContains(response, category.name)
        self.assertContains(response, category.name_en)
        self.assertContains(response, 'class="mobile-products-grid"')
        self.assertContains(response, 'class="mobile-product-card"')
        self.assertContains(response, 'id="quantityDialog"')
        self.assertContains(response, 'id="checkoutDialog"')
        self.assertContains(response, 'طلب فئات أخرى')
        self.assertContains(response, 'تنفيذ الأوردر')
        self.assertContains(response, 'تفريغ الأوردر')
        self.assertContains(response, 'id="clearOrderButton"')
        self.assertContains(response, "checkoutCount.textContent=count?'( '+count+' )':''")
        self.assertContains(response, "cart=[];saveCart()")
        self.assertContains(response, 'width:125px!important')
        self.assertContains(response, 'مكان الاستلام')
        self.assertContains(response, 'المكتب')
        self.assertContains(response, 'الكافيتريا')
        self.assertContains(response, item.name)
        self.assertContains(response, item.name_en)
        self.assertContains(
            response,
            reverse('persistent_media', args=['cafeteria_item', item.pk, 'image']),
        )
        self.assertContains(response, '10 جنيه')
        self.assertNotContains(response, '15 جنيه')
        self.assertNotContains(response, 'صنف غير نشط')
        self.assertContains(response, 'top:8px;left:8px')
        self.assertContains(response, '@media(max-width:768px)')

    def test_employee_order_reaches_specialist_and_can_be_completed(self):
        category = self.categories[100]
        item = CafeteriaItem.objects.create(
            category=category,
            code=110,
            name='مياه اختبار',
            opening_quantity=20,
            sale_price=15,
            staff_sale_price=10,
        )
        employee = User.objects.create_user(
            username='mobile.employee',
            first_name='موظف الطلب',
            password='test-password',
        )
        self.client.force_login(employee)
        response = self.client.post(reverse('cafe_staff_order_submit'), {
            'order_items': json.dumps([{'item_id': item.pk, 'quantity': 3}]),
            'delivery_place': CafeteriaStaffOrder.PLACE_OFFICE,
            'notes': 'بدون ثلج',
        })
        self.assertRedirects(response, f"{reverse('cafe_orders')}?ordered=1")
        order = CafeteriaStaffOrder.objects.prefetch_related('items').get()
        self.assertEqual(order.requested_by, employee)
        self.assertEqual(order.requester_name, 'موظف الطلب')
        self.assertEqual(order.delivery_place, CafeteriaStaffOrder.PLACE_OFFICE)
        self.assertEqual(order.notes, 'بدون ثلج')
        self.assertEqual(order.total_amount, 30)
        line = order.items.get()
        self.assertEqual(line.item_name, 'مياه اختبار')
        self.assertEqual(line.quantity, 3)
        self.assertEqual(line.unit_price, 10)

        specialist = User.objects.create_user(
            username='Cafeteria_Specialist',
            password='test-password',
        )
        self.client.force_login(specialist)
        specialist_page = self.client.get(reverse('cafe_sale_list'))
        self.assertContains(specialist_page, 'class="incoming-orders-card"')
        self.assertContains(specialist_page, 'موظف الطلب')
        self.assertContains(specialist_page, 'مياه اختبار × 3')
        self.assertContains(specialist_page, 'بدون ثلج')
        self.assertContains(specialist_page, 'المكتب')
        self.assertContains(specialist_page, '30 جنيه')

        response = self.client.post(reverse('cafe_staff_order_complete', args=[order.pk]))
        self.assertRedirects(response, reverse('cafe_sale_list'))
        order.refresh_from_db()
        self.assertEqual(order.status, CafeteriaStaffOrder.STATUS_COMPLETED)
        self.assertIsNotNone(order.completed_at)

    def test_order_database_failure_rolls_back_and_returns_to_orders_page(self):
        category = self.categories[100]
        item = CafeteriaItem.objects.create(
            category=category,
            code=111,
            name='طلب لن يكتمل',
            opening_quantity=20,
            sale_price=15,
            staff_sale_price=10,
        )
        employee = User.objects.create_user(
            username='database.failure.employee',
            password='test-password',
        )
        self.client.force_login(employee)

        with patch(
            'academies.views.CafeteriaStaffOrderItem.objects.bulk_create',
            side_effect=DatabaseError('database unavailable'),
        ):
            response = self.client.post(reverse('cafe_staff_order_submit'), {
                'order_items': json.dumps([{'item_id': item.pk, 'quantity': 2}]),
                'delivery_place': CafeteriaStaffOrder.PLACE_CAFETERIA,
                'notes': '',
            })

        self.assertRedirects(response, reverse('cafe_orders'))
        self.assertFalse(CafeteriaStaffOrder.objects.exists())

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

    def test_specialist_sales_page_survives_pending_orders_database_failure(self):
        specialist = User.objects.create_user(
            username='Cafeteria_Specialist',
            password='test-password',
        )
        self.client.force_login(specialist)

        with patch(
            'academies.views.CafeteriaStaffOrder.objects.filter',
            side_effect=DatabaseError('pending orders table unavailable'),
        ):
            response = self.client.get(reverse('cafe_sale_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'شاشة البيع ما زالت متاحة')
        self.assertContains(response, 'class="incoming-orders-card"')
