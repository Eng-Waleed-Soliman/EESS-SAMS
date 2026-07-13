from django.db import migrations
from django.db.models import F


MORNING_SLOT_COUNT = 16


def shift_existing_operation_slots(apps, schema_editor):
    override = apps.get_model('academies', 'AcademyOperationOverride')
    # Move to a temporary range first so the unique constraint cannot collide
    # while multiple slots for the same academy/date/place are updated.
    override.objects.all().update(
        original_slot_index=F('original_slot_index') + 1000,
    )
    override.objects.all().update(
        original_slot_index=F('original_slot_index') - (1000 - MORNING_SLOT_COUNT),
    )
    override.objects.filter(new_slot_index__isnull=False).update(
        new_slot_index=F('new_slot_index') + MORNING_SLOT_COUNT,
    )


def restore_existing_operation_slots(apps, schema_editor):
    override = apps.get_model('academies', 'AcademyOperationOverride')
    override.objects.filter(original_slot_index__gte=MORNING_SLOT_COUNT).update(
        original_slot_index=F('original_slot_index') + 1000,
    )
    override.objects.filter(original_slot_index__gte=1000 + MORNING_SLOT_COUNT).update(
        original_slot_index=F('original_slot_index') - (1000 + MORNING_SLOT_COUNT),
    )
    override.objects.filter(new_slot_index__gte=MORNING_SLOT_COUNT).update(
        new_slot_index=F('new_slot_index') - MORNING_SLOT_COUNT,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('academies', '0021_dailyexpense_created_by'),
    ]

    operations = [
        migrations.RunPython(
            shift_existing_operation_slots,
            restore_existing_operation_slots,
        ),
    ]
