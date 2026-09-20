from calendar import monthrange
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .constants import WEEKDAY_AR
from .models import (
    AcademyMember,
    AcademyPlayerMonthlySubscription,
    AcademyTrainingAttendance,
    AcademyTrainingGroupPlayer,
)


SECTION_LABELS = {
    'players': 'اللاعبين', 'coaches': 'المدربين', 'administrators': 'الإداريين',
    'groups': 'المجموعات', 'subscriptions': 'الاشتراكات الشهرية',
    'players_add': 'إضافة لاعب', 'placement': 'تسكين المجموعات',
    'attendance': 'الحضور والغياب',
}


def portal_month(value):
    from .views import _month_bounds
    try:
        bounds = _month_bounds(value)
        if 2000 <= bounds[0] <= 2100:
            return bounds
    except (ValueError, OverflowError):
        pass
    return _month_bounds(None)


def _portal_url(section='home', **params):
    query = {'section': section, **{key: value for key, value in params.items() if value not in (None, '')}}
    return f"{reverse('restricted_academy_portal')}?" + '&'.join(f'{key}={value}' for key, value in query.items())


def _member_form(request, academy, *, role, member=None):
    from .forms import AcademyMemberForm
    form = AcademyMemberForm(
        request.POST if request.method == 'POST' else None,
        request.FILES or None,
        instance=member,
        fixed_role=role,
    )
    for field in ('website_bio', 'website_bio_en', 'is_published_on_website'):
        form.fields.pop(field, None)
    if request.method == 'POST' and form.is_valid():
        saved = form.save(commit=False)
        saved.academy = academy
        saved.is_published_on_website = False
        saved.save()
        return form, saved
    return form, None


