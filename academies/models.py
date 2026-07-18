from calendar import monthrange
from decimal import Decimal
import base64
import datetime
import uuid
from django.db import models
from django.contrib.auth.models import User
from .constants import WEEKDAY_AR


def split_values(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split(',') if item.strip()]


class AppSetting(models.Model):
    program_name = models.CharField(max_length=200, default='EESS Management System', verbose_name='اسم البرنامج')
    company_name = models.CharField(max_length=250, default='Egyptian English Sports Services', verbose_name='اسم الشركة باللغة الإنجليزية')
    company_name_ar = models.CharField(max_length=250, blank=True, default='', verbose_name='اسم الشركة باللغة العربية')
    company_logo = models.FileField(upload_to='branding/', blank=True, verbose_name='لوجو الشركة')
    main_screen_image = models.FileField(upload_to='branding/', blank=True, verbose_name='صورة الشاشة الرئيسية')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'إعدادات البرنامج'
        verbose_name_plural = 'إعدادات البرنامج'

    def __str__(self):
        return self.program_name

    @classmethod
    def current(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Branch(models.Model):
    name = models.CharField(max_length=200, verbose_name='اسم الفرع')
    location = models.CharField(max_length=250, blank=True, verbose_name='الموقع')
    logo = models.FileField(upload_to='branches/logos/', blank=True, verbose_name='لوجو الفرع')
    image = models.FileField(upload_to='branches/images/', blank=True, verbose_name='صورة الفرع')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'فرع'
        verbose_name_plural = 'الأفرع'

    def __str__(self):
        return self.name


class Facility(models.Model):
    FACILITY_TYPES = [
        ('field', 'ملعب'),
        ('hall', 'صالة رياضية'),
        ('other', 'أخرى'),
    ]
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='facilities', verbose_name='الفرع')
    name = models.CharField(max_length=200, verbose_name='اسم الملعب / الصالة')
    facility_type = models.CharField(max_length=20, choices=FACILITY_TYPES, default='field', verbose_name='النوع')
    hourly_rent = models.PositiveIntegerField(default=0, verbose_name='قيمة إيجار الساعة')
    daily_rent = models.PositiveIntegerField(default=0, verbose_name='قيمة إيجار اليوم')
    image = models.FileField(upload_to='facilities/', blank=True, verbose_name='الصورة')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['branch__name', 'name']
        verbose_name = 'ملعب / صالة'
        verbose_name_plural = 'الملاعب والصالات'

    def __str__(self):
        return f'{self.branch} - {self.name}'


class SportActivityMedia(models.Model):
    name = models.CharField(max_length=200, verbose_name='اسم الرياضة / النشاط')
    image = models.FileField(upload_to='sports/', blank=True, verbose_name='الصورة')
    description = models.TextField(blank=True, verbose_name='وصف مختصر')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'صورة رياضة / نشاط'
        verbose_name_plural = 'صور الرياضات والأنشطة'

    def __str__(self):
        return self.name


class Activity(models.Model):
    INCOME_FIXED = 'fixed'
    INCOME_VARIABLE = 'variable'
    INCOME_REVENUE_SHARE = 'revenue_share'
    INCOME_CHOICES = [
        (INCOME_FIXED, 'قيمة ثابتة'),
        (INCOME_VARIABLE, 'قيمة متغيرة حسب الأيام والساعات'),
        (INCOME_REVENUE_SHARE, 'نسبة مشاركة من اشتراكات اللاعبين'),
    ]
    name = models.CharField(max_length=200, unique=True, verbose_name='اسم النشاط')
    training_places = models.CharField(max_length=500, blank=True, verbose_name='أماكن التدريب المتاحة')
    income_type = models.CharField(max_length=30, choices=INCOME_CHOICES, default=INCOME_FIXED, verbose_name='نوع الدخل')
    eess_share_percentage = models.PositiveIntegerField(default=0, verbose_name='نسبة EESS من الاشتراكات %')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'نشاط متاح'
        verbose_name_plural = 'الأنشطة المتاحة'

    def __str__(self):
        return self.name

    @property
    def training_places_list(self):
        return split_values(self.training_places)


