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

    def test_item_used_in_recipe_shows_reason_instead_of_server_error(self):
        component = self.create_item(9802, 'مكوّن مستخدم', CafeteriaItem.TYPE_WEIGHT)
        product = self.create_item(9803, 'صنف مختلط', CafeteriaItem.TYPE_MIXED)
        CafeteriaRecipeComponent.objects.create(
            product=product,
            component=component,
            quantity=25,
        )

        response = self.client.get(reverse('cafe_item_delete', args=[component.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'لا يمكن حذف')
        self.assertContains(response, 'مستخدم كمكوّن في وصفات: صنف مختلط')
        self.assertNotContains(response, '<button class="btn btn-danger">حذف</button>', html=False)

        post_response = self.client.post(reverse('cafe_item_delete', args=[component.pk]))
        self.assertRedirects(post_response, reverse('cafe_item_list'))
        self.assertTrue(CafeteriaItem.objects.filter(pk=component.pk).exists())

    def test_item_with_purchase_is_preserved_to_protect_history(self):
        item = self.create_item(9804, 'صنف له شراء')
        CafeteriaPurchase.objects.create(
            item=item,
            purchase_date=date.today(),
            quantity=3,
            unit_price=7,
        )

        response = self.client.get(reverse('cafe_item_delete', args=[item.pk]))

        self.assertContains(response, 'حركات الشراء: 1')
        post_response = self.client.post(reverse('cafe_item_delete', args=[item.pk]))
        self.assertRedirects(post_response, reverse('cafe_item_list'))
        self.assertTrue(CafeteriaItem.objects.filter(pk=item.pk).exists())
        self.assertTrue(CafeteriaPurchase.objects.filter(item=item).exists())

    def test_unused_item_can_still_be_deleted(self):
        item = self.create_item(9805, 'صنف غير مستخدم')

        response = self.client.post(reverse('cafe_item_delete', args=[item.pk]))

        self.assertRedirects(response, reverse('cafe_item_list'))
        self.assertFalse(CafeteriaItem.objects.filter(pk=item.pk).exists())
