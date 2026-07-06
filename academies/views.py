import json
from calendar import monthrange
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Q, Count
from datetime import date, timedelta
from .models import Academy, DailyBooking, Customer, OperationDayCancellation, AcademyOperationOverride, Shareholder, Employee, FoundingExpense, MonthlyExpense, DailyExpense, OperatingExpense, CafeteriaItem, CafeteriaPurchase, CafeteriaSale, UserPermission, DailyBookingCheckout, DailyIncomeSupply, JobTitle, BonusTier
from .forms import AcademyForm, DailyBookingForm, ShareholderForm, EmployeeForm, FoundingExpenseForm, MonthlyExpenseForm, DailyExpenseForm, OperatingExpenseForm, CafeteriaItemForm, CafeteriaPurchaseForm, CafeteriaSaleForm, EESSUserForm, EESSUserUpdateForm, EESSPermissionForm, JobTitleForm, BonusTierForm, split_values
from .constants import OPERATION_SCREEN_PLACES, TIME_INDEX, SLOT_LABELS, WEEKDAY_AR, PERIOD_CHOICES, PERIOD_SLOT_RANGES, TIME_CHOICES


def _can_manage_users(user):
    if user.is_superuser or user.is_staff:
        return True
    try:
        return bool(user.eess_permissions.can_users)
    except Exception:
        return False

def _ensure_user_profile(user):
    profile, _ = UserPermission.objects.get_or_create(user=user)
    return profile


REPORT_PERMISSION_FIELDS = {
    'income': 'can_report_income',
    'daily_booking_monthly': 'can_report_income',
    'shareholders': 'can_report_shareholders',
    'employees': 'can_report_employees',
    'payroll': 'can_report_payroll',
    'expenses': 'can_report_expenses',
    'founding_expenses': 'can_report_expenses',
    'monthly_expenses': 'can_report_expenses',
    'daily_expenses': 'can_report_expenses',
    'operating_expenses': 'can_report_expenses',
    'cafeteria': 'can_report_cafeteria',
    'cafeteria_inventory': 'can_report_cafeteria',
    'cafeteria_sales': 'can_report_cafeteria',
    'cafeteria_purchases': 'can_report_cafeteria',
    'deposits': 'can_report_deposits',
}

ARABIC_MONTH_NAMES = {
    1: 'يناير',
    2: 'فبراير',
    3: 'مارس',
    4: 'أبريل',
    5: 'مايو',
    6: 'يونيو',
    7: 'يوليو',
    8: 'أغسطس',
    9: 'سبتمبر',
    10: 'أكتوبر',
    11: 'نوفمبر',
    12: 'ديسمبر',
}

def _user_allowed_report_types(user):
    all_report_types = list(REPORT_PERMISSION_FIELDS.keys())
    if user.is_superuser or user.is_staff:
        return all_report_types
    try:
        profile = user.eess_permissions
    except Exception:
        return []
    if getattr(profile, 'can_reports', False):
        return all_report_types
    return [key for key, field in REPORT_PERMISSION_FIELDS.items() if getattr(profile, field, False)]

def _can_access_reports(user):
    return bool(_user_allowed_report_types(user))


def login_view(request):
    """Custom login screen with username selected from registered users."""
    users = User.objects.filter(is_active=True).order_by('username')
    next_url = request.GET.get('next') or request.POST.get('next') or 'dashboard'
    if request.user.is_authenticated:
        return redirect(next_url if next_url != 'dashboard' else 'dashboard')
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect(next_url if next_url != 'dashboard' else 'dashboard')
        error = 'اسم المستخدم أو كلمة المرور غير صحيحة.'
    return render(request, 'academies/login.html', {'users': users, 'login_error': error, 'next': next_url})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard(request):
    today = date.today()
    soon = today + timedelta(days=30)
    context = {
        'total_academies': Academy.objects.count(),
        'active_contracts': Academy.objects.filter(contract_end_date__gte=today).count(),
        'ending_soon': Academy.objects.filter(contract_end_date__range=(today, soon)).count(),
        'monthly_total': Academy.objects.aggregate(total=Sum('monthly_subscription'))['total'] or 0,
        'latest_academies': Academy.objects.all()[:5],
        'daily_bookings_today': DailyBooking.objects.filter(booking_date=today).count(),
        'shareholders_count': Shareholder.objects.count(),
        'employees_count': Employee.objects.count(),
    }
    return render(request, 'academies/dashboard.html', context)


@login_required
def academy_list(request):
    q = request.GET.get('q', '').strip()
    academies = Academy.objects.all()
    if q:
        academies = (Academy.objects.filter(name__icontains=q) |
                     Academy.objects.filter(sport_activity__icontains=q) |
                     Academy.objects.filter(manager_name__icontains=q) |
                     Academy.objects.filter(operation_place__icontains=q))
    return render(request, 'academies/academy_list.html', {'academies': academies, 'q': q})


@login_required
def academy_create(request):
    form = AcademyForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('academy_list')
    return render(request, 'academies/academy_form.html', {'form': form, 'title': 'إضافة أكاديمية'})


@login_required
def academy_update(request, pk):
    academy = get_object_or_404(Academy, pk=pk)
    old_schedule = {
        'operation_place': academy.operation_place,
        'training_days': academy.training_days,
        'training_hours': academy.training_hours,
        'has_extra_hours': academy.has_extra_hours,
        'extra_training_days': academy.extra_training_days,
        'extra_training_place': academy.extra_training_place,
        'extra_training_hours': academy.extra_training_hours,
    }
    form = AcademyForm(request.POST or None, instance=academy)
    if form.is_valid():
        academy = form.save()
        new_schedule = {
            'operation_place': academy.operation_place,
            'training_days': academy.training_days,
            'training_hours': academy.training_hours,
            'has_extra_hours': academy.has_extra_hours,
            'extra_training_days': academy.extra_training_days,
            'extra_training_place': academy.extra_training_place,
            'extra_training_hours': academy.extra_training_hours,
        }
        if old_schedule != new_schedule:
            # أي تعديل في مواعيد/أماكن الأكاديمية يسري على كل الأيام المخصصة للأكاديمية من تاريخ التعديل.
            # لذلك يتم حذف تعديلات شاشة التشغيل المستقبلية لنفس الأكاديمية حتى تظهر المواعيد الجديدة مباشرة.
            AcademyOperationOverride.objects.filter(academy=academy, booking_date__gte=date.today()).delete()
            messages.success(request, 'تم حفظ تعديل مواعيد الأكاديمية، وسيتم تطبيقها من تاريخ التعديل على الأيام المخصصة لها.')
        else:
            messages.success(request, 'تم حفظ بيانات الأكاديمية.')
        return redirect('academy_list')
    return render(request, 'academies/academy_form.html', {'form': form, 'title': 'تعديل أكاديمية'})


@login_required
def academy_delete(request, pk):
    academy = get_object_or_404(Academy, pk=pk)
    if request.method == 'POST':
        academy.delete()
        return redirect('academy_list')
    return render(request, 'academies/academy_confirm_delete.html', {'academy': academy})


