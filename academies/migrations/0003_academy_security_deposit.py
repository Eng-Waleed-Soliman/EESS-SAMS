from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academies', '0002_expenses_cafeteria'),
    ]

    operations = [
        migrations.AddField(
            model_name='academy',
            name='security_deposit',
            field=models.PositiveIntegerField(default=0, verbose_name='مبلغ التأمين'),
        ),
    ]
