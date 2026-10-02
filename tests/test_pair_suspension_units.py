"""Юнит-тесты пробного периода и приостановки пары набора (SPEC
01M3YCHVVEK14SK8GT4R0H7M2C) — свойства, которых не покрывает долгоживущий
файл задачи `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py`:
паритет схемы свежей и догнанной БД, вердикт канареечной задачи и шага не
на паре, однократность приостановки, виновная роль каждой причины,
пустое решение `pair-resume`; по ANSWER-1 — «подряд» по потоку вердиктов
пары, сверка модели шага при отказе автогейта, чтение пар без DDL.
"""
import io
import json
import sqlite3
import sys
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, models, schema, store  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest  # noqa: E402

COMBAT = "combat-model"
SET_MODEL = "set-model"


def columns(conn, table: str) -> list:
    return [(r[1], r[2]) for r in conn.execute(f"PRAGMA table_info({table})")]


class PairTablesSchemaTest(unittest.TestCase):

    def test_migrated_db_gets_pair_tables_like_fresh_schema(self):
        """БД прошлой версии получает таблицы пар тем же составом колонок.

        Сценарий: БД с одной таблицей `tasks` (прошлая версия) проходит
        `migrate`; свежая БД — `create_schema`. Колонки `pair_verdicts` и
        `pair_suspensions` совпадают.

        Ловит мутацию: таблицы пар заведены только в `SCHEMA`, а
        `migrate` их не догоняет (у догнанной БД таблиц нет) либо DDL
        разъехался на два литерала с разными колонками."""
        with closing(sqlite3.connect(":memory:")) as fresh, \
                closing(sqlite3.connect(":memory:")) as old:
            schema.create_schema(fresh)
            old.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, "
                        "state TEXT)")
            old.row_factory = sqlite3.Row
            schema.migrate(old)
            for table in ("pair_verdicts", "pair_suspensions"):
                self.assertTrue(columns(fresh, table), table)
                self.assertEqual(columns(fresh, table), columns(old, table),
                                 table)


