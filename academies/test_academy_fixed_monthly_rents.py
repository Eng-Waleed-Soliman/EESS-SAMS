import json
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .constants import OPERATION_PLACE_CHOICES
from .forms import AcademyForm, FIXED_RENT_MONTHS
from .models import Academy
from .views import _calculate_fixed_income_with_operation_changes


@override_settings(SECURE_SSL_REDIRECT=False)
class AcademyFixedMonthlyRentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('fixed-rent-admin', 'admin@example.com', 'password')
        self.client.force_login(self.user)
        self.place = OPERATION_PLACE_CHOICES[0][0]

    def payload(self):
        data = {
            'name': 'أكاديمية الإيجارات المتغيرة شهريًا',
            'sport_activity': 'كرة قدم',
            'company_name': 'شركة اختبار',
            'manager_name': 'مدير اختبار',
            'manager_phone': '01000000999',
            'contract_start_date': '2026-07-01',
            'contract_end_date': '2027-06-30',
            'subscription_type': 'fixed',
            'eess_share_percentage': 0,
            'security_deposit': 0,
            'training_schedule_data': json.dumps([{'place': self.place}]),
            'operation_place': [self.place],
        }
        for index, (month, _label) in enumerate(FIXED_RENT_MONTHS, start=1):
            data[f'fixed_rent_{month}'] = index * 1000
        return data

    def test_fixed_rents_save_per_month_total_and_feed_monthly_calculation(self):
        form = AcademyForm(data=self.payload())
        self.assertTrue(form.is_valid(), form.errors.as_json())
        academy = form.save()
        self.assertEqual(academy.fixed_rent_for_month(2026, 7), 1000)
        self.assertEqual(academy.fixed_rent_for_month(2026, 12), 6000)
        self.assertEqual(academy.fixed_rent_for_month(2027, 1), 7000)
        self.assertEqual(academy.fixed_rent_for_month(2027, 6), 12000)
        self.assertEqual(academy.fixed_rent_total, 78000)
        self.assertEqual(_calculate_fixed_income_with_operation_changes(academy, 2026, 8), 2000)

        page = self.client.get(reverse('academy_update', args=[academy.pk]))
        self.assertContains(page, 'قيم الإيجار الشهري من يوليو إلى يونيو')
        self.assertContains(page, 'id="id_fixed_rent_7"')
        self.assertContains(page, 'id="id_fixed_rent_6"')
        self.assertContains(page, 'id="fixedRentTotal"')
        self.assertNotContains(page, 'id="id_monthly_subscription"')

    def test_all_twelve_fixed_months_are_required(self):
        data = self.payload()
        data['fixed_rent_5'] = ''
        form = AcademyForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('fixed_rent_5', form.errors)
        self.assertFalse(Academy.objects.exists())

    def test_legacy_single_fixed_value_remains_compatible(self):
        data = self.payload()
        for month, _label in FIXED_RENT_MONTHS:
            data.pop(f'fixed_rent_{month}')
        data['monthly_subscription'] = 2500
        form = AcademyForm(data=data)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        academy = form.save()
        self.assertEqual(academy.fixed_rent_total, 30000)
        self.assertTrue(all(value == 2500 for value in academy.fixed_monthly_rents.values()))
