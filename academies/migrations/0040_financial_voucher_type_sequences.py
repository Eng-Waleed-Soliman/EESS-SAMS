from django.db import migrations, models


def backfill_type_sequences(apps, schema_editor):
    FinancialVoucher = apps.get_model('academies', 'FinancialVoucher')
    for voucher_type in ('disbursement', 'supply'):
        voucher_ids = FinancialVoucher.objects.filter(
            voucher_type=voucher_type,
        ).order_by('id').values_list('id', flat=True)
        for sequence_number, voucher_id in enumerate(voucher_ids, start=1):
            FinancialVoucher.objects.filter(pk=voucher_id).update(
                sequence_number=sequence_number,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0039_appsetting_company_logo_content_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='financialvoucher',
            name='sequence_number',
            field=models.PositiveIntegerField(
                editable=False,
                null=True,
                verbose_name='المسلسل حسب نوع الأمر',
            ),
        ),
        migrations.RunPython(backfill_type_sequences, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='financialvoucher',
            name='sequence_number',
            field=models.PositiveIntegerField(
                editable=False,
                verbose_name='المسلسل حسب نوع الأمر',
            ),
        ),
        migrations.AddConstraint(
            model_name='financialvoucher',
            constraint=models.UniqueConstraint(
                fields=('voucher_type', 'sequence_number'),
                name='unique_financial_voucher_sequence_by_type',
            ),
        ),
    ]
