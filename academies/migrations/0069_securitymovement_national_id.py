from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('academies', '0068_branch_security_arrival_lead_minutes')]

    operations = [
        migrations.AddField(
            model_name='securitymovement',
            name='national_id',
            field=models.CharField(blank=True, max_length=14, verbose_name='الرقم القومي'),
        ),
    ]
