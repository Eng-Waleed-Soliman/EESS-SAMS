from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import FinancialVoucher, UserPermission


@override_settings(SECURE_SSL_REDIRECT=False)
class FinancialVoucherDeleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='accounts-user', password='test-password')
        UserPermission.objects.create(user=self.user, can_accounts=True)
        self.client.force_login(self.user)
        self.voucher = FinancialVoucher.objects.create(
            voucher_type=FinancialVoucher.TYPE_DISBURSEMENT,
            amount=1250,
            statement='اختبار حذف أمر صرف',
            voucher_date=date(2026, 9, 15),
            signature_title='المدير المالي',
            created_by=self.user,
        )

    def test_register_shows_delete_button_next_to_edit(self):
        response = self.client.get(reverse('financial_voucher_list'))

        self.assertContains(response, reverse('financial_voucher_update', args=[self.voucher.pk]))
        self.assertContains(response, reverse('financial_voucher_delete', args=[self.voucher.pk]))
        self.assertContains(response, 'هل أنت متأكد من حذف الأمر المالي')

    def test_delete_requires_post_and_returns_to_same_voucher_type(self):
        delete_url = reverse('financial_voucher_delete', args=[self.voucher.pk])

        get_response = self.client.get(delete_url)
        self.assertRedirects(get_response, reverse('financial_voucher_list'))
        self.assertTrue(FinancialVoucher.objects.filter(pk=self.voucher.pk).exists())

        post_response = self.client.post(delete_url)
        expected_url = reverse('financial_voucher_list') + '?type=disbursement'
        self.assertRedirects(post_response, expected_url)
        self.assertFalse(FinancialVoucher.objects.filter(pk=self.voucher.pk).exists())

    def test_user_without_accounts_permission_cannot_delete(self):
        unauthorized = User.objects.create_user(username='unauthorized', password='test-password')
        self.client.force_login(unauthorized)

        response = self.client.post(reverse('financial_voucher_delete', args=[self.voucher.pk]))

        self.assertRedirects(response, reverse('dashboard'))
        self.assertTrue(FinancialVoucher.objects.filter(pk=self.voucher.pk).exists())
