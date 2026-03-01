from django.urls import path
from .views import send_otp, verify_otp, refresh_token, resend_otp, logout, me, change_user_status

urlpatterns = [
    path("send-otp/", send_otp),
    path("verify-otp/", verify_otp),
    path("refresh-token/", refresh_token),
    path("resend-otp/", resend_otp),
    path("logout/", logout),
    path("me/", me),
    path("admin/change-status/", change_user_status),
]