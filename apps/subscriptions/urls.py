# apps/subscriptions/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("plans/",    views.list_plans,      name="subscription-plans"),
    path("initiate/", views.initiate,         name="subscription-initiate"),
    path("callback/", views.callback,         name="subscription-callback"),
    path("webhook/",  views.webhook,          name="subscription-webhook"),
    path("my/",       views.my_subscription,  name="subscription-my"),
]
