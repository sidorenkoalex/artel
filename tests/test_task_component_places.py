"""Места задачи на записи из нескольких компонентов (SPEC 01M5JGSAANR1NZYQD4FCSVE48Y, требование 2, таблица «Места задачи и исход при отказе `for_task`»): профиль компонента задачи и отказ вместо пропуска при отказе `for_task`.

Сторож после мержа: каждое место берёт профиль через `for_task`, и у
записи из нескольких компонентов отказ `for_task` — отказ места с текстом
отказа, а не молчаливый пропуск проверки. Возврат места на
`decide(target)`/`profile_of(target)` или на пропуск при отказе молча снял
бы гейт неослабления у такой записи (REVIEW итерации 1, R1-F1).

Стенд — учебная запись из двух компонентов: `backend` (`junit-xml`,
pytest) и `frontend` (`pult-vitest`, `depends_on` вида `files` на
`backend/seed/`). Задача — строка БД с зонами варианта; внешние источники
(git, полный набор, итог CI, рабочая копия) подменены.
"""
import contextlib
import io
import re
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from orchestrator import (acceptance, appendix_tree, artifact_source, config,
                          fsm_autogate, fsm_merge_gate, gitcmd, project_profile,
                          pull, repo_context, review, store, suite_run)
from orchestrator.advance_gates import mandate
from orchestrator.advance_gates import review as review_gates
from orchestrator.advance_gates import test_integrity
from tests.sandbox import TaskIdSchemaConnTmpRootTest, make_project_repo

PROJECT = "uchplaces"
ARTIFACT = "refs/artifacts/T"
BASE = "basesha"
HEAD = "headsha"
BACKEND_LIMIT = 311
FRONTEND_LIMIT = 422
FRONTEND_CHECK = ["frontend-check", "--strict"]


def flow(items) -> str:
    return "[" + ", ".join(str(item) for item in items) + "]"


BACKEND_FIELDS = {
    "command": flow(["python3", "-m", "pytest"]),
    "report": "junit-xml",
    "long_lived_dir": "backend/tests",
    "long_lived_name": "test_<id>_<name>.py",
    "weakening_scope": flow(["backend/tests/**"]),
    "mutation_claim_scope": flow(["backend/tests/test_*.py"]),
    "failure_errors": flow(["AssertionError"]),
    "tests": flow(["backend/tests/**/test_*.py"]),
    "plank_layout": "backend/tests/.pb/<id>",
    "paths": flow(["^backend/"]),
    "test_support": flow(["backend/testkit/**"]),
    "full_suite_timeout_sec": str(BACKEND_LIMIT),
}

FRONTEND_FIELDS = {
    "command": flow(project_profile.VITEST_BASE_ARGV),
    "report": "pult-vitest",
    "tests": flow(["frontend/src/**/*.test.jsx"]),
    "plank_layout": "frontend/src/.pv/<id>",
    "long_lived": "frontend/src/<dir>/<name>.<id>.test.jsx",
    "weakening_scope": flow(["frontend/src/**"]),
    "mutation_claim_scope": flow(["frontend/claims/**"]),
    "failure_errors": flow(["AssertionError"]),
    "paths": flow(["^frontend/"]),
    "test_support": flow(["frontend/e2e/**"]),
    "checks_local": flow(FRONTEND_CHECK),
    "full_suite_timeout_sec": str(FRONTEND_LIMIT),
}

ENTRY = (f"  {PROJECT}:\n"
         "    forge: github\n"
         f"    url: https://localhost/artel-tests/{PROJECT}\n"
         "    base: main\n"
         f"    token_slot: {PROJECT}-token\n"
         "    no_paths: []\n"
         "    project_skills: []\n"
         "    merge_gate: operator\n"
         "    components:\n"
         "      backend:\n"
         + "".join(f"        {k}: {v}\n" for k, v in BACKEND_FIELDS.items())
         + "      frontend:\n"
         + "".join(f"        {k}: {v}\n" for k, v in FRONTEND_FIELDS.items())
         + "        depends_on:\n"
           "          backend:\n"
           "            via: files\n"
           "            paths: [^backend/seed/]\n")

