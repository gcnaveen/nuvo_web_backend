# apps/users/urls.py  — FINAL (add staff_self_register import + path)

from django.urls import path
from .views import (
    admin_delete_gallery_image,
    get_profile,
    get_staff_detail,
    update_profile,
    complete_client_profile,
    complete_staff_profile,
    complete_makeup_profile,
    get_my_profile,
    update_my_profile,
    upload_staff_images,
    update_client_subscription,
    list_staff,
    list_makeup_artists,
    list_clients,
    admin_create_client,
    get_client_detail,
    admin_create_staff,
    admin_delete_staff,
    admin_delete_client,
    admin_upload_staff_images,
    admin_update_staff,
    get_mua_detail,
    admin_create_mua,
    admin_update_mua,
    admin_delete_mua,
    admin_upload_mua_images,
    admin_delete_mua_gallery_image,
)
from .staff_registration import staff_self_register   # ← NEW

urlpatterns = [
    # ── Auth user profile ────────────────────────────────────────
    path("profile/",         get_profile),
    path("profile/update/",  update_profile),

    # ── Self-registration (public — no auth) ─────────────────────
    path("register/staff/",  staff_self_register),      # ← NEW  POST multipart/form-data 
# 


    # ── Complete profile (post-OTP, role-gated) ──────────────────
    path("complete/client/",  complete_client_profile),
    path("complete/staff/",   complete_staff_profile),
    path("complete/makeup/",  complete_makeup_profile),

    # ── Logged-in user's own profile ─────────────────────────────
    path("my-profile/",      get_my_profile),
    path("update-profile/",  update_my_profile),
    path("staff/upload-images/", upload_staff_images),

    # ── Admin — clients ──────────────────────────────────────────
    path("admin/update-subscription/",          update_client_subscription),
    path("admin/create-client/",                admin_create_client),
    path("admin/clients/<str:client_id>/delete/", admin_delete_client),

    # ── Admin — staff ────────────────────────────────────────────
    path("admin/staff/create/",                          admin_create_staff),
    path("admin/staff/<str:staff_id>/update/",           admin_update_staff),
    path("admin/staff/<str:staff_id>/delete/",           admin_delete_staff),
    path("admin/staff/<str:staff_id>/upload-images/",    admin_upload_staff_images),
    path("admin/staff/<str:staff_id>/delete-gallery/",   admin_delete_gallery_image),

    # ── Admin — makeup artists ───────────────────────────────────
    path("admin/makeup-artists/create/",                         admin_create_mua),
    path("admin/makeup-artists/<str:mua_id>/update/",            admin_update_mua),
    path("admin/makeup-artists/<str:mua_id>/delete/",            admin_delete_mua),
    path("admin/makeup-artists/<str:mua_id>/upload-images/",     admin_upload_mua_images),
    path("admin/makeup-artists/<str:mua_id>/delete-gallery/",    admin_delete_mua_gallery_image),

    # ── API — list + detail (admin-authenticated) ────────────────
    path("api/clients/",                         list_clients),
    path("api/clients/<str:client_id>/",         get_client_detail),
    path("api/staff/",                           list_staff),
    path("api/staff/<str:staff_id>/",            get_staff_detail),
    path("api/makeup-artists/",                  list_makeup_artists),
    path("api/makeup-artists/<str:mua_id>/",     get_mua_detail),
]