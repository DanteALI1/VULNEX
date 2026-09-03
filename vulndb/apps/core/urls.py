from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("healthz", views.healthz, name="healthz"),
    path("healthz/", views.healthz, name="healthz_slash"),
    path("readyz", views.readyz, name="readyz"),
]
