# Generated manually
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0007_dailybooking_payments'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserPermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('can_academies', models.BooleanField(default=False, verbose_name='الأكاديميات')),
                ('can_daily_booking', models.BooleanField(default=False, verbose_name='الحجز اليومي')),
                ('can_operation', models.BooleanField(default=False, verbose_name='التشغيل')),
                ('can_shareholders', models.BooleanField(default=False, verbose_name='المساهمين')),
                ('can_employees', models.BooleanField(default=False, verbose_name='الموظفين')),
                ('can_general_expenses', models.BooleanField(default=False, verbose_name='المصروفات العامة')),
                ('can_cafeteria', models.BooleanField(default=False, verbose_name='الكافيتريا')),
                ('can_reports', models.BooleanField(default=False, verbose_name='التقارير')),
                ('can_users', models.BooleanField(default=False, verbose_name='إدارة المستخدمين')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='eess_permissions', to=settings.AUTH_USER_MODEL, verbose_name='المستخدم')),
            ],
            options={
                'verbose_name': 'صلاحيات مستخدم',
                'verbose_name_plural': 'صلاحيات المستخدمين',
            },
        ),
    ]
