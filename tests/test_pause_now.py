"""Юнит-тесты `orchestrator.pause.cmd_pause_now` (SPEC T074).

Приёмочные тесты (tasks/T074/acceptance_tests) кроют AC-1..AC-15 сквозным
путём через реальный git worktree (`RealPultGitTest`); здесь — изоляция
оркестрации самой команды: три пути деградации, отказ по чужому host,
форма журнальной последовательности и адресация РЕАЛЬНОГО дочернего
процесса по данным lease (тот же приём, что `tests/test_doctor.py::
dead_pid` и `tasks/T074/acceptance_tests/_sandbox.py::spawn_sleep_process`
— сигнал ОС проверяется результатом, не способом доставки). Git-механика
чекпоинта (`checkpoint.commit_pause_now_checkpoint`) замокана — она уже
покрыта `tests/test_timeout_checkpoint.py::CommitPauseNowCheckpointTest`
(реальный git) и приёмочными тестами; здесь важно только то, что
`cmd_pause_now` зовёт её с правильной ролью в правильном месте
последовательности.
"""
import socket
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, checkpoint, config, pause, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


def spawn_sleep_process() -> subprocess.Popen:
    """Реальный дочерний процесс без своего обработчика сигналов — `SIGTERM`
    завершает его сразу же (тот же приём, что и в acceptance_tests T074)."""
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def dead_pid() -> int:
    """pid реального, уже завершённого и убранного процесса."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()
    return proc.pid


class PauseNowTest(TmpRootTest):
    TASK = "T001"
    OTHER_HOST = "another-host.invalid"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        self._live_procs = []
        self.addCleanup(self._reap_live_procs)
        # Чекпоинт — реальный git worktree, который эта песочница не
        # заводит (см. докстринг модуля); заглушка возвращает "" как на
        # чистом дереве, оставляя проверку самой git-механики
        # `tests/test_timeout_checkpoint.py::CommitPauseNowCheckpointTest`
        # и приёмочным тестам.
        patcher = mock.patch.object(checkpoint, "commit_pause_now_checkpoint",
                                    return_value="")
        self.checkpoint_mock = patcher.start()
        self.addCleanup(patcher.stop)

    def _reap_live_procs(self) -> None:
        for proc in self._live_procs:
            if proc.poll() is None:
                proc.kill()
            proc.wait()

    def spawn(self) -> subprocess.Popen:
        proc = spawn_sleep_process()
        self._live_procs.append(proc)
        return proc

    def row(self, task_id: str = None):
        return store.get_task(store.db(), task_id or self.TASK)

    def journal(self, task_id: str = None):
        return store.task_steps(store.db(), task_id or self.TASK)

    def journal_text(self, task_id: str = None) -> str:
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail']}"
                         for r in self.journal(task_id))

    def install_lease(self, pid: int, hostname: str = None,
                      session_id: str = "other-session") -> None:
        hostname = hostname or socket.gethostname()
        conn = store.db()
        store.insert_lease(conn, self.TASK, session_id, pid, hostname,
                           store.now())

    def lease_row(self):
        return store.lease_row(store.db(), self.TASK)

    # ------------------------------------------------------- деградации

    def test_no_agentic_role_degrades_to_plain_pause(self):
        store.update_task(store.db(), self.TASK, state="spec_gate")

        out = capture(pause.cmd_pause_now, self.TASK)

        self.assertTrue(pause.is_paused(self.row()))
        self.assertTrue(out.strip())
        self.checkpoint_mock.assert_not_called()

    def test_no_lease_degrades_to_plain_pause(self):
        self.assertIsNone(self.lease_row())

        out = capture(pause.cmd_pause_now, self.TASK)

        self.assertTrue(pause.is_paused(self.row()))
        self.assertTrue(out.strip())
        self.checkpoint_mock.assert_not_called()

    def test_dead_lease_process_degrades_to_plain_pause(self):
        self.install_lease(dead_pid())

        out = capture(pause.cmd_pause_now, self.TASK)

        self.assertTrue(pause.is_paused(self.row()))
        self.assertTrue(out.strip())
        self.checkpoint_mock.assert_not_called()
        # Мёртвый lease — деградация, не полная последовательность
        # прерывания: чекпоинт/lease-снятие звать было незачем.
        self.assertIsNotNone(self.lease_row(),
                             "деградация без прерывания не должна была "
                             "тронуть чужую lease-строку")

    def test_other_host_refuses_interrupt_and_leaves_process_untouched(self):
        proc = self.spawn()
        self.install_lease(proc.pid, hostname=self.OTHER_HOST)

        out = capture(pause.cmd_pause_now, self.TASK)

        self.assertIsNone(proc.poll(), "процесс на чужом host не должен "
                          "быть тронут")
        text = f"{out}\n{self.journal_text()}".lower()
        self.assertIn("host", text)
        self.assertTrue("вне объём" in text or "не поддерж" in text
                        or "не вход" in text)
        self.checkpoint_mock.assert_not_called()
        # Требование 1 безусловно: пометка паузы стоит даже при отказе
        # прервать процесс на чужом host.
        self.assertTrue(pause.is_paused(self.row()))
        self.assertIsNotNone(self.lease_row(),
                             "lease на чужом host не должен быть снят")

    # --------------------------------------------------- полное прерывание

    def test_addressed_process_is_terminated(self):
        proc = self.spawn()
        self.install_lease(proc.pid)

        capture(pause.cmd_pause_now, self.TASK)
        proc.wait(timeout=10)

        self.assertIsNotNone(proc.poll())

    def test_bystander_process_is_not_touched(self):
        addressed = self.spawn()
        bystander = self.spawn()
        self.install_lease(addressed.pid)

        capture(pause.cmd_pause_now, self.TASK)
        addressed.wait(timeout=10)

        self.assertIsNotNone(addressed.poll())
        self.assertIsNone(bystander.poll())

    def test_pause_mark_is_set_after_interrupt(self):
        proc = self.spawn()
        self.install_lease(proc.pid)

        capture(pause.cmd_pause_now, self.TASK)
        proc.wait(timeout=10)

        self.assertTrue(pause.is_paused(self.row()))

    def test_lease_is_released_after_interrupt(self):
        proc = self.spawn()
        self.install_lease(proc.pid)

        capture(pause.cmd_pause_now, self.TASK)
        proc.wait(timeout=10)

        self.assertIsNone(self.lease_row())

    def test_checkpoint_is_called_with_the_step_role(self):
        proc = self.spawn()
        self.install_lease(proc.pid)

        capture(pause.cmd_pause_now, self.TASK)
        proc.wait(timeout=10)

        self.checkpoint_mock.assert_called_once_with(
            mock.ANY, self.TASK, "developer")

    def test_journal_carries_the_full_action_sequence(self):
        proc = self.spawn()
        self.install_lease(proc.pid)

        capture(pause.cmd_pause_now, self.TASK)
        proc.wait(timeout=10)

        text = self.journal_text().lower()
        expectations = {
            "обнаружение бегущего шага": ("шаг", "агент", "бег"),
            "прерывание процесса": ("процесс", "прерв", "заверш"),
            "снятие lease": ("lease",),
            "пометка паузы": ("пауз", "pause"),
        }
        missing = [label for label, keywords in expectations.items()
                  if not any(kw in text for kw in keywords)]
        self.assertEqual(missing, [])

    def test_does_not_touch_lease_or_pause_of_another_task(self):
        store.insert_task(store.db(), "T002", "Другая задача", "in_dev",
                          "task/t002-drugaya", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.install_lease(dead_pid())
        store.insert_lease(store.db(), "T002", "session-other", dead_pid(),
                           "localhost", store.now())

        capture(pause.cmd_pause_now, self.TASK)

        self.assertFalse(pause.is_paused(self.row("T002")),
                         "pause --now одной задачи выставил пометку другой")
        self.assertIsNotNone(store.lease_row(store.db(), "T002"),
                             "pause --now одной задачи снял lease другой")

    # ----------------------------------------------------- частичная стоимость

    def test_no_step_log_raises_unknown_cost_alert(self):
        proc = self.spawn()
        self.install_lease(proc.pid)

        capture(pause.cmd_pause_now, self.TASK)
        proc.wait(timeout=10)

        alerts = store.db().execute(
            "SELECT * FROM alerts WHERE kind='incident' AND "
            "source LIKE 'spend.unknown_cost%'").fetchall()
        self.assertEqual(len(alerts), 1)
        self.assertIn("неизвестна", self.journal_text().lower())

    def test_step_log_with_usage_events_avoids_unknown_cost_alert(self):
        import json as jsonlib
        from orchestrator import agent_log

        log_path = agent_log.new_agent_log(self.TASK, "developer")
        log_path.write_text(
            "агент работает\n"
            + jsonlib.dumps({"type": "assistant", "message": {
                "usage": {"input_tokens": 10, "output_tokens": 5}}}) + "\n",
            encoding="utf-8")
        proc = self.spawn()
        self.install_lease(proc.pid)

        capture(pause.cmd_pause_now, self.TASK)
        proc.wait(timeout=10)

        alerts = store.db().execute(
            "SELECT * FROM alerts WHERE kind='incident' AND "
            "source LIKE 'spend.unknown_cost%'").fetchall()
        self.assertEqual(alerts, [])
        self.assertIn("частичн", self.journal_text().lower())


if __name__ == "__main__":
    unittest.main()
