"""Приёмочные тесты AC-3..AC-6 — tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/SPEC.md,
требование 2 («Порог холостых шагов»).

ВЫБОР ИМЕНИ КОНСТАНТЫ (см. также `_sandbox.py`): SPEC AC-3 требует «новую
именованную константу config.py со значением по умолчанию 5», но не
называет её. Эти тесты фиксируют имя `config.AUTO_STALL_STEPS_LIMIT` —
разработчик обязан назвать константу так же байт-в-байт, иначе тесты не
соберутся (`AttributeError`), а не просто не пройдут содержательно.

Красен до реализации: ДА, весь файл — `orchestrator/auto.py` сегодня не
считает холостые шаги вовсе (только стоп-кран требования 1 по ПОВТОРУ
ОДИНАКОВОГО отказа) и `config.py` не несёт константы `AUTO_STALL_STEPS_
LIMIT`. AC-3 падает `AttributeError` при обращении к атрибуту; AC-4..AC-6 —
`AttributeError` там же (сценарии сами используют константу, чтобы не
завязываться на литерал 5, см. скил test-authoring, «Красный тест до
реализации... предпосылки о значениях конфигурации пиши динамически») —
до того, как цикл вообще успел бы не остановиться по не существующей пока
причине.

Песочница — `_sandbox.StallDetectionSandbox`/`FakeAdvance`, тем же приёмом,
что и у AC-1/AC-2 (файл test_ac1_ac2_stop_crane_action_class.py).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, fsm  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DRAFT_PLAN_MD, FakeAdvance, StallDetectionSandbox  # noqa: E402


class Ac3ThresholdConstantExistsTest(unittest.TestCase):
    """AC-3: `config.py` несёт новую именованную константу порога холостых
    шагов со значением по умолчанию 5."""

    def test_ac3_constant_defaults_to_five(self):
        """Ловит мутацию: константа заведена, но с другим значением по
        умолчанию (например, скопирован `AUTO_MAX_STEPS=30`) — SPEC
        требование 2 прямо называет дефолт 5."""
        self.assertEqual(config.AUTO_STALL_STEPS_LIMIT, 5)


class Ac4IdleStepsStopTheCycleTest(StallDetectionSandbox):
    """AC-4: N шагов run+advance подряд без смены состояния — независимо
    от того, журналировал ли advance отказ на каждом из них и с каким
    классом, — останавливают цикл с сообщением «цикл не сходится: N шагов
    без перехода, последний отказ: <класс>», где <класс> — action записи,
    журналированной на последнем из N шагов."""

    def setUp(self):
        super().setUp()
        self.write_plan()
        self.set_state("in_dev")
        self.advance = FakeAdvance()
        self.patch_object(fsm, "cmd_advance", self.advance)

    def test_ac4_n_idle_steps_with_distinct_refusal_classes_stop_with_the_last_one_named(self):
        """N шагов подряд без перехода, на каждом — СВОЙ, отличный от
        соседей, класс отказа (не пара повторов — чтобы точно не задеть
        стоп-кран требования 1, который сработал бы раньше и по другой
        причине). Итоговое сообщение обязано назвать класс ИМЕННО
        последнего из N шагов, не первого и не какого-то произвольного.

        Ловит мутацию: сообщение подставляет `action` ПЕРВОГО отказа серии
        (или любого, кроме последнего) — с различными классами на каждом
        шаге тест отличит это от правильной реализации по тексту хвоста.
        Также ловит мутацию «порог не считается вовсе» (цикл откручивает
        все `AUTO_MAX_STEPS` шагов вместо остановки на N-м) — при
        `AUTO_MAX_STEPS > N` число вызовов `advance` разошлось бы.
        """
        n = config.AUTO_STALL_STEPS_LIMIT
        actions = [f"переход отклонён: класс {i}" for i in range(n)]
        self.advance.script = list(actions)

        out = self.auto()

        self.assertEqual(
            self.advance.calls, n,
            f"цикл не остановился ровно на {n}-м холостом шаге")
        self.assertEqual(self.state(), "in_dev", "состояние сдвинулось")
        expected = (f"цикл не сходится: {n} шагов без перехода, "
                    f"последний отказ: {actions[-1]}")
        self.assertIn(expected, out)


class Ac5LastStepWithoutAJournalledRefusalDropsTheTailTest(StallDetectionSandbox):
    """AC-5: последний из N шагов не журналировал отказ (агент ещё
    работал) — сообщение остановки требования 2 без хвоста «, последний
    отказ: <класс>»."""

    def setUp(self):
        super().setUp()
        self.write_plan()
        self.set_state("in_dev")
        self.advance = FakeAdvance()
        self.patch_object(fsm, "cmd_advance", self.advance)

    def test_ac5_message_has_no_tail_when_the_last_of_n_steps_journalled_nothing(self):
        """N-1 шагов с разными журналированными классами отказа, N-й —
        без записи вовсе (`advance.script` кончается на `None`
        имплицитно — `FakeAdvance` без запланированного элемента ничего не
        журналирует, тот же по смыслу исход, что «агент ещё работает»,
        SPEC требование 4).

        Ловит мутацию: хвост подставляется всегда, если класс отказа
        встречался хоть на КАКОМ-то из N шагов (не обязательно последнем)
        — тогда сообщение содержало бы «, последний отказ:» вопреки тому,
        что именно последний шаг ничего не журналировал.
        """
        n = config.AUTO_STALL_STEPS_LIMIT
        self.advance.script = [f"переход отклонён: класс {i}"
                               for i in range(n - 1)]  # n-й шаг — без записи

        out = self.auto()

        self.assertEqual(self.advance.calls, n)
        expected = f"цикл не сходится: {n} шагов без перехода"
        self.assertIn(expected, out)
        self.assertNotIn(", последний отказ:", out)


class Ac6StateChangeResetsTheIdleCounterTest(StallDetectionSandbox):
    """AC-6: успешная смена состояния задачи сбрасывает счётчик холостых
    шагов на 0 (в т.ч. если смена случилась раньше, чем накопилось N
    шагов)."""

    def setUp(self):
        super().setUp()
        # Черновик (не ready): реальный `advance` из `in_dev` молча отвечает
        # «не готово» и НЕ трогает состояние сам — единственный источник
        # смены состояния в этом сценарии обязан быть скрипт агента (см.
        # докстринг теста ниже).
        self.write_plan(DRAFT_PLAN_MD)
        self.set_state("in_dev")

    def test_ac6_a_transition_one_step_before_the_threshold_resets_the_count(self):
        """(N-1) холостых шагов, затем шаг, где САМ агент двигает
        состояние (`in_dev` -> `review`, тем же приёмом, что escalation-
        тесты `tests/test_auto_cycle.py` двигают состояние из скрипта
        агента), затем ещё (N-1) холостых. Без сброса счётчика суммарно
        холостых шагов ((N-1)+(N-1) >= N при N>=2) с запасом хватило бы,
        чтобы стоп сработал уже во ВТОРОМ холостом блоке — тест проверяет,
        что этого не происходит и цикл доходит до штатного лимита шагов.

        `advance` здесь настоящий (не подменён): и `in_dev` без ready
        PLAN.md, и `review` без REVIEW.md одинаково молча отвечают «не
        готово», не журналируя отказ (тот же путь, что уже использует
        `tests/test_auto_cycle.py::AutoStepLimitTest` с черновым PLAN.md)
        — держит сценарий сфокусированным ровно на подсчёте холостых
        шагов, без побочного участия стоп-крана требования 1.

        Ловит мутацию: счётчик холостых шагов не сбрасывается сменой
        состояния (растёт монотонно весь вызов) — тогда цикл остановился
        бы порогом требования 2 внутри второго холостого блока, до
        `AUTO_MAX_STEPS`, и итоговое сообщение называло бы «цикл не
        сходится», а не лимит шагов.
        """
        n = config.AUTO_STALL_STEPS_LIMIT
        self.agent.script = (
            [lambda: None] * (n - 1)
            + [lambda: self.set_state("review")]
            + [lambda: None] * (n - 1)
        )

        out = self.auto()

        self.assertEqual(
            len(self.agent.calls), config.AUTO_MAX_STEPS,
            "цикл не должен был остановиться раньше штатного лимита шагов — "
            "смена состояния обязана была сбросить счётчик холостых шагов")
        self.assertIn(f"лимит {config.AUTO_MAX_STEPS} шагов", out)
        self.assertNotIn("цикл не сходится", out)


if __name__ == "__main__":
    unittest.main()
