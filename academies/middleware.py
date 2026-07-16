import logging
import time
import traceback

from django.db import connections
from django.db.utils import InterfaceError, OperationalError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin


logger = logging.getLogger(__name__)


class AdminDiagnosticMiddleware(MiddlewareMixin):
    """Temporarily expose a traceback only to the short-lived diagnostic account."""

    diagnostic_username = '__codex_admin_diag__'

    def process_exception(self, request, exception):
        user = getattr(request, 'user', None)
        if getattr(user, 'is_authenticated', False) and user.username == self.diagnostic_username:
            return JsonResponse({
                'exception_type': type(exception).__name__,
                'message': str(exception),
                'traceback': traceback.format_exc(),
            }, status=500)
        return None


CAFETERIA_SPECIALIST_USERNAME = 'cafeteria_specialist'


def is_cafeteria_specialist(user):
    return bool(
        getattr(user, 'is_authenticated', False) and
        (getattr(user, 'username', '') or '').strip().lower() == CAFETERIA_SPECIALIST_USERNAME
    )


class CafeteriaSpecialistAccessMiddleware:
    allowed_prefixes = (
        '/cafeteria/sales/',
        '/cafeteria/menu/',
        '/cafeteria/inventory/',
        '/logout/',
        '/login/',
        '/static/',
        '/media/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_cafeteria_specialist(request.user):
            if not any(request.path.startswith(prefix) for prefix in self.allowed_prefixes):
                return redirect('cafe_sale_list')
        return self.get_response(request)


class DatabaseRetryMiddleware:
    """Retry a read request once when a pooled Neon connection has gone stale."""

    retryable_methods = {'GET', 'HEAD', 'OPTIONS'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except (OperationalError, InterfaceError):
            already_retried = getattr(request, '_database_retry_attempted', False)
            if request.method not in self.retryable_methods or already_retried:
                raise
            request._database_retry_attempted = True
            logger.warning('Retrying a read request after a transient database connection error.')
            connections.close_all()
            time.sleep(0.2)
            return self.get_response(request)
