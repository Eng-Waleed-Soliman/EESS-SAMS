import json
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import OperationalError
from django.db.models import Sum
from django.http import HttpResponse
from django.test import RequestFactory
from django.test import TestCase, override_settings
from django.urls import reverse

from .constants import OPERATION_PLACE_CHOICES, TIME_CHOICES, WEEKDAY_AR
from .forms import AcademyForm, DailyBookingForm, EESSUserUpdateForm
from .middleware import DatabaseRetryMiddleware
from .views import _academy_schedule_occurrences_for_date, _calculate_variable_income_by_facility
from .models import (
    Academy,
    AcademyMember,
    AcademyDepositPlan,
    AcademyDepositInstallment,
    AcademyMonthlyRentPayment,
    CafeteriaCategory,
    CafeteriaItem,
    CafeteriaPurchase,
    CafeteriaSale,
    Customer,
    DailyBooking,
    DailyBookingCheckout,
    DailyExpense,
    DailyIncomeSupply,
    Employee,
    MonthlyExpense,
    OperatingExpense,
    Shareholder,
    UserPermission,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class ApplicationFlowsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='test-password')
        self.client.force_login(self.user)

    def test_database_retry_middleware_retries_reads_but_not_writes(self):
        calls = {'count': 0}

        def transient_response(request):
            calls['count'] += 1
            if calls['count'] == 1:
                raise OperationalError('temporary connection failure')
            return HttpResponse('ok')

        middleware = DatabaseRetryMiddleware(transient_response)
        response = middleware(RequestFactory().get('/admin/'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls['count'], 2)

        calls['count'] = 0
        with self.assertRaises(OperationalError):
            middleware(RequestFactory().post('/save/'))
        self.assertEqual(calls['count'], 1)

    @override_settings(DEBUG=False)
    def test_django_admin_renders_without_a_static_manifest(self):
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save(update_fields=['is_staff', 'is_superuser'])
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'admin/css/base.css')

    def test_academy_deposit_plan_installments_payments_and_supplies(self):
        today = date.today()
        profile, _ = UserPermission.objects.get_or_create(user=self.user)
        profile.can_reports = True
        profile.save()
        academy = Academy.objects.create(
            name='Deposit Academy', sport_activity='Football', company_name='Deposit Company',
            manager_name='Manager', manager_phone='01099999999',
            operation_place=OPERATION_PLACE_CHOICES[0][0],
            contract_start_date=date(today.year, 1, 1),
            contract_end_date=date(today.year, 12, 31),
            subscription_type='fixed', monthly_subscription=2000, security_deposit=1000,
        )
        rent_url = reverse('academy_rent_payments') + f'?month={today:%Y-%m}'
        response = self.client.get(rent_url)
        self.assertContains(response, 'إعداد الخطة')
        self.assertEqual(response.context['deposit_totals']['expected'], 1000)

        plan_url = reverse('academy_deposit_plan', args=[academy.pk])
        response = self.client.post(plan_url, {
            'action': 'save_plan',
            'total_amount': 1000,
            'installments_count': 3,
            'first_due_month': today.strftime('%Y-%m'),
            'notes': 'Three monthly installments',
        })
        self.assertRedirects(response, plan_url)
        plan = AcademyDepositPlan.objects.get(academy=academy)
        installments = list(plan.installments.all())
        self.assertEqual([item.due_amount for item in installments], [334, 333, 333])
        self.assertEqual(installments[1].due_month, date(today.year + (1 if today.month == 12 else 0), 1 if today.month == 12 else today.month + 1, 1))

        first = installments[0]
        response = self.client.post(plan_url, {
            'action': 'save_installments',
            f'installment_{first.id}_paid_amount': 334,
            f'installment_{first.id}_payment_date': today.isoformat(),
            f'installment_{first.id}_supplied_amount': 200,
            f'installment_{first.id}_supplied_date': today.isoformat(),
            f'installment_{first.id}_notes': 'First payment',
        })
        self.assertRedirects(response, plan_url)
        first.refresh_from_db()
        self.assertEqual(first.paid_recorded_by, self.user)
        self.assertEqual(first.supplied_recorded_by, self.user)
        self.assertEqual(first.remaining_amount, 0)
        self.assertEqual(first.unsupplied_amount, 134)

        response = self.client.get(rent_url)
        self.assertEqual(response.context['deposit_totals']['paid'], 334)
        self.assertEqual(response.context['deposit_totals']['remaining'], 666)
        self.assertEqual(response.context['deposit_totals']['supplied'], 200)
        self.assertEqual(response.context['deposit_totals']['unsupplied'], 134)
        self.assertContains(response, 'السداد والتوريد')

        response = self.client.post(plan_url, {
            'action': 'save_installments',
            f'installment_{first.id}_paid_amount': 334,
            f'installment_{first.id}_payment_date': today.isoformat(),
            f'installment_{first.id}_supplied_amount': 335,
            f'installment_{first.id}_supplied_date': today.isoformat(),
        }, follow=True)
        self.assertContains(response, 'أكبر من المسدد')
        first.refresh_from_db()
        self.assertEqual(first.supplied_amount, 200)

    def test_login_uses_typed_username_without_exposing_user_list(self):
        hidden_user = User.objects.create_user(username='private_operator', password='operator-password')
        self.client.logout()
        response = self.client.get(reverse('login'))
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'placeholder="اكتب اسم المستخدم"')
        self.assertNotContains(response, '<select name="username"')
        self.assertNotContains(response, hidden_user.username)

        response = self.client.post(reverse('login'), {
            'username': hidden_user.username,
            'password': 'operator-password',
        })
        self.assertRedirects(response, reverse('dashboard'))

    def test_admin_can_set_replacement_password_but_hash_is_never_displayed(self):
        target = User.objects.create_user(username='password_reset_user', password='old-secret-password')
        original_hash = target.password
        form = EESSUserUpdateForm(data={
            'username': target.username,
            'first_name': target.first_name,
            'email': target.email,
            'is_active': 'on',
            'new_password': 'replacement-password-123',
        }, instance=target)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        updated = form.save()
        self.assertNotEqual(updated.password, original_hash)
        self.assertTrue(updated.check_password('replacement-password-123'))

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

    def test_cafeteria_stock_adjustment_replaces_old_balance_and_appears_in_sales(self):
        today = date.today()
        category = CafeteriaCategory.objects.create(code=77, name='Stock adjustment')
        item = CafeteriaItem.objects.create(
            category=category, code=1, name='Adjusted item', opening_quantity=10,
            purchase_price=5, sale_price=10,
        )
        CafeteriaPurchase.objects.create(item=item, purchase_date=today, quantity=5, unit_price=5)
        CafeteriaSale.objects.create(item=item, sale_date=today, quantity=3, unit_price=10)
        self.assertEqual(item.stock_quantity, 12)

        response = self.client.post(reverse('cafe_stock_adjust'), {
            f'quantity_{item.id}': 40,
        })
        self.assertRedirects(response, reverse('cafe_item_list'))
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, 40)

        CafeteriaPurchase.objects.create(item=item, purchase_date=today, quantity=2, unit_price=5)
        CafeteriaSale.objects.create(item=item, sale_date=today, quantity=1, unit_price=10)
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, 41)

        response = self.client.get(reverse('cafe_item_list'))
        self.assertContains(response, '<td>41</td>', html=True)
        response = self.client.get(reverse('cafe_stock_adjust'))
        self.assertContains(response, f'name="quantity_{item.id}" value="41"')
        response = self.client.get(reverse('cafe_sale_list'))
        self.assertContains(response, 'id="stock_quantity_display"')
        self.assertContains(response, '"stock_quantity": 41')

    def test_cafeteria_item_edit_includes_and_saves_sale_price(self):
        category = CafeteriaCategory.objects.create(code=78, name='Prices')
        item = CafeteriaItem.objects.create(
            category=category, code=2, name='Priced item', opening_quantity=5,
            purchase_price=6, sale_price=10,
        )
        response = self.client.get(reverse('cafe_item_update', args=[item.pk]))
        self.assertContains(response, 'id="id_sale_price"')
        self.assertContains(response, 'value="10"')

        response = self.client.post(reverse('cafe_item_update', args=[item.pk]), {
            'category': category.pk,
            'code': item.code,
            'name': item.name,
            'opening_quantity': item.opening_quantity,
            'purchase_price': item.purchase_price,
            'sale_price': 15,
            'notes': '',
        })
        self.assertRedirects(response, reverse('cafe_item_list'))
        item.refresh_from_db()
        self.assertEqual(item.sale_price, 15)

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
            '/reports/?report_type=monthly_income',
            fetch_redirect_response=False,
        )

    def test_reports_hub_contains_only_requested_management_reports(self):
        profile, _ = UserPermission.objects.get_or_create(user=self.user)
        profile.can_reports = True
        profile.save()
        today = date.today()
        Shareholder.objects.create(name='عضو مجلس اختبار', share_percentage=25)
        Employee.objects.create(name='موظف تقرير', job_title='مشغل', salary=5000)
        academy = Academy.objects.create(
            name='أكاديمية تقرير', sport_activity='كرة قدم', company_name='شركة تقرير',
            manager_name='مدير تقرير', manager_phone='01000000123',
            operation_place=OPERATION_PLACE_CHOICES[0][0],
            contract_start_date=date(today.year, 1, 1), contract_end_date=date(today.year, 12, 31),
            subscription_type='fixed', monthly_subscription=1000,
        )
        AcademyMember.objects.create(academy=academy, role=AcademyMember.ROLE_COACH, name='مدرب تقرير')
        AcademyMonthlyRentPayment.objects.create(
            academy=academy, month=date(today.year, today.month, 1),
            expected_amount=1000, paid_amount=700, supplied_amount=500,
        )
        MonthlyExpense.objects.create(title='مصروف شهري تقرير', expense_month=date(today.year, today.month, 1), amount=200)
        DailyExpense.objects.create(title='مصروف يومي تقرير', expense_date=today, amount=100, created_by=self.user)
        OperatingExpense.objects.create(title='مصروف تشغيل تقرير', expense_date=today, amount=50, notes='ملاحظة تشغيل')
        booking = DailyBooking.objects.create(
            venue=OPERATION_PLACE_CHOICES[0][0], booking_date=today,
            start_time=TIME_CHOICES[0][0], end_time=TIME_CHOICES[2][0],
            customer_name='عميل تقرير الدخل', customer_phone='01100000123',
            total_amount=300, advance_payment=300, remaining_amount=0,
        )
        DailyBookingCheckout.objects.create(
            booking=booking, income_date=today, customer_name=booking.customer_name,
            customer_phone=booking.customer_phone, venue=booking.venue,
            booking_date=today, start_time=booking.start_time, end_time=booking.end_time,
            total_amount=300, advance_payment=300, remaining_amount=0,
        )
        category = CafeteriaCategory.objects.create(code=901, name='فئة تقرير')
        item = CafeteriaItem.objects.create(
            category=category, code=1, name='صنف إحصائيات', opening_quantity=0,
            purchase_price=10, sale_price=20,
        )
        CafeteriaPurchase.objects.create(item=item, purchase_date=today, quantity=5, unit_price=10)
        CafeteriaSale.objects.create(item=item, sale_date=today, quantity=3, unit_price=20)

        response = self.client.get(reverse('reports_home'), {'report_type': 'board_members'})
        self.assertContains(response, 'عضو مجلس اختبار')
        self.assertEqual(len(response.context['allowed_report_options']), 6)
        for label in ['أعضاء مجلس الإدارة', 'بيانات الموظفين', 'الأكاديميات الرياضية', 'الدخل الشهري', 'المصروفات', 'الكافيتريا']:
            self.assertContains(response, label)
        self.assertNotContains(response, 'تقرير المرتبات الشهرية والبونص')
        self.assertNotContains(response, 'تقرير مبالغ التأمين')
        self.assertContains(response, 'تصدير PDF')
        self.assertContains(response, 'طباعة')
        self.assertContains(response, 'name="signature_title"')
        self.assertContains(response, 'print-report-header')

        response = self.client.get(reverse('reports_home'), {'report_type': 'academies'})
        self.assertContains(response, 'أكاديمية تقرير')
        self.assertContains(response, '?role=coach')
        self.assertContains(response, '?role=admin')
        self.assertContains(response, '?role=player')

        response = self.client.get(reverse('reports_home'), {
            'report_type': 'monthly_income', 'month': today.strftime('%Y-%m'),
            'section': 'expected', 'signature_title': 'مشغل',
        })
        for heading in ('الأكاديميات', 'الحجز اليومي', 'دخل الكافيتريا', 'المصروفات', 'صافي الدخل'):
            self.assertContains(response, f'class="fs-5">{heading}</th>')
        self.assertNotContains(response, 'الجزء الأول:')
        self.assertNotContains(response, 'عرض التقرير')
        self.assertContains(response, 'name="range_mode"')
        self.assertContains(response, 'عن فترة محددة')
        self.assertContains(response, 'report-filter-grid')
        self.assertContains(response, 'name="signature_title"')
        self.assertContains(response, '<option value="مشغل" selected>مشغل</option>', html=True)
        self.assertEqual(response.context['signature_title'], 'مشغل')
        self.assertContains(response, 'id="printSignatureTitle" class="fw-bold">مشغل</div>')
        self.assertContains(response, 'onchange="this.form.submit()"')
        self.assertContains(response, 'أكاديمية تقرير')
        self.assertNotContains(response, 'مصروف تشغيل تقرير')
        self.assertContains(response, 'مشتروات الكافيتريا')
        self.assertContains(response, 'صنف إحصائيات - كمية 5')
        self.assertContains(response, WEEKDAY_AR[today.weekday()])
        self.assertEqual(response.context['income_expected_total'], 1000)
        self.assertEqual(response.context['income_paid_total'], 700)
        self.assertEqual(response.context['income_supplied_total'], 500)
        self.assertEqual(response.context['income_daily_booking_total'], 300)
        self.assertEqual(response.context['income_cafeteria_total'], 60)
        self.assertEqual(response.context['income_expenses_total'], 350)
        self.assertEqual(response.context['income_total'], 1060)
        self.assertEqual(response.context['income_net_total'], 710)

        response = self.client.get(reverse('reports_home'), {
            'report_type': 'monthly_income', 'range_mode': 'custom',
            'date_from': today.isoformat(), 'date_to': today.isoformat(),
        })
        self.assertEqual(response.context['range_mode'], 'custom')
        self.assertEqual(response.context['income_daily_booking_total'], 300)
        self.assertEqual(response.context['income_cafeteria_total'], 60)
        self.assertContains(response, f'من {today.strftime("%d/%m/%Y")} إلى {today.strftime("%d/%m/%Y")}')

        response = self.client.get(reverse('reports_home'), {
            'report_type': 'expenses', 'month': today.strftime('%Y-%m'), 'section': 'daily',
        })
        self.assertEqual(response.context['monthly_expenses_total'], 200)
        self.assertEqual(response.context['daily_expenses_total'], 100)
        self.assertEqual(response.context['all_expenses_total'], 300)
        self.assertContains(response, 'مصروف يومي تقرير')

        response = self.client.get(reverse('reports_home'), {
            'report_type': 'cafeteria', 'month': today.strftime('%Y-%m'), 'section': 'statistics',
        })
        self.assertEqual(response.context['cafeteria_purchase_total'], 50)
        self.assertEqual(response.context['cafeteria_sales_total'], 60)
        self.assertEqual(response.context['cafeteria_net_profit'], 10)
        self.assertEqual(response.context['cafeteria_statistics'][0]['sold'], 3)
        self.assertEqual(response.context['cafeteria_statistics'][0]['profit_percentage'], 50.0)

        response = self.client.get(reverse('cafe_purchase_list'))
        self.assertNotContains(response, reverse('operating_expense_list'))
        response = self.client.get(reverse('cafe_item_list'))
        self.assertContains(response, 'مشتروات الكافيتريا')
        self.assertNotContains(response, reverse('operating_expense_list'))

    def test_dashboard_shows_six_current_month_linked_cards(self):
        today = date.today()
        academy = Academy.objects.create(
            name='أكاديمية لوحة التحكم', sport_activity='كرة قدم', company_name='شركة',
            manager_name='مدير', manager_phone='01000000456',
            operation_place=OPERATION_PLACE_CHOICES[0][0],
            contract_start_date=date(today.year, 1, 1), contract_end_date=date(today.year, 12, 31),
            subscription_type='fixed', monthly_subscription=1000,
        )
        AcademyMonthlyRentPayment.objects.create(
            academy=academy, month=date(today.year, today.month, 1),
            expected_amount=1000, paid_amount=800, supplied_amount=600,
        )
        booking = DailyBooking.objects.create(
            venue=OPERATION_PLACE_CHOICES[0][0], booking_date=today,
            start_time=TIME_CHOICES[0][0], end_time=TIME_CHOICES[2][0],
            customer_name='عميل لوحة', customer_phone='01100000456',
            total_amount=500, advance_payment=500, remaining_amount=0,
        )
        DailyBookingCheckout.objects.create(
            booking=booking, income_date=today, customer_name=booking.customer_name,
            customer_phone=booking.customer_phone, venue=booking.venue,
            booking_date=today, start_time=booking.start_time, end_time=booking.end_time,
            total_amount=500, advance_payment=500, remaining_amount=0,
        )
        DailyIncomeSupply.objects.create(supply_date=today, amount=450, notes='توريد حجز يومي')
        category = CafeteriaCategory.objects.create(code=902, name='فئة لوحة')
        item = CafeteriaItem.objects.create(category=category, code=1, name='صنف لوحة', sale_price=20)
        CafeteriaSale.objects.create(item=item, sale_date=today, quantity=3, unit_price=20)

        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['contracted_academies'], 1)
        self.assertEqual(response.context['expected_total'], 1000)
        self.assertEqual(response.context['paid_total'], 800)
        self.assertEqual(response.context['daily_booking_supplied'], 450)
        self.assertEqual(response.context['cafeteria_income'], 60)
        self.assertEqual(response.context['supplied_total'], 1050)
        self.assertEqual(response.content.decode().count('<div class="dashboard-card-col">'), 6)

    def test_daily_booking_cash_supply_screen_records_multiple_entries(self):
        today = date.today()
        response = self.client.get(reverse('booking_list'))
        self.assertContains(response, reverse('daily_income_supply'))
        response = self.client.get(reverse('daily_income_supply'))
        self.assertContains(response, f'value="{today.isoformat()}"')
        self.assertContains(response, 'المبلغ المورد')

        for amount in (300, 200):
            response = self.client.post(reverse('daily_income_supply'), {
                'supply_date': today.isoformat(),
                'amount': amount,
                'notes': 'توريد نقدي للاختبار',
            })
            self.assertRedirects(response, reverse('daily_income_supply'))
        self.assertEqual(DailyIncomeSupply.objects.filter(supply_date=today).count(), 2)
        self.assertEqual(
            DailyIncomeSupply.objects.filter(supply_date=today).aggregate(total=Sum('amount'))['total'],
            500,
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

    def test_daily_booking_accepts_times_touching_academy_boundaries(self):
        booking_date = date.today()
        place = OPERATION_PLACE_CHOICES[0][0]
        day_name = WEEKDAY_AR[booking_date.weekday()]
        academy_start = TIME_CHOICES[22][0]  # 7:00 PM
        academy_end = TIME_CHOICES[24][0]    # 8:00 PM
        Academy.objects.create(
            name='Boundary Academy', sport_activity='Football', company_name='Company',
            manager_name='Manager', manager_phone='01000000999', operation_place=place,
            contract_start_date=booking_date, contract_end_date=booking_date + timedelta(days=1),
            subscription_type='variable', variable_rent_type='hour', variable_rent_value=500,
            training_schedule=[{
                'place': place, 'day': day_name, 'start_time': academy_start,
                'end_time': academy_end, 'hourly_rent': 500,
            }],
        )

        def booking_form(start_time, end_time, phone):
            return DailyBookingForm(data={
                'customer_code': '', 'customer_name': 'Boundary Customer',
                'customer_phone': phone, 'national_id': '', 'players_count': 1,
                'amount': 500, 'advance_payment': 0, 'total_amount': 0, 'remaining_amount': 0,
                'venue': place, 'booking_date': booking_date.isoformat(),
                'booking_dates': booking_date.isoformat(),
                'booking_date_times': json.dumps([{
                    'date': booking_date.isoformat(), 'start_time': start_time, 'end_time': end_time,
                }]),
                'start_time': start_time, 'end_time': end_time, 'notes': '',
            })

        before = booking_form(TIME_CHOICES[20][0], academy_start, '01010000001')
        after = booking_form(academy_end, TIME_CHOICES[26][0], '01010000002')
        self.assertTrue(before.is_valid(), before.errors.as_json())
        self.assertTrue(after.is_valid(), after.errors.as_json())

    def test_booking_create_prefills_new_code_and_phone_lookup_data(self):
        response = self.client.get(reverse('booking_create'))
        self.assertEqual(response.context['form']['customer_code'].value(), 'C00001')

        customer = Customer.objects.create(
            customer_code='C00420', customer_name='Existing Customer',
            customer_phone='01012345678', national_id='29001011234567',
        )
        response = self.client.get(reverse('booking_create'))
        self.assertEqual(response.context['form']['customer_code'].value(), Customer.next_code())
        customers = json.loads(response.context['customers_json'])
        self.assertIn({
            'code': customer.customer_code,
            'name': customer.customer_name,
            'phone': customer.customer_phone,
            'national_id': customer.national_id,
            'visits_count': 0,
            'last_visit_date': '',
            'last_visit_display': '',
        }, customers)
        self.assertContains(response, "addEventListener('input', lookupByPhone)")

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
