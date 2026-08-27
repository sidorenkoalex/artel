"""Приёмочные тесты T043 — защищённые пути не затронуты в диффе задачи
(SPEC.md, AC-7), по образцу
`tasks/T042/acceptance_tests/test_map_regen_on_merge.py`
(`ProtectedPathsUntouchedTest`), расширенному `templates/` (требование 11
SPEC называет три пути: `.github/`, `skills/`, `templates/`, T042 —
только первые два)."""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

PROTECTED_PREFIXES = (".github/", "skills/", "templates/")


class ProtectedPathsUntouchedTest(unittest.TestCase):
    """AC-7: реальная проверка диффа текущей ветки задачи относительно
    `main` — без единого мока, тем же принципом, что и `protected-paths`
    в `.github/workflows/ci.yml`."""

    @staticmethod
    def _git(*args: str) -> str:
        res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True)
        return res.stdout.strip()

    def test_ac7_branch_diff_does_not_touch_protected_paths(self):
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD")
        if branch == "main":
            self.skipTest("рабочее дерево на main — диффить не с чем")
        merge_base = self._git("merge-base", "main", branch)
        changed = self._git("diff", "--name-only", merge_base,
                            branch).splitlines()
        offending = [p for p in changed
                    if p.startswith(PROTECTED_PREFIXES)]
        self.assertEqual(
            offending, [],
            f"дифф ветки {branch} относительно main трогает защищённые "
            f"пути: {offending}")


if __name__ == "__main__":
    unittest.main()
