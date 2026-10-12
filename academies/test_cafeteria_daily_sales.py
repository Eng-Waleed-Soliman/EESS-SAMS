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

    def test_inventory_has_same_size_sales_report_button(self):
        response = self.client.get(reverse('cafe_inventory'))
        self.assertContains(response, reverse('cafe_daily_sales'))
        self.assertContains(response, 'تقرير المبيعات')
        self.assertNotContains(response, '>مبيعات اليوم</a>')
        self.assertContains(response, 'class="btn btn-warning cafe-inventory-action"', count=1)
        self.assertContains(response, 'class="btn btn-info cafe-inventory-action"', count=1)
        self.assertContains(response, 'width:210px!important')

    def test_default_report_is_today_grouped_sorted_scoped_and_totalled(self):
        response = self.client.get(reverse('cafe_daily_sales'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['date_from'], date.today())
        self.assertEqual(response.context['date_to'], date.today())
        self.assertEqual([row['item_name'] for row in response.context['rows']], [
            'صنف كمي', 'صنف مختلط', 'صنف عددي',
        ])
        self.assertEqual([row['item_type'] for row in response.context['rows']], [
            'كمي', 'مختلط', 'عددي',
        ])
        self.assertEqual([row['quantity'] for row in response.context['rows']], [500, 2, 2])
        self.assertEqual([row['sale_price'] for row in response.context['rows']], ['100', '40', '10'])
        self.assertEqual([row['sale_amount'] for row in response.context['rows']], [50, 80, 20])
        self.assertEqual(response.context['total_amount'], 150)
        self.assertNotContains(response, 'صنف فرع آخر')
        self.assertContains(response, 'تقرير المبيعات')
        self.assertContains(response, 'الكمية المباعة')
        self.assertContains(response, 'سعر البيع')
        self.assertNotContains(response, '<th>كود الصنف</th>')
        self.assertNotContains(response, '>عرض</button>')
        self.assertContains(response, 'name="category" data-auto-submit')
        self.assertContains(response, 'name="date_from" value=')
        self.assertContains(response, 'name="date_to" value=')
        self.assertContains(response, '150 جنيه')
        self.assertContains(response, '<select class="form-select" id="categoryFilter"', html=False)
        self.assertNotContains(response, 'إلغاء فلتر الفئة')
        self.assertNotContains(response, 'يتم تحديث التقرير تلقائيًا')

    def test_category_filter_hides_category_column_automatically(self):
        response = self.client.get(reverse('cafe_daily_sales'), {
            'category': self.second_category.pk,
        })
        self.assertEqual([row['item_name'] for row in response.context['rows']], ['صنف عددي'])
        self.assertEqual(response.context['total_amount'], 20)
        self.assertEqual(response.context['selected_category'], self.second_category.pk)
        self.assertNotContains(response, '<th>الفئة</th>')
        self.assertNotContains(response, 'data-label="الفئة"')
        self.assertContains(response, '20 جنيه')
        self.assertNotContains(response, 'صنف كمي')
        self.assertNotContains(response, 'صنف مختلط')
        self.assertContains(response, '<select class="form-select category-filter-active" id="categoryFilter"', html=False)
        self.assertNotContains(response, 'إلغاء فلتر الفئة')
        self.assertNotContains(response, 'يتم تحديث التقرير تلقائيًا')

    def test_income_sort_dropdown_orders_rows_in_both_directions(self):
        default_response = self.client.get(reverse('cafe_daily_sales'))
        self.assertContains(default_response, 'ترتيب الأصناف')
        self.assertContains(default_response, 'أعلى دخل')
        self.assertContains(default_response, 'أقل دخل')

        descending = self.client.get(reverse('cafe_daily_sales'), {'sort': 'income_desc'})
        self.assertEqual([row['item_name'] for row in descending.context['rows']], [
            'صنف مختلط', 'صنف كمي', 'صنف عددي',
        ])
        self.assertEqual(descending.context['selected_sort'], 'income_desc')
        self.assertContains(descending, 'name="sort" value="income_desc"')

        ascending = self.client.get(reverse('cafe_daily_sales'), {'sort': 'income_asc'})
        self.assertEqual([row['item_name'] for row in ascending.context['rows']], [
            'صنف عددي', 'صنف كمي', 'صنف مختلط',
        ])
        self.assertEqual(ascending.context['selected_sort'], 'income_asc')
        self.assertContains(ascending, 'name="sort" value="income_asc"')

    def test_cafeteria_analysis_can_chart_monthly_sold_items_by_income(self):
        today = date.today()
        training_year = (
            f'{today.year}-{today.year + 1}'
            if today.month >= 7
            else f'{today.year - 1}-{today.year}'
        )
        base_params = {
            'report_type': 'statistical_analysis',
            'analysis_metric': 'cafeteria',
            'training_year': training_year,
            'analysis_month': today.strftime('%Y-%m'),
        }
        default_response = self.client.get(reverse('reports_home'), base_params)
        self.assertEqual(default_response.status_code, 200)
        self.assertContains(default_response, 'الأصناف المباعة')
        self.assertContains(default_response, 'name="analysis_month"')
        self.assertNotContains(default_response, 'analysis-cafeteria-items-labels')

        response = self.client.get(reverse('reports_home'), {
            **base_params,
            'cafeteria_items': '1',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['cafeteria_items_requested'])
        self.assertTrue(response.context['cafeteria_items_has_values'])
        item_chart = next(
            chart for chart in response.context['analysis_charts']
            if chart['key'] == 'cafeteria_items_income'
        )
        expected_count_income = 20
        if (today - timedelta(days=1)).month == today.month:
            expected_count_income += 80
        expected_rows = sorted([
            ('صنف عددي', expected_count_income),
            ('صنف كمي', 50),
            ('صنف مختلط', 80),
        ], key=lambda row: -row[1])
        self.assertEqual(item_chart['labels'], [row[0] for row in expected_rows])
        self.assertEqual(item_chart['values'], [row[1] for row in expected_rows])
        self.assertEqual(item_chart['total'], sum(row[1] for row in expected_rows))
        self.assertNotIn('صنف فرع آخر', item_chart['labels'])
        self.assertContains(response, 'data-labels-source="analysis-cafeteria-items-labels"')
        self.assertContains(response, 'id="analysis-cafeteria-items-labels"')
        self.assertContains(response, 'reverse: false')

    def test_date_range_includes_sales_from_every_selected_day(self):
        today = date.today()
        yesterday = today - timedelta(days=1)
        response = self.client.get(reverse('cafe_daily_sales'), {
            'category': self.second_category.pk,
            'date_from': yesterday.isoformat(),
            'date_to': today.isoformat(),
        })
        self.assertEqual(response.context['date_from'], yesterday)
        self.assertEqual(response.context['date_to'], today)
        self.assertEqual(len(response.context['rows']), 1)
        self.assertEqual(response.context['rows'][0]['quantity'], 10)
        self.assertEqual(response.context['rows'][0]['sale_price'], '10')
        self.assertEqual(response.context['total_amount'], 100)
        self.assertContains(response, '100 جنيه')