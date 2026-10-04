"""Юнит-тесты ссылки документов `refs/artifacts/<id>` на настоящем git с
bare `origin` (SPEC 01M3Z2DMQRD0BD7AARFVTCVVG8, требования 2-3, 5; AC-2,
AC-3, AC-6, AC-7): запись со сверкой прежнего значения, отправка после
коммита и повтор на переходе, отказ гейта мержа и `kill` при ссылке,
не совпадающей с `origin`, досылка коммита закрытия `doctor --fix`,
recovery-сверка переписанной мимо пульта ссылки.

Планка задачи — вся разовая (REVIEW итерации 1, R1-F1): эти свойства после
мержа держит только этот файл.
"""
import io
import subprocess
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import (artifact_branch, cleanup, config, doctor,
                          fsm_merge_gate, gitcmd, projects, snapshot, store)
from tests.sandbox import AutoOriginSandbox, capture, strip_dash_c

PUSH_FAILED = "push артефактной ветки FAILED"


class RefOriginSandbox(AutoOriginSandbox):
    """Пульт — настоящий git, `self.bare` — его `origin`; задача артели
    `TASK` в `in_dev` с одним коммитом в ссылке документов."""

    TASK = "01UNITREFSYNCTASK001"

    def setUp(self):
        super().setUp()
        self.git("push", "-q", "origin", f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          f"task/{self.TASK.lower()}-x", config.DEFAULT_TARGET,
                          25.0)
        self.ref = artifact_branch.branch_name(self.TASK)
        self.head0 = self.commit("SPEC.md", "спека\n")
        self.assertTrue(self.head0, "предусловие: первый коммит ссылки")

    def commit(self, name: str, text: str) -> str:
        return artifact_branch.commit_files(
            self.TASK, {f"tasks/{self.TASK}/{name}": text},
            f"{self.TASK}: {name}")

    def local_head(self) -> str:
        res = subprocess.run(["git", "rev-parse", "--verify", "--quiet",
                              self.ref], cwd=self.root, capture_output=True,
                             text=True)
        return res.stdout.strip() if res.returncode == 0 else ""

    def origin_head(self) -> str:
        res = subprocess.run(["git", "ls-remote", self.bare, self.ref],
                             capture_output=True, text=True)
        out = res.stdout.split()
        return out[0] if res.returncode == 0 and out else ""

    def file_at(self, sha: str, name: str) -> str | None:
        res = subprocess.run(["git", "show", f"{sha}:tasks/{self.TASK}/{name}"],
                             cwd=self.root, capture_output=True, text=True)
        return res.stdout if res.returncode == 0 else None

    def parents(self, sha: str) -> list:
        return self.git("rev-list", "--parents", "-n", "1", sha).split()[1:]

    def journal_actions(self) -> list:
        return [r["action"] for r in store.task_steps(store.db(), self.TASK)]

    def break_origin(self) -> None:
        self.git("remote", "set-url", "origin",
                 str(self.root / ".artel" / "нет-такого-origin.git"))
        self.addCleanup(self.restore_origin)

    def restore_origin(self) -> None:
        self.git("remote", "set-url", "origin", self.bare)

    def reject_ref_pushes(self) -> None:
        """`origin` отвергает запись в `refs/artifacts/*` (`pre-receive`):
        расхождение не «лечится» попутной отправкой пульта."""
        hook = Path(self.bare) / "hooks" / "pre-receive"
        hook.write_text(
            "#!/bin/sh\n"
            "while read old new ref; do\n"
            "  case \"$ref\" in refs/artifacts/*) exit 1;; esac\n"
            "done\n"
            "exit 0\n", encoding="utf-8")
        hook.chmod(0o755)

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]


