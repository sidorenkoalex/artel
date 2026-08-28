"""Тесты A5 — роль analyst: SPEC из свободного ТЗ Оператора (tasks/T025/SPEC.md).

Классы названы по критериям приёмки SPEC: маршрут run/auto по наличию
TZ.md (1), регрессия guard-механики AC-разметки на существующем пути (2),
батч вопросов и эскалация (3). Guard-функции (структура TZ/QUESTIONS) —
отдельными классами, структурный слой под FSM-сценариями (по образцу
tests/test_acceptance_tests_flow.py).

Песочница — лёгкая (`gitcmd.git` заглушкой) везде, кроме прогона агента
(`RunAnalystTest`), где нужны те же подмены, что и в
tests/test_agent_prompt.py: keychain, pre-flight, Popen.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artel, auto, catalog, config, fsm, gitcmd, runner, store  # noqa: E402
from scripts import guard  # noqa: E402
from tests.sandbox import TmpRootTest, fake_git  # noqa: E402

TZ_RAW = "Хотим кнопку экспорта отчёта в CSV на странице задач.\n"

SPEC_V2_NO_AC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: без AC-разметки

## Контекст

## Требования

1. ...

## Критерии приёмки

1. Критерий без AC-разметки — версия 2, обязана отказать.

## Не входит
"""

SPEC_V2_READY = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: с AC-разметкой

## Контекст

## Требования

1. ...

## Критерии приёмки

AC-1. Критерий, размеченный корректно.

## Не входит
"""

QUESTIONS_VALID = """---
task: {task}
type: questions
author_role: analyst
status: draft
schema_version: 2
---

# QUESTIONS: батч

## Вопросы

1. **Что считать успешным экспортом?** — варианты: A) CSV; B) XLSX —
   дефолт: A.
"""

QUESTIONS_NO_SECTION = """---
task: {task}
type: questions
author_role: analyst
status: draft
schema_version: 2
---

# QUESTIONS: батч без секции

