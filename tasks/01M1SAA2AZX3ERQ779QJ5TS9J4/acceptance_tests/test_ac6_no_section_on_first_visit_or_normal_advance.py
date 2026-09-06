"""AC-6 (tasks/01M1SAA2AZX3ERQ779QJ5TS9J4/SPEC.md): для визита
состояния, не начавшегося возвратом (первый визит состояния или
обычный advance из штатного предшествующего состояния), раздел
«Причина возврата» отсутствует, остальной текст брифа не меняется
относительно текущего поведения.

Зелёный с рождения: сегодняшний `brief.py` никогда не добавляет раздел
«Причина возврата» — этот файл фиксирует ту же регрессию, которую до
этой задачи уже покрывают `tests/test_brief.py::DeveloperBriefTest`/
`AnalystMapComponentTest` (собирают ровно три/один компонент), только
явно проговаривая случай «история журнала есть, но это НЕ возврат» —
после реализации раздел обязан по-прежнему не появляться здесь, иначе
эти тесты покраснеют и станут единственным сигналом того, что новый
код перепутал «advance» с «reject/changes_requested»."""
import unittest

from _sandbox import (  # noqa: E402
    BriefSandbox, DETAIL_NORMAL_SPEC_GATE_TO_TESTS_WRITING,
    DETAIL_NORMAL_TESTS_WRITING_DONE, RETURN_REASON_HEADER)


class Ac6NoSectionTest(BriefSandbox):
    """Ловит мутацию: реализация решает «это возврат» по одному лишь
    факту существования прошлой записи `state -> review`/`state ->
    tests_writing` где-то в истории задачи (вместо того, чтобы смотреть,
    ИЗ какого состояния пришла ПОСЛЕДНЯЯ запись `state -> <текущее>`) —
    тогда штатный advance после честного прохождения tests_writing/
    spec_gate ошибочно получил бы раздел «Причина возврата»."""

    def test_ac6_developer_brief_unchanged_after_normal_advance_from_tests_writing(self):
        self.seed_state("tests_writing", "operator",
                        "гейт SPEC пройден — приёмочные тесты до кода")
        self.seed_state("in_dev", "fsm", DETAIL_NORMAL_TESTS_WRITING_DONE)

        text = self.build_developer_brief()

        self.assertNotIn(RETURN_REASON_HEADER, text)
        self.assertIn("Маркер-текста-SPEC.", text)
        self.assertIn("Маркер-текста-карты.", text)

    def test_ac6_developer_brief_unchanged_after_normal_advance_from_spec_gate_skip_tests(self):
        self.seed_state("in_dev", "operator",
                        "тесты пропущены (skip_tests): стенд недоступен")

        text = self.build_developer_brief()

        self.assertNotIn(RETURN_REASON_HEADER, text)
        self.assertIn("Маркер-текста-SPEC.", text)

    def test_ac6_analyst_brief_unchanged_on_first_visit_no_journal_at_all(self):
        """Первый визит spec_writing — задача рождается там напрямую
        (`insert_task`), записи `state -> spec_writing` не бывает никогда
        (`store.refusal_history`, докстринг): журнал пуст."""
        text = self.build_analyst_brief()

        self.assertNotIn(RETURN_REASON_HEADER, text)
        self.assertIn("Маркер-текста-карты.", text)

    def test_ac6_test_author_brief_unchanged_after_normal_advance_from_spec_gate(self):
        self.seed_state("tests_writing", "operator",
                        DETAIL_NORMAL_SPEC_GATE_TO_TESTS_WRITING)

        text = self.build_test_author_brief()

        self.assertIsNone(
            text, "ANSWER ещё не было — добавка брифа test_author пуста, "
            "как и до этой задачи")


if __name__ == "__main__":
    unittest.main()
