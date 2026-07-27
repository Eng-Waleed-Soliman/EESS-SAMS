from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def preserve_existing_financial_movements(apps, schema_editor):
    RentPayment = apps.get_model('academies', 'AcademyMonthlyRentPayment')
    RentEntry = apps.get_model('academies', 'AcademyRentPaymentEntry')
    DepositPlan = apps.get_model('academies', 'AcademyDepositPlan')
    DepositInstallment = apps.get_model('academies', 'AcademyDepositInstallment')

    for payment in RentPayment.objects.all().iterator():
        if payment.paid_amount or payment.supplied_amount:
            RentEntry.objects.create(
                payment_id=payment.pk,
                paid_amount=payment.paid_amount or 0,
                payment_date=payment.payment_date,
                supplied_amount=payment.supplied_amount or 0,
                supplied_date=payment.supplied_date,
                notes=payment.notes or '',
            )

    # The previous screen generated empty fixed-schedule rows. Keep only real
    # financial movements and convert them to the new free-form installments.
    DepositInstallment.objects.filter(paid_amount=0, supplied_amount=0).delete()
    for plan in DepositPlan.objects.all().iterator():
        installments = list(
            DepositInstallment.objects.filter(plan_id=plan.pk).order_by(
                'payment_date', 'due_month', 'installment_number', 'pk'
            )
        )
        # Avoid collisions with the unique (plan, installment_number) key.
        for index, installment in enumerate(installments, start=1):
            installment.installment_number = 30000 + index
            installment.save(update_fields=['installment_number'])
        for index, installment in enumerate(installments, start=1):
            installment.installment_number = index
            installment.due_amount = installment.paid_amount or 0
            if installment.payment_date:
                installment.due_month = installment.payment_date.replace(day=1)
            installment.save(update_fields=['installment_number', 'due_amount', 'due_month'])
        if installments:
            plan.installments_count = len(installments)
            first_date = installments[0].payment_date or installments[0].due_month
            plan.first_due_month = first_date.replace(day=1)
            plan.save(update_fields=['installments_count', 'first_due_month'])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('academies', '0045_academy_manager_name_en'),
    ]

    operations = [
        migrations.CreateModel(
            name='AcademyRentPaymentEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('paid_amount', models.PositiveIntegerField(default=0, verbose_name='المبلغ المسدد')),
                ('payment_date', models.DateField(blank=True, null=True, verbose_name='تاريخ السداد')),
                ('supplied_amount', models.PositiveIntegerField(default=0, verbose_name='المبلغ المورد')),
                ('supplied_date', models.DateField(blank=True, null=True, verbose_name='تاريخ التوريد')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('payment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='entries', to='academies.academymonthlyrentpayment', verbose_name='سداد إيجار الشهر')),
                ('recorded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recorded_academy_rent_entries', to=settings.AUTH_USER_MODEL, verbose_name='مسجل الحركة')),
            ],
            options={
                'verbose_name': 'دفعة إيجار أكاديمية',
                'verbose_name_plural': 'دفعات إيجارات الأكاديميات',
                'ordering': ['payment_date', 'created_at', 'id'],
            },
        ),
        migrations.RunPython(preserve_existing_financial_movements, migrations.RunPython.noop),
    ]
