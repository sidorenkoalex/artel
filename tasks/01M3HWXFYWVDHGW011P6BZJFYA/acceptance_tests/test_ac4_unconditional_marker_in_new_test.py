"""AC-4 (tasks/01M3HWXFYWVDHGW011P6BZJFYA/SPEC.md): новый тестовый метод с
БЕЗУСЛОВНЫМ маркером (`@skip`, `@expectedFailure`, `@pytest.mark.xfail`,
`self.skipTest("<причина>")` вне `if`) остаётся находкой, даже когда
причина названа.

Зелёный с рождения: сегодня находкой считается любой появившийся маркер,
поэтому безусловные уже отказывают — это тест СОХРАНЕНИЯ рубежа на
границе будущего послабления. Он краснеет на мутации «условность не
проверяется»: признаком послабления взята одна лишь названная причина, и
`@unittest.skip("причина")` в новом файле — тест, выключенный на ВСЕХ
машинах навсегда, — проходит рубеж наравне с честно неприменимым.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (REFUSAL_ACTION, UNCONDITIONAL,  # noqa: E402
                      UNCONDITIONAL_METHODS, UNCONDITIONAL_PATH, GateSandbox)


class UnconditionalMarkerInNewTestTest(GateSandbox):

    def test_ac4_unconditional_markers_refuse_even_with_reason(self):
        """Новый файл несёт четыре безусловно выключенных метода, у трёх
        из них причина названа текстом: переход отказывает, и detail
        называет КАЖДЫЙ из четырёх методов.

        Ловит мутацию: условность распознана только у декораторов
        (`skipIf`/`skipUnless`/`skipif` против `skip`/`xfail`), а вызов
        `self.skipTest("причина")` в теле метода считается условным
        независимо от того, стоит ли он внутри `if` — самый простой
        способ погасить новый тест целиком («первой строкой тела»)
        начинает проходить рубеж с названной причиной, хотя требование 3
        называет его находкой дословно.
        """
        self.apply(UNCONDITIONAL_PATH, UNCONDITIONAL)

        outcome = self.run_gate()

        self.assertTrue(
            outcome.refused,
            f"безусловный маркер остаётся находкой (AC-4); журнал: "
            f"{outcome.journal}; stdout: {outcome.printed}")
        self.assertIn(REFUSAL_ACTION, outcome.actions, outcome.journal)
        self.assertIn(UNCONDITIONAL_PATH, outcome.detail)
        for method in UNCONDITIONAL_METHODS:
            self.assertIn(
                method, outcome.detail,
                f"detail обязан назвать метод {method}: его маркер "
                f"безусловен (AC-4); detail: {outcome.detail}")


if __name__ == "__main__":
    unittest.main()
