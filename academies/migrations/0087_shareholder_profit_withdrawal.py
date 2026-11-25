from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('academies', '0086_financialvoucher_treasury_review'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ShareholderProfitWithdrawal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='المبلغ المالي')),
                ('withdrawal_date', models.DateField(verbose_name='تاريخ الصرف')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='shareholder_profit_withdrawals', to=settings.AUTH_USER_MODEL, verbose_name='سجل بواسطة')),
                ('shareholder', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='profit_withdrawals', to='academies.shareholder', verbose_name='اسم المساهم')),
            ],
            options={
                'verbose_name': 'صرف من نصيب مساهم',
                'verbose_name_plural': 'مصروفات أنصبة المساهمين',
                'ordering': ['-withdrawal_date', '-created_at'],
            },
        ),
    ]
