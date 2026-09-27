"""AC-7, новая половина (tasks/01M3HWXFYWVDHGW011P6BZJFYA/SPEC.md): на
гейте мержа исходы совпадают с переходом `in_dev -> verifying` там, где
задача поведение МЕНЯЕТ — условный пропуск с причиной в новом тесте
(AC-1) мержу молчит, ранний `return` под условием (AC-6) эскалирует.

Узел один, зовут его два рубежа: здесь тот же сценарий прогоняется через
вход гейта мержа (`fsm_merge_gate._test_integrity_diff_gate`), а не через
обёртку перехода.

Красен до реализации: сегодня узел даёт находку на любой появившийся
маркер (условный пропуск нового файла эскалирует мерж вместо молчания) и
не знает раннего `return` вовсе (ранний выход мерж пропускает вместо
эскалации) — оба сценария падают на противоположном исходе.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (EARLY_RETURN, EARLY_RETURN_CLASS,  # noqa: E402
                      EARLY_RETURN_METHOD, EARLY_RETURN_PATH,
                      NEW_CONDITIONAL, NEW_CONDITIONAL_PATH, REFUSAL_ACTION,
                      GateSandbox)


class MergeGateNewBehaviourTest(GateSandbox):

    def test_ac7_conditional_skip_with_reason_does_not_escalate_merge_gate(self):
        """Та же единственная правка, что в AC-1 (новый файл с тремя
        условными пропусками и названной причиной), на гейте мержа:
        задача остаётся в `merge_gate`, эскалации нет, рубеж молчит.

        Ловит мутацию: послабление вписано не в общий узел, а в обёртку
        перехода `in_dev -> verifying` (`_test_integrity_gate`) — тот же
        честный неприменимый тест проходит переход и упирается в
        эскалацию на мерже, то есть рубеж всё равно требует мандата, но
        уже на самом дорогом шаге конвейера.
        """
        self.apply(NEW_CONDITIONAL_PATH, NEW_CONDITIONAL)

        outcome = self.run_merge_gate()

        self.assertFalse(
            outcome.escalated,
            f"условный пропуск с причиной мерж не останавливает (AC-7); "
            f"журнал: {outcome.journal}; stdout: {outcome.printed}")
        self.assertEqual("merge_gate", outcome.state, outcome.journal)
        self.assertNotIn(REFUSAL_ACTION, outcome.actions, outcome.journal)

    def test_ac7_early_return_escalates_merge_gate(self):
        """Та же единственная правка, что в AC-6 (новый метод с ранним
        `return` под условием), на гейте мержа: задача уходит в
        `escalated`, а detail несёт файл и квалифицированное имя метода —
        тот же текст, что отказ на переходе.

        Ловит мутацию: распознавание раннего `return` добавлено в
        обёртку перехода, а не в общий узел — ветка, дошедшая до мержа
        другим маршрутом (ручной `advance` Оператора, подтяжка main
        после `verifying`), уносит обход рубежа прямо в main.
        """
        self.apply(EARLY_RETURN_PATH, EARLY_RETURN)

        outcome = self.run_merge_gate()

        self.assertTrue(
            outcome.escalated,
            f"ранний return под условием останавливает мерж (AC-7); "
            f"журнал: {outcome.journal}; stdout: {outcome.printed}")
        self.assertEqual("escalated", outcome.state, outcome.journal)
        self.assertIn(EARLY_RETURN_PATH, outcome.journal)
        self.assertIn(EARLY_RETURN_CLASS, outcome.journal)
        self.assertIn(EARLY_RETURN_METHOD, outcome.journal)


if __name__ == "__main__":
    unittest.main()
