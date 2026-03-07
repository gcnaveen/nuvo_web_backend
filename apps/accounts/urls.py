# apps/accounts/urls.py
# Add this to your existing urlpatterns — just the new line shown with ← NEW

from django.urls import path
from . import views

urlpatterns = [
    path("send-otp/",              views.send_otp,               name="send_otp"),
    path("verify-otp/",            views.verify_otp,             name="verify_otp"),
    path("refresh-token/",         views.refresh_token,          name="refresh_token"),
    path("logout/",                views.logout,                 name="logout"),
    path("resend-otp/",            views.resend_otp,             name="resend_otp"),
    path("me/",                    views.me,                     name="me"),
    path("register/staff-makeup/", views.register_staff_or_makeup, name="register_staff_makeup"),
    path("register/admin/",        views.register_admin,         name="register_admin"),
    path("admin/login/",           views.admin_login,            name="admin_login"),   # ← NEW
    path("admin/approve-user/",    views.approve_user,           name="approve_user"),
    path("admin/pending-users/",   views.list_pending_users,     name="list_pending_users"),
    path("admin/change-status/",   views.change_user_status,     name="change_user_status"),
]