import jwt
from django.conf import settings
from django.http import JsonResponse
from apps.users.models import User


class JWTAuthenticationMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.user = None

        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

            try:
                payload = jwt.decode(
                    token,
                    settings.SECRET_KEY,
                    algorithms=["HS256"]
                )

                user = User.objects.get(id=payload["user_id"])
                if user.status == "BLOCKED":
                    return JsonResponse({
                        "success": False,
                        "message": "User is blocked",
                        "data": {}
                    }, status=403)

                request.user = user

            except jwt.ExpiredSignatureError:
                return JsonResponse({
                    "success": False,
                    "message": "Token expired",
                    "data": {}
                }, status=401)

            except Exception:
                return JsonResponse({
                    "success": False,
                    "message": "Invalid token",
                    "data": {}
                }, status=401)

        return self.get_response(request)