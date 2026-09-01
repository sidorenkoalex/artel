"""Юнит-тесты обвязки RETRO в orchestrator/fsm_postmerge.py (SPEC T043,
перенесено из fsm.py в T091 — декомпозиция диспетчеров fsm/runner):
некритичность провала, подбор killed-долгов, форма коммитов.

Сквозной путь через `cmd_approve` целиком уже покрывают приёмочные тесты
`tasks/T043/acceptance_tests/` — здесь `fsm_postmerge._generate_and_commit_retro`
по отдельности, тем же приёмом, что
`tests/test_fsm_map_regen.py::RegenerateAndCommitMapTest`.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import alerts, config, fsm_postmerge, gitcmd, retro, store  # noqa: E402
from tests.sandbox import TmpRootTest, fake_git  # noqa: E402


class GenerateAndCommitRetroTest(TmpRootTest):
    """Песочница: sandbox.TmpRootTest полным набором путей (SPEC T061, AC-3)."""

    TASK = "T900"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Задача", "merge_gate",
                          "task/t900-x", config.DEFAULT_TARGET, 50.0)

    def incidents(self):
        return alerts.open_alerts(self.conn, "incident")

    def test_happy_path_writes_and_commits_done_retro(self):
        git_calls = []

        def fake_git(*args) -> subprocess.CompletedProcess:
            git_calls.append(args)
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(gitcmd, "git", fake_git):
            fsm_postmerge._generate_and_commit_retro(self.conn, self.TASK, "a" * 40)

        self.assertTrue(retro.retro_path(self.TASK).exists())
        self.assertIn(("add", retro.retro_rel_path(self.TASK)), git_calls)
        commit_messages = [c for c in git_calls if c[0] == "commit"]
        self.assertEqual(len(commit_messages), 1)
        self.assertIn(self.TASK, " ".join(commit_messages[0]))
        self.assertEqual(self.incidents(), [])

    def test_write_failure_raises_incident_and_does_not_call_git(self):
        git_calls = []

        def fake_git(*args) -> subprocess.CompletedProcess:
            git_calls.append(args)
            return subprocess.CompletedProcess(list(args), 0, "", "")

        # ROOT указывает на файл, а не каталог: mkdir(parents=True) под ним
        # обязан провалиться (NotADirectoryError, подкласс OSError).
        bad_root = self.root / "not-a-dir"
        bad_root.write_text("x", encoding="utf-8")
        with mock.patch.object(config, "ROOT", bad_root), \
                mock.patch.object(gitcmd, "git", fake_git):
            fsm_postmerge._generate_and_commit_retro(self.conn, self.TASK, "a" * 40)

        self.assertEqual(git_calls, [])
        incidents = self.incidents()
        self.assertEqual(len(incidents), 1)
        self.assertTrue(incidents[0]["source"].startswith("fsm.retro"))

    def test_add_failure_raises_incident_and_skips_commit(self):
        def fake_git(*args) -> subprocess.CompletedProcess:
            if args and args[0] == "add":
                return subprocess.CompletedProcess(list(args), 1, "",
                                                   "стенд: add упал")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(gitcmd, "git", fake_git):
            fsm_postmerge._generate_and_commit_retro(self.conn, self.TASK, "a" * 40)

        incidents = self.incidents()
        self.assertEqual(len(incidents), 1)
        self.assertTrue(incidents[0]["source"].startswith("fsm.retro"))
        self.assertIn("add", incidents[0]["message"])

    def test_commit_failure_raises_incident(self):
        def fake_git(*args) -> subprocess.CompletedProcess:
            if args and args[0] == "commit":
                return subprocess.CompletedProcess(list(args), 1, "",
                                                   "стенд: commit упал")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(gitcmd, "git", fake_git):
            fsm_postmerge._generate_and_commit_retro(self.conn, self.TASK, "a" * 40)

        incidents = self.incidents()
        self.assertEqual(len(incidents), 1)
        self.assertIn("стенд: commit упал", incidents[0]["message"])

    def test_generation_exception_raises_incident_and_still_tries_debts(self):
        killed_id = "T901"
        store.insert_task(self.conn, killed_id, "Убитая", "killed",
                          "task/t901-x", config.DEFAULT_TARGET, 50.0)
        git_calls = []

        def fake_git(*args) -> subprocess.CompletedProcess:
            git_calls.append(args)
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(gitcmd, "git", fake_git), \
                mock.patch.object(retro, "build_done",
                                  side_effect=RuntimeError("бум")):
            fsm_postmerge._generate_and_commit_retro(self.conn, self.TASK, "a" * 40)

        self.assertFalse(retro.retro_path(self.TASK).exists())
        incidents = self.incidents()
        self.assertTrue(any(i["source"].startswith("fsm.retro")
                            and "бум" in i["message"] for i in incidents))
        # Долг killed-задачи не должен пострадать от провала done-пути.
        self.assertTrue(retro.retro_path(killed_id).exists())

    def test_killed_debt_is_picked_up_and_committed_separately(self):
        killed_id = "T901"
        store.insert_task(self.conn, killed_id, "Убитая", "killed",
                          "task/t901-x", config.DEFAULT_TARGET, 50.0)
        store.journal(self.conn, killed_id, "operator", "state -> killed",
                     "kill switch")
        git_calls = []

        def fake_git(*args) -> subprocess.CompletedProcess:
            git_calls.append(args)
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(gitcmd, "git", fake_git):
            fsm_postmerge._generate_and_commit_retro(self.conn, self.TASK, "a" * 40)

        self.assertTrue(retro.retro_path(killed_id).exists())
        self.assertIn("kill switch",
                      retro.retro_path(killed_id).read_text(encoding="utf-8"))
        commit_messages = [" ".join(c) for c in git_calls if c[0] == "commit"]
        self.assertEqual(len(commit_messages), 2)
        self.assertTrue(any(killed_id in m for m in commit_messages))
        self.assertEqual(self.incidents(), [])

    def test_killed_task_with_existing_retro_file_is_not_regenerated(self):
        killed_id = "T901"
        store.insert_task(self.conn, killed_id, "Убитая", "killed",
                          "task/t901-x", config.DEFAULT_TARGET, 50.0)
        retro.retro_path(killed_id).parent.mkdir(parents=True, exist_ok=True)
        retro.retro_path(killed_id).write_text("уже есть\n", encoding="utf-8")

        with mock.patch.object(gitcmd, "git", fake_git):
            fsm_postmerge._generate_and_commit_retro(self.conn, self.TASK, "a" * 40)

        self.assertEqual(
            retro.retro_path(killed_id).read_text(encoding="utf-8"),
            "уже есть\n")

    def test_killed_debt_commit_failure_attributes_incident_to_debt_not_task(self):
        killed_id = "T901"
        debt_target = "sled"
        store.insert_task(self.conn, killed_id, "Убитая", "killed",
                          "task/t901-x", debt_target, 50.0)
        store.journal(self.conn, killed_id, "operator", "state -> killed",
                     "kill switch")

        def fake_git(*args) -> subprocess.CompletedProcess:
            if args and args[0] == "commit" and killed_id in args[-1]:
                return subprocess.CompletedProcess(list(args), 1, "",
                                                   "стенд: commit долга упал")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(gitcmd, "git", fake_git):
            fsm_postmerge._generate_and_commit_retro(self.conn, self.TASK, "a" * 40)

        debt_journal = "\n".join(
            f"{s['action']} {s['detail']}"
            for s in store.task_steps(self.conn, killed_id))
        task_journal = "\n".join(
            f"{s['action']} {s['detail']}"
            for s in store.task_steps(self.conn, self.TASK))
        self.assertIn("RETRO FAILED", debt_journal,
                      "провал коммита killed-долга должен уйти в журнал "
                      "убитой задачи (debt_id), не мержащейся")
        self.assertNotIn("RETRO FAILED", task_journal,
                         "мержащаяся задача не должна получить чужую "
                         "запись о провале RETRO killed-долга")

        incidents = self.incidents()
        self.assertEqual(len(incidents), 1)
        self.assertEqual(
            incidents[0]["target"], debt_target,
            "incident-алерт должен уйти в target killed-задачи-долга, "
            "не в target мержащейся задачи (мультитаргет)")

    def test_killed_debt_generation_failure_attributes_incident_to_debt_not_task(self):
        killed_id = "T901"
        store.insert_task(self.conn, killed_id, "Убитая", "killed",
                          "task/t901-x", config.DEFAULT_TARGET, 50.0)
        store.journal(self.conn, killed_id, "operator", "state -> killed",
                     "kill switch")

        with mock.patch.object(gitcmd, "git", fake_git), \
                mock.patch.object(retro, "build_killed",
                                  side_effect=RuntimeError("бум долга")):
            fsm_postmerge._generate_and_commit_retro(self.conn, self.TASK, "a" * 40)

        debt_journal = "\n".join(
            f"{s['action']} {s['detail']}"
            for s in store.task_steps(self.conn, killed_id))
        task_journal = "\n".join(
            f"{s['action']} {s['detail']}"
            for s in store.task_steps(self.conn, self.TASK))
        self.assertIn("RETRO FAILED", debt_journal,
                      "провал генерации killed-долга должен уйти в журнал "
                      "убитой задачи (debt_id), не мержащейся")
        self.assertNotIn("RETRO FAILED", task_journal,
                         "мержащаяся задача не должна получить чужую "
                         "запись о провале генерации RETRO killed-долга")

    def test_no_killed_debts_means_only_done_commit(self):
        git_calls = []

        def fake_git(*args) -> subprocess.CompletedProcess:
            git_calls.append(args)
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(gitcmd, "git", fake_git):
            fsm_postmerge._generate_and_commit_retro(self.conn, self.TASK, "a" * 40)

        commit_messages = [c for c in git_calls if c[0] == "commit"]
        self.assertEqual(len(commit_messages), 1)


if __name__ == "__main__":
    unittest.main()
