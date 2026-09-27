"""AC-7, сохраняемая половина (tasks/01M3HWXFYWVDHGW011P6BZJFYA/SPEC.md):
на гейте мержа исходы совпадают с переходом `in_dev -> verifying` и там,
где задача поведение НЕ меняет — пропуск без названной причины (AC-3),
безусловный маркер (AC-4) и маркер на существующем имени (AC-5)
эскалируют мерж, как эскалировали до неё.

Зелёный с рождения: сегодня узел даёт находку на любой появившийся
маркер, и все три сценария уже эскалируют — это тест СОХРАНЕНИЯ второго
рубежа. Он краснеет на мутации «послабление вписано в общий узел шире
формулировки требования 2» (причина не проверяется, безусловность не
проверяется, имя не сверяется с базой): тогда вместе с переходом
проседает и мерж, а гейт мержа — последняя точка перед main.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (EXISTING_PATH,  # noqa: E402
                      EXISTING_WITH_CONDITIONAL_SKIP_ON_METHOD, NO_REASON,
                      NO_REASON_METHOD, NO_REASON_PATH, UNCONDITIONAL,
                      UNCONDITIONAL_METHODS, UNCONDITIONAL_PATH, GateSandbox)


class MergeGateKeptBehaviourTest(GateSandbox):

    def _assert_escalated(self, outcome, path: str, names) -> None:
        self.assertTrue(
            outcome.escalated,
            f"находка обязана остановить мерж (AC-7); журнал: "
            f"{outcome.journal}; stdout: {outcome.printed}")
        self.assertEqual("escalated", outcome.state, outcome.journal)
        self.assertIn(path, outcome.journal)
        for name in names:
            self.assertIn(name, outcome.journal,
                          f"detail эскалации обязан назвать {name} (AC-7); "
                          f"журнал: {outcome.journal}")

    def test_ac7_skip_without_reason_escalates_merge_gate(self):
        """Та же правка, что в AC-3 (условный пропуск нового метода без
        аргумента причины), на гейте мержа: задача уходит в `escalated`.

        Ловит мутацию: проверка названной причины сделана только в
        обёртке перехода — на мерже послабление шире, и пропуск без
        единого слова объяснения уезжает в main.
        """
        self.apply(NO_REASON_PATH, NO_REASON)

        self._assert_escalated(self.run_merge_gate(), NO_REASON_PATH,
                               (NO_REASON_METHOD,))

    def test_ac7_unconditional_marker_escalates_merge_gate(self):
        """Та же правка, что в AC-4 (безусловные маркеры нового файла с
        названной причиной), на гейте мержа: задача уходит в `escalated`,
        и в журнале назван каждый из четырёх методов.

        Ловит мутацию: условность проверяется только на переходе — тест,
        выключенный на всех машинах навсегда, проходит последний рубеж
        перед main с формальной причиной в скобках.
        """
        self.apply(UNCONDITIONAL_PATH, UNCONDITIONAL)

        self._assert_escalated(self.run_merge_gate(), UNCONDITIONAL_PATH,
                               UNCONDITIONAL_METHODS)

    def test_ac7_skip_on_existing_method_escalates_merge_gate(self):
        """Та же правка, что в AC-5 (условный пропуск с причиной на
        СУЩЕСТВУЮЩЕМ методе), на гейте мержа: задача уходит в
        `escalated`.

        Ловит мутацию: сверка имени с базой сравнения сделана только на
        переходе — старый тест гасится условной строкой и доезжает до
        main без мандата Оператора, хотя требование 4 сохраняет здесь
        прежнее поведение дословно.
        """
        self.apply(EXISTING_PATH, EXISTING_WITH_CONDITIONAL_SKIP_ON_METHOD)

        self._assert_escalated(self.run_merge_gate(), EXISTING_PATH,
                               ("test_existing_one",))


if __name__ == "__main__":
    unittest.main()
