"""Приёмочные тесты T077, AC-1 (tasks/T077/SPEC.md): сообщение об
отсутствии или пустом объяснении маркера красноты называет требование
«непустое объяснение на той же строке после двоеточия»
(«Красен до реализации:»/«Зелёный с рождения:»).

Красен до реализации: текущее сообщение guard.py
(`redness_marker_errors_from_files`) — общее «нет маркера «Красен до
реализации:» или «Зелёный с рождения:» в докстринге модуля», без
единого слова про «ту же строку» или «двоеточие». Фактура T069 (SPEC
T077, Контекст): роль дважды перенесла объяснение на следующую строку,
и guard об этом не предупредил — оба сценария (маркер отсутствует
вовсе / объяснение перенесено на следующую строку) сегодня дают ровно
одно и то же общее сообщение.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts import guard  # noqa: E402


class RednessMarkerMissingMessageTest(unittest.TestCase):
    """Маркер вовсе отсутствует в докстринге."""

    def test_ac1_marker_absent_message_names_same_line_after_colon(self):
        source = '"""Обычный докстринг без маркера."""\nimport unittest\n'

        errors = guard.redness_marker_errors_from_files([("test_x.py", source)])
        joined = " ".join(errors)

        self.assertTrue(errors, "маркер отсутствует — ожидалась ошибка")
        self.assertIn("той же строке", joined)
        self.assertIn("двоеточия", joined)


class RednessMarkerExplanationOnNextLineMessageTest(unittest.TestCase):
    """Маркер есть, но объяснение — на следующей строке, не после
    двоеточия (ровно фактура T069)."""

    def test_ac1_explanation_on_next_line_message_names_same_line_after_colon(self):
        source = (
            '"""Докстринг модуля.\n\n'
            'Красен до реализации:\n'
            'причина на следующей строке, не после двоеточия\n'
            '"""\nimport unittest\n')

        errors = guard.redness_marker_errors_from_files([("test_x.py", source)])
        joined = " ".join(errors)

        self.assertTrue(
            errors,
            "объяснение маркера перенесено на следующую строку — "
            "ожидалась ошибка")
        self.assertIn("той же строке", joined)
        self.assertIn("двоеточия", joined)


if __name__ == "__main__":
    unittest.main()
