from django.urls import path

from . import views

urlpatterns = [
    path("", views.setup_wizard, name="setup_wizard"),
    path("db/test/", views.setup_db_test, name="setup_db_test"),
    path("db/create/", views.setup_db_create, name="setup_db_create"),
]
