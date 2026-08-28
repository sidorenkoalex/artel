"""Тесты A4 — роль test_author, приёмочные тесты до кода (tasks/T023/SPEC.md).

Классы названы по критериям приёмки SPEC: маршрут spec_gate (1),
трассируемость AC-n -> тест/пометка (2), лок acceptance_tests/ (3),
прогон приёмки на review -> acceptance (4), эскалация test_author (5).
Guard-функции (AC-разметка SPEC, разбор пометок) — отдельными классами,
структурный слой под FSM-сценариями.

НЕОСЛАБЛЯЕМЫЕ ТЕСТЫ (ADR-0002): `TraceabilityTest` и `LockTest` кодируют
инварианты 26 и 27 реестра (docs/invariants.md) — их отключение или
ослабление допустимо только Оператором отдельным ADR.

Песочница как у `tests/test_advance_guard.py` (лёгкая, `gitcmd.git`
заглушкой) везде, кроме `LockTest`: там нужен настоящий git — лок
проверяется реальным `git diff` между двумя коммитами, заглушкой это
не изобразить (тот же приём, что `RealPultGitTest` в test_git_fixation.py).
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (acceptance, catalog, config, fsm,  # noqa: E402
                          gitcmd, runner, store, workspace)
from scripts import guard  # noqa: E402
from tests.sandbox import FakeProc, TmpRootTest, capture, fake_git  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

SPEC_V2 = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
{extra}---

# SPEC: приёмочные тесты до кода

## Контекст

## Требования

1. ...

## Критерии приёмки

AC-1. Первый критерий, проверяемый тестом.
AC-2. Второй критерий, проверяемый тестом или пометкой.

## Не входит
"""

SPEC_V1 = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: старый формат без AC-разметки

## Контекст

## Требования

1. ...

## Критерии приёмки

1. Критерий без AC-разметки — версия 1, старый беклог.

## Не входит
"""

PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: приёмочные тесты до кода

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

REVIEW_MD = """---
task: {task}
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: приёмочные тесты до кода

## Соответствие SPEC

## Замечания

## Вердикт
"""

AC_TEST_BOTH_COVERED = """import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)


# AC-2: manual — Оператор проверяет глазами на приёмке
"""

AC_TEST_MISSING_AC2 = """import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)
"""

AC_TEST_ESCALATE_AC2 = """import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)


# AC-2: escalate — критерий сформулирован противоречиво, тест не пишется
"""

AC_TEST_GREEN = """import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)

    def test_ac2_second_criterion(self):
        self.assertEqual(1 + 1, 2)
"""

AC_TEST_RED = """import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)

    def test_ac2_second_criterion(self):
        self.fail("код ещё не реализован")
