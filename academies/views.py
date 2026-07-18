import json
import re
from io import BytesIO
from calendar import monthrange
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.db import transaction
from django.db.models import Sum, Q, Count
from django.http import HttpResponse
from django.utils import timezone
from datetime import date, timedelta
from .models import Academy, DailyBooking, Customer, OperationDayCancellation, AcademyOperationOverride, Shareholder, Employee, FoundingExpense, MonthlyExpense, DailyExpense, OperatingExpense, CafeteriaCategory, CafeteriaItem, CafeteriaPurchase, CafeteriaSale, UserPermission, DailyBookingCheckout, DailyIncomeSupply, JobTitle, BonusTier, AppSetting, WebsiteSetting, Branch, Facility, SportActivityMedia, Activity, AcademyMember, AcademyMonthlyRentPayment, AcademyDepositPlan, AcademyDepositInstallment, FinancialVoucher, SecurityMovement
from .forms import AcademyForm, DailyBookingForm, ShareholderForm, EmployeeForm, FoundingExpenseForm, MonthlyExpenseForm, DailyExpenseForm, OperatingExpenseForm, CafeteriaCategoryForm, CafeteriaItemForm, CafeteriaPurchaseForm, CafeteriaSaleForm, EESSUserForm, EESSUserUpdateForm, EESSPermissionForm, JobTitleForm, BonusTierForm, AppSettingForm, WebsiteSettingForm, BranchForm, FacilityForm, SportActivityMediaForm, ActivityForm, AcademyMemberForm, DailyIncomeSupplyForm, AcademyDepositPlanForm, FinancialVoucherForm, split_values
from .constants import OPERATION_SCREEN_PLACES, TIME_INDEX, SLOT_LABELS, WEEKDAY_AR, PERIOD_CHOICES, PERIOD_SLOT_RANGES, TIME_CHOICES
from .middleware import is_cafeteria_specialist
from .branching import TRAINING_YEAR_CHOICES, selected_branch, selected_training_year


def _selected_training_year(request):
    return selected_training_year(request)


def _training_year_bounds(value):
    try:
        start_year, end_year = [int(part) for part in value.split('-', 1)]
    except (TypeError, ValueError):
        start_year, end_year = 2026, 2027
    return date(start_year, 7, 1), date(end_year, 6, 30)


def _activity_symbol(name):
    value = (name or '').lower()
    symbols = (
        (('قدم', 'football', 'soccer'), '⚽'),
        (('سلة', 'basket'), '🏀'),
        (('طائرة', 'volley'), '🏐'),
        (('تنس', 'tennis'), '🎾'),
        (('سباحة', 'swim'), '🏊'),
        (('جيم', 'لياقة', 'gym', 'fitness'), '🏋️'),
        (('قوس', 'سهم', 'archery'), '🏹'),
        (('كاراتيه', 'تايكوندو', 'كونغ', 'martial'), '🥋'),
        (('يد', 'handball'), '🤾'),
        (('بادل', 'padel'), '🎾'),
    )
    for keywords, symbol in symbols:
        if any(keyword in value for keyword in keywords):
            return symbol
    return '🏅'


def _company_short_name(company_name):
    words = re.findall(r'[A-Za-z0-9]+', company_name or '')
    if words:
        return ''.join(word[0].upper() for word in words[:6])
    return 'EESS'


PUBLIC_TEXT = {
    'ar': {
        'menu': 'القائمة',
        'nav_about': 'عن الشركة', 'nav_activities': 'الأنشطة', 'nav_branches': 'الفروع',
        'nav_academies': 'الأكاديميات', 'nav_team': 'فريقنا', 'nav_contact': 'تواصل معنا',
        'admin_login': 'دخول الإدارة', 'rights': 'جميع الحقوق محفوظة',
        'hero_default': 'نقدم منظومة رياضية متكاملة تجمع بين الإدارة الاحترافية، التدريب المتخصص، وصناعة بيئة آمنة ومحفزة لبناء أجيال أقوى.',
        'explore_academies': 'استكشف الأكاديميات', 'contact_us': 'تواصل معنا',
        'stat_branches': 'فرع رياضي', 'stat_activities': 'لعبة ونشاط',
        'stat_academies': 'أكاديمية متخصصة', 'stat_coaches': 'مدرب محترف',
        'about_kicker': 'من نحن', 'about_default_title': 'رياضة باحترافية.. مستقبل بلا حدود',
        'about_default': 'نحوّل الرياضة إلى تجربة متكاملة واحترافية. ندير الفروع والأكاديميات ونطوّر البرامج التدريبية وفق أعلى معايير الجودة، لنمنح كل لاعب مساحة حقيقية للنمو والتفوق.',
        'value_1_title': 'احترافية', 'value_1_text': 'معايير واضحة في الإدارة والتدريب',
        'value_2_title': 'تطوير مستمر', 'value_2_text': 'برامج تناسب كل مستوى ومرحلة',
        'value_3_title': 'بيئة آمنة', 'value_3_text': 'تجربة موثوقة للاعب والأسرة',
        'value_4_title': 'نتائج قابلة للقياس', 'value_4_text': 'نحو أهداف رياضية حقيقية',
        'activities_kicker': 'اكتشف شغفك', 'activities_title': 'الألعاب والأنشطة',
        'activities_intro': 'مجموعة متنوعة من الأنشطة الرياضية بإشراف فرق تدريب متخصصة داخل فروعنا.',
        'academy_singular': 'أكاديمية', 'activity_default': 'برامج تدريبية متخصصة لجميع المستويات.',
        'activities_empty': 'سيتم إضافة الأنشطة قريبًا.',
        'branches_kicker': 'أقرب إليك', 'branches_title': 'فروعنا',
        'branches_intro': 'منشآت رياضية مجهزة لتقديم تجربة تدريب وتشغيل عالية الجودة.',
        'branch_default': 'فرع متكامل لخدمة مختلف الألعاب والأنشطة الرياضية.',
        'branches_empty': 'سيتم الإعلان عن الفروع قريبًا.',
        'academies_kicker': 'تدريب يصنع الفارق', 'academies_title': 'أكاديمياتنا الرياضية',
        'academies_intro': 'اختر الأكاديمية المناسبة وابدأ رحلتك مع تدريب منظم وخبرة احترافية.',
        'academy_default': 'أكاديمية متخصصة تقدم تجربة تدريبية احترافية.',
        'learn_more': 'اعرف المزيد', 'academies_empty': 'سيتم إضافة الأكاديميات قريبًا.',
        'team_kicker': 'خبرة وشغف', 'team_title': 'مدربونا',
        'team_intro': 'طاقم تدريبي يضع تطوير اللاعب وسلامته في مقدمة الأولويات.',
        'coach': 'مدرب', 'board_kicker': 'قيادة برؤية', 'board_title': 'مجلس الإدارة',
        'board_intro': 'فريق يقود نمو الشركة ويطوّر أثرها في القطاع الرياضي.',
        'board_member': 'عضو مجلس الإدارة', 'contact_kicker': 'ابدأ الآن',
        'contact_title': 'جاهز تبدأ رحلتك الرياضية؟',
        'contact_intro': 'تواصل معنا لمعرفة البرامج المتاحة، مواعيد التدريب، وأقرب فرع إليك.',
        'phone': 'الهاتف', 'email': 'البريد الإلكتروني', 'address': 'العنوان',
        'whatsapp': 'تواصل عبر واتساب',
        'back_academies': 'العودة إلى الأكاديميات', 'about_academy': 'عن الأكاديمية',
        'professional_training': 'تدريب احترافي في', 'activity': 'النشاط', 'branch': 'الفرع',
        'academy_detail_default': 'أكاديمية متخصصة تعمل ضمن منظومة EESS لتقديم تدريب رياضي منظم وآمن وفعّال.',
        'training_team': 'فريق التدريب', 'academy_coaches': 'مدربو الأكاديمية',
        'join': 'انضم إلى', 'join_intro': 'تواصل معنا لمعرفة المواعيد والبرامج المتاحة.',
    },
    'en': {
        'menu': 'Menu',
        'nav_about': 'About', 'nav_activities': 'Activities', 'nav_branches': 'Branches',
        'nav_academies': 'Academies', 'nav_team': 'Our Team', 'nav_contact': 'Contact',
        'admin_login': 'Management Login', 'rights': 'All rights reserved',
        'hero_default': 'We deliver an integrated sports ecosystem combining professional management, specialist coaching, and a safe, inspiring environment for stronger generations.',
        'explore_academies': 'Explore Academies', 'contact_us': 'Contact Us',
        'stat_branches': 'Sports Branches', 'stat_activities': 'Sports & Activities',
        'stat_academies': 'Specialist Academies', 'stat_coaches': 'Professional Coaches',
        'about_kicker': 'Who We Are', 'about_default_title': 'Professional Sport. Limitless Potential.',
        'about_default': 'We turn sport into a complete professional experience. We manage branches and academies and develop training programmes to high quality standards, giving every athlete a real opportunity to grow and excel.',
        'value_1_title': 'Professionalism', 'value_1_text': 'Clear standards in management and coaching',
        'value_2_title': 'Continuous Growth', 'value_2_text': 'Programmes for every level and stage',
        'value_3_title': 'Safe Environment', 'value_3_text': 'A trusted experience for athletes and families',
        'value_4_title': 'Measurable Results', 'value_4_text': 'Progress towards real sporting goals',
        'activities_kicker': 'Discover Your Passion', 'activities_title': 'Sports & Activities',
        'activities_intro': 'A diverse selection of sports led by specialist coaching teams across our branches.',
        'academy_singular': 'Academies', 'activity_default': 'Specialist training programmes for every level.',
        'activities_empty': 'Activities will be added soon.',
        'branches_kicker': 'Closer to You', 'branches_title': 'Our Branches',
        'branches_intro': 'Well-equipped sports facilities delivering high-quality training and operations.',
        'branch_default': 'A fully equipped branch serving a wide range of sports and activities.',
        'branches_empty': 'Our branches will be announced soon.',
        'academies_kicker': 'Training That Makes a Difference', 'academies_title': 'Our Sports Academies',
        'academies_intro': 'Choose the right academy and begin your journey with structured training and professional expertise.',
        'academy_default': 'A specialist academy delivering a professional training experience.',
        'learn_more': 'Learn More', 'academies_empty': 'Academies will be added soon.',
        'team_kicker': 'Experience & Passion', 'team_title': 'Our Coaches',
        'team_intro': 'A coaching team committed to athlete development, wellbeing, and safety.',
        'coach': 'Coach', 'board_kicker': 'Leadership with Vision', 'board_title': 'Board of Directors',
        'board_intro': 'A leadership team driving the company’s growth and impact across the sports sector.',
        'board_member': 'Board Member', 'contact_kicker': 'Start Today',
        'contact_title': 'Ready to Begin Your Sporting Journey?',
        'contact_intro': 'Contact us to learn about available programmes, training schedules, and your nearest branch.',
        'phone': 'Phone', 'email': 'Email', 'address': 'Address',
        'whatsapp': 'Contact Us on WhatsApp',
        'back_academies': 'Back to Academies', 'about_academy': 'About the Academy',
        'professional_training': 'Professional Training in', 'activity': 'Activity', 'branch': 'Branch',
        'academy_detail_default': 'A specialist academy within the EESS ecosystem, delivering structured, safe, and effective sports training.',
        'training_team': 'Coaching Team', 'academy_coaches': 'Academy Coaches',
        'join': 'Join', 'join_intro': 'Contact us to learn about schedules and available programmes.',
    },
}


def _public_language_context(request):
    requested = request.GET.get('lang')
    if requested in PUBLIC_TEXT:
        request.session['public_language'] = requested
    language = request.session.get('public_language', 'ar')
    if language not in PUBLIC_TEXT:
        language = 'ar'
    return {
        'site_lang': language,
        'is_english': language == 'en',
        't': PUBLIC_TEXT[language],
        'language_switch_label': 'العربية' if language == 'en' else 'English',
        'language_switch_url': f'{request.path}?lang={"ar" if language == "en" else "en"}',
    }


def _localized_value(obj, arabic_field, english_field, language, fallback=''):
    if language == 'en':
        value = getattr(obj, english_field, '')
        if value and str(value).strip():
            return value
    value = getattr(obj, arabic_field, '')
    return value if value and str(value).strip() else fallback


def _prepare_public_objects(language, branding, website, branches, academies, coaches, board_members):
    branding.public_company_name = (
        branding.company_name
        if language == 'en'
        else (branding.company_name_ar or branding.company_name)
    )
    website.public_hero_title = website.hero_title_en if language == 'en' else website.hero_title_ar
    website.public_hero_text = _localized_value(website, 'hero_text', 'hero_text_en', language)
    website.public_about_title = _localized_value(website, 'about_title', 'about_title_en', language)
    website.public_about_text = _localized_value(website, 'about_text', 'about_text_en', language)
    website.public_address = _localized_value(website, 'address', 'address_en', language)
    website.public_footer_text = _localized_value(website, 'footer_text', 'footer_text_en', language)
    def prepare_branch(branch):
        if not branch:
            return
        branch.public_name = _localized_value(branch, 'display_name', 'name_en', language, branch.display_name)
        branch.public_location = _localized_value(branch, 'location', 'location_en', language)
        branch.public_description = _localized_value(
            branch, 'website_description', 'website_description_en', language,
        )

    def prepare_academy(academy):
        if not academy:
            return
        academy.public_name = _localized_value(academy, 'name', 'name_en', language, academy.name)
        academy.public_activity = _localized_value(
            academy, 'sport_activity', 'sport_activity_en', language, academy.sport_activity,
        )
        academy.public_description = _localized_value(
            academy, 'website_description', 'website_description_en', language,
        )
        prepare_branch(getattr(academy, 'branch', None))

    for branch in branches:
        prepare_branch(branch)
    for academy in academies:
        prepare_academy(academy)
    for person in coaches:
        person.public_name = _localized_value(person, 'name', 'name_en', language, person.name)
        person.public_job_title = _localized_value(person, 'job_title', 'job_title_en', language)
        person.public_bio = _localized_value(person, 'website_bio', 'website_bio_en', language)
        prepare_academy(getattr(person, 'academy', None))
    for person in board_members:
        person.public_name = _localized_value(person, 'name', 'name_en', language, person.name)
        person.public_job_title = _localized_value(person, 'job_title', 'job_title_en', language)
        person.public_bio = _localized_value(person, 'website_bio', 'website_bio_en', language)


def _can_manage_users(user):
    if user.is_superuser or user.is_staff:
        return True
    try:
        return bool(user.eess_permissions.can_users or user.eess_permissions.can_settings)
    except Exception:
        return False


def public_website(request):
    language_context = _public_language_context(request)
    language = language_context['site_lang']
    branding = AppSetting.current()
    website = WebsiteSetting.current()
    branches = list(Branch.objects.filter(is_published_on_website=True).order_by('name'))
    academies = list(
        Academy.objects.filter(is_published_on_website=True)
        .select_related('branch').order_by('name')
    )
    activity_media = {
        item.name.strip().casefold(): item
        for item in SportActivityMedia.objects.filter(is_active=True)
    }
    activity_names = []
    for academy in academies:
        name = (academy.sport_activity or '').strip()
        if name and name not in activity_names:
            activity_names.append(name)
    activities = [
        {
            'name': (
                activity_media.get(name.casefold()).name_en
                if language == 'en' and activity_media.get(name.casefold()) and activity_media.get(name.casefold()).name_en
                else (
                    next(
                        (
                            academy.sport_activity_en for academy in academies
                            if (academy.sport_activity or '').strip() == name and academy.sport_activity_en
                        ),
                        name,
                    )
                    if language == 'en' else name
                )
            ),
            'media': activity_media.get(name.casefold()),
            'academy_count': sum(1 for academy in academies if (academy.sport_activity or '').strip() == name),
            'description': (
                activity_media.get(name.casefold()).description_en
                if language == 'en' and activity_media.get(name.casefold()) and activity_media.get(name.casefold()).description_en
                else (activity_media.get(name.casefold()).description if activity_media.get(name.casefold()) else '')
            ),
        }
        for name in activity_names
    ]
    coaches = list(
        AcademyMember.objects.filter(
            role=AcademyMember.ROLE_COACH,
            is_active=True,
            is_published_on_website=True,
            academy__is_published_on_website=True,
        ).select_related('academy', 'academy__branch').order_by('academy__name', 'name')
    )
    board_members = list(
        Shareholder.objects.filter(is_published_on_website=True).order_by('name')
    )
    _prepare_public_objects(
        language, branding, website, branches, academies, coaches, board_members,
    )
    return render(request, 'public/home.html', {
        'branding': branding,
        'website': website,
        'branches': branches,
        'academies': academies,
        'activities': activities,
        'coaches': coaches,
        'board_members': board_members,
        **language_context,
    })


def public_academy_detail(request, pk):
    language_context = _public_language_context(request)
    language = language_context['site_lang']
    branding = AppSetting.current()
    website = WebsiteSetting.current()
    academy = get_object_or_404(
        Academy.objects.select_related('branch'),
        pk=pk,
        is_published_on_website=True,
    )
    coaches = academy.members.filter(
        role=AcademyMember.ROLE_COACH,
        is_active=True,
        is_published_on_website=True,
    ).order_by('name')
    branches = [academy.branch] if academy.branch else []
    _prepare_public_objects(
        language, branding, website, branches, [academy], list(coaches), [],
    )
    return render(request, 'public/academy_detail.html', {
        'branding': branding,
        'website': website,
        'academy': academy,
        'coaches': coaches,
        **language_context,
    })

def _ensure_user_profile(user):
    profile, _ = UserPermission.objects.get_or_create(user=user)
    return profile


REPORT_PERMISSION_FIELDS = {
    'employees': 'can_report_employees',
    'academies': 'can_report_income',
    'monthly_income': 'can_report_income',
    'expenses': 'can_report_expenses',
    'cafeteria': 'can_report_cafeteria',
    'security_log': 'can_security',
}

