"""Сторожа гейтов итога из отчёта компонента вне долгоживущего файла задачи 01M590GJAF0EDV4NBC4C99MFVH.

Свойства, которые до этого держала только разовая планка задачи:
`checks_local` в узле `acceptance.acceptance_suite` и цепочка
`approve --accept-red` на исходе «неизвестно» (требования 3, 13), выбор
затронутых компонентов гейта мержа по диффу и путям приложений и предел
каждого компонента (требование 10), равенство ключа итога у гейта мержа и
`suite-run` (требование 15). Плюс argv компонента с отчётом без
pytest-аргументов `pytest-own` (требования 4, 7), замок установки
зависимостей (требование 12) и перечень упавших `suite-run` только из
отчёта (требование 18). `checks_local` из записи `targets.yaml` без
подмены профиля задачи — в узле приёмки и на гейте мержа без приложений
PLAN (требование 13), пустой `install` (требование 12).
"""
import contextlib
import dataclasses
import io
import json
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, config, fsm, fsm_merge_gate,
                          project_profile, store, suite_run)
from orchestrator.reporters import outcome
from tests.report_outcome_sandbox import (
    ENTRY_HEAD, REQUIRE_ASSERTIONS, VITEST_BASE, VITEST_REPORT_ARGS, Fake,
    ReportSandbox, block, junit, vitest_report, vitest_test)


def profile(**extra) -> project_profile.Profile:
    fields = dict(command=("./run",), long_lived_dir="", long_lived_name="",
                  weakening_scope=(), mutation_claim_scope=(),
                  report="junit-xml", component="web", project="p",
                  from_components=True)
    fields.update(extra)
    return project_profile.Profile(**fields)


def check(code: int, text: str, marker: Path | None = None) -> tuple:
    """`checks_local`: печатает `text`, отмечает запуск файлом `marker`,
    выходит с кодом `code`."""
    touch = f"open({str(marker)!r}, 'w').close();" if marker else ""
    return (sys.executable, "-c", f"{touch}print({text!r}); raise SystemExit({code})")


UNKNOWN = acceptance.FullSuiteRun(
    False, acceptance.FULL_SUITE_NOT_STARTED, "", Path("/tmp/l.log"),
    acceptance.unknown_line("отчёт не создан") + " (лог прогона: /tmp/l.log)")
GREEN = acceptance.FullSuiteRun(True, acceptance.FULL_SUITE_GREEN,
                                "1 passed", Path("/tmp/l.log"), "зелёный")


class AcceptanceSuiteChecksLocalTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tree = Path(tmp.name).resolve()

    def suite(self, run, checks: tuple, actor: str = "operator"):
        with mock.patch.object(acceptance, "_acceptance_suite_run",
                               return_value=run), \
                mock.patch.object(acceptance, "_task_profile",
                                  return_value=profile(checks_local=checks)):
            return acceptance.acceptance_suite(None, self.tree, "T1", "b",
                                               self.tree, actor=actor)

    def test_failing_check_keeps_unknown_outcome_on_both_paths(self):
        """Провал `checks_local` не перекрашивает исход «неизвестно» в «красный прогон» ни на пути `approve`, ни на пути автогейта; вывод проверки — в детали.

        Ловит мутацию: непрошедшая проверка возвращает `FULL_SUITE_RED`
        при любом исходном итоге — исход «неизвестно» становится красным,
        и `approve --accept-red` его принимает.
        """
        for actor in ("operator", "fsm"):
            with self.subTest(actor=actor):
                run = self.suite(UNKNOWN, check(1, "линтер упал"), actor)
                self.assertFalse(run.green)
                self.assertEqual(run.outcome, acceptance.FULL_SUITE_NOT_STARTED)
                self.assertTrue(acceptance.is_unknown(run), run.detail)
                self.assertIn("линтер упал", run.detail)

    def test_check_runs_after_any_source_and_reddens_only_green(self):
        """`checks_local` исполняется после итога любого источника: прошла — итог прежний, не прошла — зелёный итог становится красным с выводом проверки.

        Ловит мутацию: `acceptance_suite` не зовёт `checks_local` (маркер
        запуска не появляется, зелёный итог при упавшей проверке остаётся
        зелёным) либо проверка зовётся только при свежем прогоне.
        """
        for actor in ("operator", "fsm"):
            with self.subTest(actor=actor):
                marker = self.tree / f"ran-{actor}"
                run = self.suite(GREEN, check(0, "чисто", marker), actor)
                self.assertTrue(marker.exists(), "проверка не исполнялась")
                self.assertEqual(run, GREEN)
                run = self.suite(GREEN, check(2, "тип не сошёлся"), actor)
                self.assertFalse(run.green)
                self.assertEqual(run.outcome, acceptance.FULL_SUITE_RED)
                self.assertIn("тип не сошёлся", run.detail)

    def approve(self, run, checks: tuple, accept_red: str | None) -> bool:
        @contextlib.contextmanager
        def tree(*_args, **_kwargs):
            yield types.SimpleNamespace(root=self.tree, refusal="",
                                        mark=lambda text: text)
        with mock.patch.object(fsm.workspace, "on_task_branch",
                               return_value=True), \
                mock.patch.object(fsm.workspace, "path", return_value=self.tree), \
                mock.patch.object(fsm.workspace, "task_repo",
                                  return_value=self.tree), \
                mock.patch.object(fsm.appendix_tree, "suite_tree", tree), \
                mock.patch.object(fsm.store, "journal"), \
                mock.patch.object(acceptance, "_acceptance_suite_run",
                                  return_value=run), \
                mock.patch.object(acceptance, "_task_profile",
                                  return_value=profile(checks_local=checks)), \
                contextlib.redirect_stdout(io.StringIO()):
            return fsm._acceptance_full_suite_ok(None, "T1", {"branch": "b"},
                                                 accept_red)

    def test_accept_red_refuses_unknown_even_with_failing_check(self):
        """`approve --accept-red` отказывает исходу «неизвестно» и тогда, когда `checks_local` не прошла; красноту зелёного набора от проверки он принимает.

        Ловит мутацию: `checks_local` перекрывает «неизвестно» красным
        исходом — `_acceptance_full_suite_ok` с `accept_red` возвращает
        `True` на неизвестном итоге.
        """
        self.assertFalse(self.approve(UNKNOWN, check(1, "линтер"), "основание"))
        self.assertTrue(self.approve(GREEN, check(1, "линтер"), "основание"))
        self.assertFalse(self.approve(GREEN, check(1, "линтер"), None))


class ReportArgvTest(ReportSandbox):

    def test_vitest_component_with_workdir_gets_exact_pult_argv(self):
        """Компонент `pult-vitest` с `workdir` (`runner: pytest-own`) запускается ровно с базовым argv, флагами пульта и `report_args` — без цели `long_lived_dir`, `--ignore` выкладки и `-p no:cacheprovider`.

        Ловит мутацию: к команде компонента с отчётом и `runner:
        pytest-own` добавляются pytest-аргументы (`src`,
        `--ignore=src/.artel-plank`, `-p no:cacheprovider`).
        """
        case = self.vitest_component(workdir=True)
        case["fake"].scenario(
            version_out=f"vitest/{case['version']} linux-x64 node-v22.11.0",
            report=vitest_report([vitest_test("src/a.test.js", "ok")]))
        run, out = self.full(case["clone"], case["task"], case["profile"])
        self.assertTrue(run.green, self.note(f"{run}\n{out}"))
        args = case["fake"].runs()[-1]["args"]
        head = [*VITEST_BASE[1:], REQUIRE_ASSERTIONS]
        self.assertEqual(args[:len(head)], head, self.note(str(args)))
        self.assertTrue(args[len(head)].startswith("--cacheDir="),
                        self.note(str(args)))
        tail = args[len(head) + 1:]
        self.assertEqual(len(tail), len(VITEST_REPORT_ARGS), self.note(str(args)))
        self.assertEqual([a.split("=", 1)[0] for a in tail],
                         [a.split("=", 1)[0] for a in VITEST_REPORT_ARGS],
                         self.note(str(args)))

    def test_pytest_args_only_for_pytest_command(self):
        """`junit-xml` с `runner: pytest-own`: pytest-аргументы `pytest-own` идут только к команде pytest, к своей команде раннера — нет.

        Ловит мутацию: pytest-аргументы добавляются к любой команде
        `pytest-own` с отчётом (свой раннер получает `-p
        no:cacheprovider` и цель `long_lived_dir`) либо пропадают и у
        pytest.
        """
        tree = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(lambda: __import__("shutil").rmtree(tree, True))
        (tree / "be" / "tests").mkdir(parents=True)
        report = tree / "r.xml"
        for command, expected in (((sys.executable, "-m", "pytest"), True),
                                  (("./run-tests",), False)):
            with self.subTest(command=command):
                prof = profile(command=command, runner="pytest-own",
                               workdir="be", long_lived_dir="be/tests",
                               from_components=False, component="default")
                argv, refusal = acceptance._report_argv(
                    prof, tree, tree / "be", None, report)
                self.assertEqual(refusal, "")
                self.assertEqual("no:cacheprovider" in argv, expected, argv)
                self.assertEqual("tests" in argv, expected, argv)
                self.assertEqual(argv[-2:], ["--junitxml", str(report)], argv)


