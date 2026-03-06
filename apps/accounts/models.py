# apps/accounts/models.py
import uuid
import random
from datetime import datetime, timedelta
from mongoengine import Document, StringField, DateTimeField, IntField, BooleanField


class OTP(Document):
    meta = {"collection": "otps"}

    id = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))
    email = StringField(required=True)

    otp_code = StringField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    expires_at = DateTimeField()
    attempt_count = IntField(default=0)
    is_verified = BooleanField(default=False)

    @staticmethod
    def generate_otp():
        return str(random.randint(100000, 999999))

    @staticmethod
    def expiry_time():
        return datetime.utcnow() + timedelta(minutes=5)


class BlacklistedToken(Document):
    meta = {"collection": "blacklisted_tokens"}

    token = StringField(required=True)
    blacklisted_at = DateTimeField(default=datetime.utcnow)


# ─────────────────────────────────────────────────────────────
# apps/users/models.py
# ─────────────────────────────────────────────────────────────
import uuid
from datetime import datetime
from mongoengine import (
    Document,
    StringField,
    EmailField,
    DateTimeField,
    FloatField,
    IntField,
    ListField,
    URLField,
    BooleanField,
    ReferenceField,
)
from apps.common.constants import UserRole, UserStatus, SubscriptionPlan


class User(Document):
    meta = {"collection": "users"}

    id = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))

    email = EmailField(required=True, unique=True)
    phone_number = StringField(required=True, unique=True)

    # Present on all users; mandatory only for ADMIN self-registration
    full_name = StringField(default="")

    # Hashed password — only used for ADMIN accounts
    password = StringField(default="")

    role = StringField(
        choices=[r.value for r in UserRole],
        required=True
    )

    status = StringField(
        choices=[s.value for s in UserStatus],
        default=UserStatus.ACTIVE.value
    )

    # False until an existing ADMIN explicitly approves the account.
    # Clients are auto-approved on first OTP verify.
    # Staff, MakeupArtist and new Admins start as False.
    is_approved = BooleanField(default=False)

    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)


class ClientProfile(Document):
    meta = {"collection": "client_profiles"}

    user = ReferenceField(User, required=True, unique=True)

    full_name = StringField()
    city = StringField()
    state = StringField()
    country = StringField()

    subscription_plan = StringField(
        choices=[p.value for p in SubscriptionPlan],
        default=SubscriptionPlan.SILVER.value
    )

    joined_date = DateTimeField(default=datetime.utcnow)


class StaffProfile(Document):
    meta = {"collection": "staff_profiles"}

    user = ReferenceField(User, required=True, unique=True)

    full_name = StringField()
    stage_name = StringField()
    gender = StringField()
    date_of_birth = DateTimeField()

    city = StringField()
    state = StringField()
    country = StringField()

    profile_picture = URLField()
    gallery_images = ListField(URLField())

    height = FloatField()
    weight = FloatField()

    package = StringField()
    price_of_staff = FloatField()
    experience_in_years = IntField()

    joined_date = DateTimeField(default=datetime.utcnow)


class MakeupArtistProfile(Document):
    meta = {"collection": "makeup_artist_profiles"}

    user = ReferenceField(User, required=True, unique=True)

    full_name = StringField()
    gender = StringField()
    makeup_speciality = StringField()

    city = StringField()
    state = StringField()
    country = StringField()

    experience_in_years = IntField()

    joined_date = DateTimeField(default=datetime.utcnow)


# ─────────────────────────────────────────────────────────────
# apps/common/constants.py
# ─────────────────────────────────────────────────────────────
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    CLIENT = "CLIENT"
    STAFF = "STAFF"
    MAKEUP_ARTIST = "MAKEUP_ARTIST"


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    BLOCKED = "BLOCKED"
    PENDING = "PENDING"          # Awaiting admin approval


class SubscriptionPlan(str, Enum):
    SILVER = "SILVER"
    BRONZE = "BRONZE"
    GOLD = "GOLD"
    PLATINUM = "PLATINUM"
    DIAMOND = "DIAMOND"