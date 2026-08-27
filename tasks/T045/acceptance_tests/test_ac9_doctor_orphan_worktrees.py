"""AC-9 (tasks/T045/SPEC.md): сироты-worktree в doctor.

Проверка сирот-worktree в `doctor` не считает сиротой легитимный
per-task worktree в стандартном месте, принадлежащий известной задаче;
worktree вне этого соответствия по-прежнему считается сиротой.

По образцу tests/test_doctor.py `OrphansTest`: `gitcmd.git` подменяется
заготовленным `worktree list --porcelain`, реальный git не нужен — это
проверка ЧТЕНИЯ списка, не самой worktree-механики (та — в
test_ac1_ac2/test_ac5/test_ac6_ac7).
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import alerts, catalog, config, doctor, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


class OrphanWorktreeStandardPlaceTest(TmpRootTest):

    KNOWN_ID = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        # Известная задача — прямой строкой БД (по образцу
        # tests/test_doctor.py OrphansTest.test_done_task_branch_not_
        # cleaned_up): cmd_new читает templates/SPEC.md с config.ROOT,
        # которого в этой лёгкой песочнице (TmpRootTest) нет, а самому
        # критерию нужна только строка задачи в БД, не артефакт.
        store.insert_task(store.db(), self.KNOWN_ID, "Известная задача",
                          "in_dev", f"task/{self.KNOWN_ID.lower()}-x",
                          config.DEFAULT_TARGET, 25.0)
        self.known_id = self.KNOWN_ID

    def porcelain(self, *paths: str) -> str:
        entries = [f"worktree {self.root}\nHEAD 0000000000000000000000000000"
                  f"0000000000\n\n"]
        for p in paths:
            entries.append(f"worktree {p}\nHEAD 111111111111111111111111111"
                           f"1111111111111\n\n")
        return "".join(entries)

    def check(self, porcelain: str):
        with mock.patch.object(
                doctor.gitcmd, "git",
                lambda *a: subprocess.CompletedProcess(list(a), 0, porcelain, "")):
            return doctor.check_orphans(store.db())

    def test_ac9_legitimate_per_task_worktree_is_not_flagged_as_orphan(self):
        legit = str(config.ROOT / ".artel" / "worktrees" / self.known_id)

        checks = self.check(self.porcelain(legit))

        by_name = {c.name: c for c in checks}
        self.assertEqual(by_name["orphans-worktrees"].status, "ok",
                         by_name["orphans-worktrees"].detail)
        incidents = [a for a in alerts.open_alerts(store.db(), "incident")
                    if a["source"] == "doctor.orphans.worktree"]
        self.assertEqual(incidents, [])

    def test_ac9_worktree_outside_standard_place_is_still_an_orphan(self):
        checks = self.check(self.porcelain("/some/other/worktree"))

        by_name = {c.name: c for c in checks}
        self.assertEqual(by_name["orphans-worktrees"].status, "fail")
        incidents = [a for a in alerts.open_alerts(store.db(), "incident")
                    if a["source"] == "doctor.orphans.worktree"]
        self.assertEqual(len(incidents), 1)
        self.assertIn("/some/other/worktree", incidents[0]["message"])

    def test_ac9_worktree_at_standard_place_for_unknown_task_is_an_orphan(self):
        unknown = str(config.ROOT / ".artel" / "worktrees" / "T999")

        checks = self.check(self.porcelain(unknown))

        by_name = {c.name: c for c in checks}
        self.assertEqual(by_name["orphans-worktrees"].status, "fail")
        incidents = [a for a in alerts.open_alerts(store.db(), "incident")
                    if a["source"] == "doctor.orphans.worktree"]
        self.assertEqual(len(incidents), 1)
        self.assertIn(unknown, incidents[0]["message"])

    def test_ac9_legitimate_and_orphan_worktrees_together(self):
        legit = str(config.ROOT / ".artel" / "worktrees" / self.known_id)
        stray = "/some/other/worktree"

        checks = self.check(self.porcelain(legit, stray))

        by_name = {c.name: c for c in checks}
        self.assertEqual(by_name["orphans-worktrees"].status, "fail")
        self.assertNotIn(legit, by_name["orphans-worktrees"].detail)
        self.assertIn(stray, by_name["orphans-worktrees"].detail)


if __name__ == "__main__":
    unittest.main()
