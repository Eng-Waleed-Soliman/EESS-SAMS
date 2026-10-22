from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0079_convert_stored_images_to_webp'),
    ]

    operations = [
        migrations.AddField(
            model_name='cafeteriastafforder',
            name='external_notification_token',
            field=models.TextField(blank=True, verbose_name='رمز تنبيه BICCHub'),
        ),
    ]
