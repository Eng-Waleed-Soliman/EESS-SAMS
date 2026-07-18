from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0036_websitesetting_academy_is_published_on_website_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='websitesetting',
            name='hero_text_en',
            field=models.TextField(blank=True, verbose_name='النص التعريفي الرئيسي بالإنجليزية'),
        ),
        migrations.AddField(
            model_name='websitesetting',
            name='about_title_en',
            field=models.CharField(blank=True, max_length=250, verbose_name='عنوان نبذة الشركة بالإنجليزية'),
        ),
        migrations.AddField(
            model_name='websitesetting',
            name='about_text_en',
            field=models.TextField(blank=True, verbose_name='نبذة عن الشركة بالإنجليزية'),
        ),
        migrations.AddField(
            model_name='websitesetting',
            name='address_en',
            field=models.CharField(blank=True, max_length=300, verbose_name='العنوان بالإنجليزية'),
        ),
        migrations.AddField(
            model_name='websitesetting',
            name='footer_text_en',
            field=models.CharField(blank=True, max_length=300, verbose_name='نص أسفل الموقع بالإنجليزية'),
        ),
        migrations.AddField(
            model_name='branch',
            name='name_en',
            field=models.CharField(blank=True, max_length=200, verbose_name='اسم الفرع بالإنجليزية للموقع'),
        ),
        migrations.AddField(
            model_name='branch',
            name='location_en',
            field=models.CharField(blank=True, max_length=250, verbose_name='الموقع بالإنجليزية'),
        ),
        migrations.AddField(
            model_name='branch',
            name='website_description_en',
            field=models.TextField(blank=True, verbose_name='نبذة الفرع بالإنجليزية على الموقع'),
        ),
        migrations.AddField(
            model_name='sportactivitymedia',
            name='name_en',
            field=models.CharField(blank=True, max_length=200, verbose_name='اسم الرياضة / النشاط بالإنجليزية'),
        ),
        migrations.AddField(
            model_name='sportactivitymedia',
            name='description_en',
            field=models.TextField(blank=True, verbose_name='الوصف المختصر بالإنجليزية'),
        ),
        migrations.AddField(
            model_name='academy',
            name='name_en',
            field=models.CharField(blank=True, max_length=200, verbose_name='اسم الأكاديمية بالإنجليزية للموقع'),
        ),
        migrations.AddField(
            model_name='academy',
            name='sport_activity_en',
            field=models.CharField(blank=True, max_length=150, verbose_name='النشاط الرياضي بالإنجليزية للموقع'),
        ),
        migrations.AddField(
            model_name='academy',
            name='website_description_en',
            field=models.TextField(blank=True, verbose_name='نبذة الأكاديمية بالإنجليزية على الموقع'),
        ),
        migrations.AddField(
            model_name='academymember',
            name='name_en',
            field=models.CharField(blank=True, max_length=200, verbose_name='الاسم بالإنجليزية للموقع'),
        ),
        migrations.AddField(
            model_name='academymember',
            name='job_title_en',
            field=models.CharField(blank=True, max_length=200, verbose_name='الوظيفة بالإنجليزية للموقع'),
        ),
        migrations.AddField(
            model_name='academymember',
            name='website_bio_en',
            field=models.TextField(blank=True, verbose_name='نبذة المدرب بالإنجليزية على الموقع'),
        ),
        migrations.AddField(
            model_name='shareholder',
            name='name_en',
            field=models.CharField(blank=True, max_length=200, verbose_name='الاسم بالإنجليزية للموقع'),
        ),
        migrations.AddField(
            model_name='shareholder',
            name='job_title_en',
            field=models.CharField(blank=True, max_length=200, verbose_name='الوظيفة / الصفة بالإنجليزية للموقع'),
        ),
        migrations.AddField(
            model_name='shareholder',
            name='website_bio_en',
            field=models.TextField(blank=True, verbose_name='نبذة عضو مجلس الإدارة بالإنجليزية'),
        ),
    ]
