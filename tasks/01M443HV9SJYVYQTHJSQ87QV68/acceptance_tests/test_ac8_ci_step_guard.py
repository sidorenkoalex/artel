"""PLAN и ветка задачи: сторож шага CI с приложениями (AC-8).

Группа: разовый

Красен до реализации: в ссылке документов задачи ещё нет PLAN.md с приложениями — чтение PLAN из ссылки отказывает, сторожа шага CI нет ни в приложении, ни в tests/ ветки.

Группа «разовый»: предмет — PLAN.md этой задачи, его приложения и дифф
ветки задачи; после мержа проверять не на чем.

PLAN.md читается из ссылки документов `refs/artifacts/<id>`
(`gitcmd.show(artifact_branch.branch_name(TASK_ID), …)`), не с диска;
приложения разбирает тот же узел, что ворота мержа
(`guard.plan_appendices`). Дифф ветки — от точки расхождения
`gitcmd.diff_base` (origin, если он есть).
"""
import subprocess
import sys
import unittest

from _plank import (CODE_ROOT, SCRIPT_NAME, added_lines, appendices_or_fail,
                    clean_tree, git)
from orchestrator import gitcmd

# Покрытие: AC-1..AC-4 —
# tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py, AC-5/AC-6 —
# tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py
# (долгоживущие), AC-7 — test_ac7_ci_appendix_and_doc.py (по ANSWER-1,
# вариант (а)), AC-8 — этот файл.


class CiStepGuardTest(unittest.TestCase):

    def test_ac8_ci_step_guard_present_and_green_without_appendices(self):
        """Сторож шага CI с приложениями есть — в приложении либо в tests/ ветки, зелёный без приложений.

        Сценарий: сторож внутри приложения — приложение PLAN к пути под
        `tests/`, чьи добавленные строки называют `plan_appendix_ci`.
        Сторож в `tests/` ветки — файл `tests/*.py`, изменённый веткой
        относительно точки расхождения (`gitcmd.diff_base`), чей текст
        называет и `plan_appendix_ci`, и `ci.yml`. Найден хотя бы один из
        двух; каждый найденный сторож в `tests/` прогоняется pytest на
        копии чистого дерева HEAD ветки (без приложений) и зелёный.

        Ловит мутацию: сторожа нет вовсе (шаг CI можно снять из `ci.yml`
        будущей правкой незаметно); сторож положен в `tests/` ветки и
        читает `ci.yml`, ожидая шага, которого на ветке без приложения
        нет, — он красный на дереве ветки, и CI ветки задачи красный до
        мержа.
        """
        appendices = appendices_or_fail(self)
        in_appendix = [a.paths for a in appendices
                       if any(p.startswith("tests/") for p in a.paths)
                       and SCRIPT_NAME in added_lines(a.diff)]

        base = gitcmd.diff_base("HEAD", repo=CODE_ROOT)
        self.assertIsNotNone(base, "база диффа ветки не определена")
        changed = gitcmd.diff_names(base, "HEAD", "tests", repo=CODE_ROOT)
        self.assertIsNotNone(changed, "дифф ветки по tests/ не прочитан")
        in_tests = []
        for rel in changed:
            if not rel.endswith(".py"):
                continue
            res = git("show", f"HEAD:{rel}")
            if res.returncode != 0:
                continue  # файл удалён веткой
            if SCRIPT_NAME in res.stdout and "ci.yml" in res.stdout:
                in_tests.append(rel)

        self.assertTrue(in_appendix or in_tests,
                        "сторожа шага CI с приложениями нет ни в приложении "
                        "PLAN к tests/, ни в tests/ ветки")
        if not in_tests:
            return
        tree = clean_tree("artel-plan-appendix-ci-guard-")
        run = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
             *in_tests], cwd=tree, capture_output=True, text=True,
            timeout=110)
        self.assertEqual(run.returncode, 0,
                         f"сторож в tests/ ветки красный на дереве без "
                         f"приложений ({in_tests}):\n{run.stdout[-3000:]}"
                         f"\n{run.stderr[-1500:]}")


if __name__ == "__main__":
    unittest.main()