# Зоны вариантов задачи; `None` — зоны не заданы.
ZONES = {
    "frontend": "frontend/src/App.jsx",
    "backend": "backend/app.py",
    "both": "backend/app.py, frontend/src/App.jsx",
    "outside": "docs/notes.md",
    "none": None,
}
REFUSAL_VARIANTS = ("both", "outside", "none")
NOT_SET = ("зоны задачи не заданы — компонент задачи на записи из нескольких "
           "компонентов не выбран")
NOT_TOUCHED = "зоны задачи не задевают ни одного компонента записи"
SEVERAL = re.compile(r"задача затрагивает несколько компонентов \(backend, "
                     r"frontend\) — дели задачу по компонентам")
GREEN = acceptance.FullSuiteRun(True, acceptance.FULL_SUITE_GREEN,
                                "полный набор зелёный", None,
                                "полный набор зелёный")
ALPHA = ("import unittest\n\n\nclass AlphaTest(unittest.TestCase):\n\n"
         "    def test_one(self):\n        self.assertEqual(len('ab'), 2)\n")
NO_CLAIM = "def test_new():\n    assert True\n"
NOT_COVERED = "свойство остаётся и не покрыто"
MATRIX_HEADERS = (
    "Что меняется",
    "Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка)",
    "Остаётся ли свойство после изменения",
    "Чем покрыто после (тест файл:строка) или «не покрыто»",
    "Решение")


class Stop(Exception):
    """Остановка сценария после наблюдения места."""


def matrix(element: str, covered: str) -> str:
    row = (f"`{element}`", "тест компонента", "остаётся", covered, "ок")
    return ("## Матрица неослабления\n\n"
            "| " + " | ".join(MATRIX_HEADERS) + " |\n"
            + "|" + "---|" * len(MATRIX_HEADERS) + "\n"
            + "| " + " | ".join(row) + " |\n")


