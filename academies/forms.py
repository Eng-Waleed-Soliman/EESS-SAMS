import json
from decimal import Decimal
from django import forms
from django.db.models import Q
from django.core.files.uploadedfile import UploadedFile
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Academy, DailyBooking, Customer, Shareholder, Employee, FoundingExpense, MonthlyExpense, DailyExpense, OperatingExpense, CafeteriaCategory, CafeteriaItem, CafeteriaPurchase, CafeteriaSale, UserPermission, AcademyOperationOverride, JobTitle, BonusTier, AppSetting, WebsiteSetting, Branch, Facility, SportActivityMedia, Activity, AcademyMember, AcademyMonthlyRentPayment, AcademyDepositPlan, DailyIncomeSupply, FinancialVoucher
from .constants import (
    OPERATION_PLACE_CHOICES, OPERATION_SCREEN_PLACES, TRAINING_DAY_CHOICES,
    TIME_CHOICES, TIME_INDEX, SPORT_ACTIVITY_CHOICES, TRAINING_SLOT_CHOICES,
    SUBSCRIPTION_TYPE_CHOICES, VARIABLE_RENT_TYPE_CHOICES, WEEKDAY_AR,
)


def split_values(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split(',') if item.strip()]


def _store_uploaded_image(instance, upload, field_prefix):
    # On an edit form Django returns the existing FieldFile when the user did
    # not choose a replacement.  That old path may no longer exist on Render's
    # ephemeral disk, while the durable bytes are safely stored in Neon.
    # Only touch the binary columns for a genuinely new browser upload.
    if not isinstance(upload, UploadedFile):
        return
    upload.seek(0)
    setattr(instance, f'{field_prefix}_data', upload.read())
    setattr(instance, f'{field_prefix}_content_type', getattr(upload, 'content_type', '') or 'image/jpeg')
    setattr(instance, f'{field_prefix}_name', upload.name)
    upload.seek(0)


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


def _time_ranges_overlap(first_start, first_end, second_start, second_end):
    """Use half-open ranges so touching bookings are not treated as overlapping."""
    first_start_idx = TIME_INDEX.get(first_start)
    first_end_idx = TIME_INDEX.get(first_end)
    second_start_idx = TIME_INDEX.get(second_start)
    second_end_idx = TIME_INDEX.get(second_end)
    if None in (first_start_idx, first_end_idx, second_start_idx, second_end_idx):
        return False
    return first_start_idx < second_end_idx and second_start_idx < first_end_idx


def _slot_labels_from_range(start_time, end_time):
    return [
        f'{TIME_CHOICES[idx][0]} - {TIME_CHOICES[idx + 1][0]}'
        for idx in _range_indexes(start_time, end_time)
        if 0 <= idx < len(TIME_CHOICES) - 1
    ]


def _format_conflict_slots(indexes):
    labels = []
    for idx in sorted(set(indexes)):
        if 0 <= idx < len(TIME_CHOICES) - 1:
            labels.append(f'{TIME_CHOICES[idx][0]} - {TIME_CHOICES[idx + 1][0]}')
    return '، '.join(labels) if labels else 'غير محدد'


def _schedule_entries(name, places, days, hours, source_label):
    entries = []
    slot_indexes = []
    for slot in hours:
        idx = _slot_index(slot)
        if idx is not None:
            slot_indexes.append(idx)
    for place in places:
        for day in days:
            entries.append({
                'name': name,
                'place': place,
                'day': day,
                'slots': set(slot_indexes),
                'source': source_label,
            })
    return entries


def _entries_from_detailed_schedule(schedule_rows, academy_name, subscription_type, selected_places=None):
    entries = []
    if subscription_type == 'fixed':
        all_days = [value for value, _ in TRAINING_DAY_CHOICES]
        all_slots = set(range(len(TIME_CHOICES) - 1))
        for place in selected_places or []:
            for day in all_days:
                entries.append({'name': academy_name, 'place': place, 'day': day, 'slots': all_slots, 'source': 'إيجار ثابت'})
        return entries
    for row in schedule_rows or []:
        place = row.get('place')
        day = row.get('day')
        slots = set(_range_indexes(row.get('start_time'), row.get('end_time')))
        if place and day and slots:
            entries.append({'name': academy_name, 'place': place, 'day': day, 'slots': slots, 'source': 'جدول تفصيلي'})
    return entries


