"""Тесты команды `auto` — цикла до ближайшего гейта (см. tasks/T014/SPEC.md).

Реального CLI здесь нет: `cmd_run` подменяется заготовленным исходом шага,
поэтому проверяется именно цикл — условие выхода, лимит шагов, подсказки
Оператору и журнал, а не механика прогона агента (она своя у `cmd_run`:
tests/test_agent_log.py, tests/test_agent_failure.py, tests/test_step_cost.py).
Исключение — отказ по бюджету: там `cmd_run` настоящая, потому что предмет
теста в том, как auto реагирует на её отказ, а не на его имитацию.

НЕОСЛАБЛЯЕМЫЕ ТЕСТЫ (ADR-0002, принцип целостности): `AutoNeverPassesAGateTest`
кодирует инвариант «auto не проходит ручной гейт и не имеет пути мимо него»
(docs/design.md §4, tasks/T014/SPEC.md, требование 3). Ослабить, заскипать
или удалить его может только Оператор отдельным ADR; перечень «инвариант →
тест → откуда» — docs/invariants.md.
"""
import io
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artel  # noqa: E402

# Настоящая `cmd_run`, снятая до подмены: тесту отказа по бюджету нужна она,
# а не фейк — предмет проверки в том, как auto реагирует на реальный отказ.
REAL_CMD_RUN = artel.cmd_run

# Все состояния FSM Фазы 0 — тот же список, что в tests/test_invariants.py:
# реестра состояний в коде нет, а свипы этого модуля должны идти по всем.
FSM_STATES = ("spec_writing", "spec_gate", "in_dev", "review", "acceptance",
              "merge_gate", "done", "escalated", "killed")

PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: {status}
---

# PLAN: цикл auto
"""

REVIEW_MD = """---
task: {task}
type: review
author_role: reviewer
status: {status}
iteration: {iteration}
---

