"""Шаг пересборки справочника ядра после мержа
(`fsm_merge_gate._rebuild_core_reference`, SPEC 01M4S24EBVB72B8WYJ3JY96Y0E,
требование 9): исход шага в журнале задачи и алерт его сбоя.

Песочница — `tests.sandbox.LightTransitionSandbox`; ответ К-3а — подмена
`reference_cache.get_reference`.
"""
import unittest
from unittest import mock

from orchestrator import alerts, fsm_merge_gate, reference_cache, store
from tests.sandbox import LightTransitionSandbox

SHA = "a" * 40


class RebuildStepTest(LightTransitionSandbox):

    def setUp(self):
        super().setUp()
        self.conn = store.db()

    def rebuild(self, **patch) -> list:
        with mock.patch.object(reference_cache, "get_reference", **patch):
            fsm_merge_gate._rebuild_core_reference(self.conn, self.TASK, SHA)
        return [(r["action"], r["detail"] or "")
                for r in store.task_steps(self.conn, self.TASK)]

    def test_outcome_is_journaled_with_state_sha_and_note(self):
        """Ответ `fresh` с пометкой — запись «справочник ядра после мержа»
        несёт состояние, sha источника и пометку.

        Ловит мутацию: шаг не пишет исход в журнал или теряет пометку К-3а
        (например, «кэш не записан») — записи или её части не будет.
        """
        answer = reference_cache.Reference("# справочник\n", "кэш не записан", "fresh")
        rows = self.rebuild(return_value=answer)
        mine = [d for a, d in rows if a == fsm_merge_gate.REFERENCE_REBUILD_ACTION]
        self.assertEqual(mine, [f"fresh sha={SHA}; кэш не записан"])

    def test_failure_is_journaled_and_alerted_by_project(self):
        """`get_reference` бросает — запись сбоя с типом исключения и алерт
        `incident` источника пересборки после мержа по проекту задачи.

        Ловит мутацию: обработчик сбоя глушит исключение молча (без записи
        или без алерта) либо поднимает алерт без проекта — Оператор не
        узнает, что справочник на новой голове main не собран.
        """
        rows = self.rebuild(side_effect=KeyError("ключ"))
        failed = [d for a, d in rows
                  if a == fsm_merge_gate.REFERENCE_REBUILD_FAILED_ACTION]
        self.assertEqual(len(failed), 1, rows)
        self.assertIn("KeyError", failed[0])
        target = store.task_target(self.conn, self.TASK)
        opened = [r for r in alerts.open_alerts(self.conn, "incident")
                  if r["source"] == reference_cache.ALERT_SOURCES["merge"]]
        self.assertEqual([r["target"] for r in opened], [target])


if __name__ == "__main__":
    unittest.main()
