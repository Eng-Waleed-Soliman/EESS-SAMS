from django.db import migrations, models


def copy_old_amounts(apps, schema_editor):
    DailyBooking = apps.get_model('academies', 'DailyBooking')
    for booking in DailyBooking.objects.all():
        # للبيانات القديمة: اعتبر قيمة الحجز السابقة إجماليًا حتى لا تضيع أرقام الدخل القديمة.
        booking.total_amount = booking.amount or 0
        booking.advance_payment = 0
        booking.remaining_amount = booking.total_amount
        booking.save(update_fields=['total_amount', 'advance_payment', 'remaining_amount'])


class Migration(migrations.Migration):
    dependencies = [
        ('academies', '0006_customer_dailybooking_customer_code'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dailybooking',
            name='amount',
            field=models.PositiveIntegerField(default=0, verbose_name='قيمة إيجار الساعة'),
        ),
        migrations.AddField(
            model_name='dailybooking',
            name='advance_payment',
            field=models.PositiveIntegerField(default=0, verbose_name='مقدم الحجز'),
        ),
        migrations.AddField(
            model_name='dailybooking',
            name='total_amount',
            field=models.PositiveIntegerField(default=0, verbose_name='إجمالي قيمة الحجز'),
        ),
        migrations.AddField(
            model_name='dailybooking',
            name='remaining_amount',
            field=models.PositiveIntegerField(default=0, verbose_name='المتبقي'),
        ),
        migrations.RunPython(copy_old_amounts, migrations.RunPython.noop),
    ]