class Academy(models.Model):
    branch = models.ForeignKey(Branch, null=True, blank=True, on_delete=models.SET_NULL, related_name='academies', verbose_name='الفرع')
    name = models.CharField(max_length=200, verbose_name='اسم الأكاديمية')
    logo_data = models.BinaryField(null=True, blank=True, editable=False, verbose_name='بيانات لوجو الأكاديمية')
    logo_content_type = models.CharField(max_length=100, blank=True, editable=False, verbose_name='نوع ملف لوجو الأكاديمية')
    logo_name = models.CharField(max_length=255, blank=True, editable=False, verbose_name='اسم ملف لوجو الأكاديمية')
    sport_activity = models.CharField(max_length=150, verbose_name='النشاط الرياضي')
    company_name = models.CharField(max_length=200, verbose_name='اسم الشركة')
    manager_name = models.CharField(max_length=200, verbose_name='اسم مدير الأكاديمية')
    manager_national_id = models.CharField(max_length=50, blank=True, verbose_name='الرقم القومي لمدير الأكاديمية')
    manager_phone = models.CharField(max_length=50, verbose_name='رقم الهاتف')
    operation_place = models.CharField(max_length=500, verbose_name='مكان التدريب')
    contract_start_date = models.DateField(verbose_name='بداية التعاقد')
    contract_end_date = models.DateField(verbose_name='نهاية التعاقد')
    subscription_type = models.CharField(max_length=20, default='fixed', verbose_name='نوع الاشتراك')
    monthly_subscription = models.PositiveIntegerField(default=0, verbose_name='قيمة الاشتراك الثابت')
    variable_rent_type = models.CharField(max_length=20, blank=True, verbose_name='نوع القيمة المتغيرة')
    variable_rent_value = models.PositiveIntegerField(default=0, verbose_name='قيمة الإيجار')
    eess_share_percentage = models.PositiveIntegerField(default=0, verbose_name='نسبة EESS من اشتراكات اللاعبين %')
    security_deposit = models.PositiveIntegerField(default=0, verbose_name='مبلغ التأمين')
    training_days = models.CharField(max_length=250, blank=True, verbose_name='أيام التدريب')
    training_hours = models.TextField(blank=True, verbose_name='ساعات التدريب الأساسية')
    training_schedule = models.JSONField(default=list, blank=True, verbose_name='جدول التدريب التفصيلي')
    has_extra_hours = models.BooleanField(default=False, verbose_name='إضافة ساعات تدريب إضافية')
    extra_training_days = models.CharField(max_length=250, blank=True, verbose_name='أيام التدريب الإضافية')
    extra_training_place = models.CharField(max_length=500, blank=True, verbose_name='مكان التدريب الإضافي')
    extra_training_hours = models.TextField(blank=True, verbose_name='ساعات التدريب الإضافية')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'أكاديمية'
        verbose_name_plural = 'الأكاديميات'

    def __str__(self):
        return self.name

    @property
    def operation_places_list(self):
        return split_values(self.operation_place)

    @property
    def logo_data_uri(self):
        if not self.logo_data:
            return ''
        content_type = self.logo_content_type or 'image/png'
        encoded = base64.b64encode(bytes(self.logo_data)).decode('ascii')
        return f'data:{content_type};base64,{encoded}'

    @property
    def training_hours_list(self):
        return split_values(self.training_hours)

    @property
    def training_days_list(self):
        return split_values(self.training_days)

    @property
    def extra_training_hours_list(self):
        return split_values(self.extra_training_hours)

    def training_days_count_in_month(self, year, month):
        days = set(split_values(self.training_days))
        if not days:
            return 0
        count = 0
        for day_number in range(1, monthrange(year, month)[1] + 1):
            current = datetime.date(year, month, day_number)
            if WEEKDAY_AR[current.weekday()] in days:
                count += 1
        return count

    def extra_training_days_count_in_month(self, year, month):
        days = set(split_values(self.extra_training_days))
        if not days:
            days = set(split_values(self.training_days))
        if not days:
            return 0
        count = 0
        for day_number in range(1, monthrange(year, month)[1] + 1):
            current = datetime.date(year, month, day_number)
            if WEEKDAY_AR[current.weekday()] in days:
                count += 1
        return count

    def calculate_variable_monthly_rent(self, year, month):
        if self.subscription_type != 'variable':
            return self.monthly_subscription

        rent_value = Decimal(self.variable_rent_value or 0)
        base_days_count = self.training_days_count_in_month(year, month)
        extra_days_count = self.extra_training_days_count_in_month(year, month) if self.has_extra_hours else 0

        if self.variable_rent_type == 'hour':
            base_slots_count = len(self.training_hours_list)
            extra_slots_count = len(self.extra_training_hours_list) if self.has_extra_hours else 0
            base_total = base_days_count * base_slots_count
            extra_total = extra_days_count * extra_slots_count
            return int(rent_value * Decimal(base_total + extra_total))

        if self.variable_rent_type == 'day':
            # في حالة إيجار اليوم، يتم حساب الأيام الأساسية، وتضاف الأيام الإضافية فقط إذا كانت مختلفة عن الأيام الأساسية.
            base_days = set(split_values(self.training_days))
            extra_days = set(split_values(self.extra_training_days)) if self.has_extra_hours else set()
            if extra_days and extra_days != base_days:
                return int(rent_value * Decimal(base_days_count + extra_days_count))
            return int(rent_value * Decimal(base_days_count))

        return 0


