from django.contrib.auth.models import User
from django.test import TestCase, override_settings
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

    def test_cafeteria_binary_images_are_served_separately(self):
        response = self.client.get(
            reverse('persistent_media', args=['cafeteria_item', self.item.pk, 'image'])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'item-image')
        self.assertEqual(response['Content-Type'], 'image/jpeg')

    def test_item_edit_uses_media_url_instead_of_base64_html(self):
        response = self.client.get(reverse('cafe_item_update', args=[self.item.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse('persistent_media', args=['cafeteria_item', self.item.pk, 'image']),
        )
        self.assertNotContains(response, 'data:image/jpeg;base64')