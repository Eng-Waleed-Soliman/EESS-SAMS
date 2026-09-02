from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Branch, Employee, PayrollAdjustment, UserPermission


@override_settings(SECURE_SSL_REDIRECT=False)
class PayrollAdjustmentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='payroll-tester', password='test-password')
        profile, _ = UserPermission.objects.get_or_create(user=self.user)
        profile.can_accounts = True
        profile.save()
        self.client.force_login(self.user)
        self.branch = Branch.objects.create(name='Payroll branch')
        self.employee = Employee.objects.create(name='موظف الاختبار', branch=self.branch, salary=5000)

    def post_movement(self, kind, amount, **extra):
        data = {'employee': self.employee.pk, 'month': '2026-08', 'amount': amount,
                'reason': 'سبب الحركة', 'branch_context': self.branch.pk}
        data.update(extra)
        return self.client.post(reverse('payroll_adjustments', args=[kind]), data)

    def summary(self, month='2026-08'):
        response = self.client.get(reverse('accounts_home'), {'month': month, 'branch_id': self.branch.pk})
        self.assertEqual(response.status_code, 200)
        return response.context['summary']

    def test_monthly_totals_receipt_and_wage_expense(self):
        for kind, amount in [('reward', 500), ('reward', 200), ('deduction', 100), ('advance', 1000)]:
            self.assertEqual(self.post_movement(kind, amount).status_code, 302)
        self.assertEqual(self.post_movement('reward', 900, month='2026-09').status_code, 302)
        other = Employee.objects.create(name='Other', branch=Branch.objects.create(name='Other branch'), salary=2000)
        PayrollAdjustment.objects.create(employee=other, kind='reward', amount=800, month=date(2026, 8, 1), reason='Other branch')
        summary = self.summary()
        row = summary['payroll_rows'][0]
        self.assertEqual((row['salary'], row['reward'], row['deduction'], row['advance'], row['total']),
                         (5000, 700, 100, 1000, 4600))
        self.assertEqual(summary['payroll_total'], 4600)
        self.assertEqual(summary['payroll_expense_total'], 5600)
        self.assertEqual(summary['total_expenses'], 5600)
        self.assertEqual(summary['net_profit'], -5600)
        self.assertEqual(self.summary('2026-09')['payroll_total'], 5900)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.salary, 5000)
        self.assertEqual(PayrollAdjustment.objects.filter(created_by=self.user).count(), 5)
        receipt = self.client.get(reverse('payroll_receipt', args=[self.employee.pk]),
                                  {'month': '2026-08', 'branch_id': self.branch.pk})
        self.assertEqual(receipt.status_code, 200)
        self.assertContains(receipt, '4,600 جنيه مصري')
        for label in ['المكافآت', 'الخصومات', 'السلف', 'with-adjustments']:
            self.assertContains(receipt, label)
        with patch('academies.views._bonus_for_employee', return_value=300):
            summary = self.summary()
        self.assertEqual(summary['payroll_rows'][0]['bonus'], 300)
        self.assertEqual(summary['payroll_total'], 4900)

    def test_edit_move_month_and_delete_recalculate(self):
        self.post_movement('reward', 500)
        movement = PayrollAdjustment.objects.get()
        url = reverse('payroll_adjustment_edit', args=['reward', movement.pk])
        response = self.client.get(url, {'month': '2026-08', 'branch_id': self.branch.pk, 'action': 'delete'})
        self.assertContains(response, 'value="2026-08"')
        self.assertTrue(PayrollAdjustment.objects.filter(pk=movement.pk).exists())
        response = self.client.post(url, {'employee': self.employee.pk, 'month': '2026-09', 'amount': 800,
                                          'reason': 'Updated reason', 'branch_context': self.branch.pk})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.summary()['payroll_total'], 5000)
        self.assertEqual(self.summary('2026-09')['payroll_total'], 5800)
        response = self.client.post(url, {'action': 'delete', 'branch_context': self.branch.pk})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PayrollAdjustment.objects.exists())
        self.assertEqual(self.summary('2026-09')['payroll_total'], 5000)

    def test_form_validation_and_branch_scope(self):
        for payload in [{'amount': 0}, {'amount': -10}, {'amount': '1.5'}, {'reason': ''}, {'month': 'invalid'}]:
            amount = payload.pop('amount', 100)
            response = self.post_movement('reward', amount, **payload)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
        other = Employee.objects.create(name='Other', branch=Branch.objects.create(name='Other branch'))
        self.assertEqual(self.post_movement('reward', 100, employee=other.pk).status_code, 200)
        self.assertFalse(PayrollAdjustment.objects.exists())
        movement = PayrollAdjustment.objects.create(employee=other, kind='reward', amount=100,
                                                    reason='Other', month=date(2026, 8, 1))
        response = self.client.post(reverse('payroll_adjustment_edit', args=['reward', movement.pk]),
                                    {'action': 'delete', 'branch_context': self.branch.pk})
        self.assertEqual(response.status_code, 404)
        self.assertTrue(PayrollAdjustment.objects.filter(pk=movement.pk).exists())
        self.assertEqual(self.post_movement('unknown', 100).status_code, 404)

    def test_permissions_and_negative_receipt(self):
        self.post_movement('advance', 6000)
        self.assertEqual(self.summary()['payroll_total'], -1000)
        receipt = self.client.get(reverse('payroll_receipt', args=[self.employee.pk]),
                                  {'month': '2026-08', 'branch_id': self.branch.pk})
        self.assertEqual(receipt.status_code, 302)
        profile = UserPermission.objects.get(user=self.user)
        profile.can_accounts = False
        profile.can_reports = True
        profile.save()
        self.assertEqual(self.post_movement('reward', 100).status_code, 302)
        self.assertEqual(PayrollAdjustment.objects.count(), 1)
        self.client.logout()
        self.assertEqual(self.post_movement('reward', 100).status_code, 302)
        self.assertEqual(PayrollAdjustment.objects.count(), 1)

    def test_three_screens_have_calendar_and_accounts_buttons(self):
        response = self.client.get(reverse('accounts_home'), {'month': '2026-08', 'branch_id': self.branch.pk})
        for kind, title in PayrollAdjustment.KIND_CHOICES:
            url = reverse('payroll_adjustments', args=[kind])
            self.assertContains(response, url)
            page = self.client.get(url, {'month': '2026-08', 'branch_id': self.branch.pk})
            self.assertContains(page, title)
            self.assertContains(page, 'type="month"')
            self.assertContains(page, 'value="2026-08"')
            self.assertContains(page, 'name="employee"')
            self.assertContains(page, 'name="amount"')
            self.assertContains(page, 'name="reason"')

    def test_employee_with_payroll_history_cannot_be_deleted(self):
        self.post_movement('reward', 100)
        response = self.client.post(reverse('employee_delete', args=[self.employee.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Employee.objects.filter(pk=self.employee.pk).exists())
        self.assertEqual(PayrollAdjustment.objects.count(), 1)
