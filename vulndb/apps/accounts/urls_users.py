from django.urls import path

from vulndb.apps.accounts import views

urlpatterns = [
    path("", views.user_list, name="user_list"),
    path("<int:user_id>/", views.user_edit, name="user_edit"),
]
