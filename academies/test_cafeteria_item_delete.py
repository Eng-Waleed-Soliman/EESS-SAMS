from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    Branch,
    CafeteriaCategory,
    CafeteriaItem,
    CafeteriaPurchase,
    CafeteriaRecipeComponent,
    CafeteriaSale,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class CafeteriaItemDeleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='item-delete-admin',
            email='item-delete@example.com',
            password='test-password',
        )
        self.client.force_login(self.user)
        self.branch = Branch.objects.create(name='Delete Branch', short_name='DEL')
        session = self.client.session
        session['active_branch_id'] = self.branch.pk
        session.save()
        self.category = CafeteriaCategory.objects.create(code=9801, name='خامات الحذف')

    def create_item(self, code, name, item_type=CafeteriaItem.TYPE_COUNT):
        return CafeteriaItem.objects.create(
            branch=self.branch,
            category=self.category,
            code=code,
            name=name,
            item_type=item_type,
            sale_price=10,
        )

    def archive_item(self, item):
        return self.client.post(reverse('cafe_item_delete', args=[item.pk]))

    def test_item_used_in_recipe_is_archived_without_deleting_recipe(self):
        component = self.create_item(9802, 'مكوّن مستخدم', CafeteriaItem.TYPE_WEIGHT)
        product = self.create_item(9803, 'صنف مختلط', CafeteriaItem.TYPE_MIXED)
        recipe = CafeteriaRecipeComponent.objects.create(
            product=product,
            component=component,
            quantity=25,
        )

        response = self.client.get(reverse('cafe_item_delete', args=[component.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'جميع المعاملات السابقة ستظل محفوظة')
        self.assertContains(response, 'وصفات تستخدم الصنف كمكوّن: 1')
        self.assertContains(response, '<button class="btn btn-danger">حذف</button>', html=False)

        post_response = self.archive_item(component)
        self.assertRedirects(post_response, reverse('cafe_item_list'))
        component.refresh_from_db()
        self.assertFalse(component.is_active)
        self.assertTrue(CafeteriaRecipeComponent.objects.filter(pk=recipe.pk).exists())

        edit_response = self.client.get(reverse('cafe_item_update', args=[product.pk]))
        self.assertContains(edit_response, component.name)

    def test_item_with_purchase_is_archived_and_history_preserved(self):
        item = self.create_item(9804, 'صنف له شراء')
        purchase = CafeteriaPurchase.objects.create(
            item=item,
            purchase_date=date.today(),
            quantity=3,
            unit_price=7,
        )

        response = self.client.get(reverse('cafe_item_delete', args=[item.pk]))

        self.assertContains(response, 'حركات الشراء المحفوظة: 1')
        post_response = self.archive_item(item)
        self.assertRedirects(post_response, reverse('cafe_item_list'))
        item.refresh_from_db()
        self.assertFalse(item.is_active)
        self.assertTrue(CafeteriaPurchase.objects.filter(pk=purchase.pk).exists())

    def test_archived_item_is_hidden_from_new_actions_but_sale_report_is_preserved(self):
        item = self.create_item(9805, 'صنف له مبيعات محفوظة')
        sale = CafeteriaSale.objects.create(
            item=item,
            sale_date=date.today(),
            quantity=2,
            unit_price=10,
        )

        response = self.archive_item(item)

        self.assertRedirects(response, reverse('cafe_item_list'))
        item.refresh_from_db()
        self.assertFalse(item.is_active)
        self.assertTrue(CafeteriaSale.objects.filter(pk=sale.pk).exists())

        item_list_response = self.client.get(reverse('cafe_item_list'))
        self.assertNotContains(item_list_response, item.name)

        sale_create_response = self.client.get(reverse('cafe_sale_create'))
        self.assertNotContains(sale_create_response, item.name)

        report_response = self.client.get(
            reverse('cafe_daily_sales'),
            {'date_from': date.today().isoformat(), 'date_to': date.today().isoformat()},
        )
        self.assertContains(report_response, item.name)
        self.assertEqual(report_response.context['total_amount'], 20)
