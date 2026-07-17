import uuid

from django.db import migrations, models


def populate_qr_tokens(apps, schema_editor):
    AcademyMember = apps.get_model('academies', 'AcademyMember')
    for member in AcademyMember.objects.filter(qr_token__isnull=True).iterator():
        member.qr_token = uuid.uuid4()
        member.save(update_fields=['qr_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0027_financialvoucher_signature_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='academymember',
            name='birth_date',
            field=models.DateField(blank=True, null=True, verbose_name='تاريخ الميلاد'),
        ),
        migrations.AddField(
            model_name='academymember',
            name='job_title',
            field=models.CharField(blank=True, max_length=200, verbose_name='الوظيفة'),
        ),
        migrations.AddField(
            model_name='academymember',
            name='photo_content_type',
            field=models.CharField(blank=True, editable=False, max_length=100, verbose_name='نوع ملف الصورة'),
        ),
        migrations.AddField(
            model_name='academymember',
            name='photo_data',
            field=models.BinaryField(blank=True, editable=False, null=True, verbose_name='بيانات الصورة'),
        ),
        migrations.AddField(
            model_name='academymember',
            name='photo_name',
            field=models.CharField(blank=True, editable=False, max_length=255, verbose_name='اسم ملف الصورة'),
        ),
        migrations.AddField(
            model_name='academymember',
            name='qr_token',
            field=models.UUIDField(editable=False, null=True, verbose_name='معرف QR'),
        ),
        migrations.RunPython(populate_qr_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='academymember',
            name='qr_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name='معرف QR'),
        ),
    ]