class AcademyMember(models.Model):
    ROLE_COACH = 'coach'
    ROLE_ADMIN = 'admin'
    ROLE_PLAYER = 'player'
    ROLE_CHOICES = [
        (ROLE_COACH, 'مدرب'),
        (ROLE_ADMIN, 'إداري'),
        (ROLE_PLAYER, 'لاعب'),
    ]
    academy = models.ForeignKey(Academy, on_delete=models.CASCADE, related_name='members', verbose_name='الأكاديمية')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name='النوع')
    name = models.CharField(max_length=200, verbose_name='الاسم')
    phone = models.CharField(max_length=50, blank=True, verbose_name='رقم الهاتف')
    national_id = models.CharField(max_length=50, blank=True, verbose_name='الرقم القومي')
    job_title = models.CharField(max_length=200, blank=True, verbose_name='الوظيفة')
    birth_date = models.DateField(null=True, blank=True, verbose_name='تاريخ الميلاد')
    monthly_subscription = models.PositiveIntegerField(default=0, verbose_name='الاشتراك الشهري للاعب')
    photo_data = models.BinaryField(null=True, blank=True, editable=False, verbose_name='بيانات الصورة')
    photo_content_type = models.CharField(max_length=100, blank=True, editable=False, verbose_name='نوع ملف الصورة')
    photo_name = models.CharField(max_length=255, blank=True, editable=False, verbose_name='اسم ملف الصورة')
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, verbose_name='معرف QR')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['academy__name', 'role', 'name']
        verbose_name = 'عضو أكاديمية'
        verbose_name_plural = 'مدربين وإداريين ولاعبين الأكاديميات'

    def __str__(self):
        return f'{self.name} - {self.academy}'

    @property
    def photo_data_uri(self):
        if not self.photo_data:
            return ''
        content_type = self.photo_content_type or 'image/jpeg'
        encoded = base64.b64encode(bytes(self.photo_data)).decode('ascii')
        return f'data:{content_type};base64,{encoded}'


class SecurityMovement(models.Model):
    MOVEMENT_ENTRY = 'entry'
    MOVEMENT_EXIT = 'exit'
    MOVEMENT_CHOICES = [
        (MOVEMENT_ENTRY, 'دخول'),
        (MOVEMENT_EXIT, 'خروج'),
    ]
    PERSON_STAFF = 'staff'
    PERSON_PLAYER = 'player'
    PERSON_PARENT = 'parent'
    PERSON_CHOICES = [
        (PERSON_PLAYER, 'لاعب'),
        (PERSON_STAFF, 'مدرب / إداري'),
        (PERSON_PARENT, 'ولي أمر'),
    ]
    SOURCE_MANUAL = 'manual'
    SOURCE_QR = 'qr'
    SOURCE_VISITOR = 'visitor'
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, 'اختيار من القائمة'),
        (SOURCE_QR, 'QR Code'),
        (SOURCE_VISITOR, 'زائر'),
    ]

    branch = models.ForeignKey(
        Branch, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='security_movements', verbose_name='الفرع',
    )
    academy = models.ForeignKey(
        Academy, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='security_movements', verbose_name='الأكاديمية',
    )
    member = models.ForeignKey(
        AcademyMember, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='security_movements', verbose_name='الشخص المسجل',
    )
    academy_name = models.CharField(max_length=200, blank=True, verbose_name='اسم الأكاديمية وقت التسجيل')
    person_name = models.CharField(max_length=200, verbose_name='الاسم')
    person_type = models.CharField(max_length=20, choices=PERSON_CHOICES, verbose_name='الفئة')
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_CHOICES, verbose_name='الحركة')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL, verbose_name='طريقة التسجيل')
    recorded_at = models.DateTimeField(auto_now_add=True, verbose_name='وقت التسجيل')
    recorded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='security_movements_recorded', verbose_name='سجل بواسطة',
    )
    notes = models.TextField(blank=True, verbose_name='ملاحظات')

    class Meta:
        ordering = ['-recorded_at', '-id']
        verbose_name = 'حركة أمن'
        verbose_name_plural = 'سجل الأمن'

    def __str__(self):
        return f'{self.get_movement_type_display()} - {self.person_name}'


class Customer(models.Model):
    customer_code = models.CharField(max_length=50, unique=True, verbose_name='كود العميل')
    customer_name = models.CharField(max_length=200, verbose_name='اسم العميل')
    customer_phone = models.CharField(max_length=50, unique=True, verbose_name='رقم الموبايل')
    national_id = models.CharField(max_length=50, blank=True, verbose_name='الرقم القومي')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['customer_name']
        verbose_name = 'عميل'
        verbose_name_plural = 'العملاء'

    def __str__(self):
        return f'{self.customer_name} - {self.customer_code}'

    @staticmethod
    def next_code():
        last = Customer.objects.order_by('-id').first()
        next_id = (last.id + 1) if last else 1
        code = f'C{next_id:05d}'
        while Customer.objects.filter(customer_code=code).exists():
            next_id += 1
            code = f'C{next_id:05d}'
        return code


