from django.contrib.auth import get_user_model
from django.test import TestCase

from vulndb.apps.accounts.models import Role
from vulndb.apps.core.models import SystemSettings

User = get_user_model()


class LocalUserAdminTests(TestCase):
    def setUp(self):
        s = SystemSettings.load()
        s.setup_completed = True
        s.save()
        self.admin = User.objects.create_user(
            username="admin",
            password="AdminPassw0rd!",
            role=Role.PLATFORM_ADMIN,
            is_superuser=True,
            is_staff=True,
        )
        self.analyst = User.objects.create_user(
            username="analyst",
            password="AnalystPass1!",
            role=Role.ANALYST,
        )

    def test_analyst_cannot_open_users(self):
        self.client.force_login(self.analyst)
        r = self.client.get("/users/")
        self.assertRedirects(r, "/", fetch_redirect_response=False)

    def test_analyst_nav_has_no_users_link(self):
        self.client.force_login(self.analyst)
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'href="/users/"')

    def test_admin_nav_has_users_link(self):
        self.client.force_login(self.admin)
        r = self.client.get("/")
        self.assertContains(r, 'href="/users/"')


    def test_admin_creates_local_user_with_role(self):
        self.client.force_login(self.admin)
        r = self.client.post(
            "/users/",
            {
                "username": "executor1",
                "full_name": "И. Исполнитель",
                "email": "exec@example.ru",
                "role": Role.TICKET_ASSIGNEE,
                "password": "S3cure-Local-User!",
                "password2": "S3cure-Local-User!",
                "is_active": "on",
            },
        )
        self.assertEqual(r.status_code, 302)
        u = User.objects.get(username="executor1")
        self.assertEqual(u.role, Role.TICKET_ASSIGNEE)
        self.assertFalse(u.is_superuser)
        self.assertTrue(u.check_password("S3cure-Local-User!"))

    def test_admin_cannot_remove_last_admin(self):
        self.client.force_login(self.admin)
        r = self.client.post(
            f"/users/{self.admin.pk}/",
            {
                "full_name": self.admin.full_name,
                "email": "",
                "role": Role.ANALYST,
                "is_active": "on",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, Role.PLATFORM_ADMIN)

    def test_mismatch_passwords_rejected(self):
        self.client.force_login(self.admin)
        r = self.client.post(
            "/users/",
            {
                "username": "bad",
                "role": Role.ANALYST,
                "password": "S3cure-Local-User!",
                "password2": "other",
                "is_active": "on",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="bad").exists())
