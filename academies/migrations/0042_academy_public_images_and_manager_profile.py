from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0041_cafeteria_cash_supply'),
    ]

    operations = [
        migrations.AddField(
            model_name='academy',
            name='website_image_data',
            field=models.BinaryField(blank=True, editable=False, null=True, verbose_name='بيانات صورة الأكاديمية للموقع'),
        ),
        migrations.AddField(
            model_name='academy',
            name='website_image_content_type',
            field=models.CharField(blank=True, editable=False, max_length=100, verbose_name='نوع صورة الأكاديمية للموقع'),
        ),
        migrations.AddField(
            model_name='academy',
            name='website_image_name',
            field=models.CharField(blank=True, editable=False, max_length=255, verbose_name='اسم صورة الأكاديمية للموقع'),
        ),
        migrations.AddField(
            model_name='academy',
            name='manager_photo_data',
            field=models.BinaryField(blank=True, editable=False, null=True, verbose_name='بيانات صورة مدير الأكاديمية'),
        ),
        migrations.AddField(
            model_name='academy',
            name='manager_photo_content_type',
            field=models.CharField(blank=True, editable=False, max_length=100, verbose_name='نوع صورة مدير الأكاديمية'),
        ),
        migrations.AddField(
            model_name='academy',
            name='manager_photo_name',
            field=models.CharField(blank=True, editable=False, max_length=255, verbose_name='اسم صورة مدير الأكاديمية'),
        ),
        migrations.AddField(
            model_name='academy',
            name='manager_bio',
            field=models.TextField(blank=True, verbose_name='نبذة عن مدير الأكاديمية'),
        ),
        migrations.AddField(
            model_name='academy',
            name='manager_bio_en',
            field=models.TextField(blank=True, verbose_name='نبذة عن مدير الأكاديمية بالإنجليزية'),
        ),
    ]
