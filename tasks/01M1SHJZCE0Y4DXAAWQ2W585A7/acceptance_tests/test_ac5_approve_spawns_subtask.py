"""Приёмочные тесты 01M1SHJZCE0Y4DXAAWQ2W585A7 — AC-5 (`approve` на
`spec_gate` SPEC с заполненной, без ошибок guard, секцией «## Деление»
заводит по одной подзадаче на каждый подраздел: название — из заголовка
подраздела; `TZ.md` подзадачи — текст ТЗ подраздела с первой строкой
«Родительская задача: <id родителя> — <название родителя>»).

Сценарий: родитель заводится напрямую (`SplitApproveSandbox.
enter_spec_gate`), несёт валидную секцию «## Деление» из 2 подразделов
(`_sandbox.two_valid_subsections`), `approve` подтверждает `spec_gate`
зафиксированным `sha`. Тест проверяет мехнику ОДНОЙ подзадачи (первой) —
множественность (обе подзадачи заведены, обе несут ссылку, журнал родителя
называет оба id) проверяет соседний `test_ac11_two_subtasks_end_to_end.py`.

`artifact_branch.read_tree(sub_id)` читает файлы АРТЕФАКТНОЙ ветки
подзадачи — той же ветки, в которую `catalog.cmd_new`/эквивалентный
внутренний путь коммитит `SPEC.md`/`TZ.md` (SPEC T094, `orchestrator/
catalog.py::_new_external_artifact_branch`).

Красен до реализации: `orchestrator/fsm.py::_cmd_approve` на `spec_gate`
сегодня читает `meta` из SPEC.md, но нигде не смотрит на секцию
«## Деление» и не заводит новых задач (проверено чтением тела ветки
`state == "spec_gate"`, `orchestrator/fsm.py:780-826`, единственный
побочный эффект — `store.update_task(..., zones=...)` и переход в
`tests_writing`/`in_dev`) — `all_task_ids()` после `approve` не меняется
вовсе, assertion на новый id покраснеет, пока разработчик не добавит
заведение подзадач.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (FIRST_SUBTASK_TITLE, FIRST_SUBTASK_TZ,  # noqa: E402
                      FIXTURE_ZONE, SplitApproveSandbox, spec_text,
                      two_valid_subsections)
from orchestrator import artifact_branch  # noqa: E402


class ApproveSpawnsSubtaskTest(SplitApproveSandbox):
    """Заведение подзадачи первого подраздела: название и `TZ.md`.

    Ловит мутацию: подзадаче достаётся название родителя вместо
    заголовка подраздела, либо `TZ.md` несёт голый текст ТЗ подраздела
    БЕЗ добавленной первой строки со ссылкой на родителя (мутация:
    строка «Родительская задача: ...» не собирается вовсе, либо
    собирается, но не подставляется в аргумент, ставший `TZ.md`).
    """

    def test_ac5_first_subsection_becomes_a_titled_subtask_with_linked_tz(self):
        text = spec_text(zones=FIXTURE_ZONE, subsections=two_valid_subsections())
        sha = self.enter_spec_gate(text)

        self.approve(sha)

        new_ids = self.all_task_ids() - {self.TASK}
        titles = self.titles_by_id(new_ids)
        matching = [tid for tid, title in titles.items()
                   if title == FIRST_SUBTASK_TITLE]
        self.assertTrue(
            matching,
            f"после approve ни одна новая задача не несёт название "
            f"первого подраздела «{FIRST_SUBTASK_TITLE}» (AC-5): "
            f"заведённые задачи {titles}")
        sub_id = matching[0]

        files = artifact_branch.read_tree(sub_id)
        tz = files.get(f"tasks/{sub_id}/TZ.md", "")
        link_line = f"Родительская задача: {self.TASK} — {self.TITLE}"
        self.assertIn(
            link_line, tz,
            f"TZ.md подзадачи {sub_id} не несёт строку-ссылку на "
            f"родителя (AC-5): {tz!r}")
        self.assertIn(
            FIRST_SUBTASK_TZ, tz,
            f"TZ.md подзадачи {sub_id} не несёт текст ТЗ подраздела "
            f"(AC-5): {tz!r}")
        self.assertLess(
            tz.index(link_line), tz.index(FIRST_SUBTASK_TZ),
            f"строка-ссылка на родителя не предшествует тексту ТЗ "
            f"подраздела в TZ.md подзадачи {sub_id} (AC-5, "
            f"«добавленной ПЕРВОЙ строкой»): {tz!r}")


if __name__ == "__main__":
    unittest.main()
