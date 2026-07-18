import re

from django.db import migrations, models


def populate_company_short_name(apps, schema_editor):
    AppSetting = apps.get_model('academies', 'AppSetting')
    for setting in AppSetting.objects.all():
        words = re.findall(r'[A-Za-z0-9]+', setting.company_name or '')
        setting.company_short_name = ''.join(word[0].upper() for word in words[:6]) or 'EESS'
        setting.save(update_fields=['company_short_name'])


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0034_branch_short_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='appsetting',
            name='company_short_name',
            field=models.CharField(
                blank=True,
                default='EESS',
                max_length=100,
                verbose_name='الاسم المختصر للشركة',
            ),
        ),
        migrations.RunPython(populate_company_short_name, migrations.RunPython.noop),
    ]
