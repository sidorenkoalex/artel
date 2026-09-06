"""Тесты бюджета задачи из frontmatter SPEC (см. tasks/T012/SPEC.md).

Проверяется вся дорога числа: разбор поля `budget_usd`, применение ровно
на переходе spec_writing -> spec_gate, тишина при отсутствии поля,
предупреждение при мусоре, отказ от значения выше потолка ролей
(`ROLE_BUDGET_CAP`, в его пределах потолок применяется и выше, и ниже
дефолта — инвариант 10) и приоритет ручного поднятия `budget` над
значением из SPEC — в обоих порядках.

Песочница как в test_step_cost.py: БД и артефакты во временном каталоге,
`claude` и git не запускаются (эти команды сюда не заходят).
"""
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import budget, catalog, config, fsm, gitcmd, store  # noqa: E402
from tests.sandbox import (SpyRun, TmpRootTest, capture,  # noqa: E402
                           capture_new_task_id, disk_backed_ls_tree_files,
                           disk_backed_show, fake_git, sync_spec_from_worktree)

REPO_ROOT = Path(__file__).resolve().parent.parent

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

    def test_value_above_the_role_cap_is_refused(self):
        """Требование 1 (ADR-0014): потолок ролей — верхняя граница, не
        дефолт; выше него потолок отсюда не поднимается (инвариант 10).

        Причина отказа обязана отличаться от «не сумма в долларах»: число
        корректно, нельзя именно поднятие выше потолка ролей, и Оператор
        должен видеть разницу.

        Ловит мутацию: сравнение с потолком ролей заменено сравнением с
        `DEFAULT_BUDGET_USD` (старая семантика) или снято вовсе — значение
        выше `ROLE_BUDGET_CAP` было бы принято как валидное число.
        """
        for raw in (f"{config.ROLE_BUDGET_CAP + 1:g}",
                    f"{config.ROLE_BUDGET_CAP * 10:g}"):
            with self.subTest(raw=raw):
                value, refused = budget.spec_budget({"budget_usd": raw})
                self.assertIsNone(value)
                self.assertIn("выше потолка ролей", refused)
                self.assertIn("budget", refused, "сказано, чем поднимают потолок")
                self.assertNotIn("не сумма", refused)

    def test_value_above_the_default_but_within_the_role_cap_is_taken(self):
        """Требование 4 (ADR-0014): в пределах потолка ролей значение
        применяется и когда оно выше дефолта, не только ниже.

        Ловит мутацию: `spec_budget` по-прежнему сравнивает с
        `DEFAULT_BUDGET_USD` (старая семантика «только вниз от дефолта») —
        значение между дефолтом и потолком ролей отвергалось бы, а не
        принималось."""
        value = (config.DEFAULT_BUDGET_USD + config.ROLE_BUDGET_CAP) / 2
        self.assertGreater(value, config.DEFAULT_BUDGET_USD,
                           "фикстура: значение обязано быть выше дефолта")

        self.assertEqual(budget.spec_budget({"budget_usd": f"{value:g}"}),
                         (value, ""))

    def test_value_equal_to_the_default_is_taken(self):
        """Граница дефолта больше не отказная — потолок ролей выше него.

        Ловит мутацию: старая граница `> DEFAULT_BUDGET_USD` осталась на
        месте (не заменена на `> ROLE_BUDGET_CAP`) — значение ровно в
        дефолт отвергалось бы вместо принятия."""
        self.assertEqual(
            budget.spec_budget({"budget_usd": f"{config.DEFAULT_BUDGET_USD:g}"}),
            (config.DEFAULT_BUDGET_USD, ""))

    def test_value_equal_to_the_role_cap_is_taken(self):
        """Граница строгая: SPEC говорит «не выше», сам потолок ролей ещё
        можно (AC-4: «выше», а не «начиная с»).

        Ловит мутацию: сравнение `> ROLE_BUDGET_CAP` подменено на `>=` —
        значение ровно в потолок ролей отвергалось бы вместо принятия."""
        self.assertEqual(
            budget.spec_budget({"budget_usd": f"{config.ROLE_BUDGET_CAP:g}"}),
            (config.ROLE_BUDGET_CAP, ""))


