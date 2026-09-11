"""Приёмочные тесты 01M1SHJZCE0Y4DXAAWQ2W585A7 — AC-11 (SPEC с корректной
секцией «## Деление» из 2 подразделов: `approve` на `spec_gate` заводит
РОВНО 2 подзадачи, у КАЖДОЙ `TZ.md` несёт первую строку-ссылку на
родителя; журнал родителя содержит запись «поделена на: ...» с ОБОИМИ id).

Отличие от соседних AC-5 (механика ОДНОЙ подзадачи по имени) и AC-6 (сам
факт перехода в killed + факт фразы «поделена на» без привязки к
конкретным id) — этот тест держит МНОЖЕСТВЕННОСТЬ целиком: число
подзадач ровно 2 (не 1, не 3 — например если код по ошибке останавливается
после первого подраздела или дублирует последний), у ОБЕИХ (не только
первой) есть ссылка на родителя, и запись журнала называет ОБА id
одновременно, а не только последний записанный.

Красен до реализации: см. докстринг `test_ac5_approve_spawns_subtask.py`
— до появления ветки деления ни одна подзадача не заводится, все
assertion ниже (число подзадач, ссылки, id в журнале) покраснеют.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (FIRST_SUBTASK_TITLE, FIXTURE_ZONE,  # noqa: E402
                      SECOND_SUBTASK_TITLE, SplitApproveSandbox, spec_text,
                      two_valid_subsections)
from orchestrator import artifact_branch  # noqa: E402


class TwoSubtasksEndToEndTest(SplitApproveSandbox):
    """Ловит мутацию: цикл заведения подзадач по подразделам собран так,
    что заводит только ОДНУ (например берёт только первый элемент списка
    подразделов, либо перезаписывает переменную-аккумулятор вместо
    накопления), либо журнал родителя пишет только id ПОСЛЕДНЕЙ заведённой
    подзадачи вместо перечня всех.
    """

    def test_ac11_two_subsections_yield_two_linked_subtasks_and_a_joint_journal_entry(self):
        text = spec_text(zones=FIXTURE_ZONE, subsections=two_valid_subsections())
        sha = self.enter_spec_gate(text)

        self.approve(sha)

        new_ids = self.all_task_ids() - {self.TASK}
        self.assertEqual(
            len(new_ids), 2,
            f"SPEC с 2 подразделами секции «## Деление» завёл не ровно 2 "
            f"подзадачи (AC-11): {new_ids}")

        titles = self.titles_by_id(new_ids)
        self.assertEqual(
            set(titles.values()), {FIRST_SUBTASK_TITLE, SECOND_SUBTASK_TITLE},
            f"названия заведённых подзадач не совпадают с заголовками "
            f"обоих подразделов (AC-11): {titles}")

        link_line = f"Родительская задача: {self.TASK} — {self.TITLE}"
        for sub_id in new_ids:
            files = artifact_branch.read_tree(sub_id)
            tz = files.get(f"tasks/{sub_id}/TZ.md", "")
            self.assertIn(
                link_line, tz,
                f"TZ.md подзадачи {sub_id} не несёт строку-ссылку на "
                f"родителя (AC-11): {tz!r}")

        journal = self.journal_text()
        for sub_id in new_ids:
            self.assertIn(
                sub_id, journal,
                f"журнал родителя не называет id подзадачи {sub_id} в "
                f"записи «поделена на» (AC-11): {journal!r}")


if __name__ == "__main__":
    unittest.main()
