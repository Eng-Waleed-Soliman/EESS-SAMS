import json
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import CafeteriaRecipeComponentFormSet
from .models import CafeteriaCategory, CafeteriaItem, CafeteriaSale


@override_settings(SECURE_SSL_REDIRECT=False)
class CafeteriaItemRecipeRulesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='recipe-rules-admin',
            email='recipe@example.com',
            password='test-password',
        )
        self.client.force_login(self.user)
        self.raw_category = CafeteriaCategory.objects.create(
            code=700, name='الخامات', show_in_sales=True,
        )
        self.other_category = CafeteriaCategory.objects.create(
            code=100, name='مشروبات غازية', show_in_sales=True,
        )
        self.raw_item = CafeteriaItem.objects.create(
            category=self.raw_category, code=701, name='بن خام',
            item_type=CafeteriaItem.TYPE_WEIGHT, opening_quantity=1000,
        )
        self.other_item = CafeteriaItem.objects.create(
            category=self.other_category, code=101, name='مياه معدنية',
            opening_quantity=10, purchase_price=5, sale_price=10,
        )

    def test_raw_material_category_never_appears_or_sells_directly(self):
        page = self.client.get(reverse('cafe_sale_list'))
        self.assertNotContains(page, f'data-category="{self.raw_category.pk}"')
        self.assertNotContains(page, self.raw_item.name)
        self.assertNotIn(self.raw_item.pk, [row['id'] for row in page.context['items']])
        self.assertNotIn(
            self.raw_item.pk,
            page.context['form'].fields['item'].queryset.values_list('pk', flat=True),
        )

        response = self.client.post(reverse('cafe_sale_list'), {
            'sale_date': date.today().isoformat(),
            'checkout_action': 'sale',
            'order_items': json.dumps([{'item_id': self.raw_item.pk, 'quantity': 1}]),
        })
        self.assertRedirects(response, reverse('cafe_sale_list'))
        self.assertFalse(CafeteriaSale.objects.filter(item=self.raw_item).exists())

    def test_recipe_component_choices_only_include_raw_material_category(self):
        page = self.client.get(reverse('cafe_item_create'))
        component_queryset = page.context['recipe_formset'].forms[0].fields['component'].queryset
        self.assertQuerySetEqual(component_queryset, [self.raw_item], transform=lambda item: item)
        self.assertContains(page, 'تظهر هنا أصناف فئة الخامات فقط')

    def test_recipe_validation_rejects_items_outside_raw_material_category(self):
        product = CafeteriaItem(
            category=self.other_category, code=102, name='مشروب مختلط',
            item_type=CafeteriaItem.TYPE_MIXED, sale_price=20,
        )
        formset = CafeteriaRecipeComponentFormSet(data={
            'recipe-TOTAL_FORMS': '1',
            'recipe-INITIAL_FORMS': '0',
            'recipe-MIN_NUM_FORMS': '0',
            'recipe-MAX_NUM_FORMS': '1000',
            'recipe-0-component': str(self.other_item.pk),
            'recipe-0-quantity': '1',
        }, instance=product, prefix='recipe')
        self.assertFalse(formset.is_valid())
        self.assertIn('فئة الخامات فقط', str(formset.non_form_errors()))

    def test_weight_type_hides_purchase_and_sale_price_fields(self):
        page = self.client.get(reverse('cafe_item_create'))
        self.assertContains(page, "purchaseWrap.style.display = type === 'count' ? '' : 'none';")
        self.assertContains(page, "saleWrap.style.display = type === 'weight' ? 'none' : '';")
        self.assertNotContains(page, 'سعر الشراء للكيلوجرام')
        self.assertNotContains(page, 'سعر البيع للكيلوجرام')