class DailyBooking(models.Model):
    branch = models.ForeignKey(Branch, null=True, blank=True, on_delete=models.SET_NULL, related_name='daily_bookings', verbose_name='الفرع')
    customer_code = models.CharField(max_length=50, blank=True, verbose_name='كود العميل')
    venue = models.CharField(max_length=100, verbose_name='مكان الحجز')
    booking_date = models.DateField(verbose_name='تاريخ الحجز')
    start_time = models.CharField(max_length=50, verbose_name='من الساعة')
    end_time = models.CharField(max_length=50, verbose_name='إلى الساعة')
    customer_name = models.CharField(max_length=200, verbose_name='اسم العميل')
    customer_phone = models.CharField(max_length=50, verbose_name='رقم الموبايل')
    national_id = models.CharField(max_length=50, blank=True, verbose_name='الرقم القومي')
    players_count = models.PositiveIntegerField(default=1, verbose_name='عدد اللاعبين')
    amount = models.PositiveIntegerField(default=0, verbose_name='قيمة إيجار الساعة')
    advance_payment = models.PositiveIntegerField(default=0, verbose_name='مقدم الحجز')
    total_amount = models.PositiveIntegerField(default=0, verbose_name='إجمالي قيمة الحجز')
    remaining_amount = models.PositiveIntegerField(default=0, verbose_name='المتبقي')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-booking_date', 'start_time']
        verbose_name = 'حجز يومي'
        verbose_name_plural = 'الحجز اليومي'

    def __str__(self):
        return f'{self.customer_name} - {self.venue} - {self.booking_date}'


class DailyBookingCheckout(models.Model):
    booking = models.OneToOneField(DailyBooking, on_delete=models.CASCADE, related_name='checkout', verbose_name='الحجز اليومي')
    income_date = models.DateField(verbose_name='تاريخ الدخل اليومي')
    customer_name = models.CharField(max_length=200, verbose_name='اسم العميل')
    customer_phone = models.CharField(max_length=50, verbose_name='رقم الموبايل')
    venue = models.CharField(max_length=100, verbose_name='مكان الحجز')
    booking_date = models.DateField(verbose_name='تاريخ الحجز')
    start_time = models.CharField(max_length=50, verbose_name='من الساعة')
    end_time = models.CharField(max_length=50, verbose_name='إلى الساعة')
    total_amount = models.PositiveIntegerField(default=0, verbose_name='إجمالي قيمة الحجز')
    advance_payment = models.PositiveIntegerField(default=0, verbose_name='مقدم الحجز')
    remaining_amount = models.PositiveIntegerField(default=0, verbose_name='المتبقي')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='وقت عمل Checkout')

    class Meta:
        ordering = ['-income_date', 'start_time', 'customer_name']
        verbose_name = 'دخل يومي من Checkout'
        verbose_name_plural = 'الدخل اليومي من Checkout'

    def __str__(self):
        return f'{self.customer_name} - {self.income_date} - {self.total_amount}'


class DailyIncomeSupply(models.Model):
    branch = models.ForeignKey(Branch, null=True, blank=True, on_delete=models.SET_NULL, related_name='daily_income_supplies', verbose_name='الفرع')
    supply_date = models.DateField(verbose_name='تاريخ التوريد')
    amount = models.PositiveIntegerField(default=0, verbose_name='مبلغ التوريد')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-supply_date']
        verbose_name = 'توريد دخل يومي'
        verbose_name_plural = 'توريدات الدخل اليومي'

    def __str__(self):
        return f'{self.supply_date} - {self.amount}'


class FinancialVoucher(models.Model):
    branch = models.ForeignKey(Branch, null=True, blank=True, on_delete=models.SET_NULL, related_name='financial_vouchers', verbose_name='الفرع')
    TYPE_DISBURSEMENT = 'disbursement'
    TYPE_SUPPLY = 'supply'
    TYPE_CHOICES = [
        (TYPE_DISBURSEMENT, 'أمر صرف مبلغ مالي'),
        (TYPE_SUPPLY, 'أمر توريد مبلغ مالي'),
    ]

    voucher_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='نوع الأمر')
    amount = models.PositiveIntegerField(verbose_name='قيمة المبلغ')
    statement = models.TextField(verbose_name='السبب / البيان')
    voucher_date = models.DateField(verbose_name='التاريخ')
    signature_title = models.CharField(max_length=150, verbose_name='مسمى وظيفة التوقيع')
    signature_name = models.CharField(max_length=200, blank=True, verbose_name='اسم الموظف الموقّع')
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='financial_vouchers', verbose_name='أنشئ بواسطة',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-voucher_date', '-id']
        verbose_name = 'أمر صرف أو توريد مالي'
        verbose_name_plural = 'أوامر الصرف والتوريد المالية'

    @property
    def voucher_number(self):
        prefix = 'ص' if self.voucher_type == self.TYPE_DISBURSEMENT else 'ت'
        return f'{prefix}-{self.id:05d}' if self.id else f'{prefix}-جديد'

    @property
    def amount_in_words(self):
        from .number_words import egyptian_pounds_in_words
        return egyptian_pounds_in_words(self.amount)

    @property
    def day_name(self):
        return WEEKDAY_AR[self.voucher_date.weekday()]

    @property
    def signer_name(self):
        if self.signature_name:
            return self.signature_name
        employee = Employee.objects.filter(job_title=self.signature_title).order_by('name').first()
        return employee.name if employee else ''

    def __str__(self):
        return f'{self.get_voucher_type_display()} - {self.voucher_number}'


