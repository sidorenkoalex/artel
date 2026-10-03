"""Юнит-тесты сверки ссылки документов с `origin` в `doctor` (SPEC
01M1TQ0X14Y5B3C87WC0Q31PK2, требование 3, AC-6; с ADR-0021 п.3 —
`doctor.check_artifact_ref_sync` по `refs/artifacts/<id>` вместо ветки
`artifact/<id>`, SPEC 01M3Z2DMQRD0BD7AARFVTCVVG8, требование 5, AC-7).
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from orchestrator import (artifact_branch, config, doctor, gitcmd,
                          repo_context, snapshot, store)
from tests.sandbox import AutoOriginSandbox

EXTERNAL_TARGET = "extproj"


class ArtifactBranchSyncSandbox(AutoOriginSandbox):

    def new_task(self, task_id: str, state: str = "in_dev",
                target: str = "artel") -> str:
        store.insert_task(store.db(), task_id, "Задача", state,
                          f"task/{task_id.lower()}-x", target, 25.0)
        return artifact_branch.branch_name(task_id)

    def commit(self, task_id: str, text: str) -> str:
        """Коммит пульта: пишется в ссылку и сразу уходит в origin."""
        return artifact_branch.commit_files(
            task_id, {f"tasks/{task_id}/SPEC.md": text},
            f"{task_id}: правка")

    def side_commit(self, task_id: str, text: str) -> str:
        """Коммит поверх локальной головы, ссылку не двигающий."""
        sha = artifact_branch.write_commit(
            config.ROOT, {f"tasks/{task_id}/SIDE.md": text}, "мимо пульта",
            "operator", "operator@example.invalid",
            parent=artifact_branch.ref_head(task_id))
        self.assertTrue(sha)
        return sha

    def push_external_commit(self, task_id: str) -> str:
        """Коммит мимо пульта прямо в origin; локальная ссылка не знает о нём."""
        sha = self.side_commit(task_id, "внешний коммит\n")
        ref = artifact_branch.branch_name(task_id)
        self.git("push", "-q", "origin", f"{sha}:{ref}")
        return sha

    def local_commit_unsent(self, task_id: str, text: str) -> str:
        """Локальный коммит, отправка которого не состоялась."""
        sha = self.side_commit(task_id, text)
        self.git("update-ref", artifact_branch.branch_name(task_id), sha)
        return sha

    def origin_sha(self, ref: str) -> str:
        return gitcmd.remote_ref_state(ref)[0]

    def checks(self):
        return doctor.check_artifact_ref_sync(store.db())


class SyncOkTest(ArtifactBranchSyncSandbox):

    def test_ok_when_matching(self):
        """Ловит мутацию: сверка сравнивает не голову ссылки, а что-то
        другое (например имя ветки `artifact/<id>`, которой нет) —
        совпадающая с origin ссылка дала бы `warn`."""
        task_id = "01SYNCOKMATCHING0001"
        ref = self.new_task(task_id)
        self.commit(task_id, "спека\n")
        self.assertEqual(self.origin_sha(ref), artifact_branch.ref_head(task_id))

        checks = self.checks()
        self.assertTrue(checks)
        self.assertTrue(all(c.status == "ok" for c in checks), checks)
        self.assertFalse(any(task_id in c.detail for c in checks))


class SyncOriginAheadTest(ArtifactBranchSyncSandbox):

    def test_warn_local_behind(self):
        """Ловит мутацию: сверка смотрит только «локальная впереди» —
        коммит мимо пульта в origin остался бы без строки."""
        task_id = "01SYNCLOCALBEHIND001"
        ref = self.new_task(task_id)
        self.commit(task_id, "спека v1\n")
        self.push_external_commit(task_id)

        local_sha = gitcmd.branch_head_sha(ref)
        origin_sha = self.origin_sha(ref)
        self.assertNotEqual(local_sha, origin_sha)

        warn = [c for c in self.checks() if c.status == "warn"
               and task_id in c.detail]
        self.assertEqual(len(warn), 1, self.checks())
        self.assertIn(local_sha, warn[0].detail)
        self.assertIn(origin_sha, warn[0].detail)
        self.assertIn("расходится с origin", warn[0].detail)


class SyncLocalAheadTest(ArtifactBranchSyncSandbox):

    def test_warn_origin_behind(self):
        """Ловит мутацию: сверка смотрит только «origin впереди» —
        неотправленный локальный коммит остался бы без строки."""
        task_id = "01SYNCORIGINBEHIND01"
        ref = self.new_task(task_id)
        self.commit(task_id, "спека v1\n")
        local_sha = self.local_commit_unsent(task_id, "спека v2, не отправлена\n")

        self.assertNotEqual(local_sha, self.origin_sha(ref))

        warn = [c for c in self.checks() if c.status == "warn"
               and task_id in c.detail]
        self.assertEqual(len(warn), 1, self.checks())
        self.assertIn(local_sha, warn[0].detail)
        self.assertIn("расходится с origin", warn[0].detail)


class SyncDivergedTest(ArtifactBranchSyncSandbox):

    def test_warn_diverged(self):
        """Ловит мутацию: расхождение считается только при отношении
        «предок — потомок» — разошедшиеся истории прошли бы молча."""
        task_id = "01SYNCDIVERGEDTASK01"
        self.new_task(task_id)
        self.commit(task_id, "спека v1\n")
        self.push_external_commit(task_id)
        self.local_commit_unsent(task_id, "локальная правка, не отправлена\n")

        warn = [c for c in self.checks() if c.status == "warn"
               and task_id in c.detail]
        self.assertEqual(len(warn), 1, self.checks())
        self.assertIn("расходится с origin", warn[0].detail)


class SyncSkipWithoutOriginTest(ArtifactBranchSyncSandbox):

    def test_skip_without_origin(self):
        """Ловит мутацию: без origin сверка отвечает `ok` — недоступность
        читалась бы как «совпадает»."""
        self.git("remote", "remove", "origin")
        task_id = "01SYNCSKIPNOORIGIN01"
        self.new_task(task_id)
        self.commit(task_id, "спека\n")

        checks = self.checks()
        self.assertTrue(checks)
        self.assertTrue(all(c.status == "skip" for c in checks))
        self.assertTrue(all(c.detail.strip() for c in checks))


class SyncExcludesTerminalAndForeignTargetTest(ArtifactBranchSyncSandbox):

    def external_project(self) -> Path:
        """Клон внешнего проекта со своим bare-`origin` по адресу
        `repo_context` — ссылка документов его задач живёт там (ADR-0021
        п.3)."""
        entry = ("    forge: github\n    url: file:///nonexistent/{name}\n"
                 "    base: {base}\n    token_slot: {name}-token\n"
                 "    no_paths: []\n    project_skills: []\n"
                 "    merge_gate: operator\n")
        config.TARGETS.write_text(
            "targets:\n"
            + "".join(f"  {name}:\n" + entry.format(name=name,
                                                    base=config.MAIN_BRANCH)
                      for name in (config.DEFAULT_TARGET, EXTERNAL_TARGET)),
            encoding="utf-8")
        project = repo_context.resolve(EXTERNAL_TARGET).path
        project.mkdir(parents=True, exist_ok=True)
        self.git("-C", str(project), "init", "-q", "-b", config.MAIN_BRANCH)
        bare = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, bare, ignore_errors=True)
        self.git("init", "-q", "--bare", bare)
        self.git("-C", str(project), "remote", "add", "origin", bare)
        return project

    def test_excludes_done_and_external_target(self):
        """Закрытая задача без записи о коммите закрытия (исторический
        снимок, AC-10) не сверяется; живая задача внешнего target —
        сверяется наравне с артелью, в репозитории своего проекта и с его
        `origin` (ADR-0021 п.3).

        Ловит мутацию: прежнее исключение внешнего target оставлено —
        расхождение его ссылки с origin прошло бы без строки."""
        done_id = "01SYNCEXCLUDEDONE001"
        self.new_task(done_id, state="done")
        self.commit(done_id, "спека\n")
        self.push_external_commit(done_id)

        project = self.external_project()
        external_id = "01SYNCEXCLUDEEXTERN1"
        ref = self.new_task(external_id, target=EXTERNAL_TARGET)
        self.commit(external_id, "спека\n")
        sha = artifact_branch.write_commit(
            project, {f"tasks/{external_id}/SIDE.md": "внешний коммит\n"},
            "мимо пульта", "operator", "operator@example.invalid",
            parent=artifact_branch.ref_head(external_id))
        self.assertTrue(sha)
        self.git("-C", str(project), "push", "-q", "origin", f"{sha}:{ref}")

        checks = self.checks()
        self.assertEqual([c for c in checks if done_id in c.detail], [])
        self.assertEqual(len([c for c in checks if c.status == "warn"
                              and external_id in c.detail]), 1, checks)


class ClosedRefMovedAfterClosingTest(ArtifactBranchSyncSandbox):

    def test_closed_ref_changed_after_closing_commit_is_reported(self):
        """Ловит мутацию: закрытые задачи выпали из сверки (`_closed_ref_
        problem` не сообщает ничего, как живые без локальной ссылки) —
        коммит в ссылку после коммита закрытия прошёл бы без строки."""
        task_id = "01SYNCCLOSEDMOVED001"
        self.new_task(task_id, state="done")
        self.commit(task_id, "спека\n")
        conn = store.db()
        snapshot.commit_closing(conn, task_id, "done")
        closing = snapshot.closing_sha(conn, task_id)
        self.assertEqual(closing, artifact_branch.ref_head(task_id))
        self.assertEqual([c for c in self.checks() if task_id in c.detail], [])

        moved = self.commit(task_id, "правка после закрытия\n")

        warn = [c for c in self.checks() if c.status == "warn"
               and task_id in c.detail]
        self.assertEqual(len(warn), 1, self.checks())
        self.assertIn(closing, warn[0].detail)
        self.assertIn(moved, warn[0].detail)


if __name__ == "__main__":
    unittest.main()
