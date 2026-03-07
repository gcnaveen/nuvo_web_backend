# apps/accounts/models.py
#
# Auth-related models ONLY.
# User and all profile models live in apps/users/models.py
#
import uuid
import random
from datetime import datetime, timedelta
from mongoengine import Document, StringField, DateTimeField, IntField, BooleanField


class OTP(Document):
    meta = {"collection": "otps"}

    id            = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))
    email         = StringField(required=True)
    otp_code      = StringField(required=True)
    created_at    = DateTimeField(default=datetime.utcnow)
    expires_at    = DateTimeField()
    attempt_count = IntField(default=0)
    is_verified   = BooleanField(default=False)

    @staticmethod
    def generate_otp():
        return str(random.randint(1000, 9999))

    @staticmethod
    def expiry_time():
        return datetime.utcnow() + timedelta(minutes=5)


class BlacklistedToken(Document):
    meta = {"collection": "blacklisted_tokens"}

    token          = StringField(required=True)
    blacklisted_at = DateTimeField(default=datetime.utcnow)