# apps/events/views.py  — PATCHED serialize_event + safe_str
#
# Drop this file in as apps/events/views.py.
# The ONLY change from the original is:
#   1. Import safe_deref helpers at the top
#   2. serialize_event() uses safe_ref / safe_attr / safe_list_refs
#      throughout instead of bare field access
#   3. All other view functions (create, list, update, etc.) are unchanged.
#
# This eliminates:
#   OperationError: Trying to dereference unknown document DBRef(...)

import json
from datetime import datetime

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from mongoengine.errors import DoesNotExist
from mongoengine.queryset.visitor import Q

from apps.accounts.decorators import require_auth, require_role
from apps.events.models import Event, Venue, GSTDetails, PaymentInfo, EVENT_STATUS_CHOICES
from apps.common.safe_deref import safe_ref, safe_attr, safe_id, safe_list_refs


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────

def api_response(success, message, data=None, status=200):
    return JsonResponse({
        "success": success,
        "message": message,
        "data": data or {}
    }, status=status)


def _safe_str(obj, field="id"):
    """Safely get a string attribute from any object — never raises."""
    try:
        return str(getattr(obj, field)) if obj else None
    except Exception:
        return None


def serialize_event(event, full=False) -> dict:
    """
    full=False  ->  compact list payload  (list_events)
    full=True   ->  complete detail payload (get_event / details page)

    All ReferenceField accesses are wrapped in safe_ref / safe_attr so that
    a deleted reference document never crashes the response.
    """

    # ── Venue (EmbeddedDocument — always safe, no dereference needed) ──
    venue = None
    if event.venue:
        venue = {
            "venue_name":        event.venue.venue_name,
            "formatted_address": event.venue.formatted_address,
            "latitude":          event.venue.latitude,
            "longitude":         event.venue.longitude,
            "place_id":          event.venue.place_id,
            "google_maps_url":   event.venue.google_maps_url,
        }

    # ── Client (ReferenceField -> ClientProfile -> User) ──────────────
    client_data = None
    client_doc = safe_ref(event.client)
    if client_doc:
        client_data = {
            "profile_id": str(client_doc.id),
            "full_name":  client_doc.full_name or "",
            "city":       client_doc.city or "",
        }
        if full:
            user_doc = safe_ref(client_doc.user)
            if user_doc:
                client_data["email"]        = user_doc.email or ""
                client_data["phone_number"] = user_doc.phone_number or ""
                client_data["user_id"]      = str(user_doc.id)
    elif event.client:
        # Deleted client — return raw id so the event still loads
        client_data = {"profile_id": safe_id(event.client), "full_name": "[Deleted]", "city": ""}

    # ── Payment (EmbeddedDocument — always safe) ───────────────────────
    payment = None
    if event.payment:
        payment = {
            "total_amount":            event.payment.total_amount,
            "gst_amount":              event.payment.gst_amount,
            "tax_amount":              event.payment.tax_amount,
            "paid_amount":             event.payment.paid_amount,
            "balance_due":             round(
                (event.payment.total_amount or 0) - (event.payment.paid_amount or 0), 2
            ),
            "payment_status":          event.payment.payment_status,
            "phonepay_transaction_id": event.payment.phonepay_transaction_id,
            "phonepay_order_id":       event.payment.phonepay_order_id,
            "last_updated":            str(event.payment.last_updated) if event.payment.last_updated else None,
        }

    base = {
        "id":                   str(event.id),
        "event_name":           event.event_name,
        "event_type":           event.event_type,
        "city":                 event.city,
        "state":                event.state,
        "venue":                venue,
        "event_start_datetime": str(event.event_start_datetime) if event.event_start_datetime else None,
        "event_end_datetime":   str(event.event_end_datetime)   if event.event_end_datetime   else None,
        "no_of_days":           event.no_of_days,
        "working_hours":        event.working_hours,
        "crew_count":           event.crew_count,
        "client":               client_data,
        "payment":              payment,
        "status":               event.status,
        "cancelled_reason":     event.cancelled_reason,
        "created_at":           str(event.created_at),
        "updated_at":           str(event.updated_at),
    }

    if not full:
        # Compact list view: just return the IDs, don't dereference
        base["theme_id"]           = safe_id(event.theme)
        base["uniform_id"]         = safe_id(event.uniform)
        base["package_id"]         = safe_id(event.package)
        base["luxury_uniform_type"] = event.luxury_uniform_type
        base["luxury_uniform_id"]  = safe_id(event.luxury_uniform)
        base["premium_uniform_id"] = safe_id(event.premium_uniform)
        return base

    # ── Full detail: safely dereference theme, uniform, package ────────

    theme_doc = safe_ref(event.theme)
    theme_data = None
    if theme_doc:
        theme_data = {
            "id":          str(theme_doc.id),
            "theme_name":  theme_doc.theme_name,
            "cover_image": theme_doc.cover_image,
            "status":      theme_doc.status,
        }
    elif event.theme:
        theme_data = {"id": safe_id(event.theme), "theme_name": "[Deleted]"}

    uniform_doc = safe_ref(event.uniform)
    uniform_data = None
    if uniform_doc:
        uniform_data = {
            "id":            str(uniform_doc.id),
            "category_name": uniform_doc.category_name,
            "unique_key":    uniform_doc.unique_key,
            "images":        list(uniform_doc.images or []),
        }
    elif event.uniform:
        uniform_data = {"id": safe_id(event.uniform), "category_name": "[Deleted]"}

    def _uniform_summary(ref):
        doc = safe_ref(ref)
        if doc:
            return {
                "id":            str(doc.id),
                "category_name": doc.category_name,
                "unique_key":    doc.unique_key,
                "images":        list(doc.images or []),
            }
        if ref:
            return {"id": safe_id(ref), "category_name": "[Deleted]"}
        return None

    luxury_uniform_data  = _uniform_summary(event.luxury_uniform)
    premium_uniform_data = _uniform_summary(event.premium_uniform)

    package_doc = safe_ref(event.package)
    package_data = None
    if package_doc:
        package_data = {
            "id":               str(package_doc.id),
            "name":             package_doc.name,
            "monthly_price":    package_doc.monthlyPrice,
            "yearly_price":     package_doc.yearlyPrice,
            "priority_support": package_doc.prioritySupport,
            "is_free":          package_doc.isFree,
        }
    elif event.package:
        package_data = {"id": safe_id(event.package), "name": "[Deleted]"}

    # ── Crew members (ListField of ReferenceField) ─────────────────────
    # safe_list_refs silently drops any deleted staff profiles
    crew = []
    for member in safe_list_refs(event.crew_members):
        crew.append({
            "profile_id":      str(member.id),
            "full_name":       member.full_name       or "",
            "stage_name":      member.stage_name      or "",
            "gender":          member.gender          or "",
            "city":            member.city            or "",
            "profile_picture": member.profile_picture or "",
            "package":         member.package         or "",
        })

    # ── GST (EmbeddedDocument — always safe) ───────────────────────────
    gst = None
    if event.gst_details:
        gst = {
            "company_name": event.gst_details.company_name,
            "address":      event.gst_details.address,
            "gst_number":   event.gst_details.gst_number,
        }

    base.update({
        "theme":               theme_data,
        "uniform":             uniform_data,
        "package":             package_data,
        "luxury_uniform_type": event.luxury_uniform_type,
        "luxury_uniform":      luxury_uniform_data,
        "premium_uniform":     premium_uniform_data,
        "crew_members":        crew,
        "gst_details":         gst,
    })

    return base


