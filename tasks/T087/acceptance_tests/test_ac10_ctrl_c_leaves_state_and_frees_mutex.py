"""AC-10 (tasks/T087/SPEC.md): прерывание `approve` комбинацией Ctrl-C в
любой момент цикла ожидания оставляет задачу в состоянии `merge_gate` и
не оставляет мьютекс merge-окна захваченным прерванной сессией.

Источник — tasks/T087/SPEC.md, «Критерии приёмки», AC-10.

Ctrl-C симулируется `KeyboardInterrupt`, поднятым из точки, которую
зовёт цикл ожидания на каждой итерации (`ci.branch_status` — тот же
боундари, что и в остальных файлах этой задачи) — это ЧЕСТНОЕ
прерывание в процессе теста, тем же способом, каким `KeyboardInterrupt`
обычно и попадает в код Python (исключение, поднятое обработчиком
сигнала в точке, где исполнение оказалось в момент Ctrl-C).

Красен до реализации: сегодня после "pulled" `approve` останавливается
СРАЗУ, ДО первого вызова `ci.branch_status` в этом вызове
(`orchestrator/fsm.py`) — `KeyboardInterrupt` мока никогда не
поднимется, `assertRaises(KeyboardInterrupt)` ниже упадёт "DID NOT
RAISE" — явный, не тихий провал.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import MergeGateCiWaitTest  # noqa: E402


class Ac10CtrlCLeavesStateAndFreesMutexTest(MergeGateCiWaitTest):

    def setUp(self):
        super().setUp()
        self.enter_merge_gate()

    def test_ac10_interrupt_during_wait_keeps_gate_state_and_frees_mutex(self):
        self.add_main_commit()

        def raises_keyboard_interrupt(branch):
            raise KeyboardInterrupt

        self.patch_branch_status(raises_keyboard_interrupt)

        with self.assertRaises(KeyboardInterrupt):
            self.approve()

        self.assertEqual(
            self.state(), "merge_gate",
            "AC-10: прерывание Ctrl-C во время цикла ожидания не имеет "
            "права сдвинуть задачу с гейта merge_gate")
        self.assertTrue(
            self.merge_lock_free(),
            "AC-10: прерывание Ctrl-C во время цикла ожидания не имеет "
            "права оставить мьютекс merge-окна захваченным прерванной "
            "сессией")


if __name__ == "__main__":
    import unittest
    unittest.main()
