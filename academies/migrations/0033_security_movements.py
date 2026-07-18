from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0032_operationdaycancellation_branch'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='userpermission',
            name='can_security',
            field=models.BooleanField(default=False, verbose_name='الأمن'),
        ),
        migrations.CreateModel(
            name='SecurityMovement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('academy_name', models.CharField(blank=True, max_length=200, verbose_name='اسم الأكاديمية وقت التسجيل')),
                ('person_name', models.CharField(max_length=200, verbose_name='الاسم')),
                ('person_type', models.CharField(choices=[('player', 'لاعب'), ('staff', 'مدرب / إداري'), ('parent', 'ولي أمر')], max_length=20, verbose_name='الفئة')),
                ('movement_type', models.CharField(choices=[('entry', 'دخول'), ('exit', 'خروج')], max_length=10, verbose_name='الحركة')),
                ('source', models.CharField(choices=[('manual', 'اختيار من القائمة'), ('qr', 'QR Code'), ('visitor', 'زائر')], default='manual', max_length=20, verbose_name='طريقة التسجيل')),
                ('recorded_at', models.DateTimeField(auto_now_add=True, verbose_name='وقت التسجيل')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('academy', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='security_movements', to='academies.academy', verbose_name='الأكاديمية')),
                ('branch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='security_movements', to='academies.branch', verbose_name='الفرع')),
                ('member', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='security_movements', to='academies.academymember', verbose_name='الشخص المسجل')),
                ('recorded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='security_movements_recorded', to=settings.AUTH_USER_MODEL, verbose_name='سجل بواسطة')),
            ],
            options={
                'verbose_name': 'حركة أمن',
                'verbose_name_plural': 'سجل الأمن',
                'ordering': ['-recorded_at', '-id'],
            },
        ),
    ]
