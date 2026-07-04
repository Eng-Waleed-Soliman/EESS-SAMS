# Generated manually for granular report permissions
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0009_dailybookingcheckout'),
    ]

    operations = [
        migrations.AddField(
            model_name='userpermission',
            name='can_report_income',
            field=models.BooleanField(default=False, verbose_name='تقرير الدخل'),
        ),
        migrations.AddField(
            model_name='userpermission',
            name='can_report_shareholders',
            field=models.BooleanField(default=False, verbose_name='تقرير المساهمين والأرباح'),
        ),
        migrations.AddField(
            model_name='userpermission',
            name='can_report_employees',
            field=models.BooleanField(default=False, verbose_name='تقرير الموظفين'),
        ),
        migrations.AddField(
            model_name='userpermission',
            name='can_report_payroll',
            field=models.BooleanField(default=False, verbose_name='تقرير المرتبات والبونص'),
        ),
        migrations.AddField(
            model_name='userpermission',
            name='can_report_expenses',
            field=models.BooleanField(default=False, verbose_name='تقرير المصروفات'),
        ),
        migrations.AddField(
            model_name='userpermission',
            name='can_report_cafeteria',
            field=models.BooleanField(default=False, verbose_name='تقرير الكافيتريا'),
        ),
        migrations.AddField(
            model_name='userpermission',
            name='can_report_deposits',
            field=models.BooleanField(default=False, verbose_name='تقرير مبالغ التأمين'),
        ),
    ]
