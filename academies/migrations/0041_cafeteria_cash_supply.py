import datetime
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0040_financial_voucher_type_sequences'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CafeteriaCashSupply',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('supply_date', models.DateField(default=datetime.date.today, verbose_name='تاريخ التوريد')),
                ('amount', models.PositiveIntegerField(verbose_name='مبلغ التوريد')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('branch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cafeteria_cash_supplies', to='academies.branch', verbose_name='الفرع')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cafeteria_cash_supplies', to=settings.AUTH_USER_MODEL, verbose_name='سجل بواسطة')),
            ],
            options={
                'verbose_name': 'توريد مبلغ كافيتريا',
                'verbose_name_plural': 'توريدات مبالغ الكافيتريا',
                'ordering': ['-supply_date', '-id'],
            },
        ),
    ]
