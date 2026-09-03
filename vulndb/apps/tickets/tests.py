from django.test import TestCase
from django.contrib.auth import get_user_model

from vulndb.apps.accounts.models import Role
from vulndb.apps.tickets.models import Ticket
from vulndb.apps.tickets.workflow import apply_transition, available_actions
from vulndb.apps.vulns.models import Vulnerability

User = get_user_model()


class TicketWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="x", role=Role.PLATFORM_ADMIN, is_superuser=True
        )
        self.analyst = User.objects.create_user(
            username="analyst", password="x", role=Role.ANALYST, full_name="A Analyst"
        )
        self.assignee = User.objects.create_user(
            username="assignee", password="x", role=Role.TICKET_ASSIGNEE, full_name="I Executor"
        )
        self.vuln = Vulnerability.objects.create(
            vuln_id="CVE-2024-TEST",
            title="Test",
            severity="HIGH",
            cvss_score=8.0,
        )
        self.ticket = Ticket.objects.create(
            number=2001,
            title="Fix test",
            vulnerability=self.vuln,
            created_by=self.analyst,
            status=Ticket.Status.NEW,
        )

    def test_assignee_cannot_close(self):
        self.ticket.assignee = self.assignee
        self.ticket.status = Ticket.Status.IN_PROGRESS
        self.ticket.save()
        ok, _ = apply_transition(self.assignee, self.ticket, "resolve", {"resolution": "patched"})
        self.assertTrue(ok)
        self.assertEqual(self.ticket.status, Ticket.Status.RESOLVED)
        actions = {a.action for a in available_actions(self.assignee, self.ticket)}
        self.assertNotIn("close", actions)
        ok, msg = apply_transition(self.assignee, self.ticket, "close", {})
        self.assertFalse(ok)

    def test_creator_can_close(self):
        self.ticket.assignee = self.assignee
        self.ticket.status = Ticket.Status.RESOLVED
        self.ticket.resolution = "done"
        self.ticket.save()
        ok, _ = apply_transition(self.analyst, self.ticket, "close", {})
        self.assertTrue(ok)
        self.assertEqual(self.ticket.status, Ticket.Status.CLOSED)
