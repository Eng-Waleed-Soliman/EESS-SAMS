import json
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    CafeteriaCategory,
    CafeteriaItem,
    CafeteriaSale,
    CafeteriaStaffOrder,
)


class FakeBicchubResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode('utf-8')


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

        english_response = self.client.get(
            reverse('cafe_order_category', args=[category.pk]),
            {'lang': 'en'},
        )
        self.assertContains(english_response, 'Display language')
        self.assertContains(english_response, item.name_en)
        self.assertContains(english_response, 'Other Categories')
        self.assertContains(english_response, 'Clear Order')
        self.assertContains(english_response, 'Submit Order')
        self.assertContains(english_response, 'Pickup Location')
        self.assertContains(english_response, 'value="en"')
        english_orders = self.client.get(reverse('cafe_orders'))
        self.assertContains(english_orders, 'Choose a category')
        self.assertContains(english_orders, 'Cold Drinks')
        self.assertContains(english_orders, 'Previous Orders')

    def test_item_without_image_does_not_repeat_the_category_image(self):
        category = self.categories[100]
        category.image_data = b'category-image'
        category.image_content_type = 'image/webp'
        category.image_name = 'cold-drinks.webp'
        category.save(update_fields=['image_data', 'image_content_type', 'image_name'])
        item = CafeteriaItem.objects.create(
            category=category,
            code=199,
            name='صنف بدون صورة',
            opening_quantity=5,
            sale_price=20,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse('cafe_order_category', args=[category.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            reverse('persistent_media', args=['cafeteria_category', category.pk, 'image']),
        )
        self.assertContains(response, f'<small>{item.code}</small>', html=True)

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
        self.assertContains(specialist_page, 'class="incoming-orders-minimize"')
        self.assertContains(specialist_page, 'data-live-url=')
        self.assertContains(specialist_page, 'موظف الطلب')
        self.assertContains(specialist_page, 'مياه اختبار × 3')
        self.assertContains(specialist_page, 'بدون ثلج')
        self.assertContains(specialist_page, 'المكتب')
        self.assertContains(specialist_page, '30 جنيه')
        live_orders = self.client.get(reverse('cafe_staff_orders_live'))
        self.assertEqual(live_orders.status_code, 200)
        self.assertEqual(live_orders['Cache-Control'], 'no-store')
        self.assertContains(live_orders, f'data-latest-order-id="{order.pk}"')
        self.assertContains(live_orders, 'تصغير شاشة الأوردرات')

        response = self.client.post(reverse('cafe_staff_order_complete', args=[order.pk]))
        self.assertRedirects(response, reverse('cafe_sale_list'))
        order.refresh_from_db()
        self.assertEqual(order.status, CafeteriaStaffOrder.STATUS_COMPLETED)
        self.assertIsNotNone(order.completed_at)
        self.assertEqual(CafeteriaSale.objects.filter(notes__contains=f'#{order.pk}').count(), 1)
        self.client.post(reverse('cafe_staff_order_complete', args=[order.pk]))
        self.assertEqual(CafeteriaSale.objects.filter(notes__contains=f'#{order.pk}').count(), 1)

    def test_bicchub_employee_sso_creates_restricted_identity_and_history(self):
        payload = {
            'valid': True,
            'employee': {
                'employeeId': 'EMP-215',
                'employeeName': 'أحمد موظف',
                'jobTitle': 'مسؤول إداري',
                'department': 'الموارد البشرية',
                'academicYear': '2026-2027',
                'notificationToken': 'signed-notification-token',
            },
        }
        with patch('academies.views.urlopen', return_value=FakeBicchubResponse(payload)):
            response = self.client.get(reverse('cafeteria_external_access'), {
                'token': 'signed-token',
                'mode': 'history',
            })
        redirect_url = response['Location']
        self.assertEqual(urlparse(redirect_url).path, reverse('cafe_order_history'))
        access_token = parse_qs(urlparse(redirect_url).query)['access'][0]
        identity = self.client.session['external_cafeteria_employee']
        self.assertEqual(identity['employee_id'], 'EMP-215')
        self.assertEqual(identity['job_title'], 'مسؤول إداري')
        self.assertTrue(User.objects.filter(username__startswith='bicchub_').exists())

        category = self.categories[100]
        item = CafeteriaItem.objects.create(
            category=category, code=118, name='طلب موظف خارجي', name_en='External Employee Order',
            opening_quantity=10, sale_price=30, staff_sale_price=20,
        )
        self.client.cookies.clear()
        category_page = self.client.get(
            reverse('cafe_order_category', args=[category.pk]),
            {'access': access_token},
        )
        self.assertEqual(category_page.status_code, 200)
        self.assertContains(category_page, 'طلب موظف خارجي')
        self.assertContains(category_page, f'name="access" value="{access_token}"')

        self.client.cookies.clear()
        response = self.client.post(reverse('cafe_staff_order_submit'), {
            'order_items': json.dumps([{'item_id': item.pk, 'quantity': 2}]),
            'delivery_place': CafeteriaStaffOrder.PLACE_CAFETERIA,
            'notes': 'اختبار الربط',
            'access': access_token,
        })
        self.assertEqual(urlparse(response['Location']).path, reverse('cafe_orders'))
        self.assertEqual(parse_qs(urlparse(response['Location']).query)['ordered'], ['1'])
        self.assertEqual(parse_qs(urlparse(response['Location']).query)['access'], [access_token])
        order = CafeteriaStaffOrder.objects.get()
        self.assertEqual(order.external_employee_id, 'EMP-215')
        self.assertEqual(order.requester_name, 'أحمد موظف')
        self.assertEqual(order.requester_job_title, 'مسؤول إداري')
        self.assertEqual(order.external_notification_token, 'signed-notification-token')
        self.assertEqual(order.total_amount, 40)
        history = self.client.get(reverse('cafe_order_history'))
        self.assertContains(history, 'طلب موظف خارجي × 2')
        self.assertContains(history, '40 جنيه')
        english_history = self.client.get(reverse('cafe_order_history'), {'lang': 'en'})
        self.assertContains(english_history, 'Previous Orders')
        self.assertContains(english_history, 'External Employee Order × 2')
        self.assertContains(english_history, '40 EGP')
        self.assertContains(english_history, 'Pickup Location')
        self.assertContains(english_history, 'Cafeteria')
        restricted = self.client.get(reverse('dashboard'))
        self.assertRedirects(restricted, reverse('login'))

    def test_bicchub_cafeteria_link_preserves_existing_eess_login(self):
        self.client.force_login(self.admin)
        payload = {
            'valid': True,
            'employee': {
                'employeeId': 'EMP-ADMIN',
                'employeeName': 'مدير مسجل',
                'jobTitle': 'مدير النظام',
                'department': 'الإدارة',
                'academicYear': '2026-2027',
            },
        }
        with patch('academies.views.urlopen', return_value=FakeBicchubResponse(payload)):
            response = self.client.get(reverse('cafeteria_external_access'), {
                'token': 'signed-token',
                'mode': 'new',
            })
        self.assertEqual(urlparse(response['Location']).path, reverse('cafe_orders'))
        self.assertIn('access', parse_qs(urlparse(response['Location']).query))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.admin.pk)
        orders_page = self.client.get(reverse('cafe_orders'))
        self.assertContains(orders_page, 'class="sidebar')
        dashboard = self.client.get(reverse('dashboard'))
        self.assertEqual(dashboard.status_code, 200)
        self.assertNotIn('external_cafeteria_employee', self.client.session)

    def test_bicchub_can_fetch_external_employee_order_statuses(self):
        employee = User.objects.create_user(username='external-order-owner')
        order = CafeteriaStaffOrder.objects.create(
            requested_by=employee,
            requester_name='أحمد موظف',
            requester_job_title='مسؤول إداري',
            external_employee_id='EMP-215',
            delivery_place=CafeteriaStaffOrder.PLACE_OFFICE,
            status=CafeteriaStaffOrder.STATUS_PREPARING,
        )
        order.items.create(
            item_name='قهوة',
            quantity=2,
            unit_price=25,
        )
        payload = {
            'valid': True,
            'employee': {
                'employeeId': 'EMP-215',
                'employeeName': 'أحمد موظف',
                'jobTitle': 'مسؤول إداري',
                'department': 'الموارد البشرية',
                'academicYear': '2026-2027',
                'notificationToken': 'refreshed-notification-token',
            },
        }
        with patch('academies.views.urlopen', return_value=FakeBicchubResponse(payload)):
            response = self.client.post(
                reverse('cafeteria_external_order_status'),
                data=json.dumps({'token': 'signed-token'}),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['employeeId'], 'EMP-215')
        self.assertEqual(result['orders'][0]['id'], order.pk)
        self.assertEqual(result['orders'][0]['status'], 'preparing')
        self.assertEqual(result['orders'][0]['statusLabel'], 'جاري التجهيز')
        self.assertEqual(result['orders'][0]['itemsCount'], 2)
        self.assertEqual(result['orders'][0]['total'], 50)
        order.refresh_from_db()
        self.assertEqual(order.external_notification_token, 'refreshed-notification-token')

    def test_specialist_order_status_workflow_exposes_required_details(self):
        item = CafeteriaItem.objects.create(
            category=self.categories[100], code=117, name='قهوة موظف',
            opening_quantity=12, sale_price=40, staff_sale_price=25,
        )
        employee = User.objects.create_user(username='linked.employee')
        order = CafeteriaStaffOrder.objects.create(
            requested_by=employee,
            requester_name='منى محمود',
            requester_job_title='مديرة مكتب',
            external_employee_id='EMP-9',
            external_notification_token='signed-notification-token',
            delivery_place=CafeteriaStaffOrder.PLACE_OFFICE,
            notes='سكر قليل',
        )
        order.items.create(item=item, item_name=item.name, quantity=2, unit_price=25)
        specialist = User.objects.create_user(username='Cafeteria_Specialist')
        self.client.force_login(specialist)
        page = self.client.get(reverse('cafe_sale_list'))
        for expected in ('أوردر #', 'منى محمود', 'مديرة مكتب', 'المكتب', 'سكر قليل', '25 جنيه للصنف', '50 جنيه', 'تم الإرسال'):
            self.assertContains(page, expected)
        with patch('academies.views.urlopen') as notify, self.captureOnCommitCallbacks(execute=True):
            notify.return_value.__enter__.return_value.status = 200
            self.client.post(reverse('cafe_staff_order_complete', args=[order.pk]), {'status': 'preparing'})
        notify.assert_called_once()
        notification = json.loads(notify.call_args.args[0].data.decode('utf-8'))
        self.assertEqual(notification, {
            'token': 'signed-notification-token',
            'orderId': order.pk,
            'status': 'preparing',
        })
        order.refresh_from_db()
        self.assertEqual(order.status, CafeteriaStaffOrder.STATUS_PREPARING)
        self.client.post(reverse('cafe_staff_order_complete', args=[order.pk]), {'status': 'ready'})
        order.refresh_from_db()
        self.assertEqual(order.status, CafeteriaStaffOrder.STATUS_READY)
        self.client.post(reverse('cafe_staff_order_complete', args=[order.pk]), {'status': 'completed'})
        order.refresh_from_db()
        self.assertEqual(order.status, CafeteriaStaffOrder.STATUS_COMPLETED)
        self.assertEqual(CafeteriaSale.objects.filter(notes__contains=f'#{order.pk}').count(), 1)

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

    def test_missing_sale_delete_returns_to_sales_instead_of_404(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('cafe_sale_delete', args=[10279]),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[-1][0], reverse('cafe_sale_list'))
        self.assertContains(response, 'تم حذفها بالفعل')

    def test_existing_sale_still_opens_delete_confirmation(self):
        item = CafeteriaItem.objects.create(
            category=self.categories[100],
            code=119,
            name='صنف قابل للحذف',
            opening_quantity=10,
            sale_price=10,
        )
        sale = CafeteriaSale.objects.create(
            item=item,
            sale_date='2026-10-20',
            quantity=1,
            unit_price=10,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse('cafe_sale_delete', args=[sale.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'حذف حركة بيع كافيتريا')