class CompareAndSwapRaceTest(RefOriginSandbox):

    def test_second_write_from_stale_head_keeps_both_changes(self):
        """Вторая запись вклинивается до `update-ref` первой, собравшей
        коммит от прежней головы: итоговая голова несёт обе правки, история
        линейна, коммит второй записи достижим.

        Ловит мутацию: `update-ref` без прежнего значения в
        `artifact_branch._write` — первая запись перетирает ссылку коммитом
        от прежней головы, `B.md` пропадает из головы.
        """
        real_git = gitcmd.git
        fired = {}

        def racing_git(*args, **kwargs):
            # Сквозь `-C <клон>`: ссылка документов пишется в клоне проекта
            # явным репозиторием (ADR-0021 п.1, этап 2).
            if strip_dash_c(args)[:1] == ("update-ref",) and not fired:
                fired["b"] = ""
                fired["b"] = self.commit("B.md", "правка B\n")
            return real_git(*args, **kwargs)

        with mock.patch.object(gitcmd, "git", side_effect=racing_git):
            a_sha = self.commit("A.md", "правка A\n")

        self.assertTrue(fired.get("b"), "вторая запись не прошла")
        head = self.local_head()
        self.assertEqual(head, a_sha)
        self.assertEqual(self.file_at(head, "A.md"), "правка A\n")
        self.assertEqual(self.file_at(head, "B.md"), "правка B\n")
        self.assertEqual(self.parents(head), [fired["b"]])
        self.assertEqual(self.parents(fired["b"]), [self.head0])


class SendAfterCommitTest(RefOriginSandbox):

    def test_every_commit_lands_in_origin(self):
        """После каждого коммита ссылка в `origin` равна локальной, без
        отдельного вызова `push`.

        Ловит мутацию: `_write` не зовёт `_send` после `update-ref` —
        `origin` остаётся без ссылки.
        """
        self.assertEqual(self.origin_head(), self.head0)
        head = self.commit("PLAN.md", "план\n")
        self.assertEqual(self.origin_head(), head)

    def test_refusal_is_journaled_commit_kept_and_retried_on_transition(self):
        """`origin` недоступен: коммит цел локально, в журнале отказ push,
        в `origin` прежняя голова; `origin` вернули — следующий
        `set_state` досылает ссылку.

        Ловит мутацию: `send_pending` ничего не делает (или `set_state` его
        не зовёт) — после перехода `origin` остаётся на прежней голове.
        """
        self.break_origin()
        head = self.commit("PLAN.md", "план\n")
        self.restore_origin()

        self.assertTrue(head)
        self.assertEqual(self.local_head(), head)
        self.assertEqual(self.origin_head(), self.head0)
        self.assertIn(PUSH_FAILED, self.journal_actions())

        store.set_state(store.db(), self.TASK, "verifying", "fsm",
                        expected_state="in_dev", detail="переход теста")

        self.assertEqual(self.origin_head(), head)


class OriginSyncRefusalTest(RefOriginSandbox):

    def test_synced_ref_is_not_refused(self):
        """Ловит мутацию: сверка отказывает и при совпадении с `origin`."""
        self.assertIsNone(artifact_branch.origin_sync_refusal(self.TASK))

    def test_local_ahead_refusal_names_both_sha(self):
        """Ловит мутацию: `origin_sync_refusal` всегда `None` — локальная
        голова, которую `origin` не принимает, проходит как совпадающая.
        """
        self.reject_ref_pushes()
        head = self.commit("PLAN.md", "план\n")

        refusal = artifact_branch.origin_sync_refusal(self.TASK)

        self.assertIsNotNone(refusal)
        self.assertIn(head, refusal)
        self.assertIn(self.head0, refusal)

    def test_absent_in_origin_is_refused(self):
        """Ловит мутацию: отсутствие ссылки в `origin` читается как
        совпадение (сверка смотрит только на «оба sha непусты»)."""
        self.git("push", "-q", "origin", f":{self.ref}")
        self.reject_ref_pushes()

        refusal = artifact_branch.origin_sync_refusal(self.TASK)

        self.assertIsNotNone(refusal)
        self.assertIn("нет в origin", refusal)

    def test_unreachable_origin_is_refused(self):
        """Ловит мутацию: недоступный `origin` (ls-remote не ответил)
        читается как совпадение."""
        self.break_origin()

        refusal = artifact_branch.origin_sync_refusal(self.TASK)

        self.assertIsNotNone(refusal)
        self.assertIn("не ответил", refusal)


