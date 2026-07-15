from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0023_appsetting_company_name_ar_and_daily_supply_entries'),
    ]

    operations = [
        migrations.AddField(
            model_name='cafeteriaitem',
            name='stock_adjustment',
            field=models.IntegerField(default=0, verbose_name='تسوية المخزون'),
        ),
    ]