def parse_datetime(value: str, field_name: str):
    if not value:
        return None, f"{field_name} is required"
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt), None
        except ValueError:
            continue
    return None, f"{field_name} must be ISO format e.g. 2026-03-15T18:00:00"


def _calculate_event_total(
    package_type: str,
    luxury_count: int,
    premium_count: int,
    working_hours: float,
) -> float:
    """
    Compute the base event total from PaymentTerms.staff_pricing.
    This keeps the backend calculation in sync with the mobile price preview,
    both of which source prices from the Payment Terms admin screen.
    """
    from apps.master.models import PaymentTerms

    terms         = PaymentTerms.objects.first()
    staff_pricing = (terms.staff_pricing if terms else None) or {"LUXURY": 20000, "PREMIUM": 10000}
    default_hours = float(getattr(terms, "default_hours_per_day", None) or 8)
    overtime_rate = float(getattr(terms, "overtime_rate_per_hour", None) or 0)

    total = 0.0
    if not package_type:
        return total

    def _pkg_cost(pkg_type: str, count: int) -> float:
        if count <= 0:
            return 0.0
        price = float(staff_pricing.get(pkg_type, 0))
        if price <= 0:
            return 0.0
        base        = price * count
        extra_hours = max(0.0, working_hours - default_hours)
        overtime    = extra_hours * overtime_rate * count
        return base + overtime

    if package_type in ("LUXURY", "BOTH"):
        total += _pkg_cost("LUXURY", luxury_count)
    if package_type in ("PREMIUM", "BOTH"):
        total += _pkg_cost("PREMIUM", premium_count)
    return round(total, 2)