SIDEBAR_PERMISSION_MODULES = [
    {'key': 'academies', 'field': 'can_academies', 'label': 'الأكاديميات', 'buttons': ['إضافة أكاديمية', 'تعديل أكاديمية', 'حذف أكاديمية', 'المدربين والإداريين', 'اللاعبين', 'كروت التعارف']},
    {'key': 'daily_booking', 'field': 'can_daily_booking', 'label': 'الحجز اليومي', 'buttons': ['إضافة حجز', 'تعديل حجز', 'حذف حجز', 'Checkout', 'إلغاء يوم تشغيل']},
    {'key': 'academy_rent', 'field': 'can_academy_rent', 'label': 'إيجارات الأكاديميات', 'buttons': ['عرض', 'تعديل المسدد', 'تعديل التوريد للشركة', 'تصدير PDF']},
    {'key': 'operation', 'field': 'can_operation', 'label': 'التشغيل', 'buttons': ['تعديل موعد', 'حذف من التشغيل', 'نقل مكان التدريب', 'إرجاع للحالة الأصلية']},
    {'key': 'security', 'field': 'can_security', 'label': 'الأمن', 'buttons': ['الدخول', 'الخروج', 'مسح QR Code', 'تسجيل زائر']},
    {'key': 'shareholders', 'field': 'can_shareholders', 'label': 'المساهمين', 'buttons': ['إضافة مساهم', 'تعديل مساهم', 'حذف مساهم']},
    {'key': 'employees', 'field': 'can_employees', 'label': 'الموظفين', 'buttons': ['إضافة موظف', 'تعديل موظف', 'حذف موظف']},
    {'key': 'general_expenses', 'field': 'can_general_expenses', 'label': 'المصروفات العامة', 'buttons': ['مصروف شهري', 'مصروف يومي', 'مصروف تشغيل', 'تعديل', 'حذف']},
    {'key': 'accounts', 'field': 'can_accounts', 'label': 'الحسابات', 'buttons': ['عرض الحسابات', 'تصدير PDF']},
    {'key': 'cafeteria', 'field': 'can_cafeteria', 'label': 'الكافيتريا', 'buttons': ['إضافة صنف', 'فئات الأصناف', 'الشراء', 'إضافة للأوردر', 'Checkout', 'تعديل حركة بيع', 'حذف حركة بيع']},
    {'key': 'reports', 'field': 'can_reports', 'label': 'التقارير', 'buttons': ['عرض التقرير', 'تصدير PDF']},
    {'key': 'settings', 'field': 'can_settings', 'label': 'الإعدادات', 'buttons': ['المستخدمين والصلاحيات', 'الوظائف والمرتبات', 'شرائح البونص', 'هوية البرنامج', 'الأفرع', 'الملاعب والصالات', 'صور الرياضات والأنشطة']},
]

REPORT_TYPE_OPTIONS = [
    ('employees', 'بيانات الموظفين'),
    ('academies', 'بيانات الأكاديميات'),
    ('monthly_income', 'الدخل الشهري'),
    ('expenses', 'المصروفات'),
    ('cafeteria', 'الكافيتريا'),
    ('security_log', 'سجل الأمن'),
]

ARABIC_MONTH_NAMES = {
    1: 'يناير',
    2: 'فبراير',
    3: 'مارس',
    4: 'أبريل',
    5: 'مايو',
    6: 'يونيو',
    7: 'يوليو',
    8: 'أغسطس',
    9: 'سبتمبر',
    10: 'أكتوبر',
    11: 'نوفمبر',
    12: 'ديسمبر',
}

def _user_allowed_report_types(user):
    all_report_types = list(REPORT_PERMISSION_FIELDS.keys())
    if user.is_superuser or user.is_staff:
        return all_report_types
    try:
        profile = user.eess_permissions
    except Exception:
        return []
    report_permissions = getattr(profile, 'report_permissions', {}) or {}
    if report_permissions:
        legacy_permissions = {
            'employees': ('employees',),
            'academies': ('income', 'academy_rent_payments', 'deposits', 'board_members', 'shareholders'),
            'monthly_income': ('company_income', 'income', 'academy_rent_payments', 'daily_booking_monthly'),
            'expenses': ('expenses', 'monthly_expenses', 'daily_expenses', 'operating_expenses'),
            'cafeteria': ('cafeteria', 'cafeteria_inventory', 'cafeteria_sales', 'cafeteria_purchases'),
        }
        return [
            key for key, field in REPORT_PERMISSION_FIELDS.items()
            if report_permissions.get(key)
            or any(report_permissions.get(old_key) for old_key in legacy_permissions[key])
            or getattr(profile, field, False)
            or (key == 'academies' and getattr(profile, 'can_report_shareholders', False))
        ]
    if getattr(profile, 'can_reports', False):
        return all_report_types
    return [
        key for key, field in REPORT_PERMISSION_FIELDS.items()
        if getattr(profile, field, False)
        or (key == 'academies' and getattr(profile, 'can_report_shareholders', False))
    ]

def _can_access_reports(user):
    return bool(_user_allowed_report_types(user))


def _can_access_security(user):
    if user.is_superuser or user.is_staff:
        return True
    try:
        return bool(user.eess_permissions.can_security)
    except Exception:
        return False


def _security_member_type(member):
    return (
        SecurityMovement.PERSON_PLAYER
        if member.role == AcademyMember.ROLE_PLAYER
        else SecurityMovement.PERSON_STAFF
    )


def _security_member_from_qr(raw_value, academy_queryset):
    token_match = re.search(
        r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}',
        raw_value or '',
    )
    if not token_match:
        return None
    return (
        AcademyMember.objects.select_related('academy', 'academy__branch')
        .filter(qr_token=token_match.group(0), academy__in=academy_queryset, is_active=True)
        .first()
    )


@login_required
def security_home(request):
    if not _can_access_security(request.user):
        messages.error(request, 'ليس لديك صلاحية الدخول إلى موديول الأمن.')
        return redirect('dashboard')
    return render(request, 'academies/security_home.html')


@login_required
def security_movement(request, movement_type):
    if not _can_access_security(request.user):
        messages.error(request, 'ليس لديك صلاحية الدخول إلى موديول الأمن.')
        return redirect('dashboard')
    if movement_type not in {SecurityMovement.MOVEMENT_ENTRY, SecurityMovement.MOVEMENT_EXIT}:
        return redirect('security_home')

    active_branch, all_branches = selected_branch(request)
    academies = Academy.objects.select_related('branch').order_by('sport_activity', 'name')
    if not all_branches:
        academies = academies.filter(branch=active_branch)

    academy_id = request.GET.get('academy_id') or request.POST.get('academy_id')
    group = request.GET.get('group') or request.POST.get('group') or 'staff'
    if group not in {'staff', 'player'}:
        group = 'staff'
    try:
        selected_academy = academies.filter(pk=int(academy_id)).first() if academy_id else None
    except (TypeError, ValueError):
        selected_academy = None

    scanned_member = None
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'lookup_qr':
            scanned_member = _security_member_from_qr(request.POST.get('qr_value', ''), academies)
            if not scanned_member:
                messages.error(request, 'لم يتم العثور على شخص مسجل بهذا الـ QR Code.')
            else:
                selected_academy = scanned_member.academy
                group = 'player' if scanned_member.role == AcademyMember.ROLE_PLAYER else 'staff'

        elif action == 'record_member':
            member = get_object_or_404(
                AcademyMember.objects.select_related('academy', 'academy__branch').filter(
                    academy__in=academies, is_active=True,
                ),
                pk=request.POST.get('member_id'),
            )
            source = (
                SecurityMovement.SOURCE_QR
                if request.POST.get('source') == SecurityMovement.SOURCE_QR
                else SecurityMovement.SOURCE_MANUAL
            )
            SecurityMovement.objects.create(
                branch=member.academy.branch,
                academy=member.academy,
                member=member,
                academy_name=member.academy.name,
                person_name=member.name,
                person_type=_security_member_type(member),
                movement_type=movement_type,
                source=source,
                recorded_by=request.user,
            )
            messages.success(request, f'تم تسجيل {dict(SecurityMovement.MOVEMENT_CHOICES)[movement_type]} {member.name} بنجاح.')
            return redirect(
                f'{reverse("security_movement", args=[movement_type])}?academy_id={member.academy_id}&group='
                f'{"player" if member.role == AcademyMember.ROLE_PLAYER else "staff"}'
            )

        elif action == 'record_visitor':
            visitor_name = request.POST.get('visitor_name', '').strip()
            visitor_type = request.POST.get('visitor_type', '')
            notes = request.POST.get('notes', '').strip()
            if not selected_academy:
                messages.error(request, 'اختر الأكاديمية أولًا.')
            elif not visitor_name:
                messages.error(request, 'اكتب اسم الزائر.')
            elif visitor_type not in dict(SecurityMovement.PERSON_CHOICES):
                messages.error(request, 'اختر فئة الزائر.')
            else:
                SecurityMovement.objects.create(
                    branch=selected_academy.branch,
                    academy=selected_academy,
                    academy_name=selected_academy.name,
                    person_name=visitor_name,
                    person_type=visitor_type,
                    movement_type=movement_type,
                    source=SecurityMovement.SOURCE_VISITOR,
                    recorded_by=request.user,
                    notes=notes,
                )
                messages.success(request, f'تم تسجيل {dict(SecurityMovement.MOVEMENT_CHOICES)[movement_type]} الزائر {visitor_name} بنجاح.')
                return redirect(
                    f'{reverse("security_movement", args=[movement_type])}?academy_id={selected_academy.pk}&group={group}'
                )

    members = AcademyMember.objects.none()
    if selected_academy:
        members = selected_academy.members.filter(is_active=True)
        if group == 'player':
            members = members.filter(role=AcademyMember.ROLE_PLAYER)
        else:
            members = members.filter(role__in=[AcademyMember.ROLE_COACH, AcademyMember.ROLE_ADMIN])
        members = members.order_by('name')

    return render(request, 'academies/security_movement.html', {
        'movement_type': movement_type,
        'movement_label': dict(SecurityMovement.MOVEMENT_CHOICES)[movement_type],
        'academies': academies,
        'selected_academy': selected_academy,
        'group': group,
        'members': members,
        'scanned_member': scanned_member,
        'visitor_types': SecurityMovement.PERSON_CHOICES,
    })


def login_view(request):
    """Custom login screen where users enter their username and password."""
    next_url = request.GET.get('next') or request.POST.get('next') or 'dashboard'
    if request.user.is_authenticated:
        if is_cafeteria_specialist(request.user):
            return redirect('cafe_sale_list')
        return redirect(next_url if next_url != 'dashboard' else 'dashboard')
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if is_cafeteria_specialist(user):
                return redirect('cafe_sale_list')
            return redirect(next_url if next_url != 'dashboard' else 'dashboard')
        error = 'اسم المستخدم أو كلمة المرور غير صحيحة.'
    return render(request, 'academies/login.html', {
        'login_error': error,
        'login_username': request.POST.get('username', '').strip(),
        'next': next_url,
    })


def logout_view(request):
    logout(request)
    return redirect('login')


def dashboard(request):
    if not request.user.is_authenticated:
        return login_view(request)
    branch, all_branches = selected_branch(request)
    training_year = _selected_training_year(request)
    academies = Academy.objects.select_related('branch')
    if not all_branches:
        academies = academies.filter(branch=branch)
    training_start, training_end = _training_year_bounds(training_year)
    academies = academies.filter(
        contract_start_date__lte=training_end,
        contract_end_date__gte=training_start,
    )
    activity_names = list(
        academies.exclude(sport_activity='')
        .values_list('sport_activity', flat=True).distinct().order_by('sport_activity')
    )
    media_by_name = {
        media.name.strip().casefold(): media
        for media in SportActivityMedia.objects.filter(is_active=True)
    }
    activities = []
    for name in activity_names:
        media = media_by_name.get(name.strip().casefold())
        activities.append({
            'name': name,
            'media': media,
            'symbol': _activity_symbol(name),
            'academy_count': academies.filter(sport_activity=name).count(),
        })
    context = {
        'activities': activities,
        'active_branch': branch,
        'active_branch_is_all': all_branches,
        'training_year': training_year,
    }
    return render(request, 'academies/dashboard.html', context)


@login_required
def academy_list(request):
    q = request.GET.get('q', '').strip()
    training_year = _selected_training_year(request)
    branch, all_branches = selected_branch(request)
    academies = Academy.objects.all()
    if not all_branches:
        academies = academies.filter(branch=branch)
    training_start, training_end = _training_year_bounds(training_year)
    academies = academies.filter(
        contract_start_date__lte=training_end,
        contract_end_date__gte=training_start,
    )
    activity = request.GET.get('activity', '').strip()
    if activity:
        academies = academies.filter(sport_activity=activity)
    if q:
        academies = academies.filter(
            Q(name__icontains=q)
            | Q(sport_activity__icontains=q)
            | Q(manager_name__icontains=q)
            | Q(operation_place__icontains=q)
        )
    return render(request, 'academies/academy_list.html', {
        'academies': academies,
        'q': q,
        'training_year_choices': TRAINING_YEAR_CHOICES,
        'training_year': training_year,
        'activity': activity,
    })


@login_required
def academy_create(request):
    branch, all_branches = selected_branch(request)
    form = AcademyForm(request.POST or None, request.FILES or None, initial={'branch': branch})
    if form.is_valid():
        academy = form.save(commit=False)
        if academy.branch_id is None and not all_branches:
            academy.branch = branch
        academy.save()
        form.save_m2m()
        return redirect('academy_list')
    return render(request, 'academies/academy_form.html', {'form': form, 'title': 'إضافة أكاديمية'})


@login_required
def academy_update(request, pk):
    academy = get_object_or_404(Academy, pk=pk)
    old_schedule = {
        'operation_place': academy.operation_place,
        'training_days': academy.training_days,
        'training_hours': academy.training_hours,
        'has_extra_hours': academy.has_extra_hours,
        'extra_training_days': academy.extra_training_days,
        'extra_training_place': academy.extra_training_place,
        'extra_training_hours': academy.extra_training_hours,
    }
    form = AcademyForm(request.POST or None, request.FILES or None, instance=academy)
    if form.is_valid():
        academy = form.save()
        new_schedule = {
            'operation_place': academy.operation_place,
            'training_days': academy.training_days,
            'training_hours': academy.training_hours,
            'has_extra_hours': academy.has_extra_hours,
            'extra_training_days': academy.extra_training_days,
            'extra_training_place': academy.extra_training_place,
            'extra_training_hours': academy.extra_training_hours,
        }
        if old_schedule != new_schedule:
            # أي تعديل في مواعيد/أماكن الأكاديمية يسري على كل الأيام المخصصة للأكاديمية من تاريخ التعديل.
            # لذلك يتم حذف تعديلات شاشة التشغيل المستقبلية لنفس الأكاديمية حتى تظهر المواعيد الجديدة مباشرة.
            AcademyOperationOverride.objects.filter(academy=academy, booking_date__gte=date.today()).delete()
            messages.success(request, 'تم حفظ تعديل مواعيد الأكاديمية، وسيتم تطبيقها من تاريخ التعديل على الأيام المخصصة لها.')
        else:
            messages.success(request, 'تم حفظ بيانات الأكاديمية.')
        return redirect('academy_list')
    return render(request, 'academies/academy_form.html', {'form': form, 'title': 'تعديل أكاديمية'})


@login_required
def academy_delete(request, pk):
    academy = get_object_or_404(Academy, pk=pk)
    if request.method == 'POST':
        academy.delete()
        return redirect('academy_list')
    return render(request, 'academies/academy_confirm_delete.html', {'academy': academy})


def _customers_lookup_context():
    customers = []
    for c in Customer.objects.all().order_by('customer_name'):
        visits = DailyBooking.objects.filter(customer_phone=c.customer_phone).order_by('-booking_date')
        last = visits.first()
        customers.append({
            'code': c.customer_code,
            'name': c.customer_name,
            'phone': c.customer_phone,
            'national_id': c.national_id,
            'visits_count': visits.count(),
            'last_visit_date': last.booking_date.isoformat() if last else '',
            'last_visit_display': last.booking_date.strftime('%A %d/%m/%Y') if last else '',
        })
    return json.dumps(customers, ensure_ascii=False)


@login_required
def booking_list(request):
    q = request.GET.get('q', '').strip()
    booking_date_value = request.GET.get('booking_date', '').strip()
    bookings = DailyBooking.objects.all()
    active_branch, all_branches = selected_branch(request)
    if not all_branches:
        venue_names = active_branch.facilities.values_list('name', flat=True)
        bookings = bookings.filter(venue__in=venue_names)
    if booking_date_value:
        try:
            selected_booking_date = date.fromisoformat(booking_date_value)
            bookings = bookings.filter(booking_date=selected_booking_date)
        except ValueError:
            booking_date_value = ''
    if q:
        bookings = bookings.filter(
            Q(customer_name__icontains=q) |
            Q(customer_phone__icontains=q) |
            Q(venue__icontains=q)
        )
    return render(request, 'academies/booking_list.html', {
        'bookings': bookings,
        'q': q,
        'booking_date_value': booking_date_value,
    })


@login_required
def daily_income_supply(request):
    """Record cash supplied from daily bookings and show the recent supply history."""
    active_branch, all_branches = selected_branch(request)
    form = DailyIncomeSupplyForm(request.POST or None, initial={'supply_date': date.today()})
    if form.is_valid():
        supply = form.save(commit=False)
        supply.branch = None if all_branches else active_branch
        supply.save()
        messages.success(request, 'تم تسجيل توريد المبلغ النقدي بنجاح.')
        return redirect('daily_income_supply')
    supplies = DailyIncomeSupply.objects.all().order_by('-supply_date', '-created_at')
    if not all_branches:
        supplies = supplies.filter(branch=active_branch)
    return render(request, 'academies/daily_income_supply.html', {
        'form': form,
        'supplies': supplies,
        'supplied_total': supplies.aggregate(total=Sum('amount'))['total'] or 0,
    })


@login_required
def booking_create(request):
    initial = {'customer_code': Customer.next_code()}
    requested_date = (request.GET.get('date') or '').strip()
    requested_venue = (request.GET.get('venue') or '').strip()
    requested_start = (request.GET.get('start_time') or '').strip()
    requested_end = (request.GET.get('end_time') or '').strip()
    try:
        parsed_date = date.fromisoformat(requested_date)
    except ValueError:
        parsed_date = None
    if parsed_date:
        initial['booking_date'] = parsed_date
        initial['booking_dates'] = parsed_date.isoformat()
    if requested_venue in OPERATION_SCREEN_PLACES:
        initial['venue'] = requested_venue
    if (
        requested_start in TIME_INDEX and requested_end in TIME_INDEX
        and TIME_INDEX[requested_end] > TIME_INDEX[requested_start]
    ):
        initial['start_time'] = requested_start
        initial['end_time'] = requested_end
        if parsed_date:
            initial['booking_date_times'] = json.dumps([{
                'date': parsed_date.isoformat(),
                'start_time': requested_start,
                'end_time': requested_end,
            }], ensure_ascii=False)
    active_branch, all_branches = selected_branch(request)
    form = DailyBookingForm(request.POST or None, initial=initial, branch=None if all_branches else active_branch)
    if form.is_valid():
        form.save_all()
        return redirect('booking_list')
    return render(request, 'academies/booking_form.html', {'form': form, 'title': 'إضافة حجز يومي', 'customers_json': _customers_lookup_context()})


@login_required
def booking_update(request, pk):
    booking = get_object_or_404(DailyBooking, pk=pk)
    form = DailyBookingForm(request.POST or None, instance=booking)
    if form.is_valid():
        form.save_all()
        return redirect('booking_list')
    return render(request, 'academies/booking_form.html', {'form': form, 'title': 'تعديل حجز يومي', 'customers_json': _customers_lookup_context()})


@login_required
def booking_delete(request, pk):
    booking = get_object_or_404(DailyBooking, pk=pk)
    if request.method == 'POST':
        booking.delete()
        return redirect('booking_list')
    return render(request, 'academies/booking_confirm_delete.html', {'booking': booking})




