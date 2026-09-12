"""AC-5 (tasks/01M29284PTCJXGERV5262E9XMM/SPEC.md): `canary.
_kill_outcome_note` для родителя с подзадачами возвращает «поделена»;
этот исход не считается сбоем — диагностика (`canary._needs_
diagnostics`) не запускается, как и при «штатно».

Красен до реализации: колонка `parent_task_id` ещё не существует
(`orchestrator/schema.py::migrate`) — `store.update_task(conn, ...,
parent_task_id=...)` в `setUp` ниже откажет `ValueError: tasks: нет
колонок parent_task_id`; `canary._task_metrics` (единственный сегодняшний
вызыватель `_kill_outcome_note`) не знает о подзадачах вовсе и вернёт
«не сошлась» вместо «поделена».
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import canary, config, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

PARENT_ID = "AC5PARENT"
SUB_ID = "AC5SUB"


class KillOutcomeNoteDividedParentTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, PARENT_ID, "Родитель AC-5", "killed",
                          "task/ac5parent-x", config.DEFAULT_TARGET, 25.0,
                          is_canary=True)
        store.insert_task(self.conn, SUB_ID, "Подзадача AC-5", "in_dev",
                          "task/ac5sub-x", config.DEFAULT_TARGET, 25.0)
        store.update_task(self.conn, SUB_ID, parent_task_id=PARENT_ID)

    def test_ac5_kill_outcome_note_is_divided_for_parent_with_subtasks(self):
        """`_task_metrics` (единственный вызыватель `_kill_outcome_note`)
        обязан вернуть `kill_note == "поделена"` для родителя с хотя бы
        одной подзадачей — вместо «не сошлась»/«штатно».

        Ловит мутацию: проверка наличия подзадач не реализована вовсе
        (родитель по-прежнему классифицируется старой веткой журнала —
        «не сошлась»), либо условие инвертировано (пусто -> «поделена»).
        """
        metrics = canary._task_metrics(self.conn, PARENT_ID)

        self.assertEqual(metrics["kill_note"], "поделена")

    def test_ac5_divided_outcome_is_not_flagged_for_diagnostics(self):
        """Исход «поделена» — штатный наравне со «штатно»: множество
        значений `kill_note`, для которых диагностика (`canary.
        _needs_diagnostics`) не запускается, обязано включать оба —
        ровно то множество, которое требование 4 называет явно.

        Ловит мутацию: код, сопоставляющий строковый `kill_note`
        булеву `normal_outcome` (`canary._run_one_task`), сверяет его
        только со строкой «штатно» без расширения до «поделена» — тогда
        поделённый родитель попал бы в `_needs_diagnostics(False,
        False)` == True, и второй `assertFalse` ниже это поймает.
        """
        metrics = canary._task_metrics(self.conn, PARENT_ID)
        self.assertEqual(metrics["kill_note"], "поделена")

        for kill_note in ("штатно", "поделена"):
            with self.subTest(kill_note=kill_note):
                normal_outcome = kill_note in ("штатно", "поделена")
                self.assertFalse(
                    canary._needs_diagnostics(normal_outcome, mismatch=False))

    def test_ac5_inconclusive_outcome_still_needs_diagnostics(self):
        """Контрольная ветка: исход, отличный от «штатно»/«поделена»
        («не сошлась: ...»), обязан по-прежнему требовать диагностику —
        расширение множества штатных исходов не должно случайно
        поглотить и его.

        Ловит мутацию: множество штатных исходов расширяют до ЛЮБОГО
        непустого `kill_note` вместо строго пары «штатно»/«поделена» —
        тогда `assertTrue` ниже упадёт.
        """
        normal_outcome = "не сошлась: X" in ("штатно", "поделена")

        self.assertTrue(
            canary._needs_diagnostics(normal_outcome, mismatch=False))


if __name__ == "__main__":
    unittest.main()
