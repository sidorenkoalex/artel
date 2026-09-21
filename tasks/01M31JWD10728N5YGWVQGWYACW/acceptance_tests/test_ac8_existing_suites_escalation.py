"""Приёмочные тесты 01M31JWD10728N5YGWVQGWYACW — AC-8: четыре существующих
модуля `tests/` (`test_artifact_escalation_marker.py`,
`test_auto_escalated_return_rework_gate.py`, `test_fsm_review_rework_gate.py`,
`test_fsm_review_rework_sha_gate.py`) остаются зелёными по итогам задачи, и
ни одна из их сегодняшних проверок не исчезает молча.

Решение Оператора (`ANSWER-1.md`, вопросы 1 и 2): AC-8 читается как «файлы
зелёные ПО ИТОГАМ задачи», а один тест первого модуля —
`MarkerWrittenByTheEscalationPointsTest::
test_review_escalation_does_not_journal_the_marker`
(`tests/test_artifact_escalation_marker.py:341-356`) — закрепляет прежнее
ошибочное решение SPEC 01M2XFSJ1Z7BS6HR69SAT1D81Y («случай review
невоспроизводим») и прямо противоречит AC-1. Разработчик ПЕРЕПИСЫВАЕТ его
под новое ожидание, имя метода становится ровно
`test_review_escalation_journals_the_marker`; старое имя из перечня «не
исчезли» исключено, новое — требуется.

Красен до реализации: метода `test_review_escalation_journals_the_marker` в
`tests/test_artifact_escalation_marker.py` сегодня нет (там стоит его
предшественник с обратным ожиданием) — сверка перечня в
`test_ac8_marker_suite_stays_green_with_the_review_expectation_rewritten`
падает на `missing`. Тот же метод покраснел бы и вторым способом: с уже
внесённой правкой `_review_escalate`, но НЕ переписанным ожиданием прогон
модуля даёт `1 failed` ровно на этом тесте. Остальные три модуля зелены и
сейчас — их метод фиксирует СОХРАНЕНИЕ поведения (ADR-0002, принцип
целостности: чинить задачу ослаблением существующих проверок нельзя).

Перечни имён ниже — снимок модулей на момент написания планки: добавление
НОВЫХ тестов критерий не запрещает (сверка на включение, не на равенство).
В частности, ANSWER-1 прямо разрешает разработчику завести отдельный новый
тест на «эскалация по бюджету из `review` маркера НЕ пишет» — ту половину
переписываемого теста, которая правкой не отменяется; имени у него нет, и
перечень его не требует (само свойство кроет AC-5 планки).
"""
import importlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

MARKER_MODULE = "tests.test_artifact_escalation_marker"

# Имя, которым, по решению Оператора (ANSWER-1, вопрос 1), разработчик
# называет переписанное ожидание эскалации ревьювера. Планка опирается
# именно на имя: другого способа отличить «тест переписан» от «тест
# удалён» у прогона нет — оба дают зелёный модуль.
REWRITTEN_REVIEW_CHECK = "test_review_escalation_journals_the_marker"

MARKER_EXISTING_CHECKS = frozenset({
    # RoleStepRequiredMarkerTest — чтение маркера рубежом
    "test_return_after_the_marker_blocks_until_the_role_step",
    "test_role_step_after_the_marked_return_unblocks",
    "test_first_spec_writing_visit_return_after_the_marker_is_an_anchor",
    "test_return_without_a_marker_is_still_skipped",
    "test_marker_is_consumed_by_the_first_return",
    "test_marker_is_reset_by_another_state_transition",
    "test_escalated_transition_between_marker_and_return_keeps_it",
    # MarkerWrittenByTheEscalationPointsTest — запись маркера точками
    # эскалации; `test_review_escalation_does_not_journal_the_marker`
    # исключён сознательно (ANSWER-1, вопрос 2) — он и есть
    # переписываемое ожидание.
    "test_tests_writing_escalation_journals_the_marker_after_the_transition",
    "test_spec_writing_escalation_by_a_batch_journals_the_same_marker",
    "test_spec_writing_disk_path_journals_the_marker_too",
})

