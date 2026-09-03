"""AC-7 (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md): «Журнальное событие
успешной правки помечено как «правка планки» — отличимо от прочих
событий журнала.»

Красен до реализации: `_sandbox.discover_amend_command_name()` падает
`AssertionError` — новой команды правки планки в таблице диспетчера ещё
нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AC_TEST_AMENDED_V1, AmendSandbox  # noqa: E402

MARKER = "правка планки"


class JournalMarkerTest(AmendSandbox):

    def test_ac7_journal_action_carries_amend_marker_distinct_from_other_events(self):
        """После успешной правки журнал задачи несёт ровно ОДНУ запись
        с меткой «правка планки» в action — и эта метка не встречается
        ни в одной из ДРУГИХ записей журнала той же задачи (переходы
        FSM, фиксации sha и т.п.), то есть событие правки планки отличимо
        от остального журнала по своему action, а не только по content.

        Ловит мутацию: команда журналирует правку под уже существующим
        общим action'ом (например «sha зафиксирован» — тем же, что пишет
        `fixation.record_fixation` на каждом переходе FSM) — тогда
        отличить событие правки планки от рутинной фиксации sha по одному
        только action невозможно.
        """
        self.enter_in_dev()
        self.write_acceptance_tests(AC_TEST_AMENDED_V1)

        self.run_amend(reason="исправлена опечатка теста")

        steps = self.conn.execute(
            "SELECT actor, action FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,)).fetchall()
        marked = [r for r in steps if MARKER in r["action"]]
        unrelated = [r for r in steps if MARKER not in r["action"]]

        self.assertEqual(
            len(marked), 1,
            f"ожидалась ровно одна запись с меткой «{MARKER}» в action, "
            f"получено: {[dict(r) for r in marked]}")
        self.assertEqual(
            marked[0]["actor"], "operator",
            "запись с меткой «правка планки» обязана иметь actor=operator")
        self.assertTrue(
            unrelated,
            "фикстура не создала ни одного «прочего» события журнала — "
            "тест не может показать отличимость")
        self.assertFalse(
            any(MARKER in r["action"] for r in unrelated),
            "метка «правка планки» просочилась в action события другого "
            "рода — события неотличимы")


if __name__ == "__main__":
    unittest.main()
