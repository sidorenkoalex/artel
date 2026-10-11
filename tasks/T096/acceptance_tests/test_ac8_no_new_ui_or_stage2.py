"""Приёмочный тест T096 — AC-8 (tasks/T096/SPEC.md, «Критерии приёмки»).

AC-8: Diff задачи не создаёт новых UI-поверхностей и не касается
демона/панели этапа 2.

«Новая UI-поверхность» и «демон/панель этапа 2» не заданы SPEC как
точный список путей (в отличие от AC-5/AC-6/AC-7, у которых есть точное
имя файла) — unittest не может судить о семантике «это UI-поверхность
или нет» по произвольному новому пути. Но объём диффа задачи ограничен
требованиями 1-4 SPEC (docs/design-system.md, skills/ui-standards.md,
косметика orchestrator/report.py, tasks/T096/*) — вне этого списка
задача НИЧЕГО не создаёт и не трогает по своему собственному объёму
(«Не входит»). Поэтому AC-8 проверяется механически как замкнутость
диффа этим списком: любой путь вне него — по построению либо новая
UI-поверхность/файл демона/панели, либо иное расширение объёма, которое
AC-8 запрещает так же, как и первые два явно названных случая.

Зелёный с рождения: на ветке задачи пока нет ни одного коммита
разработчика — дифф с main укладывается в разрешённый список (только
tasks/T096/SPEC.md и tasks/T096/TZ.md, оба под префиксом tasks/T096/).
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config  # noqa: E402

ALLOWED_EXACT = {
    "docs/design-system.md",
    "skills/ui-standards.md",
    "orchestrator/report.py",
    "docs/codebase-map.md",
}
ALLOWED_PREFIX = "tasks/T096/"


class Ac8NoNewUiOrStage2Test(unittest.TestCase):

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

    def test_ac8_diff_stays_within_task_scope(self):
        changed = self._changed_files()

        offending = [p for p in changed
                    if p not in ALLOWED_EXACT
                    and not p.startswith(ALLOWED_PREFIX)]

        self.assertEqual(
            offending, [],
            f"дифф ветки выходит за объём задачи (SPEC требования 1-4): "
            f"{offending} — AC-8 запрещает новые UI-поверхности и "
            f"демона/панель этапа 2, объём задачи не покрывает пути вне "
            f"docs/design-system.md, skills/ui-standards.md, "
            f"orchestrator/report.py и tasks/T096/*")


if __name__ == "__main__":
    unittest.main()
