"""Приёмочные тесты 01M1THKRK8HPXA7Y2SRB0RFTN2 — AC-2 (SPEC.md).

Зелёный с рождения: `approve`/`reject`/`budget`/`status` СЕЙЧАС не
проверяют алерты `kind=incident` вовсе — этот файл фиксирует, что так и
должно остаться, когда требование 1 добавит проверку стоп-крана в
`run`/`auto` (не в эти четыре команды). Не тавтология: каждый тест
реально ведёт задачу через настоящий переход/эффект команды (approve
меняет state, reject возвращает в in_dev, budget поднимает потолок,
status печатает строку задачи) при ОТКРЫТОМ алерте — мутация,
по ошибке подмешавшая проверку алерта стоп-крана в любую из этих
четырёх команд, эти тесты покраснит.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import RunPipelineSandbox, raise_stop_crane_alert  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import budget, catalog, fsm, store  # noqa: E402


class Ac2ApproveRejectBudgetStatusUnaffectedTest(RunPipelineSandbox):
    """AC-2: `approve`, `reject`, `budget`, `status` работают на задачах
    target self как обычно независимо от открытого алерта стоп-крана."""

    def test_ac2_approve_still_returns_task_from_escalated(self):
        """`approve` задачи, эскалированной без вопроса Оператору
        (`answer_baseline is None`), как обычно возвращает её в `in_dev`,
        даже когда по target self открыт алерт стоп-крана.

        Ловит мутацию: если `approve` начнёт отказывать при открытом
        алерте (перепутанная зона проверки требования 1), состояние
        задачи останется `escalated`, а не перейдёт в `in_dev`.
        """
        self.set_state("escalated", escalated_from=None, answer_baseline=None)
        raise_stop_crane_alert(store.db())

        fsm.cmd_approve(self.TASK, session_id="session-approve")

        self.assertEqual(self.state(), "in_dev")

    def test_ac2_reject_still_returns_task_from_merge_gate(self):
        """`reject` из `merge_gate` как обычно возвращает задачу в
        `in_dev`, даже когда по target self открыт алерт стоп-крана.

        Ловит мутацию: если `reject` начнёт отказывать при открытом
        алерте, состояние задачи останется `merge_gate`.
        """
        self.set_state("merge_gate")
        raise_stop_crane_alert(store.db())

        fsm.cmd_reject(self.TASK, "конфликт с main, перебазируй ветку",
                       session_id="session-reject")

        self.assertEqual(self.state(), "in_dev")

    def test_ac2_budget_still_raises_the_ceiling(self):
        """`budget` как обычно поднимает потолок задачи, даже когда по
        target self открыт алерт стоп-крана.

        Ловит мутацию: если `budget` начнёт отказывать при открытом
        алерте, потолок задачи останется прежним.
        """
        raise_stop_crane_alert(store.db())

        budget.cmd_budget(self.TASK, "77", session_id="session-budget")

        self.assertEqual(self.task_row()["budget_usd"], 77.0)

    def test_ac2_status_still_lists_the_task(self):
        """`status` как обычно печатает строку задачи (не отказывает и не
        падает), даже когда по target self открыт алерт стоп-крана.

        Ловит мутацию: если `status` начнёт поднимать исключение или
        пропускать задачи target self при открытом алерте, строка задачи
        пропадёт из вывода.
        """
        raise_stop_crane_alert(store.db())

        out = self.capture(catalog.cmd_status)

        self.assertIn(self.TASK, out)


if __name__ == "__main__":
    import unittest
    unittest.main()
