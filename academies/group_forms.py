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
        if self.instance and self.instance.pk:
            self.fields['training_days'].initial = [str(day) for day in self.instance.training_days]

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

    def save(self, commit=True):
        group = super().save(commit=False)
        group.academy = self.academy
        group.training_days = self.cleaned_data['training_days']
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
