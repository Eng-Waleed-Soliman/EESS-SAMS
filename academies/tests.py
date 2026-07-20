import json
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import OperationalError
from django.db.models import Sum
from django.http import HttpResponse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from django.test import TestCase, override_settings
from django.urls import reverse

from .constants import OPERATION_PLACE_CHOICES, TIME_CHOICES, WEEKDAY_AR
from .forms import (
    AcademyForm, AppSettingForm, BranchForm, DailyBookingForm,
    EESSUserUpdateForm, SportActivityMediaForm,
)
from .middleware import DatabaseRetryMiddleware
from .views import _academy_schedule_occurrences_for_date, _calculate_variable_income_by_facility
from .models import (
    Academy,
    AcademyMember,
    Activity,
    AcademyDepositPlan,
    AcademyDepositInstallment,
    AcademyMonthlyRentPayment,
    AppSetting,
    Branch,
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
    FinancialVoucher,
    JobTitle,
    MonthlyExpense,
    OperatingExpense,
    Shareholder,
    SecurityMovement,
    UserPermission,
    WebsiteSetting,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class ApplicationFlowsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='test-password')
        self.client.force_login(self.user)

    def test_public_website_uses_published_management_data(self):
        branch = Branch.objects.create(
            name='Public Branch', short_name='PB',
            website_description='Public branch introduction',
        )
        hidden_branch = Branch.objects.create(
            name='Hidden Branch', is_published_on_website=False,
        )
        academy = Academy.objects.create(
            branch=branch, name='Champions Academy', sport_activity='Football',
            company_name='Champions', manager_name='Manager', manager_phone='01000000000',
            operation_place=OPERATION_PLACE_CHOICES[0][0],
            contract_start_date=date.today(), contract_end_date=date.today() + timedelta(days=30),
            website_description='A professional public academy.',
        )
        AcademyMember.objects.create(
            academy=academy, role=AcademyMember.ROLE_COACH, name='Public Coach',
            job_title='Head Coach', website_bio='Professional coach biography.',
        )
        Shareholder.objects.create(
            name='Board Leader', job_title='Chairman',
            website_bio='Board member biography.',
        )
        website = WebsiteSetting.current()
        website.hero_title_ar = 'عنوان الموقع الاحترافي'
        website.save()

        self.client.logout()
        response = self.client.get(reverse('public_website'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'عنوان الموقع الاحترافي')
        self.assertContains(response, branch.display_name)
        self.assertContains(response, academy.name)
        self.assertContains(response, 'Public Coach')
        self.assertContains(response, 'Board Leader')
        self.assertNotContains(response, hidden_branch.name)

        detail = self.client.get(reverse('public_academy_detail', args=[academy.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, academy.website_description)
        self.assertContains(detail, 'Public Coach')

    def test_board_member_photo_upload_and_chairman_position_in_both_languages(self):
        Shareholder.objects.create(
            name='خالد العضو',
            name_en='Khaled Member',
            job_title='عضو مجلس الإدارة',
            job_title_en='Board Member',
        )
        photo = SimpleUploadedFile(
            'chairman.png',
            b'chairman-photo-bytes',
            content_type='image/png',
        )
        response = self.client.post(reverse('shareholder_create'), {
            'name': 'أحمد الرئيس',
            'name_en': 'Ahmed Chairman',
            'share_percentage': 0,
            'job_title': 'رئيس مجلس الإدارة',
            'job_title_en': 'Chairman',
            'is_published_on_website': 'on',
            'photo': photo,
        })
        self.assertRedirects(response, reverse('shareholder_list'))
        chairman = Shareholder.objects.get(name='أحمد الرئيس')
        self.assertEqual(bytes(chairman.photo_data), b'chairman-photo-bytes')

        self.client.logout()
        arabic_response = self.client.get(reverse('public_website'), {'lang': 'ar'})
        arabic_html = arabic_response.content.decode()
        self.assertLess(
            arabic_html.index('أحمد الرئيس'),
            arabic_html.index('خالد العضو'),
        )
        self.assertContains(
            arabic_response,
            reverse('persistent_media', args=['shareholder', chairman.pk, 'photo']),
        )
        self.assertContains(arabic_response, '<html lang="ar" dir="rtl">')

        english_response = self.client.get(reverse('public_website'), {'lang': 'en'})
        english_html = english_response.content.decode()
        self.assertLess(
            english_html.index('Ahmed Chairman'),
            english_html.index('Khaled Member'),
        )
        self.assertContains(
            english_response,
            reverse('persistent_media', args=['shareholder', chairman.pk, 'photo']),
        )
        self.assertContains(english_response, '<html lang="en" dir="ltr">')

    def test_public_website_does_not_load_persistent_image_blobs_into_page_context(self):
        branding = AppSetting.current()
        branding.company_logo_data = b'x' * 1024
        branding.company_logo_name = 'logo.png'
        branding.save()
        website = WebsiteSetting.current()
        website.hero_image_data = b'y' * 1024
        website.hero_image_name = 'hero.png'
        website.save()
        branch = Branch.objects.create(
            name='Memory Safe Branch',
            image_data=b'z' * 1024,
            image_name='branch.png',
        )
        academy = Academy.objects.create(
            branch=branch,
            name='Memory Safe Academy',
            logo_data=b'a' * 1024,
            logo_name='academy.png',
            sport_activity='Football',
            company_name='Company',
            manager_name='Manager',
            manager_phone='01000000000',
            operation_place=OPERATION_PLACE_CHOICES[0][0],
            contract_start_date=date.today(),
            contract_end_date=date.today() + timedelta(days=30),
        )
        coach = AcademyMember.objects.create(
            academy=academy,
            role=AcademyMember.ROLE_COACH,
            name='Memory Safe Coach',
            photo_data=b'b' * 1024,
            photo_name='coach.png',
        )

        self.client.logout()
        response = self.client.get(reverse('public_website'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('company_logo_data', response.context['branding'].get_deferred_fields())
        self.assertIn('hero_image_data', response.context['website'].get_deferred_fields())
        rendered_branch = next(item for item in response.context['branches'] if item.pk == branch.pk)
        rendered_academy = next(item for item in response.context['academies'] if item.pk == academy.pk)
        rendered_coach = next(item for item in response.context['coaches'] if item.pk == coach.pk)
        self.assertIn('image_data', rendered_branch.get_deferred_fields())
        self.assertIn('logo_data', rendered_academy.get_deferred_fields())
        self.assertIn('photo_data', rendered_coach.get_deferred_fields())

    def test_public_website_switches_all_public_content_to_english_and_remembers_language(self):
        branch = Branch.objects.create(
            name='فرع القاهرة',
            name_en='Cairo Branch',
            short_name='CAI',
            location='القاهرة',
            location_en='Cairo',
            website_description='وصف الفرع',
            website_description_en='Cairo branch description',
        )
        academy = Academy.objects.create(
            branch=branch,
            name='أكاديمية الأبطال',
            name_en='Champions Academy',
            sport_activity='كرة قدم',
            sport_activity_en='Football',
            company_name='Champions',
            manager_name='Manager',
            manager_phone='01000000000',
            operation_place=OPERATION_PLACE_CHOICES[0][0],
            contract_start_date=date.today(),
            contract_end_date=date.today() + timedelta(days=30),
            website_description='نبذة عربية',
            website_description_en='English academy introduction',
        )
        AcademyMember.objects.create(
            academy=academy,
            role=AcademyMember.ROLE_COACH,
            name='مدرب عربي',
            name_en='English Coach',
            job_title='مدرب رئيسي',
            job_title_en='Head Coach',
            website_bio='نبذة عربية',
            website_bio_en='English coach biography',
        )
        website = WebsiteSetting.current()
        website.hero_text_en = 'A complete professional sports ecosystem.'
        website.about_title_en = 'Sport Without Limits'
        website.about_text_en = 'English company profile.'
        website.address_en = 'Cairo, Egypt'
        website.footer_text_en = 'EESS official website'
        website.save()

        self.client.logout()
        response = self.client.get(reverse('public_website'), {'lang': 'en'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<html lang="en" dir="ltr">')
        self.assertContains(response, 'About')
        self.assertNotContains(response, 'Management Login')
        self.assertNotContains(response, 'class="stats"')
        self.assertContains(response, 'Cairo Branch')
        self.assertContains(response, 'Champions Academy')
        self.assertContains(response, 'Football')
        self.assertContains(response, 'English Coach')
        self.assertContains(response, 'Head Coach')
        self.assertNotContains(response, 'عن الشركة')

        detail = self.client.get(reverse('public_academy_detail', args=[academy.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, '<html lang="en" dir="ltr">')
        self.assertContains(detail, 'Back to Academies')
        self.assertContains(detail, 'English academy introduction')

        arabic = self.client.get(reverse('public_website'), {'lang': 'ar'})
        self.assertContains(arabic, '<html lang="ar" dir="rtl">')
        self.assertContains(arabic, 'عن الشركة')

    def test_sport_media_form_uses_registered_activities_dropdown_and_prevents_duplicates(self):
        Activity.objects.create(name='كرة يد', is_active=True)
        form = SportActivityMediaForm()
        self.assertEqual(form.fields['name'].widget.__class__.__name__, 'Select')
        self.assertIn(('كرة يد', 'كرة يد'), form.fields['name'].choices)
        self.assertEqual(
            [name for name in form.fields],
            ['name', 'name_en', 'image', 'description', 'description_en', 'is_active'],
        )

        form = SportActivityMediaForm(data={
            'name': 'كرة يد',
            'name_en': 'Handball',
            'description': 'وصف مختصر',
            'description_en': 'Short description',
            'is_active': True,
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        duplicate = SportActivityMediaForm(data={
            'name': 'كرة يد',
            'name_en': 'Handball',
            'is_active': True,
        })
        self.assertFalse(duplicate.is_valid())
        self.assertIn('name', duplicate.errors)

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

    def test_branch_short_name_is_used_as_the_display_label(self):
        branch = Branch.objects.create(
            name='British International College of Cairo',
            short_name='BICC',
            logo='branches/logos/bicc.png',
            image='branches/images/bicc.jpg',
        )
        self.assertEqual(str(branch), 'BICC')
        self.assertEqual(branch.display_name, 'BICC')
        self.assertIn('short_name', BranchForm().fields)

        form = BranchForm(data={
            'name': branch.name,
            'short_name': branch.short_name,
            'location': 'Cairo',
            'notes': '',
        }, instance=branch)
        self.assertTrue(form.is_valid(), form.errors)
        saved_branch = form.save()
        self.assertEqual(saved_branch.logo.name, 'branches/logos/bicc.png')
        self.assertEqual(saved_branch.image.name, 'branches/images/bicc.jpg')

        setting = AppSetting.objects.create(
            pk=99,
            company_logo='branding/company.png',
            main_screen_image='branding/main.jpg',
        )
        setting_form = AppSettingForm(data={
            'program_name': setting.program_name,
            'company_name': setting.company_name,
            'company_short_name': 'EESS TEST',
            'company_name_ar': setting.company_name_ar,
        }, instance=setting)
        self.assertTrue(setting_form.is_valid(), setting_form.errors)
        saved_setting = setting_form.save()
        self.assertEqual(saved_setting.company_logo.name, 'branding/company.png')
        self.assertEqual(saved_setting.main_screen_image.name, 'branding/main.jpg')
        self.assertEqual(saved_setting.company_short_name, 'EESS TEST')
        self.assertIn('company_short_name', setting_form.fields)

        branch.short_name = ''
        self.assertEqual(branch.display_name, branch.name)

    def test_security_entry_exit_visitors_qr_and_report(self):
        profile, _ = UserPermission.objects.get_or_create(user=self.user)
        profile.can_security = True
        profile.save()
        branch = Branch.objects.create(name='Security branch full name', short_name='SEC')
        academy = Academy.objects.create(
            branch=branch, name='Security Academy', sport_activity='Football',
            company_name='Security Company', manager_name='Manager',
            manager_phone='01012345678', operation_place=OPERATION_PLACE_CHOICES[0][0],
            contract_start_date=date.today(), contract_end_date=date.today() + timedelta(days=30),
        )
        member = AcademyMember.objects.create(
            academy=academy, role=AcademyMember.ROLE_PLAYER, name='Security Player',
        )

        response = self.client.get(reverse('security_home'))
        self.assertContains(response, 'الدخول')
        self.assertContains(response, 'الخروج')

        response = self.client.post(reverse('security_movement', args=['entry']), {
            'action': 'record_member',
            'member_id': member.pk,
            'academy_id': academy.pk,
            'group': 'player',
            'source': 'manual',
        })
        self.assertEqual(response.status_code, 302)
        movement = SecurityMovement.objects.get(member=member, movement_type='entry')
        self.assertEqual(movement.person_name, member.name)
        self.assertEqual(movement.academy, academy)
        self.assertEqual(movement.recorded_by, self.user)

        response = self.client.post(reverse('security_movement', args=['exit']), {
            'action': 'lookup_qr',
            'qr_value': f'المعرف: {member.qr_token}',
        })
        self.assertContains(response, member.name)
        self.assertContains(response, academy.name)

        response = self.client.post(reverse('security_movement', args=['entry']), {
            'action': 'record_visitor',
            'academy_id': academy.pk,
            'group': 'staff',
            'visitor_name': 'Visitor Parent',
            'visitor_type': 'parent',
            'notes': 'Test visitor',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SecurityMovement.objects.filter(
            person_name='Visitor Parent', source='visitor', person_type='parent',
        ).exists())

        response = self.client.get(reverse('reports_home'), {
            'report_type': 'security_log',
            'month': date.today().strftime('%Y-%m'),
        })
        self.assertContains(response, 'سجل الدخول والخروج')
        self.assertContains(response, member.name)
        self.assertContains(response, 'Visitor Parent')
        self.assertContains(response, 'SEC')

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
        self.assertNotContains(response, 'رجوع للإعدادات')
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

    def test_financial_disbursement_and_supply_vouchers_render_numbers_and_words(self):
        today = date.today()
        profile, _ = UserPermission.objects.get_or_create(user=self.user)
        profile.can_reports = True
        profile.can_accounts = True
        profile.save()
        JobTitle.objects.create(name='المدير المالي')
        signer = Employee.objects.create(name='أحمد محمود', job_title='المدير المالي')

        reports_response = self.client.get(reverse('reports_home'))
        self.assertNotContains(reports_response, reverse('financial_voucher_create', args=['disbursement']))
        self.assertNotContains(reports_response, reverse('financial_voucher_create', args=['supply']))
        accounts_response = self.client.get(reverse('accounts_home'))
        self.assertContains(accounts_response, reverse('financial_voucher_create', args=['disbursement']))
        self.assertContains(accounts_response, reverse('financial_voucher_create', args=['supply']))
        self.assertContains(accounts_response, reverse('financial_voucher_list'))
        self.assertContains(accounts_response, 'accountsSignatureSelector')
        self.assertContains(accounts_response, 'accountsSignatureName')
        self.assertContains(accounts_response, 'طباعة')

        disbursement_url = reverse('financial_voucher_create', args=['disbursement'])
        create_screen = self.client.get(disbursement_url)
        self.assertContains(create_screen, 'name="submit_action" value="pdf"')
        self.assertContains(create_screen, 'name="submit_action" value="print"')
        self.assertContains(create_screen, 'voucher-form-header')
        self.assertContains(create_screen, 'اسم الموظف الموقّع')
        self.assertContains(create_screen, 'voucherEmployeeNames')
        self.assertContains(create_screen, 'id_signature_name')
        self.assertContains(create_screen, 'مستند A5')
        response = self.client.post(disbursement_url, {
            'amount': 1250,
            'statement': 'شراء مستلزمات تشغيل',
            'voucher_date': today.isoformat(),
            'signature_title': 'المدير المالي',
        })
        voucher = FinancialVoucher.objects.get(voucher_type=FinancialVoucher.TYPE_DISBURSEMENT)
        self.assertRedirects(response, reverse('financial_voucher_detail', args=[voucher.pk]))
        self.assertEqual(voucher.created_by, self.user)
        self.assertEqual(voucher.voucher_number, 'ص-00001')
        self.assertEqual(voucher.signature_name, signer.name)
        self.assertEqual(voucher.amount_in_words, 'ألف ومائتان وخمسون جنيه مصري فقط لا غير')

        detail = self.client.get(reverse('financial_voucher_detail', args=[voucher.pk]))
        self.assertContains(detail, 'أمر صرف مبلغ مالي')
        self.assertContains(detail, '1250 جنيه مصري')
        self.assertContains(detail, voucher.amount_in_words)
        self.assertContains(detail, WEEKDAY_AR[today.weekday()])
        self.assertContains(detail, 'المدير المالي')
        self.assertContains(detail, 'ـ')
        self.assertContains(detail, 'يتم صرف')
        self.assertContains(detail, 'المبلغ المالي الموضح أدناه اليوم')
        self.assertContains(detail, 'voucher-number-block')
        self.assertContains(detail, 'grid-template-areas:"number . brand" "heading heading heading"')
        self.assertContains(detail, '@page{size:A5 portrait')
        self.assertNotContains(detail, 'تم إنشاء أمر صرف مبلغ مالي بنجاح')
        self.assertContains(detail, 'تصدير PDF')
        self.assertContains(detail, 'window.print()')

        supply_url = reverse('financial_voucher_create', args=['supply'])
        response = self.client.post(supply_url, {
            'amount': 2000,
            'statement': 'توريد إيراد يومي',
            'voucher_date': today.isoformat(),
            'signature_title': 'المدير المالي',
        })
        supply = FinancialVoucher.objects.get(voucher_type=FinancialVoucher.TYPE_SUPPLY)
        self.assertRedirects(response, reverse('financial_voucher_detail', args=[supply.pk]))
        self.assertEqual(supply.voucher_number, 'ت-00001')
        self.assertEqual(supply.amount_in_words, 'ألفان جنيه مصري فقط لا غير')
        supply_detail = self.client.get(reverse('financial_voucher_detail', args=[supply.pk]))
        self.assertContains(supply_detail, 'يتم استلام')
        self.assertContains(supply_detail, 'المبلغ المالي الموضح أدناه اليوم')
        list_response = self.client.get(reverse('financial_voucher_list'))
        self.assertContains(list_response, voucher.voucher_number)
        self.assertContains(list_response, supply.voucher_number)
        self.assertContains(list_response, 'printVoucherRegister')
        self.assertContains(list_response, 'voucher-register-header')
        self.assertContains(list_response, 'registerSignatureSelector')
        self.assertContains(list_response, 'registerSignatureName')
        self.assertContains(list_response, 'registerEmployeeNames')
        self.assertContains(list_response, 'voucher-register-toolbar')
        self.assertContains(list_response, 'رجوع للحسابات')
        self.assertContains(list_response, 'تصدير PDF')
        self.assertContains(list_response, signer.name)

        response = self.client.post(reverse('financial_voucher_update', args=[voucher.pk]), {
            'amount': voucher.amount,
            'statement': voucher.statement,
            'voucher_date': voucher.voucher_date.isoformat(),
            'signature_title': voucher.signature_title,
            'submit_action': 'pdf',
        })
        expected_print_url = reverse('financial_voucher_detail', args=[voucher.pk]) + '?auto_print=1&pdf=1'
        self.assertRedirects(response, expected_print_url)
        print_detail = self.client.get(expected_print_url)
        self.assertContains(print_detail, "printVoucher(true)")
        self.assertNotContains(print_detail, 'تم تحديث الأمر المالي بنجاح')
        self.assertContains(print_detail, '@media print{.global-messages{display:none!important')

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

    def test_dashboard_is_the_direct_login_entry_point_for_anonymous_users(self):
        self.client.logout()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertEqual(response.context['next'], 'dashboard')

        response = self.client.post(reverse('dashboard'), {
            'username': self.user.username,
            'password': 'test-password',
            'next': 'dashboard',
        })
        self.assertRedirects(response, reverse('dashboard'))
        dashboard = self.client.get(reverse('dashboard'))
        self.assertEqual(dashboard.status_code, 200)
        self.assertTemplateUsed(dashboard, 'academies/dashboard.html')

    def test_admin_can_set_replacement_password_but_hash_is_never_displayed(self):
        target = User.objects.create_user(username='password_reset_user', password='old-secret-password')
        original_hash = target.password
        mismatch_form = EESSUserUpdateForm(data={
            'username': target.username,
            'first_name': target.first_name,
            'email': target.email,
            'is_active': 'on',
            'new_password': 'replacement-password-123',
            'confirm_new_password': 'different-password',
        }, instance=target)
        self.assertFalse(mismatch_form.is_valid())
        self.assertIn('confirm_new_password', mismatch_form.errors)

        form = EESSUserUpdateForm(data={
            'username': target.username,
            'first_name': target.first_name,
            'email': target.email,
            'is_active': 'on',
            'new_password': 'replacement-password-123',
            'confirm_new_password': 'replacement-password-123',
        }, instance=target)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        updated = form.save()
        self.assertNotEqual(updated.password, original_hash)
        self.assertTrue(updated.check_password('replacement-password-123'))

        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        response = self.client.post(reverse('user_update', args=[target.pk]), {
            'username': target.username,
            'first_name': target.first_name,
            'email': target.email,
            'is_active': 'on',
            'new_password': 'saved-through-user-screen',
            'confirm_new_password': 'saved-through-user-screen',
        })
        self.assertRedirects(response, reverse('user_list'))
        target.refresh_from_db()
        self.assertFalse(target.check_password('replacement-password-123'))
        self.assertTrue(target.check_password('saved-through-user-screen'))
        self.client.logout()
        self.assertFalse(self.client.login(username=target.username, password='replacement-password-123'))
        self.assertTrue(self.client.login(username=target.username, password='saved-through-user-screen'))

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
        with self.assertNumQueries(3):
            calculated_income = _calculate_variable_income_by_facility(
                academy,
                selected_date.year,
                selected_date.month,
            )
        self.assertEqual(calculated_income, 300)

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
        Employee.objects.create(name='موظف تقرير', job_title='مشغل', salary=5000)
        academy = Academy.objects.create(
            name='أكاديمية تقرير', sport_activity='كرة قدم', company_name='شركة تقرير',
            manager_name='مدير تقرير', manager_phone='01000000123',
            operation_place=OPERATION_PLACE_CHOICES[0][0],
            contract_start_date=date(today.year, 1, 1), contract_end_date=date(today.year, 12, 31),
            subscription_type='fixed', monthly_subscription=1000,
        )
        report_coach = AcademyMember.objects.create(
            academy=academy, role=AcademyMember.ROLE_COACH, name='مدرب تقرير',
            job_title='مدرب رئيسي', photo_data=b'photo-bytes', photo_content_type='image/png',
        )
        AcademyMonthlyRentPayment.objects.create(
            academy=academy, month=date(today.year, today.month, 1),
            expected_amount=1000, paid_amount=700, supplied_amount=500,
            payment_date=today, supplied_date=today,
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
        self.assertNotContains(response, 'أعضاء مجلس الإدارة')
        self.assertEqual(response.context['report_type'], 'academies')
        self.assertEqual(len(response.context['allowed_report_options']), 6)
        for label in ['بيانات الموظفين', 'بيانات الأكاديميات', 'الدخل الشهري', 'المصروفات', 'الكافيتريا']:
            self.assertContains(response, label)
        self.assertNotContains(response, 'تقرير المرتبات الشهرية والبونص')
        self.assertNotContains(response, 'تقرير مبالغ التأمين')
        self.assertContains(response, 'تصدير PDF')
        self.assertContains(response, 'طباعة')
        self.assertContains(response, 'name="signature_title"')
        self.assertContains(response, 'print-report-header')

        response = self.client.get(reverse('reports_home'), {
            'report_type': 'academies', 'academy_id': academy.pk, 'section': 'staff',
        })
        self.assertContains(response, 'أكاديمية تقرير')
        self.assertContains(response, 'بيانات المدربين والإداريين')
        self.assertContains(response, 'بيانات اللاعبين')
        self.assertContains(response, 'كروت التعارف')
        self.assertContains(response, report_coach.name)
        self.assertContains(response, report_coach.job_title)
        self.assertContains(response, reverse('academy_member_qr', args=[academy.pk, report_coach.pk]))
        self.assertContains(response, 'data:image/png;base64,')

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

        outside_academy = Academy.objects.create(
            name='أكاديمية سداد خارج الفترة', sport_activity='سباحة',
            company_name='شركة خارج الفترة', manager_name='مدير خارج الفترة',
            manager_phone='01000000999',
            operation_place=OPERATION_PLACE_CHOICES[0][0],
            contract_start_date=date(today.year, 1, 1),
            contract_end_date=date(today.year, 12, 31),
            subscription_type='fixed', monthly_subscription=2000,
        )
        AcademyMonthlyRentPayment.objects.create(
            academy=outside_academy, month=date(today.year, today.month, 1),
            expected_amount=2000, paid_amount=1500, supplied_amount=1500,
            payment_date=today - timedelta(days=2),
            supplied_date=today - timedelta(days=2),
        )
        response = self.client.get(reverse('reports_home'), {
            'report_type': 'monthly_income', 'range_mode': 'custom',
            'date_from': today.isoformat(), 'date_to': today.isoformat(),
        })
        self.assertEqual(response.context['range_mode'], 'custom')
        self.assertEqual(
            [row['academy'].pk for row in response.context['income_rows']],
            [academy.pk],
        )
        self.assertEqual(response.context['income_paid_total'], 700)
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

    def test_dashboard_shows_activity_cards_instead_of_financial_cards(self):
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
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['activities']), 1)
        self.assertEqual(response.context['activities'][0]['academy_count'], 1)
        self.assertEqual(response.content.decode().count('class="activity-card"'), 1)
        self.assertNotContains(response, 'dashboard-card-col')

    def test_dashboard_does_not_leak_activities_between_branches(self):
        first = Branch.objects.create(name='الفرع الرئيسي')
        second = Branch.objects.create(name='الفرع الثاني')
        Academy.objects.create(
            branch=first, name='أكاديمية الفرع الأول', sport_activity='كرة سلة',
            company_name='شركة', manager_name='مدير', manager_phone='01000000000',
            operation_place=OPERATION_PLACE_CHOICES[0][0],
            contract_start_date=date.today(), contract_end_date=date.today(),
            subscription_type='fixed',
        )
        response = self.client.get(reverse('dashboard'), {
            'branch_id': second.pk,
            'training_year': '2027-2028',
        })
        self.assertEqual(response.context['activities'], [])
        self.assertEqual(response.context['training_year'], '2027-2028')
        self.assertNotContains(response, 'كرة سلة')

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

    def test_daily_booking_list_filters_by_calendar_date_and_uses_single_line_rows(self):
        selected_date = date.today()
        other_date = selected_date + timedelta(days=1)
        common = {
            'venue': OPERATION_PLACE_CHOICES[0][0],
            'start_time': TIME_CHOICES[0][0],
            'end_time': TIME_CHOICES[2][0],
            'customer_phone': '01000000111',
            'total_amount': 500,
            'advance_payment': 100,
            'remaining_amount': 400,
        }
        DailyBooking.objects.create(
            **common, booking_date=selected_date, customer_name='حجز اليوم المختار',
        )
        DailyBooking.objects.create(
            **{**common, 'customer_phone': '01000000222'},
            booking_date=other_date, customer_name='حجز يوم آخر',
        )
        response = self.client.get(reverse('booking_list'), {
            'booking_date': selected_date.isoformat(),
        })
        self.assertContains(response, 'حجز اليوم المختار')
        self.assertNotContains(response, 'حجز يوم آخر')
        self.assertContains(response, f'value="{selected_date.isoformat()}"')
        self.assertContains(response, 'white-space:nowrap!important')
        self.assertContains(response, 'min-width:1650px')
        self.assertNotContains(response, '<th>المقدم</th>', html=True)
        self.assertNotContains(response, '<th>المتبقي</th>', html=True)

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
        self.assertContains(response, 'operation-filter-date')
        self.assertContains(response, 'width:175px!important')
        self.assertContains(response, 'operation-filter-period')
        self.assertContains(response, 'width:310px!important')

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

    def test_staff_member_screen_combines_coaches_and_admins(self):
        academy = Academy.objects.create(
            name='أكاديمية الأعضاء', sport_activity='كرة قدم', company_name='شركة',
            manager_name='مدير', manager_phone='01000000002',
            operation_place=OPERATION_PLACE_CHOICES[0][0],
            contract_start_date=date.today(), contract_end_date=date.today() + timedelta(days=30),
        )
        AcademyMember.objects.create(
            academy=academy, role=AcademyMember.ROLE_ADMIN,
            name='إداري موجود', job_title='مدير إداري',
        )
        list_url = reverse('academy_member_list', args=[academy.pk]) + '?role=staff'
        response = self.client.get(list_url)
        self.assertContains(response, 'إضافة مدرب أو إداري')
        self.assertContains(response, 'إداري موجود')
        self.assertNotContains(response, 'إضافة لاعب')

        create_url = reverse('academy_member_create', args=[academy.pk]) + '?role=staff'
        response = self.client.get(create_url)
        self.assertContains(response, 'id_role')
        self.assertContains(response, '<option value="coach">مدرب</option>', html=True)
        self.assertContains(response, '<option value="admin">إداري</option>', html=True)
        self.assertNotContains(response, 'id_monthly_subscription')
        self.assertNotContains(response, 'id_birth_date')
        self.assertContains(response, 'id_job_title')
        self.assertContains(response, 'id_photo')
        self.assertContains(response, 'حفظ وتوليد QR Code')
        coach_photo = SimpleUploadedFile('coach.png', b'fake-image-content', content_type='image/png')
        response = self.client.post(create_url, {
            'role': AcademyMember.ROLE_COACH,
            'name': 'مدرب اختبار', 'phone': '', 'national_id': '',
            'job_title': 'مدرب لياقة', 'photo': coach_photo,
            'is_active': 'on', 'notes': '', 'submit_action': 'generate_qr',
        })
        self.assertEqual(response.status_code, 302)
        coach = AcademyMember.objects.get(name='مدرب اختبار')
        self.assertEqual(coach.role, AcademyMember.ROLE_COACH)
        self.assertEqual(coach.job_title, 'مدرب لياقة')
        self.assertEqual(bytes(coach.photo_data), b'fake-image-content')
        qr_response = self.client.get(reverse('academy_member_qr', args=[academy.pk, coach.pk]))
        self.assertEqual(qr_response.status_code, 200)
        self.assertEqual(qr_response['Content-Type'], 'image/svg+xml')
        self.assertIn(b'<svg', qr_response.content)

        player_url = reverse('academy_member_create', args=[academy.pk]) + '?role=player'
        response = self.client.get(player_url)
        self.assertContains(response, 'id_birth_date')
        self.assertContains(response, 'type="date"')
        self.assertContains(response, 'id_monthly_subscription')
        self.assertContains(response, 'id_photo')
        self.assertNotContains(response, 'id_job_title')

    def test_training_year_selector_and_portrait_identity_cards(self):
        profile, _ = UserPermission.objects.get_or_create(user=self.user)
        profile.can_reports = True
        profile.save()
        branch = Branch.objects.create(
            name='British International College of Cairo',
            short_name='BICC',
            logo='branches/logos/test-branch-logo.png',
        )
        academy = Academy.objects.create(
            branch=branch,
            name='أكاديمية البطاقات', sport_activity='كرة قدم', company_name='Card Academy Company',
            manager_name='مدير البطاقات', manager_phone='01000000003',
            operation_place=OPERATION_PLACE_CHOICES[0][0],
            contract_start_date=date.today(), contract_end_date=date.today() + timedelta(days=30),
            logo_data=b'academy-logo', logo_content_type='image/png',
        )
        coach = AcademyMember.objects.create(
            academy=academy, role=AcademyMember.ROLE_COACH,
            name='مدرب البطاقة', job_title='مدرب عام',
        )
        admin_member = AcademyMember.objects.create(
            academy=academy, role=AcademyMember.ROLE_ADMIN,
            name='إداري البطاقة', job_title='مدير فريق',
        )
        player = AcademyMember.objects.create(
            academy=academy, role=AcademyMember.ROLE_PLAYER,
            name='لاعب البطاقة', birth_date=date(2010, 1, 1),
        )
        app_setting = AppSetting.current()
        app_setting.company_short_name = 'EESS CARD'
        app_setting.save(update_fields=['company_short_name'])

        response = self.client.get(reverse('academy_list'), {'training_year': '2099-2100'})
        self.assertContains(response, '2026 - 2027')
        self.assertContains(response, '2099 - 2100')
        self.assertEqual(response.context['training_year'], '2099-2100')
        self.assertEqual(self.client.session['training_year'], '2099-2100')
        self.assertNotContains(response, academy.name)
        self.assertNotContains(response, '>المدربين<')

        cards_url = reverse('academy_id_cards')
        response = self.client.get(cards_url, {
            'academy_id': academy.pk,
            'training_year': '2027-2028',
            'card_group': 'staff',
        })
        self.assertContains(response, 'كروت تعارف المدربين والإداريين')
        self.assertContains(response, coach.name)
        self.assertContains(response, admin_member.name)
        self.assertNotContains(response, player.name)
        self.assertContains(response, 'width:54mm')
        self.assertContains(response, 'height:86mm')
        self.assertContains(response, '2027-2028')
        self.assertContains(response, reverse('academy_member_qr', args=[academy.pk, coach.pk]))
        self.assertContains(response, branch.logo.url)
        self.assertContains(response, 'BICC')
        self.assertContains(response, 'EESS CARD')
        self.assertContains(response, 'background-color:#fff')
        self.assertContains(response, 'border:1.15mm solid #082d61')
        self.assertContains(response, 'linear-gradient(132deg')
        self.assertContains(response, 'تصدير PDF')
        self.assertContains(response, 'طباعة')

        response = self.client.get(cards_url, {
            'academy_id': academy.pk,
            'training_year': '2027-2028',
            'card_group': 'player',
        })
        self.assertContains(response, player.name)
        self.assertNotContains(response, coach.name)

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
