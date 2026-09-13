from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .constants import OPERATION_PLACE_CHOICES
from .models import (
    Academy, AcademyMember, AcademyPlayerMonthlySubscription, AcademyTrainingAttendance,
    AcademyTrainingGroup, AcademyTrainingGroupPlayer,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class AcademyTrainingGroupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='group-tester', password='test-password')
        self.client.force_login(self.user)
        self.academy = Academy.objects.create(
            name='Grouped Academy', sport_activity='Football', company_name='Company',
            manager_name='Manager', manager_phone='01000000444',
            operation_place=OPERATION_PLACE_CHOICES[0][0],
            contract_start_date=date.today(), contract_end_date=date.today() + timedelta(days=365),
        )
        self.first_player = AcademyMember.objects.create(
            academy=self.academy, role=AcademyMember.ROLE_PLAYER, name='اللاعب الأول',
        )
        self.second_player = AcademyMember.objects.create(
            academy=self.academy, role=AcademyMember.ROLE_PLAYER, name='اللاعب الثاني',
        )

    def create_group(self, name='مجموعة السبت والثلاثاء', days=('5', '1')):
        return self.client.post(
            reverse('academy_training_group_create', args=[self.academy.pk]),
            {'name': name, 'training_days': list(days)},
        )

    def test_player_screen_button_create_edit_and_monthly_session_count(self):
        player_page = self.client.get(
            reverse('academy_member_list', args=[self.academy.pk]), {'role': 'player'},
        )
        groups_url = reverse('academy_training_group_list', args=[self.academy.pk])
        self.assertContains(player_page, groups_url)
        self.assertContains(player_page, 'المجموعات')

        response = self.create_group()
        self.assertRedirects(response, groups_url)
        group = AcademyTrainingGroup.objects.get(academy=self.academy)
        self.assertEqual(group.training_days, [5, 1])
        self.assertEqual(group.sessions_count_in_month(2026, 9), 9)

        list_page = self.client.get(groups_url, {'month': '2026-09'})
        self.assertEqual(list_page.status_code, 200)
        self.assertContains(list_page, 'type="month"')
        self.assertContains(list_page, 'value="2026-09"')
        self.assertContains(list_page, 'السبت، الثلاثاء')
        self.assertEqual(list_page.context['rows'][0]['sessions_count'], 9)
        self.assertContains(list_page, 'تسكين لاعب')
        self.assertContains(list_page, 'تعديل')
        self.assertContains(list_page, 'حذف')

        edit_response = self.client.post(
            reverse('academy_training_group_update', args=[self.academy.pk, group.pk]),
            {'name': 'مجموعة الإثنين والأربعاء', 'training_days': ['0', '2']},
        )
        self.assertRedirects(edit_response, groups_url)
        group.refresh_from_db()
        self.assertEqual(group.name, 'مجموعة الإثنين والأربعاء')
        self.assertEqual(group.training_days, [0, 2])
        self.assertEqual(group.sessions_count_in_month(2026, 9), 9)

    def test_assign_player_to_multiple_groups_remove_and_delete_group(self):
        groups_url = reverse('academy_training_group_list', args=[self.academy.pk])
        self.create_group(name='المجموعة الأولى')
        self.create_group(name='المجموعة الثانية', days=('6', '3'))
        first_group, second_group = list(self.academy.training_groups.order_by('id'))
        first_url = reverse('academy_training_group_players', args=[self.academy.pk, first_group.pk])
        second_url = reverse('academy_training_group_players', args=[self.academy.pk, second_group.pk])
        self.assertRedirects(self.client.post(first_url, {'player': self.first_player.pk}), first_url)
        self.assertRedirects(self.client.post(second_url, {'player': self.first_player.pk}), second_url)
        self.assertEqual(self.first_player.group_assignments.count(), 2)

        duplicate = self.client.post(first_url, {'player': self.first_player.pk})
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(AcademyTrainingGroupPlayer.objects.filter(group=first_group).count(), 1)

        other_academy = Academy.objects.create(
            name='Other Academy', sport_activity='Basketball', company_name='Other',
            manager_name='Other Manager', manager_phone='01000000555',
            operation_place=OPERATION_PLACE_CHOICES[0][0],
            contract_start_date=date.today(), contract_end_date=date.today() + timedelta(days=365),
        )
        outsider = AcademyMember.objects.create(
            academy=other_academy, role=AcademyMember.ROLE_PLAYER, name='لاعب أكاديمية أخرى',
        )
        cross_academy = self.client.post(first_url, {'player': outsider.pk})
        self.assertEqual(cross_academy.status_code, 200)
        self.assertFalse(AcademyTrainingGroupPlayer.objects.filter(group=first_group, player=outsider).exists())

        assignment = AcademyTrainingGroupPlayer.objects.get(group=first_group, player=self.first_player)
        self.assertRedirects(
            self.client.post(first_url, {'action': 'remove', 'assignment_id': assignment.pk}), first_url,
        )
        self.assertFalse(AcademyTrainingGroupPlayer.objects.filter(pk=assignment.pk).exists())
        self.assertTrue(AcademyTrainingGroupPlayer.objects.filter(group=second_group, player=self.first_player).exists())

        delete_url = reverse('academy_training_group_delete', args=[self.academy.pk, second_group.pk])
        self.assertEqual(self.client.get(delete_url).status_code, 404)
        self.assertRedirects(self.client.post(delete_url), groups_url)
        self.assertFalse(AcademyTrainingGroup.objects.filter(pk=second_group.pk).exists())
        self.assertTrue(AcademyMember.objects.filter(pk=self.first_player.pk).exists())

    def test_group_requires_days_and_unique_name_within_academy(self):
        response = self.create_group(name='مجموعة بدون أيام', days=())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'اختر يوم تدريب واحدًا على الأقل')
        self.assertFalse(AcademyTrainingGroup.objects.exists())
        self.create_group(name='المجموعة أ')
        duplicate = self.create_group(name='المجموعة أ')
        self.assertContains(duplicate, 'يوجد مجموعة بنفس الاسم')
        self.assertEqual(AcademyTrainingGroup.objects.count(), 1)

    def test_attendance_screen_uses_month_dates_payment_status_and_saves(self):
        self.create_group(days=('5', '1'))
        group = self.academy.training_groups.get()
        AcademyTrainingGroupPlayer.objects.create(group=group, player=self.first_player)
        AcademyTrainingGroupPlayer.objects.create(group=group, player=self.second_player)
        AcademyPlayerMonthlySubscription.objects.create(
            player=self.first_player,
            month=date(2026, 9, 1),
            expected_amount=650,
            paid_amount=650,
        )
        AcademyPlayerMonthlySubscription.objects.create(
            player=self.second_player,
            month=date(2026, 9, 1),
            expected_amount=650,
            paid_amount=100,
        )
        url = reverse('academy_training_group_attendance', args=[self.academy.pk, group.pk])
        group_list = self.client.get(
            reverse('academy_training_group_list', args=[self.academy.pk]), {'month': '2026-09'},
        )
        self.assertContains(group_list, f'{url}?month=2026-09')
        self.assertContains(group_list, 'تسجيل الحضور')

        page = self.client.get(url, {'month': '2026-09'})
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'تسجيل الحضور والغياب')
        self.assertContains(page, 'سبتمبر 2026')
        self.assertEqual(len(page.context['training_date_headers']), 9)
        self.assertTrue(page.context['rows'][0]['is_paid'])
        self.assertEqual(page.context['rows'][0]['remaining_amount'], 0)
        self.assertFalse(page.context['rows'][1]['is_paid'])
        self.assertEqual(page.context['rows'][1]['remaining_amount'], 550)
        self.assertContains(page, group.name)
        self.assertContains(page, 'المبلغ المتبقي')
        self.assertContains(page, 'طباعة')
        self.assertContains(page, 'حفظ')

        present_date = date(2026, 9, 1)
        response = self.client.post(url, {
            'month': '2026-09',
            f'present_{self.first_player.pk}_{present_date:%Y-%m-%d}': 'on',
        })
        self.assertRedirects(response, f'{url}?month=2026-09')
        self.assertEqual(AcademyTrainingAttendance.objects.count(), 18)
        self.assertTrue(AcademyTrainingAttendance.objects.get(
            group=group, player=self.first_player, attendance_date=present_date,
        ).is_present)
        self.assertFalse(AcademyTrainingAttendance.objects.get(
            group=group, player=self.second_player, attendance_date=present_date,
        ).is_present)
