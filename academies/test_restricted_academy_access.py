from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import EESSPermissionForm
from .models import Academy, AcademyMember, UserPermission, AcademyTrainingGroup, AcademyTrainingGroupPlayer, AcademyTrainingAttendance, AcademyPlayerMonthlySubscription
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

    def grant(self, *permissions):
        self.profile.academy_sections = list(permissions)
        self.profile.save(update_fields=['academy_sections'])

    def test_add_player_is_optional_and_forces_academy_and_role(self):
        url = reverse('restricted_academy_portal') + '?section=players_add'
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {'name': 'لاعب جديد'}).status_code, 403)
        self.grant('players_add')
        self.assertContains(self.client.get(url), 'حفظ اللاعب')
        response = self.client.post(url, {
            'name': 'لاعب جديد', 'phone': '01011111111', 'is_active': 'on',
            'academy': self.other.pk, 'role': 'coach', 'is_published_on_website': 'on',
        })
        self.assertEqual(response.status_code, 302)
        player = AcademyMember.objects.get(name='لاعب جديد')
        self.assertEqual(player.academy, self.academy)
        self.assertEqual(player.role, AcademyMember.ROLE_PLAYER)
        self.assertFalse(player.is_published_on_website)
        self.assertEqual(self.client.get(reverse('restricted_academy_portal'), {'section': 'players'}).status_code, 403)

    def test_placement_only_uses_authorized_groups_and_eligible_players(self):
        group = AcademyTrainingGroup.objects.create(academy=self.academy, name='مجموعة مسموحة', training_days=[2])
        other_group = AcademyTrainingGroup.objects.create(academy=self.other, name='مجموعة محجوبة', training_days=[2])
        outsider = self.other.members.get(role='player')
        other_assignment = AcademyTrainingGroupPlayer.objects.create(group=other_group, player=outsider)
        url = reverse('restricted_academy_portal') + '?section=placement'
        self.assertEqual(self.client.post(url, {'group': group.pk, 'player': self.player.pk}).status_code, 403)
        self.grant('placement')
        page = self.client.get(url)
        self.assertNotContains(page, other_group.name)
        self.assertNotContains(page, outsider.name)
        self.assertEqual(self.client.post(url, {'group': other_group.pk, 'player': self.player.pk}).status_code, 404)
        self.assertEqual(self.client.post(url, {'group': group.pk, 'player': outsider.pk}).status_code, 200)
        self.assertEqual(self.client.post(url, {'group': group.pk, 'player': self.player.pk}).status_code, 302)
        assignment = AcademyTrainingGroupPlayer.objects.get(group=group, player=self.player)
        self.assertNotIn(self.player, self.client.get(url).context['placement_form'].fields['player'].queryset)
        self.assertEqual(self.client.post(url, {'group': group.pk, 'action': 'remove', 'assignment': other_assignment.pk}).status_code, 404)
        self.assertTrue(AcademyTrainingGroupPlayer.objects.filter(pk=other_assignment.pk).exists())
        self.assertEqual(self.client.post(url, {'group': group.pk, 'action': 'remove', 'assignment': assignment.pk}).status_code, 302)
        self.assertFalse(AcademyTrainingGroupPlayer.objects.filter(pk=assignment.pk).exists())

    def test_attendance_view_and_record_permissions_are_independent(self):
        group = AcademyTrainingGroup.objects.create(academy=self.academy, name='مجموعة حضور', training_days=[2])
        other_group = AcademyTrainingGroup.objects.create(academy=self.other, name='حضور محجوب', training_days=[2])
        AcademyTrainingGroupPlayer.objects.create(group=group, player=self.player)
        url = reverse('restricted_academy_portal') + '?section=attendance'
        self.grant('attendance')
        page = self.client.get(url, {'group': group.pk, 'month': '2026-09'})
        self.assertContains(page, self.player.name)
        self.assertNotContains(page, 'حفظ الحضور والغياب')
        payload = {'group': group.pk, 'month': '2026-09', f'present_{self.player.pk}_2026-09-02': 'on'}
        self.assertEqual(self.client.post(url, payload).status_code, 403)
        self.assertFalse(AcademyTrainingAttendance.objects.exists())
        self.grant('attendance_record')
        self.assertContains(self.client.get(url), 'حفظ الحضور والغياب')
        self.assertEqual(self.client.post(url, dict(payload, group=other_group.pk)).status_code, 404)
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.assertTrue(AcademyTrainingAttendance.objects.get(group=group, player=self.player, attendance_date=date(2026, 9, 2)).is_present)
        self.assertFalse(AcademyTrainingAttendance.objects.filter(group=other_group).exists())

    def test_subscription_view_does_not_grant_writes_or_other_sections(self):
        self.grant('subscriptions')
        AcademyPlayerMonthlySubscription.objects.create(player=self.player, month=date(2026, 9, 1), expected_amount=1500, paid_amount=500)
        AcademyPlayerMonthlySubscription.objects.create(player=self.other.members.get(role='player'), month=date(2026, 9, 1), expected_amount=9000)
        url = reverse('restricted_academy_portal') + '?section=subscriptions'
        page = self.client.get(url, {'month': '2026-09'})
        self.assertContains(page, self.player.name)
        self.assertNotContains(page, 'لاعب محجوب')
        self.assertContains(page, '1000')
        self.assertEqual(self.client.post(url, {'paid_amount': 1500}).status_code, 403)
        self.assertEqual(self.client.get(reverse('restricted_academy_portal'), {'section': 'attendance'}).status_code, 403)

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