class ReviewVerdictTest(TaskSeededTmpRootTest):
    """Задачи на наборе {developer: SET_MODEL}; боевая модель подменена."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        patcher = mock.patch.object(models, "_combat_model",
                                    lambda role: COMBAT)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.number = 1

    def set_task(self, *, canary: bool = False) -> str:
        self.number += 1
        task_id = f"T{self.number:03d}"
        store.insert_task(self.conn, task_id, "Задача", "in_dev",
                          f"task/{task_id.lower()}", config.DEFAULT_TARGET,
                          25.0)
        store.update_task(self.conn, task_id, model_set="nabor",
                          model_set_members=json.dumps(
                              {"developer": SET_MODEL}),
                          is_canary=int(canary))
        return task_id

    def step(self, task_id: str, model: str) -> None:
        store.journal(self.conn, task_id, "developer", "agent run started",
                      f"попытка 1/3, model={model}, роль developer")

    def review_return(self, task_id: str) -> None:
        store.update_task(self.conn, task_id, state="review")
        with redirect_stdout(io.StringIO()):
            store.set_state(self.conn, task_id, "in_dev", "fsm",
                            expected_state="review")

    def review_approve(self, task_id: str) -> None:
        store.update_task(self.conn, task_id, state="review")
        with redirect_stdout(io.StringIO()):
            store.set_state(self.conn, task_id, "acceptance", "fsm",
                            expected_state="review")

    def suspended(self) -> bool:
        return store.active_pair_suspension(
            self.conn, "developer", SET_MODEL) is not None

    def test_canary_task_returns_do_not_count(self):
        """Возвраты ревью канареечной задачи пару не трогают.

        Сценарий: канареечная задача на наборе — шаг developer на модели
        набора и два возврата ревью. Вердиктов пары нет, пара не
        приостановлена; тот же сценарий настоящей задачей — приостановлена.

        Ловит мутацию: вердикт пишется паре без сверки `is_canary` —
        канарейка приостанавливает пару настоящих задач."""
        canary = self.set_task(canary=True)
        self.step(canary, SET_MODEL)
        self.review_return(canary)
        self.review_return(canary)
        self.assertEqual(store.pair_verdicts_after(
            self.conn, "developer", SET_MODEL, 0), [])
        self.assertFalse(self.suspended())

        real = self.set_task()
        self.step(real, SET_MODEL)
        self.review_return(real)
        self.review_return(real)
        self.assertTrue(self.suspended())

    def test_return_after_step_on_other_model_is_not_the_pairs(self):
        """Возврат после шага developer не на модели набора паре не засчитан.

        Сценарий: настоящая задача на наборе; последний шаг developer шёл
        на боевой модели (например, после отката); два возврата ревью.
        Пара не приостановлена, вердиктов пары нет.

        Ловит мутацию: «шёл на паре» не сверяется с моделью последнего
        шага — возврат работы на боевой модели приостанавливает пару
        набора."""
        task = self.set_task()
        self.step(task, SET_MODEL)
        self.step(task, COMBAT)
        self.review_return(task)
        self.review_return(task)
        self.assertEqual(store.pair_verdicts_after(
            self.conn, "developer", SET_MODEL, 0), [])
        self.assertFalse(self.suspended())

    def test_third_return_does_not_add_second_suspension_or_alert(self):
        """Приостановленная пара второй строки и второго алерта не получает.

        Сценарий: три возврата ревью подряд в одной задаче на паре (шаг
        на модели набора перед каждым). Строк приостановки пары — одна,
        алертов `pair_suspension` — один.

        Ловит мутацию: `_suspend_pair` не сверяет действующую
        приостановку — каждый следующий возврат плодит строку БД и
        алерт."""
        task = self.set_task()
        for _ in range(3):
            self.step(task, SET_MODEL)
            self.review_return(task)
        rows = self.conn.execute(
            "SELECT * FROM pair_suspensions WHERE role='developer'").fetchall()
        self.assertEqual(len(rows), 1)
        alerts = [row for row in store.alerts_since(self.conn, 0)
                  if row["source"] == models.PAIR_SUSPENSION_ALERT_SOURCE]
        self.assertEqual(len(alerts), 1)


    def test_return_after_approved_previous_task_does_not_suspend(self):
        """Одобрение предыдущей задачи рвёт цепочку возвратов пары.

        Сценарий (ANSWER-1, п.1): задача P на паре — возврат ревью, затем
        одобрение; задача Q на паре — возврат ревью. Пара не
        приостановлена. Следом второй возврат Q — подряд, пара
        приостановлена.

        Ловит мутацию: возврат одобренной предыдущей задачи засчитан в
        "подряд"."""
        first, second = self.set_task(), self.set_task()
        self.step(first, SET_MODEL)
        self.review_return(first)
        self.step(first, SET_MODEL)
        self.review_approve(first)
        self.step(second, SET_MODEL)
        self.review_return(second)
        self.assertFalse(self.suspended())
        self.step(second, SET_MODEL)
        self.review_return(second)
        self.assertTrue(self.suspended())

    def test_autogate_refusal_after_rollback_to_combat_spares_pair(self):
        """Отказ автогейта по вине developer, шедшего на боевой модели, пару
        не приостанавливает.

        Сценарий (ANSWER-1, п.2): последний шаг developer задачи — на
        боевой модели (откат), отказ «полный набор tests/ красный». Пара
        не приостановлена. Новый шаг developer на модели набора и тот же
        отказ — пара приостановлена.

        Ловит мутацию: вина отказа автогейта ложится на пару без сверки
        модели последнего шага роли — пару приостанавливают за работу
        боевой модели."""
        task = self.set_task()
        reason = (models.AUTOGATE_REFUSAL_PREFIX
                  + "полный набор tests/ красный: 1 failed")
        self.step(task, SET_MODEL)
        self.step(task, COMBAT)
        with redirect_stdout(io.StringIO()):
            models.suspend_on_autogate_refusal(
                self.conn, store.get_task(self.conn, task), reason)
        self.assertFalse(self.suspended())
        self.step(task, SET_MODEL)
        with redirect_stdout(io.StringIO()):
            models.suspend_on_autogate_refusal(
                self.conn, store.get_task(self.conn, task), reason)
        self.assertTrue(self.suspended())

    def test_pair_reads_keep_callers_open_transaction(self):
        """Чтение пар не коммитит открытую транзакцию вызывающего.

        Сценарий (ANSWER-1, п.3): незакоммиченная запись журнала задачи,
        затем `active_pair_suspension`, `pair_verdicts_after`,
        `last_pair_resume_mark`, затем откат транзакции — записи нет.

        Ловит мутацию: запросы к парам исполняют DDL через
        `executescript` (неявный COMMIT) — запись вызывающего
        закоммичена мимо его отката."""
        task = self.set_task()
        self.conn.execute(
            "INSERT INTO steps (task_id, actor, action, detail) "
            "VALUES (?, 'probe', 'probe', 'probe')", (task,))
        store.active_pair_suspension(self.conn, "developer", SET_MODEL)
        store.pair_verdicts_after(self.conn, "developer", SET_MODEL, 0)
        store.last_pair_resume_mark(self.conn, "developer", SET_MODEL)
        self.conn.rollback()
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM steps WHERE actor='probe'").fetchone()[0], 0)


class RefusalRoleTest(unittest.TestCase):

    def test_each_role_blame_reason_names_its_guilty_role(self):
        """Каждая причина «по вине роли» называет виновную роль SPEC.

        Сценарий: тексты отказа автогейта с префиксом для критериев
        `manual`/`skip` (test_author), красного полного набора и
        непройденного `ci` (developer); причина пульта — роли нет.

        Ловит мутацию: `skip` либо `ci` отнесены не к той роли — отказ
        приостановил бы пару роли, которая в нём не виновата."""
        prefix = models.AUTOGATE_REFUSAL_PREFIX
        cases = {
            "критерии manual — AC-1 (источник)": "test_author",
            "критерии skip — AC-2 (источник)": "test_author",
            "полный набор tests/ красный: 1 failed": "developer",
            "критерий ci не пройден — AC-3 (красный)": "developer",
            "бюджет задачи исчерпан": None,
        }
        for text, role in cases.items():
            self.assertEqual(models._refusal_role(prefix + text), role, text)


class PairResumeArgsTest(TaskSeededTmpRootTest):

    def test_blank_decision_refused_without_lifting(self):
        """`pair-resume` с пустым решением — отказ, приостановка остаётся.

        Сценарий: пара приостановлена записью БД; `pair-resume developer
        <модель> "   "`. Выход с текстом об решении, приостановка
        действует, строка не снята.

        Ловит мутацию: решение не обязательно — пара снимается без
        основания в журнале."""
        conn = store.db()
        store.insert_pair_suspension(conn, "developer", SET_MODEL, "nabor",
                                     self.TASK, "второй возврат ревью")
        with self.assertRaises(SystemExit) as caught:
            models.cmd_pair_resume(["developer", SET_MODEL, "   "])
        self.assertIn("решени", str(caught.exception.code))
        self.assertIsNotNone(store.active_pair_suspension(
            store.db(), "developer", SET_MODEL))


if __name__ == "__main__":
    unittest.main()