def outcome_text(fn, *args, **kwargs) -> tuple:
    """(значение, текст исхода): вывод, `SystemExit`, исключение и поля
    отказа читаются одним текстом — исход места любой формы."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            value = fn(*args, **kwargs)
        except SystemExit as exc:
            value = exc
            buf.write(f"\nSystemExit: {exc.code}")
        except Exception as exc:  # noqa: BLE001 — исход места любой формы
            value = exc
            buf.write(f"\n{type(exc).__name__}: {exc}")
    parts = [buf.getvalue(), repr(value)]
    parts += [getattr(value, a) for a in ("action", "detail")
              if isinstance(getattr(value, a, None), str)]
    if isinstance(value, (tuple, list)):
        parts += [str(v) for v in value]
    return value, "\n".join(parts)


@contextlib.contextmanager
def yielding(value):
    yield value


def patch_all(*patchers) -> contextlib.ExitStack:
    stack = contextlib.ExitStack()
    for patcher in patchers:
        stack.enter_context(patcher)
    return stack


class PlacesSandbox(TaskIdSchemaConnTmpRootTest):

    def setUp(self):
        super().setUp()
        old = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(old.rstrip("\n") + "\n" + ENTRY,
                                  encoding="utf-8")
        make_project_repo(PROJECT, origin=False)
        self.counter = 0

    def task(self, variant: str, state: str = "in_dev") -> SimpleNamespace:
        self.counter += 1
        tid = f"01PLACES{self.counter:018d}"
        branch = f"task/{tid.lower()}-uch"
        store.insert_task(self.conn, tid, f"Задача {variant}", state, branch,
                          PROJECT, 25.0)
        if ZONES[variant] is not None:
            store.update_task(self.conn, tid, zones=ZONES[variant])
        return SimpleNamespace(id=tid, branch=branch, variant=variant)

    def row(self, t):
        return store.get_task(self.conn, t.id)

    def journal_text(self, t) -> str:
        return "\n".join(f"{r['action']}: {r['detail'] or ''}"
                         for r in store.task_steps(self.conn, t.id))

    def assert_refusal_text(self, text: str, variant: str, where: str) -> None:
        """Исход места несёт текст отказа `for_task` своего варианта зон и
        причину `decide` (AC-3)."""
        if variant == "none":
            self.assertIn(NOT_SET, text, f"{where}:\n{text}")
        elif variant == "outside":
            self.assertIn(NOT_TOUCHED, text, f"{where}:\n{text}")
        else:
            self.assertRegex(text, SEVERAL, where)
        self.assertIn(project_profile.decide(PROJECT).refusal, text, where)

    def each_refusal(self, state: str, place, where: str) -> None:
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                t = self.task(variant, state)
                text = place(t)[1]
                self.assert_refusal_text(f"{text}\n{self.journal_text(t)}",
                                         variant, where)

    # --- места -----------------------------------------------------------

    def acceptance_suite(self, t):
        seen = []

        def checks(profile, root):
            seen.append(profile)
            return True, f"checks_local компонента {profile.component} — код 0"
        with patch_all(
                mock.patch.object(acceptance, "_acceptance_suite_run",
                                  return_value=GREEN),
                mock.patch.object(acceptance, "run_checks_local", checks)):
            value, text = outcome_text(acceptance.acceptance_suite, self.conn,
                                       self.root, t.id, t.branch, self.root,
                                       actor="operator")
        return value, text, seen

    def merge_text_gate(self, t):
        seen = []

        def escalates(conn, task_id, state, branch, artifact, scope=None):
            seen.append(scope)
            return False
        with patch_all(
                mock.patch.object(artifact_source, "resolve",
                                  return_value=(ARTIFACT, False)),
                mock.patch.object(fsm_merge_gate, "merge_gate_escalates",
                                  escalates)):
            value, text = outcome_text(
                fsm_merge_gate._test_integrity_diff_gate, self.conn, t.id,
                "merge_gate", t.branch, repo_context.resolve(PROJECT))
        return value, text, seen

    def deleted_in_branch(self, deleted):
        """git ветки: файлы `deleted` есть на базе и удалены на голове."""
        def show(ref, rel, repo=None):
            if ref == BASE and rel in deleted:
                return ALPHA, ""
            return None, "файла нет в этой ветке"
        return patch_all(
            mock.patch.object(gitcmd, "diff_base", return_value=BASE),
            mock.patch.object(gitcmd, "diff_name_status",
                              return_value=[("D", p, None) for p in deleted]),
            mock.patch.object(gitcmd, "show", show),
            mock.patch.object(gitcmd, "ls_tree_files", return_value=[]),
            mock.patch.object(gitcmd, "branch_head_sha", return_value=HEAD),
            mock.patch.object(gitcmd, "git", lambda *a: subprocess.CompletedProcess(
                a, 0, "\n", "")))

    def full_suite(self, t):
        seen = []

        def run(root, **kwargs):
            seen.append(kwargs)
            return True, "1 passed in 0.01s"
        root = self.root / "suite"
        root.mkdir(exist_ok=True)
        with patch_all(mock.patch.object(acceptance, "run_full_suite", run),
                       mock.patch.object(acceptance, "suite_tree_hash",
                                         return_value=None)):
            value, text = outcome_text(acceptance.full_suite, root, t.id)
        return value, text, seen

    def suite_run(self, t):
        seen = []
        wt = self.root / "wt"
        wt.mkdir(exist_ok=True)
        tree = SimpleNamespace(root=wt, refusal="", fixable=False, note="",
                               warning="", mark=lambda text, *a, **k: text)

        def run(root, **kwargs):
            seen.append(kwargs)
            raise Stop()
        with patch_all(
                mock.patch.object(appendix_tree, "suite_tree",
                                  lambda *a, **k: yielding(tree)),
                mock.patch.object(acceptance, "run_full_suite", run)):
            value, text = outcome_text(suite_run._run, t.id, 1,
                                       suite_run.MODE_FULL,
                                       self.root / "suite.log")
        return value, text, seen

    def mutation(self, t, files):
        def show(ref, path, repo=None):
            return (None, "новый файл") if ref == BASE else (NO_CLAIM, "")
        with patch_all(mock.patch.object(gitcmd, "diff_base", return_value=BASE),
                       mock.patch.object(gitcmd, "diff_names", return_value=files),
                       mock.patch.object(gitcmd, "show", show)):
            return outcome_text(review_gates._mutation_claim_gate, self.conn,
                                t.id, self.row(t), t.branch)

    def pull_plank(self, t):
        seen = []
        tdir = self.root / "plank" / t.id
        (tdir / "acceptance_tests").mkdir(parents=True, exist_ok=True)
        (tdir / "acceptance_tests" / "a.test.jsx").write_text("// тест\n",
                                                             encoding="utf-8")
        wt = self.root / "wt"
        wt.mkdir(exist_ok=True)

        def run(tests_dir, **kwargs):
            seen.append(kwargs)
            return True, ""
        with patch_all(
                mock.patch.object(artifact_source, "resolve",
                                  return_value=(ARTIFACT, False)),
                mock.patch.object(acceptance, "materialize_from_branch",
                                  return_value=tdir),
                mock.patch.object(acceptance, "plank_present", return_value=True),
                mock.patch.object(acceptance, "run", run)):
            value, text = outcome_text(
                pull._materialize_and_run_plank, self.conn, t.id, self.row(t),
                t.branch, config.MAIN_BRANCH, wt, "in_dev", BASE,
                lambda *a: None)
        return value, text, seen


class AcceptanceSuiteChecksLocalTest(PlacesSandbox):

    def test_task_component_checks_local_run(self):
        """`acceptance_suite` задачи на `frontend` исполняет `checks_local` компонента `frontend`; итог зелёный.

        Ловит мутацию: `acceptance_suite` берёт профиль `decide(target)` или
        перехват `ComponentsPending` даёт `profile=None` — `checks_local`
        компонента не исполняются.
        """
        t = self.task("frontend", "acceptance")
        value, text, seen = self.acceptance_suite(t)
        self.assertEqual([p.component for p in seen], ["frontend"], text)
        self.assertEqual(tuple(seen[0].checks_local), tuple(FRONTEND_CHECK))
        self.assertTrue(value.green, text)

    def test_for_task_refusal_is_not_silent_skip(self):
        """`acceptance_suite` при отказе `for_task` — не зелёный итог с текстом отказа, `checks_local` не зовутся.

        Ловит мутацию: перехват `ComponentsPending` в `acceptance_suite`
        возвращён к `profile = None` — итог CI зелёный, `checks_local`
        молча пропущены, причины нет.
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                t = self.task(variant, "acceptance")
                value, text, seen = self.acceptance_suite(t)
                self.assertFalse(getattr(value, "green", False), text)
                self.assertEqual(seen, [], text)
                self.assert_refusal_text(f"{text}\n{self.journal_text(t)}",
                                         variant, "acceptance_suite")


