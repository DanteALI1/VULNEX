from django.contrib.auth.views import LoginView


class VulndbLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True
