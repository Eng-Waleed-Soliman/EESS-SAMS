from io import BytesIO
from pathlib import Path

from django.db import migrations
from PIL import Image, ImageOps, UnidentifiedImageError


IMAGE_FIELDS = (
    ('AppSetting', ('company_logo', 'main_screen_image')),
    ('WebsiteSetting', ('hero_image', 'about_image')),
    ('Branch', ('logo', 'image')),
    ('BranchGalleryImage', ('image',)),
    ('Facility', ('image',)),
    ('FacilityGalleryImage', ('image',)),
    ('SportActivityMedia', ('image',)),
    ('Academy', ('logo', 'website_image', 'manager_photo')),
    ('AcademyMember', ('photo',)),
    ('Shareholder', ('photo',)),
    ('CafeteriaCategory', ('image',)),
    ('CafeteriaItem', ('image',)),
)


def _webp_name(value, fallback):
    stem = Path(value or fallback).stem or fallback
    return f'{stem}.webp'


def _convert_bytes(value):
    raw = bytes(value)
    with Image.open(BytesIO(raw)) as source:
        source.seek(0)
        if (source.format or '').upper() == 'WEBP':
            return raw
        image = ImageOps.exif_transpose(source)
        has_alpha = image.mode in {'RGBA', 'LA'} or (
            image.mode == 'P' and 'transparency' in image.info
        )
        normalized = image.convert('RGBA' if has_alpha else 'RGB')
        output = BytesIO()
        normalized.save(output, format='WEBP', quality=84, method=6, exact=True)
        return output.getvalue()


def convert_stored_images_to_webp(apps, schema_editor):
    for model_name, prefixes in IMAGE_FIELDS:
        model = apps.get_model('academies', model_name)
        for prefix in prefixes:
            data_field = f'{prefix}_data'
            content_type_field = f'{prefix}_content_type'
            name_field = f'{prefix}_name'
            rows = model.objects.exclude(**{f'{data_field}__isnull': True}).only(
                'pk', data_field, content_type_field, name_field,
            )
            for row in rows.iterator(chunk_size=10):
                original = getattr(row, data_field, None)
                if not original:
                    continue
                try:
                    converted = _convert_bytes(original)
                except (UnidentifiedImageError, OSError, ValueError):
                    # Preserve invalid legacy bytes instead of making deployment fail.
                    continue
                model.objects.filter(pk=row.pk).update(**{
                    data_field: converted,
                    content_type_field: 'image/webp',
                    name_field: _webp_name(getattr(row, name_field, ''), prefix),
                })


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('academies', '0078_cafeteriastafforder_cancellation_reason_and_more'),
    ]

    operations = [
        migrations.RunPython(convert_stored_images_to_webp, migrations.RunPython.noop),
    ]
