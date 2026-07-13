from .models import AppSetting
from .middleware import is_cafeteria_specialist


def app_settings(request):
    try:
        return {
            'app_settings': AppSetting.current(),
            'is_cafeteria_specialist': is_cafeteria_specialist(request.user),
        }
    except Exception:
        return {
            'app_settings': None,
            'is_cafeteria_specialist': is_cafeteria_specialist(request.user),
        }
