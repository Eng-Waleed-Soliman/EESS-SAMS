import json
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .constants import OPERATION_PLACE_CHOICES, TIME_CHOICES, WEEKDAY_AR
from .forms import AcademyForm, DailyBookingForm
from .views import _academy_schedule_occurrences_for_date, _calculate_variable_income_by_facility
from .models import (
    Academy,
    AcademyMember,
    CafeteriaCategory,
    CafeteriaItem,
    CafeteriaPurchase,
    CafeteriaSale,
    DailyBooking,
    DailyBookingCheckout,
    DailyExpense,
    UserPermission,
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

    def test_variable_academy_accepts_multiple_intervals_in_same_day(self):
        place = OPERATION_PLACE_CHOICES[0][0]
        selected_date = date.today()
        day_name = WEEKDAY_AR[selected_date.weekday()]
        schedule = [
            {'place': place, 'day': day_name, 'start_time': TIME_CHOICES[0][0], 'end_time': TIME_CHOICES[2][0], 'hourly_rent': 100},
            {'place': place, 'day': day_name, 'start_time': TIME_CHOICES[4][0], 'end_time': TIME_CHOICES[6][0], 'hourly_rent': 200},
        ]
        form = AcademyForm(data={
            'name': 'أكاديمية مواعيد متعددة', 'sport_activity': 'كرة قدم',
            'company_name': 'شركة اختبار', 'manager_name': 'مدير اختبار',
            'manager_phone': '01000000001', 'contract_start_date': selected_date.isoformat(),
            'contract_end_date': selected_date.isoformat(), 'subscription_type': 'variable',
            'monthly_subscription': 0, 'variable_rent_type': 'hour', 'variable_rent_value': 0,
            'eess_share_percentage': 0, 'security_deposit': 0,
            'training_schedule_data': json.dumps(schedule), 'operation_place': [place],
        })
        self.assertTrue(form.is_valid(), form.errors.as_json())
        academy = form.save()
        occurrences = _academy_schedule_occurrences_for_date(academy, selected_date)
        self.assertEqual(len(occurrences), 4)
        self.assertEqual(_calculate_variable_income_by_facility(academy, selected_date.year, selected_date.month), 300)

    def test_daily_booking_checkout_from_operation(self):
        booking = DailyBooking.objects.create(
            venue=OPERATION_PLACE_CHOICES[0][0], booking_date=date.today(),
            start_time=TIME_CHOICES[0][0], end_time=TIME_CHOICES[1][0],
            customer_name='عميل اختبار', customer_phone='01111111111',
            players_count=1, amount=200, advance_payment=50,
            total_amount=200, remaining_amount=150,
        )
        operation_response = self.client.get(reverse('operation_screen'), {'date': date.today().isoformat(), 'period': 'all'})
        self.assertContains(operation_response, 'operation-tooltip')
        self.assertContains(operation_response, 'operation-entry-data')
        self.assertContains(operation_response, 'عميل اختبار')
        response = self.client.post(reverse('operation_card_action'), {
            'action': 'checkout', 'item_type': 'daily', 'item_id': booking.pk,
            'date': date.today().isoformat(), 'period': 'all',
        })
        self.assertEqual(response.status_code, 302)
        checkout = DailyBookingCheckout.objects.get(booking=booking)
        self.assertEqual(checkout.total_amount, 200)
        self.assertEqual(checkout.remaining_amount, 150)

    def test_operation_daily_expense_records_user_and_is_in_reports(self):
        profile, _ = UserPermission.objects.get_or_create(user=self.user)
        profile.can_report_expenses = True
        profile.save()
        today = date.today()

        operation_response = self.client.get(reverse('operation_screen'), {'date': today.isoformat()})
        expected_create_url = reverse('daily_expense_create') + f'?date={today.isoformat()}'
        self.assertContains(operation_response, expected_create_url)
        self.assertNotContains(operation_response, reverse('daily_income') + f'?date={today.isoformat()}')

        response = self.client.post(reverse('daily_expense_create') + f'?date={today.isoformat()}', {
            'title': 'مصروف اختبار يومي',
            'expense_date': today.isoformat(),
            'amount': 125,
            'notes': 'اختبار اسم المدخل',
        })
        self.assertRedirects(response, reverse('daily_expense_list'))
        expense = DailyExpense.objects.get(title='مصروف اختبار يومي')
        self.assertEqual(expense.created_by, self.user)

        report_response = self.client.get(reverse('reports_home'), {
            'report_type': 'daily_expenses',
            'month': today.strftime('%Y-%m'),
        })
        self.assertContains(report_response, 'مصروف اختبار يومي')
        self.assertContains(report_response, self.user.username)

        old_module_response = self.client.get(reverse('daily_income'))
        self.assertRedirects(
            old_module_response,
            '/reports/?report_type=daily_booking_monthly',
            fetch_redirect_response=False,
        )

    def test_morning_operation_period_and_booking_prefill_from_available_slot(self):
        selected_date = date.today()
        place = OPERATION_PLACE_CHOICES[0][0]
        response = self.client.get(reverse('operation_screen'), {
            'date': selected_date.isoformat(),
            'period': 'morning',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['rows'][0]['cards']), 16)
        self.assertEqual(response.context['rows'][0]['cards'][0]['start_time'], TIME_CHOICES[0][0])
        self.assertEqual(response.context['rows'][0]['cards'][-1]['end_time'], TIME_CHOICES[16][0])
        self.assertContains(response, 'الفترة الصباحية')
        self.assertContains(response, 'إضافة حجز')
        self.assertContains(response, 'openSingleAvailableCard')
        self.assertContains(response, 'openSelectedAvailableSlots')

        booking_response = self.client.get(reverse('booking_create'), {
            'date': selected_date.isoformat(),
            'venue': place,
            'start_time': TIME_CHOICES[2][0],
            'end_time': TIME_CHOICES[5][0],
        })
        form = booking_response.context['form']
        self.assertEqual(form['booking_date'].value(), selected_date)
        self.assertEqual(form['venue'].value(), place)
        self.assertEqual(form['start_time'].value(), TIME_CHOICES[2][0])
        self.assertEqual(form['end_time'].value(), TIME_CHOICES[5][0])

    def test_daily_booking_hourly_rate_counts_two_half_hour_slots_as_one_hour(self):
        booking_date = date.today()
        form = DailyBookingForm(data={
            'customer_code': '', 'customer_name': 'عميل حساب الساعة',
            'customer_phone': '01111111112', 'national_id': '', 'players_count': 10,
            'amount': 500, 'advance_payment': 0, 'total_amount': 0, 'remaining_amount': 0,
            'venue': OPERATION_PLACE_CHOICES[0][0],
            'booking_date': booking_date.isoformat(),
            'booking_dates': booking_date.isoformat(),
            'booking_date_times': json.dumps([{
                'date': booking_date.isoformat(),
                'start_time': TIME_CHOICES[0][0],
                'end_time': TIME_CHOICES[2][0],
            }]),
            'start_time': TIME_CHOICES[0][0], 'end_time': TIME_CHOICES[2][0],
            'notes': '',
        })
        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(form.cleaned_data['total_amount'], 500)
        booking = form.save_all()[0]
        self.assertEqual(booking.total_amount, 500)

    def test_member_role_screen_has_only_matching_add_button_and_hidden_role(self):
        academy = Academy.objects.create(
            name='أكاديمية الأعضاء', sport_activity='كرة قدم', company_name='شركة',
            manager_name='مدير', manager_phone='01000000002',
            operation_place=OPERATION_PLACE_CHOICES[0][0],
            contract_start_date=date.today(), contract_end_date=date.today() + timedelta(days=30),
        )
        list_url = reverse('academy_member_list', args=[academy.pk]) + '?role=coach'
        response = self.client.get(list_url)
        self.assertContains(response, 'إضافة مدرب')
        self.assertNotContains(response, 'إضافة إداري')
        self.assertNotContains(response, 'إضافة لاعب')

        create_url = reverse('academy_member_create', args=[academy.pk]) + '?role=coach'
        response = self.client.get(create_url)
        self.assertNotContains(response, 'id_role')
        response = self.client.post(create_url, {
            'name': 'مدرب اختبار', 'phone': '', 'national_id': '',
            'monthly_subscription': 0, 'is_active': 'on', 'notes': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AcademyMember.objects.get(name='مدرب اختبار').role, AcademyMember.ROLE_COACH)

    def test_company_management_and_expenses_are_nested_in_parent_modules(self):
        profile, _ = UserPermission.objects.get_or_create(user=self.user)
        profile.can_shareholders = True
        profile.can_employees = True
        profile.can_general_expenses = True
        profile.save()
        response = self.client.get(reverse('company_management_home'))
        self.assertContains(response, 'فتح المساهمين')
        self.assertContains(response, 'فتح الموظفين')
        response = self.client.get(reverse('accounts_home'))
        self.assertContains(response, 'المصروفات العامة')
        self.assertNotContains(response, 'إجمالي الدخل الشهري')

    def test_cafeteria_specialist_is_limited_to_sales_menu_and_inventory(self):
        specialist = User.objects.create_user(username='Cafeteria_Specialist', password='test-password')
        profile = UserPermission.objects.create(user=specialist, can_cafeteria=True)
        category = CafeteriaCategory.objects.create(code=55, name='اختبار المنيو')
        CafeteriaItem.objects.create(
            category=category, code=1, name='صنف منخفض', opening_quantity=4,
            purchase_price=5, sale_price=10,
        )
        self.client.force_login(specialist)

        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, reverse('cafe_sale_list'))
        response = self.client.get(reverse('academy_list'))
        self.assertRedirects(response, reverse('cafe_sale_list'))

        response = self.client.get(reverse('cafe_sale_list'))
        self.assertContains(response, reverse('cafe_menu'))
        self.assertNotContains(response, reverse('cafe_category_list'))
        self.assertNotContains(response, reverse('cafe_item_list'))
        self.assertNotContains(response, reverse('cafe_purchase_list'))
        self.assertNotContains(response, 'لوحة التحكم')

        response = self.client.get(reverse('cafe_menu'))
        self.assertContains(response, 'اختبار المنيو')
        self.assertContains(response, 'صنف منخفض')
        self.assertContains(response, 'menu-low-stock')
