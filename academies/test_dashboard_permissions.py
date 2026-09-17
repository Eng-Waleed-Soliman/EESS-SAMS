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

    def test_dashboard_is_explicit_even_for_staff_and_superuser(self):
        for superuser in (False, True):
            self.user.is_superuser = superuser
            self.user.save()
            response = self.client.get(reverse('dashboard'))
            self.assertTemplateUsed(response, 'academies/access_landing.html')
            self.assertNotContains(response, 'href="/dashboard/"')
        self.profile.can_dashboard = True
        self.profile.save()
        response = self.client.get(reverse('dashboard'))
        self.assertTemplateUsed(response, 'academies/dashboard.html')
        self.assertContains(response, 'href="/dashboard/"')

    def test_security_only_overrides_dashboard_permission(self):
        self.profile.security_only = True
        self.profile.security_branch = self.branch
        self.profile.can_dashboard = True
        self.profile.save()
        self.assertRedirects(self.client.get(reverse('dashboard')), reverse('security_home'))
        self.assertNotContains(self.client.get(reverse('security_home')), 'href="/dashboard/"')

    def test_permission_form_can_save_security_without_academy(self):
        form = EESSPermissionForm(data={'security_only': 'on', 'security_branch': self.branch.pk}, instance=self.profile)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.security_only)
        self.assertFalse(self.profile.can_dashboard)
        self.assertFalse(self.profile.academy_only)
