from django.contrib import admin
from .models import (
    Academy, Customer, DailyBooking, Shareholder, Employee,
    FoundingExpense, MonthlyExpense, DailyExpense,
    CafeteriaItem, CafeteriaPurchase, CafeteriaSale,
    OperationDayCancellation, AcademyOperationOverride, UserPermission, DailyBookingCheckout,
    DailyIncomeSupply,
)


@admin.register(Academy)
class AcademyAdmin(admin.ModelAdmin):
    list_display = ('name', 'sport_activity', 'manager_name', 'manager_phone', 'contract_end_date', 'subscription_type', 'security_deposit')
    search_fields = ('name', 'sport_activity', 'manager_name', 'manager_phone')


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
    list_display = ('title', 'expense_date', 'amount')
    search_fields = ('title', 'notes')


@admin.register(CafeteriaItem)
class CafeteriaItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'purchase_price', 'sale_price', 'stock_quantity', 'is_low_stock')
    search_fields = ('name',)


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
    list_display = ('user', 'can_academies', 'can_daily_booking', 'can_operation', 'can_reports', 'can_report_income', 'can_report_expenses', 'can_users')