Текст без обязательного заголовка.
"""


class _AnalystRoleTmpRootTest(TmpRootTest):
    """Лёгкая песочница: БД и артефакты во временном каталоге, git — заглушка."""

    TASK = "T001"
    PATCHED_ATTRS = ("DB", "TASKS", "LOGS", "ROLE_HOME", "ROLE_CONFIG_DIR",
                     "WORKTREES")

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(gitcmd, "git", fake_git)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)
        # `config.TASKS` реально существует и в проде (`tasks/` пульта);
        # с SPEC T048 `cmd_new` больше не заводит его побочно как раньше
        # (пишет в worktree, не на диск main) — тесты, кладущие артефакты
        # на диск напрямую (`write`/`write_tz`, симуляция ветко-корректного
        # fallback), нуждаются в каталоге сами.
        config.TASKS.mkdir(parents=True, exist_ok=True)
        self.capture(catalog.cmd_new, "Аналитик из ТЗ")
        self.tdir = config.TASKS / self.TASK

    def wt_tdir(self, task_id: str | None = None) -> Path:
        """Каталог артефактов задачи В ВОРКТРИ (SPEC T048): `cmd_new` с
        этой задачи пишет TZ.md/SPEC.md туда, не в `config.TASKS`."""
        tid = task_id or self.TASK
        return config.WORKTREES / tid / "tasks" / tid

    def state(self) -> str:
        return store.db().execute("SELECT state FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()[0]

    def row(self):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()

    def write(self, name: str, template: str) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / name).write_text(template.format(task=self.TASK),
                                      encoding="utf-8")

    def write_tz(self, raw: str = TZ_RAW) -> Path:
        """Пишет TZ.md ЭТОЙ задаче напрямую — не через `cmd_new` (не
        заводит вторую задачу, только добавляет вход analyst к self.TASK)."""
        self.tdir.mkdir(parents=True, exist_ok=True)
        tz_path = self.tdir / "TZ.md"
        tz_path.write_text(
            catalog._tz_document(self.TASK, "Аналитик из ТЗ", raw),
            encoding="utf-8")
        return tz_path

    def journal_details(self, action: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]


TmpRootTest = _AnalystRoleTmpRootTest


# --------------------------------------------------------------------------
# Guard: структура TZ.md и QUESTIONS.md (структурный слой под FSM).

class GuardNewTypesTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "artifact.md"

    def write(self, text: str) -> Path:
        self.path.write_text(text.format(task="T999"), encoding="utf-8")
        return self.path

    def test_tz_with_minimal_frontmatter_and_free_body_is_valid(self):
        text = ("---\ntask: T999\ntype: tz\nauthor_role: operator\n"
               "status: draft\nschema_version: 2\n---\n\n"
               "Совершенно свободный текст без единого заголовка.\n")
        self.assertEqual(guard.check(self.write(text)), [])

    def test_tz_without_frontmatter_is_rejected(self):
        errors = guard.check(self.write("Просто текст без шапки.\n"))
        self.assertTrue(any("frontmatter" in e for e in errors), errors)

    def test_tz_with_unknown_status_is_rejected(self):
        text = ("---\ntask: T999\ntype: tz\nauthor_role: operator\n"
               "status: approved\nschema_version: 2\n---\n\nсвободно\n")
        errors = guard.check(self.write(text))
        self.assertTrue(any("status" in e for e in errors), errors)

    def test_questions_with_vopросы_section_is_valid(self):
        self.assertEqual(guard.check(self.write(QUESTIONS_VALID)), [])

    def test_questions_without_section_is_rejected(self):
        errors = guard.check(self.write(QUESTIONS_NO_SECTION))
        self.assertTrue(any("Вопросы" in e for e in errors), errors)


# --------------------------------------------------------------------------
# `catalog.cmd_new`: заведение TZ.md флагом (критерий приёмки 1, часть 1).

class CmdNewTzTest(TmpRootTest):
    """С SPEC T048 `cmd_new` пишет TZ.md/SPEC.md в ВОРКТРИ задачи, не на
    диск main (`config.TASKS`) — проверки ниже смотрят в `wt_tdir()`, не
    в `self.tdir` (тот теперь используется только как отдельная
    диск-песочница остальных FSM-тестов этого файла, требование 4)."""

    def test_without_tz_flag_behaves_as_before(self):
        wt_dir = self.wt_tdir()
        self.assertFalse((wt_dir / "TZ.md").exists())
        self.assertTrue((wt_dir / "SPEC.md").exists())

    def test_tz_flag_creates_a_guard_valid_artifact(self):
        tz_file = self.tdir.parent / "tz-input.txt"
        tz_file.write_text(TZ_RAW, encoding="utf-8")

        out = self.capture(catalog.cmd_new, "Экспорт CSV", str(tz_file))

        task_id = out.split("]")[0].strip("[")
        tz_path = self.wt_tdir(task_id) / "TZ.md"
        self.assertTrue(tz_path.exists())
        self.assertEqual(guard.check(tz_path), [])
        self.assertIn(TZ_RAW.strip(), tz_path.read_text(encoding="utf-8"))
        self.assertIn("run", out)

    def test_unreadable_tz_path_exits_with_reason(self):
        missing = self.tdir.parent / "нет-такого-файла.txt"

        with self.assertRaises(SystemExit) as ctx:
            catalog.cmd_new("Экспорт CSV", str(missing))

        self.assertIn("ТЗ не прочитано", str(ctx.exception))

    def test_unreadable_tz_path_leaves_no_half_created_task(self):
        """Отказ до расхода номера счётчика и до создания задачи — иначе
        БД получает сироту без ветки/воркри. Сверяется с БД, не с
        листингом каталога (conventions-core: `tasks/` двигают
        параллельные сессии)."""
        missing = self.tdir.parent / "нет-такого-файла.txt"

        with self.assertRaises(SystemExit):
            catalog.cmd_new("Экспорт CSV", str(missing))

        self.assertIsNone(store.db().execute(
            "SELECT 1 FROM tasks WHERE id='T002'").fetchone(),
            "отказ не должен создавать вторую задачу")
        # Следующая задача получает T002, а не T003 — номер не пропущен.
        self.capture(catalog.cmd_new, "Следующая задача")
        self.assertIsNotNone(store.db().execute(
            "SELECT 1 FROM tasks WHERE id='T002'").fetchone())


# --------------------------------------------------------------------------
# `artel.py`: разбор `--tz` — регрессия на замечание ревью (REVIEW.md,
# iteration 1, major): флаг последним аргументом без значения падал
# необработанным IndexError вместо понятного отказа.

class ArtelCliTzFlagTest(TmpRootTest):

    def test_tz_flag_without_value_exits_with_reason_not_indexerror(self):
        with self.assertRaises(SystemExit) as ctx:
            artel._tz_arg(["Экспорт CSV", "--tz"])
        self.assertIn("--tz", str(ctx.exception))

    def test_tz_flag_with_value_returns_it(self):
        self.assertEqual(
            artel._tz_arg(["Экспорт CSV", "--tz", "путь.txt"]), "путь.txt")

    def test_without_tz_flag_returns_none(self):
        self.assertIsNone(artel._tz_arg(["Экспорт CSV"]))

    def test_cli_new_with_dangling_tz_flag_exits_cleanly(self):
        """Воспроизводит замечание ревью буквально через `main()`: `new
        "название" --tz` без пути к файлу — понятный отказ, не трейсбек,
        и без наполовину созданной задачи (сверка с БД, не с листингом
        каталога — conventions-core)."""
        with mock.patch.object(sys, "argv",
                               ["artel.py", "new", "Экспорт CSV", "--tz"]):
            with self.assertRaises(SystemExit) as ctx:
                artel.main()
        self.assertIn("--tz", str(ctx.exception))
        self.assertIsNone(store.db().execute(
            "SELECT 1 FROM tasks WHERE id='T002'").fetchone(),
            "дефектный --tz не должен был завести вторую задачу")


# --------------------------------------------------------------------------
# FSM: критерий приёмки 1 (маршрут run) — без реального агента.

class RunWithoutAgentTest(TmpRootTest):
    """Именованный отказ без ТЗ и резолвинг роли — до запуска процесса."""

    def test_run_without_tz_refuses_by_name(self):
        with self.assertRaises(SystemExit) as ctx:
            with mock.patch.object(runner, "spawn_agent") as popen:
                runner.cmd_run(self.TASK)

        popen.assert_not_called()
        self.assertIn("SPEC пишет Оператор", str(ctx.exception))

    def test_step_role_is_none_without_tz(self):
        self.assertIsNone(runner.step_role(self.row()))

    def test_step_role_is_analyst_with_tz(self):
        self.write_tz()

        self.assertEqual(runner.step_role(self.row()), "analyst")

    def test_other_roleless_state_keeps_the_old_generic_message(self):
        conn = store.db()
        conn.execute("UPDATE tasks SET state='done' WHERE id=?", (self.TASK,))
        conn.commit()

        with self.assertRaises(SystemExit) as ctx:
            runner.cmd_run(self.TASK)

        self.assertIn("в состоянии done агент не запускается", str(ctx.exception))


class RunAnalystTest(TmpRootTest):
    """Критерий приёмки 1, часть 2: `run` реально стартует analyst при ТЗ."""

    def setUp(self):
        super().setUp()
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks",
            lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

    def run_agent(self) -> mock.Mock:
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            self.capture(runner.cmd_run, self.TASK)
        return popen

    def test_run_starts_analyst_when_tz_present(self):
        self.write_tz()

        popen = self.run_agent()

        prompt_path = Path(popen.call_args.kwargs["stdin"].name)
        prompt = prompt_path.read_text(encoding="utf-8")
        self.assertIn("Роль: аналитик", prompt)
        self.assertIn("TZ.md", prompt)
        self.assertIn("conventions-core", prompt)


class FakeStream:
    def __init__(self, lines):
        self.lines = iter(lines)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.lines)

    def close(self):
        pass


class FakeProc:
    def __init__(self, lines, returncode: int = 0):
        self.stdout = FakeStream(lines)
        self.returncode = returncode

    def wait(self, timeout=None) -> int:
        return self.returncode


# --------------------------------------------------------------------------
# `auto`: требование 2 — цикл сам запускает analyst при ТЗ, без ТЗ стоит как раньше.

class AutoAnalystTest(TmpRootTest):

    def auto(self) -> str:
        return self.capture(auto.cmd_auto, self.TASK)

    def test_auto_without_tz_stops_immediately_as_before(self):
        with mock.patch.object(runner, "cmd_run") as cmd_run:
            out = self.auto()

        cmd_run.assert_not_called()
        self.assertIn("SPEC ещё пишется", out)
        self.assertEqual(self.state(), "spec_writing")

    def test_auto_runs_analyst_and_stops_at_spec_gate(self):
        self.write_tz()

        def fake_run(task_id: str, session_id: str | None = None) -> None:
            self.write("SPEC.md", SPEC_V2_READY)

        with mock.patch.object(runner, "cmd_run", side_effect=fake_run) as cmd_run:
            out = self.auto()

        self.assertEqual(cmd_run.call_count, 1)
        self.assertEqual(self.state(), "spec_gate")
        self.assertIn("гейт SPEC", out)


# --------------------------------------------------------------------------
# FSM: критерий приёмки 2 — регрессия существующей guard-механики AC-разметки.

class SpecGateAcMarkupRegressionTest(TmpRootTest):

    def test_spec_without_ac_markup_refuses_the_transition(self):
        self.write("SPEC.md", SPEC_V2_NO_AC)

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "spec_writing")
        self.assertIn("AC-n", out)

    def test_spec_with_ac_markup_passes(self):
        self.write("SPEC.md", SPEC_V2_READY)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "spec_gate")


# --------------------------------------------------------------------------
# FSM: критерий приёмки 3 — батч вопросов, эскалация, возврат.

class QuestionsEscalationTest(TmpRootTest):

    def test_valid_questions_escalates_immediately(self):
        self.write("QUESTIONS.md", QUESTIONS_VALID)

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "escalated")
        self.assertEqual(self.row()["escalated_from"], "spec_writing")
        self.assertIn("эскалация analyst", out)

    def test_invalid_questions_blocks_the_transition_not_escalates(self):
        self.write("QUESTIONS.md", QUESTIONS_NO_SECTION)

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "spec_writing")
        self.assertIn("Вопросы", out)

    def test_questions_are_checked_before_spec_status(self):
        """SPEC.md ещё draft (аналитик не дописал) — вопросы всё равно
        эскалируют немедленно, не дожидаясь его готовности."""
        self.write("QUESTIONS.md", QUESTIONS_VALID)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "escalated")

    def test_approve_from_escalated_returns_to_spec_writing(self):
        self.write("QUESTIONS.md", QUESTIONS_VALID)
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "escalated")

        self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(self.state(), "spec_writing")
        self.assertIsNone(self.row()["escalated_from"])


if __name__ == "__main__":
    unittest.main()
