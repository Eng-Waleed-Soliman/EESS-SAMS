from django.db import migrations


def assign_unscoped_items(apps, schema_editor):
    Branch = apps.get_model('academies', 'Branch')
    CafeteriaItem = apps.get_model('academies', 'CafeteriaItem')
    branch_ids = list(Branch.objects.values_list('id', flat=True)[:2])
    if len(branch_ids) == 1:
        CafeteriaItem.objects.filter(branch__isnull=True).update(branch_id=branch_ids[0])


class Migration(migrations.Migration):
    dependencies = [('academies', '0052_link_orphan_cafeteria_items')]

    operations = [
        migrations.RunPython(assign_unscoped_items, migrations.RunPython.noop),
    ]