class SpecBudgetOnTheGateTest(unittest.TestCase):
    """`advance` из spec_writing: потолок задачи берётся из SPEC."""

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
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude"),
                            ("BACKUP_MARKER", root / ".artel" / "backup-marker"),
                            ("WORKTREES", root / ".artel" / "worktrees")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        # ДО `cmd_new` (SPEC T048) — сам заводит артефактную ветку пульта
        # через `gitcmd`, без фейка ушёл бы в реальный репозиторий пульта.
        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        # A7 (generic-путь заведения, AC-5): `cmd_new` коммитит артефакты
        # плотницки (`artifact_branch.write_commit`) — та функция зовёт
        # `subprocess.run` НАПРЯМУЮ, минуя `gitcmd.git`/фейк выше; `root`
        # здесь не настоящий git-репозиторий (только скопированные
        # `templates/`) — без этого патча `cmd_new` падает `sys.exit`
        # («git не ответил») ещё до сценария, который тест проверяет
        # (тот же приём, что `tests.sandbox.TmpRootTest.setUp`).
        spy_patcher = mock.patch.object(gitcmd.subprocess, "run", SpyRun())
        spy_patcher.start()
        self.addCleanup(spy_patcher.stop)
        # A7: `artifact_source.resolve` теперь ВСЕГДА возвращает
        # `foreign=True` (артефактная ветка пульта, даже для self/артель)
        # — `fsm._cmd_advance` читает SPEC.md через `gitcmd.show`/
        # `ls_tree_files`, не с диска напрямую; эта песочница без
        # настоящего git ведёт один источник истины — диск `self.tdir`
        # (тот же приём, что `tests.test_invariants.FsmTest`).
        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)

        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "Бюджет задачи из SPEC")
        # `write_spec` кладёт SPEC.md на диск (`config.TASKS/<id>/`, читает
        # `disk_backed_show` выше) — `cmd_new` (A7, generic-путь, AC-5)
        # коммитит его в АРТЕФАКТНУЮ ВЕТКУ пульта плотницки, не сюда;
        # `sync_spec_from_worktree` кладёт тот же нетронутый шаблон
        # (`templates/SPEC.md`), который реально закоммитил бы `cmd_new`
        # (тест проверяет закомментированную подсказку в нём).
        self.tdir = config.TASKS / self.TASK
        sync_spec_from_worktree(self.TASK)

    # ------------------------------------------------------------ утилиты

    capture = staticmethod(capture)

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
        # schema_version 4 (шаблон с этой задачи) требует поле `zones:`
        # (01M1NKVPD2A79PQ6K0JVV1B2Q1, AC-1) — заполняем закомментированную
        # подсказку шаблона, как сделал бы analyst; сам тест — про бюджет,
        # не про зоны.
        spec = self.tdir / "SPEC.md"
        spec.write_text(spec.read_text(encoding="utf-8")
                        .replace("status: draft", "status: ready")
                        .replace("# zones: orchestrator/store.py, "
                                 "orchestrator/config.py",
                                 "zones: orchestrator/store.py, "
                                 "orchestrator/config.py"),
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

    def test_value_above_the_role_cap_blocks_the_transition(self):
        """Требование 3 (ADR-0014): значение выше потолка ролей — отказ
        guard (не тихое усечение), независимо от schema_version SPEC.

        Guard теперь ловит завышенное значение РАНЬШЕ, чем переход вообще
        дойдёт до `apply_spec_budget` (AC-8, сценарий 1) — задача остаётся
        в spec_writing, а не переходит на гейт с тихо применённым дефолтом,
        как было бы при старой семантике «выше дефолта — предупреждение и
        обычный переход».

        Ловит мутацию: `role_budget_cap_errors` не подключена в
        `_content_errors` (или подключена только для `type: spec` версии
        >= 5) — переход на завышенном значении прошёл бы до гейта.
        """
        for usd in (config.ROLE_BUDGET_CAP + 1,
                    config.ROLE_BUDGET_CAP * 10):
            with self.subTest(usd=usd):
                self.reset_task()
                self.write_spec(budget_usd=f"{usd:g}")

                self.capture(fsm.cmd_advance, self.TASK)

                row = self.task_row()
                self.assertEqual(row["state"], "spec_writing",
                                 "guard обязан заблокировать переход")
                self.assertAlmostEqual(row["budget_usd"],
                                       config.DEFAULT_BUDGET_USD)
                self.assertIsNone(row["budget_source"])
                self.assertEqual(
                    len(self.journal("переход отклонён guard'ом")), 1)
                self.assertEqual(self.journal("бюджет из SPEC"), [])
                self.assertEqual(self.journal("бюджет из SPEC отклонён"), [],
                                 "guard блокирует переход раньше "
                                 "apply_spec_budget — до него не дошло")

    def test_value_above_the_default_but_within_the_role_cap_becomes_the_ceiling(self):
        """Требование 4 (ADR-0014): значение выше дефолта, но в пределах
        потолка ролей, применяется на гейте как обычно — потолок отсюда
        уже не только понижается.

        Ловит мутацию: `apply_spec_budget` по-прежнему сравнивает верхнюю
        границу с `DEFAULT_BUDGET_USD` — значение между дефолтом и
        потолком ролей на полном пути через `cmd_advance` было бы
        отклонено guard'ом вместо того, чтобы стать потолком задачи."""
        value = (config.DEFAULT_BUDGET_USD + config.ROLE_BUDGET_CAP) / 2
        self.write_spec(budget_usd=f"{value:g}")

        self.capture(fsm.cmd_advance, self.TASK)

        row = self.task_row()
        self.assertAlmostEqual(row["budget_usd"], value)
        self.assertEqual(row["budget_source"], config.BUDGET_SOURCE_SPEC)
        self.assertEqual(row["state"], "spec_gate")

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

    # Заведена напрямую записью в БД (легаси-путь ниже), не через `cmd_new`
    # — значит фиксированный id (не ULID) тут корректен (SPEC T094, AC-5:
    # старые Tnnn обязаны продолжать работать).
    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)

        # Тот же набор путей и `gitcmd.git`, что несёт `SpecBudgetOnThe
        # GateTest.setUp` (AC-2, tasks/T083/SPEC.md): без ROOT/WORKTREES
        # унаследованные тестовые методы зовут `fsm.cmd_advance`, который
        # безусловно читает `gitcmd.on_foreign_branch(branch)` — с
        # непропатченным `gitcmd.git` это настоящий `subprocess.run(["git",
        # ...], cwd=config.ROOT)`, а непропатченный `config.ROOT` — реальный
        # корень пульта (рабочая копия, откуда запущен тест), не эта
        # песочница.
        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            ("ROOT", root),
                            ("PROJECTS", root / ".artel" / "projects"),
                            ("TARGETS", root / "targets.yaml"),
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude"),
                            ("BACKUP_MARKER", root / ".artel" / "backup-marker"),
                            ("WORKTREES", root / ".artel" / "worktrees")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        # A7: та же подмена чтения ветки на диск, что и в базовом классе
        # (см. его докстринг) — `fsm._cmd_advance` читает SPEC.md через
        # `gitcmd.show`/`ls_tree_files` для ЛЮБОГО target теперь.
        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)

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


