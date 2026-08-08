import datetime

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0048_branchgalleryimage_and_main_image_label'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CafeteriaOperatingExpense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('expense_date', models.DateField(default=datetime.date.today, verbose_name='تاريخ المصروف')),
                ('title', models.CharField(max_length=200, verbose_name='بيان المصروف')),
                ('amount', models.PositiveIntegerField(verbose_name='قيمة المصروفات')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('branch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cafeteria_operating_expenses', to='academies.branch', verbose_name='الفرع')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cafeteria_operating_expenses_created', to=settings.AUTH_USER_MODEL, verbose_name='سُجل بواسطة')),
            ],
            options={
                'verbose_name': 'مصروف تشغيل كافيتريا',
                'verbose_name_plural': 'مصاريف تشغيل الكافيتريا',
                'ordering': ['-expense_date', '-id'],
            },
        ),
    ]