def _customers_lookup_context():
    customers = []
    for c in Customer.objects.all().order_by('customer_name'):
        visits = DailyBooking.objects.filter(customer_phone=c.customer_phone).order_by('-booking_date')
        last = visits.first()
        customers.append({
            'code': c.customer_code,
            'name': c.customer_name,
            'phone': c.customer_phone,
            'national_id': c.national_id,
            'visits_count': visits.count(),
            'last_visit_date': last.booking_date.isoformat() if last else '',
            'last_visit_display': last.booking_date.strftime('%A %d/%m/%Y') if last else '',
        })
    return json.dumps(customers, ensure_ascii=False)


@login_required
def booking_list(request):
    q = request.GET.get('q', '').strip()
    bookings = DailyBooking.objects.all()
    if q:
        bookings = (DailyBooking.objects.filter(customer_name__icontains=q) |
                    DailyBooking.objects.filter(customer_phone__icontains=q) |
                    DailyBooking.objects.filter(venue__icontains=q))
    return render(request, 'academies/booking_list.html', {'bookings': bookings, 'q': q})


@login_required
def booking_create(request):
    form = DailyBookingForm(request.POST or None)
    if form.is_valid():
        form.save_all()
        return redirect('booking_list')
    return render(request, 'academies/booking_form.html', {'form': form, 'title': 'إضافة حجز يومي', 'customers_json': _customers_lookup_context()})


@login_required
def booking_update(request, pk):
    booking = get_object_or_404(DailyBooking, pk=pk)
    form = DailyBookingForm(request.POST or None, instance=booking)
    if form.is_valid():
        form.save_all()
        return redirect('booking_list')
    return render(request, 'academies/booking_form.html', {'form': form, 'title': 'تعديل حجز يومي', 'customers_json': _customers_lookup_context()})


@login_required
def booking_delete(request, pk):
    booking = get_object_or_404(DailyBooking, pk=pk)
    if request.method == 'POST':
        booking.delete()
        return redirect('booking_list')
    return render(request, 'academies/booking_confirm_delete.html', {'booking': booking})




def _norm(value):
    if value is None:
        return ''
    value = str(value)
    for mark in ['ً', 'ٌ', 'ٍ', 'َ', 'ُ', 'ِ', 'ّ', 'ْ', 'ـ']:
        value = value.replace(mark, '')
    value = value.replace('# ', '#').replace(' #', '#')
    return ' '.join(value.split()).strip()


def _contains_value(csv_value, target):
    target_n = _norm(target)
    return any(_norm(item) == target_n for item in split_values(csv_value))

def _time_range_indexes(start, end):
    try:
        start_i = _time_to_index(start)
        end_i = _time_to_index(end)
        if start_i is None or end_i is None:
            return []
    except KeyError:
        return []
    if end_i <= start_i:
        return []
    return list(range(start_i, end_i))


def _time_to_index(value):
    if value in TIME_INDEX:
        return TIME_INDEX[value]
    value_n = _norm(value)
    for label, idx in TIME_INDEX.items():
        if _norm(label) == value_n:
            return idx
    return None


def _slot_label_to_index(slot_label):
    if not slot_label:
        return None
    if ' - ' in slot_label:
        start = slot_label.split(' - ', 1)[0].strip()
        return _time_to_index(start)
    return _time_to_index(slot_label)


def _academy_time_indexes_for_place(academy, place):
    indexes = []
    if _contains_value(academy.operation_place, place):
        indexes += [idx for idx in (_slot_label_to_index(slot) for slot in split_values(academy.training_hours)) if idx is not None]
    if _contains_value(academy.extra_training_place, place):
        indexes += [idx for idx in (_slot_label_to_index(slot) for slot in split_values(academy.extra_training_hours)) if idx is not None]
    return indexes


@login_required
def cancel_operation_day(request):
    selected_date_text = request.POST.get('date') or request.GET.get('date')
    try:
        selected_date = date.fromisoformat(selected_date_text)
    except Exception:
        selected_date = date.today()
    if request.method == 'POST':
        DailyBooking.objects.filter(booking_date=selected_date).delete()
        OperationDayCancellation.objects.get_or_create(cancel_date=selected_date)
        AcademyOperationOverride.objects.filter(booking_date=selected_date).delete()
        messages.success(request, f'تم إلغاء كل حجوزات يوم {selected_date}، وتم حذف الحجز اليومي وعدم احتساب حجوزات الأكاديميات لهذا اليوم.')
    return redirect(f'/operation/?date={selected_date.isoformat()}&period={request.POST.get("period", request.GET.get("period", "evening"))}')


def _academy_occurrences_for_date(selected_date, include_cancelled=False):
    selected_day_ar = WEEKDAY_AR[selected_date.weekday()]
    if OperationDayCancellation.objects.filter(cancel_date=selected_date).exists() and not include_cancelled:
        return []
    occurrences = []
    academies = Academy.objects.filter(contract_start_date__lte=selected_date, contract_end_date__gte=selected_date)
    override_map = {
        (ov.academy_id, _norm(ov.original_place), ov.original_slot_index): ov
        for ov in AcademyOperationOverride.objects.filter(booking_date=selected_date).select_related('academy')
    }
    for academy in academies:
        # أساسي
        if _contains_value(academy.training_days, selected_day_ar):
            for place in split_values(academy.operation_place):
                for slot in split_values(academy.training_hours):
                    idx = _slot_label_to_index(slot)
                    if idx is None:
                        continue
                    key = (academy.id, _norm(place), idx)
                    ov = override_map.get(key)
                    if ov and ov.is_deleted and not include_cancelled:
                        continue
                    final_place = ov.new_place if ov and ov.new_place else place
                    final_idx = ov.new_slot_index if ov and ov.new_slot_index is not None else idx
                    occurrences.append({'academy': academy, 'place': final_place, 'slot_index': final_idx, 'original_place': place, 'original_slot_index': idx, 'is_extra': False})
        # إضافي
        extra_days = academy.extra_training_days or academy.training_days
        if academy.has_extra_hours and _contains_value(extra_days, selected_day_ar):
            for place in split_values(academy.extra_training_place):
                for slot in split_values(academy.extra_training_hours):
                    idx = _slot_label_to_index(slot)
                    if idx is None:
                        continue
                    key = (academy.id, _norm(place), idx)
                    ov = override_map.get(key)
                    if ov and ov.is_deleted and not include_cancelled:
                        continue
                    final_place = ov.new_place if ov and ov.new_place else place
                    final_idx = ov.new_slot_index if ov and ov.new_slot_index is not None else idx
                    occurrences.append({'academy': academy, 'place': final_place, 'slot_index': final_idx, 'original_place': place, 'original_slot_index': idx, 'is_extra': True})
    return occurrences


