from django.db import migrations, models
import django.db.models.deletion


def copy_existing_sources(apps, schema_editor):
    FinancialVoucher = apps.get_model('academies', 'FinancialVoucher')
    IncomeAllocation = apps.get_model('academies', 'FinancialVoucherIncomeAllocation')
    rows = []
    for voucher in FinancialVoucher.objects.filter(voucher_type='supply').exclude(income_source=''):
        rows.append(IncomeAllocation(
            voucher_id=voucher.pk,
            source=voucher.income_source,
            amount=voucher.amount,
            daily_booking_date_from=voucher.daily_booking_date_from,
            daily_booking_date_to=voucher.daily_booking_date_to,
        ))
    IncomeAllocation.objects.bulk_create(rows, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [
        ('academies', '0084_financialvoucher_daily_booking_date_from_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='FinancialVoucherIncomeAllocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(choices=[('sports_academies', 'الأكاديميات الرياضية'), ('daily_booking', 'الحجز اليومي'), ('cafeteria', 'دخل الكافيتريا')], max_length=30, verbose_name='مصدر الدخل')),
                ('amount', models.PositiveIntegerField(verbose_name='المبلغ المالي')),
                ('daily_booking_date_from', models.DateField(blank=True, null=True, verbose_name='الحجز اليومي من تاريخ')),
                ('daily_booking_date_to', models.DateField(blank=True, null=True, verbose_name='الحجز اليومي إلى تاريخ')),
                ('voucher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='income_allocations', to='academies.financialvoucher', verbose_name='أمر التوريد')),
            ],
            options={
                'verbose_name': 'مصدر دخل في أمر توريد',
                'verbose_name_plural': 'مصادر الدخل في أوامر التوريد',
                'ordering': ['id'],
            },
        ),
        migrations.AddConstraint(
            model_name='financialvoucherincomeallocation',
            constraint=models.UniqueConstraint(fields=('voucher', 'source'), name='unique_income_source_per_financial_voucher'),
        ),
        migrations.RunPython(copy_existing_sources, migrations.RunPython.noop),
    ]