class InstallLockTest(unittest.TestCase):

    def test_parallel_first_installs_run_once_without_refusal(self):
        """Две параллельные первые установки одного файла блокировки: установка исполняется один раз, обе получают один каталог без отказа.

        Ловит мутацию: установка в общий каталог `deps/<компонент>/<сумма>`
        идёт без замка — вторая сносит дерево первой посреди установки
        (отказ «установка … не удалась» либо двойная установка).
        """
        tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(lambda: (acceptance._chmod_tree(tmp, False),
                                 __import__("shutil").rmtree(tmp, True)))
        cwd = tmp / "wd"
        cwd.mkdir()
        (cwd / "package-lock.json").write_text('{"v": 1}\n', encoding="utf-8")
        log = tmp / "installs.log"
        script = (f"import os, time; open({str(log)!r}, 'a').write('x\\n');"
                  f"time.sleep(0.5); os.makedirs('node_modules/pkg');"
                  f"open('node_modules/pkg/i.js', 'w').write('1')")
        prof = profile(install=(sys.executable, "-c", script))
        results = []
        with mock.patch.object(config, "PROJECTS", tmp / "projects"):
            threads = [threading.Thread(
                target=lambda: results.append(acceptance._install(prof, cwd)))
                for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(60)
        self.assertEqual([r[2] for r in results], ["", ""], results)
        self.assertEqual(results[0][:2], results[1][:2])
        self.assertEqual(results[0][1], ["node_modules"])
        self.assertEqual(log.read_text(encoding="utf-8").count("x"), 1)


class SuiteRunParseReportedTest(unittest.TestCase):

    def test_failures_of_reported_output_come_only_from_report(self):
        """`suite_run.parse` вывода профиля с отчётом: упавшие и повтор — только id из сводки отчёта, строки хода раннера (`-v`, id от `workdir`) не читаются; прежний разбор без отчёта их читает.

        Ловит мутацию: `parse` профиля с отчётом читает строки хода сырого
        вывода — в `failures`/`rerun` попадает id от `workdir` рядом с id
        из отчёта.
        """
        records = [outcome.CaseResult("be:be/tests/test_x.py::T::test_a",
                                      outcome.PASSED),
                   outcome.CaseResult("be:be/tests/test_x.py::T::test_b",
                                      outcome.FAILED, "AssertionError")]
        raw = ("tests/test_x.py::T::test_a PASSED\n"
               "tests/test_x.py::T::test_b FAILED\n")
        output = f"{raw}{outcome.summary_block(records)}\n"
        parsed = suite_run.parse(False, output, reported=True)
        self.assertEqual([n for n, _ in parsed.failures],
                         ["be:be/tests/test_x.py::T::test_b"])
        self.assertEqual(parsed.rerun, ("be:be/tests/test_x.py::T::test_b",))
        self.assertEqual((parsed.passed, parsed.failed), (1, 1))
        plain = suite_run.parse(False, output)
        self.assertIn("tests/test_x.py::T::test_b",
                      [n for n, _ in plain.failures])


class MergeGateComponentsTest(ReportSandbox):

    def two_components(self, limits: tuple = (None, None)) -> str:
        name = f"p{self.word()}"
        text = ENTRY_HEAD.format(name=name) + "    components:\n"
        for comp, area, limit in (("api", "api", limits[0]),
                                  ("web", "web", limits[1])):
            fields = {"command": [sys.executable, "-m", "pytest"],
                      "weakening_scope": [f"{area}/**"],
                      "mutation_claim_scope": [f"{area}/**"],
                      "paths": [f"{area}/.*"], "report": "junit-xml"}
            if limit is not None:
                fields["full_suite_timeout_sec"] = limit
            text += f"      {comp}:\n" + block(fields, "        ")
        self.entries.append(text)
        self.write_targets()
        return name

    def selected(self, name: str, changed, paths: list) -> list:
        ctx = types.SimpleNamespace(target=name, path=self.root)
        with mock.patch.object(fsm_merge_gate.store, "task_branch",
                               return_value="task/x"), \
                mock.patch.object(fsm_merge_gate.gitcmd, "diff_base",
                                  return_value="base"), \
                mock.patch.object(fsm_merge_gate.gitcmd, "diff_names",
                                  return_value=changed):
            chosen = fsm_merge_gate._selected_components(None, "T1", paths, ctx)
        return [p.component for p in chosen]

    def test_components_chosen_by_branch_diff_and_appendix_paths(self):
        """Гейт мержа выбирает компоненты по диффу ветки вместе с путями приложений: компонент, затронутый только приложением, тоже идёт; дифф не прочитан — все.

        Ловит мутацию: выбор компонентов не учитывает пути приложений
        (компонент `web`, затронутый только приложением, не прогоняется)
        либо при непрочитанном диффе выбор молча сужается.
        """
        name = self.two_components()
        self.assertEqual(self.selected(name, ["api/a.py"], []), ["api"])
        self.assertEqual(self.selected(name, ["api/a.py"], ["web/x.py"]),
                         ["api", "web"])
        self.assertEqual(self.selected(name, None, []), ["api", "web"])

    def test_each_component_runs_with_its_own_limit(self):
        """Узел по компонентам гоняет каждый компонент записи из двух со своим `full_suite_timeout_sec`.

        Ловит мутацию: предел полного набора берётся по проекту
        (`full_suite_limit`), а не по компоненту — оба прогона идут с одним
        пределом.
        """
        name = self.two_components((self.rng.randint(100, 400),
                                    self.rng.randint(500, 900)))
        task = self.task(name)
        profiles = project_profile.component_profiles(name)
        seen = []

        def fake(root, command=None, **kwargs):
            seen.append((command.component, kwargs.get("limit", (None,))[0]))
            return True, "1 passed in 0.01s\n"
        with mock.patch.object(acceptance, "run_full_suite", fake), \
                contextlib.redirect_stdout(io.StringIO()):
            acceptance.components_full_suite(self.root, task, profiles,
                                             fresh=True)
        self.assertEqual(seen, [(p.component, p.full_suite_timeout_sec)
                                for p in profiles], self.note())


class SuiteRunKeyTest(ReportSandbox):

    def test_merge_gate_and_suite_run_keys_match_with_tools(self):
        """Профиль `suite-run` компонента с отчётом несёт `tools`, и ключ итога у него тот же, что у профиля гейта мержа (`decide`); без `tools` ключ другой.

        Ловит мутацию: `suite_run._profile_command` строит профиль без
        `with_tools` — `tools` пусты, ключ `suite-run` расходится с ключом
        гейта мержа.
        """
        version = f"22.{self.rng.randint(0, 20)}.0"
        case = self.junit_component(tools={"node": version})
        gate = self.profile(case["name"])
        run_profile, refusal = suite_run._profile_command(case["name"])
        self.assertEqual(refusal, "")
        self.assertEqual(dict(run_profile.tools), {"node": version})
        tree = acceptance.suite_tree_hash(case["clone"])
        for base in (False, True):
            with self.subTest(base=base):
                key = acceptance.suite_result_key(tree, gate, base=base,
                                                  root=case["clone"])
                self.assertIsNotNone(key)
                self.assertEqual(acceptance.suite_result_key(
                    tree, run_profile, base=base, root=case["clone"]), key)
                bare = dataclasses.replace(run_profile, tools={})
                self.assertNotEqual(acceptance.suite_result_key(
                    tree, bare, base=base, root=case["clone"]), key)


class Reached(Exception):
    """Гейт мержа дошёл до публикации мержа — дальше тесту идти незачем."""


class ChecksLocalFromRecordTest(ReportSandbox):
    """`checks_local` из записи `targets.yaml`, без подмены профиля задачи:
    поле доезжает через `project_profile.with_tools` до узла приёмки и до
    гейта мержа без приложений PLAN (требование 13)."""

    def check_script(self) -> tuple:
        """(исполняемая проверка вне дерева, маркер запуска, файл кода
        выхода): печатает строку с текстом проверки и выходит с кодом из
        файла."""
        folder = Path(tempfile.mkdtemp(prefix="artel-check-")).resolve()
        self.addCleanup(__import__("shutil").rmtree, folder, True)
        marker, code = folder / "ran", folder / "code"
        script = folder / "check"
        script.write_text(
            f"#!{sys.executable}\nimport sys\n"
            f"open({str(marker)!r}, 'a').write('x\\n')\n"
            f"print('проверка компонента: код', open({str(code)!r}).read())\n"
            f"sys.exit(int(open({str(code)!r}).read()))\n", encoding="utf-8")
        script.chmod(0o755)
        return script, marker, code

    def checked_case(self, code: int) -> dict:
        script, marker, code_file = self.check_script()
        code_file.write_text(str(code), encoding="utf-8")
        case = self.junit_component(checks_local=[str(script)])
        case["fake"].scenario(stdout="1 passed in 0.01s\n", report=junit(
            [("src/x.test.jsx", "test_ok", "passed", "", "", "0.1")]))
        case.update(marker=marker, code_file=code_file)
        return case

    def journal(self, task_id: str, action: str) -> list:
        return [r["detail"] for r in store.task_steps(store.db(), task_id)
                if r["action"] == action]

    def test_record_checks_local_runs_in_acceptance_suite(self):
        """Запись с одним компонентом и `checks_local`: `decide(...).profile.checks_local` непуст, узел `acceptance.acceptance_suite` на обоих путях (`operator`, `fsm`) исполняет проверку из записи; прошла — итог зелёный, не прошла — красный с её выводом.

        Ловит мутацию: `project_profile.with_tools` (или
        `_with_component_fields`) теряет поле `checks_local` — профиль
        задачи приходит без проверок, маркер запуска не появляется, и
        зелёный набор при упавшей проверке остаётся зелёным.
        """
        case = self.checked_case(0)
        self.assertEqual(project_profile.decide(case["name"]).profile.checks_local,
                         (str(Path(case["marker"]).parent / "check"),))
        branch = store.task_branch(store.db(), case["task"])
        for actor in ("operator", "fsm"):
            with self.subTest(actor=actor):
                case["code_file"].write_text("0", encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()):
                    run = acceptance.acceptance_suite(
                        store.db(), case["clone"], case["task"], branch,
                        case["clone"], actor=actor, fresh=True)
                self.assertTrue(run.green, self.note(str(run)))
                case["code_file"].write_text("3", encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()):
                    run = acceptance.acceptance_suite(
                        store.db(), case["clone"], case["task"], branch,
                        case["clone"], actor=actor, fresh=True)
                self.assertFalse(run.green, self.note(str(run)))
                self.assertEqual(run.outcome, acceptance.FULL_SUITE_RED)
                self.assertIn("проверка компонента: код 3", run.detail)
        self.assertEqual(case["marker"].read_text().count("x"), 4,
                         self.note("проверка из записи исполнялась не каждый раз"))
        self.assertEqual(len(self.journal(case["task"],
                                          acceptance.CHECKS_LOCAL_ACTION)), 4)

    def merge(self, case: dict):
        """Тело гейта мержа `_cmd_approve_merge_gate` на дереве клона
        проекта: шаги до плотницкого мержа — исход «ок», приложений PLAN
        нет (узел `_apply_plan_appendices` настоящий), публикация мержа —
        `Reached`."""
        ok = lambda *a, **k: False  # noqa: E731
        patches = [
            mock.patch.object(fsm_merge_gate, "_docs_ref_unsynced", ok),
            mock.patch.object(fsm_merge_gate, "_protected_path_diff_gate", ok),
            mock.patch.object(fsm_merge_gate, "_test_integrity_diff_gate", ok),
            mock.patch.object(fsm_merge_gate, "_ensure_branch_head_published",
                              lambda *a, **k: "ok"),
            mock.patch.object(fsm_merge_gate, "_sync_main_or_wait",
                              lambda *a, **k: "fresh"),
            mock.patch.object(fsm_merge_gate, "_outcome_integrity_merge_gate",
                              ok),
            mock.patch.object(fsm_merge_gate, "_acceptance_locks_refuse", ok),
            mock.patch.object(fsm_merge_gate, "_ci_ready_or_wait",
                              lambda *a, **k: "ok"),
            mock.patch.object(fsm_merge_gate, "_refuse_if_main_red",
                              lambda *a, **k: None),
            mock.patch.object(fsm_merge_gate, "_perform_carpentry_merge",
                              lambda *a, **k: ("ok", case["clone"])),
            mock.patch.object(fsm_merge_gate, "_plan_appendices_or_refuse",
                              lambda *a, **k: []),
            mock.patch.object(fsm_merge_gate, "_drop_scratch_worktree",
                              lambda *a, **k: None),
            mock.patch.object(fsm_merge_gate, "_publish_merge_artifacts",
                              mock.Mock(side_effect=Reached)),
        ]
        conn = store.db()
        t = store.get_task(conn, case["task"])
        with contextlib.ExitStack() as stack:
            for patcher in patches:
                stack.enter_context(patcher)
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            return fsm_merge_gate._cmd_approve_merge_gate(
                conn, case["task"], "merge_gate", t)

    def test_merge_gate_without_appendices_runs_record_checks_local(self):
        """Гейт мержа без приложений PLAN: упавшая `checks_local` записи отказывает мерж (задача на гейте, вывод проверки в журнале `merge FAILED`), прошедшая пишется в журнал и мерж идёт дальше.

        Ловит мутацию: вызов `_checks_local_refuse` перенесён внутрь
        `_full_suite_or_refuse` (или в ветку с применёнными приложениями) —
        без приложений проверка не исполняется, упавшая не отказывает, и
        гейт доходит до публикации мержа.
        """
        case = self.checked_case(5)
        self.assertEqual(self.merge(case), ("stopped",), self.note())
        refusals = self.journal(case["task"],
                                fsm_merge_gate.CHECKS_LOCAL_REFUSAL_ACTION)
        self.assertTrue(any("проверка компонента: код 5" in r for r in refusals),
                        self.note(str(refusals)))
        self.assertEqual(store.task_state(store.db(), case["task"]), "in_dev")
        case["code_file"].write_text("0", encoding="utf-8")
        with self.assertRaises(Reached):
            self.merge(case)
        records = self.journal(case["task"], acceptance.CHECKS_LOCAL_ACTION)
        self.assertEqual(len(records), 2, self.note(str(records)))
        self.assertIn("— код 0", records[-1])
        self.assertEqual(case["marker"].read_text().count("x"), 2)


class EmptyInstallTest(ReportSandbox):

    def test_empty_install_neither_installs_nor_refuses(self):
        """Запись `test_profile` с итогом из отчёта (`runner: pytest-own`, `report: junit-xml`) и `install: []` без файла блокировки: прогон зелёный по отчёту, отказа «install без файла блокировки» нет, каталог установок пульта не заводится.

        Ловит мутацию: пустой `install` считается объявленной установкой
        (`if profile.install is None` вместо `if not profile.install`) —
        прогон отказывает «install без файла блокировки не исполняется»
        либо заводит каталог `deps/` пульта.
        """
        fake = Fake(self, "junit")
        workdir = f"be{self.word(5)}"
        name, clone = self.project(
            self.junit_fields(fake, workdir, install=[]),
            {f"{workdir}/src/x.test.py": "# тест\n"})
        prof = self.profile(name)
        self.assertEqual(prof.install, ())
        fake.scenario(stdout="1 passed in 0.01s\n", report=junit(
            [("src/x.test.py", "test_ok", "passed", "", "", "0.1")]))
        run, out = self.full(clone, self.task(name), prof)
        self.assertTrue(run.green, self.note(f"{run}\n{out}"))
        self.assertNotIn(acceptance.INSTALL_WITHOUT_LOCK, f"{run.detail}\n{out}")
        self.assertFalse((config.PROJECTS / name / "deps").exists())
        self.assertEqual(acceptance._install(prof, clone / workdir),
                         (None, [], ""))


if __name__ == "__main__":
    unittest.main()
