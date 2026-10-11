"""Приёмочный тест T096 — AC-6 (tasks/T096/SPEC.md, «Критерии приёмки»).

AC-6: Diff задачи не затрагивает `tasks/T080/mockup.html` (исторический
артефакт остаётся неизменным).

Зелёный с рождения: на ветке задачи пока нет ни одного коммита
разработчика — дифф с main не касается `tasks/T080/mockup.html`.
Тест краснеет, если будущий коммит разработчика тронет этот файл —
регрессия на «Не входит» SPEC («правки макета tasks/T080/mockup.html»).
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config  # noqa: E402

PROTECTED_PATH = "tasks/T080/mockup.html"


class Ac6MockupUntouchedTest(unittest.TestCase):

    @staticmethod
    def _git(*args):
        res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True)
        return res.stdout.strip()

    def _changed_files(self):
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD")
        if branch == config.MAIN_BRANCH:
            self.skipTest("рабочее дерево на main — диффить не с чем")
        merge_base = self._git("merge-base", config.MAIN_BRANCH, branch)
        changed = self._git("diff", "--name-only", merge_base,
                            branch).splitlines()
        return [p for p in changed if p]

    def test_ac6_mockup_not_in_branch_diff(self):
        changed = self._changed_files()
        self.assertNotIn(
            PROTECTED_PATH, changed,
            f"дифф ветки трогает {PROTECTED_PATH} — AC-6 запрещает "
            f"правки исторического макета")


if __name__ == "__main__":
    unittest.main()
