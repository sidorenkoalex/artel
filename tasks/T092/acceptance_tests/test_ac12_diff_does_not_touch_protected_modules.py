"""AC-12 (tasks/T092/SPEC.md): дифф реализации не касается
`orchestrator/fsm.py`, `orchestrator/runner.py`, `orchestrator/auto.py`,
`orchestrator/doctor.py`.

По образцу `tasks/T043/acceptance_tests/test_retro_protected_paths.py`
(`ProtectedPathsUntouchedTest`) — реальный дифф ветки задачи относительно
`main`, без единого мока.

Зелёный с рождения: на момент написания этих тестов ветка задачи несёт
только SPEC/PLAN/тесты — ни один из четырёх файлов ещё не тронут,
проверка обязана оставаться зелёной и после реализации (AC-12 требует
это как инвариант диффа, не как временное состояние).
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

FORBIDDEN_FILES = (
    "orchestrator/fsm.py",
    "orchestrator/runner.py",
    "orchestrator/auto.py",
    "orchestrator/doctor.py",
)


class ProtectedModulesUntouchedTest(unittest.TestCase):

    @staticmethod
    def _git(*args: str) -> str:
        res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True)
        return res.stdout.strip()

    def test_ac12_branch_diff_does_not_touch_forbidden_modules(self):
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD")
        if branch == "main":
            self.skipTest("рабочее дерево на main — диффить не с чем")
        merge_base = self._git("merge-base", "main", branch)
        changed = self._git("diff", "--name-only", merge_base,
                            branch).splitlines()
        offending = [p for p in changed if p in FORBIDDEN_FILES]
        self.assertEqual(
            offending, [],
            f"дифф ветки {branch} относительно main трогает "
            f"защищённые этой задачей модули: {offending}")


if __name__ == "__main__":
    unittest.main()