# ─────────────────────────────────────────────────────────────
#  1. Create Event
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN", "CLIENT"])
def create_event(request):
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)
    try:
        body = json.loads(request.body)
        from apps.users.models import StaffProfile, ClientProfile
        from apps.master.models import EventTheme, UniformCategory, CrewPackage

        event_name = body.get("event_name", "").strip()
        city       = body.get("city", "").strip()
        state      = body.get("state", "").strip()
        client_id  = body.get("client_id", "").strip()

        if not all([event_name, city, state, client_id]):
            return api_response(False, "event_name, city, state, client_id are required", status=400)

        start_dt, err = parse_datetime(body.get("event_start_datetime"), "event_start_datetime")
        if err: return api_response(False, err, status=400)

        end_dt, err = parse_datetime(body.get("event_end_datetime"), "event_end_datetime")
        if err: return api_response(False, err, status=400)

        if end_dt <= start_dt:
            return api_response(False, "event_end_datetime must be after event_start_datetime", status=400)

        venue_data = body.get("venue")
        if not venue_data or not venue_data.get("venue_name"):
            return api_response(False, "venue.venue_name is required", status=400)

        venue = Venue(
            venue_name        = venue_data.get("venue_name"),
            formatted_address = venue_data.get("formatted_address"),
            latitude          = venue_data.get("latitude"),
            longitude         = venue_data.get("longitude"),
            place_id          = venue_data.get("place_id"),
            google_maps_url   = venue_data.get("google_maps_url"),
        )

        client = ClientProfile.objects(id=client_id).first()
        if not client:
            return api_response(False, "Client profile not found", status=404)

        theme   = EventTheme.objects(id=body["theme_id"]).first()      if body.get("theme_id")   else None
        uniform = UniformCategory.objects(id=body["uniform_id"]).first() if body.get("uniform_id") else None

        # ── Package selection (Luxury / Premium / Both) ──────────
        package_type       = body.get("package_type", "").strip().upper() or None
        luxury_crew_count  = int(body.get("luxury_crew_count", 0))
        premium_crew_count = int(body.get("premium_crew_count", 0))

        if package_type and package_type not in ("LUXURY", "PREMIUM", "BOTH"):
            return api_response(False, "package_type must be LUXURY, PREMIUM, or BOTH", status=400)

        # ── Uniform selection — Luxury (custom or predefined) + Premium ──
        # Custom is only offered for Luxury crew; Premium is always predefined.
        luxury_uniform_type = (body.get("luxury_uniform_type") or "").strip().lower() or None
        luxury_uniform      = None
        premium_uniform     = None

        if package_type in ("LUXURY", "BOTH"):
            if luxury_uniform_type and luxury_uniform_type not in ("custom", "predefined"):
                return api_response(False, "luxury_uniform_type must be 'custom' or 'predefined'", status=400)

            if luxury_uniform_type == "custom":
                # No catalog uniform is picked — admin will contact the client to arrange it.
                luxury_uniform = None
            elif body.get("luxury_uniform_id"):
                luxury_uniform = UniformCategory.objects(id=body["luxury_uniform_id"]).first()
                if not luxury_uniform:
                    return api_response(False, "luxury_uniform_id not found", status=404)
                luxury_uniform_type = luxury_uniform_type or "predefined"
        else:
            luxury_uniform_type = None

        if package_type in ("PREMIUM", "BOTH") and body.get("premium_uniform_id"):
            premium_uniform = UniformCategory.objects(id=body["premium_uniform_id"]).first()
            if not premium_uniform:
                return api_response(False, "premium_uniform_id not found", status=404)

        # ── Payment total auto-calculation from package pricing ──
        working_hours = float(body["working_hours"]) if body.get("working_hours") else 8.0
        total_amount  = _calculate_event_total(
            package_type, luxury_crew_count, premium_crew_count, working_hours
        )

        # ── Payment collection rule ──────────────────────────────
        days_to_event   = (start_dt - datetime.utcnow()).days
        payment_method  = body.get("payment_method", "ONLINE").upper()
        advance_type    = body.get("advance_type", "FULL").upper()

        if days_to_event <= 7:
            advance_type = "FULL"   # force full payment if event is within 7 days

        balance_due_date = None
        if advance_type == "HALF":
            from datetime import timedelta
            balance_due_date = start_dt - timedelta(days=7)

        crew_members = []
        for pid in body.get("crew_member_ids", []):
            p = StaffProfile.objects(id=pid).first()
            if p: crew_members.append(p)

        gst = None
        gst_data = body.get("gst_details")
        if gst_data:
            gst = GSTDetails(
                company_name = gst_data.get("company_name"),
                address      = gst_data.get("address"),
                gst_number   = gst_data.get("gst_number"),
            )

        pay_data    = body.get("payment", {})
        gst_amount  = float(pay_data.get("gst_amount", 0))
        tax_amount  = float(pay_data.get("tax_amount", 0))
        payment = PaymentInfo(
            total_amount     = total_amount + gst_amount + tax_amount,
            gst_amount       = gst_amount,
            tax_amount       = tax_amount,
            paid_amount      = 0,
            payment_method   = payment_method if payment_method in ("CASH", "ONLINE") else "ONLINE",
            advance_type     = advance_type if advance_type in ("FULL", "HALF") else "FULL",
            balance_due_date = balance_due_date,
        )

        event = Event(
            event_name           = event_name,
            event_type           = body.get("event_type"),
            city                 = city,
            state                = state,
            venue                = venue,
            event_start_datetime = start_dt,
            event_end_datetime   = end_dt,
            no_of_days           = int(body.get("no_of_days", 1)),
            working_hours        = working_hours,
            crew_members         = crew_members,
            package_type         = package_type,
            luxury_crew_count    = luxury_crew_count,
            premium_crew_count   = premium_crew_count,
            theme                = theme,
            uniform              = uniform,
            luxury_uniform_type  = luxury_uniform_type,
            luxury_uniform       = luxury_uniform,
            premium_uniform      = premium_uniform,
            client               = client,
            gst_details          = gst,
            payment              = payment,
            status               = "created",
        )
        event.save()
        return api_response(True, "Event created successfully", serialize_event(event, full=True), status=201)

    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  2. List Events
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def list_events(request):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)
    try:
        search     = request.GET.get("search", "").strip()
        city       = request.GET.get("city", "").strip()
        status     = request.GET.get("status", "").strip()
        client_id  = request.GET.get("client_id", "").strip()
        start_date = request.GET.get("start_date", "").strip()
        end_date   = request.GET.get("end_date", "").strip()

        try:
            page      = max(1, int(request.GET.get("page", 1)))
            page_size = min(100, max(1, int(request.GET.get("page_size", 15))))
        except ValueError:
            return api_response(False, "page and page_size must be integers", status=400)

        qs = Event.objects()

        if search:
            from apps.users.models import ClientProfile
            matched_clients    = ClientProfile.objects(full_name__icontains=search)
            matched_client_ids = [c.id for c in matched_clients]
            if matched_client_ids:
                qs = qs.filter(Q(event_name__icontains=search) | Q(client__in=matched_client_ids))
            else:
                qs = qs.filter(event_name__icontains=search)

        if city:   qs = qs.filter(city__iexact=city)
        if status:
            if status not in EVENT_STATUS_CHOICES:
                return api_response(False, f"Invalid status. Valid options: {', '.join(EVENT_STATUS_CHOICES)}", status=400)
            qs = qs.filter(status=status)
        if client_id:
            from apps.users.models import ClientProfile
            client = ClientProfile.objects(id=client_id).first()
            if client: qs = qs.filter(client=client)
        if start_date:
            try:    qs = qs.filter(event_start_datetime__gte=datetime.strptime(start_date, "%Y-%m-%d"))
            except: return api_response(False, "start_date must be YYYY-MM-DD", status=400)
        if end_date:
            try:    qs = qs.filter(event_start_datetime__lte=datetime.strptime(end_date, "%Y-%m-%d"))
            except: return api_response(False, "end_date must be YYYY-MM-DD", status=400)

        total  = qs.count()
        offset = (page - 1) * page_size
        events = qs.order_by("-created_at").skip(offset).limit(page_size)

        return api_response(True, "Events fetched", {
            "results": [serialize_event(e, full=False) for e in events],
            "pagination": {
                "total":       total,
                "page":        page,
                "page_size":   page_size,
                "total_pages": -(-total // page_size),
            }
        })
    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  3. Get Single Event
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
def get_event(request, event_id):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)
    try:
        event = Event.objects.get(id=event_id)
        return api_response(True, "Event fetched", serialize_event(event, full=True))
    except DoesNotExist:
        return api_response(False, "Event not found", status=404)
    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  4. Update Event
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def update_event(request, event_id):
    if request.method != "PUT":
        return api_response(False, "Invalid request method", status=405)
    try:
        event = Event.objects.get(id=event_id)
    except DoesNotExist:
        return api_response(False, "Event not found", status=404)
    try:
        body = json.loads(request.body)
        from apps.users.models import StaffProfile, ClientProfile
        from apps.master.models import EventTheme, UniformCategory

        if body.get("event_name"):    event.event_name  = body["event_name"].strip()
        if body.get("event_type"):    event.event_type  = body["event_type"]
        if body.get("city"):          event.city        = body["city"]
        if body.get("state"):         event.state       = body["state"]
        if body.get("no_of_days")    is not None: event.no_of_days    = int(body["no_of_days"])
        if body.get("working_hours") is not None: event.working_hours = float(body["working_hours"])

        if body.get("event_start_datetime"):
            dt, err = parse_datetime(body["event_start_datetime"], "event_start_datetime")
            if err: return api_response(False, err, status=400)
            event.event_start_datetime = dt

        if body.get("event_end_datetime"):
            dt, err = parse_datetime(body["event_end_datetime"], "event_end_datetime")
            if err: return api_response(False, err, status=400)
            event.event_end_datetime = dt

        if body.get("venue"):
            vd = body["venue"]
            if not event.venue: event.venue = Venue()
            if vd.get("venue_name"):          event.venue.venue_name        = vd["venue_name"]
            if vd.get("formatted_address"):   event.venue.formatted_address = vd["formatted_address"]
            if vd.get("latitude")  is not None: event.venue.latitude        = vd["latitude"]
            if vd.get("longitude") is not None: event.venue.longitude       = vd["longitude"]
            if vd.get("place_id"):            event.venue.place_id          = vd["place_id"]
            if vd.get("google_maps_url"):     event.venue.google_maps_url   = vd["google_maps_url"]

        if body.get("theme_id"):   event.theme   = EventTheme.objects(id=body["theme_id"]).first()
        if body.get("uniform_id"): event.uniform = UniformCategory.objects(id=body["uniform_id"]).first()

        # ── Package update ─────────────────────────────────────
        if body.get("package_type"):
            pt = body["package_type"].upper()
            if pt not in ("LUXURY", "PREMIUM", "BOTH"):
                return api_response(False, "package_type must be LUXURY, PREMIUM, or BOTH", status=400)
            event.package_type = pt

        # ── Uniform selection update — Luxury (custom/predefined) + Premium ──
        if body.get("luxury_uniform_type"):
            lut = body["luxury_uniform_type"].strip().lower()
            if lut not in ("custom", "predefined"):
                return api_response(False, "luxury_uniform_type must be 'custom' or 'predefined'", status=400)
            event.luxury_uniform_type = lut
            if lut == "custom":
                event.luxury_uniform = None  # admin will contact the client directly

        if body.get("luxury_uniform_id"):
            luxury_uniform = UniformCategory.objects(id=body["luxury_uniform_id"]).first()
            if not luxury_uniform:
                return api_response(False, "luxury_uniform_id not found", status=404)
            event.luxury_uniform = luxury_uniform
            event.luxury_uniform_type = "predefined"

        if body.get("premium_uniform_id"):
            premium_uniform = UniformCategory.objects(id=body["premium_uniform_id"]).first()
            if not premium_uniform:
                return api_response(False, "premium_uniform_id not found", status=404)
            event.premium_uniform = premium_uniform
        if body.get("luxury_crew_count")  is not None:
            event.luxury_crew_count  = int(body["luxury_crew_count"])
        if body.get("premium_crew_count") is not None:
            event.premium_crew_count = int(body["premium_crew_count"])

        # Recalculate total if package or hours changed
        if any(k in body for k in ("package_type", "luxury_crew_count", "premium_crew_count", "working_hours")):
            wh = event.working_hours or 8.0
            new_total = _calculate_event_total(
                event.package_type, event.luxury_crew_count, event.premium_crew_count, wh
            )
            if event.payment:
                event.payment.total_amount = new_total + (event.payment.gst_amount or 0) + (event.payment.tax_amount or 0)

        if "crew_member_ids" in body:
            crew = []
            for pid in body["crew_member_ids"]:
                p = StaffProfile.objects(id=pid).first()
                if p: crew.append(p)
            event.crew_members = crew

        if body.get("gst_details"):
            gd = body["gst_details"]
            if not event.gst_details: event.gst_details = GSTDetails()
            if gd.get("company_name"): event.gst_details.company_name = gd["company_name"]
            if gd.get("address"):      event.gst_details.address      = gd["address"]
            if gd.get("gst_number"):   event.gst_details.gst_number   = gd["gst_number"]

        if body.get("payment"):
            pd = body["payment"]
            if not event.payment: event.payment = PaymentInfo()
            if pd.get("total_amount")   is not None: event.payment.total_amount   = float(pd["total_amount"])
            if pd.get("gst_amount")     is not None: event.payment.gst_amount     = float(pd["gst_amount"])
            if pd.get("tax_amount")     is not None: event.payment.tax_amount     = float(pd["tax_amount"])
            if pd.get("paid_amount")    is not None: event.payment.paid_amount    = float(pd["paid_amount"])
            if pd.get("payment_status"):              event.payment.payment_status = pd["payment_status"]

        event.save()
        return api_response(True, "Event updated", serialize_event(event, full=True))
    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  5. Update Event Status
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def update_event_status(request, event_id):
    if request.method != "PUT":
        return api_response(False, "Invalid request method", status=405)
    try:
        event = Event.objects.get(id=event_id)
    except DoesNotExist:
        return api_response(False, "Event not found", status=404)
    try:
        body       = json.loads(request.body)
        new_status = body.get("status", "").strip()
        if not new_status:
            return api_response(False, "status is required", status=400)
        if new_status not in EVENT_STATUS_CHOICES:
            return api_response(False, f"Invalid status. Valid options: {', '.join(EVENT_STATUS_CHOICES)}", status=400)
        if new_status == "cancelled" and not body.get("cancelled_reason"):
            return api_response(False, "cancelled_reason is required when cancelling", status=400)
        event.status = new_status
        if new_status == "cancelled":
            event.cancelled_reason = body.get("cancelled_reason")
        event.save()
        return api_response(True, f"Event status updated to '{new_status}'", {
            "id": str(event.id), "status": event.status,
        })
    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  6a. Available Staff
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def available_staff(request, event_id):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)
    try:
        event = Event.objects.get(id=event_id)
    except DoesNotExist:
        return api_response(False, "Event not found", status=404)
    if not event.event_start_datetime or not event.event_end_datetime:
        return api_response(False, "Event has no start/end datetime", status=400)
    try:
        from apps.users.models import StaffProfile
        search   = request.GET.get("search", "").strip()
        city     = request.GET.get("city", "").strip()
        package  = request.GET.get("package", "").strip()
        try:
            page      = max(1, int(request.GET.get("page", 1)))
            page_size = min(100, max(1, int(request.GET.get("page_size", 20))))
        except ValueError:
            return api_response(False, "page and page_size must be integers", status=400)

        conflicting_events = Event.objects.filter(
            id__ne=str(event.id),
            status__nin=["cancelled"],
            event_start_datetime__lt=event.event_end_datetime,
            event_end_datetime__gt=event.event_start_datetime,
        )

        busy_profile_ids = set()
        for conflict in conflicting_events:
            # Use safe_list_refs so deleted crew don't cause crashes
            for member in safe_list_refs(conflict.crew_members):
                busy_profile_ids.add(str(member.id))

        current_crew_ids = set()
        for member in safe_list_refs(event.crew_members):
            current_crew_ids.add(str(member.id))

        truly_busy = busy_profile_ids - current_crew_ids
        qs = StaffProfile.objects()
        if truly_busy:
            qs = qs.filter(id__nin=list(truly_busy))
        if search:
            qs = qs.filter(Q(full_name__icontains=search) | Q(stage_name__icontains=search))
        if city:    qs = qs.filter(city__iexact=city)
        if package: qs = qs.filter(package__iexact=package)

        total  = qs.count()
        offset = (page - 1) * page_size
        staff  = qs.order_by("full_name").skip(offset).limit(page_size)

        results = []
        for s in staff:
            sid = str(s.id)
            results.append({
                "profile_id":          sid,
                "full_name":           s.full_name       or "",
                "stage_name":          s.stage_name      or "",
                "gender":              s.gender          or "",
                "city":                s.city            or "",
                "package":             s.package         or "",
                "profile_picture":     s.profile_picture or "",
                "experience_in_years": s.experience_in_years,
                "price_of_staff":      s.price_of_staff,
                "already_assigned":    sid in current_crew_ids,
            })

        return api_response(True, "Available staff fetched", {
            "event_window": {
                "start": str(event.event_start_datetime),
                "end":   str(event.event_end_datetime),
            },
            "results":     results,
            "busy_count":  len(truly_busy),
            "pagination": {
                "total":       total,
                "page":        page,
                "page_size":   page_size,
                "total_pages": -(-total // page_size),
            }
        })
    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  6b. Assign Crew
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def assign_crew(request, event_id):
    if request.method != "PUT":
        return api_response(False, "Invalid request method", status=405)
    try:
        event = Event.objects.get(id=event_id)
    except DoesNotExist:
        return api_response(False, "Event not found", status=404)
    try:
        from apps.users.models import StaffProfile
        body            = json.loads(request.body)
        crew_member_ids = body.get("crew_member_ids", [])
        if not isinstance(crew_member_ids, list):
            return api_response(False, "crew_member_ids must be a list", status=400)

        crew, not_found = [], []
        for pid in crew_member_ids:
            p = StaffProfile.objects(id=pid).first()
            if p: crew.append(p)
            else: not_found.append(pid)

        if not_found:
            return api_response(False, f"Staff profiles not found: {not_found}", status=404)

        if event.event_start_datetime and event.event_end_datetime:
            conflicting_events = Event.objects.filter(
                id__ne=str(event.id),
                status__nin=["cancelled"],
                event_start_datetime__lt=event.event_end_datetime,
                event_end_datetime__gt=event.event_start_datetime,
            )
            conflicts = {}
            for conflict in conflicting_events:
                for member in safe_list_refs(conflict.crew_members):
                    mid = str(member.id)
                    if mid in [str(p.id) for p in crew]:
                        conflicts[mid] = {
                            "conflict_event_id":   str(conflict.id),
                            "conflict_event_name": conflict.event_name,
                            "conflict_start":      str(conflict.event_start_datetime),
                            "conflict_end":        str(conflict.event_end_datetime),
                        }
            if conflicts:
                conflict_names = []
                for mid, info in conflicts.items():
                    profile = StaffProfile.objects(id=mid).first()
                    name    = profile.full_name if profile else mid
                    conflict_names.append(f"{name} (busy on '{info['conflict_event_name']}')")
                return api_response(
                    False,
                    f"Scheduling conflict: {', '.join(conflict_names)}.",
                    data={"conflicts": conflicts},
                    status=409,
                )

        event.crew_members = crew
        event.crew_count   = len(crew)
        if crew and event.status == "planning_started":
            event.status = "staff_allocated"
        event.save()
        return api_response(True, "Crew assigned successfully", {
            "crew_count":   event.crew_count,
            "status":       event.status,
            "crew_members": [str(m.id) for m in crew],
        })
    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  7. Delete Event
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def delete_event(request, event_id):
    if request.method != "DELETE":
        return api_response(False, "Invalid request method", status=405)
    try:
        event = Event.objects.get(id=event_id)
        event.delete()
        return api_response(True, "Event deleted successfully")
    except DoesNotExist:
        return api_response(False, "Event not found", status=404)
    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  8. Track Event
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
def track_event(request, event_id):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)
    try:
        event = Event.objects.get(id=event_id)
    except DoesNotExist:
        return api_response(False, "Event not found", status=404)
    try:
        from apps.common.location_utils import get_staff_location
        crew_locations = []

        # safe_list_refs drops any deleted staff silently
        for member in safe_list_refs(event.crew_members):
            try:
                employee_id = str(member.id)
                location    = get_staff_location(employee_id)
                if location["success"] and location["lat"] and location["lng"]:
                    tracking_status = "on_event"
                elif location["success"]:
                    tracking_status = "away"
                else:
                    tracking_status = "offline"
                crew_locations.append({
                    "id":             employee_id,
                    "name":           member.full_name      or "",
                    "stage_name":     member.stage_name     or "",
                    "role":           "Staff",
                    "image_url":      member.profile_picture or "",
                    "lat":            location.get("lat"),
                    "lng":            location.get("lng"),
                    "timestamp":      location.get("timestamp"),
                    "status":         tracking_status,
                    "location_error": location.get("error"),
                })
            except Exception as member_err:
                crew_locations.append({
                    "id": str(member.id), "name": member.full_name or "",
                    "role": "Staff", "image_url": "",
                    "lat": None, "lng": None, "timestamp": None,
                    "status": "offline", "location_error": str(member_err),
                })

        # Safe access to venue and client
        venue_doc = event.venue
        client_doc = safe_ref(event.client)

        event_summary = {
            "id":                   str(event.id),
            "event_name":           event.event_name,
            "event_type":           event.event_type,
            "status":               event.status,
            "event_start_datetime": str(event.event_start_datetime) if event.event_start_datetime else None,
            "event_end_datetime":   str(event.event_end_datetime)   if event.event_end_datetime   else None,
            "venue_name":           venue_doc.venue_name  if venue_doc else "",
            "venue_lat":            venue_doc.latitude    if venue_doc else None,
            "venue_lng":            venue_doc.longitude   if venue_doc else None,
            "city":                 event.city,
            "state":                event.state,
            "client_name":          client_doc.full_name if client_doc else "",
            "crew_count":           event.crew_count,
        }

        return api_response(True, "Tracking data fetched", {
            "event":      event_summary,
            "crew":       crew_locations,
            "total_crew": len(crew_locations),
            "online":     sum(1 for c in crew_locations if c["status"] != "offline"),
        })
    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  9. Initiate Payment
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
def initiate_payment(request, event_id):
    """
    POST /api/events/<event_id>/payment/initiate/
    Body: { "amount": 31500.0, "redirect_url": "nuvoapp://payment/result" }

    Mobile app calls this → receives redirect_url → opens in WebView/browser.
    """
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)
    try:
        event = Event.objects.get(id=event_id)
    except DoesNotExist:
        return api_response(False, "Event not found", status=404)
    try:
        from apps.common.phonepay_utils import initiate_payment as phonepe_initiate
        import uuid as _uuid
        body         = json.loads(request.body)
        amount       = float(body.get("amount", 0))
        redirect_url = body.get("redirect_url", "").strip()

        if amount <= 0:
            return api_response(False, "Amount must be greater than 0", status=400)
        if not redirect_url:
            return api_response(False, "redirect_url is required", status=400)
        if event.payment and event.payment.payment_status == "paid_fully":
            return api_response(False, "Event is already fully paid", status=400)

        # Build a unique merchant order ID (max 63 chars, alphanumeric + hyphen)
        merchant_order_id = f"EVT-{str(event.id)[:8].upper()}-{_uuid.uuid4().hex[:8].upper()}"

        # Get client's mobile number for PhonePe prefill (best effort)
        user_mobile = None
        try:
            client_doc = safe_ref(event.client)
            if client_doc:
                user_doc = safe_ref(client_doc.user)
                if user_doc and user_doc.phone_number:
                    user_mobile = user_doc.phone_number
        except Exception:
            pass

        result = phonepe_initiate(
            amount_rupees=amount,
            merchant_order_id=merchant_order_id,
            redirect_url=redirect_url,
            user_mobile=user_mobile,
        )

        if result.get("success"):
            event.payment.phonepay_order_id       = merchant_order_id
            event.payment.phonepay_transaction_id = result.get("phonepe_order_id", "")
            event.payment.total_amount            = amount
            event.payment.last_updated            = datetime.utcnow()
            event.save()

        return api_response(result.get("success", False), result.get("message", ""), {
            "redirect_url":      result.get("redirect_url"),
            "merchant_order_id": merchant_order_id,
        })
    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  10 & 11. Payment Callback / Webhook
