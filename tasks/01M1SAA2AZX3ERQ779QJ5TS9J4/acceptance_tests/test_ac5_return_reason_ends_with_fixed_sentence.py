"""AC-5 (tasks/01M1SAA2AZX3ERQ779QJ5TS9J4/SPEC.md): раздел «Причина
возврата» заканчивается текстом «шаг без правки, закрывающей причину,
не засчитывается».

Красен до реализации: раздел не собирается — фиксированная фраза нигде
не встречается, `assertIn` падает на обоих сценариях.
"""
import unittest

from _sandbox import (  # noqa: E402
    BriefSandbox, DETAIL_ESCALATED_APPROVE, DETAIL_ESCALATED_LIMIT,
    DETAIL_REJECT_MERGE_GATE, RETURN_REASON_CLOSING, RETURN_REASON_HEADER)


class Ac5ClosingSentenceTest(BriefSandbox):
    """Ловит мутацию: реализация несёт закрывающую фразу только для
    «прямого» возврата (`reject`/`review`), но не для ветки возврата из
    эскалации (AC-3), поскольку та строится отдельным путём кода —
    второй сценарий ниже ловит именно эту рассинхронизацию."""

    def test_ac5_plain_reject_return_reason_ends_with_fixed_sentence(self):
        self.seed_state("in_dev", "fsm", "приёмочные тесты готовы")
        self.seed_state("review", "operator", "готово к ревью")
        self.seed_state("verifying", "fsm", "ревью пройдено")
        self.seed_state("acceptance", "fsm", "зелёный CI")
        self.seed_state("merge_gate", "operator", "приёмка пройдена")
        self.seed_state("in_dev", "operator", DETAIL_REJECT_MERGE_GATE)

        text = self.build_developer_brief()

        header_at = text.find(RETURN_REASON_HEADER)
        closing_at = text.find(RETURN_REASON_CLOSING)
        self.assertGreaterEqual(header_at, 0, "раздел не найден в брифе")
        self.assertGreater(closing_at, header_at,
                          "закрывающая фраза обязана идти после заголовка "
                          "раздела, в его теле")

    def test_ac5_escalation_return_reason_also_ends_with_fixed_sentence(self):
        self.seed_state("in_dev", "fsm", "приёмочные тесты готовы")
        self.seed_state("review", "operator", "готово к ревью")
        self.seed_state("verifying", "fsm", "ревью пройдено")
        self.seed_state("escalated", "fsm", DETAIL_ESCALATED_LIMIT)
        self.write_answer(1, "МАРКЕР-ОТВЕТА-DEV")
        self.seed_state("in_dev", "operator", DETAIL_ESCALATED_APPROVE)

        text = self.build_developer_brief()

        header_at = text.find(RETURN_REASON_HEADER)
        closing_at = text.find(RETURN_REASON_CLOSING)
        self.assertGreaterEqual(header_at, 0, "раздел не найден в брифе")
        self.assertGreater(closing_at, header_at,
                          "закрывающая фраза обязана идти после заголовка "
                          "раздела и в ветке возврата из эскалации")


if __name__ == "__main__":
    unittest.main()