class AcademyMonthlyRentPayment(models.Model):
    academy = models.ForeignKey(Academy, on_delete=models.CASCADE, related_name='monthly_rent_payments', verbose_name='الأكاديمية')
    month = models.DateField(verbose_name='الشهر')
    expected_amount = models.PositiveIntegerField(default=0, verbose_name='الإيجار المستحق')
    paid_amount = models.PositiveIntegerField(default=0, verbose_name='المبلغ المسدد')
    supplied_amount = models.PositiveIntegerField(default=0, verbose_name='المبلغ المورد للشركة')
    payment_date = models.DateField(null=True, blank=True, verbose_name='تاريخ السداد')
    supplied_date = models.DateField(null=True, blank=True, verbose_name='تاريخ التوريد')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('academy', 'month')
        ordering = ['month', 'academy__name']
        verbose_name = 'سداد إيجار أكاديمية شهري'
        verbose_name_plural = 'سدادات إيجارات الأكاديميات الشهرية'

    @property
    def remaining_amount(self):
        return max(0, int(self.expected_amount or 0) - int(self.paid_amount or 0))

    @property
    def unsupplied_amount(self):
        return max(0, int(self.paid_amount or 0) - int(self.supplied_amount or 0))

    @property
    def is_paid(self):
        return int(self.paid_amount or 0) >= int(self.expected_amount or 0)

    @property
    def is_supplied(self):
        return int(self.supplied_amount or 0) >= int(self.paid_amount or 0) and int(self.paid_amount or 0) > 0

    def __str__(self):
        return f'{self.academy} - {self.month:%Y-%m}'


class AcademyDepositPlan(models.Model):
    academy = models.OneToOneField(
        Academy, on_delete=models.CASCADE, related_name='deposit_plan', verbose_name='الأكاديمية'
    )
    total_amount = models.PositiveIntegerField(default=0, verbose_name='إجمالي مبلغ التأمين')
    installments_count = models.PositiveSmallIntegerField(default=1, verbose_name='عدد الأقساط')
    first_due_month = models.DateField(verbose_name='شهر استحقاق أول قسط')
    notes = models.TextField(blank=True, verbose_name='ملاحظات الخطة')
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='created_deposit_plans', verbose_name='أنشأها',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['academy__name']
        verbose_name = 'خطة تأمين أكاديمية'
        verbose_name_plural = 'خطط تأمين الأكاديميات'

    @property
    def paid_total(self):
        return self.installments.aggregate(total=models.Sum('paid_amount'))['total'] or 0

    @property
    def supplied_total(self):
        return self.installments.aggregate(total=models.Sum('supplied_amount'))['total'] or 0

    @property
    def remaining_amount(self):
        return max(0, int(self.total_amount or 0) - int(self.paid_total or 0))

    @property
    def unsupplied_amount(self):
        return max(0, int(self.paid_total or 0) - int(self.supplied_total or 0))

    def __str__(self):
        return f'{self.academy} - {self.total_amount}'


class AcademyDepositInstallment(models.Model):
    plan = models.ForeignKey(
        AcademyDepositPlan, on_delete=models.CASCADE, related_name='installments', verbose_name='خطة التأمين'
    )
    installment_number = models.PositiveSmallIntegerField(verbose_name='رقم القسط')
    due_month = models.DateField(verbose_name='شهر الاستحقاق')
    due_amount = models.PositiveIntegerField(default=0, verbose_name='المبلغ المستحق')
    paid_amount = models.PositiveIntegerField(default=0, verbose_name='المبلغ المسدد')
    payment_date = models.DateField(null=True, blank=True, verbose_name='تاريخ السداد')
    supplied_amount = models.PositiveIntegerField(default=0, verbose_name='المبلغ المورد')
    supplied_date = models.DateField(null=True, blank=True, verbose_name='تاريخ التوريد')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    paid_recorded_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='recorded_deposit_payments', verbose_name='مسجل السداد',
    )
    supplied_recorded_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='recorded_deposit_supplies', verbose_name='مسجل التوريد',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('plan', 'installment_number')
        ordering = ['due_month', 'installment_number']
        verbose_name = 'قسط تأمين أكاديمية'
        verbose_name_plural = 'أقساط تأمين الأكاديميات'

    @property
    def remaining_amount(self):
        return max(0, int(self.due_amount or 0) - int(self.paid_amount or 0))

    @property
    def unsupplied_amount(self):
        return max(0, int(self.paid_amount or 0) - int(self.supplied_amount or 0))

    def __str__(self):
        return f'{self.plan.academy} - قسط {self.installment_number}'


