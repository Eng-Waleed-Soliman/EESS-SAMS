import logging
import time
import hashlib

from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.core import signing
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
        if request.user.is_authenticated and not (request.user.is_superuser or request.user.is_staff):
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


class SecurityGuardAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not (request.user.is_superuser or request.user.is_staff):
            from .models import UserPermission
            profile = UserPermission.objects.filter(user=request.user, security_only=True).first()
            if profile:
                request.security_guard_profile = profile
                if not profile.security_branch_id:
                    if request.path != reverse('logout'):
                        return HttpResponseForbidden('لم يتم تحديد فرع لهذا الحساب. راجع المسؤول.')
                allowed = request.path.startswith(('/security/', '/static/')) or request.path in (reverse('logout'), '/media-db/branding/1/company_logo/')
                if not allowed:
                    if request.method not in ('GET', 'HEAD'):
                        return HttpResponseForbidden('هذا الحساب مخصص للأمن فقط.')
                    return redirect('security_home')
        return self.get_response(request)


logger = logging.getLogger(__name__)


CAFETERIA_SPECIALIST_USERNAME = 'cafeteria_specialist'
EXTERNAL_CAFETERIA_ACCESS_SALT = 'eess.external-cafeteria-access.v1'
EXTERNAL_CAFETERIA_ACCESS_MAX_AGE = 2 * 60 * 60


def external_cafeteria_username(employee_id):
    return f"bicchub_{hashlib.sha256(str(employee_id).encode('utf-8')).hexdigest()[:24]}"


def external_cafeteria_user(identity):
    username = external_cafeteria_username(identity['employee_id'])
    user, created = User.objects.get_or_create(username=username)
    if created:
        user.set_unusable_password()
    first_name = str(identity.get('name') or '')[:150]
    if created or user.first_name != first_name:
        user.first_name = first_name
        user.save(update_fields=['password', 'first_name'] if created else ['first_name'])
    return user


def issue_external_cafeteria_access(identity):
    return signing.dumps(identity, salt=EXTERNAL_CAFETERIA_ACCESS_SALT, compress=True)


def load_external_cafeteria_access(token):
    try:
        identity = signing.loads(
            token,
            salt=EXTERNAL_CAFETERIA_ACCESS_SALT,
            max_age=EXTERNAL_CAFETERIA_ACCESS_MAX_AGE,
        )
    except signing.BadSignature:
        return None
    if not isinstance(identity, dict):
        return None
    employee_id = str(identity.get('employee_id') or '').strip()
    name = str(identity.get('name') or '').strip()
    if not employee_id or not name:
        return None
    return {
        'employee_id': employee_id[:100],
        'name': name[:200],
        'job_title': str(identity.get('job_title') or '')[:200],
        'department': str(identity.get('department') or '')[:200],
        'academic_year': str(identity.get('academic_year') or '')[:20],
    }


def is_cafeteria_specialist(user):
    return bool(
        getattr(user, 'is_authenticated', False) and
        (getattr(user, 'username', '') or '').strip().lower() == CAFETERIA_SPECIALIST_USERNAME
    )


class ExternalCafeteriaEmployeeAccessMiddleware:
    """Keep BICCHub employee sessions inside the staff-ordering experience."""

    allowed_prefixes = (
        '/cafeteria/orders/',
        '/cafeteria/external-access/',
        '/logout/',
        '/static/',
        '/media/',
        '/media-db/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        access_token = ''
        if request.path.startswith('/cafeteria/orders/'):
            access_token = (request.GET.get('access') or request.POST.get('access') or '').strip()
        restored_identity = load_external_cafeteria_access(access_token) if access_token else None
        if restored_identity:
            preserve_internal_login = (
                request.user.is_authenticated
                and not (request.user.username or '').startswith('bicchub_')
            )
            if not preserve_internal_login:
                expected_username = external_cafeteria_username(restored_identity['employee_id'])
                if not request.user.is_authenticated or request.user.username != expected_username:
                    login(
                        request,
                        external_cafeteria_user(restored_identity),
                        backend='django.contrib.auth.backends.ModelBackend',
                    )
            request.session['external_cafeteria_employee'] = restored_identity
            request.external_cafeteria_access = access_token

        identity = request.session.get('external_cafeteria_employee') if hasattr(request, 'session') else None
        if identity and request.user.is_authenticated:
            request.external_cafeteria_employee = identity
            cafeteria_only = (request.user.username or '').startswith('bicchub_')
            request.external_cafeteria_only = cafeteria_only
            if cafeteria_only and not any(request.path.startswith(prefix) for prefix in self.allowed_prefixes):
                logout(request)
                if request.method not in ('GET', 'HEAD'):
                    return HttpResponseForbidden('هذا الحساب مخصص لطلبات الكافيتريا فقط.')
                return redirect('login')
            if not cafeteria_only and not request.path.startswith('/cafeteria/orders/'):
                request.session.pop('external_cafeteria_employee', None)
                request.external_cafeteria_employee = None
        return self.get_response(request)


class CafeteriaSpecialistAccessMiddleware:
    allowed_prefixes = (
        '/cafeteria/sales/',
        '/cafeteria/menu/',
        '/cafeteria/orders/',
        '/cafeteria/inventory/',
        '/cafeteria/daily-sales/',
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
        if is_cafeteria_specialist(request.user) and not getattr(request, 'restricted_academy_profile', None) and not getattr(request, 'security_guard_profile', None):
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