@login_required
def operation_card_action(request):
    if request.method != 'POST':
        return redirect('operation_screen')
    action = request.POST.get('action')
    item_type = request.POST.get('item_type')
    selected_date_text = request.POST.get('date')
    period = request.POST.get('period', 'all')
    try:
        selected_date = date.fromisoformat(selected_date_text)
    except Exception:
        selected_date = date.today()

    if item_type == 'daily':
        booking = get_object_or_404(DailyBooking, pk=request.POST.get('item_id'))
        if action == 'delete':
            # حذف الحجز اليومي يحذف أي Checkout مرتبط به تلقائيًا ويلغي قيمته من الدخل اليومي.
            booking.delete()
            messages.success(request, 'تم حذف الحجز اليومي وإلغاء قيمته من الدخل.')
        elif action == 'checkout':
            DailyBookingCheckout.objects.update_or_create(
                booking=booking,
                defaults={
                    'income_date': booking.booking_date,
                    'customer_name': booking.customer_name,
                    'customer_phone': booking.customer_phone,
                    'venue': booking.venue,
                    'booking_date': booking.booking_date,
                    'start_time': booking.start_time,
                    'end_time': booking.end_time,
                    'total_amount': booking.total_amount,
                    'advance_payment': booking.advance_payment,
                    'remaining_amount': booking.remaining_amount,
                }
            )
            messages.success(request, 'تم عمل Checkout وتسجيل قيمة الحجز في الدخل اليومي.')
            return redirect(f'/operation/?date={booking.booking_date.isoformat()}&period={period}')
        elif action == 'edit':
            new_start = request.POST.get('new_start_time')
            new_end = request.POST.get('new_end_time')
            if new_start and new_end and TIME_INDEX.get(new_end, 0) > TIME_INDEX.get(new_start, 0):
                # تحقق بسيط من التعارض بعد استبعاد نفس الحجز
                form_data = {
                    'customer_name': booking.customer_name, 'customer_phone': booking.customer_phone,
                    'national_id': booking.national_id, 'players_count': booking.players_count, 'amount': booking.amount,
                    'advance_payment': booking.advance_payment, 'total_amount': booking.total_amount, 'remaining_amount': booking.remaining_amount,
                    'venue': booking.venue, 'booking_date': booking.booking_date, 'booking_dates': booking.booking_date.isoformat(),
                    'booking_date_times': json.dumps([{'date': booking.booking_date.isoformat(), 'start_time': new_start, 'end_time': new_end}]),
                    'start_time': new_start, 'end_time': new_end, 'notes': booking.notes,
                }
                from .forms import DailyBookingForm
                form = DailyBookingForm(form_data, instance=booking)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'تم تعديل توقيت الحجز اليومي.')
                else:
                    messages.error(request, 'لم يتم تعديل الحجز: ' + ' '.join([str(e) for e in form.non_field_errors()]))
            else:
                messages.error(request, 'اختر توقيت صحيح.')

    elif item_type == 'academy':
        academy = get_object_or_404(Academy, pk=request.POST.get('item_id'))
        original_place = request.POST.get('original_place')
        try:
            original_slot_index = int(request.POST.get('original_slot_index'))
        except Exception:
            original_slot_index = -1
        if original_slot_index >= 0 and original_place:
            ov, _ = AcademyOperationOverride.objects.get_or_create(
                academy=academy, booking_date=selected_date, original_place=original_place, original_slot_index=original_slot_index,
                defaults={'new_place': original_place, 'new_slot_index': original_slot_index}
            )
            if action == 'delete':
                ov.is_deleted = True
                ov.save()
                messages.success(request, 'تم حذف حجز الأكاديمية لهذا اليوم وإلغاء قيمته من الدخل المتغير.')
            elif action == 'edit':
                new_slot = request.POST.get('new_slot_index')
                try:
                    new_slot_index = int(new_slot)
                except Exception:
                    new_slot_index = original_slot_index
                ov.is_deleted = False
                ov.new_place = original_place
                ov.new_slot_index = new_slot_index
                ov.save()
                messages.success(request, 'تم تعديل توقيت حجز الأكاديمية لهذا اليوم فقط.')
    return redirect(f'/operation/?date={selected_date.isoformat()}&period={period}')


@login_required
def operation_screen(request):
    selected_date = request.GET.get('date')
    if selected_date:
        try:
            selected_date = date.fromisoformat(selected_date)
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()

    selected_day_ar = WEEKDAY_AR[selected_date.weekday()]
    selected_period = request.GET.get('period', 'evening')
    if selected_period not in PERIOD_SLOT_RANGES:
        selected_period = 'all'
    visible_slot_indexes = list(PERIOD_SLOT_RANGES[selected_period])
    day_cancelled = OperationDayCancellation.objects.filter(cancel_date=selected_date).exists()

    academy_occurrences = _academy_occurrences_for_date(selected_date)

    rows = []
    for place in OPERATION_SCREEN_PLACES:
        cards = []
        for slot_index in visible_slot_indexes:
            slot_label = SLOT_LABELS[slot_index]
            entries = []
            for occ in academy_occurrences:
                if _norm(occ['place']) == _norm(place) and occ['slot_index'] == slot_index:
                    academy = occ['academy']
                    entries.append({
                        'label': f'أكاديمية: {academy.name}',
                        'item_type': 'academy',
                        'item_id': academy.id,
                        'original_place': occ['original_place'],
                        'original_slot_index': occ['original_slot_index'],
                    })

            for booking in DailyBooking.objects.filter(venue=place, booking_date=selected_date):
                if slot_index in _time_range_indexes(booking.start_time, booking.end_time):
                    entries.append({
                        'label': f'حجز: {booking.customer_name}',
                        'item_type': 'daily',
                        'item_id': booking.id,
                        'original_place': place,
                        'original_slot_index': slot_index,
                        'customer_name': booking.customer_name,
                        'customer_phone': booking.customer_phone,
                        'booking_date': booking.booking_date.strftime('%d/%m/%Y'),
                        'booking_day': WEEKDAY_AR[booking.booking_date.weekday()],
                        'start_time': booking.start_time,
                        'end_time': booking.end_time,
                        'total_amount': booking.total_amount,
                        'advance_payment': booking.advance_payment,
                        'remaining_amount': booking.remaining_amount,
                        'checked_out': hasattr(booking, 'checkout'),
                    })

            has_checked_out = any(e.get('item_type') == 'daily' and e.get('checked_out') for e in entries)
            has_academy = any(e.get('item_type') == 'academy' for e in entries)
            has_daily = any(e.get('item_type') == 'daily' for e in entries)
            if has_checked_out:
                card_class = 'checkout-busy'
            elif has_academy:
                card_class = 'academy-busy'
            elif has_daily:
                card_class = 'daily-busy'
            else:
                card_class = ''
            cards.append({
                'time': slot_label,
                'busy': bool(entries),
                'card_class': card_class,
                'entries': entries,
            })
        rows.append({'place': place, 'cards': cards})

    return render(request, 'academies/operation_screen.html', {
        'selected_date': selected_date,
        'selected_day_ar': selected_day_ar,
        'selected_period': selected_period,
        'period_choices': PERIOD_CHOICES,
        'rows': rows,
        'day_cancelled': day_cancelled,
        'slot_choices': [(i, SLOT_LABELS[i]) for i in visible_slot_indexes],
        'time_choices': TIME_CHOICES,
    })


