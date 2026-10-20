from pathlib import Path

from django.test import SimpleTestCase


class RenderRuntimeConfigurationTests(SimpleTestCase):
    def test_memory_safe_worker_has_thread_capacity_without_preload_copy(self):
        render_config = (
            Path(__file__).resolve().parent.parent / 'render.yaml'
        ).read_text(encoding='utf-8')

        self.assertIn('healthCheckPath: /health/', render_config)
        self.assertNotIn('--preload', render_config)
        self.assertIn('--workers 1', render_config)
        self.assertIn('--threads 4', render_config)
        self.assertIn('--max-requests 1000', render_config)
        self.assertNotIn('--max-requests 200', render_config)

    def test_render_applies_migrations_even_when_dashboard_overrides_start_command(self):
        project_root = Path(__file__).resolve().parent.parent
        render_config = (project_root / 'render.yaml').read_text(encoding='utf-8')
        wsgi_source = (project_root / 'sams_project' / 'wsgi.py').read_text(encoding='utf-8')

        self.assertIn('python manage.py migrate --noinput', render_config)
        self.assertIn("os.getenv('AUTO_MIGRATE_ON_START')", wsgi_source)
        self.assertIn("os.getenv('RENDER', 'False')", wsgi_source)
        self.assertIn('SELECT pg_advisory_lock(%s)', wsgi_source)
        self.assertIn("call_command('migrate'", wsgi_source)
