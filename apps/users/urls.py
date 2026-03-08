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
    get_staff_detail,
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

urlpatterns = [
    path("profile/", get_profile),
    path("profile/update/", update_profile),
    # path("admin/all-users/", list_all_users),
    path("complete/client/", complete_client_profile),
    path("complete/staff/", complete_staff_profile),
    path("complete/makeup/", complete_makeup_profile),
    path("my-profile/", get_my_profile),
    path("update-profile/", update_my_profile),
    path("staff/upload-images/", upload_staff_images),
    path("admin/update-subscription/", update_client_subscription),
    path("api/staff/", list_staff ),
    path("api/makeup-artists/",list_makeup_artists),
    path("api/clients/", list_clients),
    path("admin/create-client/", admin_create_client),
    path("api/clients/<str:client_id>/", get_client_detail),
    path("api/staff/<str:staff_id>/", get_staff_detail),
    path("admin/staff/create/", admin_create_staff),
    path("admin/staff/<str:staff_id>/delete/", admin_delete_staff),
    path("admin/clients/<str:client_id>/delete/", admin_delete_client),
    path("admin/staff/<str:staff_id>/upload-images/",  admin_upload_staff_images),
    path("admin/staff/<str:staff_id>/delete-gallery/",  admin_delete_gallery_image),
    path("admin/staff/<str:staff_id>/update/", admin_update_staff),

    # make up artist endpoints can be added here in the future
    path("api/makeup-artists/", list_makeup_artists),
    path("api/makeup-artists/<str:mua_id>/",   get_mua_detail),
    path("admin/makeup-artists/create/",     admin_create_mua),
    path("admin/makeup-artists/<str:mua_id>/update/", admin_update_mua),
    path("admin/makeup-artists/<str:mua_id>/delete/",  admin_delete_mua),
    path("admin/makeup-artists/<str:mua_id>/upload-images/", admin_upload_mua_images),
    path("admin/makeup-artists/<str:mua_id>/delete-gallery/", admin_delete_mua_gallery_image),
]












