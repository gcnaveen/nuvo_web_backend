# apps/master/models.py
import uuid
from datetime import datetime
from mongoengine import (
    Document,
    StringField,
    BooleanField,
    DateTimeField,
    ListField,
    URLField,
    FloatField,
    IntField,
    DictField
)


# 1️⃣ Event Themes
class EventTheme(Document):
    meta = {"collection": "event_themes"}

    id = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))
    theme_name = StringField(required=True)
    status = StringField(default="ACTIVE")
    description = StringField()
    cover_image = URLField()
    gallery_images = ListField(URLField())

    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)


# 2️⃣ Uniform Category
class UniformCategory(Document):
    meta = {"collection": "uniform_categories"}
 
    id            = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))
    category_name = StringField(required=True)
    unique_key    = StringField(required=True, unique=True)
    description   = StringField()
    images        = ListField(URLField())
    is_active     = BooleanField(default=True)
 
    # ── Master data fields ──────────────────────────────────────
    gender        = StringField(default="unisex")   # male | female | unisex
    price         = FloatField(default=0.0)          # price per unit / per use
 
    # ── Inventory fields ────────────────────────────────────────
    has_sizes     = BooleanField(default=True)
    # stock: { "S": {"total": 10, "in_use": 3}, ... }
    # DictField stores arbitrary key→value; we validate shape in views.
    stock         = DictField(default=dict)
 
    created_at    = DateTimeField(default=datetime.utcnow)
    updated_at    = DateTimeField(default=datetime.utcnow)
 
    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)

# 3️⃣ Subscription Plan Settings
class SubscriptionPlanSettings(Document):
    meta = {"collection": "subscription_plan_settings"}

    id = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))
    name = StringField(required=True, unique=True)

    monthlyPrice = FloatField(default=0)
    yearlyPrice = FloatField(default=0)
    prioritySupport = BooleanField(default=False)
    isFree = BooleanField(default=False)

    last_updated = DateTimeField(default=datetime.utcnow)

    def save(self, *args, **kwargs):
        self.last_updated = datetime.utcnow()
        return super().save(*args, **kwargs)


# 4️⃣ Crew Members
class CrewMember(Document):
    meta = {"collection": "crew_members"}

    id         = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))
    name       = StringField(required=True)
    image      = URLField(required=True)
    is_active  = BooleanField(default=True)

    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)


# 5️⃣ Payment Terms (Single Document)
class PaymentTerms(Document):
    meta = {"collection": "payment_terms"}

    advancePercentage     = FloatField(required=True)

    # Staff pricing per tier (per person per day, in INR)
    # Keys: BRONZE | SILVER | GOLD | PLATINUM  (DIAMOND excluded — negotiated directly)
    staff_pricing         = DictField(default=lambda: {
        "BRONZE": 15000, "SILVER": 30000, "GOLD": 45000, "PLATINUM": 65000
    })

    default_hours_per_day = FloatField(default=5.0)    # included hours in one day
    overtime_rate_per_hour = FloatField(default=3000.0) # charged per extra hour beyond default

    lastUpdatedAt         = DateTimeField(default=datetime.utcnow)

    def save(self, *args, **kwargs):
        self.lastUpdatedAt = datetime.utcnow()
        return super().save(*args, **kwargs)


# 6️⃣ Coupon
class Coupon(Document):
    meta = {"collection": "coupons"}

    id             = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))
    code           = StringField(required=True, unique=True)
    description    = StringField(default="")
    discount_type  = StringField(default="FLAT")   # FLAT | PERCENTAGE
    discount_value = FloatField(required=True)
    usage_limit    = IntField(default=1)           # max times it can be used
    used_count     = IntField(default=0)           # how many times used so far
    is_active      = BooleanField(default=True)
    expiry_date    = DateTimeField(default=None)

    created_at     = DateTimeField(default=datetime.utcnow)
    updated_at     = DateTimeField(default=datetime.utcnow)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)