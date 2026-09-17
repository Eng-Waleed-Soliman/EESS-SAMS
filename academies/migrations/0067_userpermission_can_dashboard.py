from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('academies', '0066_security_desk')]
    operations = [migrations.AddField(
        model_name='userpermission', name='can_dashboard',
        field=models.BooleanField(default=False, verbose_name='لوحة التحكم'),
    )]
