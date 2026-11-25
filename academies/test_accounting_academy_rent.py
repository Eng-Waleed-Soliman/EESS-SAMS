from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Academy, Branch, UserPermission


@override_settings(SECURE_SSL_REDIRECT=False)
class AccountingAcademyRentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='Accounting', password='test-password')
        UserPermission.objects.create(user=self.user, can_accounts=True)
        self.branch = Branch.objects.create(name='BICC')
        Academy.objects.create(
            branch=self.branch,
            name='أكاديمية اختبار الحسابات',
            sport_activity='كرة قدم',
            company_name='EESS',
            manager_name='مدير الأكاديمية',
            manager_phone='01000000000',
            operation_place='ملعب كرة القدم #1',
            contract_start_date=date(2026, 1, 1),
            contract_end_date=date(2027, 12, 31),
            subscription_type='fixed',
            monthly_subscription=1000,
        )
        self.client.force_login(self.user)

    def test_accounting_user_can_open_academy_rent_screen_without_report_permission(self):
        response = self.client.get(reverse('academy_rent_payments'), {
            'month': '2026-11', 'branch_id': self.branch.pk,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'إيجارات الأكاديميات الشهرية')
        self.assertContains(response, 'أكاديمية اختبار الحسابات')
        self.assertContains(response, reverse('academy_rent_payments'))
