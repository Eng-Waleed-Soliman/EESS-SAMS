from .models import Branch


TRAINING_YEAR_CHOICES = [
    (f'{year}-{year + 1}', f'{year} - {year + 1}')
    for year in range(2026, 2100)
]


def selected_training_year(request):
    valid = {value for value, _ in TRAINING_YEAR_CHOICES}
    requested = (request.GET.get('training_year') or request.POST.get('training_year') or '').strip()
    if requested in valid:
        request.session['training_year'] = requested
        return requested
    saved = request.session.get('training_year')
    if saved in valid:
        return saved
    value = TRAINING_YEAR_CHOICES[0][0]
    request.session['training_year'] = value
    return value


def selected_branch(request):
    """Return (branch, all_branches). Selection is persisted per signed-in session."""
    branches = Branch.objects.all().order_by('name')
    requested = request.GET.get('branch_id')
    if requested is None:
        requested = request.POST.get('branch_context')
    if requested == 'all':
        request.session['active_branch_id'] = 'all'
        return None, True
    if requested:
        try:
            branch = branches.get(pk=int(requested))
        except (TypeError, ValueError, Branch.DoesNotExist):
            branch = None
        if branch:
            request.session['active_branch_id'] = branch.pk
            return branch, False
    saved = request.session.get('active_branch_id')
    if saved == 'all':
        return None, True
    try:
        branch = branches.get(pk=int(saved))
    except (TypeError, ValueError, Branch.DoesNotExist):
        branch = branches.first()
    if branch:
        request.session['active_branch_id'] = branch.pk
        return branch, False
    return None, True