class MergeTextGateTest(PlacesSandbox):

    def test_task_component_scope(self):
        """Гейт текста на мерже задачи на `frontend` зовёт узел с областью `weakening_scope` компонента `frontend`.

        Ловит мутацию: `_test_integrity_diff_gate` на `decide(target)` —
        узел не зовётся (молчаливый `False`) либо область чужая.
        """
        t = self.task("frontend", "merge_gate")
        _value, text, seen = self.merge_text_gate(t)
        self.assertEqual(len(seen), 1, text)
        self.assertTrue(seen[0]("frontend/src/test_a.py"))
        self.assertFalse(seen[0]("backend/tests/test_a.py"))
        self.assertFalse(seen[0]("tests/test_a.py"))

    def test_for_task_refusal_refuses_merge(self):
        """Гейт текста на мерже при отказе `for_task` — отказ `MERGE_PROFILE_REFUSAL_ACTION` с текстом отказа, узел не зовётся.

        Ловит мутацию: ветка отказа `_test_integrity_diff_gate` у записи из
        нескольких компонентов снята — молчаливый `False` без записи, мерж
        без гейта текста.
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                t = self.task(variant, "merge_gate")
                value, text, seen = self.merge_text_gate(t)
                self.assertEqual(seen, [], text)
                self.assertIsNot(value, False, text)
                journal = self.journal_text(t)
                self.assertIn(fsm_merge_gate.MERGE_PROFILE_REFUSAL_ACTION, journal)
                self.assert_refusal_text(f"{text}\n{journal}", variant,
                                         "гейт текста на мерже")


class ExternalHelpersTest(PlacesSandbox):

    def test_task_component_area(self):
        """Область помощников гейта текста задачи на `frontend` — `workdir`/`in_weakening_scope` компонента `frontend`.

        Ловит мутацию: `_external_helpers` на `decide(target)` — откат на
        область по умолчанию (`tests/**/*.py`).
        """
        t = self.task("frontend")
        helpers = test_integrity._external_helpers(self.conn, t.id, None)
        (frontend,) = project_profile.component_profiles(PROJECT, ("frontend",))
        self.assertEqual(helpers.workdir, frontend.workdir)
        self.assertTrue(helpers.scope("frontend/src/ui/helper.py"))
        self.assertFalse(helpers.scope("tests/test_x.py"))
        self.assertFalse(helpers.scope("backend/tests/helper.py"))

    def test_for_task_refusal_has_no_default_area(self):
        """При отказе `for_task` вход гейта мержа `merge_gate_escalates` несёт текст отказа, а не находку по области по умолчанию.

        Сценарий: удалён `tests/test_x.py` — файл области по умолчанию.

        Ловит мутацию: `_external_helpers` при отказе молча откатывается
        на область по умолчанию — исход без текста отказа.
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                t = self.task(variant, "merge_gate")
                with self.deleted_in_branch(["tests/test_x.py"]):
                    _value, text = outcome_text(
                        test_integrity.merge_gate_escalates, self.conn, t.id,
                        "merge_gate", t.branch, ARTIFACT)
                self.assert_refusal_text(f"{text}\n{self.journal_text(t)}",
                                         variant, "merge_gate_escalates")