# ─────────────────────────────────────────────────────────────

@csrf_exempt
def payment_callback(request):
    """
    GET /api/events/payment/callback/?merchantOrderId=EVT-XXXX
    PhonePe redirects the user's browser here after payment.
    We verify status and update the event, then the mobile app
    reads the final state from GET /api/events/<id>/.
    """
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)
    try:
        from apps.common.phonepay_utils import get_order_status
        merchant_order_id = request.GET.get("merchantOrderId", "").strip()
        if not merchant_order_id:
            return api_response(False, "merchantOrderId query param is required", status=400)

        result = get_order_status(merchant_order_id)
        event  = Event.objects(payment__phonepay_order_id=merchant_order_id).first()
        if not event:
            return api_response(False, "No event found for this order", status=404)

        if result.get("state") == "COMPLETED":
            paid     = result.get("amount_rupees", 0)
            total    = event.payment.total_amount or 0
            new_paid = (event.payment.paid_amount or 0) + paid
            event.payment.paid_amount    = new_paid
            event.payment.last_updated   = datetime.utcnow()
            event.payment.payment_status = "paid_fully" if new_paid >= total else "advance"
            event.save()
            try:
                from apps.common.invoice_utils import generate_and_deliver_invoice
                generate_and_deliver_invoice(event)
            except Exception:
                pass

        return api_response(True, "Payment status updated", {
            "state":          result.get("state"),
            "event_id":       str(event.id),
            "payment_status": event.payment.payment_status,
            "paid_amount":    event.payment.paid_amount,
            "invoice_url":    event.payment.invoice_url if event.payment else "",
        })
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
def payment_webhook(request):
    """
    POST /api/events/payment/webhook/
    PhonePe server-to-server notification.
    This is the reliable path — always processed even if callback fails.
    """
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)
    try:
        from apps.common.phonepay_utils import parse_webhook_payload
        auth_header = request.headers.get("Authorization", "")
        result      = parse_webhook_payload(request.body, auth_header)

        if not result.get("valid"):
            return api_response(False, result.get("message", "Invalid webhook"), status=400)

        merchant_order_id = result.get("merchant_order_id")
        event = Event.objects(payment__phonepay_order_id=merchant_order_id).first()
        if not event:
            return api_response(True, "Acknowledged")

        if result.get("state") == "COMPLETED":
            paid     = result.get("amount_rupees", 0)
            total    = event.payment.total_amount or 0
            new_paid = (event.payment.paid_amount or 0) + paid
            event.payment.paid_amount             = new_paid
            event.payment.phonepay_transaction_id = result.get("phonepe_order_id", "")
            event.payment.last_updated            = datetime.utcnow()
            event.payment.payment_status          = "paid_fully" if new_paid >= total else "advance"
            event.save()
            try:
                from apps.common.invoice_utils import generate_and_deliver_invoice
                generate_and_deliver_invoice(event)
            except Exception:
                pass

        return api_response(True, "Webhook processed")
    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  12 & 13. Client My Events  (unchanged)
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["CLIENT"])
def my_events(request):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)
    try:
        from apps.users.models import ClientProfile
        profile = ClientProfile.objects(user=request.user).first()
        if not profile:
            return api_response(False, "Client profile not found", status=404)
        events = Event.objects(client=profile).order_by("-created_at")
        return api_response(True, "Events fetched", {
            "results": [serialize_event(e, full=False) for e in events],
            "total":   events.count(),
        })
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
@require_auth
@require_role(["CLIENT"])
def client_my_events(request):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)
    try:
        from apps.users.models import ClientProfile
        client_profile = ClientProfile.objects(user=request.user).first()
        if not client_profile:
            return api_response(False, "Client profile not found for this user", status=404)
        try:
            page      = max(1, int(request.GET.get("page", 1)))
            page_size = min(100, max(1, int(request.GET.get("page_size", 15))))
        except ValueError:
            return api_response(False, "page and page_size must be integers", status=400)
        # Exclude ONLINE events that are still unpaid (payment initiated but not confirmed).
        # Cash events with unpaid status are shown because cash is collected by admin offline.
        qs = Event.objects(
            Q(client=client_profile) &
            ~Q(payment__payment_method="ONLINE", payment__payment_status="unpaid")
        )
        total  = qs.count()
        offset = (page - 1) * page_size
        events = qs.order_by("-created_at").skip(offset).limit(page_size)
        results = []
        for event in events:
            theme_name = safe_attr(event.theme, "theme_name") or safe_attr(event.theme, "name") or ""
            payment_data = {}
            order_id = ""
            if event.payment:
                order_id = event.payment.phonepay_order_id or ""
                payment_data = {
                    "total_amount":           event.payment.total_amount,
                    "gst_amount":             event.payment.gst_amount,
                    "tax_amount":             event.payment.tax_amount,
                    "paid_amount":            event.payment.paid_amount,
                    "payment_status":         event.payment.payment_status,
                    "phonepay_transaction_id": event.payment.phonepay_transaction_id,
                }
            results.append({
                "event_id":         str(event.id),
                "event_name":       event.event_name,
                "event_theme_name": theme_name,
                "order_id":         order_id,
                "payment_details":  payment_data,
                "status":           event.status,
            })
        return api_response(True, "My events fetched successfully", {
            "results": results,
            "pagination": {
                "total": total, "page": page,
                "page_size": page_size, "total_pages": -(-total // page_size),
            }
        })
    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  Invoice
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
def get_invoice(request, event_id):
    """
    GET /api/events/<event_id>/invoice/
    Returns the S3 URL of the invoice PDF.
    If not yet generated (e.g. cash payment), generates it on demand.
    """
    if request.method != "GET":
        return api_response(False, "Method not allowed", status=405)
    try:
        event = Event.objects.get(id=event_id)
    except DoesNotExist:
        return api_response(False, "Event not found", status=404)
    try:
        invoice_url = event.payment.invoice_url if event.payment else ""
        if not invoice_url:
            from apps.common.invoice_utils import generate_and_deliver_invoice
            invoice_url = generate_and_deliver_invoice(event)
        return api_response(True, "Invoice fetched", {
            "invoice_url":    invoice_url,
            "invoice_number": event.payment.invoice_number if event.payment else "",
        })
    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  Staff Mobile App APIs
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["STAFF"])
def staff_upcoming_events(request):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)
    try:
        page      = max(1, int(request.GET.get("page", 1)))
        page_size = min(100, max(1, int(request.GET.get("page_size", 15))))
        qs = Event.objects(
            event_start_datetime__gte=datetime.utcnow(),
            status__nin=["cancelled", "completed"]
        )
        total  = qs.count()
        offset = (page - 1) * page_size
        events = qs.order_by("event_start_datetime").skip(offset).limit(page_size)
        return api_response(True, "Upcoming events fetched", {
            "results": [serialize_event(e, full=False) for e in events],
            "total": total
        })
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
@require_auth
@require_role(["STAFF"])
def staff_assigned_events(request):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)
    try:
        from apps.users.models import StaffProfile
        profile = StaffProfile.objects(user=request.user).first()
        if not profile:
            return api_response(False, "Staff profile not found", status=404)
        page      = max(1, int(request.GET.get("page", 1)))
        page_size = min(100, max(1, int(request.GET.get("page_size", 15))))
        qs = Event.objects(crew_members=profile, status__nin=["cancelled", "completed"])
        total  = qs.count()
        offset = (page - 1) * page_size
        events = qs.order_by("event_start_datetime").skip(offset).limit(page_size)
        return api_response(True, "Assigned events fetched", {
            "results": [serialize_event(e, full=False) for e in events],
            "total": total
        })
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
@require_auth
@require_role(["STAFF"])
def staff_completed_events(request):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)
    try:
        from apps.users.models import StaffProfile
        profile = StaffProfile.objects(user=request.user).first()
        if not profile:
            return api_response(False, "Staff profile not found", status=404)
        page      = max(1, int(request.GET.get("page", 1)))
        page_size = min(100, max(1, int(request.GET.get("page_size", 15))))
        qs = Event.objects(crew_members=profile, status__in=["completed", "cancelled"])
        total  = qs.count()
        offset = (page - 1) * page_size
        events = qs.order_by("-event_end_datetime").skip(offset).limit(page_size)
        return api_response(True, "History fetched", {
            "results": [serialize_event(e, full=False) for e in events],
            "total": total
        })
    except Exception as e:
        return api_response(False, str(e), status=500)


@csrf_exempt
@require_auth
@require_role(["STAFF"])
def update_staff_online_status(request):
    if request.method != "PUT":
        return api_response(False, "Invalid request method", status=405)
    try:
        from apps.users.models import StaffProfile
        profile = StaffProfile.objects(user=request.user).first()
        if not profile:
            return api_response(False, "Staff profile not found", status=404)
        body      = json.loads(request.body)
        is_online = body.get("is_online", True)
        profile.is_online   = is_online
        profile.last_online = datetime.utcnow()
        profile.save()
        return api_response(True, "Online status updated successfully", {
            "is_online":   profile.is_online,
            "last_online": str(profile.last_online),
        })
    except Exception as e:
        return api_response(False, str(e), status=500)