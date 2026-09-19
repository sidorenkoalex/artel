"""Приёмочные тесты AC-5/AC-6 задачи 01M2XFSNVGWA2VX5XFEYR93Y4Z: защита
от кружения (ровно один гарантированный шаг роли) и неизменность
поведения отказа гейта зон БЕЗ мандата.

Красен до реализации: `test_ac5_repeat_after_a_developer_step_stops_the_cycle`
добывает имя действия у настоящего гейта и падает на предпосылке AC-1
(сегодня это обычное «переход отклонён: гейт зон»). Зелёный с рождения —
`test_ac6_refusal_without_a_mandate_stops_without_running_the_role`: он
фиксирует сегодняшнее поведение стоп-крана «два подряд одинаковых
отказа», которое AC-6 требует сохранить.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import auto, fsm, runner  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (OLD_ZONES_REFUSAL_ACTION,  # noqa: E402
                      OUT_OF_ZONE_PATH, JournalingAdvance, ScriptedRun,
                      ZonesMandateSandbox)


class _AutoCycleSandbox(ZonesMandateSandbox):
    """`auto.cmd_auto` поверх сценария планки: `fsm.cmd_advance` заменён
    на журналирование отказа, добытого у НАСТОЯЩЕГО гейта, `runner.cmd_run`
    — на шаг роли без агента. Предмет обоих критериев — цикл, а не
    механика прогона агента."""

    ROLE_STEP_LIMIT = 3

    def setUp(self):
        super().setUp()
        self.commit_out_of_zone_file()
        self.commit_plan(extension_paths=None)

    def arm_cycle(self) -> tuple[JournalingAdvance, ScriptedRun]:
        """Прогоняет настоящий гейт (чтобы взять его собственные action/
        detail), чистит журнал и заводит задачу в `in_dev` с нуля."""
        refuses, _out = self.run_zones_gate()
        self.assertTrue(refuses, "гейт зон обязан отказать в этом сценарии")
        action, detail = self.refusals()[-1]
        self.clear_journal()
        self.enter_in_dev()
        advance = JournalingAdvance(action, detail)
        run = ScriptedRun(limit=self.ROLE_STEP_LIMIT)
        self.advance, self.run = advance, run
        self.refusal_action = action
        return advance, run

    def run_auto(self) -> str:
        with mock.patch.object(fsm, "cmd_advance", self.advance), \
             mock.patch.object(runner, "cmd_run", self.run):
            return self.capture(auto.cmd_auto, self.TASK)


class Ac5OneGuaranteedStepThenStopTest(_AutoCycleSandbox):
    """AC-5."""

    def setUp(self):
        super().setUp()
        self.commit_mandate(OUT_OF_ZONE_PATH)

    def test_ac5_repeat_after_a_developer_step_stops_the_cycle(self):
        """Отказ «мандат есть, раздел PLAN не оформлен» повторился ПОСЛЕ
        шага developer (раздел так и не оформлен) — цикл останавливается,
        отдав роли РОВНО ОДИН шаг: задача остаётся в `in_dev`, итог
        Оператору назван.

        Ловит мутацию: новое действие безусловно отнесено к классу «роль
        ещё не закончила» без всякого счётчика — цикл жёг бы шаги роли до
        самого `config.AUTO_MAX_STEPS` (потолок вызовов `ScriptedRun`
        валит тест немедленно), то есть менял бы час простоя на 30
        оплаченных прогонов developer по кругу.
        """
        self.arm_cycle()
        self.assertNotEqual(
            self.refusal_action, OLD_ZONES_REFUSAL_ACTION,
            "гейт зон ещё не различает причину отказа (AC-1) — проверять "
            "защиту от кружения нечем")

        out = self.run_auto()

        self.assertEqual(
            len(self.run.calls), 1,
            f"роли обещан РОВНО один гарантированный шаг, сделано "
            f"{len(self.run.calls)}")
        self.assertEqual(self.state(), "in_dev")
        self.assertIn("auto остановлен", out)
        self.assertIn(self.refusal_action, out)


class Ac6RefusalWithoutMandateIsUnchangedTest(_AutoCycleSandbox):
    """AC-6: мандата нет — поведение цикла как до задачи."""

    def test_ac6_refusal_without_a_mandate_stops_without_running_the_role(self):
        """Два подряд одинаковых отказа гейта зон БЕЗ мандата в `in_dev`
        останавливают цикл, не запустив роль ни разу, с сегодняшней
        подсказкой «почини причину и повтори artel.py advance <id>».

        Ловит мутацию: класс «роль ещё не закончила» распространён на
        ЛЮБОЙ отказ гейта зон (а не только на новый, подкреплённый
        мандатом) — задача без мандата Оператора начала бы гонять
        developer по пути, который никто не разрешал, вместо решения
        Оператора.
        """
        advance, run = self.arm_cycle()
        self.assertEqual(
            self.refusal_action, OLD_ZONES_REFUSAL_ACTION,
            "без мандата гейт зон обязан журналировать прежнее действие")

        out = self.run_auto()

        self.assertEqual(run.calls, [],
                         "роль не должна запускаться ни разу (AC-6)")
        self.assertEqual(advance.calls, 2,
                         "стоп-кран обязан сработать на ВТОРОМ отказе")
        self.assertEqual(self.state(), "in_dev")
        self.assertIn("auto остановлен", out)
        self.assertIn(f"почини причину и повтори artel.py advance {self.TASK}",
                      out)


if __name__ == "__main__":
    unittest.main()
