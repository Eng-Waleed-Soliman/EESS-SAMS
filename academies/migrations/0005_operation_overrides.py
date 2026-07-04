from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0004_foundingexpense'),
    ]

    operations = [
        migrations.CreateModel(
            name='OperationDayCancellation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cancel_date', models.DateField(unique=True, verbose_name='تاريخ إلغاء التشغيل')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'إلغاء حجوزات يوم',
                'verbose_name_plural': 'إلغاء حجوزات الأيام',
                'ordering': ['-cancel_date'],
            },
        ),
        migrations.CreateModel(
            name='AcademyOperationOverride',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('booking_date', models.DateField(verbose_name='تاريخ التشغيل')),
                ('original_place', models.CharField(max_length=100, verbose_name='مكان التدريب الأصلي')),
                ('original_slot_index', models.PositiveIntegerField(verbose_name='ساعة التدريب الأصلية')),
                ('new_place', models.CharField(blank=True, max_length=100, verbose_name='مكان التدريب الجديد')),
                ('new_slot_index', models.PositiveIntegerField(blank=True, null=True, verbose_name='ساعة التدريب الجديدة')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='تم حذف الحجز')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('academy', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='operation_overrides', to='academies.academy', verbose_name='الأكاديمية')),
            ],
            options={
                'verbose_name': 'تعديل تشغيل أكاديمية',
                'verbose_name_plural': 'تعديلات تشغيل الأكاديميات',
                'ordering': ['-booking_date', 'academy__name'],
                'unique_together': {('academy', 'booking_date', 'original_place', 'original_slot_index')},
            },
        ),
    ]
