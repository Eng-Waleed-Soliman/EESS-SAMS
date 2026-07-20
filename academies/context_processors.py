from .models import AppSetting, Branch
from .middleware import is_cafeteria_specialist
from .branching import TRAINING_YEAR_CHOICES, selected_branch, selected_training_year


def app_settings(request):
    try:
        branch, all_branches = selected_branch(request)
        # The images themselves can be several megabytes.  The sidebar only
        # needs their saved names because it serves the bytes through the
        # persistent-media endpoint.  Deferring the binary columns keeps every
        # management page small and prevents Render from timing out while
        # opening settings screens.
        settings_object, _ = AppSetting.objects.defer(
            'company_logo_data',
            'main_screen_image_data',
        ).get_or_create(pk=1)
        return {
            'app_settings': settings_object,
            'is_cafeteria_specialist': is_cafeteria_specialist(request.user),
            'available_branches': Branch.objects.defer(
                'logo_data',
                'image_data',
            ).order_by('name'),
            'active_branch': branch,
            'active_branch_is_all': all_branches,
            'active_branch_value': 'all' if all_branches else str(branch.pk),
            'training_year_choices': TRAINING_YEAR_CHOICES,
            'training_year': selected_training_year(request),
        }
    except Exception:
        return {
            'app_settings': None,
            'is_cafeteria_specialist': is_cafeteria_specialist(request.user),
        }
