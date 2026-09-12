"""AC-4 (tasks/01M29284PTCJXGERV5262E9XMM/SPEC.md): `retro.build_killed`
для обычной снятой задачи БЕЗ подзадач не меняется по сравнению с
текущим поведением — включая раздел последней эскалации.

Зелёный с рождения: задача без единой строки `parent_task_id = <id>` в
`tasks` не задевает новую ветку кода требования 3 вовсе (условие «есть
подзадачи» ложно для неё независимо от того, реализовано требование 3
или нет) — `build_killed` идёт прежним путём уже сегодня. Тест фиксирует
это как регрессионный барьер: расширение условия «есть подзадачи» не
должно случайно захватить задачу без единой связанной строки.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, retro, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

TASK_ID = "AC4LONE"
ESCALATION_DETAIL = "причина эскалации обычной снятой задачи AC-4"


class RetroBuildKilledWithoutSubtasksUnchangedTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, TASK_ID, "Обычная снятая задача",
                          "killed", "task/ac4lone-x", config.DEFAULT_TARGET,
                          25.0)
        store.journal(self.conn, TASK_ID, "fsm", "state -> escalated",
                      ESCALATION_DETAIL)
        store.journal(self.conn, TASK_ID, "operator", "state -> killed",
                      "kill switch AC-4")

    def test_ac4_ordinary_killed_task_still_quotes_the_last_escalation(self):
        """Задача без подзадач — RETRO строится ровно как раньше: раздел
        последней эскалации присутствует и цитирует её текст целиком, а
        итог остаётся «killed — причина: ...».

        Ловит мутацию: условие «есть подзадачи» ошибочно срабатывает и
        для задачи без единой связанной строки (например, сравнение
        `parent_task_id IS NOT NULL` у самой строки вместо поиска
        ЧУЖИХ строк, ссылающихся на неё) — тогда эскалация и «killed —
        причина» пропадут там, где требование 3 их убирать не просит.
        """
        text = retro.build_killed(self.conn, TASK_ID)

        self.assertIn("Эскалации:", text)
        self.assertIn(ESCALATION_DETAIL, text)
        self.assertIn("Итог: killed — причина: kill switch AC-4", text)


if __name__ == "__main__":
    unittest.main()
