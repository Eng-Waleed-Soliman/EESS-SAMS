from .models import AppSetting


def app_settings(request):
    try:
        return {'app_settings': AppSetting.current()}
    except Exception:
        return {'app_settings': None}
