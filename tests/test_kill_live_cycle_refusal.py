"""Юнит-тесты `cleanup._live_cycle_holder` и разбора `--yes` диспетчером
`kill` (SPEC 01M28NX0M2WTVC38XVN75N01XD, требования 1-3).

Сквозной путь (весь CLI, журнал, состояние/ветка/worktree) уже кроют
приёмочные тесты `tasks/01M28NX0M2WTVC38XVN75N01XD/acceptance_tests/
test_ac1_ac2_ac3_kill_confirmation.py` — здесь только чистая функция
признака «живой держатель» в изоляции (три составляющих отдельно, не
только их конъюнкция) и то, что диспетчер `artel.py` действительно
доносит флаг `--yes` до `cleanup.cmd_kill` как `confirmed=True`, не
трогая `tests/test_kill_cleanup.py`/`tests/test_detached_cycle.py`
(требование 6, AC-7 — только новый файл).
"""
import os
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artel, cleanup, config, store  # noqa: E402
from tests.sandbox import _dead_pid, _ts_ago  # noqa: E402
from tests.test_kill_cleanup import TmpRepoTest  # noqa: E402


def _row(**fields) -> dict:
    base = {"task_id": "T001", "session_id": "s", "pid": os.getpid(),
            "hostname": socket.gethostname(), "heartbeat_ts": store.now(),
            "pgid": None}
    base.update(fields)
    return base


class LiveCycleHolderTest(unittest.TestCase):
    """Три признака проверяются отдельно, не только их конъюнкция —
    ловит мутацию, что любой из них перестал влиять на результат."""

    def test_none_row_is_not_live(self):
        self.assertFalse(cleanup._live_cycle_holder(None))

    def test_foreign_host_is_not_live(self):
        row = _row(hostname="какой-то-другой-host")
        self.assertFalse(cleanup._live_cycle_holder(row))

    def test_dead_pid_on_this_host_is_not_live(self):
        row = _row(pid=_dead_pid())
        self.assertFalse(cleanup._live_cycle_holder(row))

    def test_stale_heartbeat_on_this_host_with_alive_pid_is_not_live(self):
        row = _row(heartbeat_ts=_ts_ago(config.LEASE_STALE_AFTER_SEC + 1))
        self.assertFalse(cleanup._live_cycle_holder(row))

    def test_same_host_alive_pid_fresh_heartbeat_is_live(self):
        row = _row()
        self.assertTrue(cleanup._live_cycle_holder(row))


class LiveCycleRoleTest(TmpRepoTest):
    """`_live_cycle_role` — вторая половина требования 1: живой lease без
    активной агентской роли на текущем состоянии (`spec_writing` без
    `TZ.md`, прежний флоу «SPEC пишет Оператор») не считается «циклом» —
    именно это разграничение и защищает `tests/test_detached_cycle.py::
    KillSignalsDetachedHolderTest` (синтетический lease на голом
    `spec_writing`, byte-в-byte прежнее поведение AC-10 SPEC
    01M1NWCHVTYQ0M8PCJ1YJ2N78P — требование 6/AC-7 этой задачи)."""

    def _seed_live_lease(self) -> None:
        store.insert_lease(store.db(), self.TASK, "cycle-session",
                           os.getpid(), socket.gethostname(), store.now())

    def test_no_role_on_the_current_state_is_not_a_live_cycle(self):
        self._seed_live_lease()
        row = store.lease_row(store.db(), self.TASK)

        self.assertIsNone(
            cleanup._live_cycle_role(store.db(), self.TASK, row))

    def test_a_role_bearing_state_with_a_live_lease_is_a_live_cycle(self):
        self._seed_live_lease()
        conn = store.db()
        store.set_state(conn, self.TASK, "in_dev", "operator",
                        expected_state=self.task_row()["state"],
                        detail="тест")
        row = store.lease_row(conn, self.TASK)

        self.assertEqual(cleanup._live_cycle_role(conn, self.TASK, row),
                         "developer")


class KillDispatchYesFlagTest(TmpRepoTest):
    """Диспетчер `"kill"` в `artel.main` — `--yes` доходит до
    `cleanup.cmd_kill` как `confirmed=True`, без флага — `False`.
    `TmpRepoTest` (не голый `unittest.TestCase`) — `artel.main` первым
    делом отказывает вне главной копии репозитория (`_refuse_if_
    worktree`, инвариант T056); песочница патчит `config.ROOT` на
    свежий `git init`, у которого `.git` — каталог, не worktree-ссылка,
    так что этот отказ не срабатывает."""

    def _dispatch(self, *flags: str) -> None:
        with mock.patch.object(sys, "argv",
                               ["artel.py", "kill", self.TASK, *flags]):
            artel.main()

    def test_yes_flag_reaches_cmd_kill_as_confirmed_true(self):
        with mock.patch.object(cleanup, "cmd_kill") as kill:
            self._dispatch("--yes")

        kill.assert_called_once_with(self.TASK, confirmed=True)

    def test_missing_flag_reaches_cmd_kill_as_confirmed_false(self):
        with mock.patch.object(cleanup, "cmd_kill") as kill:
            self._dispatch()

        kill.assert_called_once_with(self.TASK, confirmed=False)


if __name__ == "__main__":
    unittest.main()
