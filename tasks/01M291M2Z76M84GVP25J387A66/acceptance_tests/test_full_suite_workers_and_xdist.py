"""Приёмочные тесты 01M291M2Z76M84GVP25J387A66 — AC-1, AC-2, AC-7
(параллель `acceptance.run_full_suite` через pytest-xdist).

AC-7(в) («существующие тесты acceptance/автогейта остаются зелёными без
правки утверждений») здесь отдельным тестом/пометкой не заводится —
тот же класс критерия, что уже встречался дословно (tasks/T053/
acceptance_tests/test_ac7_full_suite_regression.py, tasks/
01M1SAA2AZX3ERQ779QJ5TS9J4/acceptance_tests/test_ac9_full_suite_green.py):
`tests/test_acceptance.py` — часть каталога `tests/`, и его зелёность УЖЕ
обязательное условие ЛЮБОГО автогейта acceptance для ЭТОЙ ЖЕ задачи
(`orchestrator/fsm_autogate.py` -> `acceptance.run_full_suite`, ADR-0007,
SPEC T066) — дублирующий здесь прогон не даёт нового сигнала. AC-7
считается покрытым тестами `test_ac7_...` ниже (части «а»/«б»).

Красен до реализации: `RunFullSuiteUsesWorkersAndXdistTest` —
`orchestrator/acceptance.py::run_full_suite` сегодня не добавляет `-n`/
`-p xdist` в команду pytest (grep по `orchestrator/acceptance.py` на
«xdist» пуст) — `assertIn("-n", command)` падает первым же тестом.

Красен до реализации: `FullSuiteWorkersDefaultTest` — `orchestrator.config`
сегодня не несёт атрибут `FULL_SUITE_WORKERS` (grep по
`orchestrator/config.py` на «FULL_SUITE_WORKERS» пуст) — `hasattr`
падает.

Красен до реализации: `DeveloperSuiteCoversWorkersAndXdistTest` —
`test_ac7_main_suite_has_a_test_covering_workers_and_xdist_flag` падает,
потому что ни `tests/test_acceptance.py`, ни `tests/test_fsm_autogate.py`
(единственные файлы `tests/`, упоминающие `run_full_suite` сегодня) не
несут ни слова «FULL_SUITE_WORKERS», ни слова «xdist»; следующий метод
падает `AttributeError`, потому что `mock.patch.object(config,
"FULL_SUITE_WORKERS", 1)` без `create=True` требует существующего
атрибута — сегодня его нет.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import acceptance, config  # noqa: E402


def _full_suite_command_p_values(command):
    return [command[i + 1] for i, token in enumerate(command)
            if token == "-p" and i + 1 < len(command)]


class RunFullSuiteUsesWorkersAndXdistTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "tests").mkdir()

    def test_ac1_command_carries_worker_count_and_explicit_xdist_plugin(self):
        """Разбираем реально переданную `subprocess.run` команду
        `run_full_suite`: требование 1 SPEC обязывает её нести
        `-n <config.FULL_SUITE_WORKERS>` и явную загрузку `-p xdist`
        (тем же приёмом, что уже несёт `-p timeout` в `_pytest_command`).

        Ловит мутацию: параллель не добавлена в команду `run_full_suite`
        (`-n`/`-p xdist` отсутствуют) — полный набор снова гонится
        последовательно без предупреждения.
        """
        with mock.patch.object(acceptance.stack, "pytest_python_executable",
                               return_value="python3"), \
             mock.patch.object(acceptance.subprocess, "run") as run_:
            run_.return_value = subprocess.CompletedProcess([], 0, "3 passed", "")
            acceptance.run_full_suite(self.root)

        command = run_.call_args.args[0]
        self.assertIn("-n", command, f"команда без -n: {command}")
        n_pos = command.index("-n")
        self.assertEqual(
            command[n_pos + 1], str(config.FULL_SUITE_WORKERS),
            f"-n несёт не значение config.FULL_SUITE_WORKERS: {command}")
        self.assertIn(
            "xdist", _full_suite_command_p_values(command),
            f"нет явной загрузки -p xdist в команде: {command}")


class FullSuiteWorkersDefaultTest(unittest.TestCase):

    def test_ac2_default_value_is_auto(self):
        """`config.FULL_SUITE_WORKERS` — новая константа, значение по
        умолчанию `"auto"` (строка либо целое, передаётся в `-n` как
        есть — число рабочих по числу ядер).

        Ловит мутацию: дефолт зашит конкретным числом (например, `4`)
        вместо `"auto"` — параллель перестаёт автоматически
        масштабироваться по числу ядер машины по умолчанию.
        """
        self.assertTrue(
            hasattr(config, "FULL_SUITE_WORKERS"),
            "orchestrator.config не несёт FULL_SUITE_WORKERS (AC-2)")
        self.assertEqual(config.FULL_SUITE_WORKERS, "auto")


class DeveloperSuiteCoversWorkersAndXdistTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "tests").mkdir()

    @staticmethod
    def _files_mentioning_run_full_suite():
        tests_root = Path(config.ROOT) / "tests"
        return [p for p in sorted(tests_root.glob("test_*.py"))
                if "run_full_suite" in p.read_text(encoding="utf-8")]

    def test_ac7_main_suite_has_a_test_covering_workers_and_xdist_flag(self):
        """AC-7(а): основной набор `tests/` (`test_acceptance_full_suite.py`
        либо существующий файл, несущий тесты `run_full_suite`) явно
        покрывает и число воркеров (`FULL_SUITE_WORKERS`), и явную
        загрузку плагина `xdist` — не только планка этой задачи в
        `tasks/<id>/acceptance_tests/`.

        Ловит мутацию: разработчик добавляет `-n`/`-p xdist` в
        `run_full_suite`, но не заводит по этому свойству тест в
        основном наборе `tests/` — после мержа регрессию (например,
        случайное удаление `-n` при рефакторинге) больше никто не ловит.
        """
        candidates = self._files_mentioning_run_full_suite()
        self.assertTrue(
            candidates, "нет файла в tests/, несущего тесты run_full_suite")
        covered = [p for p in candidates
                  if "FULL_SUITE_WORKERS" in p.read_text(encoding="utf-8")
                  and "xdist" in p.read_text(encoding="utf-8")]
        self.assertTrue(
            covered,
            "ни один файл tests/, несущий run_full_suite, не упоминает "
            f"одновременно FULL_SUITE_WORKERS и xdist: "
            f"{[str(p) for p in candidates]}")

    def test_ac7_full_suite_workers_set_to_one_is_still_a_valid_command(self):
        """AC-7(б): при `config.FULL_SUITE_WORKERS = 1` команда
        `run_full_suite` остаётся валидной — `-n 1`, не пустая или
        сломанная строка.

        Ловит мутацию: код формирует `-n` только для нечислового/"auto"
        значения (например, `if workers != 1: args += ["-n", workers]`)
        — при явной единице параллель тихо выключается вместо валидной
        команды `-n 1`.
        """
        with mock.patch.object(config, "FULL_SUITE_WORKERS", 1), \
             mock.patch.object(acceptance.stack, "pytest_python_executable",
                               return_value="python3"), \
             mock.patch.object(acceptance.subprocess, "run") as run_:
            run_.return_value = subprocess.CompletedProcess([], 0, "3 passed", "")
            green, _ = acceptance.run_full_suite(self.root)

        command = run_.call_args.args[0]
        self.assertIn("-n", command, f"команда без -n при FULL_SUITE_WORKERS=1: {command}")
        n_pos = command.index("-n")
        self.assertEqual(command[n_pos + 1], "1", f"-n не несёт '1': {command}")
        self.assertTrue(green)


if __name__ == "__main__":
    unittest.main()
