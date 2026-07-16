import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sams_project.settings')
application = get_wsgi_application()


def _apply_pending_migrations():
    """Keep Render's database schema in sync even when its dashboard start command is plain gunicorn."""
    if os.getenv('AUTO_MIGRATE_ON_START', 'True').strip().lower() not in {'1', 'true', 'yes', 'on'}:
        return
    from django.core.management import call_command
    from django.db import connection

    if connection.vendor == 'postgresql':
        lock_id = 82633741025
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_lock(%s)', [lock_id])
        try:
            call_command('migrate', interactive=False, verbosity=0)
        finally:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_unlock(%s)', [lock_id])
    else:
        call_command('migrate', interactive=False, verbosity=0)


_apply_pending_migrations()
