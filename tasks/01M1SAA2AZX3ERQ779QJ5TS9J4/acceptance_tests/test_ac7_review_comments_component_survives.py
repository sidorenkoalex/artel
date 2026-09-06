"""AC-7 (tasks/01M1SAA2AZX3ERQ779QJ5TS9J4/SPEC.md): бриф developer
после `review -> in_dev` содержит текст замечаний ревью (компонент
REVIEW.md остаётся частью брифа, как и до этой задачи).

Красен до реализации: раздел «Причина возврата» ещё не собирается —
`assertIn(RETURN_REASON_HEADER, ...)` падает, даже несмотря на то что
компонент REVIEW.md сам по себе уже включён в `developer_brief` до
этой задачи (SPEC 01M1NKTF173WV5CPDZ1C3WW69K) и его собственная
проверка (`assertIn("МАРКЕР-ЗАМЕЧАНИЯ-РЕВЬЮ...", ...)`) сегодня
проходит — метод проверяет оба факта разом, поэтому падает целиком."""
import unittest

from _sandbox import (  # noqa: E402
    BriefSandbox, DETAIL_REVIEW_CHANGES_REQUESTED, RETURN_REASON_HEADER)


class Ac7ReviewCommentsSurviveTest(BriefSandbox):
    """Ловит мутацию: реализация раздела «Причина возврата» по ошибке
    ЗАМЕНЯЕТ компонент REVIEW.md новым разделом (например, переиспользуя
    ту же переменную/индекс списка `parts`) вместо того, чтобы
    добавляться как отдельный, дополнительный элемент — тогда текст
    замечаний ревью пропал бы из брифа."""

    def test_ac7_developer_brief_still_carries_review_comments_text_after_changes_requested(self):
        self.write_review("МАРКЕР-ЗАМЕЧАНИЯ-РЕВЬЮ-major-исправь-X")
        self.seed_state("in_dev", "fsm", "приёмочные тесты готовы")
        self.seed_state("review", "operator", "готово к ревью")
        self.seed_state("in_dev", "fsm", DETAIL_REVIEW_CHANGES_REQUESTED)

        text = self.build_developer_brief()

        self.assertIn(RETURN_REASON_HEADER, text)
        self.assertIn("МАРКЕР-ЗАМЕЧАНИЯ-РЕВЬЮ-major-исправь-X", text,
                     "компонент REVIEW.md обязан остаться в брифе целиком")


if __name__ == "__main__":
    unittest.main()
