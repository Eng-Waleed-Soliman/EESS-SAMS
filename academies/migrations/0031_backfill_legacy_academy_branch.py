from django.db import migrations


def backfill_legacy_academies(apps, schema_editor):
    Branch = apps.get_model('academies', 'Branch')
    Academy = apps.get_model('academies', 'Academy')
    branch = Branch.objects.order_by('id').first()
    if branch:
        Academy.objects.filter(branch__isnull=True).update(branch=branch)


class Migration(migrations.Migration):
    dependencies = [('academies', '0030_branch_scoped_records')]
    operations = [
        migrations.RunPython(backfill_legacy_academies, migrations.RunPython.noop),
    ]
