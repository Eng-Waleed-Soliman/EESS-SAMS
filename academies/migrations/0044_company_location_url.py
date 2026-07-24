from django.db import migrations, models


def move_location_to_company(apps, schema_editor):
    Academy = apps.get_model('academies', 'Academy')
    WebsiteSetting = apps.get_model('academies', 'WebsiteSetting')
    website, _ = WebsiteSetting.objects.get_or_create(pk=1)
    if not (website.location_url or '').strip():
        academy = Academy.objects.exclude(location_link='').order_by('pk').first()
        if academy:
            website.location_url = academy.location_link
            website.save(update_fields=['location_url'])


class Migration(migrations.Migration):
    dependencies = [
        ('academies', '0043_academy_location_link'),
    ]

    operations = [
        migrations.AddField(
            model_name='websitesetting',
            name='location_url',
            field=models.URLField(blank=True, max_length=1000, verbose_name='رابط موقع الشركة على الخريطة'),
        ),
        migrations.RunPython(move_location_to_company, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='academy',
            name='location_link',
        ),
    ]
