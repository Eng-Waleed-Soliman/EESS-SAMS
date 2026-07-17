from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0028_academy_member_profiles_qr'),
    ]

    operations = [
        migrations.AddField(
            model_name='academy',
            name='logo_content_type',
            field=models.CharField(blank=True, editable=False, max_length=100, verbose_name='نوع ملف لوجو الأكاديمية'),
        ),
        migrations.AddField(
            model_name='academy',
            name='logo_data',
            field=models.BinaryField(blank=True, editable=False, null=True, verbose_name='بيانات لوجو الأكاديمية'),
        ),
        migrations.AddField(
            model_name='academy',
            name='logo_name',
            field=models.CharField(blank=True, editable=False, max_length=255, verbose_name='اسم ملف لوجو الأكاديمية'),
        ),
    ]
