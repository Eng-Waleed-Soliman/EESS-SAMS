from django import forms
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Academy, DailyBooking, Customer, Shareholder, Employee, FoundingExpense, MonthlyExpense, DailyExpense, OperatingExpense, CafeteriaItem, CafeteriaPurchase, CafeteriaSale, UserPermission, AcademyOperationOverride, JobTitle, BonusTier, AppSetting, Branch, Facility, SportActivityMedia, Activity, AcademyMember, AcademyMonthlyRentPayment
from .constants import (
    OPERATION_PLACE_CHOICES, OPERATION_SCREEN_PLACES, TRAINING_DAY_CHOICES,
    TIME_CHOICES, TIME_INDEX, SPORT_ACTIVITY_CHOICES, TRAINING_SLOT_CHOICES,
    SUBSCRIPTION_TYPE_CHOICES, VARIABLE_RENT_TYPE_CHOICES,
)


def split_values(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split(',') if item.strip()]


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


def _slot_index(slot_label):
    if not slot_label:
        return None
    start = slot_label.split(' - ', 1)[0].strip() if ' - ' in slot_label else slot_label
    if start in TIME_INDEX:
        return TIME_INDEX[start]
    start_n = _norm(start)
    for time_label, idx in TIME_INDEX.items():
        if _norm(time_label) == start_n:
            return idx
    return None


def _range_indexes(start_time, end_time):
    start = TIME_INDEX.get(start_time)
    end = TIME_INDEX.get(end_time)
    if start is None or end is None or end <= start:
        return []
    return list(range(start, end))




def _academy_slot_conflicts(academy, booking_date, venue, wanted_slots, selected_day_ar):
    """Return True when the academy still occupies any wanted slot after operation-screen overrides.

    This respects one-day deletions/edits made from شاشة التشغيل. If an academy hour was
    deleted for that date, the hour becomes available for daily bookings. If it was moved,
    conflict is checked against the moved venue/hour, not the original one.
    """
    def effective_conflict(days_text, places_text, hours_text):
        if not _contains_value(days_text, selected_day_ar):
            return False
        for place in split_values(places_text):
            for slot in split_values(hours_text):
                idx = _slot_index(slot)
                if idx is None:
                    continue
                override = AcademyOperationOverride.objects.filter(
                    academy=academy,
                    booking_date=booking_date,
                    original_place=place,
                    original_slot_index=idx,
                ).first()
                if override and override.is_deleted:
                    # This academy hour was cancelled from the operation screen for this date.
                    continue
                final_place = override.new_place if override and override.new_place else place
                final_idx = override.new_slot_index if override and override.new_slot_index is not None else idx
                if _norm(final_place) == _norm(venue) and final_idx in wanted_slots:
                    return True
        return False

    if effective_conflict(academy.training_days, academy.operation_place, academy.training_hours):
        return 'base'
    if academy.has_extra_hours:
        extra_days = academy.extra_training_days or academy.training_days
        if effective_conflict(extra_days, academy.extra_training_place, academy.extra_training_hours):
            return 'extra'
    return ''


