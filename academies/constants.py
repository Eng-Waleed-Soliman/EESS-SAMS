OPERATION_PLACE_CHOICES = [
    ('ملعب كرة القدم #1', 'ملعب كرة القدم #1'),
    ('ملعب كرة القدم #2', 'ملعب كرة القدم #2'),
    ('ملعب الباسكت', 'ملعب الباسكت'),
    ('حمام السباحة', 'حمام السباحة'),
    ('صالة الجمباز #1', 'صالة الجمباز #1'),
    ('صالة الجمباز #2', 'صالة الجمباز #2'),
    ('صالة الجيم', 'صالة الجيم'),
    ('صالة الباليه', 'صالة الباليه'),
    ('الجاردن', 'الجاردن'),
    ('صالة الكافيتريا', 'صالة الكافيتريا'),
    ('قاعة البدروم', 'قاعة البدروم'),
]

OPERATION_SCREEN_PLACES = [
    'ملعب كرة القدم #1',
    'ملعب كرة القدم #2',
    'ملعب الباسكت',
    'الجاردن',
    'قاعة البدروم',
]

SPORT_ACTIVITY_CHOICES = [
    ('كرة قدم', 'كرة قدم'),
    ('سباحة', 'سباحة'),
    ('جمباز', 'جمباز'),
    ('جيم', 'جيم'),
    ('كرة سلة', 'كرة سلة'),
    ('كرة طائرة', 'كرة طائرة'),
    ('إيجارات ملاعب', 'إيجارات ملاعب'),
    ('Fitness', 'Fitness'),
    ('GYM', 'GYM'),
]

TRAINING_DAY_CHOICES = [
    ('السبت', 'السبت'),
    ('الأحد', 'الأحد'),
    ('الإثنين', 'الإثنين'),
    ('الثلاثاء', 'الثلاثاء'),
    ('الأربعاء', 'الأربعاء'),
    ('الخميس', 'الخميس'),
    ('الجمعة', 'الجمعة'),
]

WEEKDAY_AR = {
    5: 'السبت',
    6: 'الأحد',
    0: 'الإثنين',
    1: 'الثلاثاء',
    2: 'الأربعاء',
    3: 'الخميس',
    4: 'الجمعة',
}

def _arabic_time_label(hour, minute=0):
    suffix = 'صباحًا' if hour < 12 else 'مساءً'
    display_hour = hour % 12
    if display_hour == 0:
        display_hour = 12
    if hour == 12:
        suffix = 'ظهرًا'
    if hour == 0:
        suffix = 'منتصف الليل'
    return f'{display_hour:02d}:{minute:02d} {suffix}'


_TRAINING_TIME_POINTS = (
    [(hour, minute) for hour in range(8, 24) for minute in (0, 30)] +
    [(hour, minute) for hour in range(0, 3) for minute in (0, 30)] +
    [(3, 0)]
)

TIME_CHOICES = [(_arabic_time_label(hour, minute), _arabic_time_label(hour, minute)) for hour, minute in _TRAINING_TIME_POINTS]

TIME_LABELS = [value for value, label in TIME_CHOICES]
TIME_INDEX = {label: index for index, label in enumerate(TIME_LABELS)}

SLOT_LABELS = [f'{TIME_LABELS[i]} - {TIME_LABELS[i + 1]}' for i in range(len(TIME_LABELS) - 1)]
TRAINING_SLOT_CHOICES = [(label, label) for label in SLOT_LABELS]

PERIOD_CHOICES = [
    ('all', 'كل اليوم'),
    ('morning', 'الفترة الصباحية 8:00 صباحًا - 4:00 مساءً'),
    ('evening', 'الفترة المسائية 4:00 مساءً - 3:00 صباحًا'),
]

PERIOD_SLOT_RANGES = {
    'all': range(0, len(SLOT_LABELS)),
    'morning': range(0, 16),
    'evening': range(16, len(SLOT_LABELS)),
}

SUBSCRIPTION_TYPE_CHOICES = [
    ('fixed', 'قيمة ثابتة'),
    ('variable', 'قيمة متغيرة'),
    ('revenue_share', 'نسبة مشاركة'),
]

VARIABLE_RENT_TYPE_CHOICES = [
    ('hour', 'قيمة إيجار الساعة'),
    ('day', 'قيمة إيجار اليوم'),
]
