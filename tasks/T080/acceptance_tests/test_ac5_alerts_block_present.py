"""AC-5 (tasks/T080/SPEC.md): макет содержит блок алертов.

Красен до реализации: HTML-файлов ещё нет (см. AC-1) — блока алертов
искать негде. Как только появится макет, тест ищет узел, который либо
структурно помечен как алерт (class/id со словом alert), либо подписан
заголовком «алерты»/«alerts»/«уведомления».
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import unittest  # noqa: E402

import _html_utils as h  # noqa: E402

HEADING_RE = re.compile(r"^(алерт\w*|alerts?|уведомлени\w*)$", re.I)
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "caption", "summary"}


def _is_alert_block(node):
    cls = (node.attrs.get("class") or "").lower()
    nid = (node.attrs.get("id") or "").lower()
    if "alert" in cls or "alert" in nid:
        return True
    if node.tag in HEADING_TAGS and HEADING_RE.match(h.own_text(node)):
        return True
    return False


class AlertsBlockPresentTest(unittest.TestCase):

    def test_ac5_alerts_block_is_present_in_some_html_file(self):
        files = h.html_files()
        if not files:
            self.fail(
                "в tasks/T080/ нет HTML-файлов макета — проверять AC-5 "
                "не на чем (см. AC-1)")
        found = False
        for path in files:
            root = h.parse(path.read_text(encoding="utf-8"))
            for node in h.walk(root):
                if _is_alert_block(node):
                    found = True
                    break
            if found:
                break
        self.assertTrue(
            found,
            "не найден блок алертов: ни в одном HTML-файле нет элемента "
            "с class/id, содержащим «alert», ни заголовка «Алерты»/"
            "«Alerts»/«Уведомления» (AC-5)")


if __name__ == "__main__":
    unittest.main()
