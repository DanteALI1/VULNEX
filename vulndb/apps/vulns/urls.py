from django.urls import path

from . import views

urlpatterns = [
    path("", views.vuln_list, name="vuln_list"),
    path("local/new/", views.vuln_create_local, name="vuln_create_local"),
    path("<path:vuln_id>/", views.vuln_detail, name="vuln_detail"),
]
