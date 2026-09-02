"""AC-6: снятие lease каждым из путей — обычный `release`, `kill`,
успешное закрытие задачи (`done`), `pause --now` — журналируется
записью, называющей снявшую сессию; тесты покрывают каждый путь
отдельно (требование явно требует раздельного покрытия, не одного
сквозного сценария).

Общий приём всех четырёх тестов: identity вызывающей стороны
контролируется через `ARTEL_SESSION_ID` (тот же источник, что уже
резолвит `lease.resolve_session_id`, AC-1), а сама снимаемая строка
`leases` изначально принадлежит ДРУГОЙ, отличимой identity — так
совпадение появившейся в журнале строки с identity releaser'а не может
быть случайным.

`kill` — особый случай: `cleanup.cmd_kill` сам берёт lease через
`lease.run_locked` (SPEC T044/T057) ПЕРЕД тем, как его снять; обычный
механизм `run_locked` освобождает lease в `finally` ТОЛЬКО если он был
взят "с нуля" этим же вызовом (см. докстринг `orchestrator/lease.py`).
Если lease уже принадлежит ТОЙ ЖЕ identity, что резолвит kill (типичная
ситуация — сессия удерживает lease весь цикл `auto`, а `kill` вызывается
из-под неё же), взятие — не "с нуля" (`fresh=False`), и штатный
`run_locked` НЕ снимет lease вовсе. AC-6 требует, чтобы `kill` снимал
lease БЕЗУСЛОВНО ("любым путём") — поэтому тест ставит именно этот
неблагоприятный для штатного механизма случай (renewal, не fresh), а
не захват с нуля: так assertion "lease снят" и assertion "снятие
названо" проверяют именно НОВУЮ, требуемую AC-6 функциональность, а не
побочный эффект уже существующего "fresh -> release" в `run_locked`.

Красны до реализации все четыре теста: `lease.release()` сегодня не
журналирует ничего вовсе (`orchestrator/lease.py::release` — голый
`store.release_lease`, без единого `store.journal`); `release.cmd_
release`, `pause.cmd_pause_now` журналируют identity ПРЕЖНЕГО
держателя, а не releaser'а; `_cmd_approve_merge_gate` (путь `done`) не
трогает lease вовсе.
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import (catalog, checkpoint, ci, cleanup, config,  # noqa: E402
                          fsm_merge_gate, lease, pause, release, store)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import LeaseTaskTest, RealGitSandbox, any_step_carries, capture  # noqa: E402


class ReleaseCommandNamesReleasingSessionTest(LeaseTaskTest):

    def test_ac6_release_command_names_the_releasing_session(self):
        self.insert_lease(self.TASK, "sess-holder-release", 424242,
                          "holder-host", store.now())
        before = len(self.steps())

        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "sess-release-ac6"}):
            capture(release.cmd_release, self.TASK)

        self.assertIsNone(self.lease_row())
        new_steps = self.steps()[before:]
        self.assertTrue(
            any_step_carries(new_steps, "sess-release-ac6"),
            f"снятие lease командой `release` не называет снявшую "
            f"сессию (AC-6): {new_steps}")


class KillReleasesLeaseTest(RealGitSandbox):
    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-nesuschestvuyuschaya-vetka",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)

    def test_ac6_kill_releases_lease_and_names_the_killing_session(self):
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "sess-kill-ac6"}):
            # Lease уже принадлежит той же identity, что резолвит сам
            # `kill` ниже, — `run_locked` внутри `cmd_kill` продлит его
            # (не "с нуля"), см. докстринг модуля.
            lease.acquire(store.db(), self.TASK, lease.resolve_session_id(None))
            self.assertIsNotNone(store.lease_row(store.db(), self.TASK))
            before = len(store.task_steps(store.db(), self.TASK))

            capture(cleanup.cmd_kill, self.TASK)

        self.assertIsNone(
            store.lease_row(store.db(), self.TASK),
            "kill обязан снять lease даже когда он не был взят с нуля "
            "этим же вызовом (AC-6, «любым путём»)")
        new_steps = store.task_steps(store.db(), self.TASK)[before:]
        self.assertTrue(
            any_step_carries(new_steps, "sess-kill-ac6"),
            f"снятие lease при kill не называет снявшую сессию (AC-6): "
            f"{new_steps}")


class PauseNowReleasesLeaseTest(LeaseTaskTest):

    def setUp(self):
        super().setUp()
        self._live_procs = []
        self.addCleanup(self._reap_live_procs)
        patcher = mock.patch.object(checkpoint, "commit_pause_now_checkpoint",
                                    return_value="")
        patcher.start()
        self.addCleanup(patcher.stop)

    def _reap_live_procs(self) -> None:
        for proc in self._live_procs:
            if proc.poll() is None:
                proc.kill()
            proc.wait()

    def _spawn_sleep_process(self) -> subprocess.Popen:
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._live_procs.append(proc)
        return proc

    def test_ac6_pause_now_releases_lease_and_names_the_pausing_session(self):
        proc = self._spawn_sleep_process()
        self.insert_lease(self.TASK, "sess-holder-pausenow", proc.pid,
                          socket.gethostname(), store.now())
        before = len(self.steps())

        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "sess-pausenow-ac6"}):
            capture(pause.cmd_pause_now, self.TASK)

        self.assertIsNone(self.lease_row())
        new_steps = self.steps()[before:]
        self.assertTrue(
            any_step_carries(new_steps, "sess-pausenow-ac6"),
            f"снятие lease при `pause --now` не называет снявшую сессию "
            f"(AC-6): {new_steps}")


class DoneTransitionReleasesLeaseTest(RealGitSandbox):
    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)

        origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, origin, ignore_errors=True)
        self.git("init", "-q", "--bare", str(origin))
        self.git("remote", "add", "origin", str(origin))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)

        self.branch = f"task/{self.TASK.lower()}-x"
        self.git("checkout", "-b", self.branch)
        (self.root / "feature.txt").write_text("код фичи\n", encoding="utf-8")
        self.git("add", "feature.txt")
        self.git("commit", "-q", "-m", f"{self.TASK}: код фичи")
        self.git("checkout", config.MAIN_BRANCH)

        store.insert_task(store.db(), self.TASK, "Задача", "merge_gate",
                          self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

        ci_patcher = mock.patch.object(
            ci, "branch_status", lambda branch: (True, "зелёный (тест)"))
        ci_patcher.start()
        self.addCleanup(ci_patcher.stop)

    def test_ac6_done_transition_releases_lease_and_names_the_closing_session(self):
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-holder-done", 424242, socket.gethostname(),
             store.now()))
        conn.commit()
        t = store.get_task(conn, self.TASK)
        before = len(store.task_steps(store.db(), self.TASK))

        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "sess-done-ac6"}):
            result = fsm_merge_gate._cmd_approve_merge_gate(
                store.db(), self.TASK, "merge_gate", t)

        self.assertEqual(result, ("done",))
        self.assertIsNone(
            store.lease_row(store.db(), self.TASK),
            "успешное закрытие задачи (done) обязано снять lease (AC-6)")
        new_steps = store.task_steps(store.db(), self.TASK)[before:]
        self.assertTrue(
            any_step_carries(new_steps, "sess-done-ac6"),
            f"снятие lease при переходе в done не называет закрывающую "
            f"сессию (AC-6): {new_steps}")


if __name__ == "__main__":
    unittest.main()
