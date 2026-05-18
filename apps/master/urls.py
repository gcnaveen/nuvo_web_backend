# apps/master/urls.py  — FINAL with inventory endpoints

from django.urls import path
from .views import *

urlpatterns = [
    # ── Event Themes ──────────────────────────────────────────────
    path("themes/create/",                   create_event_theme),
    path("themes/",                          list_event_themes),
    path("themes/<str:theme_id>/update/",    update_event_theme),
    path("themes/<str:theme_id>/delete/",    delete_event_theme),

    # ── Uniform Categories (Master Data) ──────────────────────────
    # NOTE: static paths must come before parameterised ones
    path("uniform/create/",                         create_uniform_category),
    path("uniform/filter/",                         filter_uniform_categories),   # public, no auth
    path("uniform/",                                list_uniform_categories),
    path("uniform/<str:category_id>/update/",       update_uniform_category),
    path("uniform/<str:category_id>/delete/",       delete_uniform_category),

    # ── Inventory (extends uniform categories) ─────────────────────
    # summary/ must come before <category_id>/ to avoid collision
    path("inventory/summary/",                      inventory_summary),
    path("inventory/",                              list_inventory),
    path("inventory/<str:category_id>/",            get_inventory_item),
    path("inventory/<str:category_id>/stock/",      update_stock),
    path("inventory/<str:category_id>/adjust/",     adjust_in_use),

    # ── Crew Members ──────────────────────────────────────────────
    path("crew/public/",                             list_crew_members_public),   # no auth, mobile
    path("crew/create/",                             create_crew_member),
    path("crew/",                                    list_crew_members),
    path("crew/<str:member_id>/update/",             update_crew_member),
    path("crew/<str:member_id>/delete/",             delete_crew_member),

    # ── Subscription Plans ────────────────────────────────────────
    path("subscription/",                           list_subscription_plans),
    path("subscription/<str:plan_name>/update/",    update_subscription_plan),

    # ── Payment Terms ─────────────────────────────────────────────
    path("payment/config/",                         get_payment_config_public),  # no auth, mobile
    path("payment/",                                get_payment_terms),
    path("payment/update/",                         update_payment_terms),

    # ── Coupons ───────────────────────────────────────────────────
    path("coupons/apply/",                          apply_coupon),             # no auth, mobile
    path("coupons/validate/",                       validate_coupon),          # no auth, mobile
    path("coupons/create/",                         create_coupon),
    path("coupons/",                                list_coupons),
    path("coupons/<str:coupon_id>/update/",         update_coupon),
    path("coupons/<str:coupon_id>/delete/",         delete_coupon),
]