"""


class _AcceptanceFlowTmpRootTest(TmpRootTest):
    """Лёгкая песочница: БД и артефакты во временном каталоге, git — заглушка.

    `ROOT` тоже уводится (SPEC T049: холодный старт сканирует его для
    посева счётчика — непропатченный ROOT читал бы реальное дерево
    пульта) — `templates/` копируется рядом, `cmd_new` продолжает читать
    настоящий `templates/SPEC.md`, только уже из песочницы.
    """

    TASK = "T001"
    PATCHED_ATTRS = ("DB", "TASKS", "LOGS", "ROLE_HOME", "ROLE_CONFIG_DIR",
                     "WORKTREES", "ROOT")

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        patcher = mock.patch.object(gitcmd, "git", fake_git)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Приёмочные тесты до кода")
        self.tdir = config.TASKS / self.TASK
        self.tdir.mkdir(parents=True, exist_ok=True)

    def state(self) -> str:
        return store.db().execute("SELECT state FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()[0]

    def row(self):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def write_spec(self, template: str, extra: str = "") -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(
            template.format(task=self.TASK, extra=extra), encoding="utf-8")

    def write(self, name: str, text: str) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / name).write_text(text.format(task=self.TASK),
                                      encoding="utf-8")

    def write_acceptance_tests(self, content: str,
                               name: str = "test_ac.py") -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / name).write_text(content, encoding="utf-8")

    def journal_details(self, action: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]


TmpRootTest = _AcceptanceFlowTmpRootTest


# --------------------------------------------------------------------------
# Guard: AC-разметка SPEC и разбор пометок (структурный слой под FSM).

class SpecAcMarkupGuardTest(unittest.TestCase):
    """Требование 2, 7: AC-разметка обязательна только для version >= 2
    без skip_tests; версия 1 и skip_tests остаются валидны без правок."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "SPEC.md"

    def write(self, text: str, extra: str = "") -> Path:
        self.path.write_text(text.format(task="T999", extra=extra),
                             encoding="utf-8")
        return self.path

    def test_v2_with_ac_markup_is_valid(self):
        self.assertEqual(guard.check(self.write(SPEC_V2)), [])

    def test_v1_without_ac_markup_stays_valid(self):
        """Требование 7: весь беклог T001–T022 не редактируется и валиден."""
        self.assertEqual(guard.check(self.write(SPEC_V1)), [])

    def test_v2_with_skip_tests_does_not_need_ac_markup(self):
        no_ac = SPEC_V2.replace(
            "AC-1. Первый критерий, проверяемый тестом.\n"
            "AC-2. Второй критерий, проверяемый тестом или пометкой.\n",
            "1. Обычный критерий, тесты пропущены.\n")

        errors = guard.check(self.write(
            no_ac, extra="skip_tests: пропуск по причине\n"))

        self.assertEqual(errors, [])

    def test_v2_without_ac_prefix_is_rejected(self):
        broken = SPEC_V2.replace("AC-1.", "1.").replace("AC-2.", "2.")
        errors = guard.check(self.write(broken))
        self.assertTrue(any("AC-разметки" in e or "AC-n" in e for e in errors),
                        errors)

    def test_v2_without_any_criteria_is_rejected(self):
        broken = SPEC_V2.replace(
            "AC-1. Первый критерий, проверяемый тестом.\n"
            "AC-2. Второй критерий, проверяемый тестом или пометкой.\n", "")
        errors = guard.check(self.write(broken))
        self.assertTrue(any("не размечены AC-n" in e for e in errors), errors)

    def test_duplicate_ac_numbers_are_rejected(self):
        broken = SPEC_V2.replace("AC-2.", "AC-1.")
        errors = guard.check(self.write(broken))
        self.assertTrue(any("повторяются" in e for e in errors), errors)


class ScanAcceptanceTestsTest(unittest.TestCase):
    """Статический разбор acceptance_tests/: тесты и пометки manual/skip/escalate."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)

    def write(self, content: str, name: str = "test_ac.py") -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / name).write_text(content, encoding="utf-8")

    def test_missing_directory_is_empty_not_an_error(self):
        tested, markers = guard.scan_acceptance_tests(self.tdir)
        self.assertEqual(tested, set())
        self.assertEqual(markers, {})

    def test_test_method_naming_convention_is_detected(self):
        self.write("def test_ac3_something():\n    pass\n")
        tested, _ = guard.scan_acceptance_tests(self.tdir)
        self.assertEqual(tested, {3})

    def test_manual_and_skip_markers_with_reasons(self):
        self.write("# AC-1: manual — проверка глазами\n"
                   "# AC-2: skip — временно не проверяем\n")
        _, markers = guard.scan_acceptance_tests(self.tdir)
        self.assertEqual(markers[1], ("manual", "проверка глазами"))
        self.assertEqual(markers[2], ("skip", "временно не проверяем"))

    def test_escalate_marker_with_reason(self):
        self.write("# AC-5: escalate — критерий противоречив\n")
        _, markers = guard.scan_acceptance_tests(self.tdir)
        self.assertEqual(markers[5], ("escalate", "критерий противоречив"))


class AcceptanceTraceabilityFunctionTest(unittest.TestCase):
    """`guard.acceptance_traceability_errors` — источник ошибок для fsm.py."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)
        (self.tdir / "SPEC.md").write_text(
            SPEC_V2.format(task="T999", extra=""), encoding="utf-8")

    def write(self, content: str) -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_ac.py").write_text(content, encoding="utf-8")

    def test_ac_without_test_or_marker_is_named_in_the_error(self):
        self.write(AC_TEST_MISSING_AC2)

        errors = guard.acceptance_traceability_errors(self.tdir)

        self.assertTrue(any("AC-2" in e for e in errors), errors)

    def test_manual_marker_satisfies_the_criterion(self):
        self.write(AC_TEST_BOTH_COVERED)

        self.assertEqual(guard.acceptance_traceability_errors(self.tdir), [])

    def test_marker_or_test_on_unknown_ac_is_flagged(self):
        self.write(AC_TEST_BOTH_COVERED + "\n# AC-9: manual — не из SPEC\n")

        errors = guard.acceptance_traceability_errors(self.tdir)

        self.assertTrue(any("AC-9" in e for e in errors), errors)

    def test_skip_without_reason_is_flagged(self):
        self.write(AC_TEST_MISSING_AC2 + "\n# AC-2: skip\n")

        errors = guard.acceptance_traceability_errors(self.tdir)

        self.assertTrue(any("AC-2" in e and "без причины" in e
                            for e in errors), errors)


