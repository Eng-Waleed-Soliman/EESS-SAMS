UNITS = ['', 'واحد', 'اثنان', 'ثلاثة', 'أربعة', 'خمسة', 'ستة', 'سبعة', 'ثمانية', 'تسعة']
TEENS = {
    10: 'عشرة', 11: 'أحد عشر', 12: 'اثنا عشر', 13: 'ثلاثة عشر', 14: 'أربعة عشر',
    15: 'خمسة عشر', 16: 'ستة عشر', 17: 'سبعة عشر', 18: 'ثمانية عشر', 19: 'تسعة عشر',
}
TENS = {2: 'عشرون', 3: 'ثلاثون', 4: 'أربعون', 5: 'خمسون', 6: 'ستون', 7: 'سبعون', 8: 'ثمانون', 9: 'تسعون'}
HUNDREDS = {
    1: 'مائة', 2: 'مائتان', 3: 'ثلاثمائة', 4: 'أربعمائة', 5: 'خمسمائة',
    6: 'ستمائة', 7: 'سبعمائة', 8: 'ثمانمائة', 9: 'تسعمائة',
}


def _join(parts):
    return ' و'.join(part for part in parts if part)


def _under_thousand(number):
    parts = []
    hundreds, remainder = divmod(number, 100)
    if hundreds:
        parts.append(HUNDREDS[hundreds])
    if 10 <= remainder <= 19:
        parts.append(TEENS[remainder])
    else:
        units = remainder % 10
        tens = remainder // 10
        if units:
            parts.append(UNITS[units])
        if tens:
            parts.append(TENS[tens])
    return _join(parts)


def _group_words(value, singular, dual, plural):
    if value == 0:
        return ''
    if value == 1:
        return singular
    if value == 2:
        return dual
    words = _under_thousand(value)
    return f'{words} {plural if 3 <= value <= 10 else singular}'


def number_to_arabic_words(value):
    number = int(value or 0)
    if number < 0:
        return 'سالب ' + number_to_arabic_words(abs(number))
    if number == 0:
        return 'صفر'
    if number > 999_999_999:
        return str(number)
    millions, remainder = divmod(number, 1_000_000)
    thousands, units = divmod(remainder, 1_000)
    return _join([
        _group_words(millions, 'مليون', 'مليونان', 'ملايين'),
        _group_words(thousands, 'ألف', 'ألفان', 'آلاف'),
        _under_thousand(units),
    ])


def egyptian_pounds_in_words(value):
    return f'{number_to_arabic_words(value)} جنيه مصري فقط لا غير'
