"""AC-14 (tasks/T079/SPEC.md): реализация ограничена `orchestrator/`
(новые/изменённые модули), `tests/` и `docs/codebase-map.md`; ни один
путь из `no_paths` target `artel` (`gates.yaml`, `roles.yaml`,
`targets.yaml`, `.github/`, `templates/`, `skills/`,
`docs/invariants.md`, `tests/test_invariants.py`, `CLAUDE.md`) не
меняется.

Зелёный с рождения: на ветке задачи без единого коммита разработчика
(только артефакты test_author/analyst) дифф с `main` не касается ни
`no_paths`, ни путей вне `orchestrator/`/`tests/`/`docs/codebase-map.md`
— краснеет только при нарушении требования кодом задачи. Тот же приём,
что `tasks/T073/acceptance_tests/test_ac11_invariants_untouched.py` и
`tasks/T063/acceptance_tests/test_retro_suite_and_docs_untouched.py`
(AC-5 там): реальный `git diff --name-only` ветки против `main`, не
подмена.

Список запрещённых путей и regex `PROTECTED` — дословно из
`.github/workflows/ci.yml`, джоб `protected-paths` (действующий
enforcement no_paths, targets.yaml — комментарий поля): тест не
изобретает своё сопоставление путей, а сверяет то же, что и CI-гейт.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

# Дословно из .github/workflows/ci.yml, джоб protected-paths.
PROTECTED = re.compile(
    r"^(gates\.yaml|roles\.yaml|targets\.yaml|CLAUDE\.md|\.github/|"
    r"templates/|skills/|tests/test_invariants\.py|docs/invariants\.md)")

# AC-14, первое предложение: единственные разрешённые зоны изменений
# КОДА («реализация»). `tasks/` — не код, а артефакты жизненного цикла
# задачи (SPEC.md, PLAN.md, REVIEW.md, acceptance_tests/ этого же
# каталога) — их коммитит каждая роль по своему скилу (conventions-core),
# и AC-14 их не ограничивает (речь о «реализации», не о процессе).
ALLOWED_PREFIXES = ("orchestrator/", "tests/", "docs/codebase-map.md",
                    "tasks/")


class PathScopeTest(unittest.TestCase):

    @staticmethod
    def _git(*args: str) -> str:
        res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True)
        return res.stdout.strip()

    def _changed_files(self) -> list[str]:
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD")
        if branch == "main":
            self.skipTest("рабочее дерево на main — диффить не с чем")
        merge_base = self._git("merge-base", "main", branch)
        changed = self._git("diff", "--name-only", merge_base,
                            branch).splitlines()
        return [p for p in changed if p]

    def test_ac14_branch_diff_does_not_touch_protected_paths(self):
        changed = self._changed_files()

        offending = [p for p in changed if PROTECTED.match(p)]

        self.assertEqual(
            offending, [],
            f"дифф ветки относительно main правит защищённые пути "
            f"{offending} (SPEC T079 AC-14, no_paths target artel)")

    def test_ac14_branch_diff_stays_within_allowed_directories(self):
        changed = self._changed_files()

        outside = [p for p in changed
                  if not any(p == prefix or p.startswith(prefix)
                            for prefix in ALLOWED_PREFIXES)]

        self.assertEqual(
            outside, [],
            f"дифф ветки правит пути вне orchestrator/, tests/ и "
            f"docs/codebase-map.md: {outside} (SPEC T079 AC-14)")


if __name__ == "__main__":
    unittest.main()
