from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Branch, CafeteriaCategory, CafeteriaItem, CafeteriaSale


@override_settings(SECURE_SSL_REDIRECT=False)
class CafeteriaDailySalesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='daily-sales-admin',
            email='daily-sales@example.com',
            password='test-password',
        )
        self.client.force_login(self.user)
        self.branch = Branch.objects.create(name='Daily Sales Branch', short_name='DSB')
        self.other_branch = Branch.objects.create(name='Other Daily Sales Branch', short_name='ODSB')
        session = self.client.session
        session['active_branch_id'] = self.branch.pk
        session.save()

        self.first_category = CafeteriaCategory.objects.create(code=9910, name='الفئة الأولى')
        self.second_category = CafeteriaCategory.objects.create(code=9920, name='الفئة الثانية')
        self.weight_item = CafeteriaItem.objects.create(
            branch=self.branch,
            category=self.first_category,
            code=9911,
            name='صنف كمي',
            item_type=CafeteriaItem.TYPE_WEIGHT,
            sale_price=100,
        )
        self.mixed_item = CafeteriaItem.objects.create(
            branch=self.branch,
            category=self.first_category,
            code=9912,
            name='صنف مختلط',
            item_type=CafeteriaItem.TYPE_MIXED,
            sale_price=40,
        )
        self.count_item = CafeteriaItem.objects.create(
            branch=self.branch,
            category=self.second_category,
            code=9921,
            name='صنف عددي',
            item_type=CafeteriaItem.TYPE_COUNT,
            sale_price=10,
        )
        other_item = CafeteriaItem.objects.create(
            branch=self.other_branch,
            category=self.second_category,
            code=9922,
            name='صنف فرع آخر',
            item_type=CafeteriaItem.TYPE_COUNT,
            sale_price=999,
        )

        today = date.today()
        CafeteriaSale.objects.create(item=self.count_item, sale_date=today, quantity=2, unit_price=10)
        CafeteriaSale.objects.create(item=self.weight_item, sale_date=today, quantity=500, unit_price=100)
        CafeteriaSale.objects.create(item=self.mixed_item, sale_date=today, quantity=2, unit_price=40)
        CafeteriaSale.objects.create(item=self.count_item, sale_date=today - timedelta(days=1), quantity=8, unit_price=10)
        CafeteriaSale.objects.create(item=other_item, sale_date=today, quantity=1, unit_price=999)

    def test_inventory_has_same_size_daily_sales_button(self):
        response = self.client.get(reverse('cafe_inventory'))
        self.assertContains(response, reverse('cafe_daily_sales'))
        self.assertContains(response, 'مبيعات اليوم')
        self.assertContains(response, 'class="btn btn-warning cafe-inventory-action"', count=1)
        self.assertContains(response, 'class="btn btn-info cafe-inventory-action"', count=1)
        self.assertContains(response, 'width:210px!important')

    def test_daily_sales_are_grouped_sorted_scoped_and_totalled(self):
        response = self.client.get(reverse('cafe_daily_sales'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['item_name'] for row in response.context['rows']], [
            'صنف كمي', 'صنف مختلط', 'صنف عددي',
        ])
        self.assertEqual([row['item_type'] for row in response.context['rows']], [
            'كمي', 'مختلط', 'عددي',
        ])
        self.assertEqual([row['sale_amount'] for row in response.context['rows']], [50, 80, 20])
        self.assertEqual(response.context['total_amount'], 150)
        self.assertNotContains(response, 'صنف فرع آخر')
        self.assertContains(response, 'إجمالي المبيعات')
        self.assertContains(response, '150 جنيه')

    def test_category_filter_updates_rows_and_total(self):
        response = self.client.get(reverse('cafe_daily_sales'), {
            'category': self.second_category.pk,
        })
        self.assertEqual([row['item_name'] for row in response.context['rows']], ['صنف عددي'])
        self.assertEqual(response.context['total_amount'], 20)
        self.assertEqual(response.context['selected_category'], self.second_category.pk)
        self.assertContains(response, '20 جنيه')
        self.assertNotContains(response, 'صنف كمي')
        self.assertNotContains(response, 'صنف مختلط')