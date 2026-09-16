from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.db import transaction
from calendar import monthrange
from datetime import date

from .models import AcademyMember, AcademyPlayerMonthlySubscription, AcademyTrainingAttendance, AcademyTrainingGroupPlayer
from .constants import WEEKDAY_AR


SECTION_LABELS = {
    'players': 'اللاعبين', 'coaches': 'المدربين', 'administrators': 'الإداريين',
    'groups': 'المجموعات', 'subscriptions': 'الاشتراكات الشهرية',
    'players_add': 'إضافة لاعب', 'placement': 'تسكين المجموعات', 'attendance': 'الحضور والغياب',
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


@login_required
def restricted_academy_portal(request):
    profile = getattr(request, 'restricted_academy_profile', None)
    if not profile or not profile.restricted_academy_id:
        return HttpResponseForbidden('لا توجد أكاديمية متاحة لهذا الحساب. راجع مسؤول البرنامج.')
    permissions = set(profile.academy_sections or [])
    allowed = [key for key in SECTION_LABELS if key in permissions]
    if 'attendance_record' in permissions and 'attendance' not in allowed:
        allowed.append('attendance')
    if not allowed:
        return HttpResponseForbidden('لا توجد أقسام مسموح بها لهذا الحساب.')
    section = request.GET.get('section', allowed[0])
    if section not in allowed:
        return HttpResponseForbidden('ليس لديك صلاحية عرض هذا القسم.')
    if request.method not in ('GET', 'HEAD', 'POST'):
        return HttpResponseForbidden('ليس لديك صلاحية تنفيذ هذا الإجراء.')
    writable = section in ('players_add', 'placement') or (section == 'attendance' and 'attendance_record' in permissions)
    if request.method == 'POST' and not writable:
        return HttpResponseForbidden('ليس لديك صلاحية تعديل هذا القسم.')
    academy = profile.restricted_academy
    context = {
        'academy': academy, 'section': section, 'section_label': SECTION_LABELS[section],
        'sections': [{'key': key, 'label': SECTION_LABELS[key]} for key in allowed],
    }
    roles = {'players': AcademyMember.ROLE_PLAYER, 'coaches': AcademyMember.ROLE_COACH, 'administrators': AcademyMember.ROLE_ADMIN}
    if section in roles:
        context['members'] = academy.members.filter(role=roles[section]).order_by('name', 'pk')
    elif section == 'groups' or (section == 'attendance' and request.method in ('GET', 'HEAD') and request.GET.get('list') == '1'):
        year, month, _start, _end, month_value = portal_month(request.GET.get('month'))
        context.update({
            'month_value': month_value,
            'can_place_players': 'placement' in permissions,
            'can_view_attendance': 'attendance' in allowed,
            'rows': [{'group': group, 'sessions_count': group.sessions_count_in_month(year, month), 'players_count': group.player_assignments.filter(player__academy=academy, player__role=AcademyMember.ROLE_PLAYER).count()} for group in academy.training_groups.order_by('name', 'pk')],
        })
        return render(request, 'academies/academy_training_group_list.html', context)
    elif section == 'subscriptions':
        _year, _month, start, _end, month_value = portal_month(request.GET.get('month'))
        context['month_value'] = month_value
        context['subscriptions'] = AcademyPlayerMonthlySubscription.objects.filter(
            player__academy=academy, player__role=AcademyMember.ROLE_PLAYER, month=start,
        ).select_related('player').order_by('player__name')
    elif section == 'players_add':
        from .forms import AcademyMemberForm
        form = AcademyMemberForm(request.POST if request.method == 'POST' else None, request.FILES or None, fixed_role=AcademyMember.ROLE_PLAYER)
        # Limited accounts cannot change public website publishing settings.
        for field in ('website_bio', 'website_bio_en', 'is_published_on_website', 'delete_photo'):
            form.fields.pop(field, None)
        if request.method == 'POST' and form.is_valid():
            player = form.save(commit=False)
            player.academy = academy
            player.is_published_on_website = False
            player.save()
            return redirect(f"{reverse('restricted_academy_portal')}?section=players_add&saved=1")
        context['player_form'] = form
    elif section in ('placement', 'attendance'):
        groups = academy.training_groups.order_by('name', 'pk')
        source = request.POST if request.method == 'POST' else request.GET
        group_id = source.get('group')
        if group_id:
            try:
                group_id = int(group_id)
            except (TypeError, ValueError):
                raise Http404('المجموعة غير متاحة.')
        group = get_object_or_404(groups, pk=group_id) if group_id else groups.first()
        context.update({'available_groups': groups, 'selected_group': group})
        if request.method == 'POST' and not group:
            return HttpResponseForbidden('لا توجد مجموعة متاحة.')
        if group and section == 'placement':
            from .group_forms import AcademyTrainingGroupPlayerForm
            action = request.POST.get('action', 'assign')
            if request.method == 'POST' and action == 'remove':
                assignment = get_object_or_404(AcademyTrainingGroupPlayer, pk=request.POST.get('assignment'), group=group, player__academy=academy)
                assignment.delete()
                return redirect(f"{reverse('restricted_academy_portal')}?section=placement&group={group.pk}")
            if request.method == 'POST' and action != 'assign':
                return HttpResponseForbidden('إجراء غير مسموح.')
            form = AcademyTrainingGroupPlayerForm(request.POST if request.method == 'POST' else None, academy=academy, group=group)
            if request.method == 'POST' and form.is_valid():
                AcademyTrainingGroupPlayer.objects.get_or_create(group=group, player=form.cleaned_data['player'])
                return redirect(f"{reverse('restricted_academy_portal')}?section=placement&group={group.pk}")
            context.update({'placement_form': form, 'assignments': group.player_assignments.filter(player__academy=academy, player__role=AcademyMember.ROLE_PLAYER).select_related('player')})
        elif group and section == 'attendance':
            year, month, start, _end, month_value = portal_month(source.get('month'))
            dates = [date(year, month, day) for day in range(1, monthrange(year, month)[1] + 1) if date(year, month, day).weekday() in {int(value) for value in group.training_days}]
            players = list(academy.members.filter(role=AcademyMember.ROLE_PLAYER, group_assignments__group=group).distinct().order_by('name', 'pk'))
            if request.method == 'POST':
                with transaction.atomic():
                    for player in players:
                        for training_date in dates:
                            AcademyTrainingAttendance.objects.update_or_create(group=group, player=player, attendance_date=training_date, defaults={'is_present': f'present_{player.pk}_{training_date:%Y-%m-%d}' in request.POST})
                return redirect(f"{reverse('restricted_academy_portal')}?section=attendance&group={group.pk}&month={month_value}")
            records = {(item.player_id, item.attendance_date): item.is_present for item in AcademyTrainingAttendance.objects.filter(group=group, player__in=players, attendance_date__year=year, attendance_date__month=month)}
            subscriptions = {item.player_id: item for item in AcademyPlayerMonthlySubscription.objects.filter(player__in=players, month=start)}
            rows = []
            for player in players:
                subscription = subscriptions.get(player.pk)
                expected = subscription.expected_amount if subscription else player.monthly_subscription
                paid = subscription.paid_amount if subscription else 0
                rows.append({
                    'player': player, 'is_paid': bool(subscription and subscription.is_paid),
                    'remaining_amount': max(0, int(expected or 0) - int(paid or 0)),
                    'attendance': [{'date': day, 'is_present': records.get((player.pk, day), False), 'field_name': f'present_{player.pk}_{day:%Y-%m-%d}'} for day in dates],
                })
            from .views import ARABIC_MONTH_NAMES
            context.update({
                'group': group, 'month_value': month_value,
                'month_label': f'{ARABIC_MONTH_NAMES[month]} {year}',
                'can_record_attendance': 'attendance_record' in permissions,
                'restricted_groups_section': 'groups' if 'groups' in permissions else 'attendance',
                'training_date_headers': [{'date': day, 'weekday': WEEKDAY_AR[day.weekday()]} for day in dates],
                'rows': rows,
            })
            return render(request, 'academies/academy_training_group_attendance.html', context)
    return render(request, 'academies/restricted_academy_portal.html', context)