def _academy_schedule_conflict_messages(cleaned_data, instance=None):
    schedule_rows = cleaned_data.get('parsed_training_schedule') or []
    subscription_type = cleaned_data.get('subscription_type')
    places = cleaned_data.get('operation_place') or []
    days = cleaned_data.get('training_days') or []
    hours = cleaned_data.get('training_hours') or []
    start_date = cleaned_data.get('contract_start_date')
    end_date = cleaned_data.get('contract_end_date')
    if not start_date or not end_date:
        return []

    academy_name = cleaned_data.get('name') or 'الأكاديمية الجديدة'
    wanted_entries = _entries_from_detailed_schedule(schedule_rows, academy_name, subscription_type, places)
    if not wanted_entries and places and days and hours:
        wanted_entries = _schedule_entries(academy_name, places, days, hours, 'التدريب الأساسي')
        if cleaned_data.get('has_extra_hours'):
            extra_days = cleaned_data.get('extra_training_days') or days
            wanted_entries.extend(_schedule_entries(
                academy_name,
                cleaned_data.get('extra_training_place') or [],
                extra_days,
                cleaned_data.get('extra_training_hours') or [],
                'التدريب الإضافي',
            ))
    if not wanted_entries:
        return []

    messages = []
    existing_academies = Academy.objects.filter(contract_start_date__lte=end_date, contract_end_date__gte=start_date)
    if instance and instance.pk:
        existing_academies = existing_academies.exclude(pk=instance.pk)
    for academy in existing_academies:
        existing_entries = _entries_from_detailed_schedule(
            academy.training_schedule,
            academy.name,
            academy.subscription_type,
            academy.operation_places_list,
        )
        if not existing_entries:
            existing_entries = _schedule_entries(
                academy.name,
                academy.operation_places_list,
                academy.training_days_list,
                academy.training_hours_list,
                'التدريب الأساسي',
            )
            if academy.has_extra_hours:
                existing_entries.extend(_schedule_entries(
                    academy.name,
                    split_values(academy.extra_training_place),
                    split_values(academy.extra_training_days) or academy.training_days_list,
                    academy.extra_training_hours_list,
                    'التدريب الإضافي',
                ))
        for wanted in wanted_entries:
            for existing in existing_entries:
                overlap = wanted['slots'] & existing['slots']
                if _norm(wanted['place']) == _norm(existing['place']) and wanted['day'] == existing['day'] and overlap:
                    messages.append(
                        f"يوجد تداخل مع أكاديمية {academy.name}: المكان {wanted['place']}، اليوم {wanted['day']}، "
                        f"الساعات {_format_conflict_slots(overlap)} ({existing['source']})."
                    )

    bookings = DailyBooking.objects.filter(booking_date__range=(start_date, end_date))
    for booking in bookings:
        day_ar = WEEKDAY_AR.get(booking.booking_date.weekday(), '')
        booking_slots = set(_range_indexes(booking.start_time, booking.end_time))
        if not booking_slots:
            continue
        for wanted in wanted_entries:
            overlap = wanted['slots'] & booking_slots
            if _norm(wanted['place']) == _norm(booking.venue) and wanted['day'] == day_ar and overlap:
                messages.append(
                    f"يوجد تداخل مع حجز يومي باسم {booking.customer_name}: التاريخ {booking.booking_date}، "
                    f"المكان {booking.venue}، اليوم {day_ar}، الساعات {_format_conflict_slots(overlap)}."
                )
    return list(dict.fromkeys(messages))




def _academy_slot_conflicts(academy, booking_date, venue, wanted_start, wanted_end, selected_day_ar):
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
                wanted_slots = set(_range_indexes(wanted_start, wanted_end))
                if _norm(final_place) == _norm(venue) and final_idx in wanted_slots:
                    return True
        return False

    if academy.subscription_type == 'fixed' and any(
        _norm(place) == _norm(venue) for place in academy.operation_places_list
    ):
        return 'base'
    for row in academy.training_schedule or []:
        if (
            row.get('day') == selected_day_ar
            and _norm(row.get('place')) == _norm(venue)
            and _time_ranges_overlap(wanted_start, wanted_end, row.get('start_time'), row.get('end_time'))
        ):
            return 'base'

    if effective_conflict(academy.training_days, academy.operation_place, academy.training_hours):
        return 'base'
    if academy.has_extra_hours:
        extra_days = academy.extra_training_days or academy.training_days
        if effective_conflict(extra_days, academy.extra_training_place, academy.extra_training_hours):
            return 'extra'
    return ''


