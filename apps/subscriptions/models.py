# apps/subscriptions/models.py
"""
Subscription model — tracks every payment attempt for a plan renewal.
One row per checkout attempt; completed rows are the source of truth
for when the plan expires.

Collection: subscriptions
"""
import uuid
from datetime import datetime
from mongoengine import (
    Document, StringField, FloatField, DateTimeField, BooleanField
)


class Subscription(Document):
    meta = {"collection": "subscriptions", "ordering": ["-created_at"]}

    id = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))

    # ── Who ────────────────────────────────────────────────────
    user_id = StringField(required=True)          # User.id
    client_profile_id = StringField(required=True) # ClientProfile.id

    # ── What ───────────────────────────────────────────────────
    plan = StringField(required=True)             # GOLD | PLATINUM | DIAMOND
    billing_cycle = StringField(required=True)    # monthly | yearly

    # ── Money ──────────────────────────────────────────────────
    amount = FloatField(required=True)            # INR

    # ── PhonePe ────────────────────────────────────────────────
    merchant_order_id = StringField(unique=True)  # EVT-XXXX we generated
    phonepe_order_id = StringField(default="")    # PhonePe's orderId

    # ── Lifecycle ──────────────────────────────────────────────
    # payment_status: PENDING | COMPLETED | FAILED
    payment_status = StringField(default="PENDING")

    # Subscription validity (populated on successful payment)
    start_date = DateTimeField(default=None)
    end_date   = DateTimeField(default=None)

    created_at   = DateTimeField(default=datetime.utcnow)
    last_updated = DateTimeField(default=datetime.utcnow)

    def save(self, *args, **kwargs):
        self.last_updated = datetime.utcnow()
        return super().save(*args, **kwargs)
