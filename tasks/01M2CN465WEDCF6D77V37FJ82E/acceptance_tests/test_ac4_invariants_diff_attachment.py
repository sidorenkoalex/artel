"""AC-4 — 01M2CN465WEDCF6D77V37FJ82E: `tests/test_invariants.py` не в
дифе кода ветки; новый инвариант приложен к PLAN.md unified-диффом,
проходящим `git apply --check` на чистом `main`.

Источник — SPEC.md, «Критерии приёмки»:

AC-4. Диф кода ветки задачи не содержит правок `tests/test_invariants.py`;
новый инвариант «после прогона — чисто» приложен к `PLAN.md` отдельным
unified diff по этому файлу, который проходит `git apply --check` на
чистом дереве `main`.

Оба условия критерия мехaнически проверяемы (тот же приём, что предписан
`skills/conventions-core.md`: «перед тем как сдать диф-приложение,
прогони `git apply --check` на чистом дереве»); backlog (docs/
backlog.md, запись 2) отдельно называет отсутствие именно такой проверки
дефектом практики — этот файл закрывает его для данной задачи, а не
опирается на ручную сверку Оператора, раз проверка не требует
человеческого суждения (в отличие от, например, содержательного текста
навыка — см. прецедент tasks/01M283NC4JJXK7QS68Y9ET8TBK/acceptance_tests/
test_ac6_coding_standards_skill_update.py, где критерий именно про
формулировку текста, а не про применимость диффа, помечен `manual`).

Красен до реализации: до правки разработчика `tasks/<id>/PLAN.md` ещё не
существует (создаёт роль developer) — `test_ac4_plan_attaches_an_
invariants_diff_that_applies_to_main` падает на отсутствии файла;
`tests/test_invariants.py` тем временем не тронут в этом рабочем
каталоге вовсе (ветка только что заведена от `main`), поэтому
`test_ac4_task_branch_diff_does_not_touch_test_invariants` уже зелёный —
это ожидаемо: он проверяет НЕГАТИВНОЕ условие («файла нет в дифе»), а не
позитивную работу, которую вносит эта задача.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402

TASK_ID = "01M2CN465WEDCF6D77V37FJ82E"
PLAN_PATH = _util.REPO_ROOT / "tasks" / TASK_ID / "PLAN.md"
TARGET_FILE = "tests/test_invariants.py"

_DIFF_BLOCK_RE = re.compile(
    r"```diff\n(diff --git a/" + re.escape(TARGET_FILE)
    + r" b/" + re.escape(TARGET_FILE) + r".*?)\n```", re.DOTALL)


class TaskBranchDoesNotTouchTestInvariantsTest(unittest.TestCase):

    def test_ac4_task_branch_diff_does_not_touch_test_invariants(self):
        """Диф ветки задачи (от точки расхождения с `main` до текущего
        рабочего дерева, включая незакоммиченное) не называет
        `tests/test_invariants.py` среди изменённых путей.

        Ловит мутацию: разработчик правит `tests/test_invariants.py`
        напрямую в коде ветки вместо приложения диффа к PLAN.md (SPEC
        «Не входит» это явно запрещает) — файл появится в списке
        изменённых путей, и `assertNotIn` покраснеет.
        """
        changed = _util.changed_paths_since_main()
        self.assertNotIn(
            TARGET_FILE, changed,
            f"{TARGET_FILE} не должен править код ветки задачи напрямую "
            f"— только приложением unified diff к PLAN.md (AC-4)")


class PlanAttachesApplicableInvariantsDiffTest(unittest.TestCase):

    def test_ac4_plan_attaches_an_invariants_diff_that_applies_to_main(self):
        """`PLAN.md` содержит фенсированный ```diff-блок с
        `diff --git a/tests/test_invariants.py b/tests/test_invariants.py`,
        и этот блок проходит `git apply --check` на чистом дереве `main`
        (отдельный git worktree во временном каталоге — не в
        `.artel/worktrees`, чтобы не воспроизводить утечку, которую сама
        задача чинит).

        Ловит мутацию: приложенный дифф несёт фиктивный заголовок хунка
        (`@@ ... @@` без диапазонов строк) или неверный `index` — тот же
        класс дефекта, что и в backlog.md записи 2 (`git apply --check`
        отвечает «patch with only garbage at line N») — `returncode`
        станет ненулевым, и тест покраснеет вместо тихого прохождения.
        """
        self.assertTrue(
            PLAN_PATH.exists(),
            f"{PLAN_PATH} ещё не создан — приложение диффа AC-4 — "
            f"обязанность роли developer")
        plan_text = PLAN_PATH.read_text(encoding="utf-8")

        match = _DIFF_BLOCK_RE.search(plan_text)
        self.assertIsNotNone(
            match,
            f"{PLAN_PATH} не несёт фенсированного ```diff-блока с "
            f"'diff --git a/{TARGET_FILE} b/{TARGET_FILE}' (AC-4)")
        diff_text = match.group(1) + "\n"

        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                ["git", "worktree", "add", "--detach", "--quiet", tmp,
                 "main"],
                cwd=_util.REPO_ROOT, check=True,
                capture_output=True, text=True)
            try:
                result = subprocess.run(
                    ["git", "apply", "--check", "-"],
                    cwd=tmp, input=diff_text,
                    capture_output=True, text=True)
                self.assertEqual(
                    0, result.returncode,
                    f"git apply --check на чистом main отказал:\n"
                    f"{result.stderr}")
            finally:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", tmp],
                    cwd=_util.REPO_ROOT, check=True,
                    capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
