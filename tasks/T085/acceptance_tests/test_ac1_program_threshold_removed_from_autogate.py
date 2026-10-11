"""AC-1 (tasks/T085/SPEC.md): автогейт acceptance
(`orchestrator/fsm.py::_autogate_conditions`) не проверяет условие
«пороги программы (A1) не пробиты» — при выполнении остальных условий
переход `acceptance -> merge_gate` проходит автогейтом независимо от
значения `store.total_spent` относительно `config.PROGRAM_STOP_LOSS_USD`.

Сценарий: `seed_program_overspend()` (другая задача с расходом далеко за
пределами самого строгого из `config.PROGRAM_ALERT_RATIOS`, читается из
конфигурации, а не литералом — урок T062) поверх иначе полностью зелёного
сценария (`prepare_scenario()` без прочих отклонений: приёмочные тесты
задачи зелёные без manual/skip, полный набор `tests/` worktree зелёный,
бюджет задачи не превышен, REVIEW approved свежей итерации). Единственное
отклонение от зелёного пути — пробитый порог программы.

Красен до реализации: `orchestrator/fsm.py::_autogate_conditions` сегодня
явно проверяет это условие (`if any(total >= config.PROGRAM_STOP_LOSS_USD
* ratio for ratio in config.PROGRAM_ALERT_RATIOS): return ok, "автогейт:
порог расхода программы (A1) пробит"`) и останавливает задачу в
`acceptance` — до кода задачи (удаление этой проверки, SPEC требование 1)
оба ассерта ниже красные: состояние остаётся `acceptance`, а не
`merge_gate`, и причина отказа содержит фразу «порог расхода программы».
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AutogateSandbox  # noqa: E402


class ProgramThresholdBreachNoLongerBlocksAutogateTest(AutogateSandbox):

    def test_ac1_overspend_still_reaches_merge_gate_via_autogate(self):
        self.seed_program_overspend()
        self.prepare_scenario()

        out = self.advance_to_autogate()

        self.assertEqual(
            self.state(), "merge_gate",
            f"AC-1: пробитый порог программы (A1) не имеет права "
            f"останавливать автогейт acceptance при выполнении остальных "
            f"условий — вывод: {out!r}")

    def test_ac1_breach_reason_no_longer_appears_as_a_blocking_cause(self):
        self.seed_program_overspend()
        self.prepare_scenario()

        out = self.advance_to_autogate()

        blocking_rows = [r for r in self.journal_rows()
                         if "автогейт:" in (r[2] or "")]
        self.assertFalse(
            any("порог расхода программы" in (r[2] or "")
               for r in blocking_rows),
            f"AC-1: «порог расхода программы (A1)» не имеет права быть "
            f"причиной отказа автогейта; журнал: {blocking_rows}")
        self.assertNotIn("порог расхода программы", out)


if __name__ == "__main__":
    unittest.main()
