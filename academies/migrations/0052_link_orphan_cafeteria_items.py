from django.db import migrations


def link_orphan_items_to_code_category(apps, schema_editor):
    CafeteriaCategory = apps.get_model('academies', 'CafeteriaCategory')
    CafeteriaItem = apps.get_model('academies', 'CafeteriaItem')
    categories = {
        category.code: category.id
        for category in CafeteriaCategory.objects.all().only('id', 'code')
    }
    for item in CafeteriaItem.objects.filter(category__isnull=True).only('id', 'code'):
        category_id = categories.get((item.code // 100) * 100)
        if category_id:
            CafeteriaItem.objects.filter(pk=item.pk).update(category_id=category_id)


class Migration(migrations.Migration):
    dependencies = [('academies', '0051_cafeteria_item_types_and_recipes')]

    operations = [
        migrations.AlterUniqueTogether(
            name='cafeteriaitem',
            unique_together=set(),
        ),
        migrations.RunPython(link_orphan_items_to_code_category, migrations.RunPython.noop),
    ]
