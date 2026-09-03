from django.urls import path

from . import views

urlpatterns = [
    path("", views.app_settings, name="app_settings"),
]
