from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0022_shift_operation_slots_for_morning_period'),
    ]

    operations = [
        migrations.AddField(
            model_name='appsetting',
            name='company_name_ar',
            field=models.CharField(blank=True, default='', max_length=250, verbose_name='اسم الشركة باللغة العربية'),
        ),
        migrations.AlterField(
            model_name='appsetting',
            name='company_name',
            field=models.CharField(default='Egyptian English Sports Services', max_length=250, verbose_name='اسم الشركة باللغة الإنجليزية'),
        ),
        migrations.AlterField(
            model_name='dailyincomesupply',
            name='supply_date',
            field=models.DateField(verbose_name='تاريخ التوريد'),
        ),
    ]
