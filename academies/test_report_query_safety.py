from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse


@override_settings(SECURE_SSL_REDIRECT=False)
class ReportQuerySafetyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='report-query-safety',
            password='test-password',
            email='reports@example.com',
        )
        self.client.force_login(self.user)

    def test_report_queries_never_select_binary_media_columns(self):
        report_types = (
            'monthly_income',
            'statistical_analysis',
            'employees',
            'academies',
            'expenses',
            'cafeteria',
            'security_log',
        )
        forbidden_columns = (
            'logo_data',
            'website_image_data',
            'manager_photo_data',
            'image_data',
        )

        for report_type in report_types:
            with self.subTest(report_type=report_type):
                with CaptureQueriesContext(connection) as queries:
                    response = self.client.get(
                        reverse('reports_home'),
                        {'report_type': report_type},
                    )

                self.assertEqual(response.status_code, 200)
                selected_sql = '\n'.join(
                    query['sql'].lower()
                    for query in queries.captured_queries
                    if query['sql'].lstrip().lower().startswith('select')
                )
                for column in forbidden_columns:
                    self.assertNotIn(
                        f'"{column}"',
                        selected_sql,
                        msg=f'{report_type} unexpectedly selected {column}',
                    )
