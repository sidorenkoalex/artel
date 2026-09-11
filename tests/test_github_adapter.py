"""Юнит-тесты orchestrator/github_adapter.py (SPEC T079, требования 1-3).

Приёмочные тесты (tasks/T079/acceptance_tests) кроют AC-1..AC-3 только
`manual`-пометкой — SPEC сознательно не называет механизм (см.
test_manual_criteria.py). Здесь — сам модуль в изоляции: идемпотентность
`ensure_draft_mr`/`undraft_mr` по колонке `draft_mr_created`, пропуск
канареечных и не-github задач, и что любой сбой становится инцидентом
(журнал + alert), а не исключением, летящим наружу в FSM.

`conn`/`t` — заглушки: модуль сам обращается к `store`/`alerts`/`ci`/
`gitcmd`/`targets` только через их публичные функции, все подменены.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import github_adapter, targets  # noqa: E402


def task_row(**overrides) -> dict:
    row = {
        "target": "artel",
        "branch": "task/t001-x",
        "title": "Заголовок задачи",
        "draft_mr_created": 0,
        "is_canary": 0,
    }
    row.update(overrides)
    return row


class EnsureDraftMrTest(unittest.TestCase):

    def setUp(self):
        self.conn = mock.Mock()
        patchers = {
            "target": mock.patch.object(
                github_adapter.targets, "target",
                lambda name: {"forge": "github", "base": "main"}),
            "git": mock.patch.object(
                github_adapter.gitcmd, "git",
                lambda *a: subprocess.CompletedProcess(list(a), 0, "", "")),
            "gh": mock.patch.object(
                github_adapter.ci, "gh",
                lambda *a: subprocess.CompletedProcess(
                    list(a), 0, "https://github.com/x/y/pull/1\n", "")),
            "update_task": mock.patch.object(github_adapter.store,
                                             "update_task"),
            "journal": mock.patch.object(github_adapter.store, "journal"),
            "raise_alert": mock.patch.object(github_adapter.alerts,
                                             "raise_alert"),
            "task_target": mock.patch.object(
                github_adapter.store, "task_target", lambda conn, tid: "artel"),
        }
        self.mocks = {}
        for name, patcher in patchers.items():
            self.mocks[name] = patcher.start()
            self.addCleanup(patcher.stop)

    def test_skips_when_already_created(self):
        t = task_row(draft_mr_created=1)

        github_adapter.ensure_draft_mr(self.conn, "T001", t)

        self.mocks["update_task"].assert_not_called()
        self.mocks["journal"].assert_not_called()

    def test_skips_for_a_canary_task(self):
        t = task_row(is_canary=1)

        github_adapter.ensure_draft_mr(self.conn, "T001", t)

        self.mocks["update_task"].assert_not_called()

    def test_skips_for_a_non_github_target(self):
        with mock.patch.object(github_adapter.targets, "target",
                               lambda name: {"forge": "gitlab", "base": "main"}):
            github_adapter.ensure_draft_mr(self.conn, "T001", task_row())

        self.mocks["update_task"].assert_not_called()

    def test_skips_when_targets_yaml_is_broken(self):
        """`_is_github_target` разбирает targets.yaml сама и на отказ
        возвращает False — не github, не заводить."""
        with mock.patch.object(
                github_adapter.targets, "target",
                mock.Mock(side_effect=targets.TargetsError("не разобран"))):
            github_adapter.ensure_draft_mr(self.conn, "T001", task_row())

        self.mocks["update_task"].assert_not_called()

    def test_base_branch_lookup_failing_after_the_forge_check_is_an_incident(self):
        """Между проверкой forge и чтением `base` targets.yaml теоретически
        мог перестать читаться (SPEC требование 1) — второй вызов
        `targets.target` падает отдельно от первого, успешного."""
        calls = mock.Mock(side_effect=[
            {"forge": "github", "base": "main"},
            targets.TargetsError("targets.yaml исчез"),
        ])
        with mock.patch.object(github_adapter.targets, "target", calls):
            github_adapter.ensure_draft_mr(self.conn, "T001", task_row())

        self.mocks["update_task"].assert_not_called()
        self.mocks["journal"].assert_called_once()
        self.assertIn("Draft MR FAILED", self.mocks["journal"].call_args[0])
        self.mocks["raise_alert"].assert_called_once()

    def test_push_failure_is_an_incident_not_an_exception(self):
        with mock.patch.object(
                github_adapter.gitcmd, "git",
                lambda *a: subprocess.CompletedProcess(
                    list(a), 1, "", "permission denied")):
            github_adapter.ensure_draft_mr(self.conn, "T001", task_row())

        self.mocks["update_task"].assert_not_called()
        self.assertIn("Draft MR FAILED", self.mocks["journal"].call_args[0])
        self.assertIn("permission denied", self.mocks["journal"].call_args[0][4])

    def test_push_returning_none_is_also_an_incident(self):
        with mock.patch.object(github_adapter.gitcmd, "git", lambda *a: None):
            github_adapter.ensure_draft_mr(self.conn, "T001", task_row())

        self.mocks["update_task"].assert_not_called()
        self.mocks["raise_alert"].assert_called_once()

    def test_pr_create_failure_is_an_incident(self):
        with mock.patch.object(
                github_adapter.ci, "gh",
                lambda *a: subprocess.CompletedProcess(
                    list(a), 1, "", "HTTP 422: already exists")):
            github_adapter.ensure_draft_mr(self.conn, "T001", task_row())

        self.mocks["update_task"].assert_not_called()
        self.assertIn("Draft MR FAILED", self.mocks["journal"].call_args[0])
        self.assertIn("already exists", self.mocks["journal"].call_args[0][4])

    def test_success_marks_the_task_and_journals(self):
        github_adapter.ensure_draft_mr(self.conn, "T001", task_row())

        self.mocks["update_task"].assert_called_once_with(
            self.conn, "T001", draft_mr_created=1)
        self.mocks["journal"].assert_called_once()
        self.assertIn("Draft MR заведён", self.mocks["journal"].call_args[0])
        self.mocks["raise_alert"].assert_not_called()

    def test_pr_create_is_called_with_the_task_branch_and_base(self):
        asked = []

        def spy_gh(*args):
            asked.append(args)
            return subprocess.CompletedProcess(list(args), 0, "ok\n", "")

        with mock.patch.object(github_adapter.ci, "gh", spy_gh):
            github_adapter.ensure_draft_mr(self.conn, "T001",
                                           task_row(branch="task/t001-x"))

        (call,) = asked
        self.assertIn("--draft", call)
        self.assertIn("task/t001-x", call)
        self.assertIn("main", call)


class EnsureHeadInOriginTest(unittest.TestCase):
    """`github_adapter.ensure_head_in_origin` (SPEC
    01M1GS5HZ1JXFGKVR95HEW0AEZ, требования 1-3, AC-1..AC-4): sha
    головы ветки в origin. Сюда — только сама сверка/авто-push/
    журналирование в изоляции; поведение внутри реальных переходов FSM
    (порядок относительно `reviewed_iter`, AC-5) кроют приёмочные тесты
    задачи на настоящем git."""

    def setUp(self):
        self.conn = mock.Mock()
        self.journal_patcher = mock.patch.object(github_adapter.store, "journal")
        self.journal = self.journal_patcher.start()
        self.addCleanup(self.journal_patcher.stop)
        # `ensure_head_in_origin` резолвит репозиторный контекст target'а
        # (SPEC 01M1R5B33CC7E6BZK085XV3ZCX) через `store.task_target` —
        # self по умолчанию, тем же путём, что и до этой задачи.
        self.task_target_patcher = mock.patch.object(
            github_adapter.store, "task_target",
            lambda conn, tid: "artel")
        self.task_target_patcher.start()
        self.addCleanup(self.task_target_patcher.stop)

    def test_matching_sha_is_a_noop(self):
        with mock.patch.object(github_adapter.gitcmd, "branch_head_sha",
                               lambda b, repo=None: "abc123"), \
             mock.patch.object(github_adapter.gitcmd, "remote_branch_sha",
                               lambda b, repo=None: "abc123"), \
             mock.patch.object(github_adapter.gitcmd, "git") as git_mock:
            ok, detail = github_adapter.ensure_head_in_origin(
                self.conn, "T001", "task/t001-x")

        self.assertTrue(ok)
        self.assertEqual(detail, "")
        git_mock.assert_not_called()
        self.journal.assert_not_called()

    def test_missing_head_triggers_a_push_and_journals_success(self):
        pushes = []

        def fake_git(*args):
            pushes.append(args)
            return subprocess.CompletedProcess(list(args), 0, "ok\n", "")

        with mock.patch.object(github_adapter.gitcmd, "branch_head_sha",
                               lambda b, repo=None: "abc123"), \
             mock.patch.object(github_adapter.gitcmd, "remote_branch_sha",
                               lambda b, repo=None: ""), \
             mock.patch.object(github_adapter.gitcmd, "git", fake_git):
            ok, detail = github_adapter.ensure_head_in_origin(
                self.conn, "T001", "task/t001-x")

        self.assertTrue(ok)
        self.assertEqual(detail, "")
        self.assertEqual(pushes, [("push", "-u", "origin", "task/t001-x")])
        self.journal.assert_called_once()
        self.assertIn("push", self.journal.call_args[0][3])

    def test_stale_remote_sha_triggers_a_push_too(self):
        """AC-2: расхождение по sha, не только полное отсутствие ветки в
        origin, тоже обязано запустить push."""
        with mock.patch.object(github_adapter.gitcmd, "branch_head_sha",
                               lambda b, repo=None: "new-sha"), \
             mock.patch.object(github_adapter.gitcmd, "remote_branch_sha",
                               lambda b, repo=None: "old-sha"), \
             mock.patch.object(
                 github_adapter.gitcmd, "git",
                 lambda *a: subprocess.CompletedProcess(list(a), 0, "ok\n", "")):
            ok, _ = github_adapter.ensure_head_in_origin(
                self.conn, "T001", "task/t001-x")

        self.assertTrue(ok)
        self.journal.assert_called_once()

    def test_failed_push_is_a_named_refusal(self):
        with mock.patch.object(github_adapter.gitcmd, "branch_head_sha",
                               lambda b, repo=None: "abc123"), \
             mock.patch.object(github_adapter.gitcmd, "remote_branch_sha",
                               lambda b, repo=None: ""), \
             mock.patch.object(
                 github_adapter.gitcmd, "git",
                 lambda *a: subprocess.CompletedProcess(
                     list(a), 1, "", "permission denied")):
            ok, detail = github_adapter.ensure_head_in_origin(
                self.conn, "T001", "task/t001-x")

        self.assertFalse(ok)
        self.assertEqual(
            detail,
            "голова ветки не в origin, push не удался: permission denied")
        self.journal.assert_called_once()
        self.assertIn("push не удался", self.journal.call_args[0][4])

    def test_push_returning_none_is_also_a_named_refusal(self):
        with mock.patch.object(github_adapter.gitcmd, "branch_head_sha",
                               lambda b, repo=None: "abc123"), \
             mock.patch.object(github_adapter.gitcmd, "remote_branch_sha",
                               lambda b, repo=None: ""), \
             mock.patch.object(github_adapter.gitcmd, "git", lambda *a: None):
            ok, detail = github_adapter.ensure_head_in_origin(
                self.conn, "T001", "task/t001-x")

        self.assertFalse(ok)
        self.assertIn("git не ответил", detail)


class UndraftMrTest(unittest.TestCase):

    def setUp(self):
        self.conn = mock.Mock()
        patchers = {
            "target": mock.patch.object(
                github_adapter.targets, "target",
                lambda name: {"forge": "github", "base": "main"}),
            "gh": mock.patch.object(
                github_adapter.ci, "gh",
                lambda *a: subprocess.CompletedProcess(list(a), 0, "ok\n", "")),
            "journal": mock.patch.object(github_adapter.store, "journal"),
            "raise_alert": mock.patch.object(github_adapter.alerts,
                                             "raise_alert"),
            "task_target": mock.patch.object(
                github_adapter.store, "task_target", lambda conn, tid: "artel"),
        }
        self.mocks = {}
        for name, patcher in patchers.items():
            self.mocks[name] = patcher.start()
            self.addCleanup(patcher.stop)

    def test_skips_when_no_draft_mr_was_ever_created(self):
        github_adapter.undraft_mr(self.conn, "T001", task_row(draft_mr_created=0))

        self.mocks["journal"].assert_not_called()

    def test_skips_for_a_canary_task(self):
        github_adapter.undraft_mr(
            self.conn, "T001", task_row(draft_mr_created=1, is_canary=1))

        self.mocks["journal"].assert_not_called()

    def test_skips_for_a_non_github_target(self):
        with mock.patch.object(github_adapter.targets, "target",
                               lambda name: {"forge": "gitlab", "base": "main"}):
            github_adapter.undraft_mr(self.conn, "T001",
                                      task_row(draft_mr_created=1))

        self.mocks["journal"].assert_not_called()

    def test_ready_failure_is_an_incident_not_an_exception(self):
        with mock.patch.object(
                github_adapter.ci, "gh",
                lambda *a: subprocess.CompletedProcess(
                    list(a), 1, "", "no pull requests found")):
            github_adapter.undraft_mr(self.conn, "T001",
                                      task_row(draft_mr_created=1))

        self.assertIn("MR undraft FAILED", self.mocks["journal"].call_args[0])
        self.mocks["raise_alert"].assert_called_once()

    def test_success_journals_without_an_incident(self):
        github_adapter.undraft_mr(self.conn, "T001", task_row(draft_mr_created=1))

        self.mocks["journal"].assert_called_once()
        self.assertIn("MR снят с Draft", self.mocks["journal"].call_args[0])
        self.mocks["raise_alert"].assert_not_called()

    def test_ready_is_called_for_the_task_branch(self):
        asked = []

        def spy_gh(*args):
            asked.append(args)
            return subprocess.CompletedProcess(list(args), 0, "ok\n", "")

        with mock.patch.object(github_adapter.ci, "gh", spy_gh):
            github_adapter.undraft_mr(
                self.conn, "T001",
                task_row(draft_mr_created=1, branch="task/t001-x"))

        (call,) = asked
        self.assertIn("ready", call)
        self.assertIn("task/t001-x", call)


if __name__ == "__main__":
    unittest.main()