# REVIEW: цикл auto
"""


def fake_git(*args: str) -> subprocess.CompletedProcess:
    """Подмена `artel.git`: пустой ответ вместо обращения к репозиторию."""
    return subprocess.CompletedProcess(list(args), 0, "", "")


class SpyRun:
    """Подмена `subprocess.run`: команда запоминается и не исполняется."""

    def __init__(self):
        self.calls: list[list[str]] = []

    def __call__(self, cmd, *args, **kwargs) -> subprocess.CompletedProcess:
        self.calls.append(list(cmd))
        return subprocess.CompletedProcess(list(cmd), 0, "", "")

    def git_subcommands(self) -> list[str]:
        return [c[1] for c in self.calls if len(c) > 1 and c[0] == "git"]


class FakeRun:
    """Подмена `cmd_run`: вместо агента — заготовленные исходы шагов.

    Каждый вызов берёт следующее действие сценария: так тест описывает, что
    агент «сделал» на шаге — дописал артефакт, уронил задачу в escalated или
    ничего. Кончился сценарий — шаг холостой, и это законный исход: агент,
    не доведший PLAN до ready, оставляет задачу там же, где она была.
    """

    def __init__(self):
        self.script: list = []
        self.calls: list[str] = []

    def __call__(self, task_id: str) -> None:
        self.calls.append(task_id)
        if self.script:
            self.script.pop(0)()


class SpyCommand:
    """Шпион вместо команды Оператора: вызов запоминается, тело не исполняется."""

    def __init__(self):
        self.calls: list[tuple] = []

    def __call__(self, *args) -> None:
        self.calls.append(args)


class AutoCycleTest(unittest.TestCase):
    """Песочница цикла: БД и артефакты во временном каталоге, агент подменён."""

    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs")):
            self.patch(attr, value)

        # git настоящему репозиторию в этих тестах не нужен: цикл его не
        # зовёт, а команды внутри него (ревью-пакет, merge) либо подменены,
        # либо не должны случиться — и это проверяется по списку вызовов.
        self.patch("git", fake_git)
        self.git_spy = SpyRun()
        self.patch_object(artel.subprocess, "run", self.git_spy)

        self.agent = FakeRun()
        self.patch("cmd_run", self.agent)

        self.capture(artel.cmd_init)
        self.capture(artel.cmd_new, "Цикл auto")
        self.tdir = artel.TASKS / self.TASK

    # ------------------------------------------------------------ утилиты

    def patch(self, attr: str, value) -> None:
        self.patch_object(artel, attr, value)

    def patch_object(self, target, attr: str, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def capture(self, fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def auto(self) -> str:
        return self.capture(artel.cmd_auto, self.TASK)

    def task_row(self) -> sqlite3.Row:
        return artel.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.task_row()["state"]

    def set_state(self, state: str, **fields) -> None:
        """Ставит состояние (и, если нужно, счётчики) в обход переходов."""
        conn = artel.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        for column, value in fields.items():
            conn.execute(f"UPDATE tasks SET {column}=? WHERE id=?",
                         (value, self.TASK))
        conn.commit()

    def write_plan(self, status: str) -> None:
        (self.tdir / "PLAN.md").write_text(
            PLAN_MD.format(task=self.TASK, status=status), encoding="utf-8")

    def write_review(self, status: str, iteration: int) -> None:
        (self.tdir / "REVIEW.md").write_text(
            REVIEW_MD.format(task=self.TASK, status=status, iteration=iteration),
            encoding="utf-8")

    def journal_rows(self) -> list[tuple[str, str, str]]:
        return [(r["actor"], r["action"], r["detail"]) for r in artel.db().execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def journal_detail(self, action: str) -> str:
        """Detail единственной записи журнала с таким action."""
        details = [d for _, a, d in self.journal_rows() if a == action]
        self.assertEqual(len(details), 1, f"записей «{action}»: {len(details)}")
        return details[0]


class AutoStopsWhereTheOperatorIsNeededTest(AutoCycleTest):
    """Требования 1, 2: цикл идёт по агентским состояниям и встаёт перед человеком."""

    def test_every_state_outside_state_role_stops_the_cycle(self):
        """Ни в одном неагентском состоянии цикл не делает шага."""
        for state in FSM_STATES:
            if state in artel.STATE_ROLE:
                continue
            with self.subTest(состояние=state):
                self.set_state(state)
                self.agent.calls.clear()

                out = self.auto()

                self.assertEqual(self.agent.calls, [], f"из {state} запущен агент")
                self.assertEqual(self.state(), state)
                self.assertIn("auto остановлен", out)
                self.assertIn(f"состояние: {state}", out)

    def test_stop_names_the_reason_and_the_next_command(self):
        """Требование 2: итог, причина и следующая команда Оператора."""
        expected = {
            "spec_gate": "approve",
            "acceptance": "approve",
            "merge_gate": "approve",
            "escalated": "log",
            "spec_writing": "advance",
        }
        for state, command in expected.items():
            with self.subTest(состояние=state):
                self.set_state(state)

                out = self.auto()

                reason, _ = artel.AUTO_STOP[state]
                self.assertIn(reason, out)
                self.assertIn("дальше:", out)
                self.assertIn(f"artel.py {command} {self.TASK}", out)

    def test_stop_table_covers_every_state_outside_state_role(self):
        """Полнота таблицы подсказок: состояние без строки — остановка без совета."""
        self.assertEqual(set(artel.AUTO_STOP),
                         set(FSM_STATES) - set(artel.STATE_ROLE))

    def test_terminal_states_ask_for_nothing(self):
        for state in ("done", "killed"):
            with self.subTest(состояние=state):
                self.set_state(state)

                out = self.auto()

                self.assertIn("ничего не требуется", out)

    def test_cycle_runs_the_task_from_dev_to_acceptance(self):
        """Критерий приёмки 1: от in_dev до приёмки без ручных run и advance."""
        self.write_plan("ready")
        self.set_state("in_dev")
        self.agent.script = [lambda: None, lambda: self.write_review("approved", 1)]

        out = self.auto()

        self.assertEqual(self.state(), "acceptance")
        self.assertEqual(len(self.agent.calls), 2)
        self.assertIn("приёмка — решение Оператора", out)

    def test_review_iterations_are_passed_without_the_operator(self):
        """Замечания ревью — тоже агентские шаги: цикл их отрабатывает сам."""
        self.write_plan("ready")
        self.set_state("in_dev")
        self.agent.script = [
            lambda: None,                                    # разработчик
            lambda: self.write_review("changes_requested", 1),  # ревьювер: доработать
            lambda: None,                                    # разработчик
            lambda: self.write_review("approved", 2),        # ревьювер: принято
        ]

        self.auto()

        self.assertEqual(self.state(), "acceptance")
        self.assertEqual(len(self.agent.calls), 4)
        self.assertEqual(self.task_row()["review_iters"], 1)

    def test_escalation_inside_the_step_stops_the_cycle_before_advance(self):
        """Упавший агент уводит задачу в escalated — двигать её нечем и незачем."""
        self.write_plan("ready")
        self.set_state("in_dev")
        self.agent.script = [lambda: self.set_state("escalated")]
        advance = SpyCommand()
        self.patch("cmd_advance", advance)

        out = self.auto()

        self.assertEqual(self.state(), "escalated")
        self.assertEqual(advance.calls, [], "advance вызван из escalated")
        self.assertIn("эскалация — нужен Оператор", out)


class AutoStopsOnBudgetRefusalTest(AutoCycleTest):
    """Требование 1: отказ `run` стартовать останавливает цикл, а не ретраится.

    `cmd_run` тут настоящая: предмет теста — реакция auto на её отказ по
    исчерпанному потолку (инвариант 9, docs/invariants.md), а имитация
    отказа доказывала бы только то, что тест умеет бросать SystemExit.
    """

    def setUp(self):
        super().setUp()
        # Поверх подмены базового класса — настоящая команда: до Popen она
        # не доходит, отказ случается на потолке.
        self.patch("cmd_run", REAL_CMD_RUN)
        self.write_plan("ready")
        self.set_state("in_dev", budget_usd=1.0, spent_usd=1.0)

    def test_cycle_stops_and_no_agent_starts(self):
        with mock.patch.object(artel.subprocess, "Popen") as popen:
            out = self.auto()

        popen.assert_not_called()
        self.assertEqual(self.state(), "in_dev", "задача осталась где стояла")
        self.assertIn("бюджет исчерпан", out)
        self.assertIn("run отказался стартовать", out)
        self.assertIn(f"artel.py budget {self.TASK}", out)

    def test_refusal_is_not_retried(self):
        """Отказ — причина остановки, а не повод зайти на второй круг."""
        with mock.patch.object(artel.subprocess, "Popen") as popen:
            self.auto()

        popen.assert_not_called()
        self.assertEqual(
            [a for _, a, _ in self.journal_rows()].count("auto остановлен"), 1)

    def test_refusal_lands_in_the_journal(self):
        with mock.patch.object(artel.subprocess, "Popen"):
            self.auto()

        self.assertIn("run отказался стартовать",
                      self.journal_detail("auto остановлен"))


class AutoStepLimitTest(AutoCycleTest):
    """Требование 4: у цикла числовой лимит, и по нему — Оператор, не ретрай."""

    def setUp(self):
        super().setUp()
        # PLAN не ready: шаг не двигает состояние, и цикл упирается в лимит —
        # ровно тот случай, ради которого лимит и стоит.
        self.write_plan("draft")
        self.set_state("in_dev")

    def test_cycle_stops_after_the_limit(self):
        out = self.auto()

        self.assertEqual(len(self.agent.calls), artel.AUTO_MAX_STEPS)
        self.assertIn(f"лимит {artel.AUTO_MAX_STEPS} шагов", out)

    def test_limit_is_not_an_escalation(self):
        """Задача остаётся в своём состоянии: лимит вызова — не сбой задачи."""
        out = self.auto()

        self.assertEqual(self.state(), "in_dev")
        self.assertIn(f"artel.py auto {self.TASK}", out)

    def test_limit_is_per_call(self):
        """Лимит считается заново: повторный вызов продолжает работу."""
        self.auto()

        self.auto()

        self.assertEqual(len(self.agent.calls), artel.AUTO_MAX_STEPS * 2)


class AutoReportsTheCycleTest(AutoCycleTest):
    """Требования 5, 6: журнал старта и остановки, сводка переходов и логи."""

    def setUp(self):
        super().setUp()
        self.write_plan("ready")
        self.set_state("in_dev")
        # Два шага до приёмки: разработчик и ревьювер. Цикл заканчивается
        # осмысленной остановкой, а не лимитом — иначе тесты этого класса
        # проверяли бы вывод холостых прогонов.
        self.agent.script = [lambda: None,
                             lambda: self.write_review("approved", 1)]

    def test_step_summary_names_the_transition_and_the_log(self):
        log = artel.new_agent_log(self.TASK, "developer")

        out = self.auto()

        self.assertIn(f"шаг 1/{artel.AUTO_MAX_STEPS}", out)
        self.assertIn("developer in_dev -> review", out)
        self.assertIn(f"лог: {log}", out)

    def test_step_without_a_log_does_not_break_the_summary(self):
        """Прогонов роли ещё не было — сводка печатается, цикл идёт дальше."""
        out = self.auto()

        self.assertIn("лог: —", out)
        self.assertEqual(self.state(), "acceptance")

    def test_start_and_stop_are_journalled_by_the_operator(self):
        self.auto()

        rows = self.journal_rows()
        self.assertIn(("operator", "auto старт",
                       f"состояние in_dev, лимит {artel.AUTO_MAX_STEPS} шагов"),
                      rows)
        self.assertEqual([(actor, action) for actor, action, _ in rows
                          if action == "auto остановлен"],
                         [("operator", "auto остановлен")])

    def test_stop_reason_is_in_the_journal_detail(self):
        """Требование 5: причина остановки — в detail, а не только на экране."""
        self.auto()

        detail = self.journal_detail("auto остановлен")
        self.assertTrue(detail.startswith("acceptance:"), detail)
        self.assertIn(artel.AUTO_STOP["acceptance"][0], detail)


class AutoNeverPassesAGateTest(AutoCycleTest):
    """Инвариант: `auto` не проходит ручной гейт и не имеет пути мимо него.

    Источник: docs/design.md §4 (решения на гейтах — ручные всегда),
    README «Инварианты» 4 (молчание ≠ согласие), tasks/T014/SPEC.md,
    требование 3. Команда, которая сама себя двигает, опасна ровно одним —
    возможностью нажать approve за Оператора; здесь проверяется, что такой
    возможности у неё нет ни из одного состояния FSM.
    """

    GATES = ("spec_gate", "acceptance", "merge_gate")

    def setUp(self):
        super().setUp()
        # Артефакты готовы намеренно: гейт должен держаться решением
        # Оператора, а не отсутствием документов.
        self.write_plan("ready")
        self.write_review("approved", 1)

    def test_auto_calls_neither_approve_nor_reject_from_any_state(self):
        approve, reject = SpyCommand(), SpyCommand()
        self.patch("cmd_approve", approve)
        self.patch("cmd_reject", reject)

        for state in FSM_STATES:
            with self.subTest(состояние=state):
                # reviewed_iter=0: вердикт снова свежий, иначе цикл из review
                # упёрся бы в «уже учтён» и до гейта не дошёл.
                self.set_state(state, reviewed_iter=0)

                self.auto()

                self.assertEqual(approve.calls, [],
                                 f"auto из {state} вызвала approve")
                self.assertEqual(reject.calls, [],
                                 f"auto из {state} вызвала reject")

    def test_gate_stands_however_many_times_auto_is_called(self):
        """Повторный вызов — не согласие: гейт стоит, сколько auto ни зови."""
        for gate in self.GATES:
            with self.subTest(гейт=gate):
                self.set_state(gate, reviewed_iter=0)

                for _ in range(5):
                    self.auto()

                self.assertEqual(self.state(), gate)
                self.assertNotIn("merge", self.git_spy.git_subcommands())

    def test_cycle_stops_at_the_gate_it_reaches(self):
        """Дойдя до гейта своим ходом, цикл встаёт перед ним, а не проходит."""
        self.set_state("in_dev", reviewed_iter=0)

        self.auto()

        self.assertEqual(self.state(), "acceptance",
                         "auto увела задачу дальше приёмки")
        self.assertNotIn("merge", self.git_spy.git_subcommands())


if __name__ == "__main__":
    unittest.main()
