"""Приёмочные тесты T083 — AC-2 (SPEC.md, «Критерии приёмки»):

Тестовые классы, которые после T047 зовут реальный git пульта из песочницы
без `fake_git` (пример: `tests/test_spec_budget.py::SpecBudgetOnTheGateTest`
и родственные ей классы того же дефекта), переведены на общий
`sandbox`/`fake_git` (T037) и больше не обращаются к реальному git пульта.

`SpecBudgetOnTheGateTest` сама уже патчит `gitcmd.git` на `fake_git` (T048,
коммит 37f42a8) — это не она. Родственный класс того же дефекта в том же
файле — `LegacyDbMigrationTest` (наследует `SpecBudgetOnTheGateTest`,
переопределяет `setUp` и патчит только `DB`/`TASKS`/`LOGS`; `ROOT`,
`WORKTREES` и `gitcmd.git` остаются непропатченными). Унаследованные
тестовые методы зовут `fsm.cmd_advance`, который на ветке `spec_writing`
безусловно читает `gitcmd.on_foreign_branch(branch)` — с непропатченным
`gitcmd.git` это самый настоящий `subprocess.run(["git", ...],
cwd=config.ROOT)`, а `config.ROOT` в этом классе — РЕАЛЬНЫЙ корень пульта
(рабочая копия, откуда запущен тест), не временный каталог.

Красен до реализации: подмена `subprocess.run` на прогоне
`LegacyDbMigrationTest` сегодня фиксирует 208 вызовов с `cwd`, совпадающим
с непропатченным `config.ROOT` (реальный пульт) — эмпирически
перепроверено перед записью этого файла. Подход провалидирован: с
временным стабом (те же патчи `ROOT`/`WORKTREES`/`gitcmd.git` на
`fake_git`, что несёт `SpecBudgetOnTheGateTest.setUp`, добавленные в
`LegacyDbMigrationTest.setUp`, не закоммичены) число таких вызовов падает
до нуля, и сам класс остаётся зелёным.

Поведенческая проверка, не текстовый грep по `setUp` — тот же принцип,
что в `tasks/T061/acceptance_tests/test_tmproottest_adoption.py`
(«поведенчески доказать», не «грепать код на конкретную форму патча»):
некоторые исправления оборачивают патчинг в общий хелпер, статический
разбор тела `setUp` такое пропустит.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config  # noqa: E402
from tests import test_spec_budget  # noqa: E402


class LegacyDbMigrationTestDoesNotTouchRealPultGitTest(unittest.TestCase):
    """AC-2: `LegacyDbMigrationTest` — родственный класс дефекта T047 в том
    же файле, что и `SpecBudgetOnTheGateTest`."""

    def test_ac2_legacy_db_migration_test_never_shells_out_to_the_real_pult_root(self):
        real_root = config.ROOT
        calls = []
        real_run = subprocess.run

        def spy_run(args, **kwargs):
            calls.append((list(args) if not isinstance(args, str) else [args],
                          kwargs.get("cwd")))
            return real_run(args, **kwargs)

        loader = unittest.defaultTestLoader
        suite = loader.loadTestsFromTestCase(test_spec_budget.LegacyDbMigrationTest)
        result = unittest.TestResult()
        with mock.patch("subprocess.run", side_effect=spy_run):
            suite.run(result)

        self.assertTrue(
            result.wasSuccessful(),
            f"LegacyDbMigrationTest сам не прошёл: errors={result.errors} "
            f"failures={result.failures}")

        touching_real_root = [call for call in calls if call[1] == real_root]
        self.assertEqual(
            touching_real_root, [],
            "LegacyDbMigrationTest зовёт настоящий git реального пульта "
            f"(cwd={real_root}) вместо fake_git (AC-2): "
            f"{touching_real_root[:5]}")


if __name__ == "__main__":
    unittest.main()
