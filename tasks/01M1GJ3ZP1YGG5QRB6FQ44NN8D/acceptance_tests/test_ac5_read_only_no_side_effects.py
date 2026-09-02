"""AC-5 (tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D/SPEC.md): «Команда не
запускает unittest, не пишет строк в журнал задачи и БД, не меняет
состояние (status) задачи, не берёт lease задачи.»

`subprocess.run`/`subprocess.Popen` патчатся ПРОЗРАЧНО (записывают вызов
и передают его настоящей реализации), а не заглушкой, которая отвечает
без исполнения: команде нужен настоящий git (branch-корректное чтение —
предмет AC-7 той же задачи), подменять весь subprocess целиком нельзя,
иначе тест перестаёт проверять то, что реально исполнилось.

Фикстурный метод ниже не назван `test_ac<n>_...` намеренно (та же
осторожность, что `tasks/T081/acceptance_tests/test_ac1_non_test_files_
excluded.py`): критерию AC-5 не важно, как назван метод фикстуры,
важно лишь его наличие — а `test_ac1_...` литералом в исходнике ЭТОГО
файла читался бы `guard.scan_acceptance_tests` как настоящее покрытие
задачи 01M1GJ3ZP1YGG5QRB6FQ44NN8D (класс дефекта ANSWER-1, 31.08).

Красен до реализации: `_sandbox.discover_dry_run_command_name()` падает
`AssertionError` — новой команды в таблице диспетчера ещё нет.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import store  # noqa: E402

from _sandbox import DryRunSandbox  # noqa: E402

TEST_FILE = '''"""Фикстура.

Зелёный с рождения: файл-фикстура другой задачи, не код 01M1GJ3ZP1YGG5QRB6FQ44NN8D.
"""
import unittest


class FixtureTest(unittest.TestCase):

    def test_ordinary_method(self):
        """Фикстура."""
        pass
'''

AC_SECTION = "AC-1. Критерий фикстуры.\n"


class _RecordingRun:
    """Оборачивает настоящий `subprocess.run`: вызов исполняется как
    обычно, но его argv запоминается — нужно и то, и другое одновременно
    (см. докстринг модуля)."""

    def __init__(self, real):
        self._real = real
        self.calls: list = []

    def __call__(self, args, *a, **kw):
        self.calls.append(list(args) if not isinstance(args, str) else [args])
        return self._real(args, *a, **kw)


class ReadOnlyNoSideEffectsTest(DryRunSandbox):

    def test_ac5_no_unittest_run_no_db_journal_state_or_lease_writes(self):
        """Задача существует в БД в состоянии `in_dev`, без lease; сухой
        прогон вызывается на ней. После вызова: ни один subprocess-вызов
        не содержит `unittest`, число записей журнала не выросло,
        состояние задачи не изменилось, строки lease по-прежнему нет.

        Ловит мутацию: реализация вызывает `orchestrator.acceptance.run`
        (или напрямую `subprocess.run(["python3", "-m", "unittest", ...])`)
        вместо статического разбора — тест ловит подстроку "unittest"
        среди аргументов ЛЮБОГО подпроцесса, запущенного за время вызова,
        и падает, если она там появилась. Отдельно ловит мутацию «команда
        журналирует свой вызов» (`store.journal(...)`) и «команда меняет
        status на что-то техническое» — оба варианта детектируются
        сравнением снимков БД до/после.
        """
        self.commit_fixture(AC_SECTION, {"test_x.py": TEST_FILE})
        self.seed_task(state="in_dev")

        steps_before = store.task_steps(store.db(), self.TASK)
        state_before = dict(store.get_task(store.db(), self.TASK))
        lease_before = store.lease_row(store.db(), self.TASK)
        self.assertIsNone(lease_before, "подготовка сценария несёт lease")

        recorder = _RecordingRun(subprocess.run)
        with mock.patch("subprocess.run", recorder):
            self.run_dry_run()

        unittest_calls = [c for c in recorder.calls
                          if any("unittest" in str(part) for part in c)]
        self.assertEqual(
            unittest_calls, [],
            f"команда вызвала unittest через subprocess: {unittest_calls}")

        steps_after = store.task_steps(store.db(), self.TASK)
        self.assertEqual(len(steps_after), len(steps_before),
                         "команда дописала строки в журнал задачи")

        state_after = dict(store.get_task(store.db(), self.TASK))
        self.assertEqual(state_before["state"], state_after["state"],
                         "команда изменила status задачи")

        lease_after = store.lease_row(store.db(), self.TASK)
        self.assertIsNone(lease_after, "команда взяла lease задачи")


if __name__ == "__main__":
    unittest.main()
