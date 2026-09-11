"""AC-3 (SPEC.md, требование 1): `orchestrator.acceptance.run_full_suite()`
переходит на pytest как раннер полного набора `tests/`, сохраняя
контракт (нет `tests/` — не «зелено», таймаут всего прогона —
`config.FULL_SUITE_TIMEOUT_SEC`).

Красен до реализации: `run_full_suite()` на этой ветке всё ещё вызывает
`python3 -m unittest discover` — сводка успешного/красного прогона несёт
unittest-формат («OK»/«FAILED (failures=1)»), не pytest-формат («N
passed»/«N failed»); `test_ac3_passing_suite_is_green_with_pytest_summary`
и `test_ac3_failing_suite_is_red_with_pytest_style_wording` падают на
текущем выводе. `test_ac3_missing_tests_dir_is_not_green` и
`test_ac3_timeout_is_not_green` — контроль: вырожденный случай и таймаут
не зависят от конкретного раннера и уже проходят на текущем коде (тот же
принцип, что AC-2 в `test_ac1_ac2_run.py`).
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import acceptance, config  # noqa: E402

PASSING_TEST = """import unittest


class MarkerTest(unittest.TestCase):
    def test_always_passes(self):
        self.assertTrue(True)
"""

FAILING_TEST = """import unittest


class MarkerTest(unittest.TestCase):
    def test_deliberately_fails(self):
        self.fail("MARKER-RED")
"""

SLEEPING_TEST = """import time
import unittest


class MarkerTest(unittest.TestCase):
    def test_sleeps_past_the_timeout(self):
        time.sleep(3)
"""


class RunFullSuitePytestTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def write_test(self, content: str) -> None:
        tests_dir = self.root / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_marker.py").write_text(content, encoding="utf-8")

    def test_ac3_missing_tests_dir_is_not_green(self):
        """`tests/` нет в `root` — `(False, "tests/ нет в worktree — полный
        набор не проверен")`, ровно как и до перехода на pytest.

        Ловит мутацию: смена раннера ошибочно трактует отсутствие
        `tests/` как «нечего гонять — зелено» (перепутано с вырожденным
        случаем `run()` для acceptance_tests/) — `assertFalse(green)`
        откажет.
        """
        green, tail = acceptance.run_full_suite(self.root)
        self.assertFalse(green)
        self.assertIn("tests/", tail)

    def test_ac3_passing_suite_is_green_with_pytest_summary(self):
        """Реальный прогон `tests/` с одним проходящим тестом под pytest —
        зелёный результат с pytest-сводкой в хвосте.

        Ловит мутацию: `run_full_suite()` не переключён на pytest —
        хвост несёт unittest-формат («OK») вместо «N passed»,
        `assertRegex` откажет.
        """
        self.write_test(PASSING_TEST)
        green, tail = acceptance.run_full_suite(self.root)
        self.assertTrue(green, tail)
        self.assertRegex(tail, r"\d+\s+passed")

    def test_ac3_failing_suite_is_red_with_pytest_style_wording(self):
        """Реальный прогон `tests/` с одним намеренно красным тестом под
        pytest — красный результат, диагностика в хвосте, формат сводки
        — pytest («failed»), не unittest («FAILED (failures=1)»).

        Ловит мутацию: раннер остался unittest — красная сводка несёт
        `FAILED (failures=1)`, `assertNotIn` на этот формат откажет.
        """
        self.write_test(FAILING_TEST)
        green, tail = acceptance.run_full_suite(self.root)
        self.assertFalse(green)
        self.assertIn("MARKER-RED", tail)
        self.assertRegex(tail, r"\d+\s+failed")
        self.assertNotIn("FAILED (failures=", tail)

    def test_ac3_timeout_is_not_green(self):
        """Превышение `config.FULL_SUITE_TIMEOUT_SEC` (подменённого на 1с)
        намеренно спящим тестом (3с) — красный результат с текстом о
        превышении таймаута.

        Ловит мутацию: обработчик `subprocess.TimeoutExpired` потерян
        при сборке новой pytest-команды — исключение уйдёт наружу вместо
        `(False, ...)`.
        """
        self.write_test(SLEEPING_TEST)
        with mock.patch.object(config, "FULL_SUITE_TIMEOUT_SEC", 1):
            green, tail = acceptance.run_full_suite(self.root)
        self.assertFalse(green)
        self.assertIn("превысил", tail)


if __name__ == "__main__":
    unittest.main()
