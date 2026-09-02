from datetime import date

from django import forms

from .models import PayrollAdjustment


class PayrollAdjustmentForm(forms.ModelForm):
    month = forms.DateField(
        label='الشهر والسنة', input_formats=['%Y-%m'],
        widget=forms.DateInput(format='%Y-%m', attrs={'type': 'month', 'class': 'form-control'}),
    )
    amount = forms.IntegerField(label='المبلغ', min_value=1, max_value=2147483647,
                                widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'step': 1}))

    class Meta:
        model = PayrollAdjustment
        fields = ['employee', 'month', 'amount', 'reason']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, employees, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = employees.order_by('name')

    def clean_month(self):
        month = self.cleaned_data['month']
        return date(month.year, month.month, 1)
