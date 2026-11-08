from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0080_cafeteriastafforder_external_notification_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='shareholder',
            name='fixed_monthly_salary',
            field=models.PositiveIntegerField(default=0, verbose_name='قيمة المرتب الشهري الثابت'),
        ),
        migrations.AddField(
            model_name='shareholder',
            name='has_monthly_salary',
            field=models.BooleanField(default=False, verbose_name='مرتب شهري'),
        ),
        migrations.AddField(
            model_name='shareholder',
            name='monthly_salary_type',
            field=models.CharField(
                blank=True,
                choices=[('fixed', 'مرتب ثابت'), ('variable', 'مرتب متغير')],
                max_length=10,
                verbose_name='نوع المرتب الشهري',
            ),
        ),
    ]