# Три модуля, которых правка не касается вовсе: их ожидания обязаны
# дожить до конца задачи нетронутыми.
UNTOUCHED_SUITES = {
    "tests.test_auto_escalated_return_rework_gate": frozenset({
        "test_no_entry_at_all_degrades_to_true",
        "test_review_return_without_a_developer_step_blocks",
        "test_developer_step_after_the_review_return_unblocks",
        "test_escalated_return_after_the_developer_step_does_not_hide_it",
        "test_budget_escalated_return_detail_is_ignored_the_same_way",
        "test_escalated_return_with_no_developer_step_still_blocks",
        "test_developer_step_after_the_escalated_return_unblocks",
        "test_legit_first_entry_detail_still_degrades_to_true",
        "test_only_an_escalated_return_entry_is_the_degenerate_case",
        "test_spec_gate_return_without_an_analyst_step_blocks",
        "test_analyst_step_after_the_spec_gate_return_unblocks",
    }),
    "tests.test_fsm_review_rework_gate": frozenset({
        "test_uses_the_freshest_reviewer_step_autocommit",
        "test_developer_ledger_edit_commit_is_not_a_candidate",
        "test_no_matching_commit_falls_back_to_the_journal_entry",
        "test_git_not_answering_falls_back_to_the_journal_entry",
        "test_neither_commit_nor_journal_entry_gives_none",
        "test_journal_entry_of_a_different_role_is_not_picked",
        "test_falls_back_to_last_review_md_commit_and_still_refuses",
        "test_degenerate_no_state_entry_journal_signal_does_not_override_git",
    }),
    "tests.test_fsm_review_rework_sha_gate": frozenset({
        "test_no_escalation_record_returns_none",
        "test_escalation_record_after_the_reviewer_run_is_used",
        "test_stale_escalation_record_before_a_newer_reviewer_run_is_ignored",
        "test_only_the_latest_escalation_record_counts",
        "test_no_escalation_record_passes",
        "test_unchanged_sha_passes",
        "test_changed_sha_refuses",
        "test_git_not_answering_now_passes_fail_open",
        "test_stale_escalation_record_passes",
    }),
}


def _flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten(item)
        else:
            yield item


class ExistingEscalationSuitesStayGreenTest(unittest.TestCase):

    def load(self, module_name: str):
        """Набор тестов модуля и множество имён его тестовых методов."""
        module = importlib.import_module(module_name)
        suite = unittest.TestLoader().loadTestsFromModule(module)
        names = {test.id().rsplit(".", 1)[-1] for test in _flatten(suite)}
        return suite, names

    def assert_suite_is_green(self, module_name: str, suite) -> None:
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
        self.assertTrue(
            result.wasSuccessful(),
            f"{module_name} не зелёный после правки:\n{stream.getvalue()}")

    def test_ac8_marker_suite_stays_green_with_the_review_expectation_rewritten(self):
        """`tests/test_artifact_escalation_marker.py` по итогам задачи
        загружается и проходит целиком; все его проверки, кроме
        переписываемого ожидания эскалации ревьювера, на месте, а само
        ожидание присутствует под новым именем
        `test_review_escalation_journals_the_marker`.

        Ловит мутацию: разработчик не переписывает покрасневшее ожидание,
        а УДАЛЯЕТ его (самый дешёвый способ вернуть модуль в зелёное —
        ADR-0002 запрещает ровно это) — прогон модуля станет зелёным, но
        требуемого имени в наборе не появится, и `assertIn` ниже упадёт.
        Вторая мутация того же теста: маркер эскалации ревьювера пишется
        не тем `action`/не на том месте, что у `spec_writing`/
        `tests_writing` — переписанное ожидание в модуле покраснеет, и
        это покажет прогон.
        """
        suite, names = self.load(MARKER_MODULE)

        missing = sorted(MARKER_EXISTING_CHECKS - names)
        self.assertEqual(
            missing, [],
            f"из {MARKER_MODULE} исчезли проверки: {missing} — удаление "
            f"существующего теста не способ выполнения задачи")
        self.assertIn(
            REWRITTEN_REVIEW_CHECK, names,
            f"в {MARKER_MODULE} нет метода {REWRITTEN_REVIEW_CHECK}: "
            f"прежнее ожидание эскалации ревьювера не переписано под "
            f"AC-1, а удалено или оставлено под старым именем "
            f"(решение Оператора — ANSWER-1, вопрос 1)")

        self.assert_suite_is_green(MARKER_MODULE, suite)

    def test_ac8_untouched_rework_gate_suites_stay_green(self):
        """Три модуля рубежа переделки, которых правка не касается
        (`test_auto_escalated_return_rework_gate.py`,
        `test_fsm_review_rework_gate.py`,
        `test_fsm_review_rework_sha_gate.py`), остаются зелёными, и ни
        одна их проверка не исчезает.

        Ловит мутацию: обязательный шаг роли добивается не маркером, а
        «в лоб» — из `auto._role_step_since_state_entry` убран пропуск
        `_ESCALATED_RETURN_DETAILS`, и анкером становится ЛЮБАЯ запись
        возврата из `escalated`; тогда
        `test_escalated_return_after_the_developer_step_does_not_hide_it`
        и `test_budget_escalated_return_detail_is_ignored_the_same_way`
        краснеют на прогоне, а попытка вместо этого их вычеркнуть
        ловится сверкой перечня.
        """
        for module_name, expected in sorted(UNTOUCHED_SUITES.items()):
            with self.subTest(module=module_name):
                suite, names = self.load(module_name)

                missing = sorted(expected - names)
                self.assertEqual(
                    missing, [],
                    f"из {module_name} исчезли проверки: {missing} — "
                    f"удаление существующего теста не способ выполнения "
                    f"задачи")

                self.assert_suite_is_green(module_name, suite)


if __name__ == "__main__":
    unittest.main()
