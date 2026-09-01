"""AC-3 (tasks/T085/SPEC.md): `budget.check_program_spend` при
пересечении порога из `config.PROGRAM_ALERT_RATIOS` по-прежнему пишет
событие в журнал задачи и заводит алерт `kind=threshold` через
`alerts.raise_alert`.

Зелёный с рождения: SPEC требование 2 прямо запрещает трогать этот путь
(«событие журнала задачи и алерт `kind=threshold`... сохраняются как
есть») — `orchestrator/budget.py::check_program_spend` уже журналирует
и заводит алерт сегодня, до и независимо от удаления условия A1 из
автогейта acceptance (AC-1: другой модуль, `orchestrator/fsm.py`).
Порог читается из `config.PROGRAM_ALERT_RATIOS`/`config.
PROGRAM_STOP_LOSS_USD` (крутилки Оператора), не литералом — урок T062
28.08 (скил test-authoring).
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import alerts, budget, config, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


class CheckProgramSpendJournalsAndAlertsTest(TmpRootTest):

    TASK = "T001"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Пороги программы",
                          "in_dev", "task/t001", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def cross_first_threshold(self) -> float:
        """Расход, пересекающий самый мягкий из настроенных порогов."""
        ratio = min(config.PROGRAM_ALERT_RATIOS)
        before = config.PROGRAM_STOP_LOSS_USD * ratio - 1.0
        store.update_task(self.conn, self.TASK, spent_usd=before)
        step_usd = 2.0
        store.update_task(self.conn, self.TASK,
                          spent_usd=before + step_usd)
        return step_usd

    def test_ac3_crossing_a_threshold_journals_an_event(self):
        step_usd = self.cross_first_threshold()

        capture(budget.check_program_spend, self.conn, self.TASK,
               {"usd": step_usd, "tokens": None})

        rows = [r["detail"] for r in store.task_steps(self.conn, self.TASK)
               if r["action"] == "программа: порог расхода"]
        self.assertEqual(
            len(rows), 1,
            "AC-3: пересечение порога обязано журналировать событие в "
            "задаче")

    def test_ac3_crossing_a_threshold_raises_a_threshold_alert(self):
        step_usd = self.cross_first_threshold()

        capture(budget.check_program_spend, self.conn, self.TASK,
               {"usd": step_usd, "tokens": None})

        thresholds = alerts.open_alerts(self.conn, "threshold")
        self.assertEqual(
            len(thresholds), 1,
            "AC-3: пересечение порога обязано завести alerts kind=threshold "
            f"через alerts.raise_alert; открытые alerts: {thresholds}")
        self.assertEqual(thresholds[0]["kind"], "threshold")


if __name__ == "__main__":
    unittest.main()
