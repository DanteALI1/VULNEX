from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from vulndb.apps.accounts.models import Role
from vulndb.apps.core.models import SystemSettings

User = get_user_model()


class SettingsLicenseVisibilityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="x", role=Role.PLATFORM_ADMIN, is_superuser=True
        )
        s = SystemSettings.load()
        s.setup_completed = True
        s.save()
        self.client.force_login(self.admin)

    @override_settings(LICENSE_REQUIRED=False)
    def test_free_edition_hides_license_tab(self):
        r = self.client.get("/settings/")
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'data-tab="license"')
        self.assertNotContains(r, 'data-pane-id="license"')

    @override_settings(LICENSE_REQUIRED=True, DEBUG=True)
    def test_licensed_edition_shows_license_tab(self):
        r = self.client.get("/settings/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'data-tab="license"')


class LoginSsoPlacementTests(TestCase):
    def setUp(self):
        s = SystemSettings.load()
        s.setup_completed = True
        s.auth_google_enabled = True
        s.auth_google_client_id = "google-client"
        s.auth_sso_enabled = True
        s.auth_sso_client_id = "sso-client"
        s.save()

    def test_sso_buttons_render_after_login_submit(self):
        r = self.client.get("/accounts/login/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        login_pos = html.find(">Войти<")
        google_pos = html.find("Войти через Google")
        sso_pos = html.find("Войти через SSO")
        self.assertGreater(login_pos, 0)
        self.assertGreater(google_pos, login_pos)
        self.assertGreater(sso_pos, login_pos)
        self.assertLess(html.find('class="stack-form"'), login_pos)
