from django.db import migrations, models


def copy_regular_prices_to_staff(apps, schema_editor):
    CafeteriaItem = apps.get_model('academies', 'CafeteriaItem')
    CafeteriaItem.objects.all().update(staff_sale_price=models.F('sale_price'))


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0056_player_monthly_subscriptions'),
    ]

    operations = [
        migrations.AddField(
            model_name='cafeteriaitem',
            name='staff_sale_price',
            field=models.PositiveIntegerField(default=0, verbose_name='سعر البيع Staff'),
        ),
        migrations.AddField(
            model_name='cafeteriasale',
            name='is_staff_sale',
            field=models.BooleanField(default=False, verbose_name='بيع Staff'),
        ),
        migrations.RunPython(copy_regular_prices_to_staff, migrations.RunPython.noop),
    ]
