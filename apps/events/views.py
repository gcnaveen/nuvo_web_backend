# apps/events/views.py

import json
from datetime import datetime

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from mongoengine.errors import DoesNotExist
from mongoengine.queryset.visitor import Q

from apps.accounts.decorators import require_auth, require_role
from apps.events.models import Event, Venue, GSTDetails, PaymentInfo, EVENT_STATUS_CHOICES


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
    try:
        return str(getattr(obj, field)) if obj else None
    except Exception:
        return None


def serialize_event(event, full=False) -> dict:
    """
    full=False  →  compact list payload  (list_events)
    full=True   →  complete detail payload (get_event / details page)
    """

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

    client_data = None
    if event.client:
        try:
            cp = event.client
            client_data = {
                "profile_id": str(cp.id),
                "full_name":  cp.full_name or "",
                "city":       cp.city or "",
            }
            if full:
                try:
                    u = cp.user
                    client_data["email"]        = u.email if u else ""
                    client_data["phone_number"] = u.phone_number if u else ""
                    client_data["user_id"]      = str(u.id) if u else None
                except Exception:
                    pass
        except Exception:
            client_data = {"profile_id": _safe_str(event.client)}

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
        base["theme_id"]   = _safe_str(event.theme)
        base["uniform_id"] = _safe_str(event.uniform)
        base["package_id"] = _safe_str(event.package)
        return base

    # ── Full detail enrichment ────────────────────────────────

    theme_data = None
    if event.theme:
        try:
            t = event.theme
            theme_data = {
                "id":          str(t.id),
                "theme_name":  t.theme_name,
                "cover_image": t.cover_image,
                "status":      t.status,
            }
        except Exception:
            theme_data = {"id": _safe_str(event.theme)}

    uniform_data = None
    if event.uniform:
        try:
            u = event.uniform
            uniform_data = {
                "id":            str(u.id),
                "category_name": u.category_name,
                "unique_key":    u.unique_key,
                "images":        list(u.images or []),
            }
        except Exception:
            uniform_data = {"id": _safe_str(event.uniform)}

    package_data = None
    if event.package:
        try:
            p = event.package
            package_data = {
                "id":               str(p.id),
                "name":             p.name,
                "monthly_price":    p.monthlyPrice,
                "yearly_price":     p.yearlyPrice,
                "priority_support": p.prioritySupport,
                "is_free":          p.isFree,
            }
        except Exception:
            package_data = {"id": _safe_str(event.package)}

    crew = []
    for member in (event.crew_members or []):
        try:
            crew.append({
                "profile_id":      str(member.id),
                "full_name":       member.full_name       or "",
                "stage_name":      member.stage_name      or "",
                "gender":          member.gender          or "",
                "city":            member.city            or "",
                "profile_picture": member.profile_picture or "",
                "package":         member.package         or "",
            })
        except Exception:
            crew.append({"profile_id": _safe_str(member)})

    gst = None
    if event.gst_details:
        gst = {
            "company_name": event.gst_details.company_name,
            "address":      event.gst_details.address,
            "gst_number":   event.gst_details.gst_number,
        }

    base.update({
        "theme":        theme_data,
        "uniform":      uniform_data,
        "package":      package_data,
        "crew_members": crew,
        "gst_details":  gst,
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


# ─────────────────────────────────────────────────────────────
#  1. Create Event
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def create_event(request):
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        body = json.loads(request.body)

        from apps.users.models import StaffProfile, ClientProfile
        from apps.master.models import EventTheme, UniformCategory, SubscriptionPlanSettings

        event_name = body.get("event_name", "").strip()
        city       = body.get("city", "").strip()
        state      = body.get("state", "").strip()
        client_id  = body.get("client_id", "").strip()

        if not all([event_name, city, state, client_id]):
            return api_response(False, "event_name, city, state, client_id are required", status=400)

        start_dt, err = parse_datetime(body.get("event_start_datetime"), "event_start_datetime")
        if err:
            return api_response(False, err, status=400)

        end_dt, err = parse_datetime(body.get("event_end_datetime"), "event_end_datetime")
        if err:
            return api_response(False, err, status=400)

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

        theme   = EventTheme.objects(id=body["theme_id"]).first()                    if body.get("theme_id")   else None
        uniform = UniformCategory.objects(id=body["uniform_id"]).first()              if body.get("uniform_id") else None
        package = SubscriptionPlanSettings.objects(id=body["package_id"]).first()     if body.get("package_id") else None

        crew_members = []
        for pid in body.get("crew_member_ids", []):
            p = StaffProfile.objects(id=pid).first()
            if p:
                crew_members.append(p)

        gst = None
        gst_data = body.get("gst_details")
        if gst_data:
            gst = GSTDetails(
                company_name = gst_data.get("company_name"),
                address      = gst_data.get("address"),
                gst_number   = gst_data.get("gst_number"),
            )

        pay_data = body.get("payment", {})
        payment  = PaymentInfo(
            total_amount = float(pay_data.get("total_amount", 0)),
            gst_amount   = float(pay_data.get("gst_amount", 0)),
            tax_amount   = float(pay_data.get("tax_amount", 0)),
            paid_amount  = 0,
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
            working_hours        = float(body["working_hours"]) if body.get("working_hours") else None,
            crew_count           = int(body.get("crew_count", 0)),
            crew_members         = crew_members,
            theme                = theme,
            uniform              = uniform,
            package              = package,
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
#  2. List Events  (search + filters + pagination)
# ─────────────────────────────────────────────────────────────
#
#  GET /events/
#
#  Query params:
#    search       – event_name OR client full_name (case-insensitive)
#    city         – exact city, case-insensitive
#    status       – created | planning_started | staff_allocated | completed | cancelled
#    client_id    – ClientProfile id
#    start_date   – event_start_datetime >= YYYY-MM-DD
#    end_date     – event_start_datetime <= YYYY-MM-DD
#    page         – default 1
#    page_size    – default 15, max 100

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

        # Search: event_name OR client full_name
        if search:
            from apps.users.models import ClientProfile
            matched_clients    = ClientProfile.objects(full_name__icontains=search)
            matched_client_ids = [c.id for c in matched_clients]

            if matched_client_ids:
                qs = qs.filter(
                    Q(event_name__icontains=search) | Q(client__in=matched_client_ids)
                )
            else:
                qs = qs.filter(event_name__icontains=search)

        if city:
            qs = qs.filter(city__iexact=city)

        if status:
            if status not in EVENT_STATUS_CHOICES:
                return api_response(
                    False,
                    f"Invalid status. Valid options: {', '.join(EVENT_STATUS_CHOICES)}",
                    status=400
                )
            qs = qs.filter(status=status)

        if client_id:
            from apps.users.models import ClientProfile
            client = ClientProfile.objects(id=client_id).first()
            if client:
                qs = qs.filter(client=client)

        if start_date:
            try:
                qs = qs.filter(event_start_datetime__gte=datetime.strptime(start_date, "%Y-%m-%d"))
            except ValueError:
                return api_response(False, "start_date must be YYYY-MM-DD", status=400)

        if end_date:
            try:
                qs = qs.filter(event_start_datetime__lte=datetime.strptime(end_date, "%Y-%m-%d"))
            except ValueError:
                return api_response(False, "end_date must be YYYY-MM-DD", status=400)

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
#  3. Get Single Event  (full details)
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
#  4. Update Event  (partial — all fields optional)
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
        from apps.master.models import EventTheme, UniformCategory, SubscriptionPlanSettings

        if body.get("event_name"):    event.event_name  = body["event_name"].strip()
        if body.get("event_type"):    event.event_type  = body["event_type"]
        if body.get("city"):          event.city        = body["city"]
        if body.get("state"):         event.state       = body["state"]
        if body.get("no_of_days")    is not None: event.no_of_days    = int(body["no_of_days"])
        if body.get("working_hours") is not None: event.working_hours = float(body["working_hours"])
        if body.get("crew_count")    is not None: event.crew_count    = int(body["crew_count"])

        if body.get("event_start_datetime"):
            dt, err = parse_datetime(body["event_start_datetime"], "event_start_datetime")
            if err:
                return api_response(False, err, status=400)
            event.event_start_datetime = dt

        if body.get("event_end_datetime"):
            dt, err = parse_datetime(body["event_end_datetime"], "event_end_datetime")
            if err:
                return api_response(False, err, status=400)
            event.event_end_datetime = dt

        if body.get("venue"):
            vd = body["venue"]
            if not event.venue:
                event.venue = Venue()
            if vd.get("venue_name"):          event.venue.venue_name        = vd["venue_name"]
            if vd.get("formatted_address"):   event.venue.formatted_address = vd["formatted_address"]
            if vd.get("latitude")  is not None: event.venue.latitude        = vd["latitude"]
            if vd.get("longitude") is not None: event.venue.longitude       = vd["longitude"]
            if vd.get("place_id"):            event.venue.place_id          = vd["place_id"]
            if vd.get("google_maps_url"):     event.venue.google_maps_url   = vd["google_maps_url"]

        if body.get("theme_id"):   event.theme   = EventTheme.objects(id=body["theme_id"]).first()
        if body.get("uniform_id"): event.uniform = UniformCategory.objects(id=body["uniform_id"]).first()
        if body.get("package_id"): event.package = SubscriptionPlanSettings.objects(id=body["package_id"]).first()

        if "crew_member_ids" in body:
            crew = []
            for pid in body["crew_member_ids"]:
                p = StaffProfile.objects(id=pid).first()
                if p:
                    crew.append(p)
            event.crew_members = crew
            event.crew_count   = len(crew)

        if body.get("gst_details"):
            gd = body["gst_details"]
            if not event.gst_details:
                event.gst_details = GSTDetails()
            if gd.get("company_name"): event.gst_details.company_name = gd["company_name"]
            if gd.get("address"):      event.gst_details.address      = gd["address"]
            if gd.get("gst_number"):   event.gst_details.gst_number   = gd["gst_number"]

        if body.get("payment"):
            pd = body["payment"]
            if not event.payment:
                event.payment = PaymentInfo()
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
            return api_response(
                False,
                f"Invalid status. Valid options: {', '.join(EVENT_STATUS_CHOICES)}",
                status=400
            )

        if new_status == "cancelled" and not body.get("cancelled_reason"):
            return api_response(False, "cancelled_reason is required when cancelling", status=400)

        event.status = new_status
        if new_status == "cancelled":
            event.cancelled_reason = body.get("cancelled_reason")

        event.save()
        return api_response(True, f"Event status updated to '{new_status}'", {
            "id":     str(event.id),
            "status": event.status,
        })

    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  6a. Available Staff for an Event  (conflict-aware)
# ─────────────────────────────────────────────────────────────
#
#  GET /events/<event_id>/available-staff/
#
#  Returns StaffProfile records that have NO time-slot conflict
#  with any other non-cancelled event during this event's window.
#  Staff already assigned to THIS event are still included so the
#  admin can see the full current + available pool at once.
#
#  Overlap rule (standard interval intersection):
#    other.start < this.end  AND  other.end > this.start
#
#  Optional query params (all case-insensitive):
#    search   – full_name or stage_name
#    city     – exact city
#    package  – platinum | diamond | gold | silver | bronze
#    page     – default 1
#    page_size – default 20, max 100

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
        return api_response(
            False,
            "This event has no start/end datetime set. Set them before allocating staff.",
            status=400
        )

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

        # ── Step 1: Find all conflicting events ───────────────
        # Any event (except this one and cancelled ones) whose
        # time window overlaps with [event.start, event.end].
        conflicting_events = Event.objects.filter(
            id__ne        = str(event.id),
            status__nin   = ["cancelled"],
            event_start_datetime__lt = event.event_end_datetime,
            event_end_datetime__gt   = event.event_start_datetime,
        )

        # ── Step 2: Collect all busy staff profile IDs ────────
        busy_profile_ids = set()
        for conflict in conflicting_events:
            for member in (conflict.crew_members or []):
                try:
                    busy_profile_ids.add(str(member.id))
                except Exception:
                    pass

        # ── Step 3: Current crew on THIS event ────────────────
        # We track them separately so the response can mark them
        # as already_assigned=True for the UI checkbox state.
        current_crew_ids = set()
        for member in (event.crew_members or []):
            try:
                current_crew_ids.add(str(member.id))
            except Exception:
                pass

        # ── Step 4: Build StaffProfile queryset ───────────────
        # Exclude only staff busy on OTHER events.
        # Staff on THIS event stay visible (they ARE available for it).
        truly_busy = busy_profile_ids - current_crew_ids
        qs = StaffProfile.objects()

        if truly_busy:
            qs = qs.filter(id__nin=list(truly_busy))

        # Apply optional filters
        if search:
            qs = qs.filter(
                Q(full_name__icontains=search) | Q(stage_name__icontains=search)
            )
        if city:
            qs = qs.filter(city__iexact=city)
        if package:
            qs = qs.filter(package__iexact=package)

        # ── Step 5: Paginate ──────────────────────────────────
        total  = qs.count()
        offset = (page - 1) * page_size
        staff  = qs.order_by("full_name").skip(offset).limit(page_size)

        results = []
        for s in staff:
            sid = str(s.id)
            results.append({
                "profile_id":      sid,
                "full_name":       s.full_name       or "",
                "stage_name":      s.stage_name      or "",
                "gender":          s.gender          or "",
                "city":            s.city            or "",
                "package":         s.package         or "",
                "profile_picture": s.profile_picture or "",
                "experience_in_years": s.experience_in_years,
                "price_of_staff":  s.price_of_staff,
                # Tells the UI whether this staff is already on this event
                "already_assigned": sid in current_crew_ids,
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
#  6b. Assign / Replace Crew Members  (with conflict guard)
# ─────────────────────────────────────────────────────────────
#
#  PUT /events/<event_id>/assign-crew/
#
#  Body: { "crew_member_ids": ["profile_id_1", ...] }
#
#  Before saving, validates that none of the submitted staff
#  are already assigned to a conflicting event in the same
#  time slot. Returns 409 with details if conflicts found.

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

        # ── Resolve profiles ──────────────────────────────────
        crew, not_found = [], []
        for pid in crew_member_ids:
            p = StaffProfile.objects(id=pid).first()
            if p:
                crew.append(p)
            else:
                not_found.append(pid)

        if not_found:
            return api_response(False, f"Staff profiles not found: {not_found}", status=404)

        # ── Conflict check ────────────────────────────────────
        # Only run if the event has a defined time window.
        if event.event_start_datetime and event.event_end_datetime:
            conflicting_events = Event.objects.filter(
                id__ne        = str(event.id),
                status__nin   = ["cancelled"],
                event_start_datetime__lt = event.event_end_datetime,
                event_end_datetime__gt   = event.event_start_datetime,
            )

            # Map: profile_id → conflicting event name + id
            conflicts = {}
            for conflict in conflicting_events:
                for member in (conflict.crew_members or []):
                    try:
                        mid = str(member.id)
                        if mid in [str(p.id) for p in crew]:
                            conflicts[mid] = {
                                "conflict_event_id":   str(conflict.id),
                                "conflict_event_name": conflict.event_name,
                                "conflict_start":      str(conflict.event_start_datetime),
                                "conflict_end":        str(conflict.event_end_datetime),
                            }
                    except Exception:
                        pass

            if conflicts:
                # Build a human-readable list for the error message
                conflict_names = []
                for mid, info in conflicts.items():
                    profile = StaffProfile.objects(id=mid).first()
                    name    = profile.full_name if profile else mid
                    conflict_names.append(
                        f"{name} (busy on '{info['conflict_event_name']}')"
                    )

                return api_response(
                    False,
                    f"Scheduling conflict: {', '.join(conflict_names)} "
                    f"are already assigned to another event during this time slot.",
                    data={"conflicts": conflicts},
                    status=409,
                )

        # ── No conflicts — save ───────────────────────────────
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
#  8. Track Event — Live Crew Locations
# ─────────────────────────────────────────────────────────────
#
#  GET /events/<event_id>/track/
#
#  Django proxies calls to the C++ location server per crew member.
#  One failure per member does NOT abort the whole response.
#
#  Response shape matches TrackEvent.jsx expectations:
#    id, name, stage_name, role, image_url, lat, lng, status, timestamp

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

        for member in (event.crew_members or []):
            try:
                employee_id = str(member.id)
                location    = get_staff_location(employee_id)

                # Derive on-screen badge status from location result
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
                    "location_error": location.get("error"),   # None on success
                })

            except Exception as member_err:
                crew_locations.append({
                    "id":             _safe_str(member),
                    "name":           "",
                    "role":           "Staff",
                    "image_url":      "",
                    "lat":            None,
                    "lng":            None,
                    "timestamp":      None,
                    "status":         "offline",
                    "location_error": str(member_err),
                })

        event_summary = {
            "id":                   str(event.id),
            "event_name":           event.event_name,
            "event_type":           event.event_type,
            "status":               event.status,
            "event_start_datetime": str(event.event_start_datetime) if event.event_start_datetime else None,
            "event_end_datetime":   str(event.event_end_datetime)   if event.event_end_datetime   else None,
            "venue_name":           event.venue.venue_name if event.venue else "",
            "city":                 event.city,
            "state":                event.state,
            "client_name":          event.client.full_name if event.client else "",
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
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        event = Event.objects.get(id=event_id)
    except DoesNotExist:
        return api_response(False, "Event not found", status=404)

    try:
        from apps.common.phonepay_utils import initiate_payment as phonepe_initiate

        body   = json.loads(request.body)
        amount = float(body.get("amount", 0))

        if amount <= 0:
            return api_response(False, "Amount must be greater than 0", status=400)

        if event.payment and event.payment.payment_status == "paid_fully":
            return api_response(False, "Event is already fully paid", status=400)

        user_mobile = "9999999999"
        try:
            if event.client and event.client.user:
                user_mobile = event.client.user.phone_number or user_mobile
        except Exception:
            pass

        result = phonepe_initiate(
            amount_rupees=amount,
            event_id=str(event.id),
            user_mobile=user_mobile,
        )

        if result.get("success"):
            if event.payment:
                event.payment.phonepay_order_id = result["merchant_txn_id"]
                event.payment.last_updated      = datetime.utcnow()
            event.save()

        return api_response(result.get("success", False), result.get("message", ""), {
            "payment_url":     result.get("payment_url"),
            "merchant_txn_id": result.get("merchant_txn_id"),
        })

    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  10. Payment Callback  (redirect after PhonePe)
# ─────────────────────────────────────────────────────────────

@csrf_exempt
def payment_callback(request):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)

    try:
        from apps.common.phonepay_utils import verify_payment

        txn_id = request.GET.get("txn", "").strip()
        if not txn_id:
            return api_response(False, "txn query param is required", status=400)

        result = verify_payment(txn_id)
        if not result.get("success"):
            return api_response(False, result.get("message", "Payment verification failed"), status=400)

        event = Event.objects(payment__phonepay_order_id=txn_id).first()
        if not event:
            return api_response(False, "No event found for this transaction", status=404)

        if result["status"] == "PAYMENT_SUCCESS":
            paid     = result.get("amount_rupees", 0)
            total    = event.payment.total_amount if event.payment else 0
            new_paid = (event.payment.paid_amount or 0) + paid

            event.payment.paid_amount             = new_paid
            event.payment.phonepay_transaction_id = txn_id
            event.payment.last_updated            = datetime.utcnow()
            event.payment.payment_status          = "paid_fully" if new_paid >= total else "advance"
            event.save()

        return api_response(True, "Payment status updated", {
            "phonepay_status": result["status"],
            "event_id":        str(event.id),
            "payment_status":  event.payment.payment_status,
            "paid_amount":     event.payment.paid_amount,
        })

    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  11. Payment Webhook  (server-to-server from PhonePe)
# ─────────────────────────────────────────────────────────────

@csrf_exempt
def payment_webhook(request):
    if request.method != "POST":
        return api_response(False, "Invalid request method", status=405)

    try:
        from apps.common.phonepay_utils import parse_webhook_payload

        result = parse_webhook_payload(request.body)

        if not result.get("valid"):
            return api_response(False, result.get("message", "Invalid webhook"), status=400)

        txn_id = result.get("merchant_txn_id")
        event  = Event.objects(payment__phonepay_order_id=txn_id).first()

        if not event:
            return api_response(True, "Acknowledged (event not found)")

        if result["status"] == "PAYMENT_SUCCESS":
            paid     = result.get("amount_rupees", 0)
            total    = event.payment.total_amount if event.payment else 0
            new_paid = (event.payment.paid_amount or 0) + paid

            event.payment.paid_amount             = new_paid
            event.payment.phonepay_transaction_id = txn_id
            event.payment.last_updated            = datetime.utcnow()
            event.payment.payment_status          = "paid_fully" if new_paid >= total else "advance"
            event.save()

        return api_response(True, "Webhook processed")

    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  12. My Events  (Client — mobile app)
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
    

    