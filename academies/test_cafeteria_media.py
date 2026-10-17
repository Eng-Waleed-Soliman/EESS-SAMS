from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import CafeteriaCategory, CafeteriaItem


@override_settings(SECURE_SSL_REDIRECT=False)
class CafeteriaMediaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('media-admin', 'admin@example.com', 'test-password')
        self.client.force_login(self.user)
        self.category = CafeteriaCategory.objects.create(
            code=100,
            name='مشروبات',
            image_data=b'category-image',
            image_content_type='image/png',
            image_name='category.png',
        )
        self.item = CafeteriaItem.objects.create(
            category=self.category,
            code=101,
            name='مياه',
            image_data=b'item-image',
            image_content_type='image/jpeg',
            image_name='item.jpg',
        )

    def test_cafeteria_item_images_are_not_served(self):
        response = self.client.get(
            reverse('persistent_media', args=['cafeteria_item', self.item.pk, 'image'])
        )
        self.assertEqual(response.status_code, 404)

    def test_item_edit_and_list_do_not_show_image_controls_or_images(self):
        edit_response = self.client.get(reverse('cafe_item_update', args=[self.item.pk]))
        self.assertEqual(edit_response.status_code, 200)
        self.assertNotContains(edit_response, 'name="image"')
        self.assertNotContains(edit_response, 'multipart/form-data')
        self.assertContains(edit_response, 'name="name"')
        self.assertContains(edit_response, 'name="name_en"')

        list_response = self.client.get(reverse('cafe_item_list'))
        self.assertEqual(list_response.status_code, 200)
        self.assertNotContains(list_response, '<th>الصورة</th>', html=True)
        self.assertNotContains(
            list_response,
            reverse('persistent_media', args=['cafeteria_item', self.item.pk, 'image']),
        )
    def test_item_edit_recipe_choices_do_not_fetch_binary_images(self):
        ingredients = CafeteriaCategory.objects.create(code=700, name='الخامات')
        CafeteriaItem.objects.create(
            category=ingredients,
            code=701,
            name='خام',
            image_data=b'x' * (1024 * 1024),
            image_content_type='image/jpeg',
            image_name='ingredient.jpg',
        )

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('cafe_item_update', args=[self.item.pk]))

        self.assertEqual(response.status_code, 200)
        item_queries = [
            query['sql'].lower()
            for query in queries.captured_queries
            if 'cafeteriaitem' in query['sql'].lower()
        ]
        self.assertTrue(item_queries)
        self.assertFalse(any('image_data' in sql for sql in item_queries))