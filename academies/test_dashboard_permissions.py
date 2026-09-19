from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from .forms import EESSPermissionForm
from .models import Branch, UserPermission


@override_settings(SECURE_SSL_REDIRECT=False)
class DashboardPermissionTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name='Dashboard branch')
        self.user = User.objects.create_user('dashboard_user', password='pass', is_staff=True)
        self.profile = UserPermission.objects.create(user=self.user, can_security=True)
        self.client.force_login(self.user)

    def test_staff_and_superuser_have_dashboard_without_explicit_permission(self):
        response = self.client.get(reverse('dashboard'))
        self.assertTemplateUsed(response, 'academies/dashboard.html')
        self.assertContains(response, 'href="/dashboard/"')
        self.user.is_staff = False
        self.user.is_superuser = True
        self.user.save(update_fields=['is_staff', 'is_superuser'])
        response = self.client.get(reverse('dashboard'))
        self.assertTemplateUsed(response, 'academies/dashboard.html')
        self.assertContains(response, 'href="/dashboard/"')

    def test_admin_ignores_security_only_and_sees_all_sidebar_modules(self):
        self.profile.security_only = True
        self.profile.security_branch = self.branch
        self.profile.can_dashboard = True
        self.profile.save()
        response = self.client.get(reverse('dashboard'))
        self.assertTemplateUsed(response, 'academies/dashboard.html')
        for label in ['لوحة التحكم', 'الأكاديميات', 'الحجز اليومي', 'إيجارات الأكاديميات',
                      'التشغيل', 'الأمن', 'إدارة الشركة', 'الحسابات', 'الكافيتريا',
                      'التقارير', 'الإعدادات', 'لوحة الإدارة']:
            self.assertContains(response, label)

    def test_superuser_ignores_academy_only_restriction(self):
        self.user.is_staff = False
        self.user.is_superuser = True
        self.user.save(update_fields=['is_staff', 'is_superuser'])
        self.profile.academy_only = True
        self.profile.save(update_fields=['academy_only'])
        response = self.client.get(reverse('accounts_home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'لوحة التحكم')

    def test_permission_form_can_save_security_without_academy(self):
        form = EESSPermissionForm(data={'security_only': 'on', 'security_branch': self.branch.pk}, instance=self.profile)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.security_only)
        self.assertFalse(self.profile.can_dashboard)
        self.assertFalse(self.profile.academy_only)
