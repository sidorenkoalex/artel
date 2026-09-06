"""Юнит-тесты потолка ожидания CI в `verifying` по времени, не по числу
попыток `advance` (tasks/T086/SPEC.md, требования 3-4).

Дополняет приёмочные AC-5/AC-6/AC-7 (tasks/T086/acceptance_tests/) на
уровне самой ветки `orchestrator/fsm.py::_cmd_advance` — независимо от
`auto`, тем же стендом (`tests.test_invariants.FsmTest`), что и остальные
юниты FSM этого файла.
"""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import ci, config, fsm, store  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402


class VerifyingCeilingTest(FsmTest):

    def enter_verifying(self) -> None:
        self.set_state("verifying")

    def age_entry(self, ago: timedelta) -> None:
        """Отодвигает `tasks.updated_at` — симулирует момент входа в
        `verifying` `ago` назад (требование 3: потолок считается от
        `updated_at` перехода `-> verifying`). Формат — тот же, что пишет
        `store.set_state` (микросекундная точность)."""
        stamp = (datetime.now(timezone.utc) - ago).strftime(
            "%Y-%m-%d %H:%M:%S.%fZ")
        conn = store.db()
        conn.execute("UPDATE tasks SET updated_at=? WHERE id=?",
                     (stamp, self.TASK))
        conn.commit()

    def set_running_ci(self) -> None:
        """CI незавершённо идёт — не зелёный (нечего эскалировать по
        принципу «уже прошло»), не завершённо-красный (не тот стоп)."""
        patcher = mock.patch.object(
            ci, "verifying_status",
            lambda branch: (ci.VERIFYING_RUNNING,
                            "CI коммита aaaaaaaa ещё идёт: python"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_fresh_entry_does_not_escalate_regardless_of_outcome(self):
        """Только что вошли в verifying — потолок ещё не мог истечь."""
        self.enter_verifying()
        self.set_running_ci()

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "verifying")

    def test_elapsed_past_the_ceiling_escalates_with_last_known_status(self):
        """Требования 3-4: потолок истёк по времени — один advance эскалирует."""
        self.enter_verifying()
        self.age_entry(timedelta(seconds=config.VERIFYING_CEILING_SEC + 60))
        self.set_running_ci()
        since = len(store.task_steps(store.db(), self.TASK))

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "escalated")
        details = "\n".join(
            f"{r['action']} {r['detail']}"
            for r in store.task_steps(store.db(), self.TASK)[since:])
        self.assertIn("python", details,
                      "эскалация обязана нести диагностику последнего "
                      "известного статуса CI")

    def test_elapsed_just_under_the_ceiling_does_not_escalate(self):
        """Граница: секундой меньше потолка — ещё не исчерпан."""
        self.enter_verifying()
        self.age_entry(timedelta(seconds=config.VERIFYING_CEILING_SEC - 1))
        self.set_running_ci()

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "verifying")

    def test_attempt_count_alone_never_escalates_without_elapsed_time(self):
        """Требование 3/AC-7: много быстрых advance без старения — не
        эскалирует, сколько бы их ни было (здесь — больше прежних 20)."""
        self.enter_verifying()
        self.set_running_ci()

        for _ in range(26):
            self.capture(fsm.cmd_advance, self.TASK)
            self.assertEqual(self.state(), "verifying")

    def test_verifying_attempts_still_increments_as_information_only(self):
        """Требование 3: счётчик остаётся в БД, но не как условие перехода."""
        self.enter_verifying()
        self.set_running_ci()

        self.capture(fsm.cmd_advance, self.TASK)
        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.task_row()["verifying_attempts"], 2)
        self.assertEqual(self.state(), "verifying")

    def test_green_ci_moves_on_regardless_of_elapsed_time(self):
        """Зелёный CI не завязан на потолок вовсе — трогает только не-зелёные
        исходы (требование 2 не меняется). `FsmTest.setUp` уже держит CI
        зелёным по умолчанию (`GREEN_CI`) — здесь только состариваем вход.

        Целевое состояние — `review`, не `acceptance` (ADR-0015, требование
        2: переход `verifying -> review` по зелёному CI, вместо прежнего
        `verifying -> acceptance` — AC-20, правка ассерта старого порядка)."""
        self.enter_verifying()
        self.age_entry(timedelta(seconds=config.VERIFYING_CEILING_SEC + 60))

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "review")


if __name__ == "__main__":
    unittest.main()
