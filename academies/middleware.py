from django.shortcuts import redirect


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
