from django.db import migrations, models


def initialize_effective_dates(apps, schema_editor):
    Academy = apps.get_model('academies', 'Academy')
    for academy in Academy.objects.filter(training_schedule_effective_date__isnull=True).iterator():
        academy.training_schedule_effective_date = academy.contract_start_date
        academy.save(update_fields=['training_schedule_effective_date'])


class Migration(migrations.Migration):
    dependencies = [
        ('academies', '0069_securitymovement_national_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='academy',
            name='training_schedule_effective_date',
            field=models.DateField(blank=True, null=True, verbose_name='تاريخ تطبيق جدول التدريب الحالي'),
        ),
        migrations.AddField(
            model_name='academy',
            name='training_schedule_history',
            field=models.JSONField(blank=True, default=list, verbose_name='سجل جداول التدريب السابقة'),
        ),
        migrations.RunPython(initialize_effective_dates, migrations.RunPython.noop),
    ]
