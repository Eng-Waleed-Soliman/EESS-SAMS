import uuid
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def pair_legacy_movements(apps, schema_editor):
    Movement = apps.get_model('academies', 'SecurityMovement')
    active = {}
    for row in Movement.objects.using(schema_editor.connection.alias).order_by('recorded_at', 'pk').iterator():
        key = (row.branch_id, 'member', row.member_id) if row.member_id else (row.branch_id, 'visitor', row.person_name, row.person_type)
        if row.movement_type == 'entry':
            token = active.setdefault(key, uuid.uuid4())
        else:
            token = active.pop(key, uuid.uuid4())
        Movement.objects.using(schema_editor.connection.alias).filter(pk=row.pk).update(visit_token=token)


class Migration(migrations.Migration):
    dependencies = [('academies', '0065_user_restricted_academy_access'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name='branch', name='security_closing_time', field=models.TimeField(null=True, blank=True, verbose_name='موعد انتهاء العمل — تنبيه الزوار للأمن')),
        migrations.AddField(model_name='securitymovement', name='visit_token', field=models.UUIDField(null=True, blank=True, db_index=True)),
        migrations.AddField(model_name='securitymovement', name='employee', field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, to='academies.employee')),
        migrations.AddField(model_name='securitymovement', name='contact_phone', field=models.CharField(max_length=50, blank=True, verbose_name='الهاتف')),
        migrations.AddField(model_name='securitymovement', name='visit_reason', field=models.CharField(max_length=300, blank=True, verbose_name='سبب الزيارة')),
        migrations.AddField(model_name='securitymovement', name='host_name', field=models.CharField(max_length=200, blank=True, verbose_name='الشخص المطلوب مقابلته')),
        migrations.AddField(model_name='securitymovement', name='receiver_name', field=models.CharField(max_length=200, blank=True, verbose_name='اسم المستلم')),
        migrations.AddField(model_name='securitymovement', name='receiver_relation', field=models.CharField(max_length=100, blank=True, verbose_name='صلة المستلم باللاعب')),
        migrations.AlterField(model_name='securitymovement', name='person_type', field=models.CharField(max_length=20, choices=[('player','لاعب'),('staff','مدرب / إداري'),('parent','ولي أمر'),('employee','موظف'),('visitor','زائر')], verbose_name='الفئة')),
        migrations.AddField(model_name='userpermission', name='security_only', field=models.BooleanField(default=False, verbose_name='الأمن فقط')),
        migrations.AddField(model_name='userpermission', name='security_branch', field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, to='academies.branch', verbose_name='فرع حساب الأمن')),
        migrations.CreateModel(name='SecurityMovementCorrection', fields=[('id',models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),('reason',models.CharField(max_length=500)),('before',models.JSONField(default=dict)),('after',models.JSONField(default=dict)),('corrected_at',models.DateTimeField(auto_now_add=True)),('corrected_by',models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL)),('movement',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='corrections',to='academies.securitymovement'))]),
        migrations.CreateModel(name='AcademyPlayerReceiver', fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('name',models.CharField(max_length=200,verbose_name='اسم المستلم المصرح له')),('relation',models.CharField(max_length=100,verbose_name='صلة القرابة')),('phone',models.CharField(max_length=50,blank=True,verbose_name='الهاتف')),('is_active',models.BooleanField(default=True)),('player',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='authorized_receivers',to='academies.academymember'))]),
        migrations.RunPython(pair_legacy_movements, migrations.RunPython.noop),
    ]
