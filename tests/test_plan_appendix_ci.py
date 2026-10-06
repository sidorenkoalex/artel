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
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
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
        """Сценарий берётся за пуш `task/**` и за pull_request ветки задачи
        того же репозитория (ref головы — `refs/heads/<GITHUB_HEAD_REF>`,
        SPEC 01M466ZERXQKXTR5RQCDYVDZJQ, требование 1); `main` и прочие
        ветки — None (требование 2: их прогоны не меняются).

        Ловит мутацию: проверка префикса `refs/heads/task/` снята — пуш
        `main` отдаёт имя ветки; отбор события оставлен только на push —
        pull_request ветки задачи отдаёт None; и тест краснеет.
        """
        self.assertEqual(pac.task_branch("push", "refs/heads/task/01abc-x"),
                         "01abc-x")
        self.assertIsNone(pac.task_branch("push", "refs/heads/main"))
        self.assertIsNone(pac.task_branch("push", "refs/heads/feature/task"))
        self.assertEqual(pac.task_branch("pull_request",
                                         "refs/heads/task/01abc-x"),
                         "01abc-x")

    def test_other_events_and_bare_prefix_are_skipped(self):
        """Событие не push/pull_request (`workflow_dispatch`,
        `pull_request_target`) и голый префикс `refs/heads/task/` без имени
        — None.

        Ловит мутацию: отбор события снят (любое событие с ref `task/**`
        обрабатывается) или пустое имя ветки после префикса засчитано —
        тест краснеет.
        """
        for event in ("workflow_dispatch", "pull_request_target", ""):
            self.assertIsNone(pac.task_branch(event,
                                              "refs/heads/task/01abc-x"))
        self.assertIsNone(pac.task_branch("push", "refs/heads/task/"))

    def test_main_push_never_touches_git(self):
        """Пуш `main` — код 0 без единого вызова git.

        Ловит мутацию: `run` читает ссылки `origin` до отбора пуша — тест
        краснеет на вызове git.
        """
        with mock.patch.object(pac, "_git") as git, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pac.run("push", "refs/heads/main"), 0)
        git.assert_not_called()


class TestedRefTest(unittest.TestCase):

    def pr_env(self, tmp: str, head_repo: str, head_ref: str = "task/01abc-x"):
        event = Path(tmp) / "event.json"
        event.write_text(json.dumps({"pull_request": {"head": {
            "ref": head_ref, "repo": {"full_name": head_repo}}}}),
            encoding="utf-8")
        return {"GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_REF": "refs/pull/7/merge",
                "GITHUB_HEAD_REF": head_ref,
                "GITHUB_REPOSITORY": "o/artel",
                "GITHUB_EVENT_PATH": str(event)}

    def test_push_ref_and_same_repo_pr_head(self):
        """Push — `GITHUB_REF` как есть; pull_request того же репозитория —
        `refs/heads/<GITHUB_HEAD_REF>`, а не `refs/pull/<N>/merge`.

        Ловит мутацию: на pull_request берётся `GITHUB_REF` — ref
        `refs/pull/7/merge`, ветка задачи не узнаётся, тест краснеет.
        """
        self.assertEqual(pac.tested_ref({"GITHUB_EVENT_NAME": "push",
                                         "GITHUB_REF": "refs/heads/main"}),
                         "refs/heads/main")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(pac.tested_ref(self.pr_env(tmp, "o/artel")),
                             "refs/heads/task/01abc-x")

    def test_fork_head_is_not_task_branch(self):
        """pull_request из форка с веткой `task/**` — пустой ref.

        Ловит мутацию: репозиторий головы не сверяется с
        `GITHUB_REPOSITORY` — форк отдаёт `refs/heads/task/01abc-x`, тест
        краснеет.
        """
        with tempfile.TemporaryDirectory() as tmp, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pac.tested_ref(self.pr_env(tmp, "fork/artel")),
                             "")

    def test_unreadable_event_file_fails_closed_only_for_task_head(self):
        """Файл события не читается: голова `task/**` — `CiError` (код 1),
        голова не `task/**` — пустой ref без чтения файла.

        Ловит мутацию: непрочитанный файл события трактуется как «тот же
        репозиторий» или «форк» — `CiError` не поднят; либо файл читается
        до отбора ветки — голова `feature/x` падает `CiError`; тест
        краснеет.
        """
        env = {"GITHUB_EVENT_NAME": "pull_request",
               "GITHUB_REF": "refs/pull/7/merge",
               "GITHUB_HEAD_REF": "task/01abc-x",
               "GITHUB_REPOSITORY": "o/artel",
               "GITHUB_EVENT_PATH": "/nonexistent/artel-event.json"}
        with self.assertRaises(pac.CiError):
            pac.tested_ref(env)
        env["GITHUB_HEAD_REF"] = "feature/x"
        self.assertEqual(pac.tested_ref(env), "")


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

    def test_push_only_condition_in_dash_and_multiline_forms(self):
        """Условие push-only на строке дефиса (`- if: …`) и с переносом на
        следующую строку — нарушение с именем job; условие с
        `pull_request` в тех же формах и условие другого шага — нет.

        Ловит мутацию: условие ищется только на отдельной строке `if:`
        (не на строке дефиса) или продолжение не склеивается — на
        переносе `pull_request` во второй строке ложное нарушение; условие
        берётся у соседнего шага — push-only шаг пуша main перед шагом
        сценария даёт нарушение; тест краснеет.
        """
        push_only = ("      - if: github.event_name == 'push' && "
                     "startsWith(github.ref, 'refs/heads/task/')\n"
                     "        run: python3 scripts/plan_appendix_ci.py")
        wrapped = ("      - name: приложения\n"
                   "        if: github.event_name == 'push' ||\n"
                   "          github.event_name == 'pull_request'\n"
                   "        run: python3 scripts/plan_appendix_ci.py")
        main_step = ("      - if: github.event_name == 'push'\n"
                     "        run: echo main")
        errors = pac.workflow_errors(workflow([push_only, TESTS],
                                              [main_step, wrapped, TESTS]))
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("job python:", errors[0])
        self.assertIn("только push", errors[0])


