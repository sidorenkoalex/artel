"""Юнит-тесты `scripts/plan_appendix_ci.py` (SPEC 01M443HV9SJYVYQTHJSQ87QV68):
отбор пуша, привязка ветки к ссылке документов, fail-closed на сбое git и
сторож шага в workflow (требование 7). Сквозной прогон сценария в раннере —
в долгоживущем `tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py`.

Сторож шага (AC-8) двухчастный. Сам `.github/workflows/ci.yml` защищён и
получает шаг сценария только приложением PLAN, поэтому здесь он не
читается: на ветке задачи без приложения такой тест был бы красным по
построению. Вызов сторожа на настоящем `ci.yml` — шаг job `guard` того же
приложения (`plan_appendix_ci.py --check-workflow .github/workflows/ci.yml`),
а здесь проверяется логика этого сторожа (`workflow_errors`) на
синтетических текстах workflow.
"""
import contextlib
import io
import subprocess
import unittest
from unittest import mock

from scripts import plan_appendix_ci as pac

WORKFLOW = """name: ci

on:
  push:
    branches: ["main", "task/**"]

jobs:
  guard:
    runs-on: ubuntu-latest
    steps:
      - run: python3 scripts/plan_appendix_ci.py --check-workflow
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
{python_steps}
  python-min:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
{min_steps}
"""

STEP = ("      - if: startsWith(github.ref, 'refs/heads/task/')\n"
        "        run: python3 scripts/plan_appendix_ci.py")
TESTS = "      - run: python3 -m pytest tests -n auto"


def workflow(python_steps: list[str], min_steps: list[str]) -> str:
    return WORKFLOW.format(python_steps="\n".join(python_steps),
                           min_steps="\n".join(min_steps))


class TaskBranchTest(unittest.TestCase):

    def test_only_task_push_is_processed(self):
        """Сценарий берётся только за пуш `task/**`; `main`, прочие ветки и
        pull_request — None (требование 2: их прогоны не меняются).

        Ловит мутацию: проверка события или префикса `refs/heads/task/`
        снята — пуш `main` или pull_request ветки задачи отдают имя ветки,
        и тест краснеет.
        """
        self.assertEqual(pac.task_branch("push", "refs/heads/task/01abc-x"),
                         "01abc-x")
        self.assertIsNone(pac.task_branch("push", "refs/heads/main"))
        self.assertIsNone(pac.task_branch("push", "refs/heads/feature/task"))
        self.assertIsNone(pac.task_branch("pull_request",
                                          "refs/heads/task/01abc-x"))

    def test_main_push_never_touches_git(self):
        """Пуш `main` — код 0 без единого вызова git.

        Ловит мутацию: `run` читает ссылки `origin` до отбора пуша — тест
        краснеет на вызове git.
        """
        with mock.patch.object(pac, "_git") as git, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pac.run("push", "refs/heads/main"), 0)
        git.assert_not_called()


class DocsRefForBranchTest(unittest.TestCase):

    def test_branch_owns_ref_with_its_lowercase_id(self):
        """Ветка `task/<id в нижнем регистре>-<слаг>` принадлежит ссылке
        `<id>` в исходном регистре; ссылка, чей id лишь начало id ветки
        (без дефиса слага следом), ей не принадлежит.

        Ловит мутацию: сравнение без `.lower()` — ссылка не находится;
        сравнение голым `startswith` без дефиса — ветке достаётся чужая
        ссылка с более коротким id.
        """
        refs = {"01ABC": "sha-short", "01ABCD": "sha-own", "02XYZ": "sha-x"}
        self.assertEqual(pac.docs_ref_for_branch("01abcd-ci-fix", refs),
                         ("01ABCD", "sha-own"))
        self.assertEqual(pac.docs_ref_for_branch("01abcd", refs),
                         ("01ABCD", "sha-own"))
        self.assertIsNone(pac.docs_ref_for_branch("01abcde-x",
                                                  {"01ABC": "s"}))
        self.assertIsNone(pac.docs_ref_for_branch("03qqq-x", refs))


class FailClosedTest(unittest.TestCase):

    def test_unreadable_origin_is_red_not_empty(self):
        """`git ls-remote origin` отказал — код 1 с ответом git, а не
        «приложений нет» с кодом 0.

        Ловит мутацию: сбой чтения ссылок трактуется как «ссылки нет» —
        CI ветки зелёный при PLAN, которого никто не прочитал, и тест
        краснеет на коде выхода.
        """
        failed = subprocess.CompletedProcess(
            ["git"], 128, "", "fatal: could not read from remote")
        err = io.StringIO()
        env = {"GITHUB_EVENT_NAME": "push",
               "GITHUB_REF": "refs/heads/task/01abc-x"}
        with mock.patch.object(pac, "_git", return_value=failed), \
                mock.patch.dict(pac.os.environ, env), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(err):
            self.assertEqual(pac.main([]), 1)
        self.assertIn("could not read from remote", err.getvalue())


class WorkflowErrorsTest(unittest.TestCase):

    def test_step_before_tests_in_both_jobs_passes(self):
        """Шаг сценария перед pytest в обоих jobs — нарушений нет.

        Ловит мутацию: сторож ищет строку сценария не в блоке job, а
        где-то ещё (или требует её после pytest) — здесь появляется
        нарушение, и тест краснеет.
        """
        self.assertEqual(pac.workflow_errors(
            workflow([STEP, TESTS], [STEP, TESTS])), [])

    def test_missing_or_late_step_is_named(self):
        """Шаг пропал из `python-min` (вызов `--check-workflow` в job
        `guard` его не заменяет) или стоит после pytest в `python` —
        нарушение с именем job.

        Ловит мутацию: сторож засчитывает строку сценария в любом job
        файла либо не сверяет порядок с pytest — пустой список ошибок, и
        тест краснеет.
        """
        errors = pac.workflow_errors(workflow([STEP, TESTS], [TESTS]))
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("python-min", errors[0])
        errors = pac.workflow_errors(workflow([TESTS, STEP], [STEP, TESTS]))
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("job python:", errors[0])


if __name__ == "__main__":
    unittest.main()
