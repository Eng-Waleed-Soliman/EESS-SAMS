# Generated manually for EESS checkout income

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0008_userpermission'),
    ]

    operations = [
        migrations.CreateModel(
            name='DailyBookingCheckout',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('income_date', models.DateField(verbose_name='تاريخ الدخل اليومي')),
                ('customer_name', models.CharField(max_length=200, verbose_name='اسم العميل')),
                ('customer_phone', models.CharField(max_length=50, verbose_name='رقم الموبايل')),
                ('venue', models.CharField(max_length=100, verbose_name='مكان الحجز')),
                ('booking_date', models.DateField(verbose_name='تاريخ الحجز')),
                ('start_time', models.CharField(max_length=50, verbose_name='من الساعة')),
                ('end_time', models.CharField(max_length=50, verbose_name='إلى الساعة')),
                ('total_amount', models.PositiveIntegerField(default=0, verbose_name='إجمالي قيمة الحجز')),
                ('advance_payment', models.PositiveIntegerField(default=0, verbose_name='مقدم الحجز')),
                ('remaining_amount', models.PositiveIntegerField(default=0, verbose_name='المتبقي')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='وقت عمل Checkout')),
                ('booking', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='checkout', to='academies.dailybooking', verbose_name='الحجز اليومي')),
            ],
            options={
                'verbose_name': 'دخل يومي من Checkout',
                'verbose_name_plural': 'الدخل اليومي من Checkout',
                'ordering': ['-income_date', 'start_time', 'customer_name'],
            },
        ),
    ]
