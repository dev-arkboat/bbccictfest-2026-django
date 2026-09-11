from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import Role, role_rank

#: Minimum rank per layer name.
LAYER_MIN_RANK = {
    "volunteer": 1,
    "campus_ambassador": 2,
    "organizer": 3,
    "superuser": 4,
}


def role_required(min_role: str = Role.VOLUNTEER):
    """Gate a view behind the layered admin system.

    Usage: ``@role_required("organizer")``. Superusers always pass.
    Anonymous users are sent to login; under-ranked users get bounced
    home with an error message.
    """
    min_rank = LAYER_MIN_RANK.get(min_role, 1)

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if role_rank(request.user) >= min_rank:
                return view_func(request, *args, **kwargs)
            messages.error(request, "You do not have permission to access that page.")
            return redirect("core:home")

        return _wrapped

    return decorator


volunteer_required = role_required("volunteer")
organizer_required = role_required("organizer")
