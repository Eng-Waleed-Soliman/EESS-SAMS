import re
import zipfile
from datetime import date, datetime, timedelta
from xml.etree import ElementTree


_MAIN_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
_REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
_PACKAGE_REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'


HEADER_ALIASES = {
    'role': {'النوع', 'نوع العضو', 'role'},
    'name': {'الاسم', 'الاسم بالعربية', 'الاسم العربي', 'name'},
    'name_en': {'الاسم بالإنجليزية', 'الاسم بالانجليزية', 'english name', 'name en'},
    'phone': {'رقم الهاتف', 'الهاتف', 'phone'},
    'national_id': {'الرقم القومي', 'رقم قومي', 'national id'},
    'job_title': {'الوظيفة', 'الوظيفة بالعربية', 'المسمى الوظيفي', 'job title'},
    'job_title_en': {'الوظيفة بالإنجليزية', 'الوظيفة بالانجليزية', 'english job title', 'job title en'},
    'birth_date': {'تاريخ الميلاد', 'birth date'},
    'monthly_subscription': {'الاشتراك الشهري', 'اشتراك اللاعب', 'monthly subscription'},
    'is_active': {'نشط', 'الحالة', 'active'},
    'notes': {'ملاحظات', 'notes'},
    'website_bio': {'نبذة الموقع بالعربية', 'نبذة بالعربية', 'website bio'},
    'website_bio_en': {'نبذة الموقع بالإنجليزية', 'نبذة الموقع بالانجليزية', 'website bio en'},
    'is_published_on_website': {'إظهار في الموقع', 'الظهور في الموقع', 'published'},
}


def _normalise_text(value):
    value = str(value or '').strip().lower().replace('ـ', '')
    value = re.sub(r'[\s_\-]+', ' ', value)
    return value.strip()


NORMALISED_HEADERS = {
    _normalise_text(alias): field
    for field, aliases in HEADER_ALIASES.items()
    for alias in aliases
}


def _column_index(reference):
    letters = ''.join(character for character in reference if character.isalpha())
    result = 0
    for character in letters.upper():
        result = result * 26 + ord(character) - 64
    return result - 1


def _shared_strings(archive):
    try:
        root = ElementTree.fromstring(archive.read('xl/sharedStrings.xml'))
    except KeyError:
        return []
    strings = []
    for item in root.findall(f'{{{_MAIN_NS}}}si'):
        strings.append(''.join(node.text or '' for node in item.iter(f'{{{_MAIN_NS}}}t')))
    return strings


def _first_worksheet_path(archive):
    workbook = ElementTree.fromstring(archive.read('xl/workbook.xml'))
    sheet = workbook.find(f'.//{{{_MAIN_NS}}}sheet')
    if sheet is None:
        raise ValueError('ملف Excel لا يحتوي على ورقة بيانات.')
    relationship_id = sheet.attrib.get(f'{{{_REL_NS}}}id')
    relationships = ElementTree.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
    for relationship in relationships.findall(f'{{{_PACKAGE_REL_NS}}}Relationship'):
        if relationship.attrib.get('Id') == relationship_id:
            target = relationship.attrib.get('Target', '').replace('\\', '/')
            if target.startswith('/'):
                return target.lstrip('/')
            if target.startswith('xl/'):
                return target
            return f'xl/{target}'
    raise ValueError('تعذر تحديد ورقة البيانات داخل ملف Excel.')


def _cell_value(cell, shared_strings):
    cell_type = cell.attrib.get('t', '')
    if cell_type == 'inlineStr':
        return ''.join(node.text or '' for node in cell.iter(f'{{{_MAIN_NS}}}t'))
    value_node = cell.find(f'{{{_MAIN_NS}}}v')
    if value_node is None or value_node.text is None:
        return ''
    raw_value = value_node.text
    if cell_type == 's':
        try:
            return shared_strings[int(raw_value)]
        except (ValueError, IndexError):
            return ''
    if cell_type == 'b':
        return raw_value == '1'
    if cell_type in {'str', 'e'}:
        return raw_value
    try:
        number = float(raw_value)
        return int(number) if number.is_integer() else number
    except ValueError:
        return raw_value