class MergeGateDocsRefTest(RefOriginSandbox):

    def approve_body(self):
        t = store.get_task(store.db(), self.TASK)
        buf = io.StringIO()
        with redirect_stdout(buf):
            outcome = fsm_merge_gate._cmd_approve_merge_gate(
                store.db(), self.TASK, "merge_gate", t)
        return outcome, buf.getvalue()

    def setUp(self):
        super().setUp()
        store.update_task(store.db(), self.TASK, state="merge_gate")
        # Дальше сверки документов тело гейта не идёт: следующий шаг
        # останавливает его и отмечает, что до него дошли.
        self.next_gate = mock.patch.object(
            fsm_merge_gate, "_protected_path_diff_gate", return_value=True)
        self.next_gate_mock = self.next_gate.start()
        self.addCleanup(self.next_gate.stop)

    def test_unsynced_ref_stops_the_gate_named(self):
        """Ловит мутацию: `_docs_ref_unsynced` (или `origin_sync_refusal`)
        не отказывает — тело гейта идёт дальше при ссылке, которой нет в
        `origin`.
        """
        self.reject_ref_pushes()
        self.commit("PLAN.md", "план\n")

        outcome, out = self.approve_body()

        self.assertEqual(outcome, ("stopped",))
        self.assertFalse(self.next_gate_mock.called)
        self.assertIn(fsm_merge_gate.MERGE_UNSYNCED_JOURNAL_ACTION,
                      self.journal_actions())
        self.assertIn(self.ref, out)
        self.assertEqual(self.state(), "merge_gate")

    def test_synced_ref_passes_to_the_next_gate(self):
        """Ловит мутацию: сверка отказывает и при совпадении с `origin`."""
        outcome, _ = self.approve_body()

        self.assertEqual(outcome, ("stopped",))
        self.assertTrue(self.next_gate_mock.called)
        self.assertNotIn(fsm_merge_gate.MERGE_UNSYNCED_JOURNAL_ACTION,
                         self.journal_actions())


class KillDocsRefTest(RefOriginSandbox):

    def kill(self) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            try:
                cleanup.cmd_kill(self.TASK)
            except SystemExit as exc:
                buf.write(f"\nSystemExit: {exc}")
        return buf.getvalue()

    def test_unsynced_ref_refuses_kill_and_keeps_state(self):
        """Ловит мутацию: `_refuse_unsynced_docs` не отказывает — задача
        закрывается с документами, которых нет в `origin`.
        """
        self.reject_ref_pushes()
        head = self.commit("PLAN.md", "план\n")

        out = self.kill()

        self.assertIn("SystemExit", out)
        self.assertIn(self.ref, out)
        self.assertEqual(self.state(), "in_dev")
        self.assertEqual(self.local_head(), head)
        self.assertIn(cleanup.KILL_UNSYNCED_JOURNAL_ACTION,
                      self.journal_actions())

    def test_synced_ref_kills_with_a_closing_commit_in_origin(self):
        """Ловит мутацию: сверка отказывает и при совпадении — `kill`
        синхронной задачи не закрывает её коммитом закрытия."""
        out = self.kill()

        self.assertNotIn("SystemExit", out)
        self.assertEqual(self.state(), "killed")
        head = self.local_head()
        self.assertEqual(self.parents(head), [self.head0])
        self.assertIsNotNone(self.file_at(head, "RETRO.md"))
        self.assertEqual(self.origin_head(), head)


