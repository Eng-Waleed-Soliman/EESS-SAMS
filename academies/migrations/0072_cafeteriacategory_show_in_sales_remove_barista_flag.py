from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0071_cafeteriaitem_is_barista_item'),
    ]

    operations = [
        migrations.AddField(
            model_name='cafeteriacategory',
            name='show_in_sales',
            field=models.BooleanField(default=True, verbose_name='الظهور في حركات البيع'),
        ),
        migrations.RemoveField(
            model_name='cafeteriaitem',
            name='is_barista_item',
        ),
    ]