def _norm(value):
    if value is None:
        return ''
    value = str(value)
    for mark in ['ً', 'ٌ', 'ٍ', 'َ', 'ُ', 'ِ', 'ّ', 'ْ', 'ـ']:
        value = value.replace(mark, '')
    value = value.replace('# ', '#').replace(' #', '#')
    return ' '.join(value.split()).strip()


def _contains_value(csv_value, target):
    target_n = _norm(target)
    return any(_norm(item) == target_n for item in split_values(csv_value))

def _time_range_indexes(start, end):
    try:
        start_i = _time_to_index(start)
        end_i = _time_to_index(end)
        if start_i is None or end_i is None:
            return []
    except KeyError:
        return []
    if end_i <= start_i:
        return []
    return list(range(start_i, end_i))


def _time_to_index(value):
    if value in TIME_INDEX:
        return TIME_INDEX[value]
    value_n = _norm(value)
    for label, idx in TIME_INDEX.items():
        if _norm(label) == value_n:
            return idx
    return None


def _slot_label_to_index(slot_label):
    if not slot_label:
        return None
    if ' - ' in slot_label:
        start = slot_label.split(' - ', 1)[0].strip()
        return _time_to_index(start)
    return _time_to_index(slot_label)


def _academy_schedule_occurrences_for_date(academy, selected_date):
    if not academy.training_schedule:
        return []
    selected_day_ar = WEEKDAY_AR[selected_date.weekday()]
    occurrences = []
    if academy.subscription_type == 'fixed':
        for place in academy.operation_places_list:
            for idx in range(len(SLOT_LABELS)):
                occurrences.append({'place': place, 'slot_index': idx, 'original_place': place, 'original_slot_index': idx, 'is_extra': False, 'hourly_rent': 0})
        return occurrences
    for row in academy.training_schedule:
        if row.get('day') != selected_day_ar:
            continue
        place = row.get('place')
        start_time = row.get('start_time')
        end_time = row.get('end_time')
        if not place:
            continue
        for idx in _time_range_indexes(start_time, end_time):
            occurrences.append({
                'place': place,
                'slot_index': idx,
                'original_place': place,
                'original_slot_index': idx,
                'is_extra': False,
                'hourly_rent': int(row.get('hourly_rent') or 0),
            })
    return occurrences


def _academy_time_indexes_for_place(academy, place):
    indexes = []
    if _contains_value(academy.operation_place, place):
        indexes += [idx for idx in (_slot_label_to_index(slot) for slot in split_values(academy.training_hours)) if idx is not None]
    if _contains_value(academy.extra_training_place, place):
        indexes += [idx for idx in (_slot_label_to_index(slot) for slot in split_values(academy.extra_training_hours)) if idx is not None]
    return indexes


@login_required
def cancel_operation_day(request):
    selected_date_text = request.POST.get('date') or request.GET.get('date')
    try:
        selected_date = date.fromisoformat(selected_date_text)
    except Exception:
        selected_date = date.today()
    if request.method == 'POST':
        branch, all_branches = selected_branch(request)
        bookings = DailyBooking.objects.filter(booking_date=selected_date)
        overrides = AcademyOperationOverride.objects.filter(booking_date=selected_date)
        if all_branches:
            bookings.delete()
            overrides.delete()
            for item in Branch.objects.all():
                OperationDayCancellation.objects.get_or_create(branch=item, cancel_date=selected_date)
        else:
            bookings.filter(branch=branch).delete()
            overrides.filter(academy__branch=branch).delete()
            OperationDayCancellation.objects.get_or_create(branch=branch, cancel_date=selected_date)
        messages.success(request, f'تم إلغاء كل حجوزات يوم {selected_date}، وتم حذف الحجز اليومي وعدم احتساب حجوزات الأكاديميات لهذا اليوم.')
    branch_value = request.POST.get('branch_id') or request.GET.get('branch_id') or 'all'
    return redirect(f'/operation/?date={selected_date.isoformat()}&period={request.POST.get("period", request.GET.get("period", "evening"))}&branch_id={branch_value}')


def _academy_occurrences_for_date(selected_date, include_cancelled=False, branch=None):
    selected_day_ar = WEEKDAY_AR[selected_date.weekday()]
    if branch is not None and OperationDayCancellation.objects.filter(
        cancel_date=selected_date,
    ).filter(Q(branch=branch) | Q(branch__isnull=True)).exists() and not include_cancelled:
        return []
    occurrences = []
    academies = Academy.objects.filter(contract_start_date__lte=selected_date, contract_end_date__gte=selected_date)
    if branch is not None:
        academies = academies.filter(branch=branch)
    override_map = {
        (ov.academy_id, _norm(ov.original_place), ov.original_slot_index): ov
        for ov in AcademyOperationOverride.objects.filter(booking_date=selected_date).select_related('academy')
    }
    for academy in academies:
        if not include_cancelled and OperationDayCancellation.objects.filter(
            cancel_date=selected_date,
        ).filter(Q(branch=academy.branch) | Q(branch__isnull=True)).exists():
            continue
        detailed_occurrences = _academy_schedule_occurrences_for_date(academy, selected_date)
        if detailed_occurrences:
            for occ in detailed_occurrences:
                key = (academy.id, _norm(occ['original_place']), occ['original_slot_index'])
                ov = override_map.get(key)
                if ov and ov.is_deleted and not include_cancelled:
                    continue
                final_place = ov.new_place if ov and ov.new_place else occ['place']
                final_idx = ov.new_slot_index if ov and ov.new_slot_index is not None else occ['slot_index']
                occurrences.append({
                    'academy': academy,
                    'place': final_place,
                    'slot_index': final_idx,
                    'original_place': occ['original_place'],
                    'original_slot_index': occ['original_slot_index'],
                    'is_extra': occ.get('is_extra', False),
                    'hourly_rent': occ.get('hourly_rent', 0),
                })
            continue
        # أساسي
        if _contains_value(academy.training_days, selected_day_ar):
            for place in split_values(academy.operation_place):
                for slot in split_values(academy.training_hours):
                    idx = _slot_label_to_index(slot)
                    if idx is None:
                        continue
                    key = (academy.id, _norm(place), idx)
                    ov = override_map.get(key)
                    if ov and ov.is_deleted and not include_cancelled:
                        continue
                    final_place = ov.new_place if ov and ov.new_place else place
                    final_idx = ov.new_slot_index if ov and ov.new_slot_index is not None else idx
                    occurrences.append({'academy': academy, 'place': final_place, 'slot_index': final_idx, 'original_place': place, 'original_slot_index': idx, 'is_extra': False})
        # إضافي
        extra_days = academy.extra_training_days or academy.training_days
        if academy.has_extra_hours and _contains_value(extra_days, selected_day_ar):
            for place in split_values(academy.extra_training_place):
                for slot in split_values(academy.extra_training_hours):
                    idx = _slot_label_to_index(slot)
                    if idx is None:
                        continue
                    key = (academy.id, _norm(place), idx)
                    ov = override_map.get(key)
                    if ov and ov.is_deleted and not include_cancelled:
                        continue
                    final_place = ov.new_place if ov and ov.new_place else place
                    final_idx = ov.new_slot_index if ov and ov.new_slot_index is not None else idx
                    occurrences.append({'academy': academy, 'place': final_place, 'slot_index': final_idx, 'original_place': place, 'original_slot_index': idx, 'is_extra': True})
    return occurrences


@login_required
def operation_card_action(request):
    if request.method != 'POST':
        return redirect('operation_screen')
    action = request.POST.get('action')
    item_type = request.POST.get('item_type')
    selected_date_text = request.POST.get('date')
    period = request.POST.get('period', 'all')
    try:
        selected_date = date.fromisoformat(selected_date_text)
    except Exception:
        selected_date = date.today()

    if item_type == 'daily':
        booking = get_object_or_404(DailyBooking, pk=request.POST.get('item_id'))
        if action == 'delete':
            # حذف الحجز اليومي يحذف أي Checkout مرتبط به تلقائيًا ويلغي قيمته من الدخل اليومي.
            booking.delete()
            messages.success(request, 'تم حذف الحجز اليومي وإلغاء قيمته من الدخل.')
        elif action == 'checkout':
            DailyBookingCheckout.objects.update_or_create(
                booking=booking,
                defaults={
                    'income_date': booking.booking_date,
                    'customer_name': booking.customer_name,
                    'customer_phone': booking.customer_phone,
                    'venue': booking.venue,
                    'booking_date': booking.booking_date,
                    'start_time': booking.start_time,
                    'end_time': booking.end_time,
                    'total_amount': booking.total_amount,
                    'advance_payment': booking.advance_payment,
                    'remaining_amount': booking.remaining_amount,
                }
            )
            messages.success(request, 'تم عمل Checkout وتسجيل قيمة الحجز في الدخل اليومي.')
            return redirect(f'/operation/?date={booking.booking_date.isoformat()}&period={period}')
        elif action == 'edit':
            new_start = request.POST.get('new_start_time')
            new_end = request.POST.get('new_end_time')
            if new_start and new_end and TIME_INDEX.get(new_end, 0) > TIME_INDEX.get(new_start, 0):
                # تحقق بسيط من التعارض بعد استبعاد نفس الحجز
                form_data = {
                    'customer_name': booking.customer_name, 'customer_phone': booking.customer_phone,
                    'national_id': booking.national_id, 'players_count': booking.players_count, 'amount': booking.amount,
                    'advance_payment': booking.advance_payment, 'total_amount': booking.total_amount, 'remaining_amount': booking.remaining_amount,
                    'venue': booking.venue, 'booking_date': booking.booking_date, 'booking_dates': booking.booking_date.isoformat(),
                    'booking_date_times': json.dumps([{'date': booking.booking_date.isoformat(), 'start_time': new_start, 'end_time': new_end}]),
                    'start_time': new_start, 'end_time': new_end, 'notes': booking.notes,
                }
                from .forms import DailyBookingForm
                form = DailyBookingForm(form_data, instance=booking)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'تم تعديل توقيت الحجز اليومي.')
                else:
                    messages.error(request, 'لم يتم تعديل الحجز: ' + ' '.join([str(e) for e in form.non_field_errors()]))
            else:
                messages.error(request, 'اختر توقيت صحيح.')

    elif item_type == 'academy':
        academy = get_object_or_404(Academy, pk=request.POST.get('item_id'))
        original_place = request.POST.get('original_place')
        try:
            original_slot_index = int(request.POST.get('original_slot_index'))
        except Exception:
            original_slot_index = -1
        if original_slot_index >= 0 and original_place:
            ov, _ = AcademyOperationOverride.objects.get_or_create(
                academy=academy, booking_date=selected_date, original_place=original_place, original_slot_index=original_slot_index,
                defaults={'new_place': original_place, 'new_slot_index': original_slot_index}
            )
            if action == 'delete':
                ov.is_deleted = True
                ov.save()
                messages.success(request, 'تم حذف حجز الأكاديمية لهذا اليوم وإلغاء قيمته من الدخل المتغير.')
            elif action == 'edit':
                new_slot = request.POST.get('new_slot_index')
                try:
                    new_slot_index = int(new_slot)
                except Exception:
                    new_slot_index = original_slot_index
                ov.is_deleted = False
                ov.new_place = original_place
                ov.new_slot_index = new_slot_index
                ov.save()
                messages.success(request, 'تم تعديل توقيت حجز الأكاديمية لهذا اليوم فقط.')
    return redirect(f'/operation/?date={selected_date.isoformat()}&period={period}')


@login_required
def operation_screen(request):
    active_branch, all_branches = selected_branch(request)
    selected_date = request.GET.get('date')
    if selected_date:
        try:
            selected_date = date.fromisoformat(selected_date)
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()

    selected_day_ar = WEEKDAY_AR[selected_date.weekday()]
    selected_period = request.GET.get('period', 'evening')
    if selected_period not in PERIOD_SLOT_RANGES:
        selected_period = 'all'
    visible_slot_indexes = list(PERIOD_SLOT_RANGES[selected_period])
    cancellation_query = OperationDayCancellation.objects.filter(cancel_date=selected_date)
    day_cancelled = (
        cancellation_query.exists()
        if all_branches
        else cancellation_query.filter(Q(branch=active_branch) | Q(branch__isnull=True)).exists()
    )

    academy_occurrences = _academy_occurrences_for_date(
        selected_date, branch=None if all_branches else active_branch
    )

    rows = []
    place_names = list(OPERATION_SCREEN_PLACES)
    if not all_branches:
        configured_places = list(active_branch.facilities.values_list('name', flat=True))
        if configured_places:
            place_names = configured_places
    for place in place_names:
        cards = []
        for slot_index in visible_slot_indexes:
            slot_label = SLOT_LABELS[slot_index]
            entries = []
            for occ in academy_occurrences:
                if _norm(occ['place']) == _norm(place) and occ['slot_index'] == slot_index:
                    academy = occ['academy']
                    entries.append({
                        'label': f'أكاديمية: {academy.name}',
                        'item_type': 'academy',
                        'item_id': academy.id,
                        'original_place': occ['original_place'],
                        'original_slot_index': occ['original_slot_index'],
                    })

            booking_qs = DailyBooking.objects.filter(venue=place, booking_date=selected_date)
            if not all_branches:
                booking_qs = booking_qs.filter(branch=active_branch)
            for booking in booking_qs:
                if slot_index in _time_range_indexes(booking.start_time, booking.end_time):
                    entries.append({
                        'label': f'حجز: {booking.customer_name}',
                        'item_type': 'daily',
                        'item_id': booking.id,
                        'original_place': place,
                        'original_slot_index': slot_index,
                        'customer_name': booking.customer_name,
                        'customer_phone': booking.customer_phone,
                        'booking_date': booking.booking_date.strftime('%d/%m/%Y'),
                        'booking_day': WEEKDAY_AR[booking.booking_date.weekday()],
                        'start_time': booking.start_time,
                        'end_time': booking.end_time,
                        'total_amount': booking.total_amount,
                        'advance_payment': booking.advance_payment,
                        'remaining_amount': booking.remaining_amount,
                        'checked_out': hasattr(booking, 'checkout'),
                    })

            has_checked_out = any(e.get('item_type') == 'daily' and e.get('checked_out') for e in entries)
            has_academy = any(e.get('item_type') == 'academy' for e in entries)
            has_daily = any(e.get('item_type') == 'daily' for e in entries)
            if has_checked_out:
                card_class = 'checkout-busy'
            elif has_academy:
                card_class = 'academy-busy'
            elif has_daily:
                card_class = 'daily-busy'
            else:
                card_class = ''
            cards.append({
                'time': slot_label,
                'slot_index': slot_index,
                'start_time': TIME_CHOICES[slot_index][0],
                'end_time': TIME_CHOICES[slot_index + 1][0],
                'busy': bool(entries),
                'card_class': card_class,
                'entries': entries,
            })
        rows.append({'place': place, 'cards': cards})

    return render(request, 'academies/operation_screen.html', {
        'selected_date': selected_date,
        'selected_day_ar': selected_day_ar,
        'selected_period': selected_period,
        'period_choices': PERIOD_CHOICES,
        'rows': rows,
        'day_cancelled': day_cancelled,
        'slot_choices': [(i, SLOT_LABELS[i]) for i in visible_slot_indexes],
        'time_choices': TIME_CHOICES,
        'active_branch': active_branch,
        'active_branch_is_all': all_branches,
    })


@login_required
def daily_income(request):
    return redirect('/reports/?report_type=monthly_income')


def _legacy_daily_income(request):
    selected_date = request.GET.get('date')
    if selected_date:
        try:
            selected_date = date.fromisoformat(selected_date)
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()

    view_mode = request.GET.get('view', 'daily')

    if request.method == 'POST' and view_mode == 'monthly':
        days_count = monthrange(selected_date.year, selected_date.month)[1]
        for day_no in range(1, days_count + 1):
            current_date = date(selected_date.year, selected_date.month, day_no)
            raw_amount = (request.POST.get(f'supply_{current_date.isoformat()}') or '0').strip()
            try:
                amount = max(0, int(raw_amount or 0))
            except ValueError:
                amount = 0
            if amount:
                DailyIncomeSupply.objects.update_or_create(
                    supply_date=current_date,
                    defaults={'amount': amount},
                )
            else:
                DailyIncomeSupply.objects.filter(supply_date=current_date).delete()
        return redirect(f"{request.path}?date={selected_date.isoformat()}&view=monthly")

    rows = DailyBookingCheckout.objects.filter(income_date=selected_date).order_by('start_time', 'customer_name')
    total_income = rows.aggregate(total=Sum('total_amount'))['total'] or 0
    total_advance = rows.aggregate(total=Sum('advance_payment'))['total'] or 0
    total_remaining = rows.aggregate(total=Sum('remaining_amount'))['total'] or 0

    month_rows = []
    month_income_total = 0
    month_expense_total = 0
    month_profit_total = 0
    month_supply_total = 0
    month_treasury_remaining = 0
    if view_mode == 'monthly':
        days_count = monthrange(selected_date.year, selected_date.month)[1]
        supply_map = {
            item.supply_date: item.amount
            for item in DailyIncomeSupply.objects.filter(
                supply_date__year=selected_date.year,
                supply_date__month=selected_date.month,
            )
        }
        for day_no in range(1, days_count + 1):
            current_date = date(selected_date.year, selected_date.month, day_no)
            day_income = DailyBookingCheckout.objects.filter(income_date=current_date).aggregate(total=Sum('total_amount'))['total'] or 0
            day_expenses = (DailyExpense.objects.filter(expense_date=current_date).aggregate(total=Sum('amount'))['total'] or 0) + (OperatingExpense.objects.filter(expense_date=current_date).aggregate(total=Sum('amount'))['total'] or 0)
            net_profit = int(day_income) - int(day_expenses)
            day_supply = int(supply_map.get(current_date, 0) or 0)
            month_treasury_remaining = month_treasury_remaining + int(day_income) - day_supply
            month_income_total += int(day_income)
            month_expense_total += int(day_expenses)
            month_profit_total += int(net_profit)
            month_supply_total += day_supply
            month_rows.append({
                'date': current_date,
                'day_name': WEEKDAY_AR[current_date.weekday()],
                'income': day_income,
                'expenses': day_expenses,
                'net_profit': net_profit,
                'supply': day_supply,
                'treasury_remaining': month_treasury_remaining,
            })

    return render(request, 'academies/daily_income.html', {
        'selected_date': selected_date,
        'selected_day_ar': WEEKDAY_AR[selected_date.weekday()],
        'view_mode': view_mode,
        'rows': rows,
        'total_income': total_income,
        'total_advance': total_advance,
        'total_remaining': total_remaining,
        'month_rows': month_rows,
        'month_income_total': month_income_total,
        'month_expense_total': month_expense_total,
        'month_profit_total': month_profit_total,
        'month_supply_total': month_supply_total,
        'month_treasury_remaining': month_treasury_remaining,
        'month_name': ARABIC_MONTH_NAMES[selected_date.month],
    })


@login_required
def shareholder_list(request):
    q = request.GET.get('q', '').strip()
    shareholders = Shareholder.objects.all()
    if q:
        shareholders = (Shareholder.objects.filter(name__icontains=q) |
                        Shareholder.objects.filter(phone__icontains=q) |
                        Shareholder.objects.filter(national_id__icontains=q))
    return render(request, 'academies/shareholder_list.html', {'shareholders': shareholders, 'q': q})