# --------------------------------------------------------------------------
# guard: источник-агностичные ядра (SPEC T031) — тот же разбор с диска и
# с ВЕТКИ задачи (orchestrator/fsm.py, `gitcmd.show`/`ls_tree_files`) не
# должен раздваиваться; здесь сверяется само ядро в отрыве от источника
# файлов, минуя git целиком.

class ScanAcContentTest(unittest.TestCase):
    """`guard.scan_ac_content` — то же ядро, что использует
    `scan_acceptance_tests`, но по уже прочитанным текстам."""

    def test_equivalent_to_scan_acceptance_tests_on_disk(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        tdir = Path(tmp.name)
        (tdir / "acceptance_tests").mkdir()
        (tdir / "acceptance_tests" / "test_ac.py").write_text(
            AC_TEST_BOTH_COVERED, encoding="utf-8")

        from_disk = guard.scan_acceptance_tests(tdir)
        from_content = guard.scan_ac_content([AC_TEST_BOTH_COVERED])

        self.assertEqual(from_disk, from_content)

    def test_empty_sources_is_empty_not_an_error(self):
        self.assertEqual(guard.scan_ac_content([]), (set(), {}))

    def test_multiple_sources_are_merged(self):
        tested, markers = guard.scan_ac_content([
            "def test_ac1_x():\n    pass\n",
            "# AC-2: manual — проверка глазами\n",
        ])
        self.assertEqual(tested, {1})
        self.assertEqual(markers[2], ("manual", "проверка глазами"))


class TraceabilityErrorsFromContentTest(unittest.TestCase):
    """`guard.traceability_errors_from_content` — то же ядро, что
    `acceptance_traceability_errors`, но по уже прочитанным SPEC/тестам."""

    def test_equivalent_to_acceptance_traceability_errors_on_disk(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        tdir = Path(tmp.name)
        spec_text = SPEC_V2.format(task="T999", extra="")
        (tdir / "SPEC.md").write_text(spec_text, encoding="utf-8")
        (tdir / "acceptance_tests").mkdir()
        (tdir / "acceptance_tests" / "test_ac.py").write_text(
            AC_TEST_MISSING_AC2, encoding="utf-8")

        from_disk = guard.acceptance_traceability_errors(tdir)
        meta = guard.yamlmini.frontmatter(spec_text) or {}
        tested, markers = guard.scan_ac_content([AC_TEST_MISSING_AC2])
        from_content = guard.traceability_errors_from_content(
            spec_text, meta, tested, markers)

        self.assertEqual(from_disk, from_content)
        self.assertTrue(any("AC-2" in e for e in from_content), from_content)

    def test_skip_tests_meta_short_circuits_to_no_errors(self):
        spec_text = SPEC_V2.format(task="T999", extra="")
        meta = {"schema_version": 2, "skip_tests": "демонстрационный пропуск"}

        errors = guard.traceability_errors_from_content(
            spec_text, meta, set(), {})

        self.assertEqual(errors, [])


class CheckContentTest(unittest.TestCase):
    """`guard.check_content` — то же ядро, что `check`, по уже
    прочитанному тексту (SPEC T031: чтение с диска или с ВЕТКИ задачи
    при чужом чекауте, `orchestrator/fsm.py` `guard_refuses`)."""

    def test_equivalent_to_check_on_disk(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "SPEC.md"
        text = SPEC_V2.format(task="T999", extra="")
        path.write_text(text, encoding="utf-8")

        from_disk = guard.check(path)
        from_content = guard.check_content(str(path), text)

        self.assertEqual(from_disk, from_content)
        self.assertEqual(from_disk, [])

    def test_broken_structure_is_flagged_the_same_way(self):
        text = SPEC_V1.replace("status: ready", "status: недопустимо")

        errors = guard.check_content("ветка:tasks/T999/SPEC.md", text)

        self.assertTrue(any("недопустимый status" in e for e in errors),
                        errors)


# --------------------------------------------------------------------------
# FSM: критерий 1 — маршрут spec_gate -> tests_writing / in_dev.

class SpecGateRoutingTest(TmpRootTest):

    def approve(self) -> str:
        return self.capture(fsm.cmd_approve, self.TASK)

    def test_v2_spec_without_skip_goes_through_tests_writing(self):
        self.write_spec(SPEC_V2)
        self.set_state("spec_gate")

        self.approve()

        self.assertEqual(self.state(), "tests_writing")

    def test_skip_tests_goes_directly_to_in_dev_with_reason_journaled(self):
        self.write_spec(SPEC_V2, extra="skip_tests: демонстрационный пропуск\n")
        self.set_state("spec_gate")

        self.approve()

        self.assertEqual(self.state(), "in_dev")
        details = self.journal_details("state -> in_dev")
        self.assertTrue(any("демонстрационный пропуск" in d for d in details),
                        details)

    def test_old_v1_spec_goes_directly_to_in_dev(self):
        """Требование 7: беклог без AC-разметки не спотыкается о tests_writing."""
        self.write_spec(SPEC_V1)
        self.set_state("spec_gate")

        self.approve()

        self.assertEqual(self.state(), "in_dev")


# --------------------------------------------------------------------------
# FSM: критерий 2 / инвариант 26 — трассируемость AC -> тест на выходе
# tests_writing.

class TraceabilityTest(TmpRootTest):

    def enter_tests_writing(self) -> None:
        self.write_spec(SPEC_V2)
        self.set_state("tests_writing")

    def test_ac2_without_test_or_mark_refuses_with_ac_name_in_message(self):
        self.enter_tests_writing()
        self.write_acceptance_tests(AC_TEST_MISSING_AC2)

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "tests_writing", "переход не прошёл")
        self.assertIn("AC-2", out)

    def test_manual_mark_on_ac2_passes(self):
        self.enter_tests_writing()
        self.write_acceptance_tests(AC_TEST_BOTH_COVERED)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "in_dev")

    def test_escalate_mark_moves_the_task_to_escalated_immediately(self):
        self.enter_tests_writing()
        self.write_acceptance_tests(AC_TEST_ESCALATE_AC2)

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "escalated")
        self.assertEqual(self.row()["escalated_from"], "tests_writing")
        self.assertIn("AC-2", out)

    def test_refusal_is_journaled(self):
        self.enter_tests_writing()
        self.write_acceptance_tests(AC_TEST_MISSING_AC2)

        self.capture(fsm.cmd_advance, self.TASK)

        details = self.journal_details("переход отклонён: трассируемость AC")
        self.assertEqual(len(details), 1)
        self.assertIn("AC-2", details[0])

    def test_empty_acceptance_tests_directory_lists_every_ac(self):
        """Ничего не написано вовсе — не крэш, а понятный список недостающих."""
        self.enter_tests_writing()

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "tests_writing")
        self.assertIn("AC-1", out)
        self.assertIn("AC-2", out)

    def test_success_locks_the_directory_sha(self):
        self.enter_tests_writing()
        self.write_acceptance_tests(AC_TEST_BOTH_COVERED)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "in_dev")
        # git — заглушка (fake_git), fixed_sha пустой: locked-колонка всё
        # равно берёт РОВНО то же значение, что и fixed_sha (не отдельная
        # фиксация) — проверяем именно это соответствие, не конкретный sha.
        self.assertEqual(self.row()["tests_locked_sha"], self.row()["fixed_sha"])


