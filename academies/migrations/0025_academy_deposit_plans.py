import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0024_cafeteriaitem_stock_adjustment'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AcademyDepositPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_amount', models.PositiveIntegerField(default=0, verbose_name='إجمالي مبلغ التأمين')),
                ('installments_count', models.PositiveSmallIntegerField(default=1, verbose_name='عدد الأقساط')),
                ('first_due_month', models.DateField(verbose_name='شهر استحقاق أول قسط')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات الخطة')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('academy', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='deposit_plan', to='academies.academy', verbose_name='الأكاديمية')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_deposit_plans', to=settings.AUTH_USER_MODEL, verbose_name='أنشأها')),
            ],
            options={'verbose_name': 'خطة تأمين أكاديمية', 'verbose_name_plural': 'خطط تأمين الأكاديميات', 'ordering': ['academy__name']},
        ),
        migrations.CreateModel(
            name='AcademyDepositInstallment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('installment_number', models.PositiveSmallIntegerField(verbose_name='رقم القسط')),
                ('due_month', models.DateField(verbose_name='شهر الاستحقاق')),
                ('due_amount', models.PositiveIntegerField(default=0, verbose_name='المبلغ المستحق')),
                ('paid_amount', models.PositiveIntegerField(default=0, verbose_name='المبلغ المسدد')),
                ('payment_date', models.DateField(blank=True, null=True, verbose_name='تاريخ السداد')),
                ('supplied_amount', models.PositiveIntegerField(default=0, verbose_name='المبلغ المورد')),
                ('supplied_date', models.DateField(blank=True, null=True, verbose_name='تاريخ التوريد')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('paid_recorded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recorded_deposit_payments', to=settings.AUTH_USER_MODEL, verbose_name='مسجل السداد')),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='installments', to='academies.academydepositplan', verbose_name='خطة التأمين')),
                ('supplied_recorded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recorded_deposit_supplies', to=settings.AUTH_USER_MODEL, verbose_name='مسجل التوريد')),
            ],
            options={'verbose_name': 'قسط تأمين أكاديمية', 'verbose_name_plural': 'أقساط تأمين الأكاديميات', 'ordering': ['due_month', 'installment_number'], 'unique_together': {('plan', 'installment_number')}},
        ),
    ]
