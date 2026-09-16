from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import EESSPermissionForm
from .models import Academy, AcademyMember, UserPermission
from .constants import OPERATION_PLACE_CHOICES


@override_settings(SECURE_SSL_REDIRECT=False)
class RestrictedAcademyAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('limited-user', password='safe-password-9274')
        self.academy = self.create_academy('الأكاديمية المسموحة')
        self.other = self.create_academy('أكاديمية محجوبة')
        self.player = AcademyMember.objects.create(academy=self.academy, role='player', name='اللاعب المسموح')
        AcademyMember.objects.create(academy=self.other, role='player', name='لاعب محجوب')
        AcademyMember.objects.create(academy=self.academy, role='coach', name='مدرب محجوب')
        self.profile = UserPermission.objects.create(
            user=self.user, academy_only=True, restricted_academy=self.academy,
            academy_sections=['players'], can_accounts=True, can_settings=True,
        )
        self.client.force_login(self.user)

    def create_academy(self, name):
        return Academy.objects.create(
            name=name, sport_activity='Football', company_name='Company', manager_name='Manager',
            manager_phone='01000000000', operation_place=OPERATION_PLACE_CHOICES[0][0],
            contract_start_date=date(2026, 7, 1), contract_end_date=date(2027, 6, 30),
        )

    def test_portal_only_shows_selected_academy_and_section(self):
        page = self.client.get(reverse('restricted_academy_portal'))
        self.assertContains(page, self.player.name)
        for hidden in ['لاعب محجوب', 'مدرب محجوب', 'لوحة التحكم', 'الحسابات', 'الإعدادات', 'الاشتراكات الشهرية', 'المجموعات']:
            self.assertNotContains(page, hidden)
        self.assertEqual(self.client.get(reverse('restricted_academy_portal'), {'section': 'subscriptions'}).status_code, 403)

    def test_direct_urls_and_mutations_are_blocked_even_with_broad_flags(self):
        portal = reverse('restricted_academy_portal')
        for url in ['/dashboard/', '/accounts/', '/admin/', '/reports/', '/users/', '/',
                    reverse('academy_member_list', args=[self.other.pk]),
                    reverse('academy_member_list', args=[self.academy.pk])]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, portal)
            self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.assertEqual(self.client.post(portal, {}).status_code, 403)
        self.assertEqual(self.client.get('/media-db/member/1/photo/').status_code, 302)

    def test_missing_academy_fails_closed_and_login_goes_straight_to_portal(self):
        self.client.logout()
        response = self.client.post(reverse('login'), {'username': self.user.username, 'password': 'safe-password-9274', 'next': '/accounts/'})
        self.assertEqual(response.url, reverse('restricted_academy_portal'))
        self.profile.restricted_academy = None
        self.profile.save(update_fields=['restricted_academy'])
        self.assertEqual(self.client.get(reverse('restricted_academy_portal')).status_code, 403)
        self.assertEqual(self.client.get('/accounts/').status_code, 302)

    def test_permission_form_requires_scope_and_saves_selected_sections(self):
        invalid = EESSPermissionForm({'academy_only': 'on'}, instance=self.profile)
        self.assertFalse(invalid.is_valid())
        self.assertIn('restricted_academy', invalid.errors)
        self.assertIn('academy_sections', invalid.errors)
        valid = EESSPermissionForm({'academy_only': 'on', 'restricted_academy': self.academy.pk, 'academy_sections': ['players']}, instance=self.profile)
        self.assertTrue(valid.is_valid(), valid.errors)
        saved = valid.save()
        self.assertEqual(saved.academy_sections, ['players'])
