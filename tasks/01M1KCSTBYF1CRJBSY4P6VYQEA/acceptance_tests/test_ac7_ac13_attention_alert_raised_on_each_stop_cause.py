"""Приёмочные тесты AC-7..AC-13 — tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/SPEC.md,
требование 3(а): каждая перечисленная причина остановки `auto` не на
ручном гейте поднимает алерт `kind=attention` с id задачи и причиной в
тексте. Список ТЗ — примеры, не потолок (SPEC «Контекст»); каждый AC
здесь — один класс причины из явного перечня требования 3.

Красен до реализации: ДА, весь файл. Сегодня `alerts.KINDS ==
("incident", "threshold", "trigger")` — `"attention"` там нет, и ни одна
из точек остановки `auto.py` не заводит алерт вовсе; `self.
open_attention_alerts()` (см. `_sandbox.py`) во всех сценариях этого
файла вернёт пустой список ДО реализации требования 3(а) — тесты падают
на `assertEqual(len(...), 1)` (получат 0), не на исключении: сама
проверка причины остановки (стоп-кран, эскалация, лимит шагов, гейт
ёмкости, гейт CI, отказ run, отказ guard'а) — уже сегодня рабочий, не
новый код, поэтому падать может только сравнение количества алертов.

Песочница — `_sandbox.StallDetectionSandbox` (тот же приём, что у
AC-1/AC-2/AC-3..AC-6, файлы `test_ac1_ac2_stop_crane_action_class.py` /
`test_ac3_ac6_idle_step_threshold.py`).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import ci, config, fsm, parallel_limit, runner  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import (DRAFT_PLAN_MD, REAL_CMD_RUN, FakeAdvance,  # noqa: E402
                      StallDetectionSandbox)


class Ac7EscalationRaisesAnAttentionAlertTest(StallDetectionSandbox):
    """AC-7: остановка `auto` переходом задачи в `escalated` (любой
    причины, включая исчерпанный бюджет) поднимает алерт `kind=attention`
    с id задачи и причиной остановки в тексте."""

    def setUp(self):
        super().setUp()
        self.write_plan()
        self.set_state("in_dev")

    def test_ac7_escalation_of_an_arbitrary_cause_raises_an_attention_alert(self):
        """Агент сам роняет задачу в `escalated` посреди шага (упавший
        агент, вердикт ревьювера и т.п. — причина, не связанная с
        потолком бюджета) — цикл встаёт, не пытаясь двигать `escalated`
        дальше (auto никогда не проходит гейт), и заводит алерт.

        Ловит мутацию: алерт заводится только для КОНКРЕТНОЙ причины
        эскалации (например, только для потолка бюджета — см. соседний
        тест) — тогда этот, «безбюджетный», сценарий остался бы без
        алерта, хотя SPEC прямо требует «любой причины».
        """
        self.agent.script = [lambda: self.set_state("escalated")]

        self.auto()

        self.assertEqual(self.state(), "escalated")
        opened = self.open_attention_alerts()
        self.assertEqual(len(opened), 1, f"открытых алертов: {len(opened)}")
        self.assertIn(self.TASK, opened[0]["message"])

    def test_ac7_escalation_by_exhausted_budget_raises_an_attention_alert(self):
        """Эскалация по исчерпанному потолку бюджета (`auto_stop_advice`
        подменяет причину на `AUTO_STOP_BUDGET` отдельной веткой) — SPEC
        называет этот случай явно («включая исчерпанный бюджет»).

        Ловит мутацию: хук алерта висит на одной причине эскалации мимо
        ветки потолка бюджета (`budget.budget_block` внутри `auto_stop_
        advice`) — тогда именно этот, явно названный SPEC случай, остался
        бы без алерта.
        """
        self.set_state("in_dev", budget_usd=25.0, spent_usd=0.0)
        self.agent.script = [lambda: self.set_state("escalated", spent_usd=26.0)]

        self.auto()

        self.assertEqual(self.state(), "escalated")
        self.assertEqual(len(self.open_attention_alerts()), 1)


class Ac8StopCraneRaisesAnAttentionAlertTest(StallDetectionSandbox):
    """AC-8: остановка `auto` стоп-краном требования 1 (T038) поднимает
    алерт `kind=attention` с id задачи и причиной."""

    def setUp(self):
        super().setUp()
        self.write_plan()
        self.set_state("in_dev")
        self.advance = FakeAdvance()
        self.patch_object(fsm, "cmd_advance", self.advance)

    def test_ac8_stop_crane_stop_raises_an_attention_alert(self):
        """Ловит мутацию: алерт заводится в общей точке остановки, но
        стоп-кран возвращает раньше неё (например, отдельным `return` до
        вызова точки алерта) — тогда именно этот, самый старый стоп цикла
        (T038), остался бы без алерта, хотя он ЕСТЬ остановка `auto` не
        на ручном гейте."""
        action = "переход отклонён: гейт ёмкости diff"
        self.advance.script = [
            (action, "деталь 1"),
            (action, "деталь 2"),
        ]

        self.auto()

        self.assertEqual(self.state(), "in_dev")
        self.assertEqual(len(self.open_attention_alerts()), 1)


class Ac9IdleThresholdStopRaisesAnAttentionAlertTest(StallDetectionSandbox):
    """AC-9: остановка `auto` порогом холостых шагов требования 2
    поднимает алерт `kind=attention` с id задачи и причиной."""

    def setUp(self):
        super().setUp()
        self.write_plan(DRAFT_PLAN_MD)
        self.set_state("in_dev")

    def test_ac9_idle_step_threshold_stop_raises_an_attention_alert(self):
        """PLAN.md не ready — каждый шаг холостой, ни одного журналируемого
        отказа (тот же по устройству сценарий, что и AC-4/AC-5 в
        `test_ac3_ac6_idle_step_threshold.py`).

        Ловит мутацию: алерт заводится только для стоп-крана требования 1
        (AC-8), а не для НОВОГО порога холостых шагов требования 2 — эти
        два стоп-условия независимы (AC-2 показывает, что стоп-кран НЕ
        срабатывает на разных классах отказа), и SPEC требует алерта на
        обоих.
        """
        self.auto()

        self.assertEqual(self.state(), "in_dev")
        self.assertEqual(len(self.open_attention_alerts()), 1)


class Ac10StepLimitExhaustedRaisesAnAttentionAlertTest(StallDetectionSandbox):
    """AC-10: остановка `auto` исчерпанным лимитом `AUTO_MAX_STEPS`
    поднимает алерт `kind=attention` с id задачи и причиной."""

    def setUp(self):
        super().setUp()
        self.write_plan(DRAFT_PLAN_MD)
        self.set_state("in_dev")

    def test_ac10_auto_max_steps_exhausted_raises_an_attention_alert(self):
        """Ловит мутацию: алерт хука висит только на «именованных»
        остановках (эскалация/стоп-кран/холостые), забыв про
        общий лимит шагов вызова — самую старую остановку `auto`
        (SPEC T014), которая тоже «остановка не на ручном гейте».
        """
        self.agent.script = self.idle_with_periodic_transitions(
            config.AUTO_MAX_STEPS, config.AUTO_STALL_STEPS_LIMIT)

        out = self.auto()

        self.assertEqual(len(self.agent.calls), config.AUTO_MAX_STEPS)
        self.assertIn(f"лимит {config.AUTO_MAX_STEPS} шагов", out)
        self.assertNotIn("цикл не сходится", out,
                         "сценарий должен был дойти до лимита шагов, а не "
                         "до порога холостых требования 2")
        self.assertEqual(len(self.open_attention_alerts()), 1)


class Ac11VerifyingRedCiStopRaisesAnAttentionAlertTest(StallDetectionSandbox):
    """AC-11: остановка `auto` красным CI в `verifying` поднимает алерт
    `kind=attention` с id задачи и причиной."""

    def setUp(self):
        super().setUp()
        self.patch_object(
            ci, "verifying_status",
            lambda branch: (ci.VERIFYING_RED,
                            "CI коммита aaaaaaaa не зелёный: guard=failure"))
        self.set_state("verifying")

    def test_ac11_red_ci_in_verifying_raises_an_attention_alert(self):
        """Ловит мутацию: алерт заводится в общей точке `auto_stop`, но
        опрос CI (`_advance_verifying_poll`) печатает и возвращает `True`
        МИМО этой точки — тогда именно этот стоп (единственный, что сам
        решает остановиться до `AUTO_MAX_STEPS` без похода через общий
        `auto_stop` требований 1-2) остался бы без алерта.
        """
        self.auto()

        self.assertEqual(self.state(), "verifying")
        self.assertEqual(len(self.open_attention_alerts()), 1)


class Ac12BudgetBeforeStepStartRaisesAnAttentionAlertTest(StallDetectionSandbox):
    """AC-12 (первая ветка): отказ `run` стартовать по исчерпанному
    потолку бюджета ДО начала шага — НЕ пауза, поднимает алерт."""

    def setUp(self):
        super().setUp()
        self.patch_object(runner, "cmd_run", REAL_CMD_RUN)
        self.write_plan()
        self.set_state("in_dev", budget_usd=1.0, spent_usd=1.0)

    def test_ac12_budget_exhausted_before_the_step_starts_raises_an_attention_alert(self):
        """`cmd_run` настоящая (см. `tests/test_auto_cycle.py::
        AutoStopsOnBudgetRefusalTest` — тот же довод: имитация отказа
        доказывала бы только умение теста бросить `SystemExit`).

        Ловит мутацию: алерт заводится только для отказа по паузе (общая
        причина спутана с ней) либо только внутри цикла шагов, минуя ветку
        `except SystemExit` — тогда САМЫЙ частый, по инцидентам 02-03.09,
        класс тихой остановки (`run` отказался стартовать) остался бы без
        алерта.
        """
        with mock.patch.object(runner, "spawn_agent") as popen:
            self.auto()

        popen.assert_not_called()
        self.assertEqual(self.state(), "in_dev")
        self.assertEqual(len(self.open_attention_alerts()), 1)


class Ac12ParallelTaskLimitRefusalRaisesAnAttentionAlertTest(StallDetectionSandbox):
    """AC-12 (вторая ветка): отказ `run` стартовать по лимиту
    параллельных задач — НЕ пауза, поднимает алерт."""

    def setUp(self):
        super().setUp()
        self.patch_object(runner, "cmd_run", REAL_CMD_RUN)
        self.write_plan()
        self.set_state("in_dev")

    def test_ac12_parallel_task_limit_refusal_raises_an_attention_alert(self):
        """`parallel_limit.refusal` подменена прямо (не через настоящие
        lease других задач) — предмет теста в реакции `auto` на отказ, не
        в устройстве самого лимитера (у него свои тесты).

        Ловит мутацию: алерт хука сравнивает текст причины буквально с
        «бюджет исчерпан» (или другим частным случаем) вместо общего
        правила «run отказался стартовать не по паузе» — тогда этот,
        второй явно названный SPEC пример, остался бы без алерта.
        """
        self.patch_object(
            parallel_limit, "refusal",
            lambda conn, task_id: (
                f"[{task_id}] лимит параллельных задач достигнут: "
                f"тестовая заглушка"))

        with mock.patch.object(runner, "spawn_agent") as popen:
            self.auto()

        popen.assert_not_called()
        self.assertEqual(self.state(), "in_dev")
        self.assertEqual(len(self.open_attention_alerts()), 1)


class Ac13GuardRefusalRaisesAnAttentionAlertTest(StallDetectionSandbox):
    """AC-13: остановка `auto` структурным отказом `guard`'ом
    артефакта-условия поднимает алерт `kind=attention` с id задачи и
    причиной."""

    def setUp(self):
        super().setUp()
        self.write_plan()
        self.set_state("in_dev")

    def test_ac13_artifact_guard_refusal_raises_an_attention_alert(self):
        """`fsm.cmd_advance` подменена так, чтобы вернуть `True` — тот же
        по значению исход, что и у настоящего guard'а, отклонившего
        структуру артефакта (SPEC T038, требование 3): тот же приём, что
        `tasks/T034/acceptance_tests/test_auto_guard_refusal.py`.

        Ловит мутацию: хук алерта расположен только на ветке требования 1
        (сравнение `action`/`refusal`), которая при отказе guard'ом даже
        не достигается (`auto.py` возвращает раньше неё) — тогда САМАЯ
        первая по времени добавления остановка цикла (SPEC T034) осталась
        бы без алерта.
        """
        self.patch_object(fsm, "cmd_advance",
                          lambda task_id, session_id=None: True)

        self.auto()

        self.assertEqual(self.state(), "in_dev")
        self.assertEqual(len(self.open_attention_alerts()), 1)


if __name__ == "__main__":
    unittest.main()
