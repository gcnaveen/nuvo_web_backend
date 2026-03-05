from django.urls import path
from .views import (
    get_profile,
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
]




