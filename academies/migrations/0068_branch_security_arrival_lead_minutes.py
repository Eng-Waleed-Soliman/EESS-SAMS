from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('academies', '0067_userpermission_can_dashboard')]
    operations = [migrations.AddField(
        model_name='branch', name='security_arrival_lead_minutes',
        field=models.PositiveSmallIntegerField(default=30, verbose_name='إظهار اللاعبين قبل التدريب بالدقائق'),
    )]
