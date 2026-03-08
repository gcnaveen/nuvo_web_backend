# apps/master/urls.py
from django.urls import path
from .views import *

urlpatterns = [
    # Event Themes
    path("themes/create/", create_event_theme),
    path("themes/", list_event_themes),
    path("themes/<str:theme_id>/update/", update_event_theme),
    path("themes/<str:theme_id>/delete/", delete_event_theme),

    # Uniform
    path("uniform/create/", create_uniform_category),
    path("uniform/", list_uniform_categories),
    path("uniform/<str:category_id>/update/", update_uniform_category),
    path("uniform/<str:category_id>/delete/", delete_uniform_category),

    # Subscription
    path("subscription/<str:plan_name>/update/", update_subscription_plan),
    path("subscription/",  list_subscription_plans),

    # Payment
    path("payment/update/", update_payment_terms),
    path("payment/",       get_payment_terms)
]
