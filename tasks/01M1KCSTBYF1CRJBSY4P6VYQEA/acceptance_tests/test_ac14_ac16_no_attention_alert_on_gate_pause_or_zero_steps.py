"""Приёмочные тесты AC-14..AC-16 — tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/SPEC.md,
требование 3 — три исключения из правила «каждая остановка не на гейте
поднимает алерт»: ручной гейт, штатная пауза, ноль шагов с самого начала
вызова.

Зелёный с рождения: ДА, весь файл. `alerts.KINDS` сегодня не несёт
`"attention"`, а точки остановки `auto.py` вообще не заводят такой
алерт (см. докстрину соседнего файла `test_ac7_ac13_...py`) — значит
`self.open_attention_alerts()` во всех трёх сценариях сегодня пуст ПО
ТОЙ ЖЕ причине, по которой он обязан быть пуст и ПОСЛЕ реализации (это
негативные критерии: «алерта нет»). Тесты уже сегодня проходят, но не
тавтологично: как только разработчик реализует требование 3(а), они
станут содержательной проверкой того, что три исключения не задеты
общим правилом (мутация «алерт заводится безусловно на КАЖДОЙ
остановке» покраснила бы их именно тогда).

Песочница — `_sandbox.StallDetectionSandbox`, тот же приём, что и в
остальных файлах этой задачи.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, pause, runner  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import REAL_CMD_RUN, StallDetectionSandbox  # noqa: E402


class Ac14ManualGateStopRaisesNoAlertTest(StallDetectionSandbox):
    """AC-14: остановка `auto` на ручном гейте (`spec_gate`, `acceptance`,
    `merge_gate`) НЕ поднимает алерт."""

    def test_ac14_stop_on_each_manual_gate_raises_no_alert(self):
        """Три состояния из `docs/design.md §4` — уже сегодня показывают
        «ЖДЁТ ОПЕРАТОРА» в `artel.py status`, SPEC называет их явно
        («Контекст»/требование 3) как штатный исход, не буксование.

        Ловит мутацию: алерт заводится по общему правилу «состояние вне
        `STATE_ROLE`» без исключения для ручных гейтов — тогда каждый
        обычный «жду approve» задачи поднимал бы ложный сигнал
        буксования, обесценивая алерт как индикатор реальной проблемы.
        """
        for state in ("spec_gate", "acceptance", "merge_gate"):
            with self.subTest(состояние=state):
                self.set_state(state)

                self.auto()

                self.assertEqual(
                    self.open_attention_alerts(), [],
                    f"остановка на ручном гейте {state} завела алерт")


class Ac15PauseStopRaisesNoAlertTest(StallDetectionSandbox):
    """AC-15: остановка `auto` штатной паузой Оператора НЕ поднимает
    алерт."""

    def setUp(self):
        super().setUp()
        # `cmd_run` настоящая (тот же довод, что у `AutoStopsOnPauseRefusalTest`
        # в `tests/test_auto_cycle.py`): предмет теста в реакции на
        # реальный отказ по пометке паузы, не на имитацию `SystemExit`.
        self.patch_object(runner, "cmd_run", REAL_CMD_RUN)
        self.write_plan()
        self.set_state("in_dev")
        pause.cmd_pause(self.TASK)

    def test_ac15_pause_refusal_raises_no_alert(self):
        """Пауза — действие самого Оператора (ANSWER-1, вопрос 2): он уже
        знает о причине остановки, алерт был бы уведомлением о
        собственном же решении.

        Ловит мутацию: хук алерта различает причины остановки `run` по
        общему признаку «run отказался стартовать» без исключения именно
        для паузы (`_run_paused_refusal`) — тогда штатная пауза каждый
        раз поднимала бы ложный сигнал буксования.
        """
        with mock.patch.object(runner, "spawn_agent") as popen:
            self.auto()

        popen.assert_not_called()
        self.assertEqual(self.state(), "in_dev")
        self.assertEqual(self.open_attention_alerts(), [])


class Ac16ZeroStepsFromTheStartRaisesNoAlertTest(StallDetectionSandbox):
    """AC-16: вызов `auto`, не выполнивший ни одного шага `run`+`advance`
    за этот вызов, потому что роли не было с самого начала (задача уже в
    `done`/`killed`, либо в `spec_writing` без заведённого `TZ.md`), НЕ
    поднимает алерт."""

    def test_ac16_spec_writing_without_a_tz_raises_no_alert(self):
        """Состояние сразу после `setUp` (задача заведена `catalog.cmd_new`
        БЕЗ `--tz`, см. докстрину `_sandbox.py`) — `spec_writing` без
        `TZ.md`: `runner.step_role` уже сегодня возвращает `None` для
        этого случая (SPEC T025), цикл не делает ни одного шага.

        Ловит мутацию: алерт заводится по признаку «цикл встал вне
        `STATE_ROLE`» без различения «роли не было с самого начала» —
        тогда КАЖДЫЙ вызов `auto` на ещё не заведённой аналитиком задаче
        поднимал бы ложный сигнал буксования, хотя `auto` даже не
        пытался ничего сделать (SPEC требование 3, тот же довод, что и у
        ручного гейта).
        """
        self.auto()

        self.assertEqual(self.agent.calls, [])
        self.assertEqual(self.open_attention_alerts(), [])

    def test_ac16_terminal_states_raise_no_alert(self):
        """`done`/`killed` — тоже «роли не было с самого начала»: задача
        уже завершена, `auto` не находит для неё агентской работы вовсе.

        Ловит мутацию: та же, что у соседнего теста, но со стороны
        терминальных состояний, а не спецификации без ТЗ — оба случая
        SPEC перечисляет вместе, одной причиной исключения.
        """
        for state in ("done", "killed"):
            with self.subTest(состояние=state):
                self.set_state(state)

                self.auto()

                self.assertEqual(
                    self.open_attention_alerts(), [],
                    f"вызов auto из терминального состояния {state} "
                    f"завёл алерт")


if __name__ == "__main__":
    unittest.main()
