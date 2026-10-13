from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0072_cafeteriacategory_show_in_sales_remove_barista_flag'),
    ]

    operations = [
        migrations.AddField(
            model_name='cafeteriaitem',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='صنف نشط'),
        ),
    ]
