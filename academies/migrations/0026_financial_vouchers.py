import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0025_academy_deposit_plans'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FinancialVoucher',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('voucher_type', models.CharField(choices=[('disbursement', 'أمر صرف مبلغ مالي'), ('supply', 'أمر توريد مبلغ مالي')], max_length=20, verbose_name='نوع الأمر')),
                ('amount', models.PositiveIntegerField(verbose_name='قيمة المبلغ')),
                ('statement', models.TextField(verbose_name='السبب / البيان')),
                ('voucher_date', models.DateField(verbose_name='التاريخ')),
                ('signature_title', models.CharField(max_length=150, verbose_name='مسمى وظيفة التوقيع')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='financial_vouchers', to=settings.AUTH_USER_MODEL, verbose_name='أنشئ بواسطة')),
            ],
            options={'verbose_name': 'أمر صرف أو توريد مالي', 'verbose_name_plural': 'أوامر الصرف والتوريد المالية', 'ordering': ['-voucher_date', '-id']},
        ),
    ]
