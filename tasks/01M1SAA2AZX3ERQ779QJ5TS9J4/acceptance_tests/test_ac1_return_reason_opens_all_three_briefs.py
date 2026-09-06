"""AC-1 (tasks/01M1SAA2AZX3ERQ779QJ5TS9J4/SPEC.md): бриф роли
(`developer_brief`/`analyst_map_component`/`test_author_answer_component`),
чей текущий визит состояния начался возвратом — `review -> in_dev` по
`changes_requested`, `reject` из `acceptance`/`verifying`/`merge_gate`,
либо возврат из `escalated` по `approve` — открывается разделом
«Причина возврата».

Красен до реализации: раздел «Причина возврата» нигде не собирается —
ни один из семи сценариев ниже (developer x 5 триггеров возврата,
analyst и test_author x возврат из эскалации) не находит эту строку в
собранном тексте, `assertIn` падает на каждом.
"""
import unittest

from _sandbox import (  # noqa: E402
    BriefSandbox, DETAIL_ESCALATED_ANALYST, DETAIL_ESCALATED_APPROVE,
    DETAIL_ESCALATED_LIMIT, DETAIL_ESCALATED_TEST_AUTHOR,
    DETAIL_REJECT_ACCEPTANCE, DETAIL_REJECT_MERGE_GATE, DETAIL_REJECT_VERIFYING,
    DETAIL_REVIEW_CHANGES_REQUESTED, RETURN_REASON_HEADER, TASK)


class Ac1DeveloperReturnTriggersTest(BriefSandbox):
    """Ловит мутацию: реализация добавляет раздел только для одного из
    четырёх триггеров developer_brief (например, только для
    `review -> in_dev`), забыв про `reject` из соседних состояний, либо
    про возврат из эскалации."""

    def test_ac1_developer_brief_opens_with_return_reason_after_changes_requested(self):
        """review -> in_dev по вердикту changes_requested — визит начат
        возвратом, раздел обязан появиться."""
        self.seed_state("in_dev", "fsm", "приёмочные тесты готовы")
        self.seed_state("review", "operator", "готово к ревью")
        self.seed_state("in_dev", "fsm", DETAIL_REVIEW_CHANGES_REQUESTED)

        text = self.build_developer_brief()

        self.assertIn(RETURN_REASON_HEADER, text)

    def test_ac1_developer_brief_opens_with_return_reason_after_reject_from_acceptance(self):
        """reject Оператора из acceptance — визит in_dev начат возвратом."""
        self.seed_state("in_dev", "fsm", "приёмочные тесты готовы")
        self.seed_state("review", "operator", "готово к ревью")
        self.seed_state("verifying", "fsm", "ревью пройдено")
        self.seed_state("acceptance", "fsm", "зелёный CI")
        self.seed_state("in_dev", "operator", DETAIL_REJECT_ACCEPTANCE)

        text = self.build_developer_brief()

        self.assertIn(RETURN_REASON_HEADER, text)

    def test_ac1_developer_brief_opens_with_return_reason_after_reject_from_verifying(self):
        """reject Оператора из verifying — визит in_dev начат возвратом."""
        self.seed_state("in_dev", "fsm", "приёмочные тесты готовы")
        self.seed_state("review", "operator", "готово к ревью")
        self.seed_state("verifying", "fsm", "ревью пройдено")
        self.seed_state("in_dev", "operator", DETAIL_REJECT_VERIFYING)

        text = self.build_developer_brief()

        self.assertIn(RETURN_REASON_HEADER, text)

    def test_ac1_developer_brief_opens_with_return_reason_after_reject_from_merge_gate(self):
        """reject Оператора из merge_gate — визит in_dev начат возвратом."""
        self.seed_state("in_dev", "fsm", "приёмочные тесты готовы")
        self.seed_state("review", "operator", "готово к ревью")
        self.seed_state("verifying", "fsm", "ревью пройдено")
        self.seed_state("acceptance", "fsm", "зелёный CI")
        self.seed_state("merge_gate", "operator", "приёмка пройдена")
        self.seed_state("in_dev", "operator", DETAIL_REJECT_MERGE_GATE)

        text = self.build_developer_brief()

        self.assertIn(RETURN_REASON_HEADER, text)

    def test_ac1_developer_brief_opens_with_return_reason_after_escalation_approve(self):
        """approve из escalated возвращает в in_dev — визит начат
        возвратом, хотя запись `state -> in_dev` несёт фиксированную
        фразу approve, а не содержательную причину (это отдельно
        проверяет AC-3)."""
        self.seed_state("in_dev", "fsm", "приёмочные тесты готовы")
        self.seed_state("review", "operator", "готово к ревью")
        self.seed_state("verifying", "fsm", "ревью пройдено")
        self.seed_state("escalated", "fsm", DETAIL_ESCALATED_LIMIT)
        self.write_answer(1, "МАРКЕР-ОТВЕТА-DEV")
        self.seed_state("in_dev", "operator", DETAIL_ESCALATED_APPROVE)

        text = self.build_developer_brief()

        self.assertIn(RETURN_REASON_HEADER, text)


class Ac1AnalystAndTestAuthorReturnTest(BriefSandbox):
    """Ловит мутацию: реализация покрывает возврат из эскалации только
    для developer_brief, не тронув analyst_map_component/
    test_author_answer_component — три сборщика брифа перечислены в
    требовании 1 равноправно."""

    def test_ac1_analyst_brief_opens_with_return_reason_after_escalation_approve(self):
        """approve из escalated возвращает analyst в spec_writing (первое
        состояние задачи — журнал не несёт записи `state -> spec_writing`
        до этого, только вход в escalated и выход из него)."""
        self.seed_state("escalated", "fsm", DETAIL_ESCALATED_ANALYST)
        self.write_questions("МАРКЕР-ВОПРОСА")
        self.write_answer(1, "МАРКЕР-ОТВЕТА-ANALYST")
        self.seed_state("spec_writing", "operator", DETAIL_ESCALATED_APPROVE)

        text = self.build_analyst_brief()

        self.assertIn(RETURN_REASON_HEADER, text)

    def test_ac1_test_author_brief_opens_with_return_reason_after_escalation_approve(self):
        """approve из escalated возвращает test_author в tests_writing."""
        self.seed_state("tests_writing", "operator",
                        "гейт SPEC пройден — приёмочные тесты до кода")
        self.seed_state("escalated", "fsm", DETAIL_ESCALATED_TEST_AUTHOR)
        self.write_answer(1, "МАРКЕР-ОТВЕТА-TESTAUTHOR")
        self.seed_state("tests_writing", "operator", DETAIL_ESCALATED_APPROVE)

        text = self.build_test_author_brief()

        self.assertIsNotNone(text, f"{TASK}: ANSWER есть — бриф не пуст")
        self.assertIn(RETURN_REASON_HEADER, text)


if __name__ == "__main__":
    unittest.main()