class DoctorFixResendsClosingCommitTest(RefOriginSandbox):

    def close_without_send(self) -> str:
        store.update_task(store.db(), self.TASK, state="killed")
        with mock.patch.object(artifact_branch, "_send", return_value=False):
            snapshot.commit_closing(store.db(), self.TASK, "killed")
        closing = snapshot.closing_sha(store.db(), self.TASK)
        self.assertEqual(self.local_head(), closing)
        self.assertEqual(self.origin_head(), self.head0,
                         "предусловие: коммит закрытия не отправлен")
        return closing

    def test_fix_pushes_the_closing_commit(self):
        """Ловит мутацию: `doctor --fix` не досылает закрытую ссылку —
        коммит закрытия остаётся только локально.
        """
        closing = self.close_without_send()

        capture(doctor._fix_unsent_closed_refs, store.db())

        self.assertEqual(self.origin_head(), closing)
        checks = [c for c in doctor.check_artifact_ref_sync(store.db())
                  if c.status != "ok"]
        self.assertEqual(checks, [])

    def test_fix_does_not_resend_a_ref_moved_after_closing(self):
        """Ловит мутацию: досылка не сверяет локальную голову с коммитом
        закрытия — изменённая после закрытия ссылка уезжает в `origin`."""
        closing = self.close_without_send()
        with mock.patch.object(artifact_branch, "_send", return_value=False):
            moved = self.commit("EXTRA.md", "после закрытия\n")
        self.assertNotEqual(moved, closing)

        capture(doctor._fix_unsent_closed_refs, store.db())

        self.assertEqual(self.origin_head(), self.head0)


class RecoveryRewrittenRefTest(RefOriginSandbox):

    def setUp(self):
        super().setUp()
        # Репозиторий фиксации прежнего устройства, оставшийся на диске:
        # пульт его больше не заводит (ADR-0021 п.2), фикстура — сама.
        repo = config.PROJECTS / config.DEFAULT_TARGET
        repo.mkdir(parents=True, exist_ok=True)
        gitcmd.in_repo(repo, "init", "-q", "-b", config.MAIN_BRANCH)

    def recovery_sha(self):
        checks = doctor.recovery_check(store.db(), config.DEFAULT_TARGET)
        return {c.name: c for c in checks}["recovery-sha"]

    def test_ref_rewritten_outside_its_history_is_a_mismatch(self):
        """Ссылку переписали мимо пульта на коммит без родителя:
        зафиксированный sha — не предок новой головы, но он есть в пульте.

        Ловит мутацию: признак фиксации прежнего устройства — «не предок
        головы» (`is_ancestor`) вместо отсутствия объекта: переписанная
        ссылка проходит recovery-сверку как `ok`.
        """
        store.update_task(store.db(), self.TASK, fixed_sha=self.head0)
        tree = self.git("rev-parse", f"{self.head0}^{{tree}}").strip()
        orphan = self.git("commit-tree", tree, "-m", "мимо пульта").strip()
        self.git("update-ref", self.ref, orphan)

        self.assertEqual(self.recovery_sha().status, "fail")

    def test_fixation_of_the_old_device_is_not_compared(self):
        """Зафиксирован коммит репозитория фиксации `.artel/projects/`
        (прежнее устройство): в объектной базе пульта его нет.

        Ловит мутацию: признак прежнего устройства снят — любой
        зафиксированный sha, отличный от головы ссылки, даёт инцидент.
        """
        repo = config.PROJECTS / config.DEFAULT_TARGET
        (repo / "old.md").write_text("старая фиксация\n", encoding="utf-8")
        gitcmd.in_repo(repo, "add", "-A")
        gitcmd.in_repo(repo, "-c", "user.name=t", "-c", "user.email=t@t.invalid",
                       "commit", "-q", "-m", "фиксация")
        old_sha = gitcmd.head_sha(repo)
        self.assertNotEqual(old_sha, self.head0)
        store.update_task(store.db(), self.TASK, fixed_sha=old_sha)

        self.assertEqual(self.recovery_sha().status, "ok")


if __name__ == "__main__":
    unittest.main()
