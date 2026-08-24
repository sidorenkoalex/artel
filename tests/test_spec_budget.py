"""Тесты бюджета задачи из frontmatter SPEC (см. tasks/T012/SPEC.md).

Проверяется вся дорога числа: разбор поля `budget_usd`, применение ровно
на переходе spec_writing -> spec_gate, тишина при отсутствии поля,
предупреждение при мусоре, отказ от значения выше дефолта (потолок отсюда
только понижается, инвариант 10) и приоритет ручного поднятия `budget` над
значением из SPEC — в обоих порядках.

Песочница как в test_step_cost.py: БД и артефакты во временном каталоге,
`claude` и git не запускаются (эти команды сюда не заходят).
"""
import io
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import budget, catalog, config, fsm, store  # noqa: E402

# Заготовка валидна по guard: с T017 он вызывается на переходе
# spec_writing -> spec_gate, и SPEC без обязательных секций до применения
# потолка не доходит.
SPEC_MD = """---
task: {task}
type: spec
author_role: analyst
status: {status}
schema_version: 1
{extra}---

# SPEC: бюджет из SPEC

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""

# Схема tasks до T012 — на ней проверяется миграция существующих БД.
LEGACY_SCHEMA = """
CREATE TABLE tasks (
  id TEXT PRIMARY KEY, title TEXT, state TEXT, branch TEXT,
  review_iters INTEGER DEFAULT 0, accept_rejects INTEGER DEFAULT 0,
  reviewed_iter INTEGER DEFAULT 0, escalated_from TEXT,
  budget_usd REAL, spent_usd REAL DEFAULT 0,
  created_at TEXT, updated_at TEXT
);
CREATE TABLE steps (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, ts TEXT,
  actor TEXT, action TEXT, detail TEXT
);
"""


class SpecBudgetParseTest(unittest.TestCase):
    """Разбор поля: сумма, «поля нет» и «поле есть, но не сумма» — разное."""

    def test_number_is_taken(self):
        self.assertEqual(budget.spec_budget({"budget_usd": "25"}), (25.0, ""))

    def test_fractional_and_comma_are_accepted(self):
        for raw, expected in (("12.5", 12.5), ("7,5", 7.5), (" 30 ", 30.0)):
            with self.subTest(raw=raw):
                self.assertEqual(budget.spec_budget({"budget_usd": raw})[0],
                                 expected)

    def test_missing_field_is_silence_not_refusal(self):
        """Требование 2: поля нет — ни значения, ни причины, ни записей."""
        self.assertEqual(budget.spec_budget({"status": "ready"}), (None, ""))

    def test_garbage_is_refused_with_a_reason(self):
        """Требование 3: не число или ≤ 0 — отказ, и он объясним."""
        for raw in ("", "дорого", "0", "-5", "25 долларов", "nan", "inf",
                    "$25", "true"):
            with self.subTest(raw=raw):
                value, refused = budget.spec_budget({"budget_usd": raw})
                self.assertIsNone(value)
                self.assertIn("не сумма в долларах", refused)
                self.assertIn(raw.strip(), refused, "видно, что именно отвергли")

    def test_quoted_number_is_still_a_number(self):
        """YAML-кавычки вокруг суммы — форма записи, а не повод для отказа."""
        for raw in ('"25"', "'25'", '" 25 "'):
            with self.subTest(raw=raw):
                self.assertEqual(budget.spec_budget({"budget_usd": raw})[0], 25.0)

    def test_value_above_the_default_is_refused(self):
        """Требование 1: потолок отсюда только понижается (инвариант 10).

        Причина отказа обязана отличаться от «не сумма в долларах»: число
        корректно, нельзя именно поднятие, и Оператор должен видеть разницу.
        """
        for raw in (f"{config.DEFAULT_BUDGET_USD + 1:g}",
                    f"{config.DEFAULT_BUDGET_USD * 10:g}"):
            with self.subTest(raw=raw):
                value, refused = budget.spec_budget({"budget_usd": raw})
                self.assertIsNone(value)
                self.assertIn("выше дефолта", refused)
                self.assertIn("budget", refused, "сказано, чем поднимают потолок")
                self.assertNotIn("не сумма", refused)

    def test_value_equal_to_the_default_is_taken(self):
        """Граница строгая: SPEC говорит «не выше», сам дефолт ещё можно."""
        self.assertEqual(
            budget.spec_budget({"budget_usd": f"{config.DEFAULT_BUDGET_USD:g}"}),
            (config.DEFAULT_BUDGET_USD, ""))


class SpecBudgetOnTheGateTest(unittest.TestCase):
    """`advance` из spec_writing: потолок задачи берётся из SPEC."""

    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Бюджет задачи из SPEC")
        self.tdir = config.TASKS / self.TASK

    # ------------------------------------------------------------ утилиты

    def capture(self, fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def write_spec(self, status: str = "ready", **fields) -> None:
        extra = "".join(f"{k}: {v}\n" for k, v in fields.items())
        (self.tdir / "SPEC.md").write_text(
            SPEC_MD.format(task=self.TASK, status=status, extra=extra),
            encoding="utf-8")

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def reset_task(self) -> None:
        """Задача и её журнал как сразу после `new` — для свипов по значениям."""
        conn = store.db()
        conn.execute("UPDATE tasks SET state='spec_writing', budget_usd=?, "
                     "budget_source=NULL WHERE id=?",
                     (config.DEFAULT_BUDGET_USD, self.TASK))
        conn.execute("DELETE FROM steps WHERE task_id=?", (self.TASK,))
        conn.commit()

    def journal(self, action: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]

    def budget_records(self) -> list[str]:
        """Все записи журнала про бюджет — по ним видно и молчание."""
        return [f"{r['action']} | {r['detail']}" for r in store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? "
            "AND (action LIKE 'бюджет%' OR detail LIKE '%бюджет%') ORDER BY id",
            (self.TASK,))]

    # ----------------------------------------------------------- сценарии

    def test_spec_value_becomes_the_task_budget(self):
        """Критерий приёмки 1: budget_usd: 25 в SPEC — потолок задачи $25."""
        self.write_spec(budget_usd=25)

        out = self.capture(fsm.cmd_advance, self.TASK)

        row = self.task_row()
        self.assertAlmostEqual(row["budget_usd"], 25.0)
        self.assertEqual(row["state"], "spec_gate", "переход идёт как обычно")
        self.assertEqual(row["budget_source"], config.BUDGET_SOURCE_SPEC)
        self.assertEqual(
            self.journal("бюджет из SPEC"),
            [f"$25.00 (прежний потолок ${config.DEFAULT_BUDGET_USD:.2f}, "
             f"дефолт ${config.DEFAULT_BUDGET_USD:.2f})"])
        self.assertIn("бюджет из SPEC: $25.00", out)

    def test_applied_value_is_the_ceiling_operator_sees(self):
        """Потолок из SPEC — тот самый, по которому считается расход."""
        self.write_spec(budget_usd=25)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertIn("$0.00/25.00", self.capture(catalog.cmd_status))

    def test_comment_after_the_value_is_not_part_of_it(self):
        """Аналитик пишет ориентир в строку поля — это комментарий, не сумма."""
        self.write_spec(budget_usd="15   # мелкий фикс")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertAlmostEqual(self.task_row()["budget_usd"], 15.0)

    def test_spec_without_the_field_keeps_the_default_silently(self):
        """Требование 2: SPEC из шаблона — дефолт и ни одной записи о бюджете.

        SPEC здесь ровно тот, что создала `new` из templates/SPEC.md, —
        значит закомментированная подсказка аналитику (требование 5)
        полем не притворяется.
        """
        spec = self.tdir / "SPEC.md"
        spec.write_text(spec.read_text(encoding="utf-8")
                        .replace("status: draft", "status: ready"),
                        encoding="utf-8")

        self.capture(fsm.cmd_advance, self.TASK)

        row = self.task_row()
        self.assertAlmostEqual(row["budget_usd"], config.DEFAULT_BUDGET_USD)
        self.assertIsNone(row["budget_source"])
        self.assertEqual(self.budget_records(), [])
        self.assertEqual(row["state"], "spec_gate")

    def test_garbage_warns_and_does_not_block_the_task(self):
        """Требование 3: мусор — предупреждение, дефолт и обычный переход."""
        for raw in ("дорого", "0", "-5", "", "25 долларов"):
            with self.subTest(raw=raw):
                self.reset_task()
                self.write_spec(budget_usd=raw)

                out = self.capture(fsm.cmd_advance, self.TASK)

                row = self.task_row()
                self.assertAlmostEqual(row["budget_usd"],
                                       config.DEFAULT_BUDGET_USD)
                self.assertIsNone(row["budget_source"],
                                  "отвергнутое значение источником не стало")
                self.assertEqual(row["state"], "spec_gate",
                                 "задача не заблокирована")
                self.assertIn("ВНИМАНИЕ", out)
                self.assertEqual(
                    len(self.journal("бюджет из SPEC отклонён")), 1)
                self.assertIn(
                    f"остаётся потолок ${config.DEFAULT_BUDGET_USD:.2f}",
                    self.journal("бюджет из SPEC отклонён")[0])

    def test_value_above_the_default_keeps_the_default_and_warns(self):
        """Требование 1: значение выше дефолта потолок не поднимает.

        Инвариант 10 («поднять потолок может только Оператор командой
        budget») не должен обходиться числом, которое пишет агент-аналитик:
        предупреждение, прежний потолок и обычный переход на гейт.
        """
        for usd in (config.DEFAULT_BUDGET_USD + 1,
                    config.DEFAULT_BUDGET_USD * 10):
            with self.subTest(usd=usd):
                self.reset_task()
                self.write_spec(budget_usd=f"{usd:g}")

                out = self.capture(fsm.cmd_advance, self.TASK)

                row = self.task_row()
                self.assertAlmostEqual(row["budget_usd"],
                                       config.DEFAULT_BUDGET_USD,
                                       msg="потолок задачи не поднялся")
                self.assertIsNone(row["budget_source"],
                                  "отвергнутое значение источником не стало")
                self.assertEqual(row["state"], "spec_gate",
                                 "задача не заблокирована")
                self.assertIn("ВНИМАНИЕ", out)
                refusals = self.journal("бюджет из SPEC отклонён")
                self.assertEqual(len(refusals), 1)
                self.assertIn("выше дефолта", refusals[0])
                self.assertIn("budget", refusals[0])
                self.assertEqual(self.journal("бюджет из SPEC"), [],
                                 "записи о применении нет — применять нечего")

    def test_value_equal_to_the_default_is_applied(self):
        """Граница: ровно дефолт — это «не выше», значение применяется.

        Сравнивать надо с DEFAULT_BUDGET_USD, а не с текущим потолком: в
        старых БД он бывает $5–$10 от прежних дефолтов, и сравнение с ним
        отвергло бы разрешённые SPEC суммы (см. LegacyDbMigrationTest).
        """
        self.write_spec(budget_usd=f"{config.DEFAULT_BUDGET_USD:g}")

        self.capture(fsm.cmd_advance, self.TASK)

        row = self.task_row()
        self.assertAlmostEqual(row["budget_usd"], config.DEFAULT_BUDGET_USD)
        self.assertEqual(row["budget_source"], config.BUDGET_SOURCE_SPEC)
        self.assertEqual(row["state"], "spec_gate")

    def test_not_ready_spec_does_not_touch_the_budget(self):
        """Пока SPEC не ready, перехода нет — и бюджет не меняется."""
        self.write_spec(status="draft", budget_usd=25)

        self.capture(fsm.cmd_advance, self.TASK)

        row = self.task_row()
        self.assertAlmostEqual(row["budget_usd"], config.DEFAULT_BUDGET_USD)
        self.assertEqual(row["state"], "spec_writing")
        self.assertEqual(self.budget_records(), [])

    def test_repeated_advance_does_not_apply_the_value_twice(self):
        """Требование 4: повторный проход бюджет не переприменяет."""
        self.write_spec(budget_usd=25)
        self.capture(fsm.cmd_advance, self.TASK)
        self.capture(budget.cmd_budget, self.TASK, "60")

        self.set_state("spec_writing")
        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertAlmostEqual(self.task_row()["budget_usd"], 60.0,
                               "поднятие Оператора уцелело")
        self.assertIn("не применён", out)
        self.assertEqual(self.task_row()["state"], "spec_gate")

    def test_operator_ceiling_set_before_the_gate_wins(self):
        """Требование 4: ручное поднятие сильнее и когда сделано раньше."""
        self.capture(budget.cmd_budget, self.TASK, "100")
        self.write_spec(budget_usd=25)

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertAlmostEqual(self.task_row()["budget_usd"], 100.0)
        self.assertEqual(self.task_row()["budget_source"],
                         config.BUDGET_SOURCE_OPERATOR)
        self.assertIn("потолок задан Оператором", out)
        self.assertEqual(self.journal("бюджет из SPEC не применён"),
                         ["$25.00 — потолок задан Оператором, остаётся $100.00"])
        self.assertEqual(self.journal("бюджет из SPEC"), [],
                         "потолок не менялся — действие в журнале другое")

    def test_operator_ceiling_after_the_gate_still_works(self):
        """Критерий приёмки 3: `budget` после применения работает как раньше."""
        self.write_spec(budget_usd=25)
        self.capture(fsm.cmd_advance, self.TASK)

        self.capture(budget.cmd_budget, self.TASK, "70")

        self.assertAlmostEqual(self.task_row()["budget_usd"], 70.0)
        self.assertIn("$25.00 -> $70.00",
                      self.journal("бюджет изменён")[0])

    def test_second_pass_over_the_same_spec_says_it_is_already_applied(self):
        """Без вмешательства Оператора повтор тоже ничего не переписывает."""
        self.write_spec(budget_usd=25)
        self.capture(fsm.cmd_advance, self.TASK)

        self.set_state("spec_writing")
        self.capture(fsm.cmd_advance, self.TASK)

        self.assertAlmostEqual(self.task_row()["budget_usd"], 25.0)
        self.assertEqual(self.journal("бюджет из SPEC не применён"),
                         ["$25.00 — уже применён, остаётся $25.00"])


class LegacyDbMigrationTest(SpecBudgetOnTheGateTest):
    """БД, созданная до T012: колонки источника нет, задача уже заведена.

    Наследует все сценарии базового класса намеренно: миграция обязана
    дать старой БД ровно то же поведение, что и новой, — иначе половина
    требований проверена только на свежесозданной схеме.
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        config.DB.parent.mkdir(parents=True, exist_ok=True)
        legacy = sqlite3.connect(config.DB)
        legacy.executescript(LEGACY_SCHEMA)
        legacy.execute(
            "INSERT INTO tasks (id,title,state,branch,budget_usd,"
            "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            (self.TASK, "Бюджет задачи из SPEC", "spec_writing",
             f"task/{self.TASK.lower()}-byudzhet", config.DEFAULT_BUDGET_USD,
             store.now(), store.now()))
        legacy.commit()
        legacy.close()

        self.tdir = config.TASKS / self.TASK
        self.tdir.mkdir(parents=True)
        # Базовый класс в одном тесте читает SPEC, созданный `new` из
        # шаблона; здесь задача заведена в обход команды — кладём тот же файл.
        (self.tdir / "SPEC.md").write_text(
            (Path(__file__).resolve().parent.parent / "templates" / "SPEC.md")
            .read_text(encoding="utf-8").replace("TASK_ID", self.TASK),
            encoding="utf-8")

    def test_migration_adds_the_source_column(self):
        self.assertIn("budget_source",
                      {r["name"] for r in store.db().execute(
                          "PRAGMA table_info(tasks)")})
        self.assertIsNone(self.task_row()["budget_source"],
                          "у существующей задачи источник не задан — дефолт")


if __name__ == "__main__":
    unittest.main()