# --------------------------------------------------------------------------
# FSM: критерий 4 — прогон приёмки на review -> acceptance.

class AcceptanceRunTest(TmpRootTest):

    def enter_review(self) -> None:
        self.write_spec(SPEC_V2)
        self.write("PLAN.md", PLAN_MD)
        self.write("REVIEW.md", REVIEW_MD)
        self.set_state("review")

    def test_red_acceptance_tests_block_the_transition(self):
        self.enter_review()
        self.write_acceptance_tests(AC_TEST_RED)

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "review")
        self.assertIn("красные", out)

    def test_red_acceptance_tests_are_journaled(self):
        self.enter_review()
        self.write_acceptance_tests(AC_TEST_RED)

        self.capture(fsm.cmd_advance, self.TASK)

        details = self.journal_details("переход отклонён: приёмочные тесты")
        self.assertEqual(len(details), 1)

    def test_green_acceptance_tests_transition_and_print_summary(self):
        self.enter_review()
        self.write_acceptance_tests(AC_TEST_BOTH_COVERED)

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "acceptance")
        self.assertIn("manual", out)
        self.assertIn("AC-2", out, "manual-критерий назван в карточке гейта")

    def test_summary_is_journaled_on_green_run(self):
        self.enter_review()
        self.write_acceptance_tests(AC_TEST_BOTH_COVERED)

        self.capture(fsm.cmd_advance, self.TASK)

        details = self.journal_details("приёмочные тесты пройдены")
        self.assertEqual(len(details), 1)

    def test_no_acceptance_tests_directory_does_not_block_legacy_tasks(self):
        """Задачи без acceptance_tests/ (skip_tests, либо старше T023)."""
        self.enter_review()

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "acceptance")

    def test_timeout_blocks_the_transition_and_names_the_limit(self):
        """Ревью замечание (итерация 2, major): защита таймаута прогона
        (orchestrator/acceptance.py:run) не была codified тестом — прогон
        без сна, тем же приёмом, что и test_timeout_is_not_retried в
        tests/test_agent_failure.py (мок с side_effect=TimeoutExpired)."""
        self.enter_review()
        self.write_acceptance_tests(AC_TEST_GREEN)
        exc = subprocess.TimeoutExpired(cmd="unittest",
                                        timeout=config.ACCEPTANCE_TIMEOUT_SEC)

        with mock.patch.object(acceptance.subprocess, "run",
                               side_effect=exc) as run_mock:
            out = self.capture(fsm.cmd_advance, self.TASK)

        # side_effect срабатывает независимо от переданных subprocess.run
        # аргументов — сама по себе обработка TimeoutExpired не поймала бы
        # регресс «убрали timeout= из вызова» (реальный subprocess.run без
        # предела просто не бросил бы это исключение). Проверяем отдельно,
        # что run() действительно передаёт timeout=ACCEPTANCE_TIMEOUT_SEC.
        self.assertEqual(run_mock.call_args.kwargs.get("timeout"),
                         config.ACCEPTANCE_TIMEOUT_SEC)
        self.assertEqual(self.state(), "review", "переход не должен пройти")
        self.assertIn(f"превысил {config.ACCEPTANCE_TIMEOUT_SEC}с", out)
        details = self.journal_details("переход отклонён: приёмочные тесты")
        self.assertEqual(len(details), 1)
        self.assertIn("превысил", details[0])


