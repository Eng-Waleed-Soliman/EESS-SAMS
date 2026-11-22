from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0085_financialvoucherincomeallocation'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='financialvoucher',
            name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='تاريخ مراجعة الخزينة'),
        ),
        migrations.AddField(
            model_name='financialvoucher',
            name='reviewed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_financial_vouchers', to=settings.AUTH_USER_MODEL, verbose_name='تمت المراجعة بواسطة'),
        ),
    ]
