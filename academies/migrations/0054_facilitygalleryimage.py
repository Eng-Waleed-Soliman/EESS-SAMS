from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0053_assign_unscoped_cafeteria_items'),
    ]

    operations = [
        migrations.CreateModel(
            name='FacilityGalleryImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.FileField(upload_to='facilities/gallery/', verbose_name='الصورة')),
                ('caption', models.CharField(max_length=250, verbose_name='التعليق أسفل الصورة')),
                ('image_data', models.BinaryField(blank=True, editable=False, null=True)),
                ('image_content_type', models.CharField(blank=True, editable=False, max_length=100)),
                ('image_name', models.CharField(blank=True, editable=False, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('facility', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gallery_images', to='academies.facility', verbose_name='الملعب / الصالة')),
            ],
            options={
                'verbose_name': 'صورة ملعب / صالة',
                'verbose_name_plural': 'صور الملاعب والصالات',
                'ordering': ['id'],
            },
        ),
    ]
