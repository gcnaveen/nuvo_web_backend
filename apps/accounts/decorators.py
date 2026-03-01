from django.http import JsonResponse
from functools import wraps


def require_auth(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user:
            return JsonResponse({
                "success": False,
                "message": "Authentication required",
                "data": {}
            }, status=401)

        return view_func(request, *args, **kwargs)

    return wrapper


def require_role(allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            if not request.user:
                return JsonResponse({
                    "success": False,
                    "message": "Authentication required",
                    "data": {}
                }, status=401)

            if request.user.role not in allowed_roles:
                return JsonResponse({
                    "success": False,
                    "message": "Permission denied",
                    "data": {}
                }, status=403)

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator