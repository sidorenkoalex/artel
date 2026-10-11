"""Приёмочный тест T093 — AC-2 (tasks/T093/SPEC.md, «Критерии приёмки»).

AC-2: «Каждый файл, изменённый диффом задачи, — один из: список
требования 6 ..., файлы внутри tasks/T093/, либо (только если PLAN
выбрал способ (а) требования 7) секция «Предложения системе» артефакта
задачи, чья запись дистиллирована. Файлов вне этого перечня в диффе
нет.»

Зелёный с рождения: на этой ветке пока нет ни одного коммита
разработчика — только SPEC.md/TZ.md аналитика/Оператора и этот каталог
acceptance_tests/ (роль test_author), поэтому дифф с main касается
только tasks/T093/, что укладывается в перечень AC-2. Тест краснеет,
только если дифф тронет путь вне перечня — тот же приём реального
`git diff --name-only` рабочей ветки против main, что
tasks/T079/acceptance_tests/test_ac14_path_scope.py и
tasks/T046/acceptance_tests/test_predlozheniya_sisteme.py
(`ProtectedPathsTest`), только наоборот по смыслу: этой задаче мандат
(SPEC, требование 6, прецедент tasks/T085/SPEC.md AC-6 +
tasks/T085/ANSWER-1.md) разрешает править перечисленные skills/ и
templates/ файлы напрямую в этой же ветке — тест не запрещает эти пути
целиком, а сверяет их с точным списком имён файлов требования 6.

«Секция «Предложения системе» артефакта задачи, чья запись
дистиллирована» (способ (а) требования 7) — это PLAN.md или REVIEW.md
ЧУЖОЙ задачи (T093 сам эту секцию несёт в собственных PLAN.md/REVIEW.md,
уже покрытых префиксом tasks/T093/); секция — не отдельный файл, но
единственные файлы, где она физически живёт по шаблонам
`templates/PLAN.md`/`templates/REVIEW.md`, — это `tasks/<n>/PLAN.md` и
`tasks/<n>/REVIEW.md».
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

FOREIGN_PLAN_OR_REVIEW_RE = re.compile(r"^tasks/T\d+/(?:PLAN|REVIEW)\.md$")


class Ac2DiffScopeTest(unittest.TestCase):

    @staticmethod
    def _git(*args):
        res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True)
        return res.stdout.strip()

    def _changed_files(self):
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD")
        if branch == "main":
            self.skipTest("рабочее дерево на main — диффить не с чем")
        merge_base = self._git("merge-base", "main", branch)
        changed = self._git("diff", "--name-only", merge_base,
                            branch).splitlines()
        return [p for p in changed if p]

    def test_ac2_every_changed_file_is_within_allowed_scope(self):
        changed = self._changed_files()
        offending = []
        for path in changed:
            if path in _lessons.REQ6_FILES:
                continue
            if path.startswith("tasks/T093/"):
                continue
            if FOREIGN_PLAN_OR_REVIEW_RE.match(path):
                continue
            offending.append(path)

        self.assertEqual(
            offending, [],
            f"дифф ветки правит файлы вне перечня AC-2 (список "
            f"требования 6, tasks/T093/, либо PLAN.md/REVIEW.md чужой "
            f"задачи по способу (а) требования 7): {offending}")


if __name__ == "__main__":
    unittest.main()
