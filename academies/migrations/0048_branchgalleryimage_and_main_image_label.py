from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0047_cafeteriahospitality_cafeteriahospitalityitem'),
    ]

    operations = [
        migrations.AlterField(
            model_name='branch',
            name='image',
            field=models.FileField(blank=True, upload_to='branches/images/', verbose_name='صورة الفرع الرئيسية'),
        ),
        migrations.CreateModel(
            name='BranchGalleryImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.FileField(upload_to='branches/gallery/', verbose_name='الصورة الإضافية')),
                ('caption', models.CharField(max_length=250, verbose_name='شرح الصورة (سطر واحد)')),
                ('image_data', models.BinaryField(blank=True, editable=False, null=True)),
                ('image_content_type', models.CharField(blank=True, editable=False, max_length=100)),
                ('image_name', models.CharField(blank=True, editable=False, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gallery_images', to='academies.branch', verbose_name='الفرع')),
            ],
            options={
                'verbose_name': 'صورة إضافية للفرع',
                'verbose_name_plural': 'صور الفرع الإضافية',
                'ordering': ['id'],
            },
        ),
    ]
