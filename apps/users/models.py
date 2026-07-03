# apps/users/models.py
#
# Single source of truth for ALL user and profile models.
#
# Import guide for the rest of the codebase:
#   from apps.users.models import User, ClientProfile, StaffProfile, MakeupArtistProfile
#   from apps.accounts.models import OTP, BlacklistedToken      ← auth only
#   from apps.common.constants import UserRole, UserStatus, SubscriptionPlan
#
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


# ─────────────────────────────────────────────────────────────
#  User  (core account — all roles)
# ─────────────────────────────────────────────────────────────

class User(Document):
    meta = {"collection": "users"}

    id           = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))

    email        = EmailField(required=True, unique=True)
    phone_number = StringField(default="", sparse=True)


    # full_name is mandatory for ADMIN registration; optional for other roles
    # (their name lives in the role-specific profile instead)
    full_name    = StringField(default="")

    # Hashed password — used only for ADMIN web panel login
    # Staff / Client / MakeupArtist authenticate via OTP, so password stays ""
    password     = StringField(default="")

    role = StringField(
        choices=[r.value for r in UserRole],
        required=True,
    )

    status = StringField(
        choices=[s.value for s in UserStatus],
        default=UserStatus.ACTIVE.value,
    )

    # Approval gate:
    #   ADMIN       → starts False, another admin must approve
    #   STAFF       → starts False, admin must approve
    #   MAKEUP_ARTIST → starts False, admin must approve
    #   CLIENT      → set to True automatically on first OTP verify
    is_approved = BooleanField(default=False)

    created_at  = DateTimeField(default=datetime.utcnow)
    updated_at  = DateTimeField(default=datetime.utcnow)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────
#  ClientProfile
# ─────────────────────────────────────────────────────────────

class ClientProfile(Document):
    meta = {"collection": "client_profiles"}

    user = ReferenceField(User, required=True, unique=True)

    full_name = StringField()
    city      = StringField()
    state     = StringField()
    country   = StringField()

    subscription_plan = StringField(
        choices=[p.value for p in SubscriptionPlan],
        default=SubscriptionPlan.SILVER.value,
    )

    joined_date = DateTimeField(default=datetime.utcnow)


# ─────────────────────────────────────────────────────────────
# StaffProfile
# ─────────────────────────────────────────────────────────────

class StaffProfile(Document):
    meta = {"collection": "staff_profiles"}

    user = ReferenceField(User, required=True, unique=True)

    # ── Basic identity ─────────────────────────────────────────
    full_name   = StringField()
    stage_name  = StringField()      # auto-generated on self-register
    gender      = StringField()

    # ── Personal info (from registration form) ─────────────────
    first_name      = StringField()
    last_name       = StringField()
    date_of_birth   = DateTimeField()
    place_of_birth  = StringField()
    marital_status  = StringField()  # single | married
    address         = StringField()

    # ── Location ───────────────────────────────────────────────
    city    = StringField()
    state   = StringField()
    country = StringField()

    # ── Contact ────────────────────────────────────────────────
    telephone    = StringField()
    cell_phone   = StringField()

    # ── Physical dimensions ────────────────────────────────────
    height       = FloatField()   # cm
    weight       = FloatField()   # kg
    shoe_size    = StringField()  # UK size
    blazer_size  = StringField()
    trouser_size = StringField()

    # ── Education ──────────────────────────────────────────────
    is_student  = BooleanField(default=False)
    school      = StringField()
    degree      = StringField()

    # ── Languages (up to 4, stored as list of dicts) ──────────
    # Each item: { "language": "English", "proficiency": "Fluent" }
    languages = ListField(default=list)

    # ── Work experience ────────────────────────────────────────
    hostess_experience  = BooleanField(default=False)
    group_responsible   = BooleanField(default=False)
    agency              = StringField()
    experience_areas    = ListField(StringField())  # actor/actress, modeling, etc.
    work_type           = StringField()   # full-time | part-time | both
    holiday_work        = BooleanField(default=False)

    # ── Professional (admin-managed) ───────────────────────────
    package             = StringField(default="LUXURY")
    price_of_staff      = FloatField(default=0)
    experience_in_years = IntField(default=0)

    # ── Media ──────────────────────────────────────────────────
    profile_picture = URLField()
    gallery_images  = ListField(URLField())

    # ── Meta ───────────────────────────────────────────────────
    # PENDING = self-registered, waiting admin review
    # (status lives on User but this tracks registration flow)
    registration_complete = BooleanField(default=False)

    joined_date = DateTimeField(default=datetime.utcnow)

    # ── Tracking / Duty Status ─────────────────────────────────
    is_online   = BooleanField(default=False)
    last_online = DateTimeField(default=datetime.utcnow)



# ─────────────────────────────────────────────────────────────
#  MakeupArtistProfile
# ─────────────────────────────────────────────────────────────

class MakeupArtistProfile(Document):
    meta = {"collection": "makeup_artist_profiles"}

    user = ReferenceField(User, required=True, unique=True)

    full_name         = StringField()
    gender            = StringField()
    makeup_speciality = StringField()

    city    = StringField()
    state   = StringField()
    country = StringField()

    # ── Images (S3 URLs, same pattern as StaffProfile) ────────────
    profile_picture = URLField()
    gallery_images  = ListField(URLField())

    experience_in_years = IntField()

    joined_date = DateTimeField(default=datetime.utcnow)