class OperationDayCancellation(models.Model):
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='operation_day_cancellations',
        null=True,
        blank=True,
        verbose_name='الفرع',
    )
    cancel_date = models.DateField(verbose_name='تاريخ إلغاء التشغيل')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-cancel_date']
        verbose_name = 'إلغاء حجوزات يوم'
        verbose_name_plural = 'إلغاء حجوزات الأيام'
        constraints = [
            models.UniqueConstraint(fields=['branch', 'cancel_date'], name='unique_operation_cancellation_per_branch'),
        ]

    def __str__(self):
        return f'إلغاء حجوزات يوم {self.cancel_date}'


class AcademyOperationOverride(models.Model):
    academy = models.ForeignKey(Academy, on_delete=models.CASCADE, related_name='operation_overrides', verbose_name='الأكاديمية')
    booking_date = models.DateField(verbose_name='تاريخ التشغيل')
    original_place = models.CharField(max_length=100, verbose_name='مكان التدريب الأصلي')
    original_slot_index = models.PositiveIntegerField(verbose_name='ساعة التدريب الأصلية')
    new_place = models.CharField(max_length=100, blank=True, verbose_name='مكان التدريب الجديد')
    new_slot_index = models.PositiveIntegerField(null=True, blank=True, verbose_name='ساعة التدريب الجديدة')
    is_deleted = models.BooleanField(default=False, verbose_name='تم حذف الحجز')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('academy', 'booking_date', 'original_place', 'original_slot_index')
        ordering = ['-booking_date', 'academy__name']
        verbose_name = 'تعديل تشغيل أكاديمية'
        verbose_name_plural = 'تعديلات تشغيل الأكاديميات'

    def __str__(self):
        status = 'حذف' if self.is_deleted else 'تعديل'
        return f'{status} {self.academy.name} - {self.booking_date}'


class UserPermission(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='eess_permissions', verbose_name='المستخدم')
    can_academies = models.BooleanField(default=False, verbose_name='الأكاديميات')
    can_daily_booking = models.BooleanField(default=False, verbose_name='الحجز اليومي')
    can_daily_income = models.BooleanField(default=False, verbose_name='الدخل اليومي / الشهري')
    can_academy_rent = models.BooleanField(default=False, verbose_name='إيجارات الأكاديميات')
    can_operation = models.BooleanField(default=False, verbose_name='التشغيل')
    can_security = models.BooleanField(default=False, verbose_name='الأمن')
    can_shareholders = models.BooleanField(default=False, verbose_name='المساهمين')
    can_employees = models.BooleanField(default=False, verbose_name='الموظفين')
    can_general_expenses = models.BooleanField(default=False, verbose_name='المصروفات العامة')
    can_accounts = models.BooleanField(default=False, verbose_name='الحسابات')
    can_cafeteria = models.BooleanField(default=False, verbose_name='الكافيتريا')
    can_reports = models.BooleanField(default=False, verbose_name='التقارير')
    can_settings = models.BooleanField(default=False, verbose_name='الإعدادات')
    can_report_income = models.BooleanField(default=False, verbose_name='تقرير الدخل')
    can_report_shareholders = models.BooleanField(default=False, verbose_name='تقرير المساهمين والأرباح')
    can_report_employees = models.BooleanField(default=False, verbose_name='تقرير الموظفين')
    can_report_payroll = models.BooleanField(default=False, verbose_name='تقرير المرتبات والبونص')
    can_report_expenses = models.BooleanField(default=False, verbose_name='تقرير المصروفات')
    can_report_cafeteria = models.BooleanField(default=False, verbose_name='تقرير الكافيتريا')
    can_report_deposits = models.BooleanField(default=False, verbose_name='تقرير مبالغ التأمين')
    can_users = models.BooleanField(default=False, verbose_name='إدارة المستخدمين')
    button_permissions = models.JSONField(default=dict, blank=True, verbose_name='صلاحيات أزرار الموديولات')
    report_permissions = models.JSONField(default=dict, blank=True, verbose_name='صلاحيات أنواع التقارير')

    def can_access_any_report(self):
        return bool(
            any((self.report_permissions or {}).values()) or
            self.can_reports or self.can_security or self.can_report_income or self.can_report_shareholders or
            self.can_report_employees or self.can_report_payroll or self.can_report_expenses or
            self.can_report_cafeteria or self.can_report_deposits
        )

    class Meta:
        verbose_name = 'صلاحيات مستخدم'
        verbose_name_plural = 'صلاحيات المستخدمين'

    def __str__(self):
        return f'صلاحيات {self.user.username}'


