from pathlib import Path

from django.test import TestCase
from openpyxl import Workbook

from vulndb.apps.vulns.models import Vulnerability
from vulndb.apps.vulns.tasks import parse_bdu_workbook


def _write_bdu_xlsx(path: Path, title: str, vendor: str = "Vendor") -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(["Информационное сообщение"])
    ws.append(["Перечень уязвимостей"])
    ws.append(["Идентификатор", "Наименование уязвимости", "Описание", "Вендор"] + [""] * 26)
    row = [""] * 30
    row[0] = "BDU:2026-09999"
    row[1] = title
    row[2] = "Описание"
    row[3] = vendor
    ws.append(row)
    wb.save(path)


class BduParseTests(TestCase):
    def test_title_field_has_no_varchar_limit(self):
        field = Vulnerability._meta.get_field("title")
        self.assertIsNone(getattr(field, "max_length", None))

    def test_long_fstec_title_is_stored(self):
        title = "Уязвимость " + ("А" * 600)
        vendor = "Вендор " + ("Б" * 400)
        path = Path("/tmp/vulndb_test_bdu.xlsx")
        _write_bdu_xlsx(path, title, vendor)
        synced = parse_bdu_workbook(path)
        self.assertEqual(synced, 1)
        obj = Vulnerability.objects.get(vuln_id="BDU:2026-09999")
        self.assertEqual(obj.title, title)
        self.assertEqual(obj.vendor, vendor)
        self.assertEqual(obj.record_type, Vulnerability.RecordType.BDU)
