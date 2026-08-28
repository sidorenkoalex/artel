"""AC-6, AC-7 (tasks/T049/SPEC.md).

AC-6: manual/skip — см. маркер ниже.

AC-7: «Защищённые пути (`.github/`, `skills/`, `templates/`,
`docs/invariants.md`) не затронуты диффом задачи напрямую — изменения к
ним оформлены отдельным подготовленным диффом для Оператора.» Реальная
проверка диффа текущей ветки относительно `main`, без моков — по образцу
tasks/T048/acceptance_tests/test_ac7_protected_paths.py (тот же набор
защищённых путей, тот же критерий дословно) и
tasks/T043/acceptance_tests/test_retro_protected_paths.py.
"""

# AC-6: skip — «полный набор тестов (tests/) зелёный» уже исполняется
# штатным CI-гейтом (`.github/workflows/ci.yml`, джоб `python`,
# `unittest discover -s tests -v`) на каждый коммит ветки задачи и
# требуется `merge_gate` (orchestrator/fsm.py, cmd_approve при
# state == "merge_gate") — тот же довод, что и в
# tasks/T044/acceptance_tests/test_lease_readonly_and_doctor.py (AC-7
# там) и tasks/T046/acceptance_tests/test_predlozheniya_sisteme.py
# (AC-4 там). Повторный subprocess-прогон здесь ловил бы окружение
# машины разработчика, а не дефект этой задачи, и не даёт новой гарантии
# сверх штатного гейта.

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

PROTECTED_PREFIXES = (".github/", "skills/", "templates/")
PROTECTED_FILES = ("docs/invariants.md",)


class ProtectedPathsUntouchedTest(unittest.TestCase):
    """AC-7: реальный дифф текущей ветки относительно `main`, без единого
    мока — тем же принципом, что и `protected-paths` в
    `.github/workflows/ci.yml`."""

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
            f"пути напрямую: {offending} (SPEC T049, AC-7 — эти правки "
            f"идут подготовленным диффом Оператору, не прямым коммитом)")


if __name__ == "__main__":
    unittest.main()
