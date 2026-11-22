from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    Academy,
    FinancialVoucher,
    FinancialVoucherAcademyAllocation,
    FinancialVoucherIncomeAllocation,
    UserPermission,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class TreasuryRegisterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='treasury-user', password='test-password')
        UserPermission.objects.create(user=self.user, can_accounts=True)
        self.client.force_login(self.user)
        self.academy = Academy.objects.create(
            name='أكاديمية أبطال', sport_activity='كرة قدم', company_name='EESS',
            manager_name='مدير الأكاديمية', manager_phone='01000000000',
            operation_place='الملعب', contract_start_date=date(2026, 1, 1),
            contract_end_date=date(2026, 12, 31),
        )
        self.supply = FinancialVoucher.objects.create(
            voucher_type=FinancialVoucher.TYPE_SUPPLY, amount=2500,
            income_source=FinancialVoucher.SOURCE_SPORTS_ACADEMIES,
            statement='توريد أكاديمية', voucher_date=date(2026, 11, 10),
            signature_title='مدير النشاط الرياضي', created_by=self.user,
        )
        FinancialVoucherAcademyAllocation.objects.create(
            voucher=self.supply, academy=self.academy, amount=2500,
        )
        FinancialVoucherIncomeAllocation.objects.create(
            voucher=self.supply,
            source=FinancialVoucher.SOURCE_SPORTS_ACADEMIES,
            amount=2500,
        )
        self.disbursement = FinancialVoucher.objects.create(
            voucher_type=FinancialVoucher.TYPE_DISBURSEMENT, amount=700,
            statement='صيانة الملعب', voucher_date=date(2026, 11, 12),
            signature_title='مدير النشاط الرياضي', created_by=self.user,
        )

    def test_accounts_filter_is_automatic_and_links_to_treasury(self):
        response = self.client.get(reverse('accounts_home'), {'month': '2026-11', 'branch_id': 'all'})
        self.assertContains(response, 'onchange="this.form.submit()"', count=2)
        self.assertContains(response, '>الخزينة</a>', html=False)
        self.assertNotContains(response, '>عرض</button>', html=False)

    def test_supply_and_disbursement_tabs_and_review_flow(self):
        treasury_url = reverse('treasury_register')
        response = self.client.get(treasury_url, {
            'tab': 'supply', 'month': '2026-11', 'branch_id': 'all',
        })
        self.assertContains(response, 'أكاديمية أبطال')
        self.assertContains(response, '2500')
        self.assertNotContains(response, 'صيانة الملعب')

        review_response = self.client.post(reverse('treasury_review', args=[self.supply.pk]), {
            'tab': 'supply', 'month': '2026-11', 'branch_id': 'all',
        })
        self.assertRedirects(
            review_response,
            treasury_url + '?tab=supply&month=2026-11&branch_id=all',
        )
        self.supply.refresh_from_db()
        self.assertIsNotNone(self.supply.reviewed_at)
        self.assertEqual(self.supply.reviewed_by, self.user)

        reviewed = self.client.get(treasury_url, {
            'tab': 'supply', 'month': '2026-11', 'branch_id': 'all',
        })
        self.assertContains(reviewed, 'تمت المراجعة')
        self.assertContains(reviewed, 'تصدير PDF')

        expenses = self.client.get(treasury_url, {
            'tab': 'disbursement', 'month': '2026-11', 'branch_id': 'all',
        })
        self.assertContains(expenses, 'صيانة الملعب')
        self.assertContains(expenses, '700')
        self.assertNotContains(expenses, 'أكاديمية أبطال')
