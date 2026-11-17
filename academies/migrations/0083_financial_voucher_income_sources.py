from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0082_expense_categories'),
    ]

    operations = [
        migrations.AddField(
            model_name='financialvoucher',
            name='income_source',
            field=models.CharField(blank=True, choices=[('sports_academies', 'الأكاديميات الرياضية'), ('daily_booking', 'الحجز اليومي'), ('cafeteria', 'دخل الكافيتريا')], max_length=30, verbose_name='مصدر الدخل'),
        ),
        migrations.CreateModel(
            name='FinancialVoucherAcademyAllocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.PositiveIntegerField(verbose_name='المبلغ المالي')),
                ('academy', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='financial_voucher_allocations', to='academies.academy', verbose_name='الأكاديمية')),
                ('voucher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='academy_allocations', to='academies.financialvoucher', verbose_name='أمر التوريد')),
            ],
            options={
                'verbose_name': 'تفصيل أكاديمية في أمر توريد',
                'verbose_name_plural': 'تفاصيل الأكاديميات في أوامر التوريد',
                'ordering': ['academy__name', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='financialvoucheracademyallocation',
            constraint=models.UniqueConstraint(fields=('voucher', 'academy'), name='unique_academy_per_financial_voucher'),
        ),
    ]
