# apps/events/dashboard_views.py
#
# Admin dashboard statistics API — single endpoint that returns
# all the numbers needed for the live admin dashboard.
#
# ADD to apps/events/urls.py:
#   from .dashboard_views import admin_dashboard_stats, on_duty_staff
#   path("dashboard/stats/",   admin_dashboard_stats, name="dashboard_stats"),
#   path("dashboard/on-duty/", on_duty_staff,         name="on_duty_staff"),

from datetime import datetime, timedelta 

from django.http import JsonResponse 
from django.views.decorators.csrf import csrf_exempt 

from apps.accounts.decorators import require_auth, require_role 
from apps.events.models import Event, EVENT_STATUS_CHOICES 


def api_response(success, message, data=None, status=200): 
    return JsonResponse( 
        {"success": success, "message": message, "data": data or {}}, 
        status=status, 
    ) 


# ─────────────────────────────────────────────────────────────
#  Admin Dashboard Stats 
#  GET /api/events/dashboard/stats/ 
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def admin_dashboard_stats(request):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)

    try:
        from apps.users.models import StaffProfile, ClientProfile

        now = datetime.utcnow()

        # ── Core counts ───────────────────────────────────────
        total_events   = Event.objects().count()
        upcoming_count = Event.objects(
            event_start_datetime__gte=now,
            status__nin=["cancelled", "completed"],
        ).count()

        # ── Revenue ───────────────────────────────────────────
        total_revenue   = 0.0
        pending_revenue = 0.0
        for ev in Event.objects():
            if not ev.payment:
                continue
            paid  = ev.payment.paid_amount  or 0.0
            total = ev.payment.total_amount or 0.0
            total_revenue += paid
            if ev.status != "cancelled":
                pending_revenue += max(0.0, total - paid)

        # ── Events by status ──────────────────────────────────
        status_counts = {s: Event.objects(status=s).count() for s in EVENT_STATUS_CHOICES}

        # ── Monthly booking trend (last 6 months) ─────────────
        monthly_trend = []
        for i in range(5, -1, -1):
            month_start = (now.replace(day=1) - timedelta(days=i * 30)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            month_end = (
                month_start.replace(year=month_start.year + 1, month=1)
                if month_start.month == 12
                else month_start.replace(month=month_start.month + 1)
            )
            monthly_trend.append({
                "month": month_start.strftime("%b"),
                "year":  month_start.year,
                "count": Event.objects(
                    created_at__gte=month_start,
                    created_at__lt=month_end,
                ).count(),
            })

        # ── Recent bookings (last 5) ──────────────────────────
        recent_bookings = []
        for ev in Event.objects().order_by("-created_at").limit(5):
            client_name = ""
            try:
                if ev.client:
                    client_name = ev.client.full_name or ""
            except Exception:
                pass
            recent_bookings.append({
                "id":                   str(ev.id),
                "event_name":           ev.event_name,
                "event_type":           ev.event_type or "",
                "city":                 ev.city,
                "client_name":          client_name,
                "status":               ev.status,
                "event_start_datetime": str(ev.event_start_datetime) if ev.event_start_datetime else None,
                "payment_status":       ev.payment.payment_status if ev.payment else "unpaid",
                "total_amount":         ev.payment.total_amount   if ev.payment else 0,
                "paid_amount":          ev.payment.paid_amount    if ev.payment else 0,
            })

        # ── On-duty & user counts ─────────────────────────────
        on_duty_count = StaffProfile.objects(is_online=True).count()
        total_staff   = StaffProfile.objects().count()
        total_clients = ClientProfile.objects().count()

        # ── Live events (happening right now) ─────────────────
        live_events = []
        for ev in Event.objects(
            event_start_datetime__lte=now,
            event_end_datetime__gte=now,
            status__in=["staff_allocated", "planning_started"],
        ).limit(3):
            live_events.append({
                "id":         str(ev.id),
                "event_name": ev.event_name,
                "venue_name": ev.venue.venue_name if ev.venue else "",
                "city":       ev.city,
                "crew_count": ev.crew_count,
                "status":     ev.status,
            })

        return api_response(True, "Dashboard stats fetched", {
            "total_bookings":    total_events,
            "upcoming_events":   upcoming_count,
            "total_revenue":     round(total_revenue, 2),
            "pending_revenue":   round(pending_revenue, 2),
            "on_duty_staff":     on_duty_count,
            "total_staff":       total_staff,
            "total_clients":     total_clients,
            "live_events_count": len(live_events),
            "status_counts":     status_counts,
            "monthly_trend":     monthly_trend,
            "recent_bookings":   recent_bookings,
            "live_events":       live_events,
        })

    except Exception as e:
        return api_response(False, str(e), status=500)


# ─────────────────────────────────────────────────────────────
#  On-Duty Staff with Live Locations
#  GET /api/events/dashboard/on-duty/
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
@require_role(["ADMIN"])
def on_duty_staff(request):
    if request.method != "GET":
        return api_response(False, "Invalid request method", status=405)

    try:
        from apps.users.models import StaffProfile
        from apps.common.location_utils import get_staff_location

        results = []
        for s in StaffProfile.objects(is_online=True):
            loc = get_staff_location(str(s.id))
            results.append({
                "profile_id":         str(s.id),
                "full_name":          s.full_name       or "",
                "stage_name":         s.stage_name      or "",
                "profile_picture":    s.profile_picture or "",
                "city":               s.city            or "",
                "package":            s.package         or "",
                "last_online":        str(s.last_online) if s.last_online else None,
                "lat":                loc.get("lat"),
                "lng":                loc.get("lng"),
                "location_timestamp": loc.get("timestamp"),
                "location_status":    "online" if loc.get("success") and loc.get("lat") else "no_gps",
            })

        return api_response(True, "On-duty staff fetched", {
            "results": results,
            "total":   len(results),
        })

    except Exception as e:
        return api_response(False, str(e), status=500)
    


