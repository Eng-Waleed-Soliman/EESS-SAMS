from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0070_academy_training_schedule_versions'),
    ]

    operations = [
        migrations.AddField(
            model_name='cafeteriaitem',
            name='is_barista_item',
            field=models.BooleanField(default=False, verbose_name='صنف باريستا'),
        ),
    ]