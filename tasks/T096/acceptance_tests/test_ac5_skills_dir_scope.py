"""Приёмочный тест T096 — AC-5 (tasks/T096/SPEC.md, «Критерии приёмки»).

AC-5: Diff задачи не меняет ни один существующий файл каталога
`skills/`, кроме создания нового `skills/ui-standards.md`.

Мандат на этот единственный файл — SPEC, требование 3, прецедент
tasks/T093/SPEC.md (требование 6) / tasks/T085/SPEC.md (AC-6). Тест не
запрещает `skills/` целиком, а сверяет дифф с точным списком из одного
разрешённого имени.

Зелёный с рождения: на ветке задачи пока нет ни одного коммита
разработчика — только SPEC.md/TZ.md аналитика и этот каталог
acceptance_tests/ (роль test_author); дифф с main не касается ни одного
файла `skills/` вовсе, что укладывается в AC-5 (пустое множество —
частный случай «не меняет ни один файл, кроме...»). Тест краснеет, если
дифф правки задачи затронет `skills/`-файл, отличный от
`skills/ui-standards.md`, или изменит существующий файл `skills/`
вместо создания нового. Тот же приём `git diff --name-only` ветки
против main, что `tasks/T093/acceptance_tests/test_ac2_diff_scope.py`.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config  # noqa: E402

ALLOWED_NEW_SKILL_FILE = "skills/ui-standards.md"


class Ac5SkillsDirScopeTest(unittest.TestCase):

    @staticmethod
    def _git(*args):
        res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True)
        return res.stdout.strip()

    def _changed_with_status(self):
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD")
        if branch == config.MAIN_BRANCH:
            self.skipTest("рабочее дерево на main — диффить не с чем")
        merge_base = self._git("merge-base", config.MAIN_BRANCH, branch)
        out = self._git("diff", "--name-status", merge_base, branch)
        entries = []
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            entries.append((parts[0], parts[-1]))
        return entries

    def test_ac5_no_skills_file_changed_except_new_ui_standards(self):
        entries = self._changed_with_status()
        skills_entries = [(status, path) for status, path in entries
                          if path.startswith("skills/")]

        offending = [(status, path) for status, path in skills_entries
                    if path != ALLOWED_NEW_SKILL_FILE]
        self.assertEqual(
            offending, [],
            f"дифф правит файлы skills/ вне мандата AC-5 (разрешён "
            f"только новый {ALLOWED_NEW_SKILL_FILE}): {offending}")

        for status, path in skills_entries:
            if path == ALLOWED_NEW_SKILL_FILE:
                self.assertEqual(
                    status, "A",
                    f"AC-5 требует, чтобы {ALLOWED_NEW_SKILL_FILE} был "
                    f"СОЗДАН (git status 'A'), а не изменением "
                    f"существующего файла (получен статус {status!r})")


if __name__ == "__main__":
    unittest.main()
