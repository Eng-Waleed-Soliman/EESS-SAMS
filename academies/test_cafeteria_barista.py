from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import CafeteriaItemForm
from .models import Branch, CafeteriaCategory, CafeteriaItem, CafeteriaSale


@override_settings(SECURE_SSL_REDIRECT=False)
class CafeteriaBaristaItemTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='barista-report-admin',
            email='barista@example.com',
            password='test-password',
        )
        self.client.force_login(self.user)
        self.branch = Branch.objects.create(name='Barista Branch', short_name='BAR')
        session = self.client.session
        session['active_branch_id'] = self.branch.pk
        session.save()
        self.drinks = CafeteriaCategory.objects.create(code=100, name='مشروبات')
        self.snacks = CafeteriaCategory.objects.create(code=200, name='مأكولات')
        self.barista_best = CafeteriaItem.objects.create(
            branch=self.branch, category=self.drinks, code=2, name='قهوة باريستا',
            opening_quantity=20, purchase_price=10, sale_price=25, is_barista_item=True,
        )
        self.barista_unsold = CafeteriaItem.objects.create(
            branch=self.branch, category=self.drinks, code=3, name='لاتيه باريستا',
            opening_quantity=20, purchase_price=10, sale_price=30, is_barista_item=True,
        )
        self.regular_item = CafeteriaItem.objects.create(
            branch=self.branch, category=self.snacks, code=1, name='ساندويتش',
            opening_quantity=20, purchase_price=5, sale_price=15,
        )
        CafeteriaSale.objects.create(
            item=self.barista_best, sale_date=date.today(), quantity=5, unit_price=25,
        )
        CafeteriaSale.objects.create(
            item=self.regular_item, sale_date=date.today(), quantity=2, unit_price=15,
        )

    def get_statistics(self, cafeteria_sort=None):
        params = {
            'report_type': 'cafeteria',
            'month': date.today().strftime('%Y-%m'),
            'section': 'statistics',
        }
        if cafeteria_sort:
            params['cafeteria_sort'] = cafeteria_sort
        return self.client.get(reverse('reports_home'), params)

    def test_item_form_saves_and_displays_barista_checkbox(self):
        create_page = self.client.get(reverse('cafe_item_create'))
        self.assertContains(create_page, 'name="is_barista_item"')
        self.assertContains(create_page, 'صنف باريستا')

        form = CafeteriaItemForm(data={
            'category': self.drinks.pk,
            'code': 4,
            'name': 'كابتشينو',
            'item_type': CafeteriaItem.TYPE_COUNT,
            'opening_quantity': 10,
            'purchase_price': 10,
            'sale_price': 30,
            'is_barista_item': 'on',
            'notes': '',
        })
        self.assertTrue(form.is_valid(), form.errors.as_json())
        item = form.save()
        self.assertTrue(item.is_barista_item)

        update_page = self.client.get(reverse('cafe_item_update', args=[self.barista_best.pk]))
        self.assertContains(update_page, 'name="is_barista_item"')
        self.assertContains(update_page, 'checked')

    def test_statistics_support_all_requested_sort_choices(self):
        best_selling = self.get_statistics()
        self.assertEqual(best_selling.status_code, 200)
        self.assertEqual(best_selling.context['cafeteria_sort'], 'best_selling')
        self.assertEqual(
            [row['item'].pk for row in best_selling.context['cafeteria_statistics']],
            [self.barista_best.pk, self.regular_item.pk, self.barista_unsold.pk],
        )
        for value, label in [
            ('category', 'حسب الفئة'),
            ('best_selling', 'الأكثر مبيعًا'),
            ('barista', 'أصناف الباريستا'),
        ]:
            self.assertContains(best_selling, f'value="{value}"')
            self.assertContains(best_selling, label)

        by_category = self.get_statistics('category')
        self.assertEqual(
            [row['item'].pk for row in by_category.context['cafeteria_statistics']],
            [self.barista_best.pk, self.barista_unsold.pk, self.regular_item.pk],
        )
        self.assertContains(by_category, 'إحصائيات الأصناف مرتبة حسب الفئة')

        barista_only = self.get_statistics('barista')
        self.assertEqual(
            [row['item'].pk for row in barista_only.context['cafeteria_statistics']],
            [self.barista_best.pk, self.barista_unsold.pk],
        )
        self.assertContains(barista_only, 'إحصائيات أصناف الباريستا')
        self.assertNotContains(barista_only, self.regular_item.name)

    def test_invalid_sort_value_falls_back_to_best_selling(self):
        response = self.get_statistics('not-valid')
        self.assertEqual(response.context['cafeteria_sort'], 'best_selling')
        self.assertEqual(response.context['cafeteria_statistics'][0]['item'], self.barista_best)