@login_required
def shareholder_create(request):
    form = ShareholderForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('shareholder_list')
    return render(request, 'academies/simple_form.html', {'form': form, 'title': 'إضافة مساهم', 'back_url': 'shareholder_list'})

@login_required
def shareholder_update(request, pk):
    shareholder = get_object_or_404(Shareholder, pk=pk)
    form = ShareholderForm(request.POST or None, instance=shareholder)
    if form.is_valid():
        form.save()
        return redirect('shareholder_list')
    return render(request, 'academies/simple_form.html', {'form': form, 'title': 'تعديل مساهم', 'back_url': 'shareholder_list'})

@login_required
def shareholder_delete(request, pk):
    shareholder = get_object_or_404(Shareholder, pk=pk)
    if request.method == 'POST':
        shareholder.delete()
        return redirect('shareholder_list')
    return render(request, 'academies/simple_confirm_delete.html', {'object': shareholder, 'title': 'حذف مساهم', 'back_url': 'shareholder_list'})

@login_required
def employee_list(request):
    q = request.GET.get('q', '').strip()
    employees = Employee.objects.all()
    active_branch, all_branches = selected_branch(request)
    if not all_branches:
        employees = employees.filter(branch=active_branch)
    if q:
        employees = employees.filter(
            Q(name__icontains=q) | Q(phone__icontains=q) |
            Q(national_id__icontains=q) | Q(job_title__icontains=q)
        )
    return render(request, 'academies/employee_list.html', {'employees': employees, 'q': q})

@login_required
def employee_create(request):
    active_branch, all_branches = selected_branch(request)
    form = EmployeeForm(request.POST or None)
    if form.is_valid():
        employee = form.save(commit=False)
        if employee.branch_id is None and not all_branches:
            employee.branch = active_branch
        employee.save()
        return redirect('employee_list')
    return render(request, 'academies/simple_form.html', {'form': form, 'title': 'إضافة موظف', 'back_url': 'employee_list'})

