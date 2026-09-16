from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from .models import AcademyMember, AcademyPlayerMonthlySubscription


SECTION_LABELS = {
    'players': 'اللاعبين', 'coaches': 'المدربين', 'administrators': 'الإداريين',
    'groups': 'المجموعات', 'subscriptions': 'الاشتراكات الشهرية',
}


@login_required
def restricted_academy_portal(request):
    profile = getattr(request, 'restricted_academy_profile', None)
    if not profile or not profile.restricted_academy_id:
        return HttpResponseForbidden('لا توجد أكاديمية متاحة لهذا الحساب. راجع مسؤول البرنامج.')
    if request.method not in ('GET', 'HEAD'):
        return HttpResponseForbidden('هذا الحساب للعرض فقط.')
    allowed = [key for key in SECTION_LABELS if key in (profile.academy_sections or [])]
    if not allowed:
        return HttpResponseForbidden('لا توجد أقسام مسموح بها لهذا الحساب.')
    section = request.GET.get('section', allowed[0])
    if section not in allowed:
        return HttpResponseForbidden('ليس لديك صلاحية عرض هذا القسم.')
    academy = profile.restricted_academy
    context = {
        'academy': academy, 'section': section, 'section_label': SECTION_LABELS[section],
        'sections': [{'key': key, 'label': SECTION_LABELS[key]} for key in allowed],
    }
    roles = {'players': AcademyMember.ROLE_PLAYER, 'coaches': AcademyMember.ROLE_COACH, 'administrators': AcademyMember.ROLE_ADMIN}
    if section in roles:
        context['members'] = academy.members.filter(role=roles[section]).order_by('name', 'pk')
    elif section == 'groups':
        context['groups'] = academy.training_groups.order_by('name', 'pk')
    elif section == 'subscriptions':
        from .views import _month_bounds
        _year, _month, start, _end, month_value = _month_bounds(request.GET.get('month'))
        context['month_value'] = month_value
        context['subscriptions'] = AcademyPlayerMonthlySubscription.objects.filter(
            player__academy=academy, player__role=AcademyMember.ROLE_PLAYER, month=start,
        ).select_related('player').order_by('player__name')
    return render(request, 'academies/restricted_academy_portal.html', context)
