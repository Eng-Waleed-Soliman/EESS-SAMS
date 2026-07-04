from calendar import monthrange
from decimal import Decimal
import datetime
from django.db import models
from django.contrib.auth.models import User
from .constants import WEEKDAY_AR


def split_values(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split(',') if item.strip()]


class Academy(models.Model):
    name = models.CharField(max_length=200, verbose_name='اسم الأكاديمية')
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
    security_deposit = models.PositiveIntegerField(default=0, verbose_name='مبلغ التأمين')
    training_days = models.CharField(max_length=250, blank=True, verbose_name='أيام التدريب')
    training_hours = models.TextField(blank=True, verbose_name='ساعات التدريب الأساسية')
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
        return f'C{next_id:05d}'


class DailyBooking(models.Model):
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


class OperationDayCancellation(models.Model):
    cancel_date = models.DateField(unique=True, verbose_name='تاريخ إلغاء التشغيل')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-cancel_date']
        verbose_name = 'إلغاء حجوزات يوم'
        verbose_name_plural = 'إلغاء حجوزات الأيام'

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
    can_operation = models.BooleanField(default=False, verbose_name='التشغيل')
    can_shareholders = models.BooleanField(default=False, verbose_name='المساهمين')
    can_employees = models.BooleanField(default=False, verbose_name='الموظفين')
    can_general_expenses = models.BooleanField(default=False, verbose_name='المصروفات العامة')
    can_cafeteria = models.BooleanField(default=False, verbose_name='الكافيتريا')
    can_reports = models.BooleanField(default=False, verbose_name='التقارير')
    can_report_income = models.BooleanField(default=False, verbose_name='تقرير الدخل')
    can_report_shareholders = models.BooleanField(default=False, verbose_name='تقرير المساهمين والأرباح')
    can_report_employees = models.BooleanField(default=False, verbose_name='تقرير الموظفين')
    can_report_payroll = models.BooleanField(default=False, verbose_name='تقرير المرتبات والبونص')
    can_report_expenses = models.BooleanField(default=False, verbose_name='تقرير المصروفات')
    can_report_cafeteria = models.BooleanField(default=False, verbose_name='تقرير الكافيتريا')
    can_report_deposits = models.BooleanField(default=False, verbose_name='تقرير مبالغ التأمين')
    can_users = models.BooleanField(default=False, verbose_name='إدارة المستخدمين')

    def can_access_any_report(self):
        return bool(
            self.can_reports or self.can_report_income or self.can_report_shareholders or
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
    title = models.CharField(max_length=200, verbose_name='بيان المصروف اليومي')
    expense_date = models.DateField(verbose_name='تاريخ المصروف')
    amount = models.PositiveIntegerField(default=0, verbose_name='القيمة')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-expense_date', 'title']
        verbose_name = 'مصروف يومي'
        verbose_name_plural = 'المصروفات اليومية'

    def __str__(self):
        return f'{self.title} - {self.amount}'


class OperatingExpense(models.Model):
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


class CafeteriaItem(models.Model):
    name = models.CharField(max_length=200, verbose_name='اسم الصنف')
    opening_quantity = models.PositiveIntegerField(default=0, verbose_name='رصيد افتتاحي')
    purchase_price = models.PositiveIntegerField(default=0, verbose_name='سعر الشراء')
    sale_price = models.PositiveIntegerField(default=0, verbose_name='سعر البيع')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'صنف كافيتريا'
        verbose_name_plural = 'أصناف الكافيتريا'

    def __str__(self):
        return self.name

    @property
    def purchased_quantity(self):
        return self.purchases.aggregate(total=models.Sum('quantity'))['total'] or 0

    @property
    def sold_quantity(self):
        return self.sales.aggregate(total=models.Sum('quantity'))['total'] or 0

    @property
    def stock_quantity(self):
        return int(self.opening_quantity + self.purchased_quantity - self.sold_quantity)

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
