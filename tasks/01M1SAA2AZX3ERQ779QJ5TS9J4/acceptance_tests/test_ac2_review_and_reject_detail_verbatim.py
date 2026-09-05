"""AC-2 (tasks/01M1SAA2AZX3ERQ779QJ5TS9J4/SPEC.md): раздел «Причина
возврата» несёт дословный текст поля `detail` последней записи журнала
`state -> <текущее состояние>` данной задачи — для `review -> in_dev` и
для `reject` из `acceptance`/`verifying`/`merge_gate`.

Красен до реализации: раздел не собирается вовсе, поэтому дословный
текст `detail` (например `DETAIL_REJECT_VERIFYING`, несущий конкретные
имена тестов) нигде не появляется в брифе — `assertIn` падает на
каждом из четырёх сценариев.
"""
import unittest

from _sandbox import (  # noqa: E402
    BriefSandbox, DETAIL_REJECT_ACCEPTANCE, DETAIL_REJECT_MERGE_GATE,
    DETAIL_REJECT_VERIFYING, DETAIL_REVIEW_CHANGES_REQUESTED)


class Ac2DetailVerbatimTest(BriefSandbox):
    """Ловит мутацию: реализация подставляет в раздел свой пересказ
    причины (например «правки ревью» вместо дословного `detail`) или
    берёт `detail` не ПОСЛЕДНЕЙ, а произвольной записи `state ->
    in_dev` — тесты используют разные строки на каждом шаге истории,
    ложная более ранняя запись не пройдёт `assertIn` буквальным текстом."""

    def test_ac2_review_changes_requested_detail_is_verbatim(self):
        self.seed_state("in_dev", "fsm", "приёмочные тесты готовы")
        self.seed_state("review", "operator", "готово к ревью")
        self.seed_state("in_dev", "fsm", DETAIL_REVIEW_CHANGES_REQUESTED)

        text = self.build_developer_brief()

        self.assertIn(DETAIL_REVIEW_CHANGES_REQUESTED, text)

    def test_ac2_reject_from_acceptance_detail_is_verbatim(self):
        self.seed_state("in_dev", "fsm", "приёмочные тесты готовы")
        self.seed_state("review", "operator", "готово к ревью")
        self.seed_state("verifying", "fsm", "ревью пройдено")
        self.seed_state("acceptance", "fsm", "зелёный CI")
        self.seed_state("in_dev", "operator", DETAIL_REJECT_ACCEPTANCE)

        text = self.build_developer_brief()

        self.assertIn(DETAIL_REJECT_ACCEPTANCE, text)

    def test_ac2_reject_from_verifying_detail_is_verbatim(self):
        self.seed_state("in_dev", "fsm", "приёмочные тесты готовы")
        self.seed_state("review", "operator", "готово к ревью")
        self.seed_state("verifying", "fsm", "ревью пройдено")
        self.seed_state("in_dev", "operator", DETAIL_REJECT_VERIFYING)

        text = self.build_developer_brief()

        self.assertIn(DETAIL_REJECT_VERIFYING, text)

    def test_ac2_reject_from_merge_gate_detail_is_verbatim(self):
        self.seed_state("in_dev", "fsm", "приёмочные тесты готовы")
        self.seed_state("review", "operator", "готово к ревью")
        self.seed_state("verifying", "fsm", "ревью пройдено")
        self.seed_state("acceptance", "fsm", "зелёный CI")
        self.seed_state("merge_gate", "operator", "приёмка пройдена")
        self.seed_state("in_dev", "operator", DETAIL_REJECT_MERGE_GATE)

        text = self.build_developer_brief()

        self.assertIn(DETAIL_REJECT_MERGE_GATE, text)


if __name__ == "__main__":
    unittest.main()
