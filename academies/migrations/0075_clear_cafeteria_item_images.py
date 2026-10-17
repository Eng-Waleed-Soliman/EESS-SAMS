from django.db import migrations


def clear_cafeteria_item_images(apps, schema_editor):
    CafeteriaItem = apps.get_model('academies', 'CafeteriaItem')
    CafeteriaItem.objects.exclude(image_data__isnull=True).update(
        image_data=None,
        image_content_type='',
        image_name='',
    )
    CafeteriaItem.objects.exclude(image_content_type='').update(image_content_type='')
    CafeteriaItem.objects.exclude(image_name='').update(image_name='')


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0074_cafeteriacategory_image_content_type_and_more'),
    ]

    operations = [
        migrations.RunPython(clear_cafeteria_item_images, migrations.RunPython.noop),
    ]