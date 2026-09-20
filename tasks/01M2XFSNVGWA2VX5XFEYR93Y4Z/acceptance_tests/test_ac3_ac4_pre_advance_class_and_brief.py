"""Приёмочные тесты AC-3/AC-4 задачи 01M2XFSNVGWA2VX5XFEYR93Y4Z:
`auto._pre_advance_step` относит отказ «мандат есть, раздел PLAN не
оформлен» к классу «роль ещё не закончила» (шаг developer запускается), а
история отказов брифа несёт это действие с путями мандата.

Красен до реализации: имя действия добывается прогоном настоящего гейта
(`_sandbox.ZonesMandateSandbox.run_zones_gate`), а он сегодня журналирует
для сценария «мандат есть, раздела PLAN нет» обычное «переход отклонён:
гейт зон» — `assertNotEqual` предпосылки падает в
`test_ac3_repeated_refusal_without_a_role_step_still_runs_developer` и
`test_ac4_refusal_history_carries_the_action_and_the_mandate_paths` ещё
до предмета самих критериев. Зелёный с рождения —
`test_ac4_brief_role_not_finished_list_is_not_extended`: он фиксирует
сегодняшнее содержимое `brief._ROLE_NOT_FINISHED_REFUSAL_ACTIONS`,
которое AC-4 требует НЕ менять.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import auto, brief, fsm  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (OLD_ZONES_REFUSAL_ACTION,  # noqa: E402
                      OUT_OF_ZONE_PATH, JournalingAdvance,
                      ZonesMandateSandbox, refusal_history_text)

# Сегодняшнее содержимое `orchestrator/brief.py::
# _ROLE_NOT_FINISHED_REFUSAL_ACTIONS` — AC-4 требует, чтобы `brief.py` не
# менялся; из всего модуля именно этот перечень определяет, попадёт ли
# новое действие в блок «почини это» брифа.
BRIEF_ROLE_NOT_FINISHED_TODAY = (
    "переход отклонён: замечания ревью не отработаны",
    "переход отклонён: дерево не на ветке задачи",
)


class _MandateRefusalInDevSandbox(ZonesMandateSandbox):
    """Сценарий инцидента 13.09: мандат выдан, путь вне зон закоммичен,
    PLAN.md без раздела «## Расширение зон», задача в `in_dev` ПОСЛЕ уже
    отработавшего шага developer (в инциденте — шаг, закончившийся в
    10:13:20)."""

    def setUp(self):
        super().setUp()
        self.commit_mandate(OUT_OF_ZONE_PATH)
        self.commit_out_of_zone_file()
        self.commit_plan(extension_paths=None)
        self.enter_in_dev()
        self.journal_role_step("developer")
        refuses, self.gate_out = self.run_zones_gate()
        self.assertTrue(refuses, "гейт зон обязан отказать в этом сценарии")
        self.refusal_action, self.refusal_detail = self.refusals()[-1]

    def assert_named_refusal(self) -> None:
        """Предпосылка обоих критериев: отказ уже назван своим действием
        (AC-1). Без неё AC-3/AC-4 нечего различать."""
        self.assertNotEqual(
            self.refusal_action, OLD_ZONES_REFUSAL_ACTION,
            "гейт зон ещё не различает причину отказа (AC-1) — ни класс "
            "отказа в auto, ни его попадание в бриф проверить не на чем")


class Ac3PreAdvanceRunsDeveloperTest(_MandateRefusalInDevSandbox):
    """AC-3."""

    def test_ac3_repeated_refusal_without_a_role_step_still_runs_developer(self):
        """Два подряд вызова `auto._pre_advance_step` в `in_dev` с одним и
        тем же отказом действия AC-1, БЕЗ завершённого шага роли между
        ними, оба возвращают `None` — то есть цикл на обеих итерациях
        запускает шаг developer, а не останавливается решением Оператора.

        Ловит мутацию: новое действие не внесено в перечень класса
        «роль ещё не закончила» (`auto.ROLE_NOT_FINISHED_REFUSAL_ACTIONS`
        или эквивалент) — тогда первый вызов вернёт `Refused`, второй
        (тот же текст в `cycle.prev_refusal`) — `Stop`, и developer не
        получит ни одного шага, ровно как 13.09.

        Ловит и вторую мутацию: «был ли шаг роли» проверяется общим
        `_role_step_since_state_entry` (шаг developer в этом сценарии уже
        был — ДО первого отказа) вместо «шаг между двумя отказами» —
        тогда второй вызов ошибочно ушёл бы в `Stop`.
        """
        self.assert_named_refusal()
        advance = JournalingAdvance(self.refusal_action, self.refusal_detail)
        cycle = auto._CycleState()

        with mock.patch.object(fsm, "cmd_advance", advance):
            first = auto._pre_advance_step(self.conn, self.TASK, "sid",
                                           "developer", "in_dev", "in_dev",
                                           cycle)
            second = auto._pre_advance_step(self.conn, self.TASK, "sid",
                                            "developer", "in_dev", "in_dev",
                                            cycle)

        self.assertEqual(advance.calls, 2)
        self.assertIsNone(
            first, f"первый отказ увёл цикл мимо шага developer: {first!r}")
        self.assertIsNone(
            second, f"повтор того же отказа без промежуточного шага роли "
                    f"остановил цикл: {second!r}")


class Ac4RefusalHistoryReachesTheBriefTest(_MandateRefusalInDevSandbox):
    """AC-4."""

    def test_ac4_refusal_history_carries_the_action_and_the_mandate_paths(self):
        """Блок «история отказов advance», который `orchestrator/brief.py`
        кладёт в бриф шага developer в `in_dev`, несёт новое действие и
        перечисленные в его тексте пути мандата.

        Ловит мутацию: новое действие внесено в
        `brief._ROLE_NOT_FINISHED_REFUSAL_ACTIONS` заодно с перечнем
        `auto.py` — блок отфильтруется и вернётся пустой строкой, роль
        запустится вслепую, не узнав, чего от неё ждут (та же слепота,
        что и при остановке цикла).
        """
        self.assert_named_refusal()

        text = refusal_history_text(self.conn, self.TASK, "developer", "in_dev")

        self.assertTrue(text, "история отказов advance пуста — бриф шага "
                              "developer не получит причину отказа")
        self.assertIn(self.refusal_action, text)
        self.assertIn(OUT_OF_ZONE_PATH, text,
                      f"пути мандата не доехали до брифа: {text!r}")

    def test_ac4_brief_role_not_finished_list_is_not_extended(self):
        """`orchestrator/brief.py` не изменён в той единственной своей
        части, которая решает судьбу нового действия в брифе, — перечень
        `_ROLE_NOT_FINISHED_REFUSAL_ACTIONS` остаётся прежней парой.

        Ловит мутацию: перечень `brief.py` синхронизируют с перечнем
        `auto.py` «за компанию» — тест выше стал бы красным по причине,
        которую легко списать на песочницу, а здесь она названа прямо.
        """
        self.assertEqual(brief._ROLE_NOT_FINISHED_REFUSAL_ACTIONS,
                         BRIEF_ROLE_NOT_FINISHED_TODAY)


if __name__ == "__main__":
    unittest.main()