# --------------------------------------------------------------------------
# FSM: критерий 5 — эскалация test_author падением агента (существующая
# механика escalated_from — тот же путь, что и у developer/reviewer).

class EscalationReturnsToTestsWritingTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        self.write_spec(SPEC_V2)
        self.set_state("tests_writing")
        # skills читаются по РЕАЛЬНОМУ config.ROOT (не патчится в этой
        # песочнице — только DB/TASKS/LOGS/ROLE_HOME) — файл уже в репо.
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks",
            lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)
        sleep_patcher = mock.patch.object(runner.time, "sleep", lambda s: None)
        sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

    def run_failing_agent(self) -> str:
        procs = [FakeProc(["упал\n"], 1) for _ in range(config.AGENT_ATTEMPTS)]
        with mock.patch.object(runner, "spawn_agent", side_effect=procs):
            return self.capture(runner.cmd_run, self.TASK)

    def test_test_author_crash_escalates_with_return_point(self):
        out = self.run_failing_agent()

        self.assertEqual(self.state(), "escalated")
        self.assertEqual(self.row()["escalated_from"], "tests_writing")
        self.assertIn("escalated", out)

    def test_approve_returns_to_tests_writing(self):
        self.run_failing_agent()

        self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(self.state(), "tests_writing")


# --------------------------------------------------------------------------
# FSM: критерий 3 / инвариант 27 — лок acceptance_tests/, реальный git.

