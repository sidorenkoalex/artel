"""AC-4 (tasks/01M1SAA2AZX3ERQ779QJ5TS9J4/SPEC.md): раздел «Причина
возврата» расположен до текста SPEC.md/PLAN.md/REVIEW.md/карты кодовой
базы в брифе.

Красен до реализации: раздел не собирается вовсе — `text.find`
возвращает -1 для заголовка раздела, сравнение индексов падает на
каждом сценарии (не потому что порядок неверный, а потому что левой
части сравнения ещё не существует)."""
import unittest

from _sandbox import (  # noqa: E402
    BriefSandbox, DETAIL_ESCALATED_ANALYST, DETAIL_ESCALATED_APPROVE,
    DETAIL_REVIEW_CHANGES_REQUESTED, RETURN_REASON_HEADER)

SPEC_MARKER = "Маркер-текста-SPEC."
MAP_MARKER = "Маркер-текста-карты."
CLAUDE_MARKER = "Маркер-текста-CLAUDE."


class Ac4OrderingTest(BriefSandbox):
    """Ловит мутацию: реализация дописывает раздел «Причина возврата»
    В КОНЕЦ собранного текста (например простой конкатенацией `parts +
    [return_reason]` вместо `[return_reason] + parts`) — маркеры
    SPEC/карты/REVIEW оказались бы раньше заголовка раздела, и
    `assertLess` поймает перевёрнутый порядок."""

    def test_ac4_developer_brief_return_reason_precedes_spec_map_and_review(self):
        self.write_review("МАРКЕР-ЗАМЕЧАНИЯ-РЕВЬЮ")
        self.seed_state("in_dev", "fsm", "приёмочные тесты готовы")
        self.seed_state("review", "operator", "готово к ревью")
        self.seed_state("in_dev", "fsm", DETAIL_REVIEW_CHANGES_REQUESTED)

        text = self.build_developer_brief()

        header_at = text.find(RETURN_REASON_HEADER)
        self.assertGreaterEqual(header_at, 0, "раздел не найден в брифе")
        self.assertLess(header_at, text.find(SPEC_MARKER))
        self.assertLess(header_at, text.find(MAP_MARKER))
        self.assertLess(header_at, text.find(CLAUDE_MARKER))
        self.assertLess(header_at, text.find("МАРКЕР-ЗАМЕЧАНИЯ-РЕВЬЮ"))

    def test_ac4_analyst_brief_return_reason_precedes_map(self):
        self.seed_state("escalated", "fsm", DETAIL_ESCALATED_ANALYST)
        self.write_answer(1, "МАРКЕР-ОТВЕТА-ANALYST")
        self.seed_state("spec_writing", "operator", DETAIL_ESCALATED_APPROVE)

        text = self.build_analyst_brief()

        header_at = text.find(RETURN_REASON_HEADER)
        self.assertGreaterEqual(header_at, 0, "раздел не найден в брифе")
        self.assertLess(header_at, text.find(MAP_MARKER))


if __name__ == "__main__":
    unittest.main()
