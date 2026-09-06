"""Приёмочный тест AC-3 (tasks/01M1SG9WPVN8P3S4X7975N9T69/SPEC.md,
«Критерии приёмки»).

AC-3. `tests/test_role_bash_guard.py` восстановлен в редакции коммита
80c38245 (классы `VerdictTest` — включая
`test_blocks_full_suite_forms`, `test_allows_targeted_runs_and_other_commands`,
`test_reason_names_the_rule_and_the_alternative` — и `HookProtocolTest`
с проверкой кода возврата 2/стандартного вывода ошибки и сверкой
`settings.json`); случай «пять полных прогонов подряд» в файл не
добавлен. Прогон `python3 -m unittest tests.test_role_bash_guard` —
зелёный.

Красен до реализации: `tests/test_role_bash_guard.py` снят коммитом
dea8016b — файла нет на диске, `test_ac3_file_exists` и все прочие тесты
ниже падают на импорте несуществующего модуля.

Прогон `python3 -m unittest tests.test_role_bash_guard` внутри
`test_ac3_green_run_of_the_restored_suite` — единственное место в этой
планке, где по правилу «полный набор `tests/` в шаге не запускать»
(`skills/test-authoring.md`) запускается КОНКРЕТНЫЙ модуль, а не
discovery всего дерева — это ровно форма, которую сам `bash_guard.py`
(AC-1) обязан пропускать.
"""
import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

GUARD_TEST_FILE = _REPO_ROOT / "tests" / "test_role_bash_guard.py"

# Ровно эти три метода — редакция коммита 80c38245 (см. `git show
# 80c38245:tests/test_role_bash_guard.py`). Список закрыт: требование 2/
# AC-3 SPEC явно запрещает добавлять случай «пять полных прогонов
# подряд», поэтому набор проверяется как ТОЧНОЕ множество, не подмножество.
EXPECTED_VERDICT_TEST_METHODS = {
    "test_blocks_full_suite_forms",
    "test_allows_targeted_runs_and_other_commands",
    "test_reason_names_the_rule_and_the_alternative",
}


class RestoredFileExistsTest(unittest.TestCase):

    def test_ac3_file_exists(self):
        """`tests/test_role_bash_guard.py` существует на диске.

        Ловит мутацию: восстановление хука (AC-1/AC-2) без восстановления
        его теста — файл отсутствует, `assertTrue` краснеет.
        """
        self.assertTrue(GUARD_TEST_FILE.is_file(),
                        f"файл не найден: {GUARD_TEST_FILE}")


class RestoredSuiteStructureTest(unittest.TestCase):
    """Структура восстановленного файла — сверяется через `unittest`
    loader (не текстовым grep), чтобы не зависеть от форматирования."""

    def setUp(self):
        if not GUARD_TEST_FILE.is_file():
            self.skipTest(f"файл ещё не восстановлен: {GUARD_TEST_FILE}")
        import importlib
        self.mod = importlib.import_module("tests.test_role_bash_guard")

    def test_ac3_verdict_test_class_has_exactly_the_locked_methods(self):
        """`VerdictTest` несёт РОВНО три метода редакции 80c38245 — ни
        одного лишнего (в частности, не добавлен случай «пять полных
        прогонов подряд», прямо запрещённый требованием 2/AC-3 SPEC).

        Ловит мутацию: добавление нового `test_*`-метода в `VerdictTest`
        (например, `test_repeated_full_runs_are_all_blocked`) — множество
        методов перестанет быть РАВНЫМ `EXPECTED_VERDICT_TEST_METHODS`, и
        `assertEqual` покраснеет на лишнем элементе.
        """
        cls = getattr(self.mod, "VerdictTest")
        methods = {name for name in dir(cls)
                  if name.startswith("test_") and callable(getattr(cls, name))}
        self.assertEqual(methods, EXPECTED_VERDICT_TEST_METHODS,
                         f"набор методов VerdictTest разошёлся с редакцией 80c38245: {methods}")

    def test_ac3_hook_protocol_test_class_checks_exit_code_and_settings(self):
        """`HookProtocolTest` существует и несёт проверку блокирующего
        кода возврата и сверку с `settings.json` — два признака редакции
        80c38245 (`test_blocking_exit_code_and_reason`,
        `test_reference_settings_wire_the_hook`).

        Ловит мутацию: восстановление одного класса (`VerdictTest`) без
        второго (`HookProtocolTest`) — `hasattr`/`getattr` ниже падают
        `AttributeError`/`AssertionError`.
        """
        cls = getattr(self.mod, "HookProtocolTest")
        methods = {name for name in dir(cls) if name.startswith("test_")}
        self.assertIn("test_blocking_exit_code_and_reason", methods)
        self.assertIn("test_reference_settings_wire_the_hook", methods)


class RestoredSuiteGreenRunTest(unittest.TestCase):

    def test_ac3_green_run_of_the_restored_suite(self):
        """`python3 -m unittest tests.test_role_bash_guard` завершается
        кодом 0 (все тесты внутри зелёные) — буквальное условие AC-3.

        Ловит мутацию: восстановленный файл, который не проходит на
        восстановленном же хуке (например, рассинхронизация редакций
        хука и его теста) — `returncode` ниже отличен от 0.
        """
        if not GUARD_TEST_FILE.is_file():
            self.skipTest(f"файл ещё не восстановлен: {GUARD_TEST_FILE}")
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "tests.test_role_bash_guard"],
            cwd=str(_REPO_ROOT), capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0,
                         f"прогон не зелёный:\nstdout={result.stdout}\nstderr={result.stderr}")


if __name__ == "__main__":
    unittest.main()