class LockTest(unittest.TestCase):
    """Правка залоченного файла после выхода из tests_writing — отказ
    перехода in_dev -> review; нетронутые тесты — переход проходит.

    Реальный git (не заглушка): лок сверяется настоящим `git diff` между
    sha, зафиксированным на выходе tests_writing, и текущим HEAD —
    заглушкой этого не изобразить (см. `RealPultGitTest`, test_git_fixation.py).
    """

    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        self.patches = mock.patch.multiple(
            config, ROOT=self.root, DB=self.root / ".artel" / "state.db",
            TASKS=self.root / "tasks", LOGS=self.root / ".artel" / "logs",
            ROLE_HOME=self.root / ".artel" / "home",
            ROLE_CONFIG_DIR=self.root / ".artel" / "home" / ".claude",
            WORKTREES=self.root / ".artel" / "worktrees")
        self.patches.start()
        self.addCleanup(self.patches.stop)

        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Лок приёмочных тестов")
        # С SPEC T048 `cmd_new` сам заводит РЕАЛЬНУЮ ветку/worktree и
        # коммитит в них — ROOT (`self.root`) остаётся на main (требование
        # 4), так что дальнейшие артефакты этого теста коммитятся В
        # WORKTREE задачи (`on_foreign_branch` для него истинно), не в
        # ROOT: коммит поверх main не попал бы на ветку задачи вовсе.
        self.branch = self.row()["branch"]
        self.tdir = workspace.path(self.TASK) / "tasks" / self.TASK

    def git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def git_wt(self, *args: str) -> str:
        res = subprocess.run(["git", "-C", str(workspace.path(self.TASK)),
                              *args], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git -C worktree {' '.join(args)}: {res.stderr}")
        return res.stdout

    capture = staticmethod(capture)

    def state(self) -> str:
        return store.db().execute("SELECT state FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()[0]

    def row(self):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()

    def commit_task_dir(self, message: str = "артефакт") -> None:
        self.git_wt("add", f"tasks/{self.TASK}")
        self.git_wt("commit", "-q", "-m", message)

    def head(self) -> str:
        return self.git_wt("rev-parse", "HEAD").strip()

    def enter_tests_writing(self) -> str:
        (self.tdir / "SPEC.md").write_text(
            SPEC_V2.format(task=self.TASK, extra=""), encoding="utf-8")
        self.commit_task_dir()
        self.capture(fsm.cmd_advance, self.TASK)  # spec_writing -> spec_gate
        sha = self.head()
        self.capture(fsm.cmd_approve, self.TASK, sha)  # -> tests_writing
        self.assertEqual(self.state(), "tests_writing")
        return sha

    def write_acceptance_tests(self, content: str) -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_ac.py").write_text(content, encoding="utf-8")

    def enter_in_dev(self) -> str:
        self.enter_tests_writing()
        self.write_acceptance_tests(AC_TEST_BOTH_COVERED)
        self.commit_task_dir("acceptance_tests от test_author")

        self.capture(fsm.cmd_advance, self.TASK)  # tests_writing -> in_dev

        self.assertEqual(self.state(), "in_dev")
        locked = self.row()["tests_locked_sha"]
        self.assertEqual(locked, self.head(), "лок берёт sha этого коммита")
        (self.tdir / "PLAN.md").write_text(
            PLAN_MD.format(task=self.TASK), encoding="utf-8")
        self.commit_task_dir("PLAN")
        return locked

    def test_edit_after_lock_blocks_in_dev_to_review(self):
        self.enter_in_dev()
        (self.tdir / "acceptance_tests" / "test_ac.py").write_text(
            AC_TEST_MISSING_AC2, encoding="utf-8")
        self.commit_task_dir("разработчик поправил тест — спор с тестом")

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "in_dev", "переход не прошёл")
        self.assertIn("эскалация", out)

    def test_untouched_tests_pass_the_transition(self):
        self.enter_in_dev()

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "review")

    def test_new_unrelated_file_does_not_trip_the_lock(self):
        """Лок реагирует на acceptance_tests/, а не на любой коммит задачи."""
        self.enter_in_dev()
        (self.tdir / "notes.md").write_text("заметка разработчика\n",
                                            encoding="utf-8")
        self.commit_task_dir("заметка вне тестов")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "review")

    def test_unreachable_locked_sha_fails_closed(self):
        """git не может сравнить sha (rebase/squash увёл коммит из истории)
        — отказ перехода, не тихий пропуск лока (REVIEW.md T023, замечание 1,
        blocker: `locked and diff_paths(...)` было `locked and None` = False).
        """
        self.enter_in_dev()
        conn = store.db()
        store.update_task(conn, self.TASK, tests_locked_sha="d" * 40)

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "in_dev", "переход не должен пройти")
        self.assertIn("не проверен", out)


if __name__ == "__main__":
    unittest.main()
