"""Приёмочные тесты 01M1SHJZCE0Y4DXAAWQ2W585A7 — AC-7 (идентификаторы
заведённых подзадач печатаются на экран по завершении `approve`).

`tests.sandbox.capture` перехватывает stdout вызова `fsm.cmd_approve` —
тот же приём, что уже используют `ZonesApproveSandbox`/остальные
песочницы этого пакета.

Красен до реализации: до появления ветки деления `approve` на `spec_gate`
печатает только «дальше: artel.py run ...» (`orchestrator/fsm.py:821/826`)
— ни один новый id в этом выводе появиться не может, потому что ни одна
подзадача не заводится (см. докстринг `test_ac5_approve_spawns_subtask.py`).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (FIXTURE_ZONE, SplitApproveSandbox,  # noqa: E402
                      spec_text, two_valid_subsections)


class PrintedSubtaskIdsTest(SplitApproveSandbox):
    """Оба заведённых id встречаются в тексте, напечатанном `approve`.

    Ловит мутацию: подзадачи заводятся и id собираются в переменную, но
    строка с ними не печатается (например только пишется в журнал, но не
    в `print`) — вывод `approve` не содержит ни одного из новых id, хотя
    строки задач в БД уже заведены.
    """

    def test_ac7_approve_output_names_both_new_task_ids(self):
        text = spec_text(zones=FIXTURE_ZONE, subsections=two_valid_subsections())
        sha = self.enter_spec_gate(text)

        output = self.approve(sha)

        new_ids = self.all_task_ids() - {self.TASK}
        self.assertEqual(
            len(new_ids), 2,
            f"approve не завёл ровно 2 подзадачи на 2 валидных подраздела "
            f"(предпосылка теста AC-7, см. AC-5/AC-11): {new_ids}")
        for sub_id in new_ids:
            self.assertIn(
                sub_id, output,
                f"вывод approve не называет id заведённой подзадачи "
                f"{sub_id} (AC-7): {output!r}")


if __name__ == "__main__":
    unittest.main()