def _worksheet_rows(uploaded_file):
    try:
        uploaded_file.seek(0)
        with zipfile.ZipFile(uploaded_file) as archive:
            shared_strings = _shared_strings(archive)
            worksheet = ElementTree.fromstring(archive.read(_first_worksheet_path(archive)))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError, OSError) as error:
        raise ValueError('اختر ملف Excel صحيحًا بصيغة XLSX.') from error

    rows = []
    for row in worksheet.findall(f'.//{{{_MAIN_NS}}}row'):
        values = {}
        for cell in row.findall(f'{{{_MAIN_NS}}}c'):
            reference = cell.attrib.get('r', '')
            values[_column_index(reference)] = _cell_value(cell, shared_strings)
        if values:
            last_column = max(values)
            rows.append((int(row.attrib.get('r', len(rows) + 1)), [values.get(index, '') for index in range(last_column + 1)]))
    return rows


def _as_boolean(value, default=True):
    if value in (None, ''):
        return default
    if isinstance(value, bool):
        return value
    normalised = _normalise_text(value)
    return normalised not in {'لا', 'غير نشط', 'false', 'no', '0', 'غير ظاهر', 'مخفي'}


def _as_date(value):
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        try:
            return date(1899, 12, 30) + timedelta(days=int(value))
        except (OverflowError, ValueError):
            return None
    text = str(value).strip()
    for pattern in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def _as_non_negative_integer(value):
    try:
        return max(0, int(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def _limited_text(value, length=None):
    text = str(value or '').strip()
    return text[:length] if length else text


def parse_academy_members_xlsx(uploaded_file, role_group):
    rows = _worksheet_rows(uploaded_file)
    header_position = None
    field_by_column = {}
    for position, (_, values) in enumerate(rows):
        candidates = {
            column: NORMALISED_HEADERS.get(_normalise_text(value))
            for column, value in enumerate(values)
        }
        candidates = {column: field for column, field in candidates.items() if field}
        if 'name' in candidates.values():
            header_position = position
            field_by_column = candidates
            break
    if header_position is None:
        raise ValueError('لم يتم العثور على صف عناوين صحيح. استخدم نموذج ملف الإضافة من البرنامج.')

    parsed_rows = []
    for excel_row_number, values in rows[header_position + 1:]:
        raw = {
            field: values[column] if column < len(values) else ''
            for column, field in field_by_column.items()
        }
        if not any(str(value or '').strip() for value in raw.values()):
            continue
        role_value = _normalise_text(raw.get('role'))
        role = 'player' if role_group == 'player' else ('admin' if role_value in {'إداري', 'اداري', 'admin'} else 'coach')
        parsed_rows.append({
            'role': role,
            'name': _limited_text(raw.get('name'), 200) or f'بدون اسم - صف {excel_row_number}',
            'name_en': _limited_text(raw.get('name_en'), 200),
            'phone': _limited_text(raw.get('phone'), 50),
            'national_id': _limited_text(raw.get('national_id'), 50),
            'job_title': '' if role == 'player' else _limited_text(raw.get('job_title'), 200),
            'job_title_en': '' if role == 'player' else _limited_text(raw.get('job_title_en'), 200),
            'birth_date': _as_date(raw.get('birth_date')) if role == 'player' else None,
            'monthly_subscription': _as_non_negative_integer(raw.get('monthly_subscription')) if role == 'player' else 0,
            'is_active': _as_boolean(raw.get('is_active'), True),
            'notes': _limited_text(raw.get('notes')),
            'website_bio': _limited_text(raw.get('website_bio')),
            'website_bio_en': _limited_text(raw.get('website_bio_en')),
            'is_published_on_website': _as_boolean(raw.get('is_published_on_website'), True),
        })
    return parsed_rows
