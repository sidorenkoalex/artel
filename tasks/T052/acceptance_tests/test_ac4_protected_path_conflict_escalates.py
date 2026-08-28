"""AC-4 (tasks/T052/SPEC.md): если конфликтующие файлы из AC-3
пересекаются с защищёнными путями (`gates.yaml`, `roles.yaml`,
`.github/`, `templates/`, `skills/`), задача вместо перехода в `in_dev`
переходит в `escalated`; `main` приводится в чистое состояние тем же
`git merge --abort`.

Песочница — `_sandbox.MergeGateRealGitTest` (настоящий git), тем же
доводом, что AC-3.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from _sandbox import MergeGateRealGitTest  # noqa: E402


class ProtectedPathConflictEscalatesTest(MergeGateRealGitTest):

    def test_ac4_conflict_touching_protected_path_escalates(self):
        # gates.yaml — один из пяти защищённых путей, названных SPEC
        # (требование 2 / AC-4), уже существует в базовом коммите
        # песочницы (_sandbox.MergeGateRealGitTest.setUp).
        branch_sha, main_sha = self.make_conflicting_branch(
            "gates.yaml", "task: true\n", "main: true\n")

        self.approve()

        self.assertEqual(
            self.state(), "escalated",
            "конфликт, затрагивающий защищённый путь (gates.yaml), обязан "
            "эскалировать, а не возвращать задачу в in_dev")

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


if __name__ == "__main__":
    unittest.main()
