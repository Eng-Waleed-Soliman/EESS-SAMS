import uuid
from datetime import datetime, time, timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .branching import selected_branch
from .models import (Academy, AcademyMember, AcademyPlayerReceiver,
                     AcademyTrainingGroup, Branch, Employee, SecurityMovement, SecurityMovementCorrection, UserPermission)


class VisitorForm(forms.Form):
    REASONS = [('ولي أمر', 'ولي أمر'), ('مقابلة', 'مقابلة'), ('مورد', 'مورد'), ('صيانة', 'صيانة')]
    visitor_name = forms.CharField(label='اسم الزائر', max_length=200)
    contact_phone = forms.CharField(label='الهاتف', max_length=50)
    national_id = forms.CharField(label='الرقم القومي', max_length=14, required=False,
                                 widget=forms.TextInput(attrs={'inputmode': 'numeric', 'maxlength': '14'}))
    visit_reason = forms.ChoiceField(label='سبب الزيارة', choices=[('', 'اختر السبب'), *REASONS, ('other', 'أخرى')])
    other_reason = forms.CharField(label='سبب آخر', max_length=300, required=False)
    host_name = forms.CharField(label='المطلوب مقابلته / الأكاديمية', max_length=200,
                               widget=forms.TextInput(attrs={'list': 'visitorHosts', 'placeholder': 'اختر من القائمة أو اكتب الاسم'}))
    notes = forms.CharField(label='ملاحظات', required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def clean_national_id(self):
        value = self.cleaned_data['national_id'].translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789'))
        if value and (len(value) != 14 or not value.isascii() or not value.isdecimal()):
            raise forms.ValidationError('الرقم القومي يجب أن يتكون من 14 رقمًا.')
        return value

    def __init__(self, *args, **kwargs):
        # Preserve existing API submissions while presenting preset reasons in the UI.
        if args and args[0] is not None:
            data = args[0].copy()
            reason = data.get('visit_reason', '')
            if reason and reason not in dict(self.fields_reasons()):
                data['other_reason'], data['visit_reason'] = reason, 'other'
            args = (data, *args[1:])
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'

    @classmethod
    def fields_reasons(cls):
        return [*cls.REASONS, ('other', 'أخرى')]

    def clean(self):
        data = super().clean()
        other = data.pop('other_reason', '')
        if data.get('visit_reason') == 'other':
            if not other:
                self.add_error('other_reason', 'اكتب سبب الزيارة.')
            else:
                data['visit_reason'] = other
        return data


class CorrectionForm(forms.Form):
    recorded_at = forms.DateTimeField(label='وقت الحركة', widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'))
    notes = forms.CharField(label='ملاحظات', required=False, widget=forms.Textarea(attrs={'rows': 2}))
    receiver_name = forms.CharField(label='المستلم', required=False, max_length=200)
    receiver_relation = forms.CharField(label='صلته باللاعب', required=False, max_length=100)
    reason = forms.CharField(label='سبب التصحيح', max_length=500)


def can_correct(request):
    if getattr(request, 'security_guard_profile', None):
        return False
    return request.user.is_staff or request.user.is_superuser or UserPermission.objects.filter(user=request.user, can_users=True).exists()


def can_access(request):
    return bool(getattr(request, 'security_guard_profile', None) or request.user.is_staff or request.user.is_superuser or UserPermission.objects.filter(user=request.user, can_security=True).exists())


def open_entries(branch=None, all_branches=False):
    closed = SecurityMovement.objects.filter(movement_type='exit', visit_token__isnull=False).values_list('visit_token', flat=True)
    queryset = SecurityMovement.objects.filter(movement_type='entry').exclude(visit_token__in=closed).select_related('branch').defer('branch__logo_data', 'branch__image_data')
    if not all_branches:
        queryset = queryset.filter(branch=branch)
    result = {}
    for item in queryset.order_by('recorded_at', 'pk'):
        key = item.visit_token or ('legacy', item.branch_id, item.member_id, item.person_name)
        result[key] = item
    return list(result.values())


def category(item):
    if item.source == 'visitor':
        return 'visitor'
    return 'player' if item.person_type == 'player' else 'employee'


def record(request, branch, movement_type, fields):
    if not branch:
        raise ValueError('اختر فرعًا محددًا قبل التسجيل.')
    with transaction.atomic():
        # Serialize movements at the gate, including simultaneous scans.
        Branch.objects.select_for_update().get(pk=branch.pk)
        current = open_entries(branch)
        match = next((item for item in current if (
            item.member_id == fields.get('member_id') if fields.get('member_id') else
            item.employee_id == fields.get('employee_id') if fields.get('employee_id') else
            item.source == 'visitor' and item.person_name == fields['person_name'] and item.contact_phone == fields.get('contact_phone', '')
        )), None)
        if movement_type == 'entry' and match:
            raise ValueError(f'مسجل دخول بالفعل منذ {timezone.localtime(match.recorded_at):%d/%m %H:%M}. سجل خروجه أولًا.')
        if movement_type == 'exit' and not match:
            raise ValueError('لا يوجد دخول مفتوح لهذا الشخص في الفرع.')
        if match and not match.visit_token:
            match.visit_token = uuid.uuid4()
            SecurityMovement.objects.filter(pk=match.pk).update(visit_token=match.visit_token)
        receiver = request.POST.get('receiver_name', '').strip()
        relation = request.POST.get('receiver_relation', '').strip()
        if len(receiver) > 200 or len(relation) > 100 or bool(receiver) != bool(relation):
            raise ValueError('اكتب اسم المستلم وصلته باللاعب معًا.')
        if movement_type == 'exit' and fields.get('member_id'):
            allowed = AcademyPlayerReceiver.objects.filter(player_id=fields['member_id'], is_active=True)
            if allowed.exists() and not allowed.filter(name=receiver, relation=relation).exists():
                raise ValueError('اختر مستلمًا ضمن الأشخاص المصرح لهم بالاسم وصلة القرابة. راجع المسؤول.')
        return SecurityMovement.objects.create(
            branch=branch, movement_type=movement_type, visit_token=match.visit_token if match else uuid.uuid4(),
            recorded_by=request.user, receiver_name=receiver if movement_type == 'exit' else '',
            receiver_relation=relation if movement_type == 'exit' else '', **fields,
        )


def member_card(member):
    today = timezone.localdate()
    groups = list(member.training_groups.filter(academy=member.academy))
    schedule = []
    for group in groups:
        if today.weekday() in [int(day) for day in group.training_days]:
            timing = (group.training_times or {}).get(str(today.weekday()), {})
            schedule.append({'name': group.name, 'start': timing.get('start', 'غير محدد'), 'end': timing.get('end', 'غير محدد')})
    overrides = member.academy.operation_overrides.filter(booking_date=today)
    now = timezone.localtime().time()
    valid_times = []
    for timing in schedule:
        try:
            start = timezone.datetime.strptime(timing['start'], '%H:%M').time()
            end = timezone.datetime.strptime(timing['end'], '%H:%M').time()
            valid_times.append(start <= now <= end if start <= end else now >= start or now <= end)
        except ValueError:
            pass
    return {'person': member, 'schedule': schedule, 'is_player': member.role == 'player',
            'has_groups': bool(groups),
            'outside_training_time': bool(valid_times and not any(valid_times)),
            'has_override': overrides.exists(), 'receivers': member.authorized_receivers.filter(is_active=True)}


def expected_players(academies, branch, hour, current, q=''):
    """One identity row, exact sessions, no attendance or financial mutations."""
    today = timezone.localdate()
    tz = timezone.get_current_timezone()
    window_start = timezone.make_aware(datetime.combine(today, time(hour)), tz)
    window_end = window_start + timedelta(hours=1)
    groups = AcademyTrainingGroup.objects.filter(academy__in=academies).select_related('academy__branch').defer(
        'academy__website_image_data', 'academy__manager_photo_data',
        'academy__branch__logo_data', 'academy__branch__image_data',
    ).prefetch_related(Prefetch('players', queryset=AcademyMember.objects.filter(
        role='player', is_active=True, academy__in=academies,
    ).defer('photo_data').order_by('name')))
    rows = {}
    inside = {item.member_id: item for item in current if item.member_id}
    last = {}
    events = SecurityMovement.objects.filter(member__academy__in=academies, recorded_at__date=today).order_by('recorded_at', 'pk')
    for event in events:
        last[event.member_id] = event
    for group in groups:
        if group.academy.contract_start_date > today or group.academy.contract_end_date < today:
            continue
        for session_day in (today - timedelta(days=1), today):
            if str(session_day.weekday()) not in {str(day) for day in group.training_days}:
                continue
            timing = (group.training_times or {}).get(str(session_day.weekday()), {})
            try:
                start_time = datetime.strptime(timing.get('start', ''), '%H:%M').time()
                end_time = datetime.strptime(timing.get('end', ''), '%H:%M').time()
                start = timezone.make_aware(datetime.combine(session_day, start_time), tz)
                end = timezone.make_aware(datetime.combine(session_day, end_time), tz)
                if end <= start:
                    end += timedelta(days=1)
            except (ValueError, TypeError):
                start = end = None
            # Yesterday's session only remains relevant while it crosses midnight.
            if session_day != today and (not end or end <= window_start):
                continue
            lead = group.academy.branch.security_arrival_lead_minutes if group.academy.branch else 30
            in_hour = bool(start and start - timedelta(minutes=lead) < window_end and end > window_start)
            for player in group.players.all():
                if player.academy_id != group.academy_id:
                    continue
                row = rows.setdefault(player.pk, {'player': player, 'academy': group.academy, 'sessions': [], 'in_hour': False,
                                                  'inside': inside.get(player.pk), 'last': last.get(player.pk)})
                row['sessions'].append({'group': group.name, 'start': timing.get('start', 'غير محدد'),
                                        'end': timing.get('end', 'غير محدد'), 'previous_day': session_day != today})
                row['in_hour'] |= in_hour
    for pk, row in rows.items():
        row['exited'] = bool(not row['inside'] and row['last'] and row['last'].movement_type == 'exit')
    daily_total = len(rows)
    visible = [row for row in rows.values() if row['in_hour'] and (not q or q.casefold() in row['player'].name.casefold() or q in row['player'].phone)]
    visible.sort(key=lambda row: (min(session['start'] for session in row['sessions']), row['player'].name))
    return visible, daily_total


@login_required
def security_home(request):
    return desk(request, 'entry')


@login_required
def security_movement(request, movement_type):
    if movement_type not in ('entry', 'exit'):
        return redirect('security_home')
    return desk(request, movement_type)


def desk(request, movement_type):
    if not can_access(request):
        return HttpResponseForbidden('ليس لديك صلاحية الأمن.')
    branch, all_branches = selected_branch(request)
    academies = Academy.objects.select_related('branch').all()
    employees = Employee.objects.all()
    if not all_branches:
        academies = academies.filter(branch=branch)
        employees = employees.filter(branch=branch)
    members = AcademyMember.objects.filter(academy__in=academies, is_active=True).select_related('academy', 'academy__branch').defer('photo_data', 'academy__website_image_data', 'academy__manager_photo_data', 'academy__branch__logo_data', 'academy__branch__image_data')
    scanned_member = None
    selected_employee = None
    visitor_form = VisitorForm()
    visitor_lookup_open = False
    visitor_matches = []
    visitor_lookup_message = ''
    source = request.POST if request.method == 'POST' else request.GET
    if request.method == 'GET' and source.get('member_id'):
        scanned_member = get_object_or_404(members, pk=source['member_id'])
    if request.method == 'GET' and source.get('employee_id'):
        selected_employee = get_object_or_404(employees, pk=source['employee_id'])
    if request.method == 'POST':
        action = source.get('action')
        try:
            if action == 'lookup_visitor':
                if all_branches or not branch:
                    raise ValueError('اختر فرعًا محددًا للبحث عن الزائر.')
                visitor_lookup_open = True
                previous = SecurityMovement.objects.filter(branch=branch, source='visitor', movement_type='entry')
                if source.get('previous_visit_id'):
                    previous_visit = get_object_or_404(previous, pk=source['previous_visit_id'])
                    visitor_form = VisitorForm(initial={key: getattr(previous_visit, key) for key in ('contact_phone', 'national_id')}
                                               | {'visitor_name': previous_visit.person_name})
                    visitor_lookup_message = 'تم تعبئة بيانات الزائر. اختر سبب الزيارة والمطلوب مقابلته ثم أكد الدخول.'
                else:
                    query = source.get('visitor_query', '').strip().translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789'))
                    if len(query) < 7 or len(query) > 50:
                        visitor_lookup_message = 'اكتب رقم الهاتف أو الرقم القومي كاملًا.'
                    else:
                        seen = set()
                        for visit in previous.filter(Q(contact_phone=query) | Q(national_id=query)).order_by('-recorded_at', '-pk')[:100]:
                            identity = (visit.person_name, visit.contact_phone, visit.national_id)
                            if identity not in seen:
                                seen.add(identity)
                                visitor_matches.append(visit)
                        if len(visitor_matches) == 1:
                            visit = visitor_matches.pop()
                            visitor_form = VisitorForm(initial={'visitor_name': visit.person_name, 'contact_phone': visit.contact_phone, 'national_id': visit.national_id})
                            visitor_lookup_message = 'تم تعبئة بيانات الزائر. اختر سبب الزيارة والمطلوب مقابلته ثم أكد الدخول.'
                        elif not visitor_matches:
                            visitor_lookup_message = 'لا توجد زيارة سابقة بهذا الرقم في الفرع. أكمل بيانات الزائر الجديد.'
                            initial = {'national_id' if len(query) == 14 and query.isdecimal() else 'contact_phone': query}
                            visitor_form = VisitorForm(initial=initial)
            elif action == 'lookup_qr':
                from .views import _security_member_from_qr
                scanned_member = _security_member_from_qr(source.get('qr_value', ''), academies)
                if not scanned_member:
                    raise ValueError('لم يتم العثور على شخص فعال بهذا الكود داخل الفرع.')
            elif action == 'lookup_person':
                if source.get('member_id'):
                    scanned_member = get_object_or_404(members, pk=source['member_id'])
                elif source.get('employee_id'):
                    selected_employee = get_object_or_404(employees, pk=source['employee_id'])
            elif action in ('record_member', 'record_employee', 'record_visitor', 'exit_visit'):
                if all_branches:
                    raise ValueError('اختر فرعًا محددًا قبل تسجيل أي حركة.')
                if action == 'record_member':
                    person = get_object_or_404(members, pk=source.get('member_id'))
                    fields = {'member_id': person.pk, 'academy_id': person.academy_id, 'academy_name': person.academy.name,
                              'person_name': person.name, 'person_type': 'player' if person.role == 'player' else 'staff',
                              'contact_phone': person.phone, 'source': 'qr' if source.get('source') == 'qr' else 'manual'}
                    target_branch = person.academy.branch
                elif action == 'record_employee':
                    person = get_object_or_404(employees, pk=source.get('employee_id'))
                    fields = {'employee_id': person.pk, 'person_name': person.name, 'person_type': 'employee', 'source': 'manual'}
                    target_branch = person.branch
                elif action == 'exit_visit':
                    entry = get_object_or_404(SecurityMovement, pk=source.get('visit_id'), pk__in=[item.pk for item in open_entries(branch, all_branches)])
                    fields = {key: getattr(entry, key) for key in ('member_id', 'employee_id', 'academy_id', 'academy_name', 'person_name', 'person_type', 'contact_phone', 'national_id', 'visit_reason', 'host_name', 'source')}
                    target_branch = entry.branch
                    movement_type = 'exit'
                else:
                    movement_type = 'entry'
                    visitor_form = VisitorForm(source)
                    if not visitor_form.is_valid():
                        raise ValueError('أكمل بيانات الزائر المطلوبة.')
                    data = visitor_form.cleaned_data
                    fields = {'person_name': data.pop('visitor_name'), 'person_type': 'parent' if source.get('visitor_type') == 'parent' else 'visitor', 'source': 'visitor', **data}
                    target_branch = branch
                if not all_branches and target_branch != branch:
                    raise ValueError('الشخص ليس في الفرع المحدد.')
                record(request, target_branch, movement_type, fields)
                messages.success(request, 'تم تسجيل الحركة بنجاح.')
                return redirect('security_home')
            elif action == 'add_receiver':
                if not can_correct(request):
                    return HttpResponseForbidden('تحديد المستلمين بصلاحية مسؤول فقط.')
                player = get_object_or_404(members, pk=source.get('member_id'), role='player')
                name, relation = source.get('name', '').strip(), source.get('relation', '').strip()
                phone = source.get('phone', '').strip()
                if not name or not relation or len(name) > 200 or len(relation) > 100 or len(phone) > 50:
                    raise ValueError('اكتب اسم المستلم وصلته باللاعب بصورة صحيحة.')
                AcademyPlayerReceiver.objects.get_or_create(player=player, name=name, relation=relation, defaults={'phone': phone})
                messages.success(request, 'تم تسجيل المستلم المصرح له.')
                scanned_member = player
            else:
                return HttpResponseForbidden('إجراء غير مسموح.')
        except ValueError as error:
            messages.error(request, str(error))
    q = request.GET.get('q', '').strip()
    if q:
        members = members.filter(Q(name__icontains=q) | Q(phone__icontains=q))
        employees = employees.filter(name__icontains=q)
    category_filter = request.GET.get('category', 'all')
    today = timezone.localdate()
    try:
        day = timezone.datetime.strptime(request.GET.get('day', str(today)), '%Y-%m-%d').date()
    except ValueError:
        day = today
    try:
        date_from = timezone.datetime.strptime(request.GET.get('date_from') or str(day), '%Y-%m-%d').date()
        date_to = timezone.datetime.strptime(request.GET.get('date_to') or str(day), '%Y-%m-%d').date()
        if date_to < date_from:
            date_from, date_to = date_to, date_from
    except ValueError:
        date_from = date_to = day
    log = SecurityMovement.objects.select_related('recorded_by', 'employee').filter(recorded_at__date__range=(date_from, date_to))
    if not all_branches:
        log = log.filter(branch=branch)
    current = open_entries(branch, all_branches)
    totals = {'inside': len(current), 'entry': log.filter(movement_type='entry').count(), 'exit': log.filter(movement_type='exit').count(), 'visitors': log.filter(movement_type='entry', source='visitor').count()}
    try:
        selected_hour = max(0, min(23, int(request.GET.get('hour', timezone.localtime().hour))))
    except (ValueError, TypeError):
        selected_hour = timezone.localtime().hour
    expected, totals['expected'] = expected_players(academies, branch, selected_hour, current, q)
    totals['visitors_inside'] = sum(item.source == 'visitor' for item in current)
    tab = request.GET.get('tab', 'expected')
    if tab not in ('expected', 'inside', 'log'):
        tab = 'expected'
    if q:
        log = log.filter(Q(person_name__icontains=q) | Q(contact_phone__icontains=q))
        current = [item for item in current if q.casefold() in item.person_name.casefold() or q in item.contact_phone]
    if category_filter in ('player', 'employee', 'visitor'):
        current = [item for item in current if category(item) == category_filter]
        if category_filter == 'visitor':
            log = log.filter(source='visitor')
        elif category_filter == 'player':
            log = log.filter(person_type='player').exclude(source='visitor')
        else:
            log = log.exclude(person_type='player').exclude(source='visitor')
    for item in current:
        item.overdue = timezone.localdate(item.recorded_at) < today
        item.after_closing = bool(item.source == 'visitor' and item.branch and item.branch.security_closing_time and timezone.localtime().time() >= item.branch.security_closing_time)
    card = member_card(scanned_member) if scanned_member else None
    if card:
        card['inside'] = next((item for item in open_entries(scanned_member.academy.branch) if item.member_id == scanned_member.pk), None)
        if source.get('action') in ('lookup_qr', 'lookup_person') or request.path == '/security/':
            movement_type = 'exit' if card['inside'] else 'entry'
    employee_inside = None
    if selected_employee:
        employee_inside = next((item for item in open_entries(selected_employee.branch) if item.employee_id == selected_employee.pk), None)
        if source.get('action') == 'lookup_person' or request.path == '/security/':
            movement_type = 'exit' if employee_inside else 'entry'
    return render(request, 'academies/security_desk.html', {
        'branch': branch, 'all_branches': all_branches, 'branches': Branch.objects.all() if not getattr(request, 'security_guard_profile', None) else [],
        'movement_type': movement_type, 'members': members[:100], 'employees': employees[:100],
        'card': card, 'selected_employee': selected_employee, 'visitor_form': visitor_form,
        'visitor_lookup_open': visitor_lookup_open, 'visitor_matches': visitor_matches,
        'visitor_lookup_message': visitor_lookup_message,
        'visitor_hosts': list(employees.values_list('name', flat=True)) + list(academies.values_list('name', flat=True)),
        'current': current, 'log': log, 'totals': totals, 'q': q, 'day': day,
        'category_filter': category_filter, 'can_correct': can_correct(request),
        'date_from': date_from, 'date_to': date_to,
        'card_source': 'qr' if source.get('action') == 'lookup_qr' else 'manual',
        'expected': expected, 'tab': tab, 'selected_hour': selected_hour, 'hours': range(24),
        'employee_inside': employee_inside, 'today': today,
    })


@login_required
def security_correction(request, pk):
    if not can_access(request) or not can_correct(request):
        return HttpResponseForbidden('تصحيح الحركات متاح للمسؤول فقط.')
    branch, all_branches = selected_branch(request)
    queryset = SecurityMovement.objects.all()
    if not all_branches:
        queryset = queryset.filter(branch=branch)
    movement = get_object_or_404(queryset, pk=pk)
    initial = {key: getattr(movement, key) for key in ('recorded_at', 'notes', 'receiver_name', 'receiver_relation')}
    form = CorrectionForm(request.POST if request.method == 'POST' else None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            if movement.branch_id:
                Branch.objects.select_for_update().get(pk=movement.branch_id)
            movement.refresh_from_db()
            value = form.cleaned_data['recorded_at']
            paired = SecurityMovement.objects.filter(visit_token=movement.visit_token).exclude(pk=movement.pk) if movement.visit_token else SecurityMovement.objects.none()
            invalid = value > timezone.now() + timedelta(minutes=5)
            invalid = invalid or (movement.movement_type == 'entry' and paired.filter(movement_type='exit', recorded_at__lt=value).exists())
            invalid = invalid or (movement.movement_type == 'exit' and paired.filter(movement_type='entry', recorded_at__gt=value).exists())
            if invalid:
                form.add_error('recorded_at', 'وقت الحركة غير متوافق مع الدخول والخروج أو يقع في المستقبل.')
            else:
                fields = ('recorded_at', 'notes', 'receiver_name', 'receiver_relation')
                before = {key: str(getattr(movement, key)) for key in fields}
                changes = {key: form.cleaned_data[key] for key in fields}
                SecurityMovement.objects.filter(pk=movement.pk).update(**changes)
                SecurityMovementCorrection.objects.create(movement=movement, reason=form.cleaned_data['reason'], before=before, after={key: str(value) for key, value in changes.items()}, corrected_by=request.user)
                messages.success(request, 'تم تصحيح الحركة وحفظ سبب التصحيح وسجله.')
                return redirect('security_home')
    return render(request, 'academies/security_correction.html', {'form': form, 'movement': movement, 'audit': movement.corrections.select_related('corrected_by').order_by('-corrected_at')})
