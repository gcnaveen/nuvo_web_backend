# apps/events/urls.py

from django.urls import path
from . import views

urlpatterns = [

    # ── CRUD ─────────────────────────────────────────────────────
    path("",                                  views.list_events,         name="list_events"),
    path("create/",                           views.create_event,        name="create_event"),
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

    # ── Client-facing (mobile app) ────────────────────────────────
    path("my-events/",                        views.my_events,           name="my_events"),
]