class Shareholder(models.Model):
    name = models.CharField(max_length=200, verbose_name='اسم المساهم')
    national_id = models.CharField(max_length=50, blank=True, verbose_name='الرقم القومي')
    phone = models.CharField(max_length=50, blank=True, verbose_name='رقم الهاتف')
    email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني')
    share_percentage = models.PositiveIntegerField(default=0, verbose_name='نسبة المساهمة %')
    address = models.TextField(blank=True, verbose_name='العنوان')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'مساهم'
        verbose_name_plural = 'المساهمين'

    def __str__(self):
        return self.name




class JobTitle(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name='اسم الوظيفة')
    base_salary = models.PositiveIntegerField(default=0, verbose_name='أساسي المرتب')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'وظيفة متاحة'
        verbose_name_plural = 'الوظائف المتاحة'

    def __str__(self):
        return self.name


class BonusTier(models.Model):
    SOURCE_DAILY_BOOKING = 'daily_booking'
    SOURCE_CAFETERIA = 'cafeteria'
    SOURCE_CHOICES = [
        (SOURCE_DAILY_BOOKING, 'الدخل اليومي'),
        (SOURCE_CAFETERIA, 'دخل الكافيتريا'),
    ]
    job_title = models.ForeignKey(JobTitle, on_delete=models.CASCADE, related_name='bonus_tiers', verbose_name='الوظيفة')
    source_type = models.CharField(max_length=30, choices=SOURCE_CHOICES, default=SOURCE_DAILY_BOOKING, verbose_name='نوع الدخل')
    from_amount = models.PositiveIntegerField(default=0, verbose_name='من قيمة')
    to_amount = models.PositiveIntegerField(default=0, verbose_name='حتى قيمة')
    bonus_amount = models.PositiveIntegerField(default=0, verbose_name='قيمة البونص')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['job_title__name', 'source_type', 'from_amount']
        verbose_name = 'شريحة بونص'
        verbose_name_plural = 'شرائح البونص'

    def __str__(self):
        return f'{self.job_title} - {self.get_source_type_display()} - {self.from_amount} : {self.to_amount}'


class Employee(models.Model):
    branch = models.ForeignKey(Branch, null=True, blank=True, on_delete=models.SET_NULL, related_name='employees', verbose_name='الفرع')
    name = models.CharField(max_length=200, verbose_name='اسم الموظف')
    national_id = models.CharField(max_length=50, blank=True, verbose_name='الرقم القومي')
    phone = models.CharField(max_length=50, blank=True, verbose_name='رقم الهاتف')
    email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني')
    job_title = models.CharField(max_length=150, blank=True, verbose_name='الوظيفة')
    salary = models.PositiveIntegerField(default=0, verbose_name='الراتب')
    hire_date = models.DateField(null=True, blank=True, verbose_name='تاريخ التعيين')
    address = models.TextField(blank=True, verbose_name='العنوان')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'موظف'
        verbose_name_plural = 'الموظفين'

    def __str__(self):
        return self.name



class FoundingExpense(models.Model):
    branch = models.ForeignKey(Branch, null=True, blank=True, on_delete=models.SET_NULL, related_name='founding_expenses', verbose_name='الفرع')
    title = models.CharField(max_length=200, verbose_name='بيان مصروف التأسيس')
    expense_date = models.DateField(verbose_name='تاريخ المصروف')
    amount = models.PositiveIntegerField(default=0, verbose_name='القيمة')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-expense_date', 'title']
        verbose_name = 'مصروف تأسيس'
        verbose_name_plural = 'مصروفات التأسيس'

    def __str__(self):
        return f'{self.title} - {self.amount}'


class MonthlyExpense(models.Model):
    branch = models.ForeignKey(Branch, null=True, blank=True, on_delete=models.SET_NULL, related_name='monthly_expenses', verbose_name='الفرع')
    title = models.CharField(max_length=200, verbose_name='بيان المصروف الشهري')
    expense_month = models.DateField(verbose_name='شهر المصروف')
    amount = models.PositiveIntegerField(default=0, verbose_name='القيمة')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-expense_month', 'title']
        verbose_name = 'مصروف شهري'
        verbose_name_plural = 'المصروفات الشهرية'

    def __str__(self):
        return f'{self.title} - {self.amount}'


class DailyExpense(models.Model):
    branch = models.ForeignKey(Branch, null=True, blank=True, on_delete=models.SET_NULL, related_name='daily_expenses', verbose_name='الفرع')
    title = models.CharField(max_length=200, verbose_name='بيان المصروف اليومي')
    expense_date = models.DateField(verbose_name='تاريخ المصروف')
    amount = models.PositiveIntegerField(default=0, verbose_name='القيمة')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='daily_expenses_created',
        verbose_name='أدخل بواسطة',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-expense_date', 'title']
        verbose_name = 'مصروف يومي'
        verbose_name_plural = 'المصروفات اليومية'

    def __str__(self):
        return f'{self.title} - {self.amount}'

    @property
    def created_by_display(self):
        if not self.created_by_id:
            return '-'
        return self.created_by.get_full_name().strip() or self.created_by.username


