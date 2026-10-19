from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0076_protect_cafeteria_history'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CafeteriaStaffOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('requester_name', models.CharField(max_length=200, verbose_name='اسم مقدم الطلب')),
                ('delivery_place', models.CharField(choices=[('office', 'المكتب'), ('cafeteria', 'الكافيتريا')], default='cafeteria', max_length=20, verbose_name='مكان الاستلام')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('status', models.CharField(choices=[('pending', 'قيد التنفيذ'), ('completed', 'تم التنفيذ')], default='pending', max_length=20, verbose_name='الحالة')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('branch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cafeteria_staff_orders', to='academies.branch', verbose_name='الفرع')),
                ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cafeteria_staff_orders', to=settings.AUTH_USER_MODEL, verbose_name='مقدم الطلب')),
            ],
            options={
                'verbose_name': 'طلب موظف من الكافيتريا',
                'verbose_name_plural': 'طلبات الموظفين من الكافيتريا',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='CafeteriaStaffOrderItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('item_name', models.CharField(max_length=200, verbose_name='اسم الصنف وقت الطلب')),
                ('quantity', models.PositiveIntegerField(default=1, verbose_name='الكمية')),
                ('unit_price', models.PositiveIntegerField(default=0, verbose_name='السعر وقت الطلب')),
                ('item', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='staff_order_items', to='academies.cafeteriaitem', verbose_name='الصنف')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='academies.cafeteriastafforder', verbose_name='الطلب')),
            ],
            options={
                'verbose_name': 'صنف طلب موظف',
                'verbose_name_plural': 'أصناف طلبات الموظفين',
                'ordering': ['id'],
            },
        ),
    ]
