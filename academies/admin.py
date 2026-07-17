from django.contrib import admin
from .models import (
    Academy, Customer, DailyBooking, Shareholder, Employee,
    FoundingExpense, MonthlyExpense, DailyExpense,
    CafeteriaCategory, CafeteriaItem, CafeteriaPurchase, CafeteriaSale,
    OperationDayCancellation, AcademyOperationOverride, UserPermission, DailyBookingCheckout,
    DailyIncomeSupply, AppSetting, Branch, Facility, SportActivityMedia, Activity, AcademyMember, AcademyMonthlyRentPayment,
    AcademyDepositPlan, AcademyDepositInstallment,
    FinancialVoucher,
)


@admin.register(Academy)
class AcademyAdmin(admin.ModelAdmin):
    list_display = ('name', 'branch', 'sport_activity', 'manager_name', 'manager_phone', 'contract_end_date', 'subscription_type', 'security_deposit')
    search_fields = ('name', 'sport_activity', 'manager_name', 'manager_phone', 'branch__name')


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ('program_name', 'company_name', 'updated_at')


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'created_at')
    search_fields = ('name', 'location', 'notes')


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ('name', 'branch', 'facility_type', 'hourly_rent', 'daily_rent', 'created_at')
    search_fields = ('name', 'branch__name', 'notes')


@admin.register(SportActivityMedia)
class SportActivityMediaAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    search_fields = ('name', 'description')


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('name', 'income_type', 'training_places', 'eess_share_percentage', 'is_active')
    search_fields = ('name', 'training_places', 'notes')


@admin.register(AcademyMember)
class AcademyMemberAdmin(admin.ModelAdmin):
    list_display = ('academy', 'role', 'name', 'job_title', 'birth_date', 'phone', 'monthly_subscription', 'is_active')
    list_filter = ('role', 'is_active')
    search_fields = ('academy__name', 'name', 'job_title', 'phone', 'national_id')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('customer_code', 'customer_name', 'customer_phone', 'national_id')
    search_fields = ('customer_code', 'customer_name', 'customer_phone', 'national_id')


@admin.register(DailyBooking)
class DailyBookingAdmin(admin.ModelAdmin):
    list_display = ('customer_code', 'customer_name', 'customer_phone', 'venue', 'booking_date', 'start_time', 'end_time', 'amount', 'total_amount', 'advance_payment', 'remaining_amount')
    search_fields = ('customer_code', 'customer_name', 'customer_phone', 'venue')


@admin.register(DailyBookingCheckout)
class DailyBookingCheckoutAdmin(admin.ModelAdmin):
    list_display = ('income_date', 'customer_name', 'customer_phone', 'venue', 'booking_date', 'start_time', 'end_time', 'total_amount', 'advance_payment', 'remaining_amount')
    search_fields = ('customer_name', 'customer_phone', 'venue')


@admin.register(DailyIncomeSupply)
class DailyIncomeSupplyAdmin(admin.ModelAdmin):
    list_display = ('supply_date', 'amount', 'updated_at')
    search_fields = ('supply_date', 'notes')


@admin.register(AcademyMonthlyRentPayment)
class AcademyMonthlyRentPaymentAdmin(admin.ModelAdmin):
    list_display = ('academy', 'month', 'expected_amount', 'paid_amount', 'supplied_amount', 'updated_at')
    list_filter = ('month',)
    search_fields = ('academy__name', 'notes')


@admin.register(AcademyDepositPlan)
class AcademyDepositPlanAdmin(admin.ModelAdmin):
    list_display = ('academy', 'total_amount', 'installments_count', 'first_due_month', 'paid_total', 'remaining_amount', 'supplied_total', 'unsupplied_amount')
    search_fields = ('academy__name', 'notes')


@admin.register(AcademyDepositInstallment)
class AcademyDepositInstallmentAdmin(admin.ModelAdmin):
    list_display = ('plan', 'installment_number', 'due_month', 'due_amount', 'paid_amount', 'supplied_amount', 'remaining_amount', 'unsupplied_amount')
    list_filter = ('due_month',)
    search_fields = ('plan__academy__name', 'notes')


@admin.register(FinancialVoucher)
class FinancialVoucherAdmin(admin.ModelAdmin):
    list_display = ('voucher_number', 'voucher_type', 'voucher_date', 'amount', 'signature_title', 'created_by')
    list_filter = ('voucher_type', 'voucher_date')
    search_fields = ('statement', 'signature_title')


@admin.register(Shareholder)
class ShareholderAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'share_percentage')
    search_fields = ('name', 'phone', 'national_id')


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'job_title', 'phone', 'salary')
    search_fields = ('name', 'job_title', 'phone', 'national_id')


@admin.register(FoundingExpense)
class FoundingExpenseAdmin(admin.ModelAdmin):
    list_display = ('title', 'expense_date', 'amount')
    search_fields = ('title', 'notes')


@admin.register(MonthlyExpense)
class MonthlyExpenseAdmin(admin.ModelAdmin):
    list_display = ('title', 'expense_month', 'amount')
    search_fields = ('title', 'notes')


@admin.register(DailyExpense)
class DailyExpenseAdmin(admin.ModelAdmin):
    list_display = ('title', 'expense_date', 'amount', 'created_by')
    search_fields = ('title', 'notes', 'created_by__username', 'created_by__first_name', 'created_by__last_name')


@admin.register(CafeteriaCategory)
class CafeteriaCategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('name',)
    ordering = ('code', 'name')


@admin.register(CafeteriaItem)
class CafeteriaItemAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'purchase_price', 'sale_price', 'stock_quantity', 'is_low_stock')
    search_fields = ('name', 'category__name')
    list_filter = ('category',)
    ordering = ('category__code', 'code', 'name')


@admin.register(CafeteriaPurchase)
class CafeteriaPurchaseAdmin(admin.ModelAdmin):
    list_display = ('item', 'purchase_date', 'quantity', 'unit_price', 'total_amount')


@admin.register(CafeteriaSale)
class CafeteriaSaleAdmin(admin.ModelAdmin):
    list_display = ('item', 'sale_date', 'quantity', 'unit_price', 'total_amount', 'estimated_profit')


@admin.register(OperationDayCancellation)
class OperationDayCancellationAdmin(admin.ModelAdmin):
    list_display = ('cancel_date', 'created_at')


@admin.register(AcademyOperationOverride)
class AcademyOperationOverrideAdmin(admin.ModelAdmin):
    list_display = ('academy', 'booking_date', 'original_place', 'original_slot_index', 'new_place', 'new_slot_index', 'is_deleted')


@admin.register(UserPermission)
class UserPermissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'can_academies', 'can_daily_booking', 'can_daily_income', 'can_academy_rent', 'can_operation', 'can_accounts', 'can_cafeteria', 'can_reports', 'can_settings', 'can_users')
