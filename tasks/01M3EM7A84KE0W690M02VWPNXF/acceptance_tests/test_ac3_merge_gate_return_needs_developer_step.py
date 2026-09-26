"""Приёмочный тест 01M3EM7A84KE0W690M02VWPNXF — AC-3: воспроизведение
живого случая 21.09 (задача 01M31DRD81) заглушками git — конфликт подтяжки
на ГЕЙТЕ МЕРЖА, возврат из эскалации в `in_dev`, и следующий `auto`,
который обязан отдать шаг роли developer вместо немедленного повтора
предварительного advance по тому же неизменившемуся конфликту.

Красен до реализации: эскалация конфликта подтяжки из `merge_gate` сегодня
метки не пишет (`orchestrator/pull.py::_handle_merge_failure`, ветка `if
state == "in_dev"`), поэтому единственная запись `state -> in_dev`, которую
`auto._role_step_since_state_entry` видит после возврата, несёт
фиксированный текст `_approve_escalated` («эскалация разрешена,
продолжаем») из `_ESCALATED_RETURN_DETAILS` и пропускается при поиске
анкера — рубеж деградирует на «сверять нечем» и НЕ держит предварительный
advance: тот первым же действием итерации повторяет подтяжку, снова ловит
тот же конфликт и эскалирует задачу раньше, чем developer получит шаг.
Прогон до реализации обязан упасть именно на `assertNotIn(ESCALATION_
ACTION, ...)`/отсутствии `auto.REWORK_REFUSAL_ACTION`, не на чём-то ещё.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (ESCALATION_ACTION, PullConflictSandbox,  # noqa: E402
                      ROLE_STEP_ACTION)
from orchestrator import auto  # noqa: E402


class MergeGateConflictReturnGivesDeveloperItsStepTest(PullConflictSandbox):
    """AC-3: после возврата из эскалации конфликта подтяжки гейта мержа
    цикл `auto` обязан начать со шага роли текущего состояния (`developer`
    в `in_dev`), журналируя отказ рубежа переделки, — иначе разрешать
    конфликт некому, и Оператор платит лишним кругом `answer`/`approve`
    за каждый такой конфликт (копилка П1 21.09)."""

    def test_ac3_auto_refuses_pre_advance_and_runs_developer_after_the_return(self):
        """Конфликт подтяжки на гейте мержа эскалирует задачу; `approve`
        возврата переводит её в `in_dev`; следующий `auto` обязан
        журналировать `auto.REWORK_REFUSAL_ACTION` и позвать developer —
        и не сделать ни одного предварительного advance до этого шага
        (в журнале до шага роли нет новой записи `state -> escalated`).

        Ловит мутацию: метка записана только для `in_dev` (условие не
        расширено на `merge_gate`) — рубеж пред-advance не держится,
        `_pre_advance_step` первым же действием повторяет подтяжку и
        переэскалирует задачу: `auto.REWORK_REFUSAL_ACTION` в журнале не
        появится вовсе, а `state -> escalated` появится ДО шага
        developer — оба `assert` ниже это поймают.
        """
        self.write_plan_ready()

        outcome = self.escalate_via_merge_gate()
        self.assertEqual(
            outcome, ("stopped",),
            "конфликт подтяжки обязан остановить тело гейта мержа — "
            "сценарий 21.09 не воспроизведён")
        self.assertEqual(self.state(), "escalated")

        self.approve()
        self.assertEqual(
            self.state(), "in_dev",
            "возврат из эскалации подтяжки обязан вести в in_dev "
            "(escalated_from эта эскалация не пишет)")

        before_auto = len(self.journal_rows())
        self.auto()
        rows = self.journal_rows()[before_auto:]
        actions = [r["action"] for r in rows]

        self.assertIn(
            auto.REWORK_REFUSAL_ACTION, actions,
            "auto не журналировал отказ рубежа переделки — предварительный "
            "advance не был отклонён после возврата из эскалации")
        step_index = next(
            (i for i, r in enumerate(rows)
             if r["action"] == ROLE_STEP_ACTION and r["actor"] == "developer"),
            None)
        self.assertIsNotNone(
            step_index,
            "auto не отдал шаг роли developer после возврата из эскалации")
        self.assertLess(
            actions.index(auto.REWORK_REFUSAL_ACTION), step_index,
            "отказ рубежа переделки обязан быть журналирован ДО шага "
            "developer — он и есть причина, по которой шаг отдан роли")
        self.assertNotIn(
            ESCALATION_ACTION, actions[:step_index],
            "auto сделал предварительный advance до шага developer и снова "
            "эскалировал задачу тем же конфликтом — лишний круг "
            "answer/approve Оператора (живой случай 21.09)")


if __name__ == "__main__":
    import unittest
    unittest.main()
