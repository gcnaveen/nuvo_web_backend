# apps/events/models.py

import uuid
from datetime import datetime
from mongoengine import (
    Document,
    EmbeddedDocument,
    StringField,
    FloatField,
    IntField,
    BooleanField,
    DateTimeField,
    ListField,
    ReferenceField,
    EmbeddedDocumentField,
)

from apps.master.models import EventTheme, UniformCategory, SubscriptionPlanSettings
from apps.users.models import User, StaffProfile, ClientProfile


# ─────────────────────────────────────────────────────────────
#  Embedded: Venue
# ─────────────────────────────────────────────────────────────

class Venue(EmbeddedDocument):
    """
    Stores the full Google Maps–compatible location payload.
    Frontend receives this as a JSON object and can build the
    Maps link directly from google_maps_url or place_id.
    """
    venue_name       = StringField(required=True)
    formatted_address = StringField()
    latitude         = FloatField()
    longitude        = FloatField()
    place_id         = StringField()          # Google Places placeId
    google_maps_url  = StringField()          # Pre-built Maps URL


# ─────────────────────────────────────────────────────────────
#  Embedded: GST Details  (optional — corporate events only)
# ─────────────────────────────────────────────────────────────

class GSTDetails(EmbeddedDocument):
    company_name = StringField()
    address      = StringField()
    gst_number   = StringField()


# ─────────────────────────────────────────────────────────────
#  Embedded: Payment
# ─────────────────────────────────────────────────────────────

class PaymentInfo(EmbeddedDocument):
    """
    1-to-1 with Event so embedded keeps queries simple.
    PhonePe transaction IDs are stored here once the gateway
    utility is wired up.
    """
    # Amounts
    total_amount    = FloatField(default=0)
    gst_amount      = FloatField(default=0)
    tax_amount      = FloatField(default=0)
    paid_amount     = FloatField(default=0)

    # Status
    payment_status  = StringField(
        choices=["unpaid", "advance", "paid_fully", "refund_pending"],
        default="unpaid"
    )

    # PhonePe — populated after gateway callback
    phonepay_transaction_id = StringField(default="")
    phonepay_order_id       = StringField(default="")

    last_updated = DateTimeField(default=datetime.utcnow)


# ─────────────────────────────────────────────────────────────
#  Event Status Choices
# ─────────────────────────────────────────────────────────────

EVENT_STATUS_CHOICES = [
    "created",           # Booking created, no planning yet
    "planning_started",  # Internal planning underway
    "staff_allocated",   # Staff/crew confirmed and assigned
    "completed",         # Event successfully executed
    "cancelled",         # Cancelled by client or admin
]


# ─────────────────────────────────────────────────────────────
#  Event  (main document)
# ─────────────────────────────────────────────────────────────

class Event(Document):
    meta = {"collection": "events"}

    id = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))

    # ── Basic Info ───────────────────────────────────────────
    event_name  = StringField(required=True)
    event_type  = StringField()                  # Wedding, Corporate, Birthday …

    # ── Location ─────────────────────────────────────────────
    venue = EmbeddedDocumentField(Venue, required=True)
    city  = StringField(required=True)
    state = StringField(required=True)

    # ── Schedule ─────────────────────────────────────────────
    event_start_datetime = DateTimeField(required=True)   # ISO datetime → Google Calendar
    event_end_datetime   = DateTimeField(required=True)   # ISO datetime → Google Calendar
    no_of_days           = IntField(default=1)
    working_hours        = FloatField()                   # e.g. 8.5

    # ── Crew ─────────────────────────────────────────────────
    crew_count    = IntField(default=0)
    crew_members  = ListField(ReferenceField(StaffProfile))  # Selected staff/models

    # ── Master Data References ────────────────────────────────
    theme   = ReferenceField(EventTheme)               # Selected from master data
    uniform = ReferenceField(UniformCategory)          # Selected from master data
    package = ReferenceField(SubscriptionPlanSettings) # Diamond / Platinum / Gold …

    # ── Client ───────────────────────────────────────────────
    client = ReferenceField(ClientProfile, required=True)

    # ── GST (optional — corporate only) ──────────────────────
    gst_details = EmbeddedDocumentField(GSTDetails)    # None if not corporate

    # ── Payment ──────────────────────────────────────────────
    payment = EmbeddedDocumentField(PaymentInfo, default=PaymentInfo)

    # ── Status & Audit ───────────────────────────────────────
    status       = StringField(choices=EVENT_STATUS_CHOICES, default="created")
    cancelled_reason = StringField()                   # Populated only on cancel

    created_at   = DateTimeField(default=datetime.utcnow)
    updated_at   = DateTimeField(default=datetime.utcnow)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)