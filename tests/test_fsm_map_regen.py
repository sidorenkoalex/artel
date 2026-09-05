"""Юнит-тесты регенерации/коммита карты кодовой базы на merge_gate
(orchestrator/fsm_postmerge.py, tasks/T042/SPEC.md).

Функции по отдельности, не через `fsm.cmd_approve` целиком — сквозной путь
(AC-1..AC-3) уже покрывают приёмочные тесты
`tasks/T042/acceptance_tests/test_map_regen_on_merge.py`.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import alerts, fsm_postmerge, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest, fake_git  # noqa: E402

COMMITTED_MAP = ("---\nbuilt_at_sha: aaaa000011112222333344445555666677778888\n"
                 "---\n\n# Карта кодовой базы\n\nСодержимое A.\n")


class MapContentWithoutShaTest(unittest.TestCase):

    def test_only_built_at_sha_differs_is_equal(self):
        other = COMMITTED_MAP.replace(
            "aaaa000011112222333344445555666677778888",
            "dddd444455556666777788889999000011112222")

        self.assertEqual(fsm_postmerge._map_content_without_sha(COMMITTED_MAP),
                         fsm_postmerge._map_content_without_sha(other))

    def test_text_difference_is_not_equal(self):
        other = COMMITTED_MAP.replace("Содержимое A.", "Содержимое B.")

        self.assertNotEqual(fsm_postmerge._map_content_without_sha(COMMITTED_MAP),
                            fsm_postmerge._map_content_without_sha(other))


class RegenerateAndCommitMapTest(TmpRootTest):
    """Песочница: sandbox.TmpRootTest полным набором путей (SPEC T061,
    AC-3) — карта на месте, тот же приём, что `tests/test_brief.py`
    (`BriefUnitTest`)."""

    def setUp(self):
        super().setUp()
        (self.root / "docs").mkdir(parents=True)
        self.map_path = self.root / "docs" / "codebase-map.md"
        self.map_path.write_text(COMMITTED_MAP, encoding="utf-8")

        store.create_schema(store.db())
        self.conn = store.db()

    def incidents(self):
        return alerts.open_alerts(self.conn, "incident")

    def test_content_changed_is_added_and_committed(self):
        regenerated = COMMITTED_MAP.replace(
            "aaaa000011112222333344445555666677778888",
            "cccc111122223333444455556666777788889999",
        ).replace("Содержимое A.", "Содержимое B.")
        git_calls = []

        def fake_git(*args) -> subprocess.CompletedProcess:
            git_calls.append(args)
            return subprocess.CompletedProcess(list(args), 0, "", "")

        def fake_run(cmd, **kwargs) -> subprocess.CompletedProcess:
            self.map_path.write_text(regenerated, encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with mock.patch.object(gitcmd, "git", fake_git), \
                mock.patch("subprocess.run", side_effect=fake_run):
            fsm_postmerge._regenerate_and_commit_map(self.conn, "T001")

        self.assertIn(("add", fsm_postmerge.MAP_REL), git_calls)
        commit_calls = [c for c in git_calls if c[0] == "commit"]
        self.assertEqual(len(commit_calls), 1)
        message = " ".join(commit_calls[0])
        self.assertIn("T001", message)
        self.assertIn("регенерация", message.lower())
        self.assertNotIn(("checkout", "--", fsm_postmerge.MAP_REL), git_calls)
        self.assertEqual(self.incidents(), [])

    def test_only_built_at_sha_changed_restores_and_does_not_commit(self):
        regenerated = COMMITTED_MAP.replace(
            "aaaa000011112222333344445555666677778888",
            "dddd444455556666777788889999000011112222")
        git_calls = []

        def fake_git(*args) -> subprocess.CompletedProcess:
            git_calls.append(args)
            if args and args[0] == "checkout":
                self.map_path.write_text(COMMITTED_MAP, encoding="utf-8")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        def fake_run(cmd, **kwargs) -> subprocess.CompletedProcess:
            self.map_path.write_text(regenerated, encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with mock.patch.object(gitcmd, "git", fake_git), \
                mock.patch("subprocess.run", side_effect=fake_run):
            fsm_postmerge._regenerate_and_commit_map(self.conn, "T001")

        self.assertIn(("checkout", "--", fsm_postmerge.MAP_REL), git_calls)
        self.assertFalse(any(c[0] in ("add", "commit") for c in git_calls))
        self.assertEqual(self.map_path.read_text(encoding="utf-8"),
                         COMMITTED_MAP)
        self.assertEqual(self.incidents(), [])

    def test_regeneration_failure_raises_incident_and_does_not_commit(self):
        fail = subprocess.CompletedProcess(
            ["python3"], 1, "", "стенд: генератор карты упал")

        with mock.patch.object(gitcmd, "git", fake_git), \
                mock.patch("subprocess.run", return_value=fail) as run_mock:
            fsm_postmerge._regenerate_and_commit_map(self.conn, "T001")

        run_mock.assert_called_once()
        incidents = self.incidents()
        self.assertEqual(len(incidents), 1)
        self.assertTrue(incidents[0]["source"].startswith("fsm.map_regen"))
        self.assertIn("стенд: генератор карты упал", incidents[0]["message"])
        self.assertEqual(self.map_path.read_text(encoding="utf-8"),
                         COMMITTED_MAP, "провал регенерации — карта не тронута")

    def test_add_failure_raises_incident_and_does_not_call_commit(self):
        regenerated = COMMITTED_MAP.replace("Содержимое A.", "Содержимое B.")
        git_calls = []

        def fake_git(*args) -> subprocess.CompletedProcess:
            git_calls.append(args)
            if args and args[0] == "add":
                return subprocess.CompletedProcess(
                    list(args), 1, "", "стенд: add упал")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        def fake_run(cmd, **kwargs) -> subprocess.CompletedProcess:
            self.map_path.write_text(regenerated, encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with mock.patch.object(gitcmd, "git", fake_git), \
                mock.patch("subprocess.run", side_effect=fake_run):
            fsm_postmerge._regenerate_and_commit_map(self.conn, "T001")

        self.assertFalse(any(c[0] == "commit" for c in git_calls),
                         "add упал — коммитить нечего")
        incidents = self.incidents()
        self.assertEqual(len(incidents), 1)
        self.assertTrue(incidents[0]["source"].startswith("fsm.map_regen"))

    def test_commit_failure_raises_incident(self):
        regenerated = COMMITTED_MAP.replace("Содержимое A.", "Содержимое B.")

        def fake_git(*args) -> subprocess.CompletedProcess:
            if args and args[0] == "commit":
                return subprocess.CompletedProcess(
                    list(args), 1, "", "стенд: commit упал")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        def fake_run(cmd, **kwargs) -> subprocess.CompletedProcess:
            self.map_path.write_text(regenerated, encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with mock.patch.object(gitcmd, "git", fake_git), \
                mock.patch("subprocess.run", side_effect=fake_run):
            fsm_postmerge._regenerate_and_commit_map(self.conn, "T001")

        incidents = self.incidents()
        self.assertEqual(len(incidents), 1)
        self.assertTrue(incidents[0]["source"].startswith("fsm.map_regen"))
        self.assertIn("стенд: commit упал", incidents[0]["message"])

    def test_checkout_failure_after_no_content_diff_raises_incident(self):
        regenerated = COMMITTED_MAP.replace(
            "aaaa000011112222333344445555666677778888",
            "dddd444455556666777788889999000011112222")

        def fake_git(*args) -> subprocess.CompletedProcess:
            if args and args[0] == "checkout":
                return subprocess.CompletedProcess(
                    list(args), 1, "", "стенд: checkout упал")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        def fake_run(cmd, **kwargs) -> subprocess.CompletedProcess:
            self.map_path.write_text(regenerated, encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with mock.patch.object(gitcmd, "git", fake_git), \
                mock.patch("subprocess.run", side_effect=fake_run):
            fsm_postmerge._regenerate_and_commit_map(self.conn, "T001")

        incidents = self.incidents()
        self.assertEqual(len(incidents), 1)
        self.assertTrue(incidents[0]["source"].startswith("fsm.map_regen"))
        self.assertIn("стенд: checkout упал", incidents[0]["message"])

    def test_regeneration_oserror_raises_incident_and_does_not_commit(self):
        with mock.patch.object(gitcmd, "git", fake_git), \
                mock.patch("subprocess.run",
                           side_effect=FileNotFoundError("python3 не найден")) as run_mock:
            fsm_postmerge._regenerate_and_commit_map(self.conn, "T001")

        run_mock.assert_called_once()
        incidents = self.incidents()
        self.assertEqual(len(incidents), 1)
        self.assertTrue(incidents[0]["source"].startswith("fsm.map_regen"))
        self.assertIn("python3 не найден", incidents[0]["message"])
        self.assertEqual(self.map_path.read_text(encoding="utf-8"),
                         COMMITTED_MAP, "провал регенерации — карта не тронута")

    def test_second_read_oserror_raises_incident_and_does_not_commit(self):
        def fake_run(cmd, **kwargs) -> subprocess.CompletedProcess:
            self.map_path.unlink()
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with mock.patch.object(gitcmd, "git", fake_git), \
                mock.patch("subprocess.run", side_effect=fake_run):
            fsm_postmerge._regenerate_and_commit_map(self.conn, "T001")

        incidents = self.incidents()
        self.assertEqual(len(incidents), 1)
        self.assertTrue(incidents[0]["source"].startswith("fsm.map_regen"))
        self.assertIn("не прочитан", incidents[0]["message"])

    def test_missing_map_file_raises_incident(self):
        self.map_path.unlink()

        with mock.patch.object(gitcmd, "git", fake_git), \
                mock.patch("subprocess.run") as run_mock:
            fsm_postmerge._regenerate_and_commit_map(self.conn, "T001")

        run_mock.assert_not_called()
        incidents = self.incidents()
        self.assertEqual(len(incidents), 1)
        self.assertTrue(incidents[0]["source"].startswith("fsm.map_regen"))


class MapSizeJournalUnitTest(TmpRootTest):
    """01M1RFVWV6WWTXRC5F40K61632, требования 2, 5; AC-5..AC-7 — компактный
    юнит поверх приёмочной планки задачи (`tasks/
    01M1RFVWV6WWTXRC5F40K61632/acceptance_tests/
    test_fsm_map_size_journal.py`, покрывающей эти же критерии полно)."""

    def setUp(self):
        super().setUp()
        (self.root / "docs").mkdir(parents=True)
        self.map_path = self.root / "docs" / "codebase-map.md"
        self.map_path.write_text(COMMITTED_MAP, encoding="utf-8")
        store.create_schema(store.db())
        self.conn = store.db()

    def size_steps(self, task_id: str) -> list:
        return [r for r in store.task_steps(self.conn, task_id)
               if r["action"] == fsm_postmerge.MAP_SIZE_ACTION]

    def test_content_changed_writes_size_entry_with_stats_and_new_sha(self):
        """Ловит мутацию: запись «карта: размер» не пишется на ветке
        изменения содержимого, либо несёт sha ДО коммита карты, а не
        HEAD после его завершения (AC-5)."""
        regenerated = COMMITTED_MAP.replace("Содержимое A.", "Содержимое B.")

        def fake_git_commit(*args) -> subprocess.CompletedProcess:
            if args[:1] == ("commit",):
                return subprocess.CompletedProcess(list(args), 0, "", "")
            if args[:2] == ("rev-parse", "HEAD"):
                return subprocess.CompletedProcess(list(args), 0, "1" * 40, "")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        def fake_run(cmd, **kwargs) -> subprocess.CompletedProcess:
            self.map_path.write_text(regenerated, encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with mock.patch.object(gitcmd, "git", fake_git_commit), \
                mock.patch("subprocess.run", side_effect=fake_run):
            fsm_postmerge._regenerate_and_commit_map(self.conn, "T001")

        rows = self.size_steps("T001")
        self.assertEqual(len(rows), 1)
        detail = json.loads(rows[0]["detail"])
        self.assertEqual(detail["sha"], "1" * 40)
        self.assertEqual(detail["bytes_total"],
                         len(regenerated.encode("utf-8")))

    def test_unchanged_content_still_writes_size_entry(self):
        """Ловит мутацию: запись «карта: размер» пишется ТОЛЬКО на ветке
        изменения содержимого — на ветке отката (нет содержательных
        отличий) запись пропускается вместо того, чтобы описывать текст,
        реально оставшийся на диске (AC-6, ряд без пропусков)."""
        regenerated = COMMITTED_MAP.replace(
            "aaaa000011112222333344445555666677778888",
            "dddd444455556666777788889999000011112222")

        def fake_git_checkout(*args) -> subprocess.CompletedProcess:
            if args and args[0] == "checkout":
                self.map_path.write_text(COMMITTED_MAP, encoding="utf-8")
            if args[:2] == ("rev-parse", "HEAD"):
                return subprocess.CompletedProcess(list(args), 0, "0" * 40, "")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        def fake_run(cmd, **kwargs) -> subprocess.CompletedProcess:
            self.map_path.write_text(regenerated, encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with mock.patch.object(gitcmd, "git", fake_git_checkout), \
                mock.patch("subprocess.run", side_effect=fake_run):
            fsm_postmerge._regenerate_and_commit_map(self.conn, "T001")

        rows = self.size_steps("T001")
        self.assertEqual(len(rows), 1)
        self.assertEqual(json.loads(rows[0]["detail"])["sha"], "0" * 40)

    def test_regeneration_failure_writes_no_size_entry(self):
        """Ловит мутацию: провал регенерации (путь `_map_regen_incident`)
        всё равно пишет запись «карта: размер» — нарушило бы AC-6
        («ряд без пропусков» превратился бы в ряд с шумом на провалах)."""
        fail = subprocess.CompletedProcess(["python3"], 1, "", "стенд: сбой")

        with mock.patch.object(gitcmd, "git", fake_git), \
                mock.patch("subprocess.run", return_value=fail):
            fsm_postmerge._regenerate_and_commit_map(self.conn, "T001")

        self.assertEqual(self.size_steps("T001"), [])


if __name__ == "__main__":
    unittest.main()