class OperatingExpense(models.Model):
    branch = models.ForeignKey(Branch, null=True, blank=True, on_delete=models.SET_NULL, related_name='operating_expenses', verbose_name='الفرع')
    title = models.CharField(max_length=200, verbose_name='بيان مصروف التشغيل')
    expense_date = models.DateField(verbose_name='تاريخ المصروف')
    amount = models.PositiveIntegerField(default=0, verbose_name='قيمة المصروف')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-expense_date', 'title']
        verbose_name = 'مصروف تشغيل'
        verbose_name_plural = 'مصروفات التشغيل'

    def __str__(self):
        return f'{self.title} - {self.amount}'


class CafeteriaCategory(models.Model):
    code = models.PositiveIntegerField(unique=True, verbose_name='كود الفئة')
    name = models.CharField(max_length=200, unique=True, verbose_name='اسم الفئة')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['code', 'name']
        verbose_name = 'فئة صنف كافيتريا'
        verbose_name_plural = 'فئات أصناف الكافيتريا'

    def __str__(self):
        return f'{self.code} - {self.name}'


class CafeteriaItem(models.Model):
    branch = models.ForeignKey(Branch, null=True, blank=True, on_delete=models.SET_NULL, related_name='cafeteria_items', verbose_name='الفرع')
    category = models.ForeignKey(CafeteriaCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name='items', verbose_name='فئة الصنف')
    code = models.PositiveIntegerField(default=0, verbose_name='كود الصنف')
    name = models.CharField(max_length=200, verbose_name='اسم الصنف')
    opening_quantity = models.PositiveIntegerField(default=0, verbose_name='رصيد افتتاحي')
    stock_adjustment = models.IntegerField(default=0, verbose_name='تسوية المخزون')
    purchase_price = models.PositiveIntegerField(default=0, verbose_name='سعر الشراء')
    sale_price = models.PositiveIntegerField(default=0, verbose_name='سعر البيع')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category__code', 'code', 'name']
        unique_together = [('category', 'code')]
        verbose_name = 'صنف كافيتريا'
        verbose_name_plural = 'أصناف الكافيتريا'

    def __str__(self):
        return f'{self.code} - {self.name}' if self.code else self.name

    @property
    def purchased_quantity(self):
        return self.purchases.aggregate(total=models.Sum('quantity'))['total'] or 0

    @property
    def sold_quantity(self):
        return self.sales.aggregate(total=models.Sum('quantity'))['total'] or 0

    @property
    def stock_quantity(self):
        return int(self.opening_quantity + self.purchased_quantity - self.sold_quantity + self.stock_adjustment)

    @property
    def alert_limit(self):
        base_quantity = self.opening_quantity + self.purchased_quantity
        if base_quantity <= 0:
            return 0
        return max(1, int(base_quantity / 4))

    @property
    def is_low_stock(self):
        return self.alert_limit > 0 and self.stock_quantity < self.alert_limit


class CafeteriaPurchase(models.Model):
    item = models.ForeignKey(CafeteriaItem, on_delete=models.CASCADE, related_name='purchases', verbose_name='الصنف')
    purchase_date = models.DateField(verbose_name='تاريخ الشراء')
    quantity = models.PositiveIntegerField(default=1, verbose_name='الكمية')
    unit_price = models.PositiveIntegerField(default=0, verbose_name='سعر شراء الوحدة')
    supplier = models.CharField(max_length=200, blank=True, verbose_name='المورد')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-purchase_date']
        verbose_name = 'حركة شراء كافيتريا'
        verbose_name_plural = 'حركات شراء الكافيتريا'

    @property
    def total_amount(self):
        return int((self.quantity or 0) * (self.unit_price or 0))

    def __str__(self):
        return f'{self.item} - {self.quantity}'


class CafeteriaSale(models.Model):
    item = models.ForeignKey(CafeteriaItem, on_delete=models.CASCADE, related_name='sales', verbose_name='الصنف')
    sale_date = models.DateField(verbose_name='تاريخ البيع')
    quantity = models.PositiveIntegerField(default=1, verbose_name='الكمية')
    unit_price = models.PositiveIntegerField(default=0, verbose_name='سعر بيع الوحدة')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sale_date']
        verbose_name = 'حركة بيع كافيتريا'
        verbose_name_plural = 'حركات بيع الكافيتريا'

    @property
    def total_amount(self):
        return int((self.quantity or 0) * (self.unit_price or 0))

    @property
    def estimated_profit(self):
        purchase_price = self.item.purchase_price if self.item_id else 0
        return int((self.unit_price - purchase_price) * self.quantity)

    def __str__(self):
        return f'{self.item} - {self.quantity}'
