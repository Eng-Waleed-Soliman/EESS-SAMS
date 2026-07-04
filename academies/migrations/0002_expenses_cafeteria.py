from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MonthlyExpense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='بيان المصروف الشهري')),
                ('expense_month', models.DateField(verbose_name='شهر المصروف')),
                ('amount', models.PositiveIntegerField(default=0, verbose_name='القيمة')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'مصروف شهري',
                'verbose_name_plural': 'المصروفات الشهرية',
                'ordering': ['-expense_month', 'title'],
            },
        ),
        migrations.CreateModel(
            name='DailyExpense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='بيان المصروف اليومي')),
                ('expense_date', models.DateField(verbose_name='تاريخ المصروف')),
                ('amount', models.PositiveIntegerField(default=0, verbose_name='القيمة')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'مصروف يومي',
                'verbose_name_plural': 'المصروفات اليومية',
                'ordering': ['-expense_date', 'title'],
            },
        ),
        migrations.CreateModel(
            name='CafeteriaItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='اسم الصنف')),
                ('opening_quantity', models.PositiveIntegerField(default=0, verbose_name='رصيد افتتاحي')),
                ('purchase_price', models.PositiveIntegerField(default=0, verbose_name='سعر الشراء')),
                ('sale_price', models.PositiveIntegerField(default=0, verbose_name='سعر البيع')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'صنف كافيتريا',
                'verbose_name_plural': 'أصناف الكافيتريا',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='CafeteriaPurchase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('purchase_date', models.DateField(verbose_name='تاريخ الشراء')),
                ('quantity', models.PositiveIntegerField(default=1, verbose_name='الكمية')),
                ('unit_price', models.PositiveIntegerField(default=0, verbose_name='سعر شراء الوحدة')),
                ('supplier', models.CharField(blank=True, max_length=200, verbose_name='المورد')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='purchases', to='academies.cafeteriaitem', verbose_name='الصنف')),
            ],
            options={
                'verbose_name': 'حركة شراء كافيتريا',
                'verbose_name_plural': 'حركات شراء الكافيتريا',
                'ordering': ['-purchase_date'],
            },
        ),
        migrations.CreateModel(
            name='CafeteriaSale',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sale_date', models.DateField(verbose_name='تاريخ البيع')),
                ('quantity', models.PositiveIntegerField(default=1, verbose_name='الكمية')),
                ('unit_price', models.PositiveIntegerField(default=0, verbose_name='سعر بيع الوحدة')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sales', to='academies.cafeteriaitem', verbose_name='الصنف')),
            ],
            options={
                'verbose_name': 'حركة بيع كافيتريا',
                'verbose_name_plural': 'حركات بيع الكافيتريا',
                'ordering': ['-sale_date'],
            },
        ),
    ]
