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

from apps.master.models import UniformCategory, SubscriptionPlanSettings
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

    # Payment method and advance type
    payment_method  = StringField(choices=["CASH", "ONLINE"], default="ONLINE")
    advance_type    = StringField(choices=["FULL", "HALF"], default="FULL")

    # Balance due tracking (populated when advance_type=HALF)
    balance_due_date        = DateTimeField(default=None)
    balance_reminder_sent   = BooleanField(default=False)

    # Invoice — populated after successful payment
    invoice_url     = StringField(default="")
    invoice_number  = StringField(default="")

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
    meta = {"collection": "events", "strict": False}

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
    crew_members        = ListField(ReferenceField(StaffProfile))

    # Package (Luxury / Premium / Both)
    package_type        = StringField(choices=["LUXURY", "PREMIUM", "BOTH"], default=None)
    luxury_crew_count   = IntField(default=0)
    premium_crew_count  = IntField(default=0)

    # Legacy fields kept so existing DB events still deserialise
    crew_count    = IntField(default=0)

    # ── Master Data References ────────────────────────────────
    uniform = ReferenceField(UniformCategory)   # legacy — single-uniform events, kept for old data
    package = ReferenceField(SubscriptionPlanSettings)  # legacy — kept for old events

    # Uniform selection (Luxury / Premium crew, chosen independently)
    luxury_uniform_type = StringField(choices=["custom", "predefined"], default=None)
    luxury_uniform      = ReferenceField(UniformCategory)  # None when luxury_uniform_type == "custom"
    premium_uniform     = ReferenceField(UniformCategory)

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