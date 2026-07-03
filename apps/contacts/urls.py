from django.urls import path
from . import views

urlpatterns = [
    # Categories
    path("categories/",                      views.list_categories,   name="list_categories"),
    path("categories/create/",               views.create_category,   name="create_category"),
    path("categories/<str:category_id>/delete/", views.delete_category, name="delete_category"),

    # Contacts
    path("",                                 views.list_contacts,     name="list_contacts"),
    path("create/",                          views.create_contact,    name="create_contact"),
    path("<str:contact_id>/",                views.get_contact,       name="get_contact"),
    path("<str:contact_id>/update/",         views.update_contact,    name="update_contact"),
    path("<str:contact_id>/delete/",         views.delete_contact,    name="delete_contact"),
]