class MatrixRefusalsTest(PlacesSandbox):

    def test_task_component_path_covers(self):
        """Матрица мандата задачи на `frontend` засчитывает покрытием путь файла области `frontend`.

        Ловит мутацию: `matrix_refusals` на `decide(target)` или откат на
        правило `tests/…` — «свойство остаётся и не покрыто».
        """
        t = self.task("frontend")
        element = "frontend/src/ui/old.test.jsx"
        got = mandate.matrix_refusals(
            matrix(element, "frontend/src/ui/new.test.jsx:1"), [element],
            conn=self.conn, task_id=t.id)
        self.assertEqual([r for r in got if NOT_COVERED in r], [], got)

    def test_for_task_refusal_refuses(self):
        """Матрица мандата при отказе `for_task` — отказ с текстом отказа, не откат на правило `tests/…`.

        Ловит мутацию: `matrix_refusals` при отказе профиля засчитывает
        `tests/test_new.py` по правилу артели — отказов нет.
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                t = self.task(variant)
                got = mandate.matrix_refusals(
                    matrix("tests/test_old.py", "tests/test_new.py:1"),
                    ["tests/test_old.py"], conn=self.conn, task_id=t.id)
                self.assertTrue(got)
                self.assert_refusal_text("\n".join(got), variant, "матрица")


class SuiteLimitTest(PlacesSandbox):

    def test_task_component_limit(self):
        """Предел `acceptance.full_suite` и `suite-run <id>` — `component_limit` компонента задачи; `suite-run` гонит каналом его профиля.

        Ловит мутацию: предел по `full_suite_limit(target)` (`TargetsError`)
        или по первому компоненту записи — у задачи на `frontend` предел
        `backend`; `suite-run` на `_profile_command(target)` — отказ.
        """
        for variant, limit in (("frontend", FRONTEND_LIMIT),
                               ("backend", BACKEND_LIMIT)):
            with self.subTest(variant=variant):
                t = self.task(variant)
                _value, text, seen = self.full_suite(t)
                self.assertEqual(len(seen), 1, text)
                self.assertEqual(seen[0]["limit"][0], limit)
                _value, text, seen = self.suite_run(t)
                self.assertEqual(len(seen), 1, text)
                self.assertEqual(seen[0]["limit"][0], limit)
                self.assertEqual(seen[0]["command"].component, variant)

    def test_for_task_refusal_refuses_run(self):
        """`acceptance.full_suite` и `suite-run <id>` при отказе `for_task` — отказ с текстом отказа, полный набор не зовётся.

        Ловит мутацию: предел при отказе берётся по умолчанию/по первому
        компоненту — прогон идёт без профиля задачи.
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                t = self.task(variant)
                value, text, seen = self.full_suite(t)
                self.assertEqual(seen, [], text)
                self.assertFalse(getattr(value, "green", False), text)
                self.assert_refusal_text(text, variant, "full_suite")
                value, text, seen = self.suite_run(t)
                self.assertEqual(seen, [], text)
                self.assertIn(f"[{t.id}] suite-run №1: отказ — ", value[0])
                self.assert_refusal_text(value[0], variant, "suite-run")


