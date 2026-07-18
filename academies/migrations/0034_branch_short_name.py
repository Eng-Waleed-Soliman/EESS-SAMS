import re
from django.db import migrations, models


def populate_short_names(apps, schema_editor):
    Branch = apps.get_model('academies', 'Branch')
    ignored = {'of', 'the', 'and', 'for', 'in', 'at'}
    for branch in Branch.objects.filter(short_name=''):
        words = re.findall(r'[A-Za-z0-9]+', branch.name or '')
        significant = [word for word in words if word.lower() not in ignored]
        if len(significant) >= 2:
            short_name = ''.join(word[0].upper() for word in significant)
        else:
            short_name = (branch.name or '')[:100]
        branch.short_name = short_name
        branch.save(update_fields=['short_name'])


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0033_security_movements'),
    ]

    operations = [
        migrations.AddField(
            model_name='branch',
            name='short_name',
            field=models.CharField(blank=True, max_length=100, verbose_name='الاسم المختصر للفرع'),
        ),
        migrations.RunPython(populate_short_names, migrations.RunPython.noop),
    ]
