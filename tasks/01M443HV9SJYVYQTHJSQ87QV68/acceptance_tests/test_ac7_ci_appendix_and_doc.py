"""PLAN и ветка задачи: приложение к ci.yml и правка docs/operator-session.md (AC-7).

Группа: разовый

Красен до реализации: в ссылке документов задачи ещё нет PLAN.md с приложением к ci.yml, а ветка ещё не правит docs/operator-session.md.

Группа «разовый»: предмет — PLAN.md этой задачи и дифф её ветки; после
мержа проверять не на чем.

AC-7 в редакции ответа Оператора (ANSWER-1, вариант (а)): docs/operator-
session.md — не защищённый путь, приложение к нему невозможно; описание
правится в ветке задачи как обычный файл зоны. Тест проверяет приложение
к `.github/workflows/ci.yml` в PLAN (`git apply --check` на чистом дереве
ветки и шаг сценария в нужных jobs) и правку docs/operator-session.md в
диффе ветки от точки расхождения (`gitcmd.diff_base`).
"""
import re
import unittest

from _plank import (CI_REL, CODE_ROOT, DOC_REL, SCRIPT_NAME, TEST_JOBS,
                    added_lines, appendices_or_fail, clean_tree, git, jobs,
                    step_index, steps)
from orchestrator import gitcmd


class CiAppendixAndDocTest(unittest.TestCase):

    def test_ac7_ci_appendix_applies_and_adds_task_only_step_before_tests(self):
        """Приложение PLAN к ci.yml ложится на чистое дерево ветки и добавляет шаг сценария.

        Сценарий: из PLAN (ссылка документов задачи) берётся приложение,
        чьи пути включают `.github/workflows/ci.yml`; на копии чистого
        дерева HEAD ветки оно проходит `git apply --check` и накладывается.
        В получившемся ci.yml в каждом из jobs `python` и `python-min`
        есть шаг, вызывающий `plan_appendix_ci`, он стоит раньше шага
        pytest и несёт условие на ветки `task/` (только пуши `task/**`).

        Ловит мутацию: приложение к ci.yml не положено в PLAN или его хедер
        хунка не совпадает с файлом ветки (`git apply --check` отказывает);
        шаг добавлен только в `python`, а `python-min` забыт; шаг стоит
        после pytest (тесты идут на дереве без приложений); у шага нет
        условия `task/`, и сценарий запускается на `main`.
        """
        appendices = appendices_or_fail(self)
        ci = [a for a in appendices if CI_REL in a.paths]
        self.assertTrue(ci, f"в PLAN нет приложения к {CI_REL}")

        tree = clean_tree("artel-plan-appendix-ci-ac7-")
        for a in ci:
            check = git("apply", "--check", "-", cwd=tree, input=a.diff)
            self.assertEqual(check.returncode, 0,
                             f"приложение {a.paths} не проходит git apply "
                             f"--check на чистом дереве ветки:\n{check.stderr}")
            res = git("apply", "-", cwd=tree, input=a.diff)
            self.assertEqual(res.returncode, 0, res.stderr)

        text = (tree / CI_REL).read_text(encoding="utf-8")
        parsed = jobs(text)
        for job in TEST_JOBS:
            with self.subTest(job=job):
                self.assertIn(job, parsed, f"job {job} не найден в ci.yml")
                st = steps(parsed[job])
                i_script = step_index(st, re.escape(SCRIPT_NAME))
                i_tests = step_index(st, r"pytest")
                self.assertIsNotNone(i_script,
                                     f"в job {job} нет шага {SCRIPT_NAME}")
                self.assertIsNotNone(i_tests, f"в job {job} нет шага pytest")
                self.assertLess(i_script, i_tests,
                                f"в job {job} шаг {SCRIPT_NAME} не раньше "
                                f"шага pytest")
                self.assertIn("task/", st[i_script],
                              f"шаг {SCRIPT_NAME} в job {job} не ограничен "
                              f"пушами task/**:\n{st[i_script]}")

    def test_ac7_operator_session_doc_edited_in_branch_diff(self):
        """Ветка задачи правит docs/operator-session.md, добавляя текст описания.

        Сценарий: дифф ветки от точки расхождения (`gitcmd.diff_base`)
        включает `docs/operator-session.md`, и в диффе этого файла есть
        добавленные непустые строки.

        Ловит мутацию: описание нового поведения не внесено в документ
        (забыто или оставлено только в PLAN) — файла нет в диффе ветки;
        правка документа только удаляет строки, ничего не описывая.
        """
        base = gitcmd.diff_base("HEAD", repo=CODE_ROOT)
        self.assertIsNotNone(base, "база диффа ветки не определена")
        changed = gitcmd.diff_names(base, "HEAD", DOC_REL, repo=CODE_ROOT)
        self.assertIsNotNone(changed, "дифф ветки по документу не прочитан")
        self.assertIn(DOC_REL, changed,
                      f"ветка задачи не правит {DOC_REL}")
        diff = git("diff", base, "HEAD", "--", DOC_REL)
        self.assertEqual(diff.returncode, 0, diff.stderr)
        self.assertTrue(added_lines(diff.stdout).strip(),
                        f"дифф {DOC_REL} не добавляет ни одной строки")


if __name__ == "__main__":
    unittest.main()
