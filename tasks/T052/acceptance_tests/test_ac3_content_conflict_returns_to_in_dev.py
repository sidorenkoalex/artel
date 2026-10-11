"""AC-3 (tasks/T052/SPEC.md): при `approve` из `merge_gate`, если
`git merge` завершается содержательным конфликтом (не разрешён
автоматически), оркестратор выполняет `git merge --abort`, `main`
остаётся в чистом состоянии (без незавершённого merge), задача
переходит `merge_gate -> in_dev`, а перечень конфликтующих файлов
записывается в журнал.

Песочница — `_sandbox.MergeGateRealGitTest` (настоящий git, тем же
доводом, что `tasks/T051/acceptance_tests/_sandbox.py`): содержательный
конфликт, `git merge --abort` и чистоту main заглушкой `subprocess.run`
не воспроизвести.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from _sandbox import MergeGateRealGitTest  # noqa: E402


class ContentConflictReturnsToInDevTest(MergeGateRealGitTest):

    def test_ac3_content_conflict_returns_to_in_dev_with_files_journaled(self):
        branch_sha, main_sha = self.make_conflicting_branch(
            "shared.txt", "правка ветки задачи\n", "правка main\n")

        self.approve()

        self.assertEqual(self.state(), "in_dev",
                         "содержательный конфликт обязан вернуть задачу в in_dev")

        self.assertEqual(self.branch_head(), branch_sha,
                         "ветка задачи не должна измениться merge-попыткой")
        self.assertEqual(self.main_head(), main_sha,
                         "main обязан остаться в чистом состоянии (merge --abort)")

        status = self.git("status", "--porcelain").stdout
        self.assertEqual(
            status.strip(), "",
            "рабочее дерево main не должно остаться в конфликтном "
            "состоянии — git merge --abort обязан быть выполнен")
        self.assertFalse(
            (self.root / ".git" / "MERGE_HEAD").exists(),
            "незавершённый merge (MERGE_HEAD) не должен остаться")
        content = (self.root / "shared.txt").read_text(encoding="utf-8")
        self.assertNotIn("<<<<<<<", content,
                         "конфликт-маркеры не должны просочиться в main")

        journal = "\n".join(self.journal_details())
        self.assertIn("shared.txt", journal,
                     "перечень конфликтующих файлов обязан попасть в журнал")


if __name__ == "__main__":
    unittest.main()
