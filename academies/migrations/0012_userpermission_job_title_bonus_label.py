# Generated manually
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0011_jobtitle_bonustier'),
    ]

    operations = [
        migrations.AddField(
            model_name='userpermission',
            name='job_title',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='academies.jobtitle', verbose_name='المسمى الوظيفي'),
        ),
        migrations.AlterField(
            model_name='bonustier',
            name='source_type',
            field=models.CharField(choices=[('daily_booking', 'الدخل اليومي'), ('cafeteria', 'دخل الكافيتريا')], default='daily_booking', max_length=30, verbose_name='نوع الدخل'),
        ),
    ]
