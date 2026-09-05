"""AC-3 (tasks/01M1SAA2AZX3ERQ779QJ5TS9J4/SPEC.md): для возврата из
`escalated` по `approve` раздел «Причина возврата» несёт дословный
`detail` записи журнала `state -> escalated`, которой задача вошла в
этот цикл эскалации, и явную ссылку на файл `tasks/<id>/ANSWER-n.md` с
наибольшим `n`.

Красен до реализации: раздел не собирается вовсе — ни детали
эскалации, ни ссылки на ANSWER-n.md в брифе нет; `assertIn` падает на
каждом сценарии. Там, где тест проверяет ОТСУТСТВИЕ фиксированной
фразы approve в теле раздела, он сегодня красный по другой причине
(раздела нет вовсе, слайс пуст) — тоже ожидаемо для «красен до
реализации», не отдельный дефект теста.
"""
import unittest

from _sandbox import (  # noqa: E402
    BriefSandbox, DETAIL_ESCALATED_ANALYST, DETAIL_ESCALATED_APPROVE,
    DETAIL_ESCALATED_LIMIT, DETAIL_ESCALATED_TEST_AUTHOR, RETURN_REASON_CLOSING,
    RETURN_REASON_HEADER, TASK)


def _return_reason_span(text: str) -> str:
    """Текст раздела «Причина возврата» — от заголовка до фиксированной
    закрывающей фразы включительно; пустая строка, если раздела нет."""
    start = text.find(RETURN_REASON_HEADER)
    if start < 0:
        return ""
    end = text.find(RETURN_REASON_CLOSING, start)
    if end < 0:
        return text[start:]
    return text[start:end + len(RETURN_REASON_CLOSING)]


class Ac3EscalationReturnTest(BriefSandbox):
    """Ловит мутацию: реализация вместо `detail` записи `state ->
    escalated` наивно повторяет `detail` записи `state -> in_dev`,
    которую пишет approve (фиксированная фраза без содержания) — тест
    отдельно проверяет, что фиксированная фраза НЕ занимает место
    настоящей причины в теле раздела."""

    def test_ac3_developer_escalation_return_shows_escalated_state_detail(self):
        self.seed_state("in_dev", "fsm", "приёмочные тесты готовы")
        self.seed_state("review", "operator", "готово к ревью")
        self.seed_state("verifying", "fsm", "ревью пройдено")
        self.seed_state("escalated", "fsm", DETAIL_ESCALATED_LIMIT)
        self.write_answer(1, "МАРКЕР-ОТВЕТА-DEV")
        self.seed_state("in_dev", "operator", DETAIL_ESCALATED_APPROVE)

        text = self.build_developer_brief()
        span = _return_reason_span(text)

        self.assertIn(DETAIL_ESCALATED_LIMIT, span,
                     "раздел обязан нести дословную причину эскалации")
        self.assertNotIn(DETAIL_ESCALATED_APPROVE, span,
                        "фиксированная фраза approve — не содержательная "
                        "причина, не должна занимать место раздела")

    def test_ac3_developer_escalation_return_links_latest_answer_file(self):
        """Несколько раундов ANSWER — ссылка обязана указывать на
        файл с НАИБОЛЬШИМ `n` (5), не на первый попавшийся."""
        self.seed_state("in_dev", "fsm", "приёмочные тесты готовы")
        self.seed_state("review", "operator", "готово к ревью")
        self.seed_state("verifying", "fsm", "ревью пройдено")
        self.seed_state("escalated", "fsm", DETAIL_ESCALATED_LIMIT)
        for n in (1, 2, 5):
            self.write_answer(n, f"МАРКЕР-ОТВЕТА-{n}")
        self.seed_state("in_dev", "operator", DETAIL_ESCALATED_APPROVE)

        text = self.build_developer_brief()
        span = _return_reason_span(text)

        self.assertIn(f"tasks/{TASK}/ANSWER-5.md", span)
        self.assertNotIn(f"tasks/{TASK}/ANSWER-1.md", span)
        self.assertNotIn(f"tasks/{TASK}/ANSWER-2.md", span)

    def test_ac3_analyst_escalation_return_shows_escalated_detail_and_link(self):
        self.seed_state("escalated", "fsm", DETAIL_ESCALATED_ANALYST)
        self.write_answer(1, "МАРКЕР-ОТВЕТА-ANALYST")
        self.seed_state("spec_writing", "operator", DETAIL_ESCALATED_APPROVE)

        text = self.build_analyst_brief()
        span = _return_reason_span(text)

        self.assertIn(DETAIL_ESCALATED_ANALYST, span)
        self.assertIn(f"tasks/{TASK}/ANSWER-1.md", span)
        self.assertNotIn(DETAIL_ESCALATED_APPROVE, span)

    def test_ac3_test_author_escalation_return_shows_escalated_detail_and_link(self):
        self.seed_state("tests_writing", "operator",
                        "гейт SPEC пройден — приёмочные тесты до кода")
        self.seed_state("escalated", "fsm", DETAIL_ESCALATED_TEST_AUTHOR)
        self.write_answer(1, "МАРКЕР-ОТВЕТА-TESTAUTHOR")
        self.seed_state("tests_writing", "operator", DETAIL_ESCALATED_APPROVE)

        text = self.build_test_author_brief()
        span = _return_reason_span(text or "")

        self.assertIn(DETAIL_ESCALATED_TEST_AUTHOR, span)
        self.assertIn(f"tasks/{TASK}/ANSWER-1.md", span)
        self.assertNotIn(DETAIL_ESCALATED_APPROVE, span)


if __name__ == "__main__":
    unittest.main()
