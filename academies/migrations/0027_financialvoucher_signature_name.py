from django.db import migrations, models


def populate_signature_names(apps, schema_editor):
    FinancialVoucher = apps.get_model('academies', 'FinancialVoucher')
    Employee = apps.get_model('academies', 'Employee')
    for voucher in FinancialVoucher.objects.filter(signature_name='').iterator():
        employee = Employee.objects.filter(job_title=voucher.signature_title).order_by('name').first()
        if employee:
            voucher.signature_name = employee.name
            voucher.save(update_fields=['signature_name'])


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0026_financial_vouchers'),
    ]

    operations = [
        migrations.AddField(
            model_name='financialvoucher',
            name='signature_name',
            field=models.CharField(blank=True, max_length=200, verbose_name='اسم الموظف الموقّع'),
        ),
        migrations.RunPython(populate_signature_names, migrations.RunPython.noop),
    ]
