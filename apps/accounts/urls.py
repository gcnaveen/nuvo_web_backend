# apps/accounts/urls.py
from django.urls import path
from .views import (
    send_otp,
    verify_otp,
    refresh_token,
    resend_otp,
    logout,
    me,
    change_user_status,
    # New
    register_staff_or_makeup,
    register_admin,
    approve_user,
    list_pending_users,
)

urlpatterns = [
    # ── OTP / Login flow ──────────────────────────────────────
    path("send-otp/",       send_otp),
    path("verify-otp/",     verify_otp),
    path("refresh-token/",  refresh_token),
    path("resend-otp/",     resend_otp),
    path("logout/",         logout),
    path("me/",             me),

    # ── Self-registration ─────────────────────────────────────
    path("register/staff-makeup/",  register_staff_or_makeup),
    path("register/admin/",         register_admin),

    # ── Admin actions ─────────────────────────────────────────
    path("admin/change-status/",    change_user_status),
    path("admin/approve-user/",     approve_user),
    path("admin/pending-users/",    list_pending_users),
]