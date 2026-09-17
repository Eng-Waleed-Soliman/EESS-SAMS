from datetime import date, timedelta
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import (Academy, AcademyMember, AcademyPlayerMonthlySubscription, AcademyTrainingGroup,
                     AcademyTrainingGroupPlayer, AcademyPlayerReceiver, Branch, Employee, SecurityMovement,
                     SecurityMovementCorrection, UserPermission)
from .security_views import open_entries
from .constants import OPERATION_PLACE_CHOICES
from django.apps import apps
from django.db import connection
from importlib import import_module
from types import SimpleNamespace


@override_settings(SECURE_SSL_REDIRECT=False)
class SecurityDeskTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name='فرع الأمن')
        self.other = Branch.objects.create(name='فرع آخر')
        self.user = User.objects.create_user('guard', password='Guard-pass-3928')
        self.profile = UserPermission.objects.create(user=self.user, security_only=True, security_branch=self.branch, can_accounts=True, can_settings=True)
        self.academy = Academy.objects.create(branch=self.branch, name='أكاديمية الأمن', sport_activity='Football', company_name='Company', manager_name='Manager', manager_phone='01000000000', operation_place=OPERATION_PLACE_CHOICES[0][0], contract_start_date=date(2026,7,1), contract_end_date=date(2027,6,30))
        self.player = AcademyMember.objects.create(academy=self.academy, role='player', name='لاعب الأمن')
        self.employee = Employee.objects.create(branch=self.branch, name='موظف الأمن', job_title='حارس', salary=98765)
        self.client.force_login(self.user)

    def movement(self, kind='entry', **payload):
        return self.client.post(reverse('security_movement', args=[kind]), payload)

    def training_group(self, name='مجموعة الساعة', start='17:30', end='19:00'):
        today = timezone.localdate()
        self.academy.contract_start_date = today - timedelta(days=30)
        self.academy.contract_end_date = today + timedelta(days=30)
        self.academy.save()
        group = AcademyTrainingGroup.objects.create(
            academy=self.academy, name=name, training_days=[today.weekday()],
            training_times={str(today.weekday()): {'start': start, 'end': end}},
        )
        AcademyTrainingGroupPlayer.objects.create(group=group, player=self.player)
        return group

    def test_expected_hour_deduplicates_players_and_is_scoped(self):
        self.training_group()
        self.training_group('مجموعة ثانية', '18:00', '20:00')
        other_academy = Academy.objects.create(
            branch=self.other, name='Hidden academy', sport_activity='Football', company_name='Company',
            manager_name='Manager', manager_phone='01000000000', operation_place=OPERATION_PLACE_CHOICES[0][0],
            contract_start_date=timezone.localdate(), contract_end_date=timezone.localdate()+timedelta(days=30),
        )
        outsider = AcademyMember.objects.create(academy=other_academy, role='player', name='لاعب فرع آخر')
        group = AcademyTrainingGroup.objects.create(academy=other_academy, name='Hidden group', training_days=[timezone.localdate().weekday()], training_times={str(timezone.localdate().weekday()): {'start':'17:00','end':'19:00'}})
        AcademyTrainingGroupPlayer.objects.create(group=group, player=outsider)
        page = self.client.get(reverse('security_home'), {'hour':17, 'branch_id':self.other.pk})
        self.assertEqual(len(page.context['expected']), 1)
        self.assertEqual(len(page.context['expected'][0]['sessions']), 2)
        self.assertEqual(page.context['totals']['expected'], 1)
        self.assertContains(page, '17:30')
        self.assertNotContains(page, outsider.name)
        self.assertFalse(SecurityMovement.objects.exists())

    def test_arrival_lead_setting_and_exact_hour_boundaries(self):
        self.training_group(start='17:00', end='19:00')
        self.assertEqual(len(self.client.get(reverse('security_home'), {'hour':16}).context['expected']),1)
        self.branch.security_arrival_lead_minutes = 0
        self.branch.save()
        self.assertEqual(len(self.client.get(reverse('security_home'), {'hour':16}).context['expected']),0)
        self.assertEqual(len(self.client.get(reverse('security_home'), {'hour':19}).context['expected']),0)
        self.assertEqual(len(self.client.get(reverse('security_home'), {'hour':17}).context['expected']),1)

    def test_lookup_automatically_selects_exit_but_scan_does_not_record(self):
        self.training_group()
        self.movement(action='record_member', member_id=self.player.pk)
        page = self.movement(action='lookup_qr', qr_value=str(self.player.qr_token))
        self.assertEqual(page.context['movement_type'], 'exit')
        self.assertContains(page, 'action="/security/exit/"')
        self.assertEqual(SecurityMovement.objects.count(),1)
        self.movement('exit', action='record_member', member_id=self.player.pk)
        page = self.client.get(reverse('security_home'), {'hour':17})
        self.assertTrue(page.context['expected'][0]['exited'])
        self.assertContains(page, 'إعادة دخول استثنائية')

    def test_visitor_dialog_works_from_exit_page_and_invalid_data_stays_visible(self):
        page = self.movement('exit', action='record_visitor', visitor_name='زائر جديد', contact_phone='01011111111', visit_reason='مقابلة', host_name='المدير')
        self.assertEqual(page.status_code,302)
        self.assertEqual(SecurityMovement.objects.get().movement_type,'entry')
        page = self.client.post(reverse('security_home'), {'action':'record_visitor','visitor_name':'ناقص'})
        self.assertContains(page, 'id="visitorDialog" open')
        self.assertEqual(SecurityMovement.objects.count(),1)

    def test_duplicate_entry_and_exit_without_entry_are_rejected(self):
        self.movement('exit', action='record_member', member_id=self.player.pk)
        self.assertFalse(SecurityMovement.objects.exists())
        self.assertEqual(self.movement(action='record_member', member_id=self.player.pk).status_code,302)
        self.movement(action='record_member', member_id=self.player.pk)
        self.assertEqual(SecurityMovement.objects.count(),1)
        self.assertEqual(len(open_entries(self.branch)),1)
        entry = SecurityMovement.objects.get()
        self.client.post(reverse('security_home'), {'action':'exit_visit','visit_id':entry.pk})
        self.assertEqual(len(open_entries(self.branch)),0)
        self.assertEqual(SecurityMovement.objects.get(movement_type='exit').visit_token,entry.visit_token)
        self.client.post(reverse('security_home'), {'action':'exit_visit','visit_id':entry.pk})
        self.assertEqual(SecurityMovement.objects.count(),2)
        self.movement(action='record_member',member_id=self.player.pk)
        self.assertEqual(len(open_entries(self.branch)),1)

    def test_employee_and_visitor_are_independent_and_do_not_expose_salary(self):
        self.movement(action='record_employee', employee_id=self.employee.pk)
        self.assertEqual(SecurityMovement.objects.get(employee=self.employee).person_type,'employee')
        self.assertNotContains(self.client.get(reverse('security_home')),'98765')
        payload = {'action':'record_visitor','visitor_name':'زائر الأمن','contact_phone':'01011222333','visit_reason':'مقابلة','host_name':'مسؤول الفرع'}
        self.assertEqual(self.client.post(reverse('security_home'),payload).status_code,302)
        self.client.post(reverse('security_home'),payload)
        self.assertEqual(SecurityMovement.objects.filter(source='visitor').count(),1)
        self.assertEqual(len(open_entries(self.branch)),2)
        self.movement('exit',action='record_employee',employee_id=self.employee.pk)
        self.assertEqual(len(open_entries(self.branch)),1)

    def test_guard_is_locked_to_branch_and_security_even_with_other_flags(self):
        page = self.client.get(reverse('security_home'),{'branch_id':self.other.pk})
        self.assertEqual(page.context['branch'],self.branch)
        for hidden in ['لوحة التحكم','الحسابات','لوحة الإدارة']:
            self.assertNotContains(page,hidden)
        self.assertEqual(self.client.get('/accounts/').url,reverse('security_home'))
        self.assertEqual(self.client.post('/accounts/',{}).status_code,403)
        outsider = Employee.objects.create(branch=self.other,name='موظف آخر',job_title='عامل',salary=1)
        self.assertEqual(self.movement(action='record_employee',employee_id=outsider.pk).status_code,404)
        self.profile.security_branch = None
        self.profile.save(update_fields=['security_branch'])
        self.assertEqual(self.client.get(reverse('security_home')).status_code,403)

    def test_qr_card_shows_group_time_and_subscription_without_training_attendance_write(self):
        today = timezone.localdate()
        group = AcademyTrainingGroup.objects.create(academy=self.academy,name='مجموعة التدريب',training_days=[today.weekday()],training_times={str(today.weekday()):{'start':'17:00','end':'19:00'}})
        AcademyTrainingGroupPlayer.objects.create(group=group,player=self.player)
        AcademyPlayerMonthlySubscription.objects.create(player=self.player,month=today.replace(day=1),expected_amount=1500,paid_amount=1500)
        page = self.movement(action='lookup_qr',qr_value=str(self.player.qr_token))
        self.assertContains(page,'17:00')
        self.assertContains(page,'19:00')
        self.assertContains(page,'مسدد ✓')
        self.assertNotContains(page,'>1500<')
        self.assertFalse(SecurityMovement.objects.exists())

    def test_registered_receiver_is_required_and_guard_cannot_authorize_one(self):
        AcademyPlayerReceiver.objects.create(player=self.player,name='والد اللاعب',relation='والد')
        self.movement(action='record_member',member_id=self.player.pk)
        self.movement('exit',action='record_member',member_id=self.player.pk)
        self.assertFalse(SecurityMovement.objects.filter(movement_type='exit').exists())
        self.movement('exit',action='record_member',member_id=self.player.pk,receiver_name='شخص آخر',receiver_relation='والد')
        self.assertEqual(len(open_entries(self.branch)),1)
        self.movement('exit',action='record_member',member_id=self.player.pk,receiver_name='والد اللاعب',receiver_relation='والد')
        self.assertEqual(len(open_entries(self.branch)),0)
        self.assertEqual(self.client.post(reverse('security_home'),{'action':'add_receiver','member_id':self.player.pk,'name':'آخر','relation':'والد'}).status_code,403)

    def test_correction_requires_admin_and_keeps_audit(self):
        self.movement(action='record_member',member_id=self.player.pk)
        item = SecurityMovement.objects.get()
        url = reverse('security_correction',args=[item.pk]) + f'?branch_id={self.branch.pk}'
        self.assertEqual(self.client.get(url).status_code,403)
        admin = User.objects.create_superuser('security-admin','admin@example.com','Strong-pass-2938')
        self.client.force_login(admin)
        when = timezone.localtime(item.recorded_at).strftime('%Y-%m-%dT%H:%M')
        response = self.client.post(url,{'recorded_at':when,'notes':'تم التصحيح','reason':'تصحيح ملاحظة'})
        self.assertEqual(response.status_code,302)
        audit = SecurityMovementCorrection.objects.get(movement=item)
        self.assertEqual(audit.corrected_by,admin)
        self.assertEqual(audit.before['notes'],'')
        self.assertEqual(audit.after['notes'],'تم التصحيح')
        self.assertEqual(len(open_entries(self.branch)),1)

    def test_previous_day_presence_and_person_report_filters(self):
        self.movement(action='record_member',member_id=self.player.pk)
        old = timezone.now()-timedelta(days=1)
        SecurityMovement.objects.update(recorded_at=old)
        page = self.client.get(reverse('security_home'),{'q':self.player.name,'date_from':str(timezone.localdate(old)),'date_to':str(timezone.localdate())})
        self.assertContains(page,'لم يسجل خروجه منذ يوم سابق')
        self.assertEqual(len(page.context['log']),1)

    def test_legacy_migration_preserves_history_and_pairs_open_visits(self):
        old = SecurityMovement.objects.create(branch=self.branch, member=self.player, person_name=self.player.name, person_type='player', movement_type='entry')
        duplicate = SecurityMovement.objects.create(branch=self.branch, member=self.player, person_name=self.player.name, person_type='player', movement_type='entry')
        exited = SecurityMovement.objects.create(branch=self.branch, member=self.player, person_name=self.player.name, person_type='player', movement_type='exit')
        current = SecurityMovement.objects.create(branch=self.branch, member=self.player, person_name=self.player.name, person_type='player', movement_type='entry')
        import_module('academies.migrations.0066_security_desk').pair_legacy_movements(apps,SimpleNamespace(connection=connection))
        old.refresh_from_db(); duplicate.refresh_from_db(); exited.refresh_from_db(); current.refresh_from_db()
        self.assertEqual(old.visit_token,duplicate.visit_token)
        self.assertEqual(old.visit_token,exited.visit_token)
        self.assertNotEqual(old.visit_token,current.visit_token)
        self.assertEqual(SecurityMovement.objects.count(),4)
        self.assertEqual([item.pk for item in open_entries(self.branch)],[current.pk])

    def test_after_closing_visitor_alert_and_all_branch_write_is_denied(self):
        from datetime import time
        self.branch.security_closing_time = time(0,0)
        self.branch.save(update_fields=['security_closing_time'])
        self.client.post(reverse('security_home'),{'action':'record_visitor','visitor_name':'زائر متأخر','contact_phone':'01012345678','visit_reason':'مقابلة','host_name':'المسؤول'})
        page = self.client.get(reverse('security_home'))
        self.assertTrue(page.context['current'][0].after_closing)
        admin = User.objects.create_superuser('all-branches-admin','a@example.com','Strong-pass-2938')
        self.client.force_login(admin)
        self.client.get(reverse('security_home'),{'branch_id':'all'})
        self.movement(action='record_member',member_id=self.player.pk)
        self.assertFalse(SecurityMovement.objects.filter(member=self.player).exists())
