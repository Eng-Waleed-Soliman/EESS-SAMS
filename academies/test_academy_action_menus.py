from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Academy


@override_settings(SECURE_SSL_REDIRECT=False)
class AcademyActionMenusTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='academy-action-admin',
            email='academy-actions@example.com',
            password='test-password',
        )
        self.client.force_login(self.user)
        self.academy = Academy.objects.create(
            name='أكاديمية قوائم الإجراءات',
            sport_activity='كرة قدم',
            company_name='شركة الاختبار',
            manager_name='مدير الاختبار',
            manager_phone='01000000000',
            operation_place='ملعب الاختبار',
            contract_start_date=date.today(),
            contract_end_date=date.today() + timedelta(days=30),
        )

    def test_each_academy_row_uses_people_and_settings_dropdowns(self):
        response = self.client.get(reverse('academy_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="academy-row-menu academy-people-menu"')
        self.assertContains(response, 'class="academy-row-menu academy-settings-menu"')
        self.assertContains(response, '🧑‍🏫⚽')
        self.assertContains(response, '⚙️')
        self.assertContains(response, 'المدربين والإداريين')
        self.assertContains(response, 'اللاعبين')
        self.assertContains(response, reverse('academy_update', args=[self.academy.pk]))
        self.assertContains(response, reverse('academy_delete', args=[self.academy.pk]))
        self.assertContains(response, "document.querySelectorAll('.academy-row-menu')")
