"""Приёмочные тесты 01M1SHJZCE0Y4DXAAWQ2W585A7 — AC-6 (родительская задача
при успешном заведении подзадач переходит в состояние `killed` с записью
в журнал «поделена на: <id1>, <id2>, ...»).

Точный перечень id — предмет соседнего `test_ac11_two_subtasks_end_to_end.py`
(AC-11); этот тест проверяет ДВА свойства AC-6 общего порядка: сам факт
перехода в `killed` и сам факт записи фразы «поделена на» в журнал
родителя, независимо от того, сколько подзадач и какими id они пришли.

Красен до реализации: `orchestrator/fsm.py::_cmd_approve` на `spec_gate`
никогда не переводит задачу в `killed` (единственные ветки перехода —
`in_dev`/`tests_writing`, `orchestrator/fsm.py:818-826`) — оба assertion
ниже (`state == "killed"`, «поделена на» в журнале) покраснеют, пока
разработчик не добавит ветку деления.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (FIXTURE_ZONE, SplitApproveSandbox,  # noqa: E402
                      spec_text, two_valid_subsections)


class ParentKilledWithJournalEntryTest(SplitApproveSandbox):
    """`approve`, заведший подзадачи, переводит родителя в `killed` и
    пишет в его журнал фразу «поделена на».

    Ловит мутацию: код заводит подзадачи, но оставляет родителя в
    `spec_gate` (забытый вызов перехода состояния), либо переводит в
    `killed` без записи журнала (детали `store.set_state` не переданы,
    например `detail=""`).
    """

    def test_ac6_parent_transitions_to_killed_and_journal_names_the_split(self):
        text = spec_text(zones=FIXTURE_ZONE, subsections=two_valid_subsections())
        sha = self.enter_spec_gate(text)

        self.approve(sha)

        row = self.task_row()
        self.assertEqual(
            row["state"], "killed",
            f"после approve, заведшего подзадачи, родитель не в "
            f"состоянии killed (AC-6): строка {row}")
        journal = self.journal_text()
        self.assertIn(
            "поделена на", journal,
            f"журнал родителя не несёт записи «поделена на» (AC-6): "
            f"{journal!r}")


if __name__ == "__main__":
    unittest.main()
