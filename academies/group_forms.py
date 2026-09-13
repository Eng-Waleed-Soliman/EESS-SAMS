from django import forms

from .constants import WEEKDAY_AR
from .models import AcademyMember, AcademyTrainingGroup


WEEKDAY_CHOICES = [(str(number), label) for number, label in sorted(WEEKDAY_AR.items(), key=lambda item: (item[0] - 5) % 7)]


class AcademyTrainingGroupForm(forms.ModelForm):
    training_days = forms.MultipleChoiceField(
        label='أيام التدريب', choices=WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text='يمكن اختيار أكثر من يوم، مثل السبت والثلاثاء.',
        error_messages={'required': 'اختر يوم تدريب واحدًا على الأقل.'},
    )

    class Meta:
        model = AcademyTrainingGroup
        fields = ['name', 'training_days']
        widgets = {'name': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True})}

    def __init__(self, *args, academy, **kwargs):
        self.academy = academy
        super().__init__(*args, **kwargs)
        saved_times = self.instance.training_times if self.instance and self.instance.pk else {}
        for day, label in WEEKDAY_CHOICES:
            timing = saved_times.get(day, {})
            self.fields[f'start_{day}'] = forms.TimeField(
                label=f'من الساعة - {label}', required=False,
                initial=timing.get('start'),
                input_formats=['%H:%M'],
                widget=forms.TimeInput(format='%H:%M', attrs={
                    'class': 'form-control', 'type': 'time', 'step': '300',
                }),
            )
            self.fields[f'end_{day}'] = forms.TimeField(
                label=f'إلى الساعة - {label}', required=False,
                initial=timing.get('end'),
                input_formats=['%H:%M'],
                widget=forms.TimeInput(format='%H:%M', attrs={
                    'class': 'form-control', 'type': 'time', 'step': '300',
                }),
            )
        if self.instance and self.instance.pk:
            self.fields['training_days'].initial = [str(day) for day in self.instance.training_days]

    @property
    def schedule_fields(self):
        return [
            {
                'day': day,
                'label': label,
                'start': self[f'start_{day}'],
                'end': self[f'end_{day}'],
            }
            for day, label in WEEKDAY_CHOICES
        ]

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        duplicate = AcademyTrainingGroup.objects.filter(academy=self.academy, name__iexact=name)
        if self.instance and self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError('يوجد مجموعة بنفس الاسم داخل هذه الأكاديمية.')
        return name

    def clean_training_days(self):
        selected = set(self.cleaned_data['training_days'])
        days = [int(value) for value, _label in WEEKDAY_CHOICES if value in selected]
        if not days:
            raise forms.ValidationError('اختر يوم تدريب واحدًا على الأقل.')
        return days

    def clean(self):
        cleaned = super().clean()
        selected_days = cleaned.get('training_days') or []
        for day in selected_days:
            start_name = f'start_{day}'
            end_name = f'end_{day}'
            start_time = cleaned.get(start_name)
            end_time = cleaned.get(end_name)
            if not start_time:
                self.add_error(start_name, 'حدد وقت بداية التدريب لهذا اليوم.')
            if not end_time:
                self.add_error(end_name, 'حدد وقت نهاية التدريب لهذا اليوم.')
            if start_time and end_time and end_time <= start_time:
                self.add_error(end_name, 'وقت نهاية التدريب يجب أن يكون بعد وقت البداية.')
        return cleaned

    def save(self, commit=True):
        group = super().save(commit=False)
        group.academy = self.academy
        group.training_days = self.cleaned_data['training_days']
        group.training_times = {
            str(day): {
                'start': self.cleaned_data[f'start_{day}'].strftime('%H:%M'),
                'end': self.cleaned_data[f'end_{day}'].strftime('%H:%M'),
            }
            for day in group.training_days
        }
        if commit:
            group.save()
        return group


class AcademyTrainingGroupPlayerForm(forms.Form):
    player = forms.ModelChoiceField(
        label='اسم اللاعب', queryset=AcademyMember.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, academy, group, **kwargs):
        super().__init__(*args, **kwargs)
        assigned_ids = group.player_assignments.values_list('player_id', flat=True)
        self.fields['player'].queryset = academy.members.filter(
            role=AcademyMember.ROLE_PLAYER,
        ).exclude(pk__in=assigned_ids).order_by('-is_active', 'name', 'id')