class AcademyForm(forms.ModelForm):
    branch = forms.ModelChoiceField(
        label='فرع التعاقد',
        queryset=Branch.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    logo = forms.FileField(
        label='لوجو الأكاديمية',
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/jpeg,image/png,image/webp,image/gif',
        }),
    )
    training_schedule_data = forms.CharField(required=False, widget=forms.HiddenInput(attrs={'id': 'id_training_schedule_data'}))
    sport_activity = forms.ChoiceField(
        label='النشاط الرياضي',
        choices=[('', 'اختر النشاط الرياضي')] + SPORT_ACTIVITY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    operation_place = forms.MultipleChoiceField(
        label='مكان التدريب',
        choices=OPERATION_PLACE_CHOICES,
        widget=forms.SelectMultiple(attrs={'class': 'form-select multi-select', 'size': '7'}),
        required=False,
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
        label='قيمة إيجار افتراضية',
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
            'branch', 'name', 'name_en', 'logo', 'sport_activity', 'sport_activity_en', 'company_name', 'manager_name', 'manager_national_id', 'manager_phone',
            'operation_place', 'contract_start_date', 'contract_end_date', 'subscription_type', 'monthly_subscription',
            'variable_rent_type', 'variable_rent_value', 'eess_share_percentage', 'security_deposit', 'training_days', 'training_hours',
            'has_extra_hours', 'extra_training_days', 'extra_training_place', 'extra_training_hours', 'notes',
            'website_description', 'website_description_en', 'is_published_on_website'
        ]
        widgets = {
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'contract_start_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'contract_end_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'website_description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'website_description_en': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'dir': 'ltr'}),
            'is_published_on_website': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'monthly_subscription': forms.NumberInput(attrs={'class': 'form-control fixed-field', 'step': '1'}),
            'eess_share_percentage': forms.NumberInput(attrs={'class': 'form-control share-field', 'step': '1', 'min': '0', 'max': '100'}),
            'security_deposit': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['branch'].queryset = Branch.objects.all().order_by('name')
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
            if name in {'has_extra_hours', 'is_published_on_website'}:
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
            self.fields['training_schedule_data'].initial = json.dumps(self._initial_schedule_rows(), ensure_ascii=False)

    def _initial_schedule_rows(self):
        if self.instance and self.instance.pk and self.instance.training_schedule:
            return self.instance.training_schedule
        rows = []
        for place in split_values(getattr(self.instance, 'operation_place', '')):
            for day in split_values(getattr(self.instance, 'training_days', '')):
                for slot in split_values(getattr(self.instance, 'training_hours', '')):
                    if ' - ' not in slot:
                        continue
                    start_time, end_time = [part.strip() for part in slot.split(' - ', 1)]
                    rows.append({'place': place, 'day': day, 'start_time': start_time, 'end_time': end_time, 'hourly_rent': self.instance.variable_rent_value or 0})
        return rows

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if not logo:
            return logo
        allowed_types = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
        if getattr(logo, 'content_type', '') not in allowed_types:
            raise forms.ValidationError('اختر صورة بصيغة JPG أو PNG أو WEBP أو GIF.')
        if logo.size > 5 * 1024 * 1024:
            raise forms.ValidationError('حجم لوجو الأكاديمية يجب ألا يتجاوز 5 ميجابايت.')
        return logo

    def clean(self):
        cleaned_data = super().clean()
        subscription_type = cleaned_data.get('subscription_type')
        variable_rent_type = cleaned_data.get('variable_rent_type')
        variable_rent_value = cleaned_data.get('variable_rent_value')
        raw_schedule = cleaned_data.get('training_schedule_data') or '[]'
        try:
            parsed_rows = json.loads(raw_schedule)
        except json.JSONDecodeError:
            parsed_rows = []
        parsed_rows = [row for row in parsed_rows if isinstance(row, dict)]
        selected_places = []
        selected_days = []
        selected_hours = []
        normalized_rows = []
        if subscription_type == 'fixed':
            for row in parsed_rows:
                place = row.get('place')
                if place and place not in selected_places:
                    selected_places.append(place)
            if not selected_places:
                selected_places = cleaned_data.get('operation_place') or []
            if not selected_places:
                raise forms.ValidationError('اختر مكان تدريب واحد على الأقل للأكاديمية الثابتة.')
        elif subscription_type == 'variable':
            if not variable_rent_type:
                cleaned_data['variable_rent_type'] = 'hour'
            for row in parsed_rows:
                place = row.get('place')
                day = row.get('day')
                start_time = row.get('start_time')
                end_time = row.get('end_time')
                hourly_rent = row.get('hourly_rent')
                slots = _range_indexes(start_time, end_time)
                try:
                    hourly_rent = max(0, int(hourly_rent or 0))
                except (TypeError, ValueError):
                    hourly_rent = 0
                if not (place and day and slots):
                    continue
                if hourly_rent <= 0:
                    raise forms.ValidationError(f'أدخل قيمة إيجار الساعة للمكان {place} يوم {day}.')
                normalized_rows.append({'place': place, 'day': day, 'start_time': start_time, 'end_time': end_time, 'hourly_rent': hourly_rent})
                if place not in selected_places:
                    selected_places.append(place)
                if day not in selected_days:
                    selected_days.append(day)
                for label in _slot_labels_from_range(start_time, end_time):
                    if label not in selected_hours:
                        selected_hours.append(label)
            if not normalized_rows:
                raise forms.ValidationError('أضف جدول تدريب واحد على الأقل: مكان التدريب، اليوم، من الساعة، إلى الساعة، وقيمة إيجار الساعة.')
        cleaned_data['parsed_training_schedule'] = normalized_rows if subscription_type == 'variable' else [{'place': place} for place in selected_places]
        cleaned_data['operation_place'] = selected_places
        if subscription_type == 'variable':
            cleaned_data['training_days'] = selected_days
            cleaned_data['training_hours'] = selected_hours
            cleaned_data['variable_rent_value'] = variable_rent_value or 0
        if subscription_type == 'fixed':
            cleaned_data['training_days'] = []
            cleaned_data['training_hours'] = []
        if cleaned_data.get('has_extra_hours'):
            if not cleaned_data.get('extra_training_place'):
                raise forms.ValidationError('اختر مكان التدريب الإضافي.')
            if not cleaned_data.get('extra_training_hours'):
                raise forms.ValidationError('اختر ساعات التدريب الإضافية.')
            if not cleaned_data.get('extra_training_days'):
                cleaned_data['extra_training_days'] = cleaned_data.get('training_days') or []
        conflict_messages = _academy_schedule_conflict_messages(cleaned_data, self.instance)
        if conflict_messages:
            raise forms.ValidationError('لا يمكن حفظ الأكاديمية بسبب تداخل في مواعيد التدريب: ' + ' '.join(conflict_messages))
        return cleaned_data

    def save(self, commit=True):
        academy = super().save(commit=False)
        logo = self.cleaned_data.get('logo')
        if logo:
            academy.logo_data = logo.read()
            academy.logo_content_type = getattr(logo, 'content_type', '') or 'image/png'
            academy.logo_name = logo.name
        academy.operation_place = ', '.join(self.cleaned_data.get('operation_place', []))
        academy.training_days = ', '.join(self.cleaned_data.get('training_days', []))
        academy.training_hours = ', '.join(self.cleaned_data.get('training_hours', []))
        academy.training_schedule = self.cleaned_data.get('parsed_training_schedule', [])
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
            if name in {'is_active', 'is_published_on_website'}:
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
    photo = forms.FileField(
        label='إضافة صورة', required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/jpeg,image/png,image/webp,image/gif'}),
    )

    class Meta:
        model = AcademyMember
        fields = ['role', 'name', 'name_en', 'phone', 'national_id', 'job_title', 'job_title_en', 'birth_date', 'monthly_subscription', 'photo', 'is_active', 'notes', 'website_bio', 'website_bio_en', 'is_published_on_website']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
            'birth_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'monthly_subscription': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '1'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'website_bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'website_bio_en': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'dir': 'ltr'}),
            'is_published_on_website': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, fixed_role=None, **kwargs):
        self.fixed_role = fixed_role
        super().__init__(*args, **kwargs)
        if self.fixed_role in dict(AcademyMember.ROLE_CHOICES):
            self.fields.pop('role', None)
        elif self.fixed_role == 'staff':
            self.fields['role'].label = 'النوع'
            self.fields['role'].choices = [
                (AcademyMember.ROLE_COACH, 'مدرب'),
                (AcademyMember.ROLE_ADMIN, 'إداري'),
            ]
        effective_role = (
            self.instance.role
            if self.fixed_role == 'staff' and self.instance and self.instance.pk
            else self.fixed_role or (self.instance.role if self.instance and self.instance.pk else '')
        )
        if effective_role == AcademyMember.ROLE_PLAYER:
            self.fields.pop('job_title', None)
            self.fields.pop('job_title_en', None)
        else:
            self.fields.pop('birth_date', None)
            self.fields.pop('monthly_subscription', None)
        for name, field in self.fields.items():
            if name in {'is_active', 'is_published_on_website'}:
                continue
            css = field.widget.attrs.get('class', '')
            if field.widget.__class__.__name__ == 'Select':
                field.widget.attrs['class'] = 'form-select'
            elif 'form-control' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if not photo:
            return photo
        allowed_types = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
        if getattr(photo, 'content_type', '') not in allowed_types:
            raise forms.ValidationError('اختر صورة بصيغة JPG أو PNG أو WEBP أو GIF.')
        if photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError('حجم الصورة يجب ألا يتجاوز 5 ميجابايت.')
        return photo

    def save(self, commit=True):
        member = super().save(commit=False)
        if self.fixed_role in dict(AcademyMember.ROLE_CHOICES):
            member.role = self.fixed_role
        if member.role != AcademyMember.ROLE_PLAYER:
            member.monthly_subscription = 0
            member.birth_date = None
        else:
            member.job_title = ''
        photo = self.cleaned_data.get('photo')
        if photo:
            member.photo_data = photo.read()
            member.photo_content_type = getattr(photo, 'content_type', '') or 'image/jpeg'
            member.photo_name = photo.name
        if commit:
            member.save()
        return member


