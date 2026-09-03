"""AC-9 (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md): «Превышение порога —
больше одной правки «планки» в скользящем окне последних 5 задач пульта,
дошедших до фиксации лока (вышедших из tests_writing), program-wide по
всем target, упорядоченных по task_number (при менее чем 5 таких задачах
всего — окно составляют все они) — поднимает алерт «планка девальвируется»
существующим механизмом alerts сразу после записи нового события правки
текущей задачи.»

В свежей песочнице единственная локнутая задача программы — это она сама
(<5 задач всего, ANSWER-1: «задач меньше 5 — берётся всё, что есть») —
сценарий прицельно бьёт по грани «>1» без необходимости заводить пять
отдельных задач-фикстур и без предположений о конкретном способе
упорядочивания по task_number (см. `_sandbox.py`, докстринг): при одной
задаче в окне порядок не имеет значения.

Красен до реализации: `_sandbox.discover_amend_command_name()` падает
`AssertionError` — новой команды правки планки в таблице диспетчера ещё
нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import store  # noqa: E402

from _sandbox import (AC_TEST_AMENDED_V1, AC_TEST_AMENDED_V2,  # noqa: E402
                      AmendSandbox)

ALERT_PHRASE = "планка девальвируется"


class ThresholdAlertTest(AmendSandbox):

    def _open_devaluation_alerts(self):
        conn = store.db()
        return [a for a in store.open_alerts(conn, kind="threshold")
               if ALERT_PHRASE in a["message"]]

    def test_ac9_second_amend_within_window_raises_devaluation_alert(self):
        """Одна и та же задача (единственная локнутая задача программы,
        окно < 5 составляют все они) правится дважды подряд — после
        ПЕРВОЙ правки алерта «планка девальвируется» быть не должно (порог
        — БОЛЬШЕ одной правки), после ВТОРОЙ — алерт обязан появиться
        (kind=threshold) сразу же, без ожидания внешнего прогона doctor.

        Ловит мутацию: порог сравнивается через `>= 1` вместо `> 1`
        (алерт после первой же правки — false positive) или вовсе не
        поднимается через `alerts.raise_alert`/`kind="threshold"` (алерта
        нет и после второй).
        """
        self.enter_in_dev()

        self.write_acceptance_tests(AC_TEST_AMENDED_V1)
        self.run_amend(reason="первая правка окна")
        self.assertFalse(
            self._open_devaluation_alerts(),
            "алерт «планка девальвируется» не должен подниматься после "
            "ОДНОЙ правки в окне — порог «больше одной»")

        self.write_acceptance_tests(AC_TEST_AMENDED_V2)
        self.run_amend(reason="вторая правка окна")
        alerts_now = self._open_devaluation_alerts()
        self.assertTrue(
            alerts_now,
            "алерт «планка девальвируется» обязан подняться сразу после "
            "второй правки той же задачи в окне")
        self.assertEqual(alerts_now[0]["kind"], "threshold")


if __name__ == "__main__":
    unittest.main()
