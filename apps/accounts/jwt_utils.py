import jwt
from datetime import datetime, timedelta
from django.conf import settings


def generate_access_token(user):
    payload = {
        "user_id": user.id,
        "email": user.email,
        "role": user.role,
        "type": "access",
        "exp": datetime.utcnow() + timedelta(hours=1)
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def generate_refresh_token(user):
    payload = {
        "user_id": user.id,
        "type": "refresh",
        "exp": datetime.utcnow() + timedelta(days=7)
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token):
    return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])