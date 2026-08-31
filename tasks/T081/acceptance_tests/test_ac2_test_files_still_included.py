"""AC-2 (tasks/T081/SPEC.md): `guard.scan_acceptance_tests` по-прежнему
включает в результат маркеры и тестовые методы из файлов
acceptance_tests/test_*.py — поведение для этих файлов не изменилось.

Зелёный с рождения: для файлов `test_*.py` это уже сегодняшнее поведение
`scan_acceptance_tests` (scripts/guard.py:216) — AC-2 требует, чтобы фильтр
по имени файла из AC-1 не задел этот случай, а не вводит новую логику.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts import guard  # noqa: E402


class TestFileStillIncludedTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)
        (self.tdir / "acceptance_tests").mkdir(parents=True)

    def write(self, name: str, content: str) -> None:
        (self.tdir / "acceptance_tests" / name).write_text(
            content, encoding="utf-8")

    def test_ac2_test_method_in_test_file_is_counted(self):
        self.write("test_ac.py", "def test_ac3_something():\n    pass\n")

        tested, _ = guard.scan_acceptance_tests(self.tdir)

        self.assertIn(3, tested)

    def test_ac2_manual_marker_in_test_file_is_counted(self):
        # Конкатенация литерала (приём T075, коммит 7cb7e25): этот файл
        # сам подпадает под test_*.py и читается scan_acceptance_tests при
        # проверке T081, поэтому сплошной литерал "AC-4: manual" в
        # исходнике был бы прочитан как реальная пометка T081 (тот же
        # класс дефекта, что ANSWER-1, 31.08).
        self.write("test_ac.py", "# AC-" + "4: manual — проверка глазами\n")

        _, markers = guard.scan_acceptance_tests(self.tdir)

        self.assertEqual(markers[4], ("manual", "проверка глазами"))

    def test_ac2_escalate_marker_in_test_file_is_counted(self):
        # Конкатенация литерала (приём T075, коммит 7cb7e25): этот файл
        # сам подпадает под test_*.py и читается scan_acceptance_tests при
        # проверке T081, поэтому сплошной литерал "AC-5: escalate" в
        # исходнике был бы прочитан как настоящая эскалация T081
        # (ANSWER-1, 31.08).
        self.write("test_ac.py",
                   "# AC-5: esca" + "late — критерий противоречив\n")

        _, markers = guard.scan_acceptance_tests(self.tdir)

        self.assertEqual(markers[5], ("escalate", "критерий противоречив"))
