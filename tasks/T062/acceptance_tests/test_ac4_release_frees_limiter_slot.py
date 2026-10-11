"""Приёмочные тесты T062 — AC-4 (SPEC.md).

AC-4: после `release` чужой задачи, державшей слот лимитера
`MAX_PARALLEL_TASKS`, запуск (`run`/`auto`) своей задачи, которая до
этого отказывала по инварианту 32 из-за занятых слотов, проходит.

Нужна тяжёлая песочница `tests.test_invariants.FsmTest` (git/агент
заглушены, `FakeProc`) — в отличие от AC-1/2/3/5 (см.
`test_ac1_ac2_ac3_ac5_release_command.py`), здесь критерий явно требует
реального прогона `run`/`auto` до и после `release`, а не только
состояния таблицы `leases`. Песочница и приём заведения «других занятых
задач» напрямую в БД — тот же, что и
`tasks/T060/acceptance_tests/test_max_parallel_tasks.py::LimiterSandbox`
(лимитер читает только `store.all_leases`, полноценный FSM-цикл фиктивным
занятым задачам не нужен).

Допущение интерфейса — то же, что в соседнем файле: `orchestrator/
release.py::cmd_release(task_id: str) -> None`.
"""
import io
import os
import socket
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import auto, config, release, runner, store  # noqa: E402
from tests.test_invariants import FakeProc, FsmTest  # noqa: E402


def _invoke(call) -> str:
    """Стдаут вызова + текст SystemExit (если он был) — отказ лимитера мог
    уйти любым из двух путей, для теста это один и тот же наблюдаемый
    текст (тот же приём, что tasks/T060/acceptance_tests/
    test_max_parallel_tasks.py)."""
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            call()
    except SystemExit as exc:
        return buf.getvalue() + str(exc)
    return buf.getvalue()


class Ac4Sandbox(FsmTest):
    """`FsmTest` (T001, git/агент заглушены) + прямые операции над
    `leases`/`tasks` для симуляции ДРУГИХ занятых задач."""

    CALLER_SESSION = "session-caller"

    def seed_busy_task(self, task_id: str, session_id: str, pid: int,
                       hostname: str, heartbeat_ts: str) -> None:
        store.insert_task(store.db(), task_id, f"Другая задача {task_id}",
                          "in_dev", f"task/{task_id.lower()}-fake",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (task_id, session_id, pid, hostname, heartbeat_ts))
        conn.commit()

    def reset_task(self) -> None:
        self.set_state("in_dev", budget_usd=config.DEFAULT_BUDGET_USD,
                       spent_usd=0.0, escalated_from=None)
        conn = store.db()
        conn.execute("DELETE FROM leases")
        conn.execute("DELETE FROM tasks WHERE id != ?", (self.TASK,))
        conn.commit()

    def run_with_fake_agent(self, call) -> tuple[str, mock.Mock]:
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            out = _invoke(call)
        return out, popen


class Ac4ReleaseFreesLimiterSlotForRunTest(Ac4Sandbox):
    """AC-4 через `run`: две другие задачи держат слоты лимитера (потолок
    достигнут) -> `run` своей задачи отказывает -> `release` одной из
    занятых задач -> тот же `run` проходит."""

    # Динамика от config (правка Оператора 28.08 по эскалации PLAN:
    # зашитая двойка сломалась при подъёме потолка 2 -> 5 подтяжкой) —
    # держателей сеется ровно столько, каков текущий потолок.
    @property
    def HOLDERS(self):
        return tuple((f"T9{i:02d}", f"session-busy-{i}")
                     for i in range(1, config.MAX_PARALLEL_TASKS + 1))

    def _seed_holders_at_cap(self) -> None:
        self.assertEqual(
            len(self.HOLDERS), config.MAX_PARALLEL_TASKS,
            "фикстура должна давать ровно config.MAX_PARALLEL_TASKS "
            "занятых других задач, чтобы run своей задачи отказал")
        for task_id, session_id in self.HOLDERS:
            self.seed_busy_task(task_id, session_id, os.getpid(),
                               socket.gethostname(), store.now())

    def test_ac4_run_passes_after_releasing_one_busy_task(self):
        self.reset_task()
        self._seed_holders_at_cap()

        out_before, popen_before = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))
        # предусловие критерия: "которая до этого отказывала"
        popen_before.assert_not_called()

        released_task_id = self.HOLDERS[0][0]
        release.cmd_release(released_task_id)

        out_after, popen_after = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))
        self.assertTrue(
            popen_after.called,
            f"run не прошёл после release чужой занятой задачи "
            f"{released_task_id}: {out_after!r}")


class Ac4ReleaseFreesLimiterSlotForAutoTest(Ac4Sandbox):
    """AC-4 через `auto`: тот же сценарий, но запуск — `auto`."""

    # Динамика от config — см. комментарий у Run-класса выше.
    @property
    def HOLDERS(self):
        return tuple((f"T9{i:02d}", f"session-busy-{i}")
                     for i in range(51, 51 + config.MAX_PARALLEL_TASKS))

    def _seed_holders_at_cap(self) -> None:
        self.assertEqual(
            len(self.HOLDERS), config.MAX_PARALLEL_TASKS,
            "фикстура должна давать ровно config.MAX_PARALLEL_TASKS "
            "занятых других задач, чтобы auto своей задачи отказал")
        for task_id, session_id in self.HOLDERS:
            self.seed_busy_task(task_id, session_id, os.getpid(),
                               socket.gethostname(), store.now())

    def test_ac4_auto_passes_after_releasing_one_busy_task(self):
        self.reset_task()
        self._seed_holders_at_cap()

        out_before, popen_before = self.run_with_fake_agent(
            lambda: auto.cmd_auto(self.TASK, session_id=self.CALLER_SESSION))
        popen_before.assert_not_called()

        released_task_id = self.HOLDERS[0][0]
        release.cmd_release(released_task_id)

        out_after, popen_after = self.run_with_fake_agent(
            lambda: auto.cmd_auto(self.TASK, session_id=self.CALLER_SESSION))
        self.assertTrue(
            popen_after.called,
            f"auto не прошёл после release чужой занятой задачи "
            f"{released_task_id}: {out_after!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