class AppSettingForm(forms.ModelForm):
    class Meta:
        model = AppSetting
        fields = ['program_name', 'company_name', 'company_short_name', 'company_name_ar', 'company_logo', 'main_screen_image']
        widgets = {
            'program_name': forms.TextInput(attrs={'class': 'form-control'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'company_short_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'مثال: EESS'}),
            'company_name_ar': forms.TextInput(attrs={'class': 'form-control'}),
            'company_logo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'main_screen_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == 'is_published_on_website':
                continue
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()
        if self.instance and self.instance.pk:
            if self.instance.company_logo:
                self.fields['company_logo'].help_text = 'لوجو الشركة الحالي محفوظ تلقائيًا. اختر ملفًا فقط إذا أردت استبداله.'
            if self.instance.main_screen_image:
                self.fields['main_screen_image'].help_text = 'الصورة الحالية محفوظة تلقائيًا. اختر ملفًا فقط إذا أردت استبدالها.'

    def save(self, commit=True):
        setting = super().save(commit=False)
        _store_uploaded_image(setting, self.cleaned_data.get('company_logo'), 'company_logo')
        _store_uploaded_image(setting, self.cleaned_data.get('main_screen_image'), 'main_screen_image')
        if commit:
            setting.save()
        return setting


class WebsiteSettingForm(forms.ModelForm):
    class Meta:
        model = WebsiteSetting
        fields = [
            'hero_title_ar', 'hero_title_en', 'hero_text', 'hero_text_en', 'hero_image',
            'about_title', 'about_title_en', 'about_text', 'about_text_en', 'about_image',
            'phone', 'email', 'address', 'address_en', 'whatsapp',
            'facebook_url', 'instagram_url', 'youtube_url',
            'footer_text', 'footer_text_en', 'is_published',
        ]
        widgets = {
            'hero_text': forms.Textarea(attrs={'rows': 4}),
            'hero_text_en': forms.Textarea(attrs={'rows': 4, 'dir': 'ltr'}),
            'about_text': forms.Textarea(attrs={'rows': 6}),
            'about_text_en': forms.Textarea(attrs={'rows': 6, 'dir': 'ltr'}),
            'hero_image': forms.FileInput(attrs={'accept': 'image/*'}),
            'about_image': forms.FileInput(attrs={'accept': 'image/*'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == 'is_published':
                continue
            field.widget.attrs['class'] = 'form-control'
        if self.instance and self.instance.pk:
            if self.instance.hero_image:
                self.fields['hero_image'].help_text = 'الصورة الحالية محفوظة؛ اختر ملفًا فقط لاستبدالها.'
            if self.instance.about_image:
                self.fields['about_image'].help_text = 'الصورة الحالية محفوظة؛ اختر ملفًا فقط لاستبدالها.'

    def save(self, commit=True):
        setting = super().save(commit=False)
        _store_uploaded_image(setting, self.cleaned_data.get('hero_image'), 'hero_image')
        _store_uploaded_image(setting, self.cleaned_data.get('about_image'), 'about_image')
        if commit:
            setting.save()
        return setting


class DailyIncomeSupplyForm(forms.ModelForm):
    class Meta:
        model = DailyIncomeSupply
        fields = ['supply_date', 'amount', 'notes']
        labels = {
            'supply_date': 'تاريخ التوريد',
            'amount': 'المبلغ المورد',
            'notes': 'ملاحظات',
        }
        widgets = {
            'supply_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'min': 1, 'step': 1, 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        }


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ['name', 'name_en', 'short_name', 'location', 'location_en', 'logo', 'image', 'notes', 'website_description', 'website_description_en', 'is_published_on_website']
        widgets = {
            'logo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'website_description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'website_description_en': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'dir': 'ltr'}),
            'is_published_on_website': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == 'is_published_on_website':
                continue
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()
        if self.instance and self.instance.pk:
            if self.instance.logo:
                self.fields['logo'].help_text = 'لوجو الفرع الحالي محفوظ تلقائيًا. اختر ملفًا فقط إذا أردت استبداله.'
            if self.instance.image:
                self.fields['image'].help_text = 'صورة الفرع الحالية محفوظة تلقائيًا. اختر ملفًا فقط إذا أردت استبدالها.'

    def save(self, commit=True):
        branch = super().save(commit=False)
        _store_uploaded_image(branch, self.cleaned_data.get('logo'), 'logo')
        _store_uploaded_image(branch, self.cleaned_data.get('image'), 'image')
        if commit:
            branch.save()
        return branch


class FacilityForm(forms.ModelForm):
    class Meta:
        model = Facility
        fields = ['branch', 'name', 'facility_type', 'hourly_rent', 'daily_rent', 'image', 'notes']
        widgets = {
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'facility_type': forms.Select(attrs={'class': 'form-select'}),
            'hourly_rent': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
            'daily_rent': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
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
    name = forms.ChoiceField(
        label='اسم الرياضة / النشاط',
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = SportActivityMedia
        fields = ['name', 'name_en', 'image', 'description', 'description_en', 'is_active']
        widgets = {
            'name_en': forms.TextInput(attrs={
                'class': 'form-control',
                'dir': 'ltr',
                'placeholder': 'Example: Football',
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg,image/png,image/webp,image/gif',
            }),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'description_en': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'dir': 'ltr'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        activity_names = set(
            Activity.objects.filter(is_active=True)
            .exclude(name='')
            .values_list('name', flat=True)
        )
        activity_names.update(
            Academy.objects.exclude(sport_activity='')
            .values_list('sport_activity', flat=True)
        )
        activity_names.update(
            value for value, _label in SPORT_ACTIVITY_CHOICES if value
        )
        activity_names.update(
            SportActivityMedia.objects.exclude(name='')
            .values_list('name', flat=True)
        )
        if self.instance and self.instance.pk and self.instance.name:
            activity_names.add(self.instance.name)
        selected_name = (
            self.data.get('name')
            if self.is_bound
            else (self.instance.name if self.instance and self.instance.pk else '')
        )
        self.fields['name'].choices = [
            ('', 'اختر الرياضة / النشاط')
        ] + [(name, name) for name in sorted(activity_names)]
        self.fields['name'].initial = selected_name
        self.fields['image'].help_text = (
            'اختر صورة بصيغة JPG أو PNG أو WEBP أو GIF.'
            if not (self.instance and self.instance.pk and self.instance.image)
            else 'الصورة الحالية محفوظة؛ اختر ملفًا فقط إذا أردت استبدالها.'
        )
        for name, field in self.fields.items():
            if name == 'is_active':
                continue
            if name == 'name':
                field.widget.attrs['class'] = 'form-select'
                continue
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        duplicate = SportActivityMedia.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError(
                'تم إنشاء قسم صور لهذه الرياضة / النشاط من قبل؛ استخدم زر تعديل.'
            )
        return name

    def save(self, commit=True):
        item = super().save(commit=False)
        _store_uploaded_image(item, self.cleaned_data.get('image'), 'image')
        if commit:
            item.save()
        return item


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


class AcademyDepositPlanForm(forms.ModelForm):
    first_due_month = forms.DateField(
        label='شهر استحقاق أول قسط',
        input_formats=['%Y-%m', '%Y-%m-%d'],
        widget=forms.DateInput(format='%Y-%m', attrs={'type': 'month', 'class': 'form-control'}),
    )

    class Meta:
        model = AcademyDepositPlan
        fields = ['total_amount', 'installments_count', 'first_due_month', 'notes']
        widgets = {
            'total_amount': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'step': '1'}),
            'installments_count': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '3', 'step': '1'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def clean_installments_count(self):
        count = self.cleaned_data.get('installments_count') or 0
        if count < 1 or count > 3:
            raise forms.ValidationError('عدد أقساط التأمين يجب أن يكون من قسط واحد إلى 3 أقساط فقط.')
        return count

    def clean_total_amount(self):
        amount = self.cleaned_data.get('total_amount') or 0
        if amount <= 0:
            raise forms.ValidationError('أدخل مبلغ تأمين أكبر من صفر.')
        return amount


class FinancialVoucherForm(forms.ModelForm):
    signature_title = forms.ChoiceField(
        label='مسمى وظيفة التوقيع',
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    signature_name = forms.CharField(
        label='اسم الموظف الموقّع',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
    )

    class Meta:
        model = FinancialVoucher
        fields = ['amount', 'statement', 'voucher_date', 'signature_title', 'signature_name']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'step': '1'}),
            'statement': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'voucher_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        titles = set(JobTitle.objects.values_list('name', flat=True))
        titles.update(Employee.objects.exclude(job_title='').values_list('job_title', flat=True))
        current_title = self.instance.signature_title if self.instance and self.instance.pk else ''
        if current_title:
            titles.add(current_title)
        self.fields['signature_title'].choices = [('', 'اختر مسمى وظيفة التوقيع')] + [
            (title, title) for title in sorted(title for title in titles if title)
        ]
        self.employee_names_by_title = {}
        for employee in Employee.objects.exclude(job_title='').order_by('name'):
            self.employee_names_by_title.setdefault(employee.job_title, []).append(employee.name)
        if self.instance and self.instance.pk and self.instance.signature_name:
            self.fields['signature_name'].initial = self.instance.signature_name

    def clean_signature_name(self):
        title = self.cleaned_data.get('signature_title', '')
        submitted_name = (self.cleaned_data.get('signature_name') or '').strip()
        if (
            self.instance and self.instance.pk
            and title == self.instance.signature_title
            and submitted_name == self.instance.signature_name
        ):
            return submitted_name
        employee_names = list(
            Employee.objects.filter(job_title=title).order_by('name').values_list('name', flat=True)
        )
        if submitted_name in employee_names:
            return submitted_name
        return employee_names[0] if employee_names else ''

    def clean_amount(self):
        amount = self.cleaned_data.get('amount') or 0
        if amount <= 0:
            raise forms.ValidationError('قيمة المبلغ يجب أن تكون أكبر من صفر.')
        return amount


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
        self.branch = kwargs.pop('branch', None)
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
            return Decimal(max(0, end_idx - start_idx)) / Decimal(2)
        except Exception:
            return Decimal(0)

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
        cleaned_data['total_amount'] = int(Decimal(hourly_rate) * total_hours)
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
                    conflict_type = _academy_slot_conflicts(academy, booking_date, venue, st, et, selected_day_ar)
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
        if self.branch is not None:
            booking.branch = self.branch
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
            first_booking.total_amount = int(Decimal(first_booking.amount or 0) * first_hours)
            first_booking.remaining_amount = max(0, int(first_booking.total_amount or 0) - int(first_booking.advance_payment or 0))
            first_booking.save()
        if is_update:
            return [first_booking]
        created = [first_booking]
        for booking_date, start_time, end_time in selected_date_times[1:]:
            hours_count = self._hours_count(start_time, end_time)
            total_amount = int(Decimal(first_booking.amount or 0) * hours_count)
            clone = DailyBooking.objects.create(
                branch=first_booking.branch,
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
    photo = forms.FileField(
        label='صورة عضو مجلس الإدارة',
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/jpeg,image/png,image/webp'}),
    )

    class Meta:
        model = Shareholder
        fields = ['name', 'name_en', 'national_id', 'phone', 'email', 'share_percentage', 'address', 'job_title', 'job_title_en', 'photo', 'website_bio', 'website_bio_en', 'is_published_on_website', 'notes']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'website_bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'website_bio_en': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'dir': 'ltr'}),
            'is_published_on_website': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'share_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == 'is_published_on_website':
                continue
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css and 'form-select' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()
        if self.instance and self.instance.pk and self.instance.photo_data:
            self.fields['photo'].help_text = 'الصورة الحالية محفوظة؛ اختر ملفًا فقط لاستبدالها.'

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo and photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError('حجم الصورة يجب ألا يتجاوز 5 ميجابايت.')
        return photo

    def save(self, commit=True):
        shareholder = super().save(commit=False)
        photo = self.cleaned_data.get('photo')
        if photo:
            shareholder.photo_data = photo.read()
            shareholder.photo_content_type = getattr(photo, 'content_type', '') or 'image/jpeg'
            shareholder.photo_name = photo.name
        if commit:
            shareholder.save()
        return shareholder


class EmployeeForm(forms.ModelForm):
    branch = forms.ModelChoiceField(
        label='اسم الفرع',
        queryset=Branch.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    job_title = forms.ChoiceField(label='الوظيفة', required=False, choices=[], widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_job_title'}))

    class Meta:
        model = Employee
        fields = ['branch', 'name', 'national_id', 'phone', 'email', 'job_title', 'salary', 'hire_date', 'address', 'notes']
        widgets = {
            'hire_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'salary': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0', 'id': 'id_salary'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['branch'].queryset = Branch.objects.all().order_by('name')
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


class CafeteriaCategoryForm(forms.ModelForm):
    class Meta:
        model = CafeteriaCategory
        fields = ['code', 'name', 'notes']
        widgets = {
            'code': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '1'}),
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
        fields = ['category', 'code', 'name', 'opening_quantity', 'purchase_price', 'sale_price', 'notes']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'code': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '1'}),
            'opening_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'sale_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
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
        self.fields['item'].queryset = CafeteriaItem.objects.select_related('category').order_by('category__code', 'code', 'name')
        self.fields['item'].label_from_instance = lambda obj: f"{obj.category.code if obj.category_id else '-'} / {obj.code} - {obj.name}"
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
        self.fields['item'].queryset = CafeteriaItem.objects.select_related('category').order_by('category__code', 'code', 'name')
        self.fields['item'].label_from_instance = lambda obj: f"{obj.category.code if obj.category_id else '-'} / {obj.code} - {obj.name}"
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css and 'form-select' not in css:
                field.widget.attrs['class'] = (css + ' form-control').strip()
            if field.widget.__class__.__name__ == 'Select':
                field.widget.attrs['class'] = 'form-select'
        self.fields['unit_price'].label = 'سعر بيع الوحدة'

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
        if item:
            cleaned_data['unit_price'] = item.sale_price
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
        label='تعيين كلمة مرور جديدة',
        required=False,
        widget=forms.PasswordInput(attrs={'class':'form-control', 'placeholder':'اتركها فارغة للاحتفاظ بكلمة المرور الحالية'}),
        help_text='كلمة المرور الحالية مشفّرة ولا يمكن استرجاعها. اكتب كلمة جديدة هنا عند نسيانها، أو اترك الخانة فارغة دون تغيير.'
    )
    confirm_new_password = forms.CharField(
        label='تأكيد كلمة المرور الجديدة',
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'أعد كتابة كلمة المرور الجديدة',
            'autocomplete': 'new-password',
        }),
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

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('new_password')
        confirmation = cleaned_data.get('confirm_new_password')
        if password and not confirmation:
            self.add_error('confirm_new_password', 'يجب تأكيد كلمة المرور الجديدة.')
        elif confirmation and not password:
            self.add_error('new_password', 'اكتب كلمة المرور الجديدة أولًا.')
        elif password and confirmation and password != confirmation:
            self.add_error('confirm_new_password', 'كلمتا المرور غير متطابقتين.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('new_password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


PERMISSION_MODULE_FIELDS = [
    'can_academies', 'can_daily_booking', 'can_daily_income', 'can_academy_rent',
    'can_operation', 'can_security', 'can_shareholders', 'can_employees', 'can_general_expenses',
    'can_accounts', 'can_cafeteria', 'can_reports', 'can_settings'
]
PERMISSION_REPORT_FIELDS = [
    'can_report_income', 'can_report_shareholders', 'can_report_employees',
    'can_report_payroll', 'can_report_expenses', 'can_report_cafeteria', 'can_report_deposits'
]


class EESSPermissionForm(forms.ModelForm):
    MODULE_FIELDS = PERMISSION_MODULE_FIELDS
    REPORT_FIELDS = PERMISSION_REPORT_FIELDS

    class Meta:
        model = UserPermission
        fields = PERMISSION_MODULE_FIELDS + PERMISSION_REPORT_FIELDS
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
        if self.instance and self.instance.pk and not self.is_bound:
            if 'can_daily_income' in self.fields and self.instance.can_daily_booking and not self.instance.can_daily_income:
                self.fields['can_daily_income'].initial = True
            if 'can_academy_rent' in self.fields and self.instance.can_report_income and not self.instance.can_academy_rent:
                self.fields['can_academy_rent'].initial = True
            if 'can_accounts' in self.fields and self.instance.can_access_any_report and not self.instance.can_accounts:
                self.fields['can_accounts'].initial = True
            if 'can_settings' in self.fields and self.instance.can_users and not self.instance.can_settings:
                self.fields['can_settings'].initial = True
