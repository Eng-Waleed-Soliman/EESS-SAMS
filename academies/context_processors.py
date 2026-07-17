from .models import AppSetting, Branch
from .middleware import is_cafeteria_specialist
from .branching import TRAINING_YEAR_CHOICES, selected_branch, selected_training_year


def app_settings(request):
    try:
        branch, all_branches = selected_branch(request)
        return {
            'app_settings': AppSetting.current(),
            'is_cafeteria_specialist': is_cafeteria_specialist(request.user),
            'available_branches': Branch.objects.all().order_by('name'),
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