class AcademyForm(forms.ModelForm):
    sport_activity = forms.ChoiceField(
        label='النشاط الرياضي',
        choices=[('', 'اختر النشاط الرياضي')] + SPORT_ACTIVITY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    operation_place = forms.MultipleChoiceField(
        label='مكان التدريب',
        choices=OPERATION_PLACE_CHOICES,
        widget=forms.SelectMultiple(attrs={'class': 'form-select multi-select', 'size': '7'}),
        required=True,
    )
    subscription_type = forms.ChoiceField(
        label='نوع الاشتراك الشهري',
        choices=SUBSCRIPTION_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_subscription_type'}),
    )
    variable_rent_type = forms.ChoiceField(
        label='اختيار القيمة المتغيرة',
        choices=[('', 'اختر نوع القيمة')] + VARIABLE_RENT_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select variable-field'}),
    )
    variable_rent_value = forms.IntegerField(
        label='قيمة الإيجار',
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control variable-field', 'step': '1'}),
    )
    training_days = forms.MultipleChoiceField(
        label='أيام التدريب',
        choices=TRAINING_DAY_CHOICES,
        widget=forms.SelectMultiple(attrs={'class': 'form-select multi-select', 'size': '7'}),
        required=False,
    )
    training_hours = forms.MultipleChoiceField(
        label='ساعات التدريب الأساسية',
        choices=TRAINING_SLOT_CHOICES,
        widget=forms.SelectMultiple(attrs={'class': 'form-select multi-select', 'size': '8'}),
        required=False,
    )
    has_extra_hours = forms.BooleanField(
        label='إضافة ساعات تدريب إضافية',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_has_extra_hours'}),
    )
    extra_training_days = forms.MultipleChoiceField(
        label='أيام التدريب الإضافية',
        choices=TRAINING_DAY_CHOICES,
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select multi-select', 'size': '6'}),
    )
    extra_training_place = forms.MultipleChoiceField(
        label='مكان التدريب الإضافي',
        choices=OPERATION_PLACE_CHOICES,
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select multi-select', 'size': '6'}),
    )
    extra_training_hours = forms.MultipleChoiceField(
        label='ساعات التدريب الإضافية',
        choices=TRAINING_SLOT_CHOICES,
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select multi-select', 'size': '6'}),
    )

    class Meta:
        model = Academy
        fields = [
            'branch', 'name', 'sport_activity', 'company_name', 'manager_name', 'manager_national_id', 'manager_phone',
            'operation_place', 'contract_start_date', 'contract_end_date', 'subscription_type', 'monthly_subscription',
            'variable_rent_type', 'variable_rent_value', 'eess_share_percentage', 'security_deposit', 'training_days', 'training_hours',
            'has_extra_hours', 'extra_training_days', 'extra_training_place', 'extra_training_hours', 'notes'
        ]
        widgets = {
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'contract_start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'contract_end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'monthly_subscription': forms.NumberInput(attrs={'class': 'form-control fixed-field', 'step': '1'}),
            'eess_share_percentage': forms.NumberInput(attrs={'class': 'form-control share-field', 'step': '1', 'min': '0', 'max': '100'}),
            'security_deposit': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        activity_names = list(Activity.objects.filter(is_active=True).values_list('name', flat=True).order_by('name'))
        static_names = [value for value, _ in SPORT_ACTIVITY_CHOICES]
        choices = []
        for name in activity_names + static_names:
            if name and name not in [value for value, _ in choices]:
                choices.append((name, name))
        if self.instance and self.instance.pk and self.instance.sport_activity and self.instance.sport_activity not in [value for value, _ in choices]:
            choices.insert(0, (self.instance.sport_activity, self.instance.sport_activity))
        self.fields['sport_activity'].choices = [('', 'اختر النشاط الرياضي')] + choices
        for name, field in self.fields.items():
            css_class = field.widget.attrs.get('class', '')
            if name == 'has_extra_hours':
                continue
            if 'form-control' not in css_class and 'form-select' not in css_class:
                field.widget.attrs['class'] = (css_class + ' form-control').strip()
        if self.instance and self.instance.pk:
            self.fields['operation_place'].initial = split_values(self.instance.operation_place)
            self.fields['training_days'].initial = split_values(self.instance.training_days)
            self.fields['training_hours'].initial = split_values(self.instance.training_hours)
            self.fields['extra_training_days'].initial = split_values(getattr(self.instance, 'extra_training_days', ''))
            self.fields['extra_training_place'].initial = split_values(self.instance.extra_training_place)
            self.fields['extra_training_hours'].initial = split_values(self.instance.extra_training_hours)
            self.fields['has_extra_hours'].initial = bool(self.instance.has_extra_hours)

    def clean(self):
        cleaned_data = super().clean()
        subscription_type = cleaned_data.get('subscription_type')
        variable_rent_type = cleaned_data.get('variable_rent_type')
        variable_rent_value = cleaned_data.get('variable_rent_value')
        if subscription_type == 'variable' and (not variable_rent_type or variable_rent_value in (None, '')):
            raise forms.ValidationError('عند اختيار قيمة متغيرة يجب اختيار نوع القيمة وإدخال قيمة الإيجار.')
        if cleaned_data.get('has_extra_hours'):
            if not cleaned_data.get('extra_training_place'):
                raise forms.ValidationError('اختر مكان التدريب الإضافي.')
            if not cleaned_data.get('extra_training_hours'):
                raise forms.ValidationError('اختر ساعات التدريب الإضافية.')
            if not cleaned_data.get('extra_training_days'):
                cleaned_data['extra_training_days'] = cleaned_data.get('training_days') or []
        return cleaned_data

    def save(self, commit=True):
        academy = super().save(commit=False)
        academy.operation_place = ', '.join(self.cleaned_data.get('operation_place', []))
        academy.training_days = ', '.join(self.cleaned_data.get('training_days', []))
        academy.training_hours = ', '.join(self.cleaned_data.get('training_hours', []))
        academy.has_extra_hours = bool(self.cleaned_data.get('has_extra_hours'))
        if academy.has_extra_hours:
            academy.extra_training_days = ', '.join(self.cleaned_data.get('extra_training_days', []))
            academy.extra_training_place = ', '.join(self.cleaned_data.get('extra_training_place', []))
            academy.extra_training_hours = ', '.join(self.cleaned_data.get('extra_training_hours', []))
        else:
            academy.extra_training_days = ''
            academy.extra_training_place = ''
            academy.extra_training_hours = ''
        if academy.subscription_type == 'fixed':
            academy.variable_rent_type = ''
            academy.variable_rent_value = 0
            academy.eess_share_percentage = 0
        if academy.subscription_type == 'variable':
            academy.eess_share_percentage = 0
        if academy.subscription_type == 'revenue_share':
            academy.monthly_subscription = 0
            academy.variable_rent_type = ''
            academy.variable_rent_value = 0
        if commit:
            academy.save()
        return academy


class ActivityForm(forms.ModelForm):
    training_places = forms.MultipleChoiceField(
        label='أماكن التدريب المتاحة',
        choices=OPERATION_PLACE_CHOICES,
        widget=forms.SelectMultiple(attrs={'class': 'form-select multi-select', 'size': '7'}),
        required=False,
    )

    class Meta:
        model = Activity
        fields = ['name', 'training_places', 'income_type', 'eess_share_percentage', 'is_active', 'notes']
        widgets = {
            'income_type': forms.Select(attrs={'class': 'form-select'}),
            'eess_share_percentage': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '100'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['training_places'].initial = split_values(self.instance.training_places)
        for name, field in self.fields.items():
            if name == 'is_active':
                continue
            css = field.widget.attrs.get('class', '')
            if field.widget.__class__.__name__ == 'Select':
                field.widget.attrs['class'] = 'form-select'
            elif 'form-control' not in css and 'form-select' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()

    def save(self, commit=True):
        activity = super().save(commit=False)
        activity.training_places = ', '.join(self.cleaned_data.get('training_places', []))
        if activity.income_type != Activity.INCOME_REVENUE_SHARE:
            activity.eess_share_percentage = 0
        if commit:
            activity.save()
        return activity


class AcademyMemberForm(forms.ModelForm):
    class Meta:
        model = AcademyMember
        fields = ['role', 'name', 'phone', 'national_id', 'monthly_subscription', 'is_active', 'notes']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
            'monthly_subscription': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '1'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == 'is_active':
                continue
            css = field.widget.attrs.get('class', '')
            if field.widget.__class__.__name__ == 'Select':
                field.widget.attrs['class'] = 'form-select'
            elif 'form-control' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()


class AppSettingForm(forms.ModelForm):
    class Meta:
        model = AppSetting
        fields = ['program_name', 'company_name', 'company_logo', 'main_screen_image']
        widgets = {
            'program_name': forms.TextInput(attrs={'class': 'form-control'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ['name', 'location', 'logo', 'image', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()


class FacilityForm(forms.ModelForm):
    class Meta:
        model = Facility
        fields = ['branch', 'name', 'facility_type', 'image', 'notes']
        widgets = {
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'facility_type': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            if field.widget.__class__.__name__ == 'Select':
                field.widget.attrs['class'] = 'form-select'
            elif 'form-control' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()


class SportActivityMediaForm(forms.ModelForm):
    class Meta:
        model = SportActivityMedia
        fields = ['name', 'image', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == 'is_active':
                continue
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()


class AcademyMonthlyRentPaymentForm(forms.ModelForm):
    class Meta:
        model = AcademyMonthlyRentPayment
        fields = ['paid_amount', 'payment_date', 'supplied_amount', 'supplied_date', 'notes']
        widgets = {
            'paid_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
            'payment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'supplied_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
            'supplied_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.TextInput(attrs={'class': 'form-control'}),
        }


class DailyBookingForm(forms.ModelForm):
    customer_code = forms.CharField(
        label='كود العميل',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_customer_code', 'placeholder': 'يتم إنشاؤه تلقائيًا أو اكتب كود عميل سابق'}),
    )
    booking_dates = forms.CharField(
        label='تواريخ الحجز',
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_booking_dates'}),
    )
    booking_date_times = forms.CharField(
        label='توقيتات التواريخ',
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_booking_date_times'}),
    )
    venue = forms.ChoiceField(
        label='مكان الحجز',
        choices=[('', 'اختر مكان الحجز')] + [(x, x) for x in OPERATION_SCREEN_PLACES],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    start_time = forms.ChoiceField(
        label='من الساعة',
        required=False,
        choices=[('', 'اختر الساعة')] + TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    end_time = forms.ChoiceField(
        label='إلى الساعة',
        required=False,
        choices=[('', 'اختر الساعة')] + TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = DailyBooking
        fields = ['customer_code', 'customer_name', 'customer_phone', 'national_id', 'players_count', 'amount', 'advance_payment', 'total_amount', 'remaining_amount', 'venue', 'booking_date', 'booking_dates', 'booking_date_times', 'start_time', 'end_time', 'notes']
        widgets = {
            'booking_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'id': 'id_booking_date'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control calc-field', 'readonly': 'readonly', 'style': 'background:#fff3cd;border:2px solid #ffc107;font-weight:bold;'}),
            'remaining_amount': forms.NumberInput(attrs={'class': 'form-control calc-field', 'readonly': 'readonly', 'style': 'background:#fff3cd;border:2px solid #ffc107;font-weight:bold;'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css_class = field.widget.attrs.get('class', '')
            if 'form-control' not in css_class and 'form-select' not in css_class and field.widget.__class__.__name__ != 'HiddenInput':
                field.widget.attrs['class'] = (css_class + ' form-control').strip()
        if self.instance and self.instance.pk:
            self.fields['booking_dates'].initial = self.instance.booking_date.isoformat()
            self.fields['booking_date_times'].initial = f'{self.instance.booking_date.isoformat()}|{self.instance.start_time}|{self.instance.end_time}'

    def _selected_dates(self, cleaned_data):
        from datetime import date as date_class
        dates_text = cleaned_data.get('booking_dates') or ''
        selected_dates = []
        for part in str(dates_text).split(','):
            part = part.strip()
            if not part:
                continue
            try:
                selected_dates.append(date_class.fromisoformat(part))
            except Exception:
                pass
        if cleaned_data.get('booking_date') and cleaned_data.get('booking_date') not in selected_dates:
            selected_dates.append(cleaned_data.get('booking_date'))
        # حذف التكرارات مع الحفاظ على الترتيب
        unique_dates = []
        for d in selected_dates:
            if d not in unique_dates:
                unique_dates.append(d)
        return unique_dates

    def _selected_date_times(self, cleaned_data):
        """يرجع قائمة من (التاريخ، من، إلى). عند تاريخ واحد يستخدم توقيت الشاشة الرئيسي، وعند أكثر من تاريخ يستخدم توقيت كل تاريخ."""
        import json
        selected_dates = self._selected_dates(cleaned_data)
        main_start = cleaned_data.get('start_time')
        main_end = cleaned_data.get('end_time')
        raw = cleaned_data.get('booking_date_times') or ''
        parsed = []
        if raw:
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = []
        by_date = {}
        for item in parsed:
            if not isinstance(item, dict):
                continue
            d = str(item.get('date') or '').strip()
            if d:
                by_date[d] = (item.get('start_time') or main_start, item.get('end_time') or main_end)
        result = []
        for d in selected_dates:
            key = d.isoformat()
            start, end = by_date.get(key, (main_start, main_end))
            result.append((d, start, end))
        return result

    def _hours_count(self, start_time, end_time):
        try:
            start_idx = TIME_INDEX.get(start_time, 0)
            end_idx = TIME_INDEX.get(end_time, 0)
            return max(0, end_idx - start_idx)
        except Exception:
            return 0

    def clean(self):
        cleaned_data = super().clean()
        venue = cleaned_data.get('venue')
        selected_dates = self._selected_dates(cleaned_data)
        selected_date_times = self._selected_date_times(cleaned_data)
        if selected_dates:
            cleaned_data['booking_date'] = selected_dates[0]
        if not selected_dates:
            raise forms.ValidationError('اختر تاريخًا واحدًا على الأقل للحجز.')
        for booking_date, st, et in selected_date_times:
            if not st or not et:
                raise forms.ValidationError(f'اختر توقيت الحجز ليوم {booking_date}.')
            if TIME_INDEX.get(et, 0) <= TIME_INDEX.get(st, 0):
                raise forms.ValidationError(f'ساعة النهاية يجب أن تكون بعد ساعة البداية ليوم {booking_date}.')

        hourly_rate = cleaned_data.get('amount') or 0
        advance = cleaned_data.get('advance_payment') or 0
        total_hours = sum(self._hours_count(st, et) for _, st, et in selected_date_times)
        cleaned_data['total_amount'] = int(hourly_rate) * int(total_hours)
        cleaned_data['remaining_amount'] = max(0, cleaned_data['total_amount'] - int(advance))

        if venue and selected_date_times:
            conflict_messages = []
            from .constants import WEEKDAY_AR
            for booking_date, st, et in selected_date_times:
                wanted_slots = set(_range_indexes(st, et))
                daily_bookings = DailyBooking.objects.filter(venue=venue, booking_date=booking_date)
                if self.instance and self.instance.pk:
                    daily_bookings = daily_bookings.exclude(pk=self.instance.pk)
                for booking in daily_bookings:
                    booking_slots = set(_range_indexes(booking.start_time, booking.end_time))
                    if wanted_slots & booking_slots:
                        conflict_messages.append(f'{booking_date}: محجوز مسبقًا كحجز يومي باسم: {booking.customer_name}.')

                selected_day_ar = WEEKDAY_AR[booking_date.weekday()]
                academies = Academy.objects.filter(contract_start_date__lte=booking_date, contract_end_date__gte=booking_date)
                for academy in academies:
                    conflict_type = _academy_slot_conflicts(academy, booking_date, venue, wanted_slots, selected_day_ar)
                    if conflict_type == 'base':
                        conflict_messages.append(f'{booking_date}: التوقيت محجوز لأكاديمية: {academy.name}.')
                    elif conflict_type == 'extra':
                        conflict_messages.append(f'{booking_date}: التوقيت محجوز كساعات إضافية لأكاديمية: {academy.name}.')
            if conflict_messages:
                raise forms.ValidationError(' لا يمكن تسجيل الحجز: ' + ' '.join(dict.fromkeys(conflict_messages)))
        return cleaned_data

    def save(self, commit=True):
        booking = super().save(commit=False)
        code = (self.cleaned_data.get('customer_code') or '').strip()
        phone = (self.cleaned_data.get('customer_phone') or '').strip()
        name = (self.cleaned_data.get('customer_name') or '').strip()
        national_id = (self.cleaned_data.get('national_id') or '').strip()
        customer = None
        if phone:
            customer = Customer.objects.filter(customer_phone=phone).first()
        if not customer and code:
            customer = Customer.objects.filter(customer_code=code).first()
        if not customer:
            customer = Customer(customer_code=code or Customer.next_code(), customer_phone=phone)
        customer.customer_name = name
        customer.customer_phone = phone
        customer.national_id = national_id
        if commit:
            customer.save()
        booking.customer_code = customer.customer_code
        booking.total_amount = self.cleaned_data.get('total_amount') or booking.total_amount or 0
        booking.remaining_amount = self.cleaned_data.get('remaining_amount') or 0
        if commit:
            booking.save()
        return booking

    def save_all(self):
        # حفظ حجز واحد عند التعديل، أو حفظ عدة حجوزات عند الإضافة من نفس الشاشة.
        is_update = bool(self.instance and self.instance.pk)
        selected_date_times = self._selected_date_times(self.cleaned_data)
        first_booking = self.save(commit=True)
        # تأكد أن الحجز الأول يأخذ توقيت أول تاريخ والقيمة المحسوبة لهذا اليوم.
        if selected_date_times:
            first_date, first_start, first_end = selected_date_times[0]
            first_hours = self._hours_count(first_start, first_end)
            first_booking.booking_date = first_date
            first_booking.start_time = first_start
            first_booking.end_time = first_end
            first_booking.total_amount = int(first_booking.amount or 0) * int(first_hours)
            first_booking.remaining_amount = max(0, int(first_booking.total_amount or 0) - int(first_booking.advance_payment or 0))
            first_booking.save()
        if is_update:
            return [first_booking]
        created = [first_booking]
        for booking_date, start_time, end_time in selected_date_times[1:]:
            hours_count = self._hours_count(start_time, end_time)
            total_amount = int(first_booking.amount or 0) * int(hours_count)
            clone = DailyBooking.objects.create(
                customer_code=first_booking.customer_code,
                customer_name=first_booking.customer_name,
                customer_phone=first_booking.customer_phone,
                national_id=first_booking.national_id,
                players_count=first_booking.players_count,
                amount=first_booking.amount,
                advance_payment=0,
                total_amount=total_amount,
                remaining_amount=total_amount,
                venue=first_booking.venue,
                booking_date=booking_date,
                start_time=start_time,
                end_time=end_time,
                notes=first_booking.notes,
            )
            created.append(clone)
        return created


class ShareholderForm(forms.ModelForm):
    class Meta:
        model = Shareholder
        fields = ['name', 'national_id', 'phone', 'email', 'share_percentage', 'address', 'notes']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'share_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css and 'form-select' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()


class EmployeeForm(forms.ModelForm):
    job_title = forms.ChoiceField(label='الوظيفة', required=False, choices=[], widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_job_title'}))

    class Meta:
        model = Employee
        fields = ['name', 'national_id', 'phone', 'email', 'job_title', 'salary', 'hire_date', 'address', 'notes']
        widgets = {
            'hire_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'salary': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0', 'id': 'id_salary'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        jobs = list(JobTitle.objects.all())
        self.fields['job_title'].choices = [('', 'اختر من الوظائف المسجلة')] + [(job.name, f'{job.name} - أساسي المرتب {job.base_salary}') for job in jobs]
        self.fields['name'].required = True
        self.fields['salary'].required = False
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css and 'form-select' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()

    def clean(self):
        cleaned = super().clean()
        job_name = cleaned.get('job_title')
        salary = cleaned.get('salary')
        if job_name and (salary is None or salary == 0):
            job = JobTitle.objects.filter(name=job_name).first()
            if job:
                cleaned['salary'] = job.base_salary
        return cleaned



class JobTitleForm(forms.ModelForm):
    class Meta:
        model = JobTitle
        fields = ['name', 'base_salary', 'notes']
        labels = {'name': 'اسم الوظيفة', 'base_salary': 'أساسي المرتب', 'notes': 'ملاحظات'}
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'base_salary': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }


class BonusTierForm(forms.ModelForm):
    class Meta:
        model = BonusTier
        fields = ['job_title', 'source_type', 'from_amount', 'to_amount', 'bonus_amount', 'notes']
        widgets = {
            'job_title': forms.Select(attrs={'class': 'form-select'}),
            'source_type': forms.Select(attrs={'class': 'form-select'}),
            'from_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
            'to_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
            'bonus_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def clean(self):
        cleaned = super().clean()
        from_amount = cleaned.get('from_amount') or 0
        to_amount = cleaned.get('to_amount') or 0
        if to_amount and to_amount < from_amount:
            raise forms.ValidationError('قيمة حتى يجب أن تكون أكبر من أو تساوي قيمة من.')
        return cleaned


class FoundingExpenseForm(forms.ModelForm):
    class Meta:
        model = FoundingExpense
        fields = ['title', 'expense_date', 'amount', 'notes']
        widgets = {
            'expense_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css and 'form-select' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()


class MonthlyExpenseForm(forms.ModelForm):
    class Meta:
        model = MonthlyExpense
        fields = ['title', 'expense_month', 'amount', 'notes']
        widgets = {
            'expense_month': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css and 'form-select' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()


class DailyExpenseForm(forms.ModelForm):
    class Meta:
        model = DailyExpense
        fields = ['title', 'expense_date', 'amount', 'notes']
        widgets = {
            'expense_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css and 'form-select' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()


class OperatingExpenseForm(forms.ModelForm):
    class Meta:
        model = OperatingExpense
        fields = ['title', 'expense_date', 'amount', 'notes']
        widgets = {
            'expense_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css and 'form-select' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()


class CafeteriaItemForm(forms.ModelForm):
    class Meta:
        model = CafeteriaItem
        fields = ['name', 'opening_quantity', 'purchase_price', 'sale_price', 'notes']
        widgets = {
            'opening_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'sale_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css and 'form-select' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()


class CafeteriaPurchaseForm(forms.ModelForm):
    class Meta:
        model = CafeteriaPurchase
        fields = ['item', 'purchase_date', 'quantity', 'unit_price', 'supplier', 'notes']
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css and 'form-select' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()
            if field.widget.__class__.__name__ == 'Select':
                field.widget.attrs['class'] = 'form-select'


class CafeteriaSaleForm(forms.ModelForm):
    class Meta:
        model = CafeteriaSale
        fields = ['item', 'sale_date', 'quantity', 'unit_price', 'notes']
        widgets = {
            'sale_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css and 'form-select' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()
            if field.widget.__class__.__name__ == 'Select':
                field.widget.attrs['class'] = 'form-select'
        self.fields['unit_price'].label = 'سعر بيع الوحدة'

    def clean(self):
        cleaned = super().clean()
        item = cleaned.get('item')
        quantity = cleaned.get('quantity') or 0
        unit_price = cleaned.get('unit_price') or 0
        if item and not unit_price:
            cleaned['unit_price'] = item.sale_price
        if item:
            available = item.stock_quantity
            if self.instance and self.instance.pk and self.instance.item_id == item.id:
                available += self.instance.quantity or 0
            if quantity > available:
                raise forms.ValidationError(f'الكمية المطلوبة غير متاحة. المخزون الحالي للصنف {item.name} هو {available} فقط.')
        return cleaned

    def _selected_date_times(self, cleaned_data):
        """يرجع قائمة من (التاريخ، من، إلى). عند تاريخ واحد يستخدم توقيت الشاشة الرئيسي، وعند أكثر من تاريخ يستخدم توقيت كل تاريخ."""
        import json
        selected_dates = self._selected_dates(cleaned_data)
        main_start = cleaned_data.get('start_time')
        main_end = cleaned_data.get('end_time')
        raw = cleaned_data.get('booking_date_times') or ''
        parsed = []
        if raw:
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = []
        by_date = {}
        for item in parsed:
            if not isinstance(item, dict):
                continue
            d = str(item.get('date') or '').strip()
            if d:
                by_date[d] = (item.get('start_time') or main_start, item.get('end_time') or main_end)
        result = []
        for d in selected_dates:
            key = d.isoformat()
            start, end = by_date.get(key, (main_start, main_end))
            result.append((d, start, end))
        return result

    def _hours_count(self, start_time, end_time):
        try:
            start_idx = TIME_INDEX.get(start_time, 0)
            end_idx = TIME_INDEX.get(end_time, 0)
            return max(0, end_idx - start_idx)
        except Exception:
            return 0

    def clean(self):
        cleaned_data = super().clean()
        item = cleaned_data.get('item')
        quantity = cleaned_data.get('quantity') or 0
        if item and self.instance and self.instance.pk and self.instance.item_id == item.id:
            available = item.stock_quantity + self.instance.quantity
        else:
            available = item.stock_quantity if item else 0
        if item and quantity > available:
            raise forms.ValidationError(f'الكمية المطلوبة للبيع أكبر من المخزون المتاح. المتاح حاليًا: {available}')
        return cleaned_data




def _employee_name_choices(current_name=None):
    choices = [('', 'اختر من الموظفين المسجلين')]
    employee_names = list(Employee.objects.values_list('name', flat=True).order_by('name'))
    if current_name and current_name not in employee_names:
        choices.append((current_name, current_name))
    choices.extend([(name, name) for name in employee_names])
    return choices

def _job_title_username_choices(current_username=None):
    choices = [('', 'اختر من الوظائف المسجلة')]
    job_names = list(JobTitle.objects.values_list('name', flat=True).order_by('name'))
    if current_username and current_username not in job_names:
        choices.append((current_username, current_username))
    choices.extend([(name, name) for name in job_names])
    return choices


class EESSUserForm(UserCreationForm):
    username = forms.ChoiceField(
        label='اسم المستخدم',
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='اختر اسم المستخدم من الوظائف المسجلة في الإعدادات.'
    )
    first_name = forms.CharField(label='الاسم', required=False, widget=forms.TextInput(attrs={'class':'form-control'}))
    email = forms.EmailField(label='البريد الإلكتروني', required=False, widget=forms.EmailInput(attrs={'class':'form-control'}))
    is_active = forms.BooleanField(label='مستخدم فعال', required=False, initial=True, widget=forms.CheckboxInput(attrs={'class':'form-check-input'}))

    class Meta:
        model = User
        fields = ['username', 'first_name', 'email', 'password1', 'password2', 'is_active']
        labels = {'username': 'اسم المستخدم'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].choices = _job_title_username_choices()
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            if field.widget.__class__.__name__ == 'Select':
                field.widget.attrs['class'] = 'form-select'
            elif field.widget.__class__.__name__ != 'CheckboxInput' and 'form-control' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()


class EESSUserUpdateForm(forms.ModelForm):
    username = forms.ChoiceField(
        label='اسم المستخدم',
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='اختر اسم المستخدم من الوظائف المسجلة في الإعدادات.'
    )
    new_password = forms.CharField(
        label='كلمة مرور جديدة',
        required=False,
        widget=forms.PasswordInput(attrs={'class':'form-control', 'placeholder':'اتركها فارغة للاحتفاظ بكلمة المرور الحالية'}),
        help_text='لا يمكن عرض كلمة المرور الحالية لأنها محفوظة بشكل مشفر. اكتب كلمة جديدة فقط إذا أردت تغييرها.'
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'email', 'is_active']
        labels = {'username': 'اسم المستخدم', 'first_name': 'الاسم', 'email': 'البريد الإلكتروني', 'is_active': 'مستخدم فعال'}
        widgets = {
            'first_name': forms.TextInput(attrs={'class':'form-control'}),
            'email': forms.EmailInput(attrs={'class':'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class':'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_username = self.instance.username if self.instance and self.instance.pk else None
        self.fields['username'].choices = _job_title_username_choices(current_username)

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('new_password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


PERMISSION_MODULE_FIELDS = [
    'can_academies', 'can_daily_booking', 'can_operation', 'can_shareholders',
    'can_employees', 'can_general_expenses', 'can_cafeteria', 'can_users'
]
PERMISSION_REPORT_FIELDS = [
    'can_reports', 'can_report_income', 'can_report_shareholders', 'can_report_employees',
    'can_report_payroll', 'can_report_expenses', 'can_report_cafeteria', 'can_report_deposits'
]


class EESSPermissionForm(forms.ModelForm):
    MODULE_FIELDS = PERMISSION_MODULE_FIELDS
    REPORT_FIELDS = PERMISSION_REPORT_FIELDS

    class Meta:
        model = UserPermission
        exclude = ['user']
        labels = {'job_title': 'المسمى الوظيفي'}
        widgets = {
            'job_title': forms.Select(attrs={'class': 'form-select'}),
            **{name: forms.CheckboxInput(attrs={'class':'form-check-input'}) for name in PERMISSION_MODULE_FIELDS + PERMISSION_REPORT_FIELDS}
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'job_title' in self.fields:
            self.fields['job_title'].queryset = JobTitle.objects.all()
            self.fields['job_title'].empty_label = 'اختر من الوظائف المسجلة'
