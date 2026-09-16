import logging
import time

from django.db import connections
from django.db.utils import InterfaceError, OperationalError
from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from django.urls import reverse


class RestrictedAcademyAccessMiddleware:
    """Fail closed for academy-only accounts, including direct URLs and writes."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            from .models import UserPermission
            profile = UserPermission.objects.filter(user=request.user, academy_only=True).first()
            if profile:
                request.restricted_academy_profile = profile
                allowed = request.path in (reverse('restricted_academy_portal'), reverse('logout'))
                allowed = allowed or request.path.startswith('/static/')
                # Only the shared company logo is needed by this isolated portal.
                allowed = allowed or request.path == '/media-db/branding/1/company_logo/'
                if not allowed:
                    if request.method not in ('GET', 'HEAD'):
                        return HttpResponseForbidden('ليس لديك صلاحية الوصول إلى هذا الإجراء.')
                    return redirect('restricted_academy_portal')
        return self.get_response(request)


logger = logging.getLogger(__name__)


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
        '/cafeteria/cash-supplies/',
        '/cafeteria/operating-expenses/',
        '/logout/',
        '/login/',
        '/static/',
        '/media/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_cafeteria_specialist(request.user) and not getattr(request, 'restricted_academy_profile', None):
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
