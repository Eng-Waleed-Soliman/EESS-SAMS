from django.db import migrations, models
import django.db.models.deletion


def assign_existing_records_to_first_branch(apps, schema_editor):
    Branch = apps.get_model('academies', 'Branch')
    branch = Branch.objects.order_by('id').first()
    if not branch:
        return
    for model_name in (
        'CafeteriaItem', 'DailyBooking', 'DailyExpense', 'DailyIncomeSupply',
        'Employee', 'FinancialVoucher', 'FoundingExpense', 'MonthlyExpense',
        'OperatingExpense',
    ):
        apps.get_model('academies', model_name).objects.filter(branch__isnull=True).update(branch=branch)


class Migration(migrations.Migration):
    dependencies = [('academies', '0029_academy_logo_data')]

    operations = [
        migrations.AddField(
            model_name='cafeteriaitem', name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cafeteria_items', to='academies.branch', verbose_name='الفرع'),
        ),
        migrations.AddField(
            model_name='dailybooking', name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='daily_bookings', to='academies.branch', verbose_name='الفرع'),
        ),
        migrations.AddField(
            model_name='dailyexpense', name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='daily_expenses', to='academies.branch', verbose_name='الفرع'),
        ),
        migrations.AddField(
            model_name='dailyincomesupply', name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='daily_income_supplies', to='academies.branch', verbose_name='الفرع'),
        ),
        migrations.AddField(
            model_name='employee', name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='employees', to='academies.branch', verbose_name='الفرع'),
        ),
        migrations.AddField(
            model_name='financialvoucher', name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='financial_vouchers', to='academies.branch', verbose_name='الفرع'),
        ),
        migrations.AddField(
            model_name='foundingexpense', name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='founding_expenses', to='academies.branch', verbose_name='الفرع'),
        ),
        migrations.AddField(
            model_name='monthlyexpense', name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='monthly_expenses', to='academies.branch', verbose_name='الفرع'),
        ),
        migrations.AddField(
            model_name='operatingexpense', name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='operating_expenses', to='academies.branch', verbose_name='الفرع'),
        ),
        migrations.RunPython(assign_existing_records_to_first_branch, migrations.RunPython.noop),
    ]