@login_required
def daily_income(request):
    selected_date = request.GET.get('date')
    if selected_date:
        try:
            selected_date = date.fromisoformat(selected_date)
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()

    view_mode = request.GET.get('view', 'daily')

    if request.method == 'POST' and view_mode == 'monthly':
        days_count = monthrange(selected_date.year, selected_date.month)[1]
        for day_no in range(1, days_count + 1):
            current_date = date(selected_date.year, selected_date.month, day_no)
            raw_amount = (request.POST.get(f'supply_{current_date.isoformat()}') or '0').strip()
            try:
                amount = max(0, int(raw_amount or 0))
            except ValueError:
                amount = 0
            if amount:
                DailyIncomeSupply.objects.update_or_create(
                    supply_date=current_date,
                    defaults={'amount': amount},
                )
            else:
                DailyIncomeSupply.objects.filter(supply_date=current_date).delete()
        return redirect(f"{request.path}?date={selected_date.isoformat()}&view=monthly")

    rows = DailyBookingCheckout.objects.filter(income_date=selected_date).order_by('start_time', 'customer_name')
    total_income = rows.aggregate(total=Sum('total_amount'))['total'] or 0
    total_advance = rows.aggregate(total=Sum('advance_payment'))['total'] or 0
    total_remaining = rows.aggregate(total=Sum('remaining_amount'))['total'] or 0

    month_rows = []
    month_income_total = 0
    month_expense_total = 0
    month_profit_total = 0
    month_supply_total = 0
    month_treasury_remaining = 0
    if view_mode == 'monthly':
        days_count = monthrange(selected_date.year, selected_date.month)[1]
        supply_map = {
            item.supply_date: item.amount
            for item in DailyIncomeSupply.objects.filter(
                supply_date__year=selected_date.year,
                supply_date__month=selected_date.month,
            )
        }
        for day_no in range(1, days_count + 1):
            current_date = date(selected_date.year, selected_date.month, day_no)
            day_income = DailyBookingCheckout.objects.filter(income_date=current_date).aggregate(total=Sum('total_amount'))['total'] or 0
            day_expenses = (DailyExpense.objects.filter(expense_date=current_date).aggregate(total=Sum('amount'))['total'] or 0) + (OperatingExpense.objects.filter(expense_date=current_date).aggregate(total=Sum('amount'))['total'] or 0)
            net_profit = int(day_income) - int(day_expenses)
            day_supply = int(supply_map.get(current_date, 0) or 0)
            month_treasury_remaining = month_treasury_remaining + int(day_income) - day_supply
            month_income_total += int(day_income)
            month_expense_total += int(day_expenses)
            month_profit_total += int(net_profit)
            month_supply_total += day_supply
            month_rows.append({
                'date': current_date,
                'day_name': WEEKDAY_AR[current_date.weekday()],
                'income': day_income,
                'expenses': day_expenses,
                'net_profit': net_profit,
                'supply': day_supply,
                'treasury_remaining': month_treasury_remaining,
            })

    return render(request, 'academies/daily_income.html', {
        'selected_date': selected_date,
        'selected_day_ar': WEEKDAY_AR[selected_date.weekday()],
        'view_mode': view_mode,
        'rows': rows,
        'total_income': total_income,
        'total_advance': total_advance,
        'total_remaining': total_remaining,
        'month_rows': month_rows,
        'month_income_total': month_income_total,
        'month_expense_total': month_expense_total,
        'month_profit_total': month_profit_total,
        'month_supply_total': month_supply_total,
        'month_treasury_remaining': month_treasury_remaining,
        'month_name': ARABIC_MONTH_NAMES[selected_date.month],
    })


@login_required
def shareholder_list(request):
    q = request.GET.get('q', '').strip()
    shareholders = Shareholder.objects.all()
    if q:
        shareholders = (Shareholder.objects.filter(name__icontains=q) |
                        Shareholder.objects.filter(phone__icontains=q) |
                        Shareholder.objects.filter(national_id__icontains=q))
    return render(request, 'academies/shareholder_list.html', {'shareholders': shareholders, 'q': q})

@login_required
def shareholder_create(request):
    form = ShareholderForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('shareholder_list')
    return render(request, 'academies/simple_form.html', {'form': form, 'title': 'إضافة مساهم', 'back_url': 'shareholder_list'})

@login_required
def shareholder_update(request, pk):
    shareholder = get_object_or_404(Shareholder, pk=pk)
    form = ShareholderForm(request.POST or None, instance=shareholder)
    if form.is_valid():
        form.save()
        return redirect('shareholder_list')
    return render(request, 'academies/simple_form.html', {'form': form, 'title': 'تعديل مساهم', 'back_url': 'shareholder_list'})

@login_required
def shareholder_delete(request, pk):
    shareholder = get_object_or_404(Shareholder, pk=pk)
    if request.method == 'POST':
        shareholder.delete()
        return redirect('shareholder_list')
    return render(request, 'academies/simple_confirm_delete.html', {'object': shareholder, 'title': 'حذف مساهم', 'back_url': 'shareholder_list'})

@login_required
def employee_list(request):
    q = request.GET.get('q', '').strip()
    employees = Employee.objects.all()
    if q:
        employees = (Employee.objects.filter(name__icontains=q) |
                     Employee.objects.filter(phone__icontains=q) |
                     Employee.objects.filter(national_id__icontains=q) |
                     Employee.objects.filter(job_title__icontains=q))
    return render(request, 'academies/employee_list.html', {'employees': employees, 'q': q})

@login_required
def employee_create(request):
    form = EmployeeForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('employee_list')
    return render(request, 'academies/simple_form.html', {'form': form, 'title': 'إضافة موظف', 'back_url': 'employee_list'})

