from django.db import migrations, models


def copy_existing_academy_bios(apps, schema_editor):
    Academy = apps.get_model('academies', 'Academy')
    for academy in Academy.objects.all().iterator():
        updates = {}
        if not (academy.website_description or '').strip() and (academy.manager_bio or '').strip():
            updates['website_description'] = academy.manager_bio
        if not (academy.website_description_en or '').strip() and (academy.manager_bio_en or '').strip():
            updates['website_description_en'] = academy.manager_bio_en
        if updates:
            Academy.objects.filter(pk=academy.pk).update(**updates)


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0042_academy_public_images_and_manager_profile'),
    ]

    operations = [
        migrations.AddField(
            model_name='academy',
            name='location_link',
            field=models.URLField(blank=True, max_length=1000, verbose_name='رابط موقع الأكاديمية'),
        ),
        migrations.RunPython(copy_existing_academy_bios, migrations.RunPython.noop),
    ]
