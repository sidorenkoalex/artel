"""AC-5 (tasks/T066/SPEC.md): при политике гейта acceptance=`manual`,
либо отсутствии секции политики в `gates.yaml`, либо нечитаемом
`gates.yaml` — поведение перехода `review -> acceptance` байт-в-байт
совпадает с сегодняшним: задача останавливается в `acceptance` и ждёт
Оператора, без автогейта.

«Байт-в-байт» здесь проверяется буквальным текстом детали существующей
записи журнала перехода (`orchestrator/fsm.py`, ветка `status ==
"approved"` состояния `review`: `detail="ревью пройдено — приёмка
Оператором (по критериям SPEC)"`) — та же строка, что и до этой задачи;
её появление без изменений и есть доказательство, что сработал СТАРЫЙ
код, а не новая автогейт-ветка.

Все сценарии построены на ИНАЧЕ ПОЛНОСТЬЮ ЗЕЛЁНОМ прогоне
(`prepare_scenario()` без переопределений — все условия SPEC требования
2 выполнены), кроме самой политики/файла `gates.yaml`: расхождение с
AC-1 обязано объясняться только политикой, не случайно подвернувшимся
красным условием.

Зелёный с рождения: сегодня `gates.yaml` не читается вовсе (см.
докстринг `_sandbox.py`) — переход `review -> acceptance` уже
безусловно останавливается в `acceptance` этой самой строкой журнала,
при любом содержимом/отсутствии `gates.yaml`. Это ровно то поведение,
которое AC-5 обязывает сохранить: тест зелёный уже сегодня и обязан
остаться зелёным после кода задачи (регрессионный якорь, не новая
проверка).
"""
import unittest

from _sandbox import (GATES_ACCEPTANCE_MANUAL, GATES_NO_POLICY_SECTION,  # noqa: E402
                      GATES_UNREADABLE, AutogateSandbox)
from orchestrator import fsm  # noqa: E402

UNCHANGED_DETAIL = "ревью пройдено — приёмка Оператором (по критериям SPEC)"


class _UnchangedBehaviorMixin:

    def assert_stops_in_acceptance_unchanged(self) -> None:
        self.assertEqual(
            self.state(), "acceptance",
            "AC-5: переход обязан остановиться в acceptance, как и до "
            "этой задачи")
        rows = [r for r in self.journal_rows()
               if r[0] == "fsm" and r[1] == "state -> acceptance"]
        self.assertTrue(rows, f"журнал: {self.journal_rows()}")
        self.assertEqual(
            rows[-1][2], UNCHANGED_DETAIL,
            "AC-5: деталь перехода обязана быть байт-в-байт прежней — "
            "сработал старый код, не автогейт-ветка")
        autogate_rows = [r for r in self.journal_rows() if r[0] == "autogate"]
        self.assertEqual(
            autogate_rows, [],
            f"AC-5: автогейт не имеет права оставить след в журнале при "
            f"этой политике: {autogate_rows}")


class ManualPolicyUnchangedTest(_UnchangedBehaviorMixin, AutogateSandbox):

    def test_ac5_manual_policy_stays_in_acceptance_unchanged(self):
        self.prepare_scenario(gates_content=GATES_ACCEPTANCE_MANUAL)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assert_stops_in_acceptance_unchanged()


class MissingPolicySectionUnchangedTest(_UnchangedBehaviorMixin, AutogateSandbox):

    def test_ac5_missing_policy_section_stays_in_acceptance_unchanged(self):
        self.prepare_scenario(gates_content=GATES_NO_POLICY_SECTION)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assert_stops_in_acceptance_unchanged()


class UnreadableGatesYamlUnchangedTest(_UnchangedBehaviorMixin, AutogateSandbox):

    def test_ac5_unreadable_gates_yaml_stays_in_acceptance_unchanged(self):
        self.prepare_scenario(gates_content=GATES_UNREADABLE)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assert_stops_in_acceptance_unchanged()


class MissingGatesYamlFileUnchangedTest(_UnchangedBehaviorMixin, AutogateSandbox):
    """Требование 1 трактует ОТСУТСТВИЕ секции политики как manual;
    отсутствие самого файла — тот же fail-closed случай (`gates.yaml`
    «не читается»/не найден — AC-4/AC-5 перечисляют его тем же классом
    отказа, что и нечитаемый файл)."""

    def test_ac5_no_gates_yaml_file_at_all_stays_in_acceptance_unchanged(self):
        self.prepare_scenario()
        (self.root / "gates.yaml").unlink()

        self.capture(fsm.cmd_advance, self.TASK)

        self.assert_stops_in_acceptance_unchanged()


if __name__ == "__main__":
    unittest.main()
