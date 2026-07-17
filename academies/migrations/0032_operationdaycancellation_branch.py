from django.db import migrations, models
import django.db.models.deletion


def backfill_cancellation_branches(apps, schema_editor):
    Branch = apps.get_model('academies', 'Branch')
    Cancellation = apps.get_model('academies', 'OperationDayCancellation')
    first_branch = Branch.objects.order_by('id').first()
    if first_branch:
        Cancellation.objects.filter(branch__isnull=True).update(branch=first_branch)


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0031_backfill_legacy_academy_branch'),
    ]

    operations = [
        migrations.AlterField(
            model_name='operationdaycancellation',
            name='cancel_date',
            field=models.DateField(verbose_name='تاريخ إلغاء التشغيل'),
        ),
        migrations.AddField(
            model_name='operationdaycancellation',
            name='branch',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='operation_day_cancellations',
                to='academies.branch',
                verbose_name='الفرع',
            ),
        ),
        migrations.RunPython(backfill_cancellation_branches, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='operationdaycancellation',
            constraint=models.UniqueConstraint(
                fields=('branch', 'cancel_date'),
                name='unique_operation_cancellation_per_branch',
            ),
        ),
    ]
