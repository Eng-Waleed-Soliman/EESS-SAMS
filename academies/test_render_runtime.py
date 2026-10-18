from pathlib import Path

from django.test import SimpleTestCase


class RenderRuntimeConfigurationTests(SimpleTestCase):
    def test_memory_safe_worker_is_preloaded_with_thread_capacity(self):
        render_config = (
            Path(__file__).resolve().parent.parent / 'render.yaml'
        ).read_text(encoding='utf-8')

        self.assertIn('healthCheckPath: /health/', render_config)
        self.assertIn('--preload', render_config)
        self.assertIn('--workers 1', render_config)
        self.assertIn('--threads 4', render_config)
        self.assertIn('--max-requests 1000', render_config)
        self.assertNotIn('--max-requests 200', render_config)
