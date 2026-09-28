"""AC-9 — приложение к новым путям требует полного прогона `tests/` в
цикле мержа; приложение к `skills/` — по-прежнему нет.

Источник — SPEC.md, «Критерии приёмки»:

AC-9. `fsm_merge_gate._appendix_needs_full_suite` истинна для каждого из
путей `conftest.py`, `tests/sub/conftest.py`, `pyproject.toml`,
`pytest.ini`, `setup.cfg`, `tox.ini` и ложна для приложения к
`skills/spec-authoring.md` (прежнее поведение).

Красен до реализации: `_FULL_SUITE_APPENDIX_PREFIXES` — `("tests/", ".github/")`, и ни один корневой файл настроек pytest под этот префикс не попадает.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _protected  # noqa: E402,F401 — кладёт корень репозитория в sys.path
from orchestrator import fsm_merge_gate  # noqa: E402

#: Пути критерия. Порядок и состав — дословно из AC-9.
FULL_SUITE_PATHS = ("conftest.py", "tests/sub/conftest.py", "pyproject.toml",
                    "pytest.ini", "setup.cfg", "tox.ini")
NO_FULL_SUITE_PATH = "skills/spec-authoring.md"


class AppendixNeedsFullSuiteTest(unittest.TestCase):

    def test_ac9_appendix_to_test_settings_requires_the_full_suite(self):
        """Каждый из шести путей настроек сбора тестов — корневой
        `conftest.py`, вложенный `tests/sub/conftest.py` и четыре корневых
        файла настроек pytest — включает полный прогон `tests/` после
        применения приложений на мерже.

        Ловит мутацию: условие пополнили только корневым `conftest.py`
        (буквальным префиксом `"conftest.py"`), а остальные четыре
        литерала забыли — самый вероятный неполный вариант, потому что
        именно `conftest.py` назван в заголовке задачи. Наблюдаемое
        расхождение: `_appendix_needs_full_suite(["pyproject.toml"])`
        ложна, `_full_suite_after_appendices_or_refuse` возвращается
        сразу, `acceptance.full_suite` не зовётся вовсе — приложение,
        меняющее настройки pytest, уезжает в main без единого прогона
        тестов на этих настройках.
        """
        for path in FULL_SUITE_PATHS:
            with self.subTest(path=path):
                self.assertTrue(
                    fsm_merge_gate._appendix_needs_full_suite([path]),
                    f"приложение к {path} обязано требовать полного "
                    f"прогона tests/")

    def test_ac9_appendix_to_skills_still_needs_no_full_suite(self):
        """Приложение к `skills/spec-authoring.md` полного прогона не
        требует — прежнее поведение остальных защищённых путей.

        Ловит мутацию: условие пополнили не перечнем новых путей, а
        общей проверкой «путь защищён» (позвав того же помощника) — тогда
        полный прогон включается для ЛЮБОГО приложения. Наблюдаемое
        расхождение: `_appendix_needs_full_suite(["skills/spec-authoring.
        md"])` истинна, и каждый мерж с правкой скила начинает гонять
        полный набор `tests/` — прежнее поведение, которое критерий
        требует сохранить, сломано.
        """
        self.assertFalse(
            fsm_merge_gate._appendix_needs_full_suite([NO_FULL_SUITE_PATH]),
            f"приложение к {NO_FULL_SUITE_PATH} не требовало полного "
            f"прогона и не должно требовать")


if __name__ == "__main__":
    unittest.main()
