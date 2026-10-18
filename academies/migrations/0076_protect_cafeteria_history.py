import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0075_clear_cafeteria_item_images'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cafeteriapurchase',
            name='item',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='purchases',
                to='academies.cafeteriaitem',
                verbose_name='الصنف',
            ),
        ),
        migrations.AlterField(
            model_name='cafeteriasale',
            name='item',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='sales',
                to='academies.cafeteriaitem',
                verbose_name='الصنف',
            ),
        ),
    ]
