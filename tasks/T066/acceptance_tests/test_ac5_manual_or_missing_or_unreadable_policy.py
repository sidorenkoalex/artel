"""AC-5 (tasks/T066/SPEC.md): при политике гейта acceptance=`manual`,
либо отсутствии секции политики в `gates.yaml`, либо нечитаемом
`gates.yaml` — поведение перехода `review -> acceptance` не получает
автогейт-эффекта: задача останавливается в `acceptance` и ждёт
Оператора, без единого следа автогейта в журнале.

Маршрут обновлён под T079/ADR-0009 (мандат ANSWER-1 T085, 01.09):
байт-в-байт совпадение с детaлью ОДНОШАГОВОГО перехода `review ->
acceptance` (`detail="ревью пройдено — приёмка Оператором (по критериям
SPEC)"`) сегодня недостижимо в принципе — T079 (независимо от этой
задачи) вставил между `review` и `acceptance` состояние `verifying`,
и именно оно, а не старая ветка "approved", теперь пишет запись `state
-> acceptance` (деталь — статус CI, `orchestrator/ci.py::
verifying_status`). Инвариант AC-5 по существу — «эта политика не даёт
автогейту никакого эффекта» — проверяется тем, что имеет значение:
задача доходит до `acceptance` (через `verifying`, см.
`_sandbox.py::advance_to_autogate`) и ни одна запись журнала не несёт
`actor=autogate`.

Все сценарии построены на ИНАЧЕ ПОЛНОСТЬЮ ЗЕЛЁНОМ прогоне
(`prepare_scenario()` без переопределений — все условия SPEC требования
2 выполнены), кроме самой политики/файла `gates.yaml`: расхождение с
AC-1 обязано объясняться только политикой, не случайно подвернувшимся
красным условием.

Зелёный с рождения: сегодня `gates.yaml` не читается вовсе (см.
докстринг `_sandbox.py`) — переход `review -> ... -> acceptance` уже
безусловно останавливается в `acceptance` без автогейт-следа в журнале,
при любом содержимом/отсутствии `gates.yaml`. Это ровно то поведение,
которое AC-5 обязывает сохранить: тест зелёный уже сегодня (после
починки маршрута под T079) и обязан остаться зелёным после кода задачи
T066 (регрессионный якорь, не новая проверка).
"""
import unittest

from _sandbox import (GATES_ACCEPTANCE_MANUAL, GATES_NO_POLICY_SECTION,  # noqa: E402
                      GATES_UNREADABLE, AutogateSandbox)


class _UnchangedBehaviorMixin:

    def assert_stops_in_acceptance_unchanged(self) -> None:
        self.assertEqual(
            self.state(), "acceptance",
            "AC-5: переход обязан остановиться в acceptance, как и до "
            "этой задачи")
        rows = [r for r in self.journal_rows()
               if r[0] == "fsm" and r[1] == "state -> acceptance"]
        self.assertTrue(rows, f"журнал: {self.journal_rows()}")
        autogate_rows = [r for r in self.journal_rows() if r[0] == "autogate"]
        self.assertEqual(
            autogate_rows, [],
            f"AC-5: автогейт не имеет права оставить след в журнале при "
            f"этой политике: {autogate_rows}")


class ManualPolicyUnchangedTest(_UnchangedBehaviorMixin, AutogateSandbox):

    def test_ac5_manual_policy_stays_in_acceptance_unchanged(self):
        self.prepare_scenario(gates_content=GATES_ACCEPTANCE_MANUAL)

        self.advance_to_autogate()

        self.assert_stops_in_acceptance_unchanged()


class MissingPolicySectionUnchangedTest(_UnchangedBehaviorMixin, AutogateSandbox):

    def test_ac5_missing_policy_section_stays_in_acceptance_unchanged(self):
        self.prepare_scenario(gates_content=GATES_NO_POLICY_SECTION)

        self.advance_to_autogate()

        self.assert_stops_in_acceptance_unchanged()


class UnreadableGatesYamlUnchangedTest(_UnchangedBehaviorMixin, AutogateSandbox):

    def test_ac5_unreadable_gates_yaml_stays_in_acceptance_unchanged(self):
        self.prepare_scenario(gates_content=GATES_UNREADABLE)

        self.advance_to_autogate()

        self.assert_stops_in_acceptance_unchanged()


class MissingGatesYamlFileUnchangedTest(_UnchangedBehaviorMixin, AutogateSandbox):
    """Требование 1 трактует ОТСУТСТВИЕ секции политики как manual;
    отсутствие самого файла — тот же fail-closed случай (`gates.yaml`
    «не читается»/не найден — AC-4/AC-5 перечисляют его тем же классом
    отказа, что и нечитаемый файл)."""

    def test_ac5_no_gates_yaml_file_at_all_stays_in_acceptance_unchanged(self):
        self.prepare_scenario()
        (self.root / "gates.yaml").unlink()

        self.advance_to_autogate()

        self.assert_stops_in_acceptance_unchanged()


if __name__ == "__main__":
    unittest.main()
