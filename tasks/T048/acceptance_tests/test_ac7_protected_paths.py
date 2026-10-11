"""AC-7 (tasks/T048/SPEC.md): дифф задачи не затрагивает защищённые
пути — `.github/`, `skills/`, `templates/`, `docs/invariants.md` — по
образцу `tasks/T043/acceptance_tests/test_retro_protected_paths.py`,
расширенному точным файлом `docs/invariants.md` (SPEC T048 называет его
отдельно от директорий-префиксов, не как каталог).
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

PROTECTED_PREFIXES = (".github/", "skills/", "templates/")
PROTECTED_FILES = ("docs/invariants.md",)


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
                    if p.startswith(PROTECTED_PREFIXES)
                    or p in PROTECTED_FILES]
        self.assertEqual(
            offending, [],
            f"дифф ветки {branch} относительно main трогает защищённые "
            f"пути: {offending}")


if __name__ == "__main__":
    unittest.main()
