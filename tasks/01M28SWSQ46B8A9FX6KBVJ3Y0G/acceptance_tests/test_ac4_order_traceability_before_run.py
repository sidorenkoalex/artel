"""Приёмочный тест AC-4 задачи 01M28SWSQ46B8A9FX6KBVJ3Y0G: порядок
проверок в `_cmd_amend_tests` — сначала трассируемость (`guard.
acceptance_traceability_errors`), потом прогон планки (`acceptance.run`);
отказ трассируемости обязан остановить команду ДО прогона, не просто
где-то до коммита.

Красен до реализации: `_cmd_amend_tests` (orchestrator/amend.py) сегодня
вызывает только `acceptance.run(tdir)` — на правке, снимающей тест
AC-1 без пометки, `acceptance.run` РЕАЛЬНО вызывается (планка с
пустым/сокращённым набором тестов исполняется прогоном) прежде, чем
команда вообще доходит до какой-либо проверки трассируемости, которой
сегодня нет вовсе — мок ниже фиксирует вызов, тест падает.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AC_TEST_MISSING_AC1_NO_MARKER, WorktreeGateSandbox, amend  # noqa: E402

# AC-9: ci - существующие тесты tests/test_amend.py остаются зелёными без
# правки их утверждений; CI кодовой ветки гоняет их отдельно от этой планки.


class TraceabilityBeforeRunOrderTest(WorktreeGateSandbox):

    def test_ac4_traceability_failure_short_circuits_before_acceptance_run(self):
        """Правка worktree ломает трассируемость (тест AC-1 снят без
        пометки) — `_cmd_amend_tests` отказывает ДО вызова `acceptance.
        run`: мок `acceptance.run` не вызывается ни разу за время
        отказавшего вызова.

        Ловит мутацию: порядок перевёрнут (прогон планки идёт первым,
        проверка трассируемости — только если прогон зелёный) — на
        сломанной трассируемости, но случайно зелёном прогоне (пустой
        класс TestCase без тестов — валидный `unittest`-модуль),
        `acceptance.run` успевает исполниться прежде отказа.
        """
        self.edit_tests(AC_TEST_MISSING_AC1_NO_MARKER)

        with mock.patch.object(amend.acceptance, "run",
                               return_value=(True, "0 passed in 0.00s")) as run_mock:
            with self.assertRaises(SystemExit):
                amend.cmd_amend_tests(self.TASK, "правка ломает AC-1")
            run_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
