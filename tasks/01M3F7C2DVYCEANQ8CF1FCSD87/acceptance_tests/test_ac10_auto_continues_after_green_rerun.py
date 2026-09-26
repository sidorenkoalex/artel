"""AC-10: после зелёного повтора опрос `verifying` продолжается штатно.

Красен до реализации: команды `ci-rerun` в пульте нет вовсе — `resolve_command`
не находит обработчика ни в таблице команд `orchestrator/artel.py`, ни по
очевидным адресам, и `run_ci_rerun` валит тест этим сообщением.

Опрос статуса цикла `auto` в `verifying` — это ровно вызов `fsm.cmd_advance`
(`orchestrator/auto.py::_advance_verifying_poll`, строка `fsm.cmd_advance(
task_id, session_id=session_id)`), поэтому «цикл читает новый статус»
проверяется этим вызовом, а не входом в сам `cmd_auto`: тело цикла за
границей опроса ушло бы в состояние `review` с агентской ролью, то есть в
запуск агента, которого критерий не касается вовсе.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import fsm  # noqa: E402
from _sandbox import BRANCH_GREEN, REASON, CiRerunSandbox  # noqa: E402


class AutoContinuesAfterGreenRerunTest(CiRerunSandbox):

    def test_ac10_green_rerun_leaves_state_to_the_cycle(self):
        """Зелёный повтор: состояние двигает опрос цикла, не команда.

        Повтор завершается зелёным CI. Сама команда обязана оставить задачу
        в `verifying` (ни перехода, ни записи о нём), а следующий опрос
        статуса — прочитать НОВЫЙ статус и увести задачу дальше штатным
        маршрутом `verifying -> review`, как это делает `fsm_advance.
        verifying` на зелёном исходе.

        Ловит мутацию: команда, увидев зелёный повтор, двигает задачу сама
        (`store.set_state` внутри `ci-rerun`) — тогда после её вызова
        состояние уже не `verifying`, а запись о переходе появляется в
        журнале команды, и единственная точка движения автомата
        (`fsm.cmd_advance`) перестаёт быть единственной.
        """
        self.enter_verifying_red()
        self.branch_check_runs_after_rerun = BRANCH_GREEN
        before_command = self.last_step_id()

        self.run_ci_rerun(REASON)

        self.assertEqual(
            self.state(), "verifying",
            "сама команда ci-rerun состояния задачи не меняет")
        self.assertEqual(
            self.state_transitions_since(before_command), [],
            "запись о переходе состояния командой не пишется")

        before_poll = self.last_step_id()
        self.capture(lambda: fsm.cmd_advance(self.TASK))
        poll_records = self.journal_since(before_poll)

        self.assertEqual(
            self.state(), "review",
            f"опрос обязан прочитать НОВЫЙ (зелёный) статус CI и увести "
            f"задачу из verifying штатно; записи опроса: {poll_records}")
        self.assertTrue(
            any(fsm.VERIFYING_STATUS_ACTION in record
                for record in poll_records),
            f"опрос обязан записать прочитанный статус CI; записи: "
            f"{poll_records}")


if __name__ == "__main__":
    unittest.main()
