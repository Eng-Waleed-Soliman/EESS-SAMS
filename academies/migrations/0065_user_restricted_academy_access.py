from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('academies', '0064_academy_fixed_monthly_rents')]

    operations = [
        migrations.AddField(model_name='userpermission', name='academy_only', field=models.BooleanField(default=False, verbose_name='قصر الدخول على أكاديمية واحدة فقط')),
        migrations.AddField(model_name='userpermission', name='restricted_academy', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='academies.academy', verbose_name='الأكاديمية المسموح بها')),
        migrations.AddField(model_name='userpermission', name='academy_sections', field=models.JSONField(blank=True, default=list, verbose_name='الأقسام المسموح بعرضها داخل الأكاديمية')),
    ]