class CheckWorkflowOnRunTest(unittest.TestCase):
    """`--check-workflow` на прогоне ветки задачи сперва накладывает
    приложения PLAN (ANSWER-1 01M466ZERXQKXTR5RQCDYVDZJQ). Само наложение
    (`run`) покрыто долгоживущими сквозными тестами; здесь — что сторож
    зовёт его ровно на прогонах ветки задачи и проверяет файл после."""

    PUSH_ONLY = ("      - if: github.event_name == 'push' && "
                 "startsWith(github.ref, 'refs/heads/task/')\n"
                 "        run: python3 scripts/plan_appendix_ci.py")
    WITH_PR = ("      - if: github.event_name == 'push' || "
               "github.event_name == 'pull_request'\n"
               "        run: python3 scripts/plan_appendix_ci.py")

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="artel-wf-run-")
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "ci.yml"
        self.path.write_text(workflow([self.PUSH_ONLY, TESTS],
                                      [self.PUSH_ONLY, TESTS]),
                             encoding="utf-8")
        self.calls = []

    def appendix_run(self, code: int):
        """Заместитель `run`: «приложение» PLAN чинит условие шага в файле."""
        def fake(event_name, ref):
            self.calls.append((event_name, ref))
            if code == 0:
                self.path.write_text(workflow([self.WITH_PR, TESTS],
                                              [self.WITH_PR, TESTS]),
                                     encoding="utf-8")
            return code
        return fake

    def check(self, env: dict, code: int = 0) -> tuple[int, str]:
        err = io.StringIO()
        with mock.patch.object(pac, "run", side_effect=self.appendix_run(code)), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(err):
            result = pac.check_workflow_on_run(self.path, env)
        return result, err.getvalue()

    def test_task_branch_run_checks_workflow_with_appendices(self):
        """Пуш `task/**` и pull_request `task/**` того же репозитория:
        сторож зелёный на файле, который зелен только после приложений;
        вне CI и на пуше `main` — файл как есть (push-only — код 1), `run`
        не зовётся.

        Ловит мутацию: `--check-workflow` не накладывает приложения (или
        накладывает после проверки) — на прогоне ветки задачи код 1;
        наложение зовётся и вне прогона ветки задачи — `run` вызван при
        пустом окружении или пуше `main`; тест краснеет.
        """
        push = {"GITHUB_EVENT_NAME": "push",
                "GITHUB_REF": "refs/heads/task/01abc-x"}
        self.assertEqual(self.check(push)[0], 0)
        self.assertEqual(self.calls, [("push", "refs/heads/task/01abc-x")])

        self.setUp()
        with tempfile.TemporaryDirectory() as tmp:
            event = Path(tmp) / "event.json"
            event.write_text(json.dumps({"pull_request": {"head": {
                "repo": {"full_name": "o/artel"}}}}), encoding="utf-8")
            pr = {"GITHUB_EVENT_NAME": "pull_request",
                  "GITHUB_REF": "refs/pull/7/merge",
                  "GITHUB_HEAD_REF": "task/01abc-x",
                  "GITHUB_REPOSITORY": "o/artel",
                  "GITHUB_EVENT_PATH": str(event)}
            self.assertEqual(self.check(pr)[0], 0)
        self.assertEqual(self.calls,
                         [("pull_request", "refs/heads/task/01abc-x")])

        for env in ({}, {"GITHUB_EVENT_NAME": "push",
                         "GITHUB_REF": "refs/heads/main"}):
            self.setUp()
            code, err = self.check(env)
            self.assertEqual(code, 1, env)
            self.assertIn("только push", err)
            self.assertEqual(self.calls, [], env)

    def test_failed_appendices_are_red_before_the_check(self):
        """Наложение отказало (неприменимое приложение, сбой git) — код 1,
        даже если файл как есть сторож бы пропустил.

        Ловит мутацию: код `run` игнорируется и сторож проверяет файл —
        здесь файл без нарушений, код 0, тест краснеет; `CiError`
        наложения не перехвачен — исключение вместо кода 1.
        """
        self.path.write_text(workflow([self.WITH_PR, TESTS],
                                      [self.WITH_PR, TESTS]),
                             encoding="utf-8")
        push = {"GITHUB_EVENT_NAME": "push",
                "GITHUB_REF": "refs/heads/task/01abc-x"}
        code, err = self.check(push, code=1)
        self.assertEqual(code, 1)
        self.assertIn("не наложены", err)

        err = io.StringIO()
        with mock.patch.object(pac, "run",
                               side_effect=pac.CiError("git упал")), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(err):
            self.assertEqual(pac.check_workflow_on_run(self.path, push), 1)
        self.assertIn("git упал", err.getvalue())


if __name__ == "__main__":
    unittest.main()