class OtherPlacesTest(PlacesSandbox):

    def test_mutation_claim_by_task_component(self):
        """Гейт заявки мутации задачи на `frontend` судит область `mutation_claim_scope` компонента `frontend`; при отказе `for_task` — `REFUSAL_ACTION` с текстом отказа.

        Ловит мутацию: `_mutation_claim_gate` на `decide(target)` — отказ
        профиля у задачи на `frontend`, причина без текста варианта зон.
        """
        t = self.task("frontend")
        value, _text = self.mutation(t, ["frontend/claims/test_a.py",
                                         "backend/tests/test_b.py"])
        self.assertIn("frontend/claims/test_a.py", value.detail)
        self.assertNotIn("backend/tests/test_b.py", value.detail)
        self.each_refusal("in_dev", lambda t: self.mutation(
            t, ["frontend/claims/test_a.py"]), "заявка мутации")

    def test_autogate_plank_rule_by_task_component(self):
        """Автогейт по правилу планки у задачи на `frontend` (в границе) не отказывает; при отказе `for_task` — отказ с текстом отказа.

        Ловит мутацию: граница `_plank_rule_refusal` по `_bounds(…, target)`
        — отказ «до G3б» у задачи на `frontend` и без текста варианта.
        """
        rule = project_profile.plank_rule(PROJECT)
        t = self.task("frontend", "acceptance")
        self.assertIsNone(fsm_autogate._plank_rule_refusal(rule, self.row(t)))
        self.each_refusal("acceptance", lambda t: outcome_text(
            fsm_autogate._plank_rule_refusal, rule, self.row(t)), "правило планки")

    def test_review_package_exit_by_task_component(self):
        """Пакет ревьювера задачи на `frontend` собирается; при отказе `for_task` — `PACKAGE_REFUSED_ACTION` с текстом отказа.

        Ловит мутацию: `_exit_without_profile` на `decide(target)` —
        выход «ревью-пакет не собран» у задачи на `frontend`.
        """
        t = self.task("frontend", "review")
        value, text = outcome_text(review._exit_without_profile, self.conn,
                                   t.id, PROJECT)
        self.assertIsNone(value, text)
        self.each_refusal("review", lambda t: outcome_text(
            review._exit_without_profile, self.conn, t.id, PROJECT),
            "пакет ревьювера")

    def test_pull_plank_by_task_component(self):
        """Подтяжка main задачи на `frontend` гонит планку каналом профиля `frontend`; при отказе `for_task` — отказ без прогона.

        Ловит мутацию: `pull._task_own_profile` на `profile_of(target)` —
        `ComponentsPending` у задачи на `frontend`; при отказе — прогон
        прежним раннером пульта.
        """
        t = self.task("frontend")
        _value, text, seen = self.pull_plank(t)
        self.assertEqual([k["command"].component for k in seen], ["frontend"], text)
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                t = self.task(variant)
                _value, text, seen = self.pull_plank(t)
                self.assertEqual(seen, [], text)
                self.assert_refusal_text(f"{text}\n{self.journal_text(t)}",
                                         variant, "подтяжка")


if __name__ == "__main__":
    unittest.main()