@login_required
def employee_update(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    form = EmployeeForm(request.POST or None, instance=employee)
    if form.is_valid():
        form.save()
        return redirect('employee_list')
    return render(request, 'academies/simple_form.html', {'form': form, 'title': 'تعديل موظف', 'back_url': 'employee_list'})

@login_required
def employee_delete(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        employee.delete()
        return redirect('employee_list')
    return render(request, 'academies/simple_confirm_delete.html', {'object': employee, 'title': 'حذف موظف', 'back_url': 'employee_list'})



def _month_bounds(month_text):
    if month_text:
        try:
            year, month = [int(x) for x in month_text.split('-')[:2]]
        except Exception:
            today = date.today(); year, month = today.year, today.month
    else:
        today = date.today(); year, month = today.year, today.month
    from calendar import monthrange
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return year, month, start, end, f'{year:04d}-{month:02d}'


def _generic_crud_list(request, model, template, context_name, search_fields=None):
    q = request.GET.get('q', '').strip()
    objects = model.objects.all()
    active_branch, all_branches = selected_branch(request)
    if not all_branches and any(field.name == 'branch' for field in model._meta.fields):
        objects = objects.filter(branch=active_branch)
    if q and search_fields:
        query = None
        for field in search_fields:
            part = {f'{field}__icontains': q}
            query = Q(**part) if query is None else query | Q(**part)
        objects = objects.filter(query)
    return render(request, template, {context_name: objects, 'q': q})


def _generic_form(request, form_class, title, back_url, instance=None):
    form = form_class(request.POST or None, request.FILES or None, instance=instance)
    if form.is_valid():
        obj = form.save(commit=False)
        active_branch, all_branches = selected_branch(request)
        if hasattr(obj, 'branch_id') and not all_branches:
            obj.branch = active_branch
        obj.save()
        if hasattr(form, 'save_m2m'):
            form.save_m2m()
        return redirect(back_url)
    return render(request, 'academies/simple_form.html', {'form': form, 'title': title, 'back_url': back_url})


def _generic_delete(request, obj, title, back_url):
    if request.method == 'POST':
        obj.delete()
        return redirect(back_url)
    return render(request, 'academies/simple_confirm_delete.html', {'object': obj, 'title': title, 'back_url': back_url})


@login_required
def general_expenses_home(request):
    monthly_total = MonthlyExpense.objects.aggregate(total=Sum('amount'))['total'] or 0
    daily_total = DailyExpense.objects.aggregate(total=Sum('amount'))['total'] or 0
    operating_total = OperatingExpense.objects.aggregate(total=Sum('amount'))['total'] or 0
    return render(request, 'academies/general_expenses.html', {
        'monthly_total': monthly_total,
        'daily_total': daily_total,
        'operating_total': operating_total,
    })

@login_required
def founding_expense_list(request):
    return _generic_crud_list(request, FoundingExpense, 'academies/founding_expense_list.html', 'expenses', ['title', 'notes'])

@login_required
def founding_expense_create(request):
    return _generic_form(request, FoundingExpenseForm, 'إضافة مصروف تأسيس', 'founding_expense_list')

@login_required
def founding_expense_update(request, pk):
    return _generic_form(request, FoundingExpenseForm, 'تعديل مصروف تأسيس', 'founding_expense_list', get_object_or_404(FoundingExpense, pk=pk))

@login_required
def founding_expense_delete(request, pk):
    return _generic_delete(request, get_object_or_404(FoundingExpense, pk=pk), 'حذف مصروف تأسيس', 'founding_expense_list')

@login_required
def monthly_expense_list(request):
    return _generic_crud_list(request, MonthlyExpense, 'academies/monthly_expense_list.html', 'expenses', ['title', 'notes'])

@login_required
def monthly_expense_create(request):
    return _generic_form(request, MonthlyExpenseForm, 'إضافة مصروف شهري', 'monthly_expense_list')

@login_required
def monthly_expense_update(request, pk):
    return _generic_form(request, MonthlyExpenseForm, 'تعديل مصروف شهري', 'monthly_expense_list', get_object_or_404(MonthlyExpense, pk=pk))

@login_required
def monthly_expense_delete(request, pk):
    return _generic_delete(request, get_object_or_404(MonthlyExpense, pk=pk), 'حذف مصروف شهري', 'monthly_expense_list')


@login_required
def daily_expense_list(request):
    return _generic_crud_list(request, DailyExpense, 'academies/daily_expense_list.html', 'expenses', ['title', 'notes'])

@login_required
def daily_expense_create(request):
    selected_date = request.GET.get('date', '').strip()
    try:
        initial_date = date.fromisoformat(selected_date) if selected_date else date.today()
    except ValueError:
        initial_date = date.today()
    form = DailyExpenseForm(
        request.POST or None,
        initial={'expense_date': initial_date},
    )
    if form.is_valid():
        expense = form.save(commit=False)
        expense.created_by = request.user
        active_branch, all_branches = selected_branch(request)
        if not all_branches:
            expense.branch = active_branch
        expense.save()
        messages.success(request, 'تم تسجيل المصروف اليومي بنجاح.')
        return redirect('daily_expense_list')
    return render(request, 'academies/simple_form.html', {
        'form': form,
        'title': 'إضافة مصروف يومي',
        'back_url_path': f'/operation/?date={initial_date.isoformat()}',
    })

@login_required
def daily_expense_update(request, pk):
    return _generic_form(request, DailyExpenseForm, 'تعديل مصروف يومي', 'daily_expense_list', get_object_or_404(DailyExpense, pk=pk))

@login_required
def daily_expense_delete(request, pk):
    return _generic_delete(request, get_object_or_404(DailyExpense, pk=pk), 'حذف مصروف يومي', 'daily_expense_list')


@login_required
def operating_expense_list(request):
    return _generic_crud_list(request, OperatingExpense, 'academies/operating_expense_list.html', 'expenses', ['title', 'notes'])

@login_required
def operating_expense_create(request):
    return _generic_form(request, OperatingExpenseForm, 'إضافة مصروف تشغيل', 'operating_expense_list')

@login_required
def operating_expense_update(request, pk):
    return _generic_form(request, OperatingExpenseForm, 'تعديل مصروف تشغيل', 'operating_expense_list', get_object_or_404(OperatingExpense, pk=pk))

@login_required
def operating_expense_delete(request, pk):
    return _generic_delete(request, get_object_or_404(OperatingExpense, pk=pk), 'حذف مصروف تشغيل', 'operating_expense_list')


@login_required
def cafe_item_list(request):
    q = request.GET.get('q', '').strip()
    items = CafeteriaItem.objects.select_related('category').all().order_by('category__code', 'code', 'name')
    active_branch, all_branches = selected_branch(request)
    if not all_branches:
        items = items.filter(branch=active_branch)
    if q:
        items = items.filter(Q(name__icontains=q) | Q(notes__icontains=q) | Q(category__name__icontains=q))
    return render(request, 'academies/cafe_item_list.html', {'items': items, 'q': q})

@login_required
def cafe_category_list(request):
    q = request.GET.get('q', '').strip()
    categories = CafeteriaCategory.objects.all().order_by('code', 'name')
    if q:
        categories = categories.filter(Q(name__icontains=q) | Q(notes__icontains=q))
    return render(request, 'academies/cafe_category_list.html', {'categories': categories, 'q': q})

@login_required
def cafe_category_create(request):
    return _generic_form(request, CafeteriaCategoryForm, 'إضافة فئة أصناف', 'cafe_category_list')

@login_required
def cafe_category_update(request, pk):
    return _generic_form(request, CafeteriaCategoryForm, 'تعديل فئة أصناف', 'cafe_category_list', get_object_or_404(CafeteriaCategory, pk=pk))

@login_required
def cafe_category_delete(request, pk):
    return _generic_delete(request, get_object_or_404(CafeteriaCategory, pk=pk), 'حذف فئة أصناف', 'cafe_category_list')

@login_required
def cafe_settings(request):
    return render(request, 'academies/cafe_settings.html', {
        'category_count': CafeteriaCategory.objects.count(),
        'item_count': CafeteriaItem.objects.count(),
    })

@login_required
def cafe_stock_adjust(request):
    items = CafeteriaItem.objects.select_related('category').all().order_by('category__code', 'code', 'name')
    if request.method == 'POST':
        for item in items:
            value = request.POST.get(f'quantity_{item.id}', '').strip()
            if value != '':
                try:
                    desired_quantity = max(0, int(value))
                    quantity_before_adjustment = (
                        item.opening_quantity + item.purchased_quantity - item.sold_quantity
                    )
                    item.stock_adjustment = desired_quantity - quantity_before_adjustment
                    item.save(update_fields=['stock_adjustment'])
                except ValueError:
                    messages.error(request, f'قيمة المخزون للصنف {item.name} غير صحيحة.')
                    return redirect('cafe_stock_adjust')
        messages.success(request, 'تم حفظ كميات المخزون بنجاح.')
        return redirect('cafe_item_list')
    return render(request, 'academies/cafe_stock_adjust.html', {'items': items})

@login_required
def cafe_sale_prices(request):
    items = CafeteriaItem.objects.select_related('category').all().order_by('category__code', 'code', 'name')
    if request.method == 'POST':
        for item in items:
            value = request.POST.get(f'price_{item.id}', '').strip()
            if value != '':
                try:
                    item.sale_price = max(0, int(value))
                    item.save(update_fields=['sale_price'])
                except ValueError:
                    messages.error(request, f'سعر البيع للصنف {item.name} غير صحيح.')
                    return redirect('cafe_sale_prices')
        messages.success(request, 'تم حفظ أسعار البيع بنجاح.')
        return redirect('cafe_item_list')
    return render(request, 'academies/cafe_sale_prices.html', {'items': items})


@login_required
def cafe_inventory(request):
    today = date.today()
    preset = request.GET.get('preset', '').strip()
    if preset == 'today':
        date_from = date_to = today
    elif preset == 'month':
        date_from = today.replace(day=1)
        date_to = today
    else:
        try:
            date_from = date.fromisoformat(request.GET.get('date_from', ''))
        except (TypeError, ValueError):
            date_from = today.replace(day=1)
        try:
            date_to = date.fromisoformat(request.GET.get('date_to', ''))
        except (TypeError, ValueError):
            date_to = today
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    rows = []
    for item in CafeteriaItem.objects.select_related('category').order_by('category__code', 'code', 'name'):
        purchased_before = item.purchases.filter(purchase_date__lt=date_from).aggregate(total=Sum('quantity'))['total'] or 0
        sold_before = item.sales.filter(sale_date__lt=date_from).aggregate(total=Sum('quantity'))['total'] or 0
        purchased = item.purchases.filter(purchase_date__range=(date_from, date_to)).aggregate(total=Sum('quantity'))['total'] or 0
        sold = item.sales.filter(sale_date__range=(date_from, date_to)).aggregate(total=Sum('quantity'))['total'] or 0
        opening_balance = item.opening_quantity + purchased_before - sold_before
        rows.append({
            'item': item,
            'opening_balance': opening_balance,
            'purchased_quantity': purchased,
            'sold_quantity': sold,
            'remaining_quantity': opening_balance + purchased - sold,
        })
    return render(request, 'academies/cafe_inventory.html', {
        'rows': rows,
        'date_from': date_from,
        'date_to': date_to,
        'preset': preset,
    })


@login_required
def cafe_menu(request):
    groups = []
    for category in CafeteriaCategory.objects.prefetch_related('items').order_by('code', 'name'):
        rows = [
            {'item': item, 'available_quantity': item.stock_quantity, 'low_stock': item.stock_quantity < 5}
            for item in category.items.all().order_by('code', 'name')
        ]
        if rows:
            groups.append({'category': category, 'label': f'{category.code} - {category.name}', 'rows': rows})
    orphan_rows = [
        {'item': item, 'available_quantity': item.stock_quantity, 'low_stock': item.stock_quantity < 5}
        for item in CafeteriaItem.objects.filter(category__isnull=True).order_by('code', 'name')
    ]
    if orphan_rows:
        groups.append({'category': None, 'label': 'بدون فئة', 'rows': orphan_rows})
    return render(request, 'academies/cafe_menu.html', {'groups': groups})

@login_required
def cafe_item_create(request):
    return _generic_form(request, CafeteriaItemForm, 'إضافة صنف كافيتريا', 'cafe_item_list')

@login_required
def cafe_item_update(request, pk):
    return _generic_form(request, CafeteriaItemForm, 'تعديل صنف كافيتريا', 'cafe_item_list', get_object_or_404(CafeteriaItem, pk=pk))

@login_required
def cafe_item_delete(request, pk):
    return _generic_delete(request, get_object_or_404(CafeteriaItem, pk=pk), 'حذف صنف كافيتريا', 'cafe_item_list')


@login_required
def cafe_purchase_list(request):
    purchases = CafeteriaPurchase.objects.select_related('item').all()
    return render(request, 'academies/cafe_purchase_list.html', {'purchases': purchases})

@login_required
def cafe_purchase_create(request):
    return _generic_form(request, CafeteriaPurchaseForm, 'إضافة حركة شراء كافيتريا', 'cafe_purchase_list')

@login_required
def cafe_purchase_update(request, pk):
    return _generic_form(request, CafeteriaPurchaseForm, 'تعديل حركة شراء كافيتريا', 'cafe_purchase_list', get_object_or_404(CafeteriaPurchase, pk=pk))

@login_required
def cafe_purchase_delete(request, pk):
    return _generic_delete(request, get_object_or_404(CafeteriaPurchase, pk=pk), 'حذف حركة شراء كافيتريا', 'cafe_purchase_list')


@login_required
def cafe_sale_list(request):
    form = CafeteriaSaleForm(request.POST or None)
    if request.method == 'POST':
        raw_order = request.POST.get('order_items', '').strip()
        if raw_order:
            try:
                order_items = json.loads(raw_order)
            except json.JSONDecodeError:
                order_items = []
            sale_date = request.POST.get('sale_date') or date.today().isoformat()
            notes = request.POST.get('notes', '').strip()
            if not order_items:
                messages.error(request, 'أضف صنف واحد على الأقل قبل Checkout.')
                return redirect('cafe_sale_list')
            prepared_rows = []
            try:
                for row in order_items:
                    item = get_object_or_404(CafeteriaItem, pk=row.get('item_id'))
                    quantity = max(1, int(row.get('quantity') or 1))
                    unit_price = item.sale_price
                    prepared_rows.append((item, quantity, unit_price))
            except (TypeError, ValueError):
                messages.error(request, 'بيانات الأوردر غير صحيحة.')
                return redirect('cafe_sale_list')
            requested_by_item = {}
            for item, quantity, unit_price in prepared_rows:
                requested_by_item[item.id] = requested_by_item.get(item.id, 0) + quantity
                if requested_by_item[item.id] > item.stock_quantity:
                    messages.error(request, f'المخزون غير كاف للصنف {item.name}. المتاح: {item.stock_quantity}.')
                    return redirect('cafe_sale_list')
            with transaction.atomic():
                for item, quantity, unit_price in prepared_rows:
                    CafeteriaSale.objects.create(
                        item=item,
                        sale_date=sale_date,
                        quantity=quantity,
                        unit_price=unit_price,
                        notes=notes,
                    )
            created_count = len(prepared_rows)
            messages.success(request, f'تم Checkout للأوردر وحفظ {created_count} صنف بنجاح.')
            return redirect('cafe_sale_list')
        if form.is_valid():
            sale = form.save(commit=False)
            sale.unit_price = sale.item.sale_price
            sale.save()
            messages.success(request, 'تم تسجيل البيع بنجاح.')
            return redirect('cafe_sale_list')

    sales = CafeteriaSale.objects.select_related('item', 'item__category').all()[:50]
    today = date.today()
    today_sales = CafeteriaSale.objects.filter(sale_date=today).select_related('item')
    today_total = sum(sale.total_amount for sale in today_sales)
    today_profit = sum(sale.estimated_profit for sale in today_sales)
    category_id = request.GET.get('category', '').strip()
    categories = list(CafeteriaCategory.objects.all().order_by('code', 'name'))
    item_queryset = CafeteriaItem.objects.select_related('category').all().order_by('category__code', 'code', 'name')
    low_stock_items = [item for item in CafeteriaItem.objects.select_related('category').all().order_by('category__code', 'code', 'name') if item.is_low_stock]
    items = [
        {
            'id': item.id,
            'code': item.code,
            'name': item.name,
            'category_id': item.category_id,
            'category_name': item.category.name if item.category_id else 'بدون فئة',
            'sale_price': item.sale_price,
            'stock_quantity': item.stock_quantity,
        }
        for item in item_queryset
    ]
    return render(request, 'academies/cafe_sale_list.html', {
        'form': form,
        'sales': sales,
        'items': items,
        'categories': categories,
        'selected_category': category_id,
        'today_total': today_total,
        'today_profit': today_profit,
        'today_count': today_sales.count(),
        'low_stock_items': low_stock_items,
    })

@login_required
def cafe_sale_create(request):
    form = CafeteriaSaleForm(request.POST or None)
    if form.is_valid():
        sale = form.save(commit=False)
        sale.unit_price = sale.item.sale_price
        sale.save()
        messages.success(request, 'تم حفظ حركة البيع بنجاح.')
        return redirect('cafe_sale_list')
    return render(request, 'academies/cafe_sale_form.html', {'form': form, 'title': 'إضافة حركة بيع كافيتريا', 'back_url': 'cafe_sale_list', 'items': list(CafeteriaItem.objects.values('id', 'sale_price'))})

@login_required
def cafe_sale_update(request, pk):
    sale_obj = get_object_or_404(CafeteriaSale, pk=pk)
    form = CafeteriaSaleForm(request.POST or None, instance=sale_obj)
    if form.is_valid():
        sale = form.save(commit=False)
        sale.unit_price = sale.item.sale_price
        sale.save()
        messages.success(request, 'تم تعديل حركة البيع بنجاح.')
        return redirect('cafe_sale_list')
    return render(request, 'academies/cafe_sale_form.html', {'form': form, 'title': 'تعديل حركة بيع كافيتريا', 'back_url': 'cafe_sale_list', 'items': list(CafeteriaItem.objects.values('id', 'sale_price'))})

@login_required
def cafe_sale_delete(request, pk):
    return _generic_delete(request, get_object_or_404(CafeteriaSale, pk=pk), 'حذف حركة بيع كافيتريا', 'cafe_sale_list')



def _calculate_fixed_income_with_operation_changes(academy, year, month):
    # توزيع الاشتراك الثابت على عدد ساعات التشغيل في الشهر حتى يتم خصم أي ساعة/يوم ملغي من الدخل.
    if academy.subscription_type != 'fixed':
        return academy.monthly_subscription
    from calendar import monthrange
    total_planned = 0
    active_planned = 0
    for day_number in range(1, monthrange(year, month)[1] + 1):
        current = date(year, month, day_number)
        if not (academy.contract_start_date <= current <= academy.contract_end_date):
            continue
        # احسب الجدول الأصلي بدون إلغاءات.
        total_planned += len([o for o in _academy_occurrences_for_date(current, include_cancelled=True) if o['academy'].id == academy.id])
        active_planned += len([o for o in _academy_occurrences_for_date(current) if o['academy'].id == academy.id])
    if total_planned <= 0:
        return int(academy.monthly_subscription or 0)
    return int((academy.monthly_subscription or 0) * active_planned / total_planned)


def _calculate_variable_income_with_operation_changes(academy, year, month):
    # حساب الاشتراك المتغير مع استبعاد الأيام الملغاة وحجوزات الأكاديمية المحذوفة في شاشة التشغيل.
    if academy.subscription_type != 'variable':
        return academy.monthly_subscription
    from calendar import monthrange
    rent_value = int(academy.variable_rent_value or 0)
    total_units = 0
    for day_number in range(1, monthrange(year, month)[1] + 1):
        current = date(year, month, day_number)
        if not (academy.contract_start_date <= current <= academy.contract_end_date):
            continue
        if OperationDayCancellation.objects.filter(cancel_date=current).filter(
            Q(branch=academy.branch) | Q(branch__isnull=True)
        ).exists():
            continue
        occs = [o for o in _academy_occurrences_for_date(current) if o['academy'].id == academy.id]
        if academy.variable_rent_type == 'hour':
            total_units += len(occs)
        elif academy.variable_rent_type == 'day' and occs:
            total_units += 1
    return int(rent_value * total_units)


def _facility_rent_for_place(place, rent_type, fallback_value):
    place_norm = _norm(place)
    facility = next((item for item in Facility.objects.all() if _norm(item.name) == place_norm), None)
    if not facility:
        return int(fallback_value or 0)
    if rent_type == 'hour':
        return int(facility.hourly_rent or fallback_value or 0)
    if rent_type == 'day':
        return int(facility.daily_rent or fallback_value or 0)
    return int(fallback_value or 0)


def _calculate_variable_income_by_facility(academy, year, month):
    if academy.subscription_type != 'variable':
        return int(academy.monthly_subscription or 0)
    fallback_value = int(academy.variable_rent_value or 0)
    total = 0
    for day_number in range(1, monthrange(year, month)[1] + 1):
        current = date(year, month, day_number)
        if not (academy.contract_start_date <= current <= academy.contract_end_date):
            continue
        if OperationDayCancellation.objects.filter(cancel_date=current).filter(
            Q(branch=academy.branch) | Q(branch__isnull=True)
        ).exists():
            continue
        occs = [o for o in _academy_occurrences_for_date(current) if o['academy'].id == academy.id]
        if academy.variable_rent_type == 'hour':
            for occ in occs:
                hourly_rate = int(occ.get('hourly_rent') or 0) or _facility_rent_for_place(occ['place'], 'hour', fallback_value)
                total += Decimal(hourly_rate) / Decimal(2)
        elif academy.variable_rent_type == 'day' and occs:
            for place in sorted({_norm(occ['place']): occ['place'] for occ in occs}.values()):
                total += _facility_rent_for_place(place, 'day', fallback_value)
    return int(total)


def _monthly_academy_operation_counts(year, month, academies):
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    academy_ids = [academy.id for academy in academies]
    cancelled_dates = set(
        OperationDayCancellation.objects.filter(
            cancel_date__range=(start, end)
        ).values_list('branch_id', 'cancel_date')
    )
    deleted_overrides = {
        (item.academy_id, item.booking_date, _norm(item.original_place), item.original_slot_index)
        for item in AcademyOperationOverride.objects.filter(
            academy_id__in=academy_ids,
            booking_date__range=(start, end),
            is_deleted=True,
        )
    }
    total_counts = {}
    active_counts = {}
    active_days = {}
    for day_number in range(1, monthrange(year, month)[1] + 1):
        current = date(year, month, day_number)
        day_ar = WEEKDAY_AR[current.weekday()]
        for academy in academies:
            is_cancelled = (academy.branch_id, current) in cancelled_dates or (None, current) in cancelled_dates
            if not (academy.contract_start_date <= current <= academy.contract_end_date):
                continue
            day_active_count = 0
            detailed_occurrences = _academy_schedule_occurrences_for_date(academy, current)
            if detailed_occurrences:
                for occ in detailed_occurrences:
                    total_counts[academy.id] = total_counts.get(academy.id, 0) + 1
                    deleted_key = (academy.id, current, _norm(occ['original_place']), occ['original_slot_index'])
                    if not is_cancelled and deleted_key not in deleted_overrides:
                        active_counts[academy.id] = active_counts.get(academy.id, 0) + 1
                        day_active_count += 1
                if day_active_count:
                    active_days[academy.id] = active_days.get(academy.id, 0) + 1
                continue
            occurrence_sources = []
            if _contains_value(academy.training_days, day_ar):
                occurrence_sources.append((academy.operation_place, academy.training_hours))
            extra_days = academy.extra_training_days or academy.training_days
            if academy.has_extra_hours and _contains_value(extra_days, day_ar):
                occurrence_sources.append((academy.extra_training_place, academy.extra_training_hours))
            for places_text, hours_text in occurrence_sources:
                for place in split_values(places_text):
                    for slot in split_values(hours_text):
                        slot_index = _slot_label_to_index(slot)
                        if slot_index is None:
                            continue
                        total_counts[academy.id] = total_counts.get(academy.id, 0) + 1
                        deleted_key = (academy.id, current, _norm(place), slot_index)
                        if not is_cancelled and deleted_key not in deleted_overrides:
                            active_counts[academy.id] = active_counts.get(academy.id, 0) + 1
                            day_active_count += 1
            if day_active_count:
                active_days[academy.id] = active_days.get(academy.id, 0) + 1
    return total_counts, active_counts, active_days


def _academy_month_income_from_counts(academy, total_counts, active_counts, active_days, year=None, month=None):
    academy_id = academy.id
    if academy.subscription_type == 'revenue_share':
        players_total = academy.members.filter(role=AcademyMember.ROLE_PLAYER, is_active=True).aggregate(total=Sum('monthly_subscription'))['total'] or 0
        return int(players_total * (academy.eess_share_percentage or 0) / 100)
    if academy.subscription_type == 'fixed':
        return int(academy.monthly_subscription or 0)
    if year and month:
        return _calculate_variable_income_by_facility(academy, year, month)
    rent_value = int(academy.variable_rent_value or 0)
    if academy.variable_rent_type == 'hour':
        return rent_value * active_counts.get(academy_id, 0)
    if academy.variable_rent_type == 'day':
        return rent_value * active_days.get(academy_id, 0)
    return 0


BALL_FIELD_NAMES = ['ملعب كرة القدم #1', 'ملعب كرة القدم #2', 'ملعب الباسكت']


def _is_ball_field_academy(academy):
    places = [academy.operation_place]
    if academy.has_extra_hours:
        places.append(academy.extra_training_place)
    return any(_contains_value(place_text, field_name) for place_text in places for field_name in BALL_FIELD_NAMES)


def _academy_rent_rows(year, month, start, end, branch=None):
    queryset = Academy.objects.select_related('branch').filter(
            contract_start_date__lte=end,
            contract_end_date__gte=start,
        )
    if branch is not None:
        queryset = queryset.filter(branch=branch)
    academies = list(queryset)
    total_counts, active_counts, active_days = _monthly_academy_operation_counts(year, month, academies)
    month_start = date(year, month, 1)
    rows = []
    for academy in academies:
        expected = _academy_month_income_from_counts(academy, total_counts, active_counts, active_days, year, month)
        payment, _ = AcademyMonthlyRentPayment.objects.get_or_create(
            academy=academy,
            month=month_start,
            defaults={'expected_amount': expected},
        )
        if payment.expected_amount != expected:
            payment.expected_amount = expected
            payment.save(update_fields=['expected_amount', 'updated_at'])
        rows.append({
            'academy': academy,
            'payment': payment,
            'expected': int(expected or 0),
            'paid': int(payment.paid_amount or 0),
            'remaining': payment.remaining_amount,
            'supplied': int(payment.supplied_amount or 0),
            'unsupplied': payment.unsupplied_amount,
            'is_paid': payment.is_paid,
            'is_supplied': payment.is_supplied,
            'is_ball_field_academy': _is_ball_field_academy(academy),
        })
    rows.sort(key=lambda row: (row['academy'].branch.display_name if row['academy'].branch_id else '', row['academy'].name))
    return rows


def _add_months(month_date, offset):
    month_index = (month_date.year * 12 + month_date.month - 1) + offset
    return date(month_index // 12, month_index % 12 + 1, 1)


def _academy_deposit_rows(rent_rows, month_start):
    academies = [row['academy'] for row in rent_rows]
    plans = {
        plan.academy_id: plan
        for plan in AcademyDepositPlan.objects.filter(
            academy_id__in=[academy.id for academy in academies]
        ).prefetch_related('installments')
    }
    rows = []
    for academy in academies:
        plan = plans.get(academy.id)
        if not plan and not academy.security_deposit:
            continue
        installments = list(plan.installments.all()) if plan else []
        total = int(plan.total_amount if plan else academy.security_deposit or 0)
        paid = sum(int(item.paid_amount or 0) for item in installments)
        supplied = sum(int(item.supplied_amount or 0) for item in installments)
        remaining = max(0, total - paid)
        unsupplied = max(0, paid - supplied)
        due_this_month = sum(
            int(item.due_amount or 0) for item in installments
            if item.due_month.year == month_start.year and item.due_month.month == month_start.month
        )
        overdue = sum(
            item.remaining_amount for item in installments if item.due_month < month_start
        )
        if not plan:
            status_label, status_class = 'لم يتم إعداد الخطة', 'secondary'
        elif paid >= total and supplied >= paid and total > 0:
            status_label, status_class = 'مسدد ومورد بالكامل', 'success'
        elif paid >= total and unsupplied > 0:
            status_label, status_class = 'مسدد وغير مورد بالكامل', 'info'
        elif overdue > 0:
            status_label, status_class = 'يوجد قسط متأخر', 'danger'
        elif paid > 0:
            status_label, status_class = 'مسدد جزئيًا', 'warning'
        elif plan.first_due_month > month_start:
            status_label, status_class = 'لم يحن موعد السداد', 'secondary'
        else:
            status_label, status_class = 'غير مسدد', 'danger'
        rows.append({
            'academy': academy,
            'plan': plan,
            'total': total,
            'installments_count': plan.installments_count if plan else 0,
            'due_this_month': due_this_month,
            'paid': paid,
            'remaining': remaining,
            'supplied': supplied,
            'unsupplied': unsupplied,
            'overdue': overdue,
            'status_label': status_label,
            'status_class': status_class,
        })
    rows.sort(key=lambda row: (row['academy'].branch.display_name if row['academy'].branch_id else '', row['academy'].name))
    return rows


def _bonus_for_employee(employee, daily_income_total, cafe_sales_total):
    job = JobTitle.objects.filter(name=employee.job_title).first()
    if not job:
        return 0
    total_bonus = 0
    for tier in job.bonus_tiers.all():
        source_total = daily_income_total if tier.source_type == BonusTier.SOURCE_DAILY_BOOKING else cafe_sales_total
        if source_total >= tier.from_amount and (not tier.to_amount or source_total <= tier.to_amount):
            total_bonus += int(tier.bonus_amount or 0)
    return total_bonus


def _month_financial_summary(year, month, start, end, branch=None):
    rent_rows = _academy_rent_rows(year, month, start, end, branch)
    academy_income = sum(row['expected'] for row in rent_rows)
    checkout_qs = DailyBookingCheckout.objects.filter(income_date__range=(start, end))
    sale_qs = CafeteriaSale.objects.filter(sale_date__range=(start, end)).select_related('item')
    purchase_qs = CafeteriaPurchase.objects.filter(purchase_date__range=(start, end)).select_related('item')
    monthly_qs = MonthlyExpense.objects.filter(expense_month__range=(start, end))
    daily_qs = DailyExpense.objects.filter(expense_date__range=(start, end))
    operating_qs = OperatingExpense.objects.filter(expense_date__range=(start, end))
    employee_qs = Employee.objects.all()
    if branch is not None:
        checkout_qs = checkout_qs.filter(booking__branch=branch)
        sale_qs = sale_qs.filter(item__branch=branch)
        purchase_qs = purchase_qs.filter(item__branch=branch)
        monthly_qs = monthly_qs.filter(branch=branch)
        daily_qs = daily_qs.filter(branch=branch)
        operating_qs = operating_qs.filter(branch=branch)
        employee_qs = employee_qs.filter(branch=branch)
    daily_income_total = checkout_qs.aggregate(total=Sum('total_amount'))['total'] or 0
    cafe_sales_total = sum(s.total_amount for s in sale_qs)
    cafe_purchase_total = sum(p.total_amount for p in purchase_qs)
    monthly_expenses = monthly_qs.aggregate(total=Sum('amount'))['total'] or 0
    daily_expenses = daily_qs.aggregate(total=Sum('amount'))['total'] or 0
    operating_expenses = operating_qs.aggregate(total=Sum('amount'))['total'] or 0
    payroll_rows = []
    payroll_total = 0
    for employee in employee_qs.order_by('name'):
        bonus = _bonus_for_employee(employee, int(daily_income_total or 0), int(cafe_sales_total or 0))
        total = int(employee.salary or 0) + bonus
        payroll_total += total
        payroll_rows.append({'employee': employee, 'salary': employee.salary, 'bonus': bonus, 'total': total})
    gross_income = int(academy_income or 0) + int(daily_income_total or 0) + int(cafe_sales_total or 0)
    total_expenses = int(monthly_expenses or 0) + int(daily_expenses or 0) + int(operating_expenses or 0) + int(cafe_purchase_total or 0) + int(payroll_total or 0)
    net_profit = gross_income - total_expenses
    return {
        'rent_rows': rent_rows,
        'academy_income': academy_income,
        'daily_income_total': daily_income_total,
        'cafe_sales_total': cafe_sales_total,
        'cafe_purchase_total': cafe_purchase_total,
        'monthly_expenses': monthly_expenses,
        'daily_expenses': daily_expenses,
        'operating_expenses': operating_expenses,
        'payroll_rows': payroll_rows,
        'payroll_total': payroll_total,
        'gross_income': gross_income,
        'total_expenses': total_expenses,
        'net_profit': net_profit,
    }


@login_required
def reports_home(request):
    allowed_report_types = _user_allowed_report_types(request.user)
    if not allowed_report_types:
        messages.error(request, 'ليس لديك صلاحية عرض التقارير.')
        return redirect('dashboard')
    year, month, start, end, month_value = _month_bounds(request.GET.get('month'))
    report_type = request.GET.get('report_type', 'company_income')
    report_titles = {
        'company_income': 'إجمالي دخل الشركة',
        'income': 'تقرير الدخل من الأكاديميات والحجز اليومي',
        'daily_booking_monthly': 'تقرير الدخل الشهري من الحجز اليومي',
        'academy_rent_payments': 'تقرير سداد إيجارات الأكاديميات الشهرية',
        'training_place_income': 'تقرير دخل أماكن التدريب',
        'shareholders': 'تقرير المساهمين والنسب والأرباح',
        'employees': 'تقرير الموظفين',
        'payroll': 'تقرير المرتبات الشهرية والبونص',
        'expenses': 'تقرير المصروفات',
        'cafeteria': 'تقرير الكافيتريا والأرباح والمخزون',
        'deposits': 'تقرير مبالغ التأمين للأكاديميات',
        'monthly_expenses': 'تقرير المصروفات الشهرية',
        'daily_expenses': 'تقرير المصروفات اليومية',
        'operating_expenses': 'تقرير مصروفات التشغيل',
        'cafeteria_inventory': 'تقرير مخزون الكافيتريا',
        'cafeteria_sales': 'تقرير مبيعات الكافيتريا',
        'cafeteria_purchases': 'تقرير مشتريات الكافيتريا',
    }
    if report_type not in report_titles or report_type not in allowed_report_types:
        report_type = allowed_report_types[0]

    allowed_report_options = [(key, report_titles[key]) for key in allowed_report_types if key in report_titles]

    context = {
        'month_value': month_value,
        'report_type': report_type,
        'report_title': report_titles[report_type],
        'allowed_report_options': allowed_report_options,
        'fixed_income': 0,
        'variable_income': 0,
        'revenue_share_income': 0,
        'daily_booking_income': 0,
        'daily_booking_checkout_income': 0,
        'total_academy_income': 0,
        'founding_expenses': 0,
        'monthly_expenses': 0,
        'daily_expenses': 0,
        'operating_expenses': 0,
        'salaries_total': 0,
        'cafe_purchase_total': 0,
        'cafe_sales_total': 0,
        'cafe_profit': 0,
        'net_profit': 0,
        'shareholder_rows': [],
        'employees': [],
        'low_stock_items': [],
        'academy_rows': [],
        'daily_booking_monthly_rows': [],
        'academy_rent_rows': [],
        'academy_rent_expected_total': 0,
        'academy_rent_paid_total': 0,
        'academy_rent_remaining_total': 0,
        'academy_rent_supplied_total': 0,
        'academy_rent_unsupplied_total': 0,
        'training_place_rows': [],
        'company_income_daily_total': 0,
        'company_income_daily_supplied_total': 0,
        'company_income_daily_unsupplied_total': 0,
        'company_income_expected_total': 0,
        'company_income_paid_total': 0,
        'company_income_remaining_total': 0,
        'company_income_supplied_total': 0,
        'company_income_unsupplied_total': 0,
        'company_income_total_due': 0,
        'company_income_rows': [],
        'cafe_sales': [],
        'cafe_purchases': [],
        'deposit_academies': [],
        'security_deposit_total': 0,
    }

    if report_type == 'company_income':
        rent_rows = _academy_rent_rows(year, month, start, end)
        daily_total = DailyBookingCheckout.objects.filter(income_date__range=(start, end)).aggregate(total=Sum('total_amount'))['total'] or 0
        daily_supplied_total = DailyIncomeSupply.objects.filter(supply_date__range=(start, end)).aggregate(total=Sum('amount'))['total'] or 0
        daily_unsupplied_total = max(0, int(daily_total or 0) - int(daily_supplied_total or 0))
        academy_expected_total = sum(row['expected'] for row in rent_rows)
        academy_paid_total = sum(row['paid'] for row in rent_rows)
        academy_remaining_total = sum(row['remaining'] for row in rent_rows)
        academy_supplied_total = sum(row['supplied'] for row in rent_rows)
        academy_unsupplied_total = sum(row['unsupplied'] for row in rent_rows)
        context.update({
            'company_income_rows': rent_rows,
            'company_income_daily_total': daily_total,
            'company_income_daily_supplied_total': daily_supplied_total,
            'company_income_daily_unsupplied_total': daily_unsupplied_total,
            'company_income_expected_total': academy_expected_total,
            'company_income_paid_total': academy_paid_total,
            'company_income_remaining_total': academy_remaining_total,
            'company_income_supplied_total': academy_supplied_total + int(daily_supplied_total or 0),
            'company_income_unsupplied_total': academy_unsupplied_total + daily_unsupplied_total,
            'company_income_total_due': academy_expected_total + int(daily_total or 0),
            'academy_rent_supplied_total': academy_supplied_total,
            'academy_rent_unsupplied_total': academy_unsupplied_total,
        })

    elif report_type == 'income':
        academies = list(Academy.objects.filter(contract_start_date__lte=end, contract_end_date__gte=start))
        total_counts, active_counts, active_days = _monthly_academy_operation_counts(year, month, academies)
        academy_rows = []
        for a in academies:
            if a.subscription_type == 'variable':
                value = _academy_month_income_from_counts(a, total_counts, active_counts, active_days, year, month)
                kind = 'متغير'
                sort_type = 1
            elif a.subscription_type == 'revenue_share':
                value = _academy_month_income_from_counts(a, total_counts, active_counts, active_days, year, month)
                kind = 'نسبة مشاركة'
                sort_type = 2
            else:
                value = _academy_month_income_from_counts(a, total_counts, active_counts, active_days, year, month)
                kind = 'ثابت'
                sort_type = 0
            academy_rows.append({
                'academy': a,
                'activity': a.sport_activity,
                'kind': kind,
                'value': value,
                'sort_type': sort_type,
            })
        academy_rows.sort(key=lambda row: (row['sort_type'], row['activity'] or '', row['academy'].name or ''))
        fixed_income = sum(row['value'] for row in academy_rows if row['sort_type'] == 0)
        variable_income = sum(row['value'] for row in academy_rows if row['sort_type'] == 1)
        revenue_share_income = sum(row['value'] for row in academy_rows if row['sort_type'] == 2)
        daily_booking_income = DailyBookingCheckout.objects.filter(income_date__range=(start, end)).aggregate(total=Sum('total_amount'))['total'] or 0
        context.update({
            'academy_rows': academy_rows,
            'fixed_income': fixed_income,
            'variable_income': variable_income,
            'revenue_share_income': revenue_share_income,
            'daily_booking_income': daily_booking_income,
            'total_academy_income': fixed_income + variable_income + revenue_share_income + daily_booking_income,
        })

    elif report_type == 'academy_rent_payments':
        rent_rows = _academy_rent_rows(year, month, start, end)
        context.update({
            'academy_rent_rows': rent_rows,
            'academy_rent_expected_total': sum(row['expected'] for row in rent_rows),
            'academy_rent_paid_total': sum(row['paid'] for row in rent_rows),
            'academy_rent_remaining_total': sum(row['remaining'] for row in rent_rows),
            'academy_rent_supplied_total': sum(row['supplied'] for row in rent_rows),
            'academy_rent_unsupplied_total': sum(row['unsupplied'] for row in rent_rows),
        })

    elif report_type == 'training_place_income':
        rent_rows = _academy_rent_rows(year, month, start, end)
        place_totals = {}
        for row in rent_rows:
            places = row['academy'].operation_places_list or ['غير محدد']
            share = int(row['expected'] / len(places)) if places else row['expected']
            for place in places:
                place_totals[place] = place_totals.get(place, 0) + share
        context.update({
            'training_place_rows': [
                {'place': place, 'income': income}
                for place, income in sorted(place_totals.items(), key=lambda item: item[0])
            ]
        })

    elif report_type == 'daily_booking_monthly':
        grouped = {
            row['income_date']: row
            for row in DailyBookingCheckout.objects.filter(income_date__range=(start, end))
            .values('income_date')
            .annotate(
                total=Sum('total_amount'),
                advance=Sum('advance_payment'),
                remaining=Sum('remaining_amount'),
                count=Count('id'),
            )
        }
        daily_booking_monthly_rows = []
        daily_booking_checkout_income = 0
        for day_number in range(1, monthrange(year, month)[1] + 1):
            current = date(year, month, day_number)
            row = grouped.get(current, {})
            total = row.get('total') or 0
            daily_booking_checkout_income += int(total)
            daily_booking_monthly_rows.append({
                'date': current,
                'day_name': WEEKDAY_AR[current.weekday()],
                'total': total,
                'advance': row.get('advance') or 0,
                'remaining': row.get('remaining') or 0,
                'count': row.get('count') or 0,
            })
        context.update({
            'daily_booking_monthly_rows': daily_booking_monthly_rows,
            'daily_booking_checkout_income': daily_booking_checkout_income,
        })

    elif report_type in {'expenses', 'monthly_expenses', 'daily_expenses', 'operating_expenses'}:
        daily_expense_rows = DailyExpense.objects.filter(
            expense_date__range=(start, end)
        ).select_related('created_by')
        context.update({
            'monthly_expenses': MonthlyExpense.objects.filter(expense_month__range=(start, end)).aggregate(total=Sum('amount'))['total'] or 0,
            'daily_expenses': DailyExpense.objects.filter(expense_date__range=(start, end)).aggregate(total=Sum('amount'))['total'] or 0,
            'operating_expenses': OperatingExpense.objects.filter(expense_date__range=(start, end)).aggregate(total=Sum('amount'))['total'] or 0,
            'daily_expense_rows': daily_expense_rows,
        })

    elif report_type == 'employees':
        employees = Employee.objects.all()
        context.update({
            'employees': employees,
            'salaries_total': employees.aggregate(total=Sum('salary'))['total'] or 0,
        })

    elif report_type == 'payroll':
        financial_summary = _month_financial_summary(year, month, start, end)
        context.update({
            'payroll_rows': financial_summary['payroll_rows'],
            'payroll_total': financial_summary['payroll_total'],
        })

    elif report_type == 'cafeteria':
        cafe_purchases = CafeteriaPurchase.objects.filter(purchase_date__range=(start, end))
        cafe_sales = CafeteriaSale.objects.filter(sale_date__range=(start, end)).select_related('item')
        cafe_purchase_total = sum(p.total_amount for p in cafe_purchases)
        cafe_sales_total = sum(s.total_amount for s in cafe_sales)
        context.update({
            'cafe_purchases': cafe_purchases,
            'cafe_sales': cafe_sales,
            'cafe_purchase_total': cafe_purchase_total,
            'cafe_sales_total': cafe_sales_total,
            'cafe_profit': cafe_sales_total - cafe_purchase_total,
            'low_stock_items': [item for item in CafeteriaItem.objects.all() if item.is_low_stock],
        })

    elif report_type in {'cafeteria_inventory', 'cafeteria_sales', 'cafeteria_purchases'}:
        context.update({
            'cafe_purchases': CafeteriaPurchase.objects.filter(purchase_date__range=(start, end)),
            'cafe_sales': CafeteriaSale.objects.filter(sale_date__range=(start, end)).select_related('item'),
            'low_stock_items': [item for item in CafeteriaItem.objects.all() if item.is_low_stock],
        })

    elif report_type == 'deposits':
        deposit_academies = Academy.objects.all().order_by('sport_activity', 'name')
        context.update({
            'deposit_academies': deposit_academies,
            'security_deposit_total': sum(a.security_deposit for a in deposit_academies),
        })

    elif report_type == 'shareholders':
        summary = _month_financial_summary(year, month, start, end)
        net_profit = summary['net_profit']
        context.update({
            'net_profit': net_profit,
            'shareholder_rows': [
                {'shareholder': sh, 'profit_share': int(net_profit * sh.share_percentage / 100)}
                for sh in Shareholder.objects.all()
            ],
        })
    return render(request, 'academies/reports.html', context)


def _voucher_access_or_redirect(request):
    profile = _ensure_user_profile(request.user)
    if (
        request.user.is_superuser or request.user.is_staff or
        profile.can_accounts
    ):
        return None
    messages.error(request, 'ليس لديك صلاحية الحسابات لإدارة أوامر الصرف والتوريد.')
    return redirect('dashboard')


def _voucher_signature_titles():
    titles = set(JobTitle.objects.values_list('name', flat=True))
    titles.update(Employee.objects.exclude(job_title='').values_list('job_title', flat=True))
    return sorted(title for title in titles if title)


def _voucher_employee_names_by_title():
    names_by_title = {}
    for employee in Employee.objects.exclude(job_title='').order_by('name'):
        names_by_title.setdefault(employee.job_title, []).append(employee.name)
    return names_by_title


def _aligned_signature_name(job_title, employee_name):
    """Stretch the second name with Arabic tatweel to align with the job title."""
    job_title = (job_title or '').strip()
    employee_name = (employee_name or '').strip()
    missing = max(len(job_title) - len(employee_name), 0)
    if not employee_name or not missing:
        return employee_name
    parts = employee_name.split()
    target_index = 1 if len(parts) > 1 else 0
    target = parts[target_index]
    insert_at = max(1, len(target) // 2)
    parts[target_index] = target[:insert_at] + ('ـ' * missing) + target[insert_at:]
    return ' '.join(parts)


def _voucher_aligned_employee_names_by_title():
    return {
        title: [_aligned_signature_name(title, name) for name in names]
        for title, names in _voucher_employee_names_by_title().items()
    }


@login_required
def financial_voucher_list(request):
    denied = _voucher_access_or_redirect(request)
    if denied:
        return denied
    selected_type = request.GET.get('type', '').strip()
    vouchers = FinancialVoucher.objects.select_related('created_by')
    active_branch, all_branches = selected_branch(request)
    if not all_branches:
        vouchers = vouchers.filter(branch=active_branch)
    if selected_type in dict(FinancialVoucher.TYPE_CHOICES):
        vouchers = vouchers.filter(voucher_type=selected_type)
    signature_titles = _voucher_signature_titles()
    requested_signature = request.GET.get('signature_title', '').strip()
    signature_title = requested_signature if requested_signature in signature_titles else (
        'مدير التشغيل' if 'مدير التشغيل' in signature_titles
        else (signature_titles[0] if signature_titles else 'التوقيع')
    )
    employee_names_by_title = _voucher_aligned_employee_names_by_title()
    signature_names = employee_names_by_title.get(signature_title, [])
    return render(request, 'academies/financial_voucher_list.html', {
        'vouchers': vouchers,
        'selected_type': selected_type,
        'signature_titles': signature_titles,
        'signature_title': signature_title,
        'signature_name': signature_names[0] if signature_names else '',
        'employee_names_by_title': employee_names_by_title,
        'print_date': date.today(),
    })


@login_required
def financial_voucher_create(request, voucher_type):
    denied = _voucher_access_or_redirect(request)
    if denied:
        return denied
    type_labels = dict(FinancialVoucher.TYPE_CHOICES)
    if voucher_type not in type_labels:
        messages.error(request, 'نوع الأمر المالي غير صحيح.')
        return redirect('financial_voucher_list')
    form = FinancialVoucherForm(request.POST or None, initial={'voucher_date': date.today()})
    if form.is_valid():
        voucher = form.save(commit=False)
        voucher.voucher_type = voucher_type
        voucher.created_by = request.user
        active_branch, all_branches = selected_branch(request)
        if not all_branches:
            voucher.branch = active_branch
        voucher.save()
        destination = reverse('financial_voucher_detail', kwargs={'pk': voucher.pk})
        submit_action = request.POST.get('submit_action', 'save')
        if submit_action in {'print', 'pdf'}:
            destination += f'?auto_print=1&pdf={1 if submit_action == "pdf" else 0}'
        return redirect(destination)
    return render(request, 'academies/financial_voucher_form.html', {
        'form': form,
        'voucher_type': voucher_type,
        'title': type_labels[voucher_type],
    })


@login_required
def financial_voucher_update(request, pk):
    denied = _voucher_access_or_redirect(request)
    if denied:
        return denied
    voucher = get_object_or_404(FinancialVoucher, pk=pk)
    form = FinancialVoucherForm(request.POST or None, instance=voucher)
    if form.is_valid():
        form.save()
        messages.success(request, 'تم تحديث الأمر المالي بنجاح.')
        destination = reverse('financial_voucher_detail', kwargs={'pk': voucher.pk})
        submit_action = request.POST.get('submit_action', 'save')
        if submit_action in {'print', 'pdf'}:
            destination += f'?auto_print=1&pdf={1 if submit_action == "pdf" else 0}'
        return redirect(destination)
    return render(request, 'academies/financial_voucher_form.html', {
        'form': form,
        'voucher_type': voucher.voucher_type,
        'title': f'تعديل {voucher.get_voucher_type_display()}',
        'voucher': voucher,
    })


@login_required
def financial_voucher_detail(request, pk):
    denied = _voucher_access_or_redirect(request)
    if denied:
        return denied
    voucher = get_object_or_404(FinancialVoucher.objects.select_related('created_by'), pk=pk)
    return render(request, 'academies/financial_voucher_detail.html', {
        'voucher': voucher,
        'signature_display_name': _aligned_signature_name(voucher.signature_title, voucher.signer_name),
        'print_date': date.today(),
        'auto_print': request.GET.get('auto_print') == '1',
        'print_as_pdf': request.GET.get('pdf') == '1',
    })


@login_required
def reports_home_v2(request):
    """Focused reports hub containing only the reports used by management."""
    allowed_report_types = _user_allowed_report_types(request.user)
    if not allowed_report_types:
        messages.error(request, 'ليس لديك صلاحية عرض التقارير.')
        return redirect('dashboard')

    active_branch, all_branches = selected_branch(request)
    year, month, month_start, month_end, month_value = _month_bounds(request.GET.get('month'))
    range_mode = request.GET.get('range_mode', 'month')
    start, end = month_start, month_end
    if range_mode == 'custom':
        try:
            custom_start = date.fromisoformat(request.GET.get('date_from', ''))
            custom_end = date.fromisoformat(request.GET.get('date_to', ''))
            if custom_start <= custom_end:
                start, end = custom_start, custom_end
            else:
                range_mode = 'month'
        except (TypeError, ValueError):
            range_mode = 'month'
    period_label = (
        f'من {start.strftime("%d/%m/%Y")} إلى {end.strftime("%d/%m/%Y")}'
        if range_mode == 'custom' else f'عن شهر {month_value}'
    )
    requested_type = request.GET.get('report_type', '').strip()
    requested_section = request.GET.get('section', '').strip()
    legacy_aliases = {
        'shareholders': ('academies', 'summary'),
        'board_members': ('academies', 'summary'),
        'income': ('monthly_income', 'summary'),
        'company_income': ('monthly_income', 'summary'),
        'academy_rent_payments': ('monthly_income', 'summary'),
        'daily_booking_monthly': ('monthly_income', 'summary'),
        'monthly_expenses': ('expenses', 'monthly'),
        'daily_expenses': ('expenses', 'daily'),
        'operating_expenses': ('expenses', 'summary'),
        'cafeteria_inventory': ('cafeteria', 'inventory'),
        'cafeteria_sales': ('cafeteria', 'statistics'),
        'cafeteria_purchases': ('cafeteria', 'inventory'),
    }
    if requested_type in legacy_aliases:
        requested_type, alias_section = legacy_aliases[requested_type]
        requested_section = requested_section or alias_section
    report_type = requested_type if requested_type in allowed_report_types else allowed_report_types[0]

    report_titles = dict(REPORT_TYPE_OPTIONS)
    section_choices = {
        'academies': {'summary', 'staff', 'player'},
        'monthly_income': {'summary', 'expected', 'paid', 'supplied'},
        'expenses': {'summary', 'monthly', 'daily'},
        'cafeteria': {'summary', 'inventory', 'statistics'},
    }
    if report_type == 'academies' and requested_section in {'coach', 'admin'}:
        requested_section = 'staff'
    section = requested_section if requested_section in section_choices.get(report_type, {'summary'}) else 'summary'
    signature_titles = list(
        Employee.objects.exclude(job_title='')
        .values_list('job_title', flat=True)
        .distinct()
        .order_by('job_title')
    )
    requested_signature = request.GET.get('signature_title', '').strip()
    signature_title = requested_signature if requested_signature in signature_titles else (
        'مدير التشغيل' if 'مدير التشغيل' in signature_titles
        else (signature_titles[0] if signature_titles else 'التوقيع')
    )
    context = {
        'month_value': month_value,
        'range_mode': range_mode,
        'date_from': start.isoformat(),
        'date_to': end.isoformat(),
        'period_label': period_label,
        'report_type': report_type,
        'report_title': report_titles[report_type],
        'allowed_report_options': [(key, report_titles[key]) for key in allowed_report_types],
        'signature_titles': signature_titles,
        'signature_title': signature_title,
        'section': section,
        'print_date': date.today(),
        'active_branch': active_branch,
        'active_branch_is_all': all_branches,
        'employees': [],
        'academy_choices': [],
        'selected_academy': None,
        'selected_academy_row': None,
        'academy_members': [],
        'income_rows': [],
        'monthly_expense_rows': [],
        'daily_expense_rows': [],
        'cafeteria_rows': [],
        'cafeteria_statistics': [],
        'security_rows': [],
    }
    employee_qs = Employee.objects.all()
    booking_checkout_qs = DailyBookingCheckout.objects.all()
    monthly_expense_qs = MonthlyExpense.objects.all()
    daily_expense_qs = DailyExpense.objects.all()
    cafeteria_item_qs = CafeteriaItem.objects.all()
    if not all_branches:
        employee_qs = employee_qs.filter(branch=active_branch)
        booking_checkout_qs = booking_checkout_qs.filter(booking__branch=active_branch)
        monthly_expense_qs = monthly_expense_qs.filter(branch=active_branch)
        daily_expense_qs = daily_expense_qs.filter(branch=active_branch)
        cafeteria_item_qs = cafeteria_item_qs.filter(branch=active_branch)

    if report_type == 'employees':
        context['employees'] = employee_qs

    elif report_type == 'academies':
        subscription_labels = {
            'fixed': 'قيمة ثابتة',
            'variable': 'قيمة متغيرة',
            'revenue_share': 'نسبة مشاركة',
        }
        academy_choices = Academy.objects.select_related('branch').all()
        if not all_branches:
            academy_choices = academy_choices.filter(branch=active_branch)
        context['academy_choices'] = academy_choices
        try:
            selected_academy_id = int(request.GET.get('academy_id', '') or 0)
        except (TypeError, ValueError):
            selected_academy_id = 0
        selected_academy = academy_choices.filter(pk=selected_academy_id).first() if selected_academy_id else None
        if selected_academy:
            context['selected_academy'] = selected_academy
            context['selected_academy_row'] = {
                'academy': selected_academy,
                'subscription_label': subscription_labels.get(selected_academy.subscription_type, selected_academy.subscription_type),
            }
            if section == 'staff':
                context['academy_members'] = selected_academy.members.filter(
                    role__in=[AcademyMember.ROLE_COACH, AcademyMember.ROLE_ADMIN]
                ).order_by('role', 'name')
            elif section == 'player':
                context['academy_members'] = selected_academy.members.filter(role=section).order_by('name')

    elif report_type == 'monthly_income':
        monthly_rent_rows = []
        cursor = date(start.year, start.month, 1)
        last_month = date(end.year, end.month, 1)
        while cursor <= last_month:
            cursor_end = date(cursor.year, cursor.month, monthrange(cursor.year, cursor.month)[1])
            monthly_rent_rows.extend(_academy_rent_rows(
                cursor.year, cursor.month, cursor, cursor_end,
                None if all_branches else active_branch,
            ))
            cursor = date(cursor.year + (1 if cursor.month == 12 else 0), 1 if cursor.month == 12 else cursor.month + 1, 1)
        rows_by_academy = {}
        for monthly_row in monthly_rent_rows:
            academy_id = monthly_row['academy'].id
            if academy_id not in rows_by_academy:
                rows_by_academy[academy_id] = {
                    'academy': monthly_row['academy'], 'expected': 0, 'paid': 0,
                    'remaining': 0, 'supplied': 0, 'unsupplied': 0, 'supplied_date': None,
                }
            row = rows_by_academy[academy_id]
            for field in ('expected', 'paid', 'remaining', 'supplied', 'unsupplied'):
                row[field] += int(monthly_row[field] or 0)
            supplied_date = monthly_row['payment'].supplied_date
            if supplied_date and (not row['supplied_date'] or supplied_date > row['supplied_date']):
                row['supplied_date'] = supplied_date
        rows = sorted(rows_by_academy.values(), key=lambda row: row['academy'].name)
        daily_booking_rows = list(
            booking_checkout_qs.filter(income_date__range=(start, end))
            .values('income_date')
            .annotate(total_amount=Sum('total_amount'))
            .order_by('income_date')
        )
        for booking_row in daily_booking_rows:
            booking_row['day_name'] = WEEKDAY_AR[booking_row['income_date'].weekday()]
        cafeteria_income_by_date = {}
        for sale in CafeteriaSale.objects.filter(
            sale_date__range=(start, end), item__in=cafeteria_item_qs
        ).select_related('item'):
            cafeteria_income_by_date[sale.sale_date] = cafeteria_income_by_date.get(sale.sale_date, 0) + sale.total_amount
        cafeteria_income_rows = [
            {'date': sale_date, 'day_name': WEEKDAY_AR[sale_date.weekday()], 'amount': amount}
            for sale_date, amount in sorted(cafeteria_income_by_date.items())
        ]
        expense_rows = []
        for expense in monthly_expense_qs.filter(expense_month__range=(start, end)):
            expense_rows.append({
                'type': 'مصروف شهري', 'date': expense.expense_month,
                'title': expense.title, 'amount': expense.amount, 'notes': expense.notes,
            })
        for expense in daily_expense_qs.filter(expense_date__range=(start, end)):
            expense_rows.append({
                'type': 'مصروف يومي', 'date': expense.expense_date,
                'title': expense.title, 'amount': expense.amount, 'notes': expense.notes,
            })
        for purchase in CafeteriaPurchase.objects.filter(
            purchase_date__range=(start, end), item__in=cafeteria_item_qs
        ).select_related('item'):
            expense_rows.append({
                'type': 'مشتروات الكافيتريا', 'date': purchase.purchase_date,
                'title': f'{purchase.item.name} - كمية {purchase.quantity}',
                'amount': purchase.total_amount,
                'notes': purchase.notes or (f'المورد: {purchase.supplier}' if purchase.supplier else ''),
            })
        expense_rows.sort(key=lambda item: (item['date'], item['title']))
        academy_income_total = sum(row['paid'] for row in rows)
        daily_booking_total = sum(row['total_amount'] or 0 for row in daily_booking_rows)
        cafeteria_income_total = sum(row['amount'] or 0 for row in cafeteria_income_rows)
        expenses_total = sum(row['amount'] or 0 for row in expense_rows)
        total_income = academy_income_total + daily_booking_total + cafeteria_income_total
        context.update({
            'income_rows': rows,
            'income_expected_total': sum(row['expected'] for row in rows),
            'income_paid_total': sum(row['paid'] for row in rows),
            'income_remaining_total': sum(row['remaining'] for row in rows),
            'income_supplied_total': sum(row['supplied'] for row in rows),
            'income_unsupplied_total': sum(row['unsupplied'] for row in rows),
            'income_daily_booking_rows': daily_booking_rows,
            'income_daily_booking_total': daily_booking_total,
            'income_cafeteria_rows': cafeteria_income_rows,
            'income_cafeteria_total': cafeteria_income_total,
            'income_expense_rows': expense_rows,
            'income_expenses_total': expenses_total,
            'income_academy_total': academy_income_total,
            'income_total': total_income,
            'income_net_total': total_income - expenses_total,
        })

    elif report_type == 'expenses':
        monthly_rows = monthly_expense_qs.filter(expense_month__range=(start, end))
        daily_rows = daily_expense_qs.filter(expense_date__range=(start, end)).select_related('created_by')
        monthly_total = monthly_rows.aggregate(total=Sum('amount'))['total'] or 0
        daily_total = daily_rows.aggregate(total=Sum('amount'))['total'] or 0
        context.update({
            'monthly_expense_rows': monthly_rows,
            'daily_expense_rows': daily_rows,
            'monthly_expenses_total': monthly_total,
            'daily_expenses_total': daily_total,
            'all_expenses_total': int(monthly_total) + int(daily_total),
        })

    elif report_type == 'cafeteria':
        purchases = list(CafeteriaPurchase.objects.filter(
            purchase_date__range=(start, end), item__in=cafeteria_item_qs
        ).select_related('item'))
        sales = list(CafeteriaSale.objects.filter(
            sale_date__range=(start, end), item__in=cafeteria_item_qs
        ).select_related('item'))
        purchase_total = sum(row.total_amount for row in purchases)
        sales_total = sum(row.total_amount for row in sales)
        purchased_quantities = {}
        sold_quantities = {}
        revenue_by_item = {}
        profit_by_item = {}
        all_purchased_quantities = {
            row['item_id']: row['total'] or 0
            for row in CafeteriaPurchase.objects.values('item_id').annotate(total=Sum('quantity'))
        }
        all_sold_quantities = {
            row['item_id']: row['total'] or 0
            for row in CafeteriaSale.objects.values('item_id').annotate(total=Sum('quantity'))
        }
        for purchase in purchases:
            purchased_quantities[purchase.item_id] = purchased_quantities.get(purchase.item_id, 0) + purchase.quantity
        for sale in sales:
            sold_quantities[sale.item_id] = sold_quantities.get(sale.item_id, 0) + sale.quantity
            revenue_by_item[sale.item_id] = revenue_by_item.get(sale.item_id, 0) + sale.total_amount
            profit_by_item[sale.item_id] = profit_by_item.get(sale.item_id, 0) + sale.estimated_profit
        cafeteria_rows = []
        for item in cafeteria_item_qs.select_related('category'):
            revenue = revenue_by_item.get(item.id, 0)
            profit = profit_by_item.get(item.id, 0)
            cafeteria_rows.append({
                'item': item,
                'purchased': purchased_quantities.get(item.id, 0),
                'sold': sold_quantities.get(item.id, 0),
                'remaining': int(item.opening_quantity or 0) + int(all_purchased_quantities.get(item.id, 0)) - int(all_sold_quantities.get(item.id, 0)),
                'revenue': revenue,
                'profit': profit,
                'profit_percentage': round((profit / revenue) * 100, 1) if revenue else 0,
            })
        context.update({
            'cafeteria_purchase_total': purchase_total,
            'cafeteria_sales_total': sales_total,
            'cafeteria_net_profit': sales_total - purchase_total,
            'cafeteria_rows': cafeteria_rows,
            'cafeteria_statistics': sorted(cafeteria_rows, key=lambda row: (-row['sold'], row['item'].name)),
        })

    elif report_type == 'security_log':
        security_rows = SecurityMovement.objects.select_related(
            'branch', 'academy', 'member', 'recorded_by'
        ).filter(recorded_at__date__range=(start, end))
        if not all_branches:
            security_rows = security_rows.filter(branch=active_branch)
        movement_filter = request.GET.get('movement', '')
        if movement_filter in {SecurityMovement.MOVEMENT_ENTRY, SecurityMovement.MOVEMENT_EXIT}:
            security_rows = security_rows.filter(movement_type=movement_filter)
        security_rows = list(security_rows)
        for row in security_rows:
            row.day_name = WEEKDAY_AR[timezone.localtime(row.recorded_at).weekday()]
        context.update({
            'security_rows': security_rows,
            'security_movement_filter': movement_filter,
            'security_movement_choices': SecurityMovement.MOVEMENT_CHOICES,
        })

    return render(request, 'academies/reports_v2.html', context)


@login_required
def settings_home(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    return render(request, 'academies/settings_home.html', {
        'users_count': User.objects.count(),
        'jobs_count': JobTitle.objects.count(),
        'bonus_count': BonusTier.objects.count(),
        'branches_count': Branch.objects.count(),
        'facilities_count': Facility.objects.count(),
        'sports_media_count': SportActivityMedia.objects.count(),
        'activities_count': Activity.objects.count(),
    })


@login_required
def company_management_home(request):
    if not (request.user.is_superuser or request.user.is_staff):
        profile = _ensure_user_profile(request.user)
        if not (profile.can_shareholders or profile.can_employees):
            messages.error(request, 'ليس لديك صلاحية إدارة الشركة.')
            return redirect('dashboard')
    return render(request, 'academies/company_management_home.html', {
        'shareholders_count': Shareholder.objects.count(),
        'employees_count': Employee.objects.count(),
    })


@login_required
def accounts_home(request):
    profile = _ensure_user_profile(request.user)
    can_view_financial_summary = bool(
        request.user.is_superuser or request.user.is_staff or
        profile.can_accounts or profile.can_access_any_report()
    )
    can_view_expenses = bool(
        request.user.is_superuser or request.user.is_staff or profile.can_general_expenses
    )
    can_manage_vouchers = bool(
        request.user.is_superuser or request.user.is_staff or profile.can_accounts
    )
    if not (can_view_financial_summary or can_view_expenses):
        messages.error(request, 'ليس لديك صلاحية الحسابات.')
        return redirect('dashboard')
    year, month, start, end, month_value = _month_bounds(request.GET.get('month'))
    active_branch, all_branches = selected_branch(request)
    summary = _month_financial_summary(
        year, month, start, end, None if all_branches else active_branch
    ) if can_view_financial_summary else None
    shareholder_rows = []
    if summary:
        shareholder_rows = [
            {'shareholder': sh, 'profit_share': int(summary['net_profit'] * sh.share_percentage / 100)}
            for sh in Shareholder.objects.all()
        ]
    signature_titles = _voucher_signature_titles()
    requested_signature = request.GET.get('signature_title', '').strip()
    signature_title = requested_signature if requested_signature in signature_titles else (
        'مدير التشغيل' if 'مدير التشغيل' in signature_titles
        else (signature_titles[0] if signature_titles else 'التوقيع')
    )
    employee_names_by_title = _voucher_aligned_employee_names_by_title()
    signature_names = employee_names_by_title.get(signature_title, [])
    return render(request, 'academies/accounts_home.html', {
        'month_value': month_value,
        'summary': summary,
        'shareholders': Shareholder.objects.all(),
        'shareholder_rows': shareholder_rows,
        'can_view_financial_summary': can_view_financial_summary,
        'can_view_expenses': can_view_expenses,
        'can_manage_vouchers': can_manage_vouchers,
        'signature_titles': signature_titles,
        'signature_title': signature_title,
        'signature_name': signature_names[0] if signature_names else '',
        'employee_names_by_title': employee_names_by_title,
        'print_date': date.today(),
        'active_branch': active_branch,
        'active_branch_is_all': all_branches,
    })


@login_required
def branding_settings(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    setting = AppSetting.current()
    form = AppSettingForm(request.POST or None, request.FILES or None, instance=setting)
    if form.is_valid():
        form.save()
        messages.success(request, 'تم حفظ اسم البرنامج واللوجو.')
        return redirect('settings_home')
    return render(request, 'academies/simple_form.html', {'form': form, 'title': 'هوية البرنامج واللوجو', 'back_url': 'settings_home'})


@login_required
def website_settings(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    setting = WebsiteSetting.current()
    form = WebsiteSettingForm(request.POST or None, request.FILES or None, instance=setting)
    if form.is_valid():
        form.save()
        messages.success(request, 'تم حفظ بيانات الموقع الإلكتروني.')
        return redirect('website_settings')
    return render(request, 'academies/simple_form.html', {
        'form': form,
        'title': 'إعدادات الموقع الإلكتروني',
        'back_url': 'settings_home',
    })


@login_required
def branch_list(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    q = request.GET.get('q', '').strip()
    branches = Branch.objects.all()
    if q:
        branches = branches.filter(Q(name__icontains=q) | Q(location__icontains=q) | Q(notes__icontains=q))
    return render(request, 'academies/branch_list.html', {'branches': branches, 'q': q})


@login_required
def branch_create(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    return _generic_form(request, BranchForm, 'إضافة فرع', 'branch_list')


@login_required
def branch_update(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    return _generic_form(request, BranchForm, 'تعديل فرع', 'branch_list', get_object_or_404(Branch, pk=pk))


@login_required
def branch_delete(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    return _generic_delete(request, get_object_or_404(Branch, pk=pk), 'حذف فرع', 'branch_list')


@login_required
def facility_list(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    q = request.GET.get('q', '').strip()
    facilities = Facility.objects.select_related('branch').all()
    if q:
        facilities = facilities.filter(Q(name__icontains=q) | Q(branch__name__icontains=q) | Q(notes__icontains=q))
    return render(request, 'academies/facility_list.html', {'facilities': facilities, 'q': q})


@login_required
def facility_create(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    return _generic_form(request, FacilityForm, 'إضافة ملعب / صالة', 'facility_list')


@login_required
def facility_update(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    return _generic_form(request, FacilityForm, 'تعديل ملعب / صالة', 'facility_list', get_object_or_404(Facility, pk=pk))


@login_required
def facility_delete(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    return _generic_delete(request, get_object_or_404(Facility, pk=pk), 'حذف ملعب / صالة', 'facility_list')


@login_required
def sport_media_list(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    q = request.GET.get('q', '').strip()
    sports_media = SportActivityMedia.objects.all()
    if q:
        sports_media = sports_media.filter(Q(name__icontains=q) | Q(description__icontains=q))
    return render(request, 'academies/sport_media_list.html', {'sports_media': sports_media, 'q': q})


@login_required
def sport_media_create(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    return _generic_form(request, SportActivityMediaForm, 'إضافة صورة رياضة / نشاط', 'sport_media_list')


@login_required
def sport_media_update(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    return _generic_form(request, SportActivityMediaForm, 'تعديل صورة رياضة / نشاط', 'sport_media_list', get_object_or_404(SportActivityMedia, pk=pk))


@login_required
def sport_media_delete(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    return _generic_delete(request, get_object_or_404(SportActivityMedia, pk=pk), 'حذف صورة رياضة / نشاط', 'sport_media_list')


@login_required
def activity_list(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    q = request.GET.get('q', '').strip()
    activities = Activity.objects.all()
    if q:
        activities = activities.filter(Q(name__icontains=q) | Q(training_places__icontains=q) | Q(notes__icontains=q))
    return render(request, 'academies/activity_list.html', {'activities': activities, 'q': q})


@login_required
def activity_create(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    return _generic_form(request, ActivityForm, 'إضافة نشاط متاح', 'activity_list')


@login_required
def activity_update(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    return _generic_form(request, ActivityForm, 'تعديل نشاط متاح', 'activity_list', get_object_or_404(Activity, pk=pk))


@login_required
def activity_delete(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    return _generic_delete(request, get_object_or_404(Activity, pk=pk), 'حذف نشاط متاح', 'activity_list')


@login_required
def academy_member_list(request, academy_id):
    academy = get_object_or_404(Academy, pk=academy_id)
    role = request.GET.get('role', '').strip()
    members = academy.members.all()
    if role in {AcademyMember.ROLE_COACH, AcademyMember.ROLE_ADMIN}:
        role = 'staff'
    if role == 'staff':
        members = members.filter(role__in=[AcademyMember.ROLE_COACH, AcademyMember.ROLE_ADMIN])
    elif role == AcademyMember.ROLE_PLAYER:
        members = members.filter(role=role)
    else:
        role = ''
    return render(request, 'academies/academy_member_list.html', {
        'academy': academy,
        'members': members,
        'role': role,
        'role_label': {'staff': 'مدربو وإداريو', 'player': 'لاعبو'}.get(role, 'أعضاء'),
        'role_singular': {'staff': 'مدرب أو إداري', 'player': 'لاعب'}.get(role, 'عضو'),
    })


@login_required
def academy_member_create(request, academy_id):
    academy = get_object_or_404(Academy, pk=academy_id)
    role = request.GET.get('role', '').strip()
    if role in {AcademyMember.ROLE_COACH, AcademyMember.ROLE_ADMIN}:
        role = 'staff'
    if role not in {'staff', AcademyMember.ROLE_PLAYER}:
        messages.error(request, 'اختر نوع العضو من شاشة الأكاديمية.')
        return redirect(f'/academies/{academy.id}/members/')
    form = AcademyMemberForm(request.POST or None, request.FILES or None, fixed_role=role)
    if form.is_valid():
        member = form.save(commit=False)
        member.academy = academy
        member.save()
        destination = f'/academies/{academy.id}/members/?role={role}'
        if request.POST.get('submit_action') == 'generate_qr':
            destination += f'&qr_member={member.pk}'
        return redirect(destination)
    role_singular = {'staff': 'مدرب أو إداري', 'player': 'لاعب'}[role]
    return render(request, 'academies/academy_member_form.html', {
        'form': form, 'title': f'إضافة {role_singular} - {academy.name}',
        'back_url_path': f'/academies/{academy.id}/members/?role={role}',
        'member_role': role,
    })


@login_required
def academy_member_update(request, academy_id, pk):
    academy = get_object_or_404(Academy, pk=academy_id)
    member = get_object_or_404(AcademyMember, pk=pk, academy=academy)
    destination_role = 'staff' if member.role in {AcademyMember.ROLE_COACH, AcademyMember.ROLE_ADMIN} else member.role
    form = AcademyMemberForm(request.POST or None, request.FILES or None, instance=member, fixed_role=destination_role)
    if form.is_valid():
        member = form.save()
        destination = f'/academies/{academy.id}/members/?role={destination_role}'
        if request.POST.get('submit_action') == 'generate_qr':
            destination += f'&qr_member={member.pk}'
        return redirect(destination)
    return render(request, 'academies/academy_member_form.html', {
        'form': form, 'title': f'تعديل {member.get_role_display()} - {academy.name}',
        'back_url_path': f'/academies/{academy.id}/members/?role={destination_role}',
        'member': member, 'member_role': member.role,
    })


@login_required
def academy_member_qr(request, academy_id, pk):
    import qrcode
    from qrcode.image.svg import SvgPathImage

    member = get_object_or_404(AcademyMember.objects.select_related('academy'), pk=pk, academy_id=academy_id)
    details = [
        'EESS Management System',
        f'الأكاديمية: {member.academy.name}',
        f'النوع: {member.get_role_display()}',
        f'الاسم: {member.name}',
    ]
    if member.role in {AcademyMember.ROLE_COACH, AcademyMember.ROLE_ADMIN} and member.job_title:
        details.append(f'الوظيفة: {member.job_title}')
    if member.role == AcademyMember.ROLE_PLAYER and member.birth_date:
        details.append(f'تاريخ الميلاد: {member.birth_date:%d/%m/%Y}')
    details.append(f'المعرف: {member.qr_token}')
    qr = qrcode.QRCode(version=None, box_size=8, border=2)
    qr.add_data('\n'.join(details))
    qr.make(fit=True)
    image = qr.make_image(image_factory=SvgPathImage)
    output = BytesIO()
    image.save(output)
    response = HttpResponse(output.getvalue(), content_type='image/svg+xml')
    response['Cache-Control'] = 'private, max-age=3600'
    return response


@login_required
def academy_id_cards(request):
    if not _can_access_reports(request.user):
        messages.error(request, 'ليس لديك صلاحية عرض كروت التعارف.')
        return redirect('dashboard')

    academy_choices = Academy.objects.select_related('branch').order_by('name')
    try:
        academy_id = int(request.GET.get('academy_id', '') or 0)
    except (TypeError, ValueError):
        academy_id = 0
    academy = academy_choices.filter(pk=academy_id).first() if academy_id else None
    card_group = request.GET.get('card_group', '').strip()
    if card_group not in {'staff', 'player'}:
        card_group = ''
    members = AcademyMember.objects.none()
    if academy and card_group == 'staff':
        members = academy.members.filter(
            role__in=[AcademyMember.ROLE_COACH, AcademyMember.ROLE_ADMIN]
        ).order_by('role', 'name')
    elif academy and card_group == 'player':
        members = academy.members.filter(role=AcademyMember.ROLE_PLAYER).order_by('name')

    app_settings = AppSetting.objects.first()
    company_name = app_settings.company_name if app_settings else 'Egyptian English Sports Services'
    company_short_name = (
        app_settings.company_short_name.strip()
        if app_settings and app_settings.company_short_name and app_settings.company_short_name.strip()
        else _company_short_name(company_name)
    )
    return render(request, 'academies/academy_id_cards.html', {
        'academy_choices': academy_choices,
        'academy': academy,
        'members': members,
        'card_group': card_group,
        'training_year_choices': TRAINING_YEAR_CHOICES,
        'training_year': _selected_training_year(request),
        'company_short_name': company_short_name,
        'app_settings': app_settings,
    })


@login_required
def academy_member_delete(request, academy_id, pk):
    academy = get_object_or_404(Academy, pk=academy_id)
    member = get_object_or_404(AcademyMember, pk=pk, academy=academy)
    if request.method == 'POST':
        member.delete()
        return redirect('academy_member_list', academy_id=academy.id)
    return render(request, 'academies/simple_confirm_delete.html', {'object': member, 'title': 'حذف عضو أكاديمية', 'back_url_path': f'/academies/{academy.id}/members/'})


@login_required
def academy_rent_payments(request):
    if not _can_access_reports(request.user):
        messages.error(request, 'ليس لديك صلاحية عرض الإيجارات الشهرية.')
        return redirect('dashboard')
    year, month, start, end, month_value = _month_bounds(request.GET.get('month'))
    active_branch, all_branches = selected_branch(request)
    rows = _academy_rent_rows(year, month, start, end, None if all_branches else active_branch)
    if request.method == 'POST':
        for row in rows:
            payment = row['payment']
            prefix = f'payment_{payment.id}_'
            for field_name in ['paid_amount', 'supplied_amount']:
                raw_value = (request.POST.get(prefix + field_name) or '0').strip()
                try:
                    setattr(payment, field_name, max(0, int(raw_value or 0)))
                except ValueError:
                    setattr(payment, field_name, 0)
            for field_name in ['payment_date', 'supplied_date']:
                raw_date = (request.POST.get(prefix + field_name) or '').strip()
                try:
                    setattr(payment, field_name, date.fromisoformat(raw_date) if raw_date else None)
                except ValueError:
                    setattr(payment, field_name, None)
            payment.notes = request.POST.get(prefix + 'notes', '').strip()
            payment.save()
        messages.success(request, 'تم حفظ سدادات وتوريدات إيجارات الأكاديميات.')
        return redirect(f"{request.path}?month={month_value}")
    booking_income_qs = DailyBookingCheckout.objects.filter(income_date__range=(start, end))
    if not all_branches:
        booking_income_qs = booking_income_qs.filter(booking__branch=active_branch)
    totals = {
        'expected': sum(row['expected'] for row in rows),
        'paid': sum(row['paid'] for row in rows),
        'ball_field_paid': sum(row['paid'] for row in rows if row['is_ball_field_academy']),
        'daily_booking_income': booking_income_qs.aggregate(total=Sum('total_amount'))['total'] or 0,
        'remaining': sum(row['remaining'] for row in rows),
        'supplied': sum(row['supplied'] for row in rows),
        'unsupplied': sum(row['unsupplied'] for row in rows),
    }
    deposit_rows = _academy_deposit_rows(rows, date(year, month, 1))
    deposit_totals = {
        'expected': sum(row['total'] for row in deposit_rows),
        'due_this_month': sum(row['due_this_month'] for row in deposit_rows),
        'paid': sum(row['paid'] for row in deposit_rows),
        'remaining': sum(row['remaining'] for row in deposit_rows),
        'supplied': sum(row['supplied'] for row in deposit_rows),
        'unsupplied': sum(row['unsupplied'] for row in deposit_rows),
        'overdue_academies': sum(1 for row in deposit_rows if row['overdue'] > 0),
    }
    return render(request, 'academies/academy_rent_payments.html', {
        'rows': rows,
        'totals': totals,
        'deposit_rows': deposit_rows,
        'deposit_totals': deposit_totals,
        'month_value': month_value,
        'active_branch': active_branch,
        'active_branch_is_all': all_branches,
    })


@login_required
def academy_deposit_plan(request, academy_id):
    if not _can_access_reports(request.user):
        messages.error(request, 'ليس لديك صلاحية إدارة تأمينات الأكاديميات.')
        return redirect('dashboard')
    academy = get_object_or_404(Academy.objects.select_related('branch'), pk=academy_id)
    plan = AcademyDepositPlan.objects.filter(academy=academy).prefetch_related('installments').first()
    has_movements = bool(plan and plan.installments.filter(Q(paid_amount__gt=0) | Q(supplied_amount__gt=0)).exists())
    initial = None
    if not plan:
        initial = {
            'total_amount': academy.security_deposit or 0,
            'installments_count': 1,
            'first_due_month': date(academy.contract_start_date.year, academy.contract_start_date.month, 1),
        }
    form = AcademyDepositPlanForm(request.POST or None, instance=plan, initial=initial)
    if has_movements:
        for field in form.fields.values():
            field.disabled = True

    if request.method == 'POST' and request.POST.get('action') == 'save_plan':
        if has_movements:
            messages.error(request, 'لا يمكن تغيير خطة التأمين بعد تسجيل سداد أو توريد. يمكن تعديل الأقساط المسجلة فقط.')
        elif form.is_valid():
            with transaction.atomic():
                saved_plan = form.save(commit=False)
                saved_plan.academy = academy
                if not saved_plan.pk:
                    saved_plan.created_by = request.user
                saved_plan.first_due_month = date(
                    saved_plan.first_due_month.year, saved_plan.first_due_month.month, 1
                )
                saved_plan.save()
                saved_plan.installments.all().delete()
                base_amount, remainder = divmod(saved_plan.total_amount, saved_plan.installments_count)
                for index in range(saved_plan.installments_count):
                    AcademyDepositInstallment.objects.create(
                        plan=saved_plan,
                        installment_number=index + 1,
                        due_month=_add_months(saved_plan.first_due_month, index),
                        due_amount=base_amount + (1 if index < remainder else 0),
                    )
                academy.security_deposit = saved_plan.total_amount
                academy.save(update_fields=['security_deposit'])
            messages.success(request, 'تم حفظ خطة التأمين وإنشاء الأقساط بنجاح.')
            return redirect('academy_deposit_plan', academy_id=academy.id)

    if request.method == 'POST' and request.POST.get('action') == 'save_installments':
        if not plan:
            messages.error(request, 'أنشئ خطة التأمين أولًا.')
            return redirect('academy_deposit_plan', academy_id=academy.id)
        prepared = []
        validation_errors = []
        for installment in plan.installments.all():
            prefix = f'installment_{installment.id}_'
            try:
                paid_amount = max(0, int(request.POST.get(prefix + 'paid_amount') or 0))
                supplied_amount = max(0, int(request.POST.get(prefix + 'supplied_amount') or 0))
            except ValueError:
                validation_errors.append(f'القيم المالية للقسط {installment.installment_number} غير صحيحة.')
                continue
            payment_date_text = (request.POST.get(prefix + 'payment_date') or '').strip()
            supplied_date_text = (request.POST.get(prefix + 'supplied_date') or '').strip()
            try:
                payment_date = date.fromisoformat(payment_date_text) if payment_date_text else None
                supplied_date = date.fromisoformat(supplied_date_text) if supplied_date_text else None
            except ValueError:
                validation_errors.append(f'تاريخ القسط {installment.installment_number} غير صحيح.')
                continue
            if paid_amount > installment.due_amount:
                validation_errors.append(f'المسدد في القسط {installment.installment_number} أكبر من المستحق.')
            if supplied_amount > paid_amount:
                validation_errors.append(f'المورد في القسط {installment.installment_number} أكبر من المسدد.')
            if paid_amount > 0 and not payment_date:
                validation_errors.append(f'أدخل تاريخ سداد القسط {installment.installment_number}.')
            if supplied_amount > 0 and not supplied_date:
                validation_errors.append(f'أدخل تاريخ توريد القسط {installment.installment_number}.')
            prepared.append((
                installment, paid_amount, payment_date, supplied_amount, supplied_date,
                (request.POST.get(prefix + 'notes') or '').strip(),
            ))
        if validation_errors:
            for error in dict.fromkeys(validation_errors):
                messages.error(request, error)
            return redirect('academy_deposit_plan', academy_id=academy.id)
        with transaction.atomic():
            for installment, paid_amount, payment_date, supplied_amount, supplied_date, notes in prepared:
                if paid_amount != installment.paid_amount:
                    installment.paid_recorded_by = request.user
                if supplied_amount != installment.supplied_amount:
                    installment.supplied_recorded_by = request.user
                installment.paid_amount = paid_amount
                installment.payment_date = payment_date
                installment.supplied_amount = supplied_amount
                installment.supplied_date = supplied_date
                installment.notes = notes
                installment.save()
        messages.success(request, 'تم حفظ سداد وتوريد أقساط التأمين بنجاح.')
        return redirect('academy_deposit_plan', academy_id=academy.id)

    installments = list(plan.installments.select_related('paid_recorded_by', 'supplied_recorded_by')) if plan else []
    return render(request, 'academies/academy_deposit_plan.html', {
        'academy': academy,
        'plan': plan,
        'form': form,
        'installments': installments,
        'has_movements': has_movements,
        'back_month': request.GET.get('month', ''),
    })

@login_required
def job_title_list(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    q = request.GET.get('q', '').strip()
    jobs = JobTitle.objects.all()
    if q:
        jobs = jobs.filter(Q(name__icontains=q) | Q(notes__icontains=q))
    return render(request, 'academies/job_title_list.html', {'jobs': jobs, 'q': q})

@login_required
def job_title_create(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    form = JobTitleForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('job_title_list')
    return render(request, 'academies/simple_form.html', {'form': form, 'title': 'إضافة وظيفة متاحة', 'back_url': 'job_title_list'})

@login_required
def job_title_update(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    job = get_object_or_404(JobTitle, pk=pk)
    form = JobTitleForm(request.POST or None, instance=job)
    if form.is_valid():
        form.save()
        Employee.objects.filter(job_title=job.name).update(salary=job.base_salary)
        return redirect('job_title_list')
    return render(request, 'academies/simple_form.html', {'form': form, 'title': 'تعديل وظيفة متاحة', 'back_url': 'job_title_list'})

@login_required
def job_title_delete(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    job = get_object_or_404(JobTitle, pk=pk)
    if request.method == 'POST':
        job.delete()
        return redirect('job_title_list')
    return render(request, 'academies/simple_confirm_delete.html', {'object': job, 'title': 'حذف وظيفة متاحة', 'back_url': 'job_title_list'})

@login_required
def bonus_tier_list(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    tiers = BonusTier.objects.select_related('job_title').all()
    return render(request, 'academies/bonus_tier_list.html', {'tiers': tiers})

@login_required
def bonus_tier_create(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    form = BonusTierForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('bonus_tier_list')
    return render(request, 'academies/simple_form.html', {'form': form, 'title': 'إضافة شريحة بونص', 'back_url': 'bonus_tier_list'})

@login_required
def bonus_tier_update(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    tier = get_object_or_404(BonusTier, pk=pk)
    form = BonusTierForm(request.POST or None, instance=tier)
    if form.is_valid():
        form.save()
        return redirect('bonus_tier_list')
    return render(request, 'academies/simple_form.html', {'form': form, 'title': 'تعديل شريحة بونص', 'back_url': 'bonus_tier_list'})

@login_required
def bonus_tier_delete(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية الإعدادات.')
        return redirect('dashboard')
    tier = get_object_or_404(BonusTier, pk=pk)
    if request.method == 'POST':
        tier.delete()
        return redirect('bonus_tier_list')
    return render(request, 'academies/simple_confirm_delete.html', {'object': tier, 'title': 'حذف شريحة بونص', 'back_url': 'bonus_tier_list'})


@login_required
def user_list(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية إدارة المستخدمين.')
        return redirect('dashboard')
    q = request.GET.get('q', '').strip()
    users = User.objects.all().order_by('username')
    if q:
        users = users.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(email__icontains=q))
    for u in users:
        _ensure_user_profile(u)
    return render(request, 'academies/user_list.html', {'users': users, 'q': q})


def _permission_detail_context(profile=None):
    saved_buttons = (getattr(profile, 'button_permissions', {}) or {}) if profile else {}
    saved_reports = (getattr(profile, 'report_permissions', {}) or {}) if profile else {}
    modules = []
    for module in SIDEBAR_PERMISSION_MODULES:
        item = module.copy()
        selected = set(saved_buttons.get(module['key'], []))
        item['button_options'] = [
            {'name': button, 'checked': button in selected}
            for button in module['buttons']
        ]
        modules.append(item)
    return {
        'permission_modules': modules,
        'report_type_options': [
            {'key': key, 'label': label, 'checked': bool(
                saved_reports.get(key)
                or (key == 'academies' and (saved_reports.get('board_members') or saved_reports.get('shareholders')))
                or (profile and getattr(profile, REPORT_PERMISSION_FIELDS.get(key, ''), False))
                or (key == 'academies' and profile and profile.can_report_shareholders)
            )}
            for key, label in REPORT_TYPE_OPTIONS
        ],
    }


def _apply_permission_details_from_post(profile, post_data):
    button_permissions = {}
    for module in SIDEBAR_PERMISSION_MODULES:
        selected_buttons = post_data.getlist(f'buttons_{module["key"]}')
        button_permissions[module['key']] = selected_buttons
    profile.button_permissions = button_permissions
    profile.report_permissions = {
        report_key: (f'report_{report_key}' in post_data)
        for report_key, _ in REPORT_TYPE_OPTIONS
    }

@login_required
def user_create(request):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية إدارة المستخدمين.')
        return redirect('dashboard')
    form = EESSUserForm(request.POST or None)
    permission_form = EESSPermissionForm(request.POST or None)
    if form.is_valid() and permission_form.is_valid():
        user = form.save()
        profile = permission_form.save(commit=False)
        profile.user = user
        _apply_permission_details_from_post(profile, request.POST)
        profile.save()
        messages.success(request, 'تم إضافة المستخدم وتحديد صلاحياته.')
        return redirect('user_list')
    context = {'form': form, 'permission_form': permission_form, 'title': 'إضافة مستخدم'}
    context.update(_permission_detail_context())
    return render(request, 'academies/user_form.html', context)

@login_required
def user_update(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية إدارة المستخدمين.')
        return redirect('dashboard')
    user = get_object_or_404(User, pk=pk)
    profile = _ensure_user_profile(user)
    form = EESSUserUpdateForm(request.POST or None, instance=user)
    permission_form = EESSPermissionForm(request.POST or None, instance=profile)
    if form.is_valid() and permission_form.is_valid():
        form.save()
        saved_profile = permission_form.save(commit=False)
        _apply_permission_details_from_post(saved_profile, request.POST)
        saved_profile.save()
        messages.success(request, 'تم تعديل المستخدم وصلاحياته.')
        return redirect('user_list')
    context = {'form': form, 'permission_form': permission_form, 'title': 'تعديل مستخدم'}
    context.update(_permission_detail_context(profile))
    return render(request, 'academies/user_form.html', context)

@login_required
def user_delete(request, pk):
    if not _can_manage_users(request.user):
        messages.error(request, 'ليس لديك صلاحية إدارة المستخدمين.')
        return redirect('dashboard')
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        if user == request.user:
            messages.error(request, 'لا يمكن حذف المستخدم الحالي.')
        else:
            user.delete()
            messages.success(request, 'تم حذف المستخدم.')
        return redirect('user_list')
    return render(request, 'academies/simple_confirm_delete.html', {'object': user, 'title': 'حذف مستخدم', 'back_url': 'user_list'})
