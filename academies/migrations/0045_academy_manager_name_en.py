from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0044_company_location_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='academy',
            name='manager_name_en',
            field=models.CharField(blank=True, max_length=200, verbose_name='اسم مدير الأكاديمية بالإنجليزية'),
        ),
    ]
