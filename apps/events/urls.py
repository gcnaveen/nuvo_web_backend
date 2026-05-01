# apps/events/urls.py

from django.urls import path
from . import views
from .dashboard_views import admin_dashboard_stats, on_duty_staff

urlpatterns = [

    # ── Admin Dashboard ───────────────────────────────────────────
    path("dashboard/stats/",    admin_dashboard_stats, name="dashboard_stats"),
    path("dashboard/on-duty/",  on_duty_staff,         name="on_duty_staff"),

    # ── CRUD ─────────────────────────────────────────────────────
    path("",                                  views.list_events,         name="list_events"),
    path("create/",                           views.create_event,        name="create_event"),

    # ── Client-facing (mobile app) ────────────────────────────────
    path("get-my-events/",                    views.client_my_events,    name="get_my_events"),

    path("<str:event_id>/",                   views.get_event,           name="get_event"),
    path("<str:event_id>/update/",            views.update_event,        name="update_event"),
    path("<str:event_id>/delete/",            views.delete_event,        name="delete_event"),

    # ── Status & Crew ─────────────────────────────────────────────
    path("<str:event_id>/status/",            views.update_event_status, name="update_event_status"),
    path("<str:event_id>/available-staff/",   views.available_staff,     name="available_staff"),
    path("<str:event_id>/assign-crew/",       views.assign_crew,         name="assign_crew"),

    # ── Live Tracking ─────────────────────────────────────────────
    path("<str:event_id>/track/",             views.track_event,         name="track_event"),

    # ── Payment ───────────────────────────────────────────────────
    path("<str:event_id>/payment/initiate/",  views.initiate_payment,    name="initiate_payment"),
    path("payment/callback/",                 views.payment_callback,    name="payment_callback"),
    path("payment/webhook/",                  views.payment_webhook,     name="payment_webhook"),

    # ── Staff-facing (mobile app) ─────────────────────────────────
    path("staff/upcoming-all/",   views.staff_upcoming_events,      name="staff_upcoming_events"),
    path("staff/assigned/",       views.staff_assigned_events,      name="staff_assigned_events"),
    path("staff/completed/",      views.staff_completed_events,     name="staff_completed_events"),
    path("staff/online-status/",  views.update_staff_online_status, name="update_staff_online_status"),

]