@login_required
def employee_update(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    form = EmployeeForm(request.POST or None, instance=employee)
    if form.is_valid():
        form.save()
        return redirect('employee_list')
    return render(request, 'academies/simple_form.html', {'form': form, 'title': 'تعديل موظف', 'back_url': 'employee_list'})

@login_required
def employee_delete(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        employee.delete()
        return redirect('employee_list')
    return render(request, 'academies/simple_confirm_delete.html', {'object': employee, 'title': 'حذف موظف', 'back_url': 'employee_list'})



def _month_bounds(month_text):
    if month_text:
        try:
            year, month = [int(x) for x in month_text.split('-')[:2]]
        except Exception:
            today = date.today(); year, month = today.year, today.month
    else:
        today = date.today(); year, month = today.year, today.month
    from calendar import monthrange
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return year, month, start, end, f'{year:04d}-{month:02d}'


def _generic_crud_list(request, model, template, context_name, search_fields=None):
    q = request.GET.get('q', '').strip()
    objects = model.objects.all()
    if q and search_fields:
        query = None
        for field in search_fields:
            part = {f'{field}__icontains': q}
            query = Q(**part) if query is None else query | Q(**part)
        objects = objects.filter(query)
    return render(request, template, {context_name: objects, 'q': q})


def _generic_form(request, form_class, title, back_url, instance=None):
    form = form_class(request.POST or None, instance=instance)
    if form.is_valid():
        form.save()
        return redirect(back_url)
    return render(request, 'academies/simple_form.html', {'form': form, 'title': title, 'back_url': back_url})


def _generic_delete(request, obj, title, back_url):
    if request.method == 'POST':
        obj.delete()
        return redirect(back_url)
    return render(request, 'academies/simple_confirm_delete.html', {'object': obj, 'title': title, 'back_url': back_url})


@login_required
def general_expenses_home(request):
    founding_total = FoundingExpense.objects.aggregate(total=Sum('amount'))['total'] or 0
    monthly_total = MonthlyExpense.objects.aggregate(total=Sum('amount'))['total'] or 0
    daily_total = DailyExpense.objects.aggregate(total=Sum('amount'))['total'] or 0
    operating_total = OperatingExpense.objects.aggregate(total=Sum('amount'))['total'] or 0
    return render(request, 'academies/general_expenses.html', {
        'founding_total': founding_total,
        'monthly_total': monthly_total,
        'daily_total': daily_total,
        'operating_total': operating_total,
    })

@login_required
def founding_expense_list(request):
    return _generic_crud_list(request, FoundingExpense, 'academies/founding_expense_list.html', 'expenses', ['title', 'notes'])

@login_required
def founding_expense_create(request):
    return _generic_form(request, FoundingExpenseForm, 'إضافة مصروف تأسيس', 'founding_expense_list')

@login_required
def founding_expense_update(request, pk):
    return _generic_form(request, FoundingExpenseForm, 'تعديل مصروف تأسيس', 'founding_expense_list', get_object_or_404(FoundingExpense, pk=pk))

@login_required
def founding_expense_delete(request, pk):
    return _generic_delete(request, get_object_or_404(FoundingExpense, pk=pk), 'حذف مصروف تأسيس', 'founding_expense_list')

@login_required
def monthly_expense_list(request):
    return _generic_crud_list(request, MonthlyExpense, 'academies/monthly_expense_list.html', 'expenses', ['title', 'notes'])

@login_required
def monthly_expense_create(request):
    return _generic_form(request, MonthlyExpenseForm, 'إضافة مصروف شهري', 'monthly_expense_list')

@login_required
def monthly_expense_update(request, pk):
    return _generic_form(request, MonthlyExpenseForm, 'تعديل مصروف شهري', 'monthly_expense_list', get_object_or_404(MonthlyExpense, pk=pk))

@login_required
def monthly_expense_delete(request, pk):
    return _generic_delete(request, get_object_or_404(MonthlyExpense, pk=pk), 'حذف مصروف شهري', 'monthly_expense_list')


@login_required
def daily_expense_list(request):
    return _generic_crud_list(request, DailyExpense, 'academies/daily_expense_list.html', 'expenses', ['title', 'notes'])

@login_required
def daily_expense_create(request):
    return _generic_form(request, DailyExpenseForm, 'إضافة مصروف يومي', 'daily_expense_list')

@login_required
def daily_expense_update(request, pk):
    return _generic_form(request, DailyExpenseForm, 'تعديل مصروف يومي', 'daily_expense_list', get_object_or_404(DailyExpense, pk=pk))

@login_required
def daily_expense_delete(request, pk):
    return _generic_delete(request, get_object_or_404(DailyExpense, pk=pk), 'حذف مصروف يومي', 'daily_expense_list')


@login_required
def operating_expense_list(request):
    return _generic_crud_list(request, OperatingExpense, 'academies/operating_expense_list.html', 'expenses', ['title', 'notes'])

@login_required
def operating_expense_create(request):
    return _generic_form(request, OperatingExpenseForm, 'إضافة مصروف تشغيل', 'operating_expense_list')

@login_required
def operating_expense_update(request, pk):
    return _generic_form(request, OperatingExpenseForm, 'تعديل مصروف تشغيل', 'operating_expense_list', get_object_or_404(OperatingExpense, pk=pk))

@login_required
def operating_expense_delete(request, pk):
    return _generic_delete(request, get_object_or_404(OperatingExpense, pk=pk), 'حذف مصروف تشغيل', 'operating_expense_list')


@login_required
def cafe_item_list(request):
    return _generic_crud_list(request, CafeteriaItem, 'academies/cafe_item_list.html', 'items', ['name', 'notes'])

@login_required
def cafe_settings(request):
    return render(request, 'academies/cafe_settings.html')

@login_required
def cafe_stock_adjust(request):
    items = CafeteriaItem.objects.all().order_by('name')
    if request.method == 'POST':
        for item in items:
            value = request.POST.get(f'quantity_{item.id}', '').strip()
            if value != '':
                try:
                    item.opening_quantity = max(0, int(value))
                    item.save(update_fields=['opening_quantity'])
                except ValueError:
                    messages.error(request, f'قيمة المخزون للصنف {item.name} غير صحيحة.')
                    return redirect('cafe_stock_adjust')
        messages.success(request, 'تم حفظ كميات المخزون بنجاح.')
        return redirect('cafe_item_list')
    return render(request, 'academies/cafe_stock_adjust.html', {'items': items})

@login_required
def cafe_sale_prices(request):
    items = CafeteriaItem.objects.all().order_by('name')
    if request.method == 'POST':
        for item in items:
            value = request.POST.get(f'price_{item.id}', '').strip()
            if value != '':
                try:
                    item.sale_price = max(0, int(value))
                    item.save(update_fields=['sale_price'])
                except ValueError:
                    messages.error(request, f'سعر البيع للصنف {item.name} غير صحيح.')
                    return redirect('cafe_sale_prices')
        messages.success(request, 'تم حفظ أسعار البيع بنجاح.')
        return redirect('cafe_item_list')
    return render(request, 'academies/cafe_sale_prices.html', {'items': items})

@login_required
def cafe_item_create(request):
    return _generic_form(request, CafeteriaItemForm, 'إضافة صنف كافيتريا', 'cafe_item_list')

@login_required
def cafe_item_update(request, pk):
    return _generic_form(request, CafeteriaItemForm, 'تعديل صنف كافيتريا', 'cafe_item_list', get_object_or_404(CafeteriaItem, pk=pk))

@login_required
def cafe_item_delete(request, pk):
    return _generic_delete(request, get_object_or_404(CafeteriaItem, pk=pk), 'حذف صنف كافيتريا', 'cafe_item_list')


@login_required
def cafe_purchase_list(request):
    purchases = CafeteriaPurchase.objects.select_related('item').all()
    return render(request, 'academies/cafe_purchase_list.html', {'purchases': purchases})

@login_required
def cafe_purchase_create(request):
    return _generic_form(request, CafeteriaPurchaseForm, 'إضافة حركة شراء كافيتريا', 'cafe_purchase_list')

@login_required
def cafe_purchase_update(request, pk):
    return _generic_form(request, CafeteriaPurchaseForm, 'تعديل حركة شراء كافيتريا', 'cafe_purchase_list', get_object_or_404(CafeteriaPurchase, pk=pk))

@login_required
def cafe_purchase_delete(request, pk):
    return _generic_delete(request, get_object_or_404(CafeteriaPurchase, pk=pk), 'حذف حركة شراء كافيتريا', 'cafe_purchase_list')


@login_required
def cafe_sale_list(request):
    sales = CafeteriaSale.objects.select_related('item').all()
    return render(request, 'academies/cafe_sale_list.html', {'sales': sales})

@login_required
def cafe_sale_create(request):
    form = CafeteriaSaleForm(request.POST or None)
    if form.is_valid():
        sale = form.save(commit=False)
        if not sale.unit_price and sale.item_id:
            sale.unit_price = sale.item.sale_price
        sale.save()
        messages.success(request, 'تم حفظ حركة البيع بنجاح.')
        return redirect('cafe_sale_list')
    return render(request, 'academies/cafe_sale_form.html', {'form': form, 'title': 'إضافة حركة بيع كافيتريا', 'back_url': 'cafe_sale_list', 'items': list(CafeteriaItem.objects.values('id', 'sale_price'))})

@login_required
def cafe_sale_update(request, pk):
    sale_obj = get_object_or_404(CafeteriaSale, pk=pk)
    form = CafeteriaSaleForm(request.POST or None, instance=sale_obj)
    if form.is_valid():
        sale = form.save(commit=False)
        if not sale.unit_price and sale.item_id:
            sale.unit_price = sale.item.sale_price
        sale.save()
        messages.success(request, 'تم تعديل حركة البيع بنجاح.')
        return redirect('cafe_sale_list')
    return render(request, 'academies/cafe_sale_form.html', {'form': form, 'title': 'تعديل حركة بيع كافيتريا', 'back_url': 'cafe_sale_list', 'items': list(CafeteriaItem.objects.values('id', 'sale_price'))})

@login_required
def cafe_sale_delete(request, pk):
    return _generic_delete(request, get_object_or_404(CafeteriaSale, pk=pk), 'حذف حركة بيع كافيتريا', 'cafe_sale_list')



def _calculate_fixed_income_with_operation_changes(academy, year, month):
    # توزيع الاشتراك الثابت على عدد ساعات التشغيل في الشهر حتى يتم خصم أي ساعة/يوم ملغي من الدخل.
    if academy.subscription_type != 'fixed':
        return academy.monthly_subscription
    from calendar import monthrange
    total_planned = 0
    active_planned = 0
    for day_number in range(1, monthrange(year, month)[1] + 1):
        current = date(year, month, day_number)
        if not (academy.contract_start_date <= current <= academy.contract_end_date):
            continue
        # احسب الجدول الأصلي بدون إلغاءات.
        total_planned += len([o for o in _academy_occurrences_for_date(current, include_cancelled=True) if o['academy'].id == academy.id])
        active_planned += len([o for o in _academy_occurrences_for_date(current) if o['academy'].id == academy.id])
    if total_planned <= 0:
        return int(academy.monthly_subscription or 0)
    return int((academy.monthly_subscription or 0) * active_planned / total_planned)


def _calculate_variable_income_with_operation_changes(academy, year, month):
    # حساب الاشتراك المتغير مع استبعاد الأيام الملغاة وحجوزات الأكاديمية المحذوفة في شاشة التشغيل.
    if academy.subscription_type != 'variable':
        return academy.monthly_subscription
    from calendar import monthrange
    rent_value = int(academy.variable_rent_value or 0)
    total_units = 0
    for day_number in range(1, monthrange(year, month)[1] + 1):
        current = date(year, month, day_number)
        if not (academy.contract_start_date <= current <= academy.contract_end_date):
            continue
        if OperationDayCancellation.objects.filter(cancel_date=current).exists():
            continue
        occs = [o for o in _academy_occurrences_for_date(current) if o['academy'].id == academy.id]
        if academy.variable_rent_type == 'hour':
            total_units += len(occs)
        elif academy.variable_rent_type == 'day' and occs:
            total_units += 1
    return int(rent_value * total_units)


def _monthly_academy_operation_counts(year, month, academies):
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    academy_ids = [academy.id for academy in academies]
    cancelled_dates = set(
        OperationDayCancellation.objects.filter(
            cancel_date__range=(start, end)
        ).values_list('cancel_date', flat=True)
    )
    deleted_overrides = {
        (item.academy_id, item.booking_date, _norm(item.original_place), item.original_slot_index)
        for item in AcademyOperationOverride.objects.filter(
            academy_id__in=academy_ids,
            booking_date__range=(start, end),
            is_deleted=True,
        )
    }
    total_counts = {}
    active_counts = {}
    active_days = {}
    for day_number in range(1, monthrange(year, month)[1] + 1):
        current = date(year, month, day_number)
        day_ar = WEEKDAY_AR[current.weekday()]
        is_cancelled = current in cancelled_dates
        for academy in academies:
            if not (academy.contract_start_date <= current <= academy.contract_end_date):
                continue
            day_active_count = 0
            occurrence_sources = []
            if _contains_value(academy.training_days, day_ar):
                occurrence_sources.append((academy.operation_place, academy.training_hours))
            extra_days = academy.extra_training_days or academy.training_days
            if academy.has_extra_hours and _contains_value(extra_days, day_ar):
                occurrence_sources.append((academy.extra_training_place, academy.extra_training_hours))
            for places_text, hours_text in occurrence_sources:
                for place in split_values(places_text):
                    for slot in split_values(hours_text):
                        slot_index = _slot_label_to_index(slot)
                        if slot_index is None:
                            continue
                        total_counts[academy.id] = total_counts.get(academy.id, 0) + 1
                        deleted_key = (academy.id, current, _norm(place), slot_index)
                        if not is_cancelled and deleted_key not in deleted_overrides:
                            active_counts[academy.id] = active_counts.get(academy.id, 0) + 1
                            day_active_count += 1
            if day_active_count:
                active_days[academy.id] = active_days.get(academy.id, 0) + 1
    return total_counts, active_counts, active_days


def _academy_month_income_from_counts(academy, total_counts, active_counts, active_days):
    academy_id = academy.id
    if academy.subscription_type == 'fixed':
        total_planned = total_counts.get(academy_id, 0)
        active_planned = active_counts.get(academy_id, 0)
        if total_planned <= 0:
            return int(academy.monthly_subscription or 0)
        return int((academy.monthly_subscription or 0) * active_planned / total_planned)
    rent_value = int(academy.variable_rent_value or 0)
    if academy.variable_rent_type == 'hour':
        return rent_value * active_counts.get(academy_id, 0)
    if academy.variable_rent_type == 'day':
        return rent_value * active_days.get(academy_id, 0)
    return 0

@login_required
def reports_home(request):
    allowed_report_types = _user_allowed_report_types(request.user)
    if not allowed_report_types:
        messages.error(request, 'ليس لديك صلاحية عرض التقارير.')
        return redirect('dashboard')
    year, month, start, end, month_value = _month_bounds(request.GET.get('month'))
    report_type = request.GET.get('report_type', 'income')
    report_titles = {
        'income': 'تقرير الدخل من الأكاديميات والحجز اليومي',
        'daily_booking_monthly': 'تقرير الدخل الشهري من الحجز اليومي',
        'shareholders': 'تقرير المساهمين والنسب والأرباح',
        'employees': 'تقرير الموظفين',
        'payroll': 'تقرير المرتبات الشهرية والبونص',
        'expenses': 'تقرير المصروفات',
        'cafeteria': 'تقرير الكافيتريا والأرباح والمخزون',
        'deposits': 'تقرير مبالغ التأمين للأكاديميات',
        'founding_expenses': 'تقرير مصروفات التأسيس',
        'monthly_expenses': 'تقرير المصروفات الشهرية',
        'daily_expenses': 'تقرير المصروفات اليومية',
        'operating_expenses': 'تقرير مصروفات التشغيل',
        'cafeteria_inventory': 'تقرير مخزون الكافيتريا',
        'cafeteria_sales': 'تقرير مبيعات الكافيتريا',
        'cafeteria_purchases': 'تقرير مشتريات الكافيتريا',
    }
    if report_type not in report_titles or report_type not in allowed_report_types:
        report_type = allowed_report_types[0]

    allowed_report_options = [(key, report_titles[key]) for key in allowed_report_types if key in report_titles]

    context = {
        'month_value': month_value,
        'report_type': report_type,
        'report_title': report_titles[report_type],
        'allowed_report_options': allowed_report_options,
        'fixed_income': 0,
        'variable_income': 0,
        'daily_booking_income': 0,
        'daily_booking_checkout_income': 0,
        'total_academy_income': 0,
        'founding_expenses': 0,
        'monthly_expenses': 0,
        'daily_expenses': 0,
        'operating_expenses': 0,
        'salaries_total': 0,
        'cafe_purchase_total': 0,
        'cafe_sales_total': 0,
        'cafe_profit': 0,
        'net_profit': 0,
        'shareholder_rows': [],
        'employees': [],
        'low_stock_items': [],
        'academy_rows': [],
        'daily_booking_monthly_rows': [],
        'cafe_sales': [],
        'cafe_purchases': [],
        'deposit_academies': [],
        'security_deposit_total': 0,
    }

    if report_type == 'income':
        academies = list(Academy.objects.filter(contract_start_date__lte=end, contract_end_date__gte=start))
        total_counts, active_counts, active_days = _monthly_academy_operation_counts(year, month, academies)
        academy_rows = []
        for a in academies:
            if a.subscription_type == 'variable':
                value = _academy_month_income_from_counts(a, total_counts, active_counts, active_days)
                kind = 'متغير'
                sort_type = 1
            else:
                value = _academy_month_income_from_counts(a, total_counts, active_counts, active_days)
                kind = 'ثابت'
                sort_type = 0
            academy_rows.append({
                'academy': a,
                'activity': a.sport_activity,
                'kind': kind,
                'value': value,
                'sort_type': sort_type,
            })
        academy_rows.sort(key=lambda row: (row['sort_type'], row['activity'] or '', row['academy'].name or ''))
        fixed_income = sum(row['value'] for row in academy_rows if row['sort_type'] == 0)
        variable_income = sum(row['value'] for row in academy_rows if row['sort_type'] == 1)
        daily_booking_income = DailyBooking.objects.filter(booking_date__range=(start, end)).aggregate(total=Sum('total_amount'))['total'] or 0
        context.update({
            'academy_rows': academy_rows,
            'fixed_income': fixed_income,
            'variable_income': variable_income,
            'daily_booking_income': daily_booking_income,
            'total_academy_income': fixed_income + variable_income + daily_booking_income,
        })

    elif report_type == 'daily_booking_monthly':
        grouped = {
            row['income_date']: row
            for row in DailyBookingCheckout.objects.filter(income_date__range=(start, end))
            .values('income_date')
            .annotate(
                total=Sum('total_amount'),
                advance=Sum('advance_payment'),
                remaining=Sum('remaining_amount'),
                count=Count('id'),
            )
        }
        daily_booking_monthly_rows = []
        daily_booking_checkout_income = 0
        for day_number in range(1, monthrange(year, month)[1] + 1):
            current = date(year, month, day_number)
            row = grouped.get(current, {})
            total = row.get('total') or 0
            daily_booking_checkout_income += int(total)
            daily_booking_monthly_rows.append({
                'date': current,
                'day_name': WEEKDAY_AR[current.weekday()],
                'total': total,
                'advance': row.get('advance') or 0,
                'remaining': row.get('remaining') or 0,
                'count': row.get('count') or 0,
            })
        context.update({
            'daily_booking_monthly_rows': daily_booking_monthly_rows,
            'daily_booking_checkout_income': daily_booking_checkout_income,
        })

    elif report_type in {'expenses', 'founding_expenses', 'monthly_expenses', 'daily_expenses', 'operating_expenses'}:
        context.update({
            'founding_expenses': FoundingExpense.objects.filter(expense_date__range=(start, end)).aggregate(total=Sum('amount'))['total'] or 0,
            'monthly_expenses': MonthlyExpense.objects.filter(expense_month__range=(start, end)).aggregate(total=Sum('amount'))['total'] or 0,
            'daily_expenses': DailyExpense.objects.filter(expense_date__range=(start, end)).aggregate(total=Sum('amount'))['total'] or 0,
            'operating_expenses': OperatingExpense.objects.filter(expense_date__range=(start, end)).aggregate(total=Sum('amount'))['total'] or 0,
        })

    elif report_type in {'employees', 'payroll'}:
        employees = Employee.objects.all()
        context.update({
            'employees': employees,
            'salaries_total': employees.aggregate(total=Sum('salary'))['total'] or 0,
        })

    elif report_type == 'cafeteria':
        cafe_purchases = CafeteriaPurchase.objects.filter(purchase_date__range=(start, end))
        cafe_sales = CafeteriaSale.objects.filter(sale_date__range=(start, end)).select_related('item')
        cafe_purchase_total = sum(p.total_amount for p in cafe_purchases)
        cafe_sales_total = sum(s.total_amount for s in cafe_sales)
        context.update({
            'cafe_purchases': cafe_purchases,
            'cafe_sales': cafe_sales,
            'cafe_purchase_total': cafe_purchase_total,
            'cafe_sales_total': cafe_sales_total,
            'cafe_profit': cafe_sales_total - cafe_purchase_total,
            'low_stock_items': [item for item in CafeteriaItem.objects.all() if item.is_low_stock],
        })

    elif report_type in {'cafeteria_inventory', 'cafeteria_sales', 'cafeteria_purchases'}:
        context.update({
            'cafe_purchases': CafeteriaPurchase.objects.filter(purchase_date__range=(start, end)),
            'cafe_sales': CafeteriaSale.objects.filter(sale_date__range=(start, end)).select_related('item'),
            'low_stock_items': [item for item in CafeteriaItem.objects.all() if item.is_low_stock],
        })

    elif report_type == 'deposits':
        deposit_academies = Academy.objects.all().order_by('sport_activity', 'name')
        context.update({
            'deposit_academies': deposit_academies,
            'security_deposit_total': sum(a.security_deposit for a in deposit_academies),
        })

    elif report_type == 'shareholders':
        academies = list(Academy.objects.filter(contract_start_date__lte=end, contract_end_date__gte=start))
        total_counts, active_counts, active_days = _monthly_academy_operation_counts(year, month, academies)
        fixed_income = sum(_academy_month_income_from_counts(a, total_counts, active_counts, active_days) for a in academies if a.subscription_type == 'fixed')
        variable_income = sum(_academy_month_income_from_counts(a, total_counts, active_counts, active_days) for a in academies if a.subscription_type == 'variable')
        daily_booking_income = DailyBooking.objects.filter(booking_date__range=(start, end)).aggregate(total=Sum('total_amount'))['total'] or 0
        total_academy_income = fixed_income + variable_income + daily_booking_income
        founding_expenses = FoundingExpense.objects.filter(expense_date__range=(start, end)).aggregate(total=Sum('amount'))['total'] or 0
        monthly_expenses = MonthlyExpense.objects.filter(expense_month__range=(start, end)).aggregate(total=Sum('amount'))['total'] or 0
        daily_expenses = DailyExpense.objects.filter(expense_date__range=(start, end)).aggregate(total=Sum('amount'))['total'] or 0
        operating_expenses = OperatingExpense.objects.filter(expense_date__range=(start, end)).aggregate(total=Sum('amount'))['total'] or 0
        salaries_total = Employee.objects.aggregate(total=Sum('salary'))['total'] or 0
        cafe_purchase_total = sum(p.total_amount for p in CafeteriaPurchase.objects.filter(purchase_date__range=(start, end)))
        cafe_sales_total = sum(s.total_amount for s in CafeteriaSale.objects.filter(sale_date__range=(start, end)).select_related('item'))
        cafe_profit = cafe_sales_total - cafe_purchase_total - operating_expenses
        net_profit = total_academy_income + cafe_profit - founding_expenses - monthly_expenses - daily_expenses - operating_expenses - salaries_total
        context.update({
            'net_profit': net_profit,
            'shareholder_rows': [
                {'shareholder': sh, 'profit_share': int(net_profit * sh.share_percentage / 100)}
                for sh in Shareholder.objects.all()
            ],
        })
    return render(request, 'academies/reports.html', context)


@login_required
def settings_home(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    return render(request, 'academies/settings_home.html', {
        'users_count': User.objects.count(),
        'jobs_count': JobTitle.objects.count(),
        'bonus_count': BonusTier.objects.count(),
    })

@login_required
def job_title_list(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    q = request.GET.get('q', '').strip()
    jobs = JobTitle.objects.all()
    if q:
        jobs = jobs.filter(Q(name__icontains=q) | Q(notes__icontains=q))
    return render(request, 'academies/job_title_list.html', {'jobs': jobs, 'q': q})

@login_required
def job_title_create(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    form = JobTitleForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('job_title_list')
    return render(request, 'academies/simple_form.html', {'form': form, 'title': 'إضافة وظيفة متاحة', 'back_url': 'job_title_list'})

@login_required
def job_title_update(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    job = get_object_or_404(JobTitle, pk=pk)
    form = JobTitleForm(request.POST or None, instance=job)
    if form.is_valid():
        form.save()
        Employee.objects.filter(job_title=job.name).update(salary=job.base_salary)
        return redirect('job_title_list')
    return render(request, 'academies/simple_form.html', {'form': form, 'title': 'تعديل وظيفة متاحة', 'back_url': 'job_title_list'})

@login_required
def job_title_delete(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    job = get_object_or_404(JobTitle, pk=pk)
    if request.method == 'POST':
        job.delete()
        return redirect('job_title_list')
    return render(request, 'academies/simple_confirm_delete.html', {'object': job, 'title': 'حذف وظيفة متاحة', 'back_url': 'job_title_list'})

@login_required
def bonus_tier_list(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    tiers = BonusTier.objects.select_related('job_title').all()
    return render(request, 'academies/bonus_tier_list.html', {'tiers': tiers})

@login_required
def bonus_tier_create(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    form = BonusTierForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('bonus_tier_list')
    return render(request, 'academies/simple_form.html', {'form': form, 'title': 'إضافة شريحة بونص', 'back_url': 'bonus_tier_list'})

@login_required
def bonus_tier_update(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    tier = get_object_or_404(BonusTier, pk=pk)
    form = BonusTierForm(request.POST or None, instance=tier)
    if form.is_valid():
        form.save()
        return redirect('bonus_tier_list')
    return render(request, 'academies/simple_form.html', {'form': form, 'title': 'تعديل شريحة بونص', 'back_url': 'bonus_tier_list'})

@login_required
def bonus_tier_delete(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    tier = get_object_or_404(BonusTier, pk=pk)
    if request.method == 'POST':
        tier.delete()
        return redirect('bonus_tier_list')
    return render(request, 'academies/simple_confirm_delete.html', {'object': tier, 'title': 'حذف شريحة بونص', 'back_url': 'bonus_tier_list'})


@login_required
def user_list(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية إدارة المستخدمين.')
        return redirect('dashboard')
    q = request.GET.get('q', '').strip()
    users = User.objects.all().order_by('username')
    if q:
        users = users.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(email__icontains=q))
    for u in users:
        _ensure_user_profile(u)
    return render(request, 'academies/user_list.html', {'users': users, 'q': q})

@login_required
def user_create(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية إدارة المستخدمين.')
        return redirect('dashboard')
    form = EESSUserForm(request.POST or None)
    permission_form = EESSPermissionForm(request.POST or None)
    if form.is_valid() and permission_form.is_valid():
        user = form.save()
        profile = permission_form.save(commit=False)
        profile.user = user
        profile.save()
        messages.success(request, 'تم إضافة المستخدم وتحديد صلاحياته.')
        return redirect('user_list')
    return render(request, 'academies/user_form.html', {'form': form, 'permission_form': permission_form, 'title': 'إضافة مستخدم'})

@login_required
def user_update(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية إدارة المستخدمين.')
        return redirect('dashboard')
    user = get_object_or_404(User, pk=pk)
    profile = _ensure_user_profile(user)
    form = EESSUserUpdateForm(request.POST or None, instance=user)
    permission_form = EESSPermissionForm(request.POST or None, instance=profile)
    if form.is_valid() and permission_form.is_valid():
        form.save()
        permission_form.save()
        messages.success(request, 'تم تعديل المستخدم وصلاحياته.')
        return redirect('user_list')
    return render(request, 'academies/user_form.html', {'form': form, 'permission_form': permission_form, 'title': 'تعديل مستخدم'})

@login_required
def user_delete(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية إدارة المستخدمين.')
        return redirect('dashboard')
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        if user == request.user:
            messages.error(request, 'لا يمكن حذف المستخدم الحالي.')
        else:
            user.delete()
            messages.success(request, 'تم حذف المستخدم.')
        return redirect('user_list')
    return render(request, 'academies/simple_confirm_delete.html', {'object': user, 'title': 'حذف مستخدم', 'back_url': 'user_list'})
