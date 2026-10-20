import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sams_project.settings')
application = get_wsgi_application()


def _apply_pending_migrations():
    """Keep Render's database schema in sync even when its dashboard start command is plain gunicorn."""
    # Render always exposes RENDER=true.  Use it as the safe default because a
    # dashboard-managed service may ignore render.yaml's start command.  An
    # explicit AUTO_MIGRATE_ON_START value still wins, including an explicit
    # false value for environments that manage migrations separately.
    auto_migrate = os.getenv('AUTO_MIGRATE_ON_START')
    if auto_migrate is None:
        auto_migrate = os.getenv('RENDER', 'False')
    if auto_migrate.strip().lower() not in {'1', 'true', 'yes', 'on'}:
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
