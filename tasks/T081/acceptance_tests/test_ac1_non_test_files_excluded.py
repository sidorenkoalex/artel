"""AC-1 (tasks/T081/SPEC.md): `guard.scan_acceptance_tests` не включает
в результат (ни в тестированные AC, ни в пометки manual/skip/escalate)
маркеры и тестовые методы из файлов каталога acceptance_tests/, чьё имя
не начинается с `test_`.

Красен до реализации: `scan_acceptance_tests` сейчас читает все `*.py`
каталога acceptance_tests/ без фильтра по имени файла
(scripts/guard.py:216, `rglob("*.py")`) — маркер и тест-метод из файла
вроде `_sandbox.py` сегодня тоже попадают в результат, а этот тест
ожидает обратное.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts import guard  # noqa: E402


class NonTestFileExcludedTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)
        (self.tdir / "acceptance_tests").mkdir(parents=True)

    def write(self, name: str, content: str) -> None:
        (self.tdir / "acceptance_tests" / name).write_text(
            content, encoding="utf-8")

    def test_ac1_test_method_in_non_test_file_is_not_counted(self):
        # Конкатенация литерала (приём T075, коммит 7cb7e25): нынешний
        # (ещё не починенный этой задачей) scan_acceptance_tests читает и
        # ЭТОТ файл, поэтому сплошной литерал "test_ac7_helper" в
        # исходнике теста был бы прочитан как реальный тест-метод T081
        # (тот же класс дефекта, что ANSWER-1, 31.08).
        self.write("_sandbox.py", "def test_ac" + "7_helper():\n    pass\n")

        tested, _ = guard.scan_acceptance_tests(self.tdir)

        self.assertNotIn(7, tested)

    def test_ac1_manual_marker_in_non_test_file_is_not_counted(self):
        # Конкатенация литерала (та же причина, что выше): сплошной
        # литерал "AC-8: manual" в исходнике был бы прочитан как реальная
        # пометка T081.
        self.write("_sandbox.py", "# AC-" + "8: manual — проверка глазами\n")

        _, markers = guard.scan_acceptance_tests(self.tdir)

        self.assertNotIn(8, markers)

    def test_ac1_escalate_marker_in_non_test_file_is_not_counted(self):
        # Конкатенация литерала (приём T075, коммит 7cb7e25): нынешний
        # (ещё не починенный этой задачей) scan_acceptance_tests читает и
        # ЭТОТ файл (test_ac1_*.py сам под acceptance_tests/), поэтому
        # сплошной литерал "AC-9: escalate" в исходнике теста был бы
        # прочитан как настоящая эскалация T081 (ANSWER-1, 31.08).
        self.write(
            "_sandbox.py",
            "# AC-9: esca" + "late — критерий противоречив\n")

        _, markers = guard.scan_acceptance_tests(self.tdir)

        self.assertNotIn(9, markers)
