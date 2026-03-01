import uuid
from datetime import datetime
from mongoengine import (
    Document,
    StringField,
    BooleanField,
    DateTimeField,
    ListField,
    URLField,
    FloatField
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

    id = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))
    category_name = StringField(required=True)
    unique_key = StringField(required=True, unique=True)
    description = StringField()
    images = ListField(URLField())
    is_active = BooleanField(default=True)

    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

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


# 4️⃣ Payment Terms (Single Document)
class PaymentTerms(Document):
    meta = {"collection": "payment_terms"}

    advancePercentage = FloatField(required=True)
    lastUpdatedAt = DateTimeField(default=datetime.utcnow)

    def save(self, *args, **kwargs):
        self.lastUpdatedAt = datetime.utcnow()
        return super().save(*args, **kwargs)