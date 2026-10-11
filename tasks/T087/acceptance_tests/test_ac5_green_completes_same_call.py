"""AC-5 (tasks/T087/SPEC.md): зелёный CI пушнутого head (в том числе
позеленевший после авто-ре-рана T082) внутри цикла ожидания приводит к
перезахвату мьютекса merge-окна той же сессией и продолжению ТОГО ЖЕ
ВЫЗОВА `approve` к сверке свежести и мержу — без нового вызова `approve`
Оператором.

Источник — tasks/T087/SPEC.md, «Критерии приёмки», AC-5.

Контраст с прежним поведением (T053, требование 6, зафиксированным
`tasks/T053/acceptance_tests/test_ac3_...py::
test_ac3_second_approve_after_pull_merges_into_main`): там `pulled`
останавливал `approve` СРАЗУ, и merge выполнял ТОЛЬКО отдельный,
следующий вызов `approve`, сделанный заново (Оператором, руками, после
того как CI нового head позеленел). `self.approve()` этой песочницы —
двухшаговое подтверждение sha (`confirm_fixation`), НЕ имеющее отношения
к ожиданию CI (тот же приём, что и во всех остальных AC-файлах этой
задачи) — предмет этого теста в том, что после ЭТОГО одного
раунда `self.approve()` задача обязана дойти до `done`, не оставаясь на
`merge_gate` в ожидании ЕЩЁ одного самостоятельного вызова `approve`.

Красен до реализации: сегодня `_cmd_approve_merge_gate` печатает
"дождись зелёного CI... и повтори" и возвращается, не читая
`ci.branch_status` вовсе в этом вызове (`orchestrator/fsm.py`) — задача
остаётся в `merge_gate`, не `done`, после одного `self.approve()`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import GREEN, MergeGateCiWaitTest  # noqa: E402


class Ac5GreenCompletesSameCallTest(MergeGateCiWaitTest):

    def setUp(self):
        super().setUp()
        self.enter_merge_gate()

    def test_ac5_single_approve_call_reaches_done_after_pull_and_green_ci(self):
        c2 = self.add_main_commit()
        self.patch_branch_status(lambda branch: GREEN)

        self.approve()

        self.assertEqual(
            self.state(), "done",
            "AC-5: один раунд approve (сверка sha + окно merge_gate) "
            "обязан довести задачу до done после подтяжки и зелёного CI "
            "— без отдельного повторного вызова approve Оператором")
        self.assertTrue(
            self.is_ancestor(c2, self.main_head()),
            "коммит, из-за которого ветка отстала, обязан остаться "
            "предком итогового main (main не откачен назад)")


if __name__ == "__main__":
    import unittest
    unittest.main()
