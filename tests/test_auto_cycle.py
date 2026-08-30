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
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (agent_log, auto, budget, catalog,  # noqa: E402
                          config, fsm, gitcmd, pause, runner, store)
from tests.sandbox import capture, fake_git  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

# Настоящая `cmd_run`, снятая до подмены: тесту отказа по бюджету нужна она,
# а не фейк — предмет проверки в том, как auto реагирует на реальный отказ.
REAL_CMD_RUN = runner.cmd_run

# Все состояния FSM Фазы 0 — тот же список, что в tests/test_invariants.py:
# реестра состояний в коде нет, а свипы этого модуля должны идти по всем.
FSM_STATES = ("spec_writing", "spec_gate", "in_dev", "review", "acceptance",
              "merge_gate", "done", "escalated", "killed")

# Заготовки валидны по guard: с T017 он вызывается на каждом переходе
# `advance`, и артефакт без обязательных секций цикл дальше не пускает.
PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: {status}
schema_version: 1
---

# PLAN: цикл auto

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

REVIEW_MD = """---
task: {task}
type: review
author_role: reviewer
status: {status}
iteration: {iteration}
schema_version: 1
---

# REVIEW: цикл auto

## Соответствие SPEC

## Замечания

## Вердикт

## Проверено исполнением
`python3 -m unittest discover -s tests` — зелёный.
"""


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

    Свой потолок вызовов (`arm`) — не дубль лимита цикла, а способ его
    пришпилить: холостой шаг состояние не двигает, поэтому цикл без рабочего
    `AUTO_MAX_STEPS` крутился бы вечно, и тест лимита не падал бы, а висел —
    в CI это шесть часов молчания вместо красного прогона.
    """

    def __init__(self):
        self.script: list = []
        self.calls: list[str] = []
        self.limit: int | None = None

    def arm(self, steps: int) -> None:
        """Разрешает ещё `steps` вызовов — столько, сколько цикл вправе сделать."""
        self.limit = len(self.calls) + steps

    def __call__(self, task_id: str, session_id: str | None = None) -> None:
        if self.limit is not None and len(self.calls) >= self.limit:
            raise AssertionError(
                f"цикл не остановился: шагов больше {config.AUTO_MAX_STEPS}")
        self.calls.append(task_id)
        if self.script:
            self.script.pop(0)()


class SpyCommand:
    """Шпион вместо команды Оператора: вызов запоминается, тело не исполняется."""

    def __init__(self):
        self.calls: list[tuple] = []

    def __call__(self, *args, **kwargs) -> None:
        self.calls.append(args)


class AutoCycleTest(unittest.TestCase):
    """Песочница цикла: БД и артефакты во временном каталоге, агент подменён."""

    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        # `ROOT` тоже уводится (SPEC T049: холодный старт сканирует его для
        # посева счётчика — непропатченный ROOT читал бы реальное дерево
        # пульта); `templates/` копируется рядом, `cmd_new` продолжает
        # читать настоящий `templates/SPEC.md`, только уже из песочницы.
        shutil.copytree(REPO_ROOT / "templates", root / "templates")

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            ("ROOT", root),
                            ("PROJECTS", root / ".artel" / "projects"),
                            ("TARGETS", root / "targets.yaml"),
                            # Курируемый слой ролей (T019): каталог заводит
                            # запуск шага — пусть заводит в песочнице, а не
                            # в .artel/ репозитория.
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude"),
                            ("BACKUP_MARKER", root / ".artel" / "backup-marker"),
                            # `cmd_new` (SPEC T048) пишет TZ.md/SPEC.md в
                            # worktree — пусть тоже в песочницу, не в
                            # `.artel/worktrees/` репозитория.
                            ("WORKTREES", root / ".artel" / "worktrees")):
            self.patch_object(config, attr, value)

        # git настоящему репозиторию в этих тестах не нужен: цикл его не
        # зовёт, а команды внутри него (ревью-пакет, merge) либо подменены,
        # либо не должны случиться — и это проверяется по списку вызовов.
        self.patch_object(gitcmd, "git", fake_git)
        self.git_spy = SpyRun()
        self.patch_object(gitcmd.subprocess, "run", self.git_spy)

        self.agent = FakeRun()
        self.patch_object(runner, "cmd_run", self.agent)

        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Цикл auto")
        self.tdir = config.TASKS / self.TASK
        # С SPEC T048 `cmd_new` пишет артефакты в worktree, не на диск
        # main — тесты этого файла кладут PLAN.md/REVIEW.md/... напрямую
        # на диск (симуляция ветко-корректного fallback), каталог для них
        # заводит сам файл, не `cmd_new`.
        self.tdir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ утилиты

    def patch_object(self, target, attr: str, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    capture = staticmethod(capture)

    def auto(self) -> str:
        # Столько шагов цикл вправе сделать за вызов; шаг сверх этого — не
        # «долгий прогон», а неостановленный цикл, и тест обязан упасть сразу.
        self.agent.arm(config.AUTO_MAX_STEPS)
        return self.capture(auto.cmd_auto, self.TASK)

    def task_row(self) -> sqlite3.Row:
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.task_row()["state"]

    def set_state(self, state: str, **fields) -> None:
        """Ставит состояние (и, если нужно, счётчики) в обход переходов."""
        conn = store.db()
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
        return [(r["actor"], r["action"], r["detail"]) for r in store.db().execute(
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
            if state in config.STATE_ROLE:
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

                reason, _ = config.AUTO_STOP[state]
                self.assertIn(reason, out)
                self.assertIn("дальше:", out)
                self.assertIn(f"artel.py {command} {self.TASK}", out)

    def test_stop_table_covers_every_state_outside_state_role(self):
        """Полнота таблицы подсказок: состояние без строки — остановка без совета."""
        self.assertEqual(set(config.AUTO_STOP),
                         set(FSM_STATES) - set(config.STATE_ROLE))

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

    def test_escalation_by_the_ceiling_names_budget(self):
        """Требование 2: у эскалации по потолку следующая команда — budget.

        approve здесь увёл бы Оператора по кругу: задача вернулась бы в работу,
        а следующий run снова отказался бы стартовать по тому же потолку.
        """
        self.write_plan("ready")
        self.set_state("in_dev", budget_usd=25.0, spent_usd=0.0)
        # Так задачу роняет enforce_budget: шаг стоил больше остатка потолка.
        self.agent.script = [lambda: self.set_state("escalated", spent_usd=26.0)]

        out = self.auto()

        self.assertEqual(self.state(), "escalated")
        self.assertIn(f"дальше: подними потолок: artel.py budget {self.TASK}", out)
        self.assertNotIn(f"artel.py approve {self.TASK}", out)

    def test_escalation_with_the_ceiling_intact_names_approve(self):
        """Вторая ветка: потолок цел (упал агент) — разбор через log и approve."""
        self.write_plan("ready")
        self.set_state("in_dev", budget_usd=25.0, spent_usd=1.0)
        self.agent.script = [lambda: self.set_state("escalated")]

        out = self.auto()

        self.assertEqual(self.state(), "escalated")
        self.assertIn(f"artel.py approve {self.TASK}", out)
        self.assertNotIn(f"artel.py budget {self.TASK}", out)

    def test_escalation_inside_the_step_stops_the_cycle_before_advance(self):
        """Упавший агент уводит задачу в escalated — двигать её нечем и незачем."""
        self.write_plan("ready")
        self.set_state("in_dev")
        self.agent.script = [lambda: self.set_state("escalated")]
        advance = SpyCommand()
        self.patch_object(fsm, "cmd_advance", advance)

        out = self.auto()

        self.assertEqual(self.state(), "escalated")
        self.assertEqual(advance.calls, [], "advance вызван из escalated")
        self.assertIn("эскалация — нужен Оператор", out)


class FakeAdvance:
    """Подмена `fsm.cmd_advance`: сценарий журналирует заданный текст
    `action` (или ничего) и всегда возвращает `False` — тот же по
    характеру исход, что и у настоящего отказа `advance`, отличного от
    отказа guard'ом (SPEC T038, требование 3: guard возвращает `True`,
    сюда не долетает).
    """

    def __init__(self):
        self.script: list = []
        self.calls = 0

    def __call__(self, task_id: str, session_id: str | None = None) -> bool:
        self.calls += 1
        action = self.script.pop(0) if self.script else None
        if action is not None:
            store.journal(store.db(), task_id, "fsm", action,
                          "деталь тестового отказа")
        return False


class AutoStopsOnRepeatedAdvanceRefusalTest(AutoCycleTest):
    """SPEC T038: стоп-кран по двум подряд отказам `advance` с тем же
    текстом `action` — инцидент T035 (11 повторов одного детерминированного
    отказа сожгли ~$9)."""

    def setUp(self):
        super().setUp()
        self.write_plan("ready")
        self.set_state("in_dev")
        self.advance = FakeAdvance()
        self.patch_object(fsm, "cmd_advance", self.advance)

    def test_ac1_identical_refusal_twice_in_a_row_stops_the_cycle(self):
        """AC-1: остановка на ВТОРОМ из двух отказов, задача — там же, где
        была перед первым; причина и подсказка — в выводе."""
        text = "переход отклонён: рабочая копия артефактов грязная"
        self.advance.script = [text, text]

        out = self.auto()

        self.assertEqual(self.advance.calls, 2,
                         "цикл не остановился на втором подряд отказе")
        self.assertEqual(self.state(), "in_dev")
        self.assertIn("auto остановлен", out)
        self.assertIn(text, out)
        self.assertIn(f"почини причину и повтори artel.py advance {self.TASK}",
                      out)

    def test_ac1_stop_is_journalled_with_the_reused_refusal_text(self):
        """Требование 2: причина остановки в журнале — текст, уже
        записанный `fsm`, не пересказ своими словами."""
        text = "переход отклонён: лок приёмочных тестов"
        self.advance.script = [text, text]

        self.auto()

        detail = self.journal_detail("auto остановлен")
        self.assertIn(text, detail)
        self.assertIn(f"почини причину и повтори artel.py advance {self.TASK}",
                      detail)

    def test_ac2_refusal_without_a_journal_entry_does_not_count(self):
        """AC-2 / требование 4: шаг без записи в журнал (агент ещё
        работает) не входит в серию — цикл идёт до штатного лимита."""
        self.advance.script = []  # ни разу не журналирует отказ

        out = self.auto()

        self.assertEqual(self.advance.calls, config.AUTO_MAX_STEPS)
        self.assertIn(f"лимит {config.AUTO_MAX_STEPS} шагов", out)
        self.assertNotIn(
            f"почини причину и повтори artel.py advance {self.TASK}", out)

    def test_ac3_two_different_refusal_texts_do_not_stop_the_cycle(self):
        """AC-3: разный текст на двух подряд шагах — не серия."""
        self.advance.script = [
            "переход отклонён: рабочая копия артефактов грязная",
            "переход отклонён: трассируемость AC",
        ]

        out = self.auto()

        self.assertEqual(self.advance.calls, config.AUTO_MAX_STEPS,
                         "разные тексты отказа не должны были остановить цикл")
        self.assertIn(f"лимит {config.AUTO_MAX_STEPS} шагов", out)
        self.assertNotIn(
            f"почини причину и повтори artel.py advance {self.TASK}", out)

    def test_a_step_without_a_refusal_breaks_the_streak(self):
        """Требование 4: одинаковый отказ ДО и ПОСЛЕ холостого шага (агент
        ещё работает) — не подряд, стоп-кран не срабатывает."""
        text = "переход отклонён: дерево не на ветке задачи"
        self.advance.script = [text, None, text]

        out = self.auto()

        self.assertEqual(self.advance.calls, config.AUTO_MAX_STEPS,
                         "отказ через холостой шаг не должен был засчитаться")
        self.assertIn(f"лимит {config.AUTO_MAX_STEPS} шагов", out)
        self.assertNotIn(
            f"почини причину и повтори artel.py advance {self.TASK}", out)

    def test_progress_between_refusals_does_not_carry_the_streak_across_states(self):
        """Отказ до смены состояния не складывается с таким же по тексту
        отказом после неё в одну серию — прогресс между ними рвёт счёт.

        Шаг 1: отказ `text` в `in_dev`. Шаг 2: агент сам двигает состояние
        в `review` (роль `reviewer` там тоже есть — advance вызывается),
        отказа нет. Шаг 3: отказ тем же `text`, но уже в `review` — это
        первый отказ новой серии, не вторая половина старой.
        """
        text = "переход отклонён: приёмочные тесты"
        self.agent.script = [lambda: None, lambda: self.set_state("review"),
                             lambda: None]
        self.advance.script = [text, None, text]

        out = self.auto()

        self.assertEqual(self.advance.calls, config.AUTO_MAX_STEPS,
                         "отказ до смены состояния сложился с отказом после "
                         "неё в одну серию — цикл остановился раньше лимита")
        self.assertIn(f"лимит {config.AUTO_MAX_STEPS} шагов", out)
        self.assertNotIn(
            f"почини причину и повтори artel.py advance {self.TASK}", out)


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
        self.patch_object(runner, "cmd_run", REAL_CMD_RUN)
        self.write_plan("ready")
        self.set_state("in_dev", budget_usd=1.0, spent_usd=1.0)

    def test_cycle_stops_and_no_agent_starts(self):
        with mock.patch.object(runner, "spawn_agent") as popen:
            out = self.auto()

        popen.assert_not_called()
        self.assertEqual(self.state(), "in_dev", "задача осталась где стояла")
        self.assertIn("бюджет исчерпан", out)
        self.assertIn("run отказался стартовать", out)
        self.assertIn(f"artel.py budget {self.TASK}", out)

    def test_refusal_is_not_retried(self):
        """Отказ — причина остановки, а не повод зайти на второй круг."""
        with mock.patch.object(runner, "spawn_agent") as popen:
            self.auto()

        popen.assert_not_called()
        self.assertEqual(
            [a for _, a, _ in self.journal_rows()].count("auto остановлен"), 1)

    def test_refusal_lands_in_the_journal(self):
        with mock.patch.object(runner, "spawn_agent"):
            self.auto()

        self.assertIn("run отказался стартовать",
                      self.journal_detail("auto остановлен"))


class AutoStopsOnPauseRefusalTest(AutoCycleTest):
    """SPEC T070, требование 2: пауза, поставленная до старта `auto`,
    останавливает цикл на первой же попытке `run` — не после
    `AUTO_MAX_STEPS` попыток (регресс REVIEW.md итерации 1: `auto` не
    отличал отказ по паузе от «шаг ещё не готов» и прокручивал цикл до
    предела, а итоговое сообщение называло лимит шагов, а не паузу).

    `cmd_run` тут настоящая — по тому же доводу, что и у
    `AutoStopsOnBudgetRefusalTest`: имитация отказа доказывала бы только
    то, что тест умеет бросать `SystemExit`, а не то, что `auto`
    действительно отличает отказ по паузе от прочих.
    """

    def setUp(self):
        super().setUp()
        # Поверх подмены базового класса — настоящая команда: до Popen она
        # не доходит, отказ случается на пометке паузы.
        self.patch_object(runner, "cmd_run", REAL_CMD_RUN)
        self.write_plan("ready")
        self.set_state("in_dev")
        pause.cmd_pause(self.TASK)

    def test_cycle_stops_on_the_first_attempt_and_no_agent_starts(self):
        with mock.patch.object(runner, "spawn_agent") as popen:
            out = self.auto()

        popen.assert_not_called()
        self.assertEqual(self.state(), "in_dev", "задача осталась где стояла")
        self.assertIn("задача на паузе", out)
        self.assertIn(f"artel.py resume {self.TASK}", out)

    def test_refusal_is_not_retried(self):
        """Отказ — причина остановки, а не повод крутиться до лимита шагов."""
        with mock.patch.object(runner, "spawn_agent") as popen:
            self.auto()

        popen.assert_not_called()
        self.assertEqual(
            [a for _, a, _ in self.journal_rows()]
            .count("run отклонён: задача на паузе"), 1,
            "run на паузе отказал больше одного раза за вызов auto")

    def test_final_message_names_pause_not_the_step_limit(self):
        with mock.patch.object(runner, "spawn_agent"):
            out = self.auto()

        # "лимит N шагов за вызов" тоже встречается на старте (информационная
        # строка) — предмет проверки в том, что СТОП не мотивирован лимитом.
        self.assertNotIn(f"лимит {config.AUTO_MAX_STEPS} шагов исчерпан", out)

    def test_refusal_lands_in_the_journal(self):
        with mock.patch.object(runner, "spawn_agent"):
            self.auto()

        self.assertIn("задача на паузе",
                      self.journal_detail("auto остановлен"))


class AutoStopsOnPauseAndBudgetTogetherTest(AutoCycleTest):
    """REVIEW.md T070, итерация 2, замечание 1 (major): пауза и исчерпанный
    бюджет — независимые пометки, Оператор вправе выставить обе одной и той
    же задаче (снизить потолок и поставить паузу — «остановить понадёжнее»).
    `budget_block` в `runner._cmd_run` проверяется РАНЬШЕ паузы (та же
    функция, budget выше по коду) — значит именно бюджет и есть настоящая
    причина этого конкретного отказа `run`, а не пауза, хотя пометка паузы
    тоже стоит. Итоговое сообщение обязано называть бюджет: `resume` его не
    решает, а старая реализация (опрос текущего `pause.is_paused` вместо
    разбора того, что журналировал именно этот вызов) называла бы паузу.
    """

    def setUp(self):
        super().setUp()
        self.patch_object(runner, "cmd_run", REAL_CMD_RUN)
        self.write_plan("ready")
        self.set_state("in_dev", budget_usd=1.0, spent_usd=2.0)
        pause.cmd_pause(self.TASK)

    def test_final_message_names_budget_not_pause(self):
        with mock.patch.object(runner, "spawn_agent") as popen:
            out = self.auto()

        popen.assert_not_called()
        self.assertEqual(self.state(), "in_dev", "задача осталась где стояла")
        self.assertIn("run отказался стартовать", out)
        self.assertIn(f"artel.py budget {self.TASK}", out)
        self.assertNotIn("auto остановлен: задача на паузе", out)

    def test_journal_names_budget_not_pause(self):
        with mock.patch.object(runner, "spawn_agent"):
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

        self.assertEqual(len(self.agent.calls), config.AUTO_MAX_STEPS)
        self.assertIn(f"лимит {config.AUTO_MAX_STEPS} шагов", out)

    def test_limit_is_not_an_escalation(self):
        """Задача остаётся в своём состоянии: лимит вызова — не сбой задачи."""
        out = self.auto()

        self.assertEqual(self.state(), "in_dev")
        self.assertIn(f"artel.py auto {self.TASK}", out)

    def test_limit_is_per_call(self):
        """Лимит считается заново: повторный вызов продолжает работу."""
        self.auto()

        self.auto()

        self.assertEqual(len(self.agent.calls), config.AUTO_MAX_STEPS * 2)


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
        log = agent_log.new_agent_log(self.TASK, "developer")

        out = self.auto()

        self.assertIn(f"шаг 1/{config.AUTO_MAX_STEPS}", out)
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
                       f"состояние in_dev, лимит {config.AUTO_MAX_STEPS} шагов"),
                      rows)
        self.assertEqual([(actor, action) for actor, action, _ in rows
                          if action == "auto остановлен"],
                         [("operator", "auto остановлен")])

    def test_stop_reason_is_in_the_journal_detail(self):
        """Требование 5: причина остановки — в detail, а не только на экране."""
        self.auto()

        detail = self.journal_detail("auto остановлен")
        self.assertTrue(detail.startswith("acceptance:"), detail)
        self.assertIn(config.AUTO_STOP["acceptance"][0], detail)


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
        self.patch_object(fsm, "cmd_approve", approve)
        self.patch_object(fsm, "cmd_reject", reject)

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


class AutoLeaseTest(AutoCycleTest):
    """SPEC T044: `auto` берёт lease задачи один раз на весь цикл.

    Приёмочные тесты (tasks/T044/acceptance_tests) кроют AC-1..AC-4 через
    все семь команд сквозным путём с реальным `runner.cmd_run`; здесь —
    именно обёртка `auto.cmd_auto` в изоляции (агент подменён `FakeRun`,
    как и в остальных тестах этого файла), два её собственных края: отказ
    до первого шага цикла и освобождение по завершении.
    """

    def test_foreign_fresh_lease_refuses_before_the_first_step(self):
        self.set_state("in_dev")
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-holder", 999, "holder-host", store.now()))
        conn.commit()

        out = self.capture(auto.cmd_auto, self.TASK, "sess-caller")

        self.assertIn("sess-holder", out)
        self.assertIn("holder-host", out)
        self.assertEqual(self.agent.calls, [], "auto запустила шаг при чужом lease")
        self.assertEqual(self.state(), "in_dev")

    def test_own_fresh_lease_is_released_when_the_cycle_stops(self):
        """Гейт без единого шага (роли нет с самого начала) — lease всё
        равно взят и отпущен: следующая сессия его не встречает."""
        self.set_state("spec_gate", reviewed_iter=0)

        self.capture(auto.cmd_auto, self.TASK, "sess-a")

        self.assertIsNone(store.lease_row(store.db(), self.TASK),
                          "cmd_auto не отпустила взятый ею с нуля lease")


if __name__ == "__main__":
    unittest.main()
