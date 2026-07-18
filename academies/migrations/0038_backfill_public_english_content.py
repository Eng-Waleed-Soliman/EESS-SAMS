from django.db import migrations


ACTIVITY_TRANSLATIONS = {
    'كرة قدم': 'Football',
    'سباحة': 'Swimming',
    'القوس والسهم': 'Archery',
    'جمباز': 'Gymnastics',
    'جيم': 'Fitness',
    'GYM': 'Fitness',
}

ACADEMY_TRANSLATIONS = {
    'اكتيفور للخدمات الرياضيه': 'Active4 Sports Services',
    'اكتيفور للخدمات الرياضية': 'Active4 Sports Services',
    'القوس والسهم': 'Archery Academy',
    'تالنت': 'Talent',
    'تالنت سبورتس': 'Talent Sports',
    'جولدن بوي': 'Golden Boy',
    'كرة جيم': 'Kora Gym',
}

PERSON_TRANSLATIONS = {
    'أحمد سمير زكريا': 'Ahmed Samir Zakaria',
    'حسين البسيوني': 'Hussein El-Bassiouni',
    'مصطفى جاد': 'Mostafa Gad',
    'وليد محمد محمد سليمان': 'Waleed Mohamed Mohamed Soliman',
}

JOB_TRANSLATIONS = {
    'مدرب': 'Coach',
    'مدرب رئيسي': 'Head Coach',
    'مدرب لياقة بدنية': 'Fitness Coach',
    'رئيس مجلس الإدارة': 'Chairman',
    'نائب رئيس مجلس الإدارة': 'Vice Chairman',
    'عضو مجلس الإدارة': 'Board Member',
}


def backfill_english_content(apps, schema_editor):
    WebsiteSetting = apps.get_model('academies', 'WebsiteSetting')
    Branch = apps.get_model('academies', 'Branch')
    Academy = apps.get_model('academies', 'Academy')
    AcademyMember = apps.get_model('academies', 'AcademyMember')
    Shareholder = apps.get_model('academies', 'Shareholder')
    SportActivityMedia = apps.get_model('academies', 'SportActivityMedia')

    WebsiteSetting.objects.filter(about_title_en='').update(
        about_title_en='Professional Sport. Limitless Potential.',
    )

    for branch in Branch.objects.all():
        updates = {}
        if not branch.name_en:
            updates['name_en'] = branch.short_name or branch.name
        if not branch.location_en and branch.location.strip() == 'التجمع الخامس':
            updates['location_en'] = 'Fifth Settlement, Cairo'
        if updates:
            Branch.objects.filter(pk=branch.pk).update(**updates)

    for academy in Academy.objects.all():
        updates = {}
        if not academy.name_en:
            translated_name = ACADEMY_TRANSLATIONS.get(academy.name.strip())
            if translated_name:
                updates['name_en'] = translated_name
            elif academy.name.isascii():
                updates['name_en'] = academy.name
        if not academy.sport_activity_en:
            translated_activity = ACTIVITY_TRANSLATIONS.get(academy.sport_activity.strip())
            if translated_activity:
                updates['sport_activity_en'] = translated_activity
            elif academy.sport_activity.isascii():
                updates['sport_activity_en'] = academy.sport_activity
        if updates:
            Academy.objects.filter(pk=academy.pk).update(**updates)

    for member in AcademyMember.objects.all():
        updates = {}
        if not member.name_en:
            translated_name = PERSON_TRANSLATIONS.get(member.name.strip())
            if translated_name:
                updates['name_en'] = translated_name
            elif member.name.isascii():
                updates['name_en'] = member.name
        if not member.job_title_en:
            translated_job = JOB_TRANSLATIONS.get(member.job_title.strip())
            if translated_job:
                updates['job_title_en'] = translated_job
            elif member.job_title.isascii():
                updates['job_title_en'] = member.job_title
        if updates:
            AcademyMember.objects.filter(pk=member.pk).update(**updates)

    for member in Shareholder.objects.all():
        updates = {}
        if not member.name_en:
            translated_name = PERSON_TRANSLATIONS.get(member.name.strip())
            if translated_name:
                updates['name_en'] = translated_name
            elif member.name.isascii():
                updates['name_en'] = member.name
        if not member.job_title_en:
            translated_job = JOB_TRANSLATIONS.get(member.job_title.strip())
            if translated_job:
                updates['job_title_en'] = translated_job
            elif member.job_title.isascii():
                updates['job_title_en'] = member.job_title
        if updates:
            Shareholder.objects.filter(pk=member.pk).update(**updates)

    for media in SportActivityMedia.objects.all():
        updates = {}
        if not media.name_en:
            translated_name = ACTIVITY_TRANSLATIONS.get(media.name.strip())
            if translated_name:
                updates['name_en'] = translated_name
            elif media.name.isascii():
                updates['name_en'] = media.name
        if updates:
            SportActivityMedia.objects.filter(pk=media.pk).update(**updates)


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0037_public_website_english_content'),
    ]

    operations = [
        migrations.RunPython(backfill_english_content, migrations.RunPython.noop),
    ]
