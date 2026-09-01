"""Приёмочный тест T093 — AC-3 (tasks/T093/SPEC.md, «Критерии приёмки»).

AC-3: «Для каждого файла из списка требования 6, изменённого диффом,
PLAN.md несёт явную ссылку на фактуру — минимум два номера задач/
инцидентов урока, из которого сделана правка (соответствие перечню
AC-1).»

Зелёный с рождения: текущая ветка (роль test_author) не правит ни
одного файла из списка требования 6 — `_changed_req6_files()` возвращает
пустой список, и тест самопропускается (`skipTest`). Как только
разработчик поправит любой файл требования 6 без парного абзаца с двумя
номерами T\\d+ рядом с его путём в PLAN.md, тест перестаёт пропускаться
и падает на явном списке недостающих файлов.

Проверка — по литеральному вхождению пути файла требования 6 в текст
PLAN.md: абзац (блок между пустыми строками), где путь встретился,
обязан нести минимум два разных номера T\\d+. Абзац, а не строка —
формулировка ссылки на фактуру обычно длиннее одной строки, а SPEC не
диктует более узкий формат (требование 3 отдаёт формулировку
разработчику).
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _lessons  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN_PATH = REPO_ROOT / "tasks" / "T093" / "PLAN.md"


class Ac3PlanCitesEvidenceTest(unittest.TestCase):

    @staticmethod
    def _git(*args):
        res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True)
        return res.stdout.strip()

    def _changed_req6_files(self):
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD")
        if branch == "main":
            self.skipTest("рабочее дерево на main — диффить не с чем")
        merge_base = self._git("merge-base", "main", branch)
        changed = self._git("diff", "--name-only", merge_base,
                            branch).splitlines()
        return [p for p in changed if p in _lessons.REQ6_FILES]

    def test_ac3_every_edited_req6_file_has_two_number_citation_in_plan(self):
        changed = self._changed_req6_files()
        if not changed:
            self.skipTest("дифф не правит ни один файл из списка "
                          "требования 6 — сверять ссылку на фактуру не "
                          "с чем")

        self.assertTrue(
            PLAN_PATH.exists(),
            f"дифф правит файлы требования 6 {changed}, но "
            f"tasks/T093/PLAN.md отсутствует — AC-3 требует ссылку на "
            f"фактуру именно в PLAN.md")
        text = PLAN_PATH.read_text(encoding="utf-8")
        paragraphs = re.split(r"\n\s*\n", text)

        missing = []
        for path in changed:
            hosting = [p for p in paragraphs if path in p]
            if not hosting or not any(
                    len(_lessons.refs_in(p)) >= 2 for p in hosting):
                missing.append(path)

        self.assertEqual(
            missing, [],
            f"PLAN.md не несёт для этих файлов требования 6 абзаца с "
            f"минимум двумя номерами задач/инцидентов рядом с путём "
            f"файла (AC-3): {missing}")


if __name__ == "__main__":
    unittest.main()
