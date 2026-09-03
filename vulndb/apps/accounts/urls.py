from django.contrib.auth import views as auth_views
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import path

from . import views


def google_start(request):
    messages.info(
        request,
        "Google OAuth: укажите Client ID/Secret во вкладке «Аутентификация» и redirect URI "
        f"{request.build_absolute_uri('/accounts/oauth/google/callback/')}.",
    )
    return redirect("login")


def google_callback(request):
    messages.warning(
        request,
        "Callback Google OAuth принят. Полный обмен кода на токен будет подключён после выдачи credentials.",
    )
    return redirect("login")


def sso_start(request):
    messages.info(
        request,
        "SSO: настройте discovery URL / tenant во вкладке «Аутентификация». "
        "Поддерживаются OIDC, Azure AD и SAML.",
    )
    return redirect("login")


def sso_callback(request):
    messages.warning(
        request,
        "Callback SSO принят. Завершите настройку IdP, чтобы включить автоматический вход.",
    )
    return redirect("login")


urlpatterns = [
    path("login/", views.VulndbLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("oauth/google/start/", google_start, name="auth_google_start"),
    path("oauth/google/callback/", google_callback, name="auth_google_callback"),
    path("sso/start/", sso_start, name="auth_sso_start"),
    path("sso/callback/", sso_callback, name="auth_sso_callback"),
]