@login_required
def restricted_academy_portal(request):
    profile = getattr(request, 'restricted_academy_profile', None)
    if not profile or not profile.restricted_academy_id:
        return HttpResponseForbidden('لا توجد أكاديمية متاحة لهذا الحساب. راجع مسؤول البرنامج.')
    permissions = set(profile.academy_sections or [])
    if not permissions:
        return HttpResponseForbidden('لا توجد أقسام مسموح بها لهذا الحساب.')
    if request.method not in ('GET', 'HEAD', 'POST'):
        return HttpResponseForbidden('ليس لديك صلاحية تنفيذ هذا الإجراء.')

    academy = profile.restricted_academy
    can_players = bool({'players', 'players_add'} & permissions)
    can_add_players = 'players_add' in permissions
    can_staff = bool({'coaches', 'administrators'} & permissions)
    can_groups = bool({'groups', 'placement', 'attendance', 'attendance_record'} & permissions)
    can_manage_groups = 'groups' in permissions
    can_place_players = 'placement' in permissions
    can_view_attendance = bool({'attendance', 'attendance_record'} & permissions)
    can_record_attendance = 'attendance_record' in permissions
    can_subscriptions = 'subscriptions' in permissions

    requested_section = request.GET.get('section', 'home').strip() or 'home'
    section = {'players_add': 'player_form', 'coaches': 'staff', 'administrators': 'staff'}.get(
        requested_section, requested_section,
    )
    if section == 'attendance' and request.GET.get('list') == '1':
        section = 'groups'
    context = {
        'academy': academy, 'section': section,
        'can_players': can_players, 'can_add_players': can_add_players,
        'can_staff': can_staff, 'can_groups': can_groups,
        'can_manage_groups': can_manage_groups, 'can_place_players': can_place_players,
        'can_view_attendance': can_view_attendance,
        'can_record_attendance': can_record_attendance,
        'can_subscriptions': can_subscriptions,
        'restricted_academy_profile': profile,
    }

    if section == 'home':
        if request.method == 'POST':
            return HttpResponseForbidden('ليس لديك صلاحية تنفيذ هذا الإجراء.')
        return render(request, 'academies/restricted_academy_portal.html', context)

    if section == 'players':
        if not can_players:
            return HttpResponseForbidden('ليس لديك صلاحية عرض اللاعبين.')
        if request.method == 'POST':
            return HttpResponseForbidden('ليس لديك صلاحية تنفيذ هذا الإجراء.')
        context['members'] = academy.members.filter(role=AcademyMember.ROLE_PLAYER).order_by('-is_active', 'name', 'pk')

    elif section == 'player_form':
        if not can_add_players:
            return HttpResponseForbidden('ليس لديك صلاحية إضافة أو تعديل اللاعبين.')
        member_id = request.GET.get('member')
        member = get_object_or_404(academy.members, pk=member_id, role=AcademyMember.ROLE_PLAYER) if member_id else None
        form, saved = _member_form(request, academy, role=AcademyMember.ROLE_PLAYER, member=member)
        if saved:
            messages.success(request, 'تم حفظ بيانات اللاعب بنجاح.')
            return redirect(_portal_url('players'))
        context.update({'member_form': form, 'member': member, 'member_kind': 'player'})

    elif section == 'player_delete':
        if not can_add_players or request.method != 'POST':
            return HttpResponseForbidden('ليس لديك صلاحية حذف اللاعبين.')
        player = get_object_or_404(academy.members, pk=request.POST.get('member'), role=AcademyMember.ROLE_PLAYER)
        player.delete()
        messages.success(request, 'تم حذف اللاعب.')
        return redirect(_portal_url('players'))

    elif section == 'staff':
        if not can_staff:
            return HttpResponseForbidden('ليس لديك صلاحية عرض المدربين والإداريين.')
        if request.method == 'POST':
            return HttpResponseForbidden('ليس لديك صلاحية تنفيذ هذا الإجراء.')
        context['members'] = academy.members.filter(
            role__in=[AcademyMember.ROLE_COACH, AcademyMember.ROLE_ADMIN],
        ).order_by('role', '-is_active', 'name', 'pk')

    elif section == 'staff_form':
        if not can_staff:
            return HttpResponseForbidden('ليس لديك صلاحية إضافة أو تعديل المدربين والإداريين.')
        member_id = request.GET.get('member')
        member = get_object_or_404(
            academy.members, pk=member_id,
            role__in=[AcademyMember.ROLE_COACH, AcademyMember.ROLE_ADMIN],
        ) if member_id else None
        form, saved = _member_form(request, academy, role='staff', member=member)
        if saved:
            messages.success(request, 'تم حفظ بيانات المدرب أو الإداري بنجاح.')
            return redirect(_portal_url('staff'))
        context.update({'member_form': form, 'member': member, 'member_kind': 'staff'})

    elif section == 'staff_delete':
        if not can_staff or request.method != 'POST':
            return HttpResponseForbidden('ليس لديك صلاحية حذف المدربين والإداريين.')
        member = get_object_or_404(
            academy.members, pk=request.POST.get('member'),
            role__in=[AcademyMember.ROLE_COACH, AcademyMember.ROLE_ADMIN],
        )
        member.delete()
        messages.success(request, 'تم حذف المدرب أو الإداري.')
        return redirect(_portal_url('staff'))

    elif section == 'groups':
        if not can_groups:
            return HttpResponseForbidden('ليس لديك صلاحية عرض المجموعات.')
        if request.method == 'POST':
            return HttpResponseForbidden('ليس لديك صلاحية تنفيذ هذا الإجراء.')
        year, month, _start, _end, month_value = portal_month(request.GET.get('month'))
        context.update({
            'month_value': month_value,
            'rows': [{
                'group': group,
                'sessions_count': group.sessions_count_in_month(year, month),
                'players_count': group.player_assignments.filter(
                    player__academy=academy, player__role=AcademyMember.ROLE_PLAYER,
                ).count(),
            } for group in academy.training_groups.order_by('name', 'pk')],
        })

    elif section == 'group_form':
        if not can_manage_groups:
            return HttpResponseForbidden('ليس لديك صلاحية إضافة أو تعديل المجموعات.')
        from .group_forms import AcademyTrainingGroupForm
        group_id = request.GET.get('group')
        group = get_object_or_404(academy.training_groups, pk=group_id) if group_id else None
        form = AcademyTrainingGroupForm(request.POST or None, instance=group, academy=academy)
        if request.method == 'POST' and form.is_valid():
            saved_group = form.save()
            messages.success(request, 'تم حفظ المجموعة ومواعيد التدريب بنجاح.')
            return redirect(_portal_url('group_detail', group=saved_group.pk))
        context.update({'group_form': form, 'group': group})

    elif section == 'group_delete':
        if not can_manage_groups or request.method != 'POST':
            return HttpResponseForbidden('ليس لديك صلاحية حذف المجموعات.')
        group = get_object_or_404(academy.training_groups, pk=request.POST.get('group'))
        group.delete()
        messages.success(request, 'تم حذف المجموعة دون حذف اللاعبين من الأكاديمية.')
        return redirect(_portal_url('groups'))

    elif section == 'group_detail':
        if not can_groups:
            return HttpResponseForbidden('ليس لديك صلاحية عرض المجموعة.')
        if request.method == 'POST':
            return HttpResponseForbidden('ليس لديك صلاحية تنفيذ هذا الإجراء.')
        group = get_object_or_404(academy.training_groups, pk=request.GET.get('group'))
        context.update({
            'group': group,
            'assignments': group.player_assignments.filter(
                player__academy=academy, player__role=AcademyMember.ROLE_PLAYER,
            ).select_related('player'),
        })

    elif section == 'placement':
        if not can_place_players:
            return HttpResponseForbidden('ليس لديك صلاحية تسكين اللاعبين.')
        from .group_forms import AcademyTrainingGroupPlayerForm
        source = request.POST if request.method == 'POST' else request.GET
        group_id = source.get('group')
        group = get_object_or_404(academy.training_groups, pk=group_id) if group_id else academy.training_groups.order_by('name', 'pk').first()
        if not group:
            raise Http404('لا توجد مجموعة متاحة.')
        action = request.POST.get('action', 'assign')
        if request.method == 'POST' and action == 'remove':
            assignment = get_object_or_404(
                AcademyTrainingGroupPlayer, pk=request.POST.get('assignment'),
                group=group, player__academy=academy,
            )
            assignment.delete()
            messages.success(request, 'تم رفع تسكين اللاعب من المجموعة.')
            return redirect(_portal_url('placement', group=group.pk))
        if request.method == 'POST' and action != 'assign':
            return HttpResponseForbidden('إجراء غير مسموح.')
        form = AcademyTrainingGroupPlayerForm(request.POST or None, academy=academy, group=group)
        if request.method == 'POST' and form.is_valid() and form.assign():
            messages.success(request, f"تم تسكين {len(form.cleaned_data['player'])} لاعب في المجموعة.")
            return redirect(_portal_url('group_detail', group=group.pk))
        context.update({
            'group': group, 'placement_form': form,
            'assignments': group.player_assignments.filter(player__academy=academy).select_related('player'),
        })

    elif section == 'attendance':
        if not can_view_attendance:
            return HttpResponseForbidden('ليس لديك صلاحية عرض الحضور والغياب.')
        source = request.POST if request.method == 'POST' else request.GET
        group_id = source.get('group')
        group = get_object_or_404(academy.training_groups, pk=group_id) if group_id else academy.training_groups.order_by('name', 'pk').first()
        if not group:
            raise Http404('لا توجد مجموعة متاحة.')
        year, month, start, _end, month_value = portal_month(source.get('month'))
        dates = [date(year, month, day) for day in range(1, monthrange(year, month)[1] + 1)
                 if date(year, month, day).weekday() in {int(value) for value in group.training_days}]
        players = list(academy.members.filter(
            role=AcademyMember.ROLE_PLAYER, group_assignments__group=group,
        ).distinct().order_by('name', 'pk'))
        if request.method == 'POST':
            if not can_record_attendance:
                return HttpResponseForbidden('ليس لديك صلاحية تسجيل الحضور والغياب.')
            with transaction.atomic():
                for player in players:
                    for training_date in dates:
                        AcademyTrainingAttendance.objects.update_or_create(
                            group=group, player=player, attendance_date=training_date,
                            defaults={'is_present': f'present_{player.pk}_{training_date:%Y-%m-%d}' in request.POST},
                        )
            messages.success(request, 'تم حفظ الحضور والغياب.')
            return redirect(_portal_url('attendance', group=group.pk, month=month_value))
        records = {(item.player_id, item.attendance_date): item.is_present for item in
                   AcademyTrainingAttendance.objects.filter(
                       group=group, player__in=players,
                       attendance_date__year=year, attendance_date__month=month,
                   )}
        subscriptions = {item.player_id: item for item in
                         AcademyPlayerMonthlySubscription.objects.filter(player__in=players, month=start)}
        rows = []
        for player in players:
            subscription = subscriptions.get(player.pk)
            expected = subscription.expected_amount if subscription else player.monthly_subscription
            paid = subscription.paid_amount if subscription else 0
            rows.append({
                'player': player, 'is_paid': bool(subscription and subscription.is_paid),
                'remaining_amount': max(0, int(expected or 0) - int(paid or 0)),
                'attendance': [{
                    'date': day, 'is_present': records.get((player.pk, day), False),
                    'field_name': f'present_{player.pk}_{day:%Y-%m-%d}',
                } for day in dates],
            })
        from .views import ARABIC_MONTH_NAMES
        context.update({
            'group': group, 'month_value': month_value,
            'month_label': f'{ARABIC_MONTH_NAMES[month]} {year}',
            'restricted_groups_section': 'groups',
            'training_date_headers': [{'date': day, 'weekday': WEEKDAY_AR[day.weekday()]} for day in dates],
            'rows': rows,
        })
        return render(request, 'academies/academy_training_group_attendance.html', context)

    elif section == 'subscriptions':
        if not can_subscriptions:
            return HttpResponseForbidden('الاشتراكات الشهرية غير متاحة لهذا الحساب.')
        if request.method == 'POST':
            return HttpResponseForbidden('ليس لديك صلاحية تعديل الاشتراكات.')
        _year, _month, start, _end, month_value = portal_month(request.GET.get('month'))
        context.update({
            'month_value': month_value,
            'subscriptions': AcademyPlayerMonthlySubscription.objects.filter(
                player__academy=academy, player__role=AcademyMember.ROLE_PLAYER, month=start,
            ).select_related('player').order_by('player__name'),
        })
    else:
        raise Http404('القسم غير متاح.')

    return render(request, 'academies/restricted_academy_portal.html', context)
