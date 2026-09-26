"""Приёмочные тесты 01M3EM7A84KE0W690M02VWPNXF — AC-1, AC-2: набор
состояний, при которых эскалация по неразрешённому конфликту содержимого
подтяжки метит задачу записью `pull.PULL_CONFLICT_ROLE_STEP_MARKER`, —
ровно `in_dev`, `acceptance`, `merge_gate`, и ни одного состояния сверх
них.

Красен до реализации: сегодня метка пишется единственной ветвью `if state
== "in_dev"` (`orchestrator/pull.py::_handle_merge_failure`, ~стр. 266) —
для `acceptance` и `merge_gate` записи с action
`pull.PULL_CONFLICT_ROLE_STEP_MARKER` в журнале нет вовсе, оба
соответствующих теста падают на `assertEqual(len(marker_rows), 1)`. Тест
`in_dev` и тест AC-2 (состояние вне трёх) зелены уже сегодня — это лок
существующего поведения, которое требование 2 обязано сохранить (метка
только для трёх состояний, ни одним больше).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (CONFLICT_FILE, ESCALATION_ACTION,  # noqa: E402
                      PullConflictSandbox)


class MarkerIsWrittenForEveryStateThatReturnsToInDevTest(PullConflictSandbox):
    """AC-1: в каждом из трёх состояний, из которых возврат из эскалации
    ведёт в `in_dev` (`escalated_from` эскалация подтяжки не пишет —
    «Контекст» SPEC), конфликт подтяжки обязан оставить в журнале запись
    метки с тем же `detail`, что и запись самой эскалации."""

    def assert_marker_matches_escalation(self, state: str) -> None:
        """Общая сверка для всех трёх состояний: задача эскалирована,
        метка ровно одна, её `detail` совпадает с `detail` записи
        эскалации (по нему Оператор читает, ЧЕМ помечена задача)."""
        outcome = self.escalate_via_pull_conflict(state)

        self.assertEqual(outcome, "escalated",
                         f"неразрешённый конфликт подтяжки из {state} обязан "
                         f"эскалировать — сценарий не воспроизведён")
        self.assertEqual(self.state(), "escalated")
        escalations = self.escalation_rows()
        self.assertEqual(len(escalations), 1,
                         f"ожидалась одна запись {ESCALATION_ACTION}")
        markers = self.marker_rows()
        self.assertEqual(
            len(markers), 1,
            f"конфликт подтяжки из состояния {state} не пометил задачу "
            f"признаком «нужен шаг роли до следующего предварительного "
            f"advance» — записи метки в журнале нет")
        self.assertEqual(
            markers[0]["detail"], escalations[0]["detail"],
            f"detail метки из состояния {state} не совпал с detail записи "
            f"эскалации")
        self.assertIn(CONFLICT_FILE, markers[0]["detail"],
                      "detail обязан остаться тем же текстом конфликта, что "
                      "и у эскалации (конфликтные файлы + вывод git merge)")

    def test_ac1_marker_is_written_when_the_conflict_escalates_in_dev(self):
        """Конфликт подтяжки при задаче в `in_dev` метит её записью
        `pull.PULL_CONFLICT_ROLE_STEP_MARKER` с `detail` эскалации.

        Ловит мутацию: расширяя условие на три состояния, разработчик
        подменяет набор (например, пишет `if state in ("acceptance",
        "merge_gate")`) и теряет уже работающий случай `in_dev` —
        `assertEqual(len(markers), 1)` это поймает.
        """
        self.assert_marker_matches_escalation("in_dev")

    def test_ac1_marker_is_written_when_the_conflict_escalates_acceptance(self):
        """Тот же конфликт подтяжки при задаче в `acceptance` (подтяжку
        там зовёт `fsm._approve_acceptance`) обязан оставить такую же
        запись метки с `detail` эскалации.

        Ловит мутацию: условие записи метки осталось `if state ==
        "in_dev"` (или расширено только на `merge_gate` — случай из
        копилки 21.09 разобран, «симметричный» случай приёмки забыт) —
        записи метки в журнале не появится, и `assertEqual(len(markers),
        1)` это поймает.
        """
        self.assert_marker_matches_escalation("acceptance")

    def test_ac1_marker_is_written_when_the_conflict_escalates_merge_gate(self):
        """Тот же конфликт подтяжки при задаче в `merge_gate` (подтяжку
        там зовёт `fsm_merge_gate._sync_main_or_wait`) обязан оставить
        такую же запись метки с `detail` эскалации — живой случай 21.09.

        Ловит мутацию: условие записи метки осталось `if state ==
        "in_dev"`, либо метка пишется со своим собственным `detail`
        (пустым, либо `note` без префикса «конфликт подтяжки … в
        ветку …») — `assertEqual(len(markers), 1)`/`assertEqual` по
        `detail` это поймают.
        """
        self.assert_marker_matches_escalation("merge_gate")


class MarkerIsNotWrittenOutsideTheThreeStatesTest(PullConflictSandbox):
    """AC-2: состояние вне трёх метки не получает — метится только то, из
    чего возврат из эскалации действительно ведёт в `in_dev` (требование
    2); сама эскалация при этом происходит как прежде."""

    OUTSIDE_STATE = "review"

    def test_ac2_no_marker_for_a_state_outside_the_three(self):
        """Тот же неразрешённый конфликт подтяжки при задаче в состоянии
        вне набора (`review`) обязан эскалировать её ровно как прежде —
        но записи метки в журнале не оставить.

        Ловит мутацию: условие записи метки снято целиком (метка пишется
        на ЛЮБОЙ эскалации конфликта подтяжки, `store.journal` вынесен
        из-под `if`) — в журнале появится запись метки для `review`, и
        `assertEqual(len(markers), 0)` это поймает; `assertEqual` по
        состоянию и `detail` эскалации поймает обратную мутацию —
        сужение самой эскалации вместе с меткой.
        """
        outcome = self.escalate_via_pull_conflict(self.OUTSIDE_STATE)

        self.assertEqual(outcome, "escalated",
                         "эскалация конфликта подтяжки обязана произойти как "
                         "прежде, независимо от состояния")
        self.assertEqual(self.state(), "escalated")
        escalations = self.escalation_rows()
        self.assertEqual(len(escalations), 1)
        self.assertIn(CONFLICT_FILE, escalations[0]["detail"],
                      "detail эскалации обязан остаться прежним текстом "
                      "конфликта подтяжки")
        self.assertEqual(
            len(self.marker_rows()), 0,
            f"состояние {self.OUTSIDE_STATE} вне набора «возврат ведёт в "
            f"in_dev» получило метку конфликта подтяжки")


if __name__ == "__main__":
    import unittest
    unittest.main()
