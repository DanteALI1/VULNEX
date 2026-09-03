from django.urls import path

from . import views

urlpatterns = [
    path("", views.app_settings, name="app_settings"),
    path("system/metrics/", views.system_metrics_api, name="system_metrics_api"),
]