class SpentWithEstimateGateTest(TmpRootTest):
    """`budget.spent_with_estimate`/`budget_block`/`enforce_budget` считают
    потолок по `spent_usd + spent_estimate_usd` (SPEC
    01M1NWCM3TDY0YABEKE8DYQA1C, требование 5) — юнит-угол на функцию
    суммы и на вырожденные случаи, дополняющий приёмочные
    `tasks/01M1NWCM3TDY0YABEKE8DYQA1C/acceptance_tests/test_ac5_*`."""

    TASK = "T900"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Задача", "in_dev",
                          "task/t900-x", config.DEFAULT_TARGET, 50.0)

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def set_task(self, **fields) -> None:
        assignments = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(f"UPDATE tasks SET {assignments} WHERE id=?",
                          (*fields.values(), self.TASK))
        self.conn.commit()

    def test_spent_with_estimate_adds_both_columns(self):
        """Ловит мутацию: `spent_with_estimate` возвращает только
        `spent_usd` (забывает прибавить `spent_estimate_usd`) — тогда
        результат будет 3.0 вместо 7.0."""
        self.set_task(spent_usd=3.0, spent_estimate_usd=4.0)

        self.assertEqual(budget.spent_with_estimate(self.task_row()), 7.0)

    def test_spent_with_estimate_treats_null_estimate_as_zero(self):
        """Строки старше этой задачи (или свежие с NULL из ручного UPDATE)
        не должны ронять сумму — тот же приём деградации, что и у
        `spent_usd or 0.0` рядом.

        Ловит мутацию: `spent_with_estimate` складывает
        `t["spent_estimate_usd"]` без `or 0.0` — тогда на строке с
        NULL сложение `3.0 + None` бросит `TypeError` вместо того,
        чтобы вернуть 3.0."""
        self.set_task(spent_usd=3.0, spent_estimate_usd=None)

        self.assertEqual(budget.spent_with_estimate(self.task_row()), 3.0)

    def test_budget_block_ignores_the_estimate_when_there_is_no_ceiling(self):
        """Потолок <= 0 — потолка нет вовсе, независимо от того, сколько
        стоит верхняя оценка (тот же вырожденный случай, что уже был у
        одного только `spent_usd` до этой задачи).

        Ловит мутацию: `budget_block` проверяет исчерпание раньше
        вырожденного случая `budget <= 0` (или проверяет его по
        одному `spent_usd`, без учёта того, что `spent_with_estimate`
        уже >= 0) — тогда при `budget_usd=0.0` и
        `spent_estimate_usd=999.0` функция всё равно вернёт сообщение
        о блокировке вместо `None`."""
        self.set_task(budget_usd=0.0, spent_usd=0.0, spent_estimate_usd=999.0)

        self.assertIsNone(budget.budget_block(self.task_row()))

    def test_enforce_budget_does_not_escalate_below_the_combined_ceiling(self):
        """Ловит мутацию: `enforce_budget` завышает сумму — например,
        прибавляет `spent_estimate_usd` ещё раз поверх
        `spent_with_estimate`, или сравнивает с потолком `spent_usd`
        и `spent_estimate_usd` по отдельности через `or` — тогда
        `3.0 + 4.0` ложно дотянется/превысит потолок $10.00, задача
        уйдёт в `escalated`, и оба `assert` ниже упадут."""
        self.set_task(budget_usd=10.0, spent_usd=3.0, spent_estimate_usd=4.0)

        escalated = budget.enforce_budget(self.conn, self.TASK, "in_dev")

        self.assertFalse(escalated)
        self.assertEqual(self.task_row()["state"], "in_dev")


if __name__ == "__main__":
    unittest.main()
