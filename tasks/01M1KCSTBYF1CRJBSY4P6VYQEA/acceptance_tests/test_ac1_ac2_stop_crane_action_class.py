"""Приёмочные тесты AC-1, AC-2 — tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/SPEC.md.

Красен до реализации: НЕТ — обе проверки уже сегодня зелёные на существующем
коде (`orchestrator/auto.py::_advance_refusal` возвращает `row["action"]`, не
полную запись с `detail`, и цикл сравнивает `refusal == prev_refusal` именно
по этим строкам) — SPEC прямо называет это регрессом, фиксируемым тестами, а
не новым поведением («Контекст»: «Требование 1 ниже фиксирует это тестами
как регресс-гарантию»; «T038 не ослабляется и не переписывается»). AC-1 при
этом — НЕ дубликат существующего `tests/test_auto_cycle.py::
AutoStopsOnRepeatedAdvanceRefusalTest.test_ac1_identical_refusal_twice_in_a_
row_stops_the_cycle`: тот фиксирует ОДИНАКОВЫЙ `action` при ОДИНАКОВОМ
(тестовом) `detail`, тогда как здесь `detail` на двух шагах намеренно
РАЗНЫЙ — ровно та ситуация, которая в проде отличает «гейт ёмкости diff
120 КиБ» от «гейт ёмкости diff 340 КиБ» на одном и том же классе отказа
(SPEC «Контекст»).

Песочница — `_sandbox.StallDetectionSandbox`/`FakeAdvance` (тот же приём,
что у tasks/T038/acceptance_tests/.../FakeAdvance, расширенный парой
`(action, detail)` — этой задаче нужен разный `detail` при одинаковом
`action`).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, fsm  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import FakeAdvance, StallDetectionSandbox  # noqa: E402


class Ac1SameActionDifferentDetailStopsTheCycleTest(StallDetectionSandbox):
    """AC-1: два подряд отказа с ОДИНАКОВЫМ `action`, но РАЗНЫМ `detail`
    (разный размер diff в байтах), останавливают цикл на втором из них —
    тем же образом, что и буквально идентичный отказ."""

    def setUp(self):
        super().setUp()
        self.write_plan()
        self.set_state("in_dev")
        self.advance = FakeAdvance()
        self.patch_object(fsm, "cmd_advance", self.advance)

    def test_ac1_two_refusals_of_the_same_class_and_different_detail_stop_the_cycle(self):
        """Разыгрывает гейт ёмкости diff дважды подряд: оба раза `action`
        — «переход отклонён: гейт ёмкости diff», но `detail` называет
        РАЗНЫЙ размер (120 512 и 340 118 байт) — так же, как разные
        прогоны одного и того же гейта в проде.

        Ловит мутацию: сравнение отказов по полной записи журнала
        (`action` И `detail` вместе) вместо одного только `action` —
        тогда разный `detail` замаскировал бы совпадение класса, стоп-кран
        не сработал бы на втором шаге, и цикл докрутился бы до
        `config.AUTO_MAX_STEPS`.
        """
        action = "переход отклонён: гейт ёмкости diff"
        self.advance.script = [
            (action, "полный diff снимка 120512 байт превышает потолок"),
            (action, "полный diff снимка 340118 байт превышает потолок"),
        ]

        out = self.auto()

        self.assertEqual(
            self.advance.calls, 2,
            "цикл не остановился на втором подряд отказе того же класса — "
            "разный `detail` не должен был это замаскировать")
        self.assertEqual(self.state(), "in_dev")
        self.assertIn("auto остановлен", out)
        self.assertIn(action, out)
        self.assertIn(f"почини причину и повтори artel.py advance {self.TASK}",
                      out)

    def test_ac1_stop_reason_names_the_shared_action_not_either_detail(self):
        """Причина остановки в журнале — текст `action` (класс отказа), а
        не один из двух разных `detail`, которые сам класс не переживают.

        Ловит мутацию: остановка печатает/журналирует `detail` последнего
        отказа вместо `action` — тогда сообщение разошлось бы с образцом
        T038 (стоп-кран называет КЛАСС отказа, не переменную часть).
        """
        action = "переход отклонён: лок приёмочных тестов"
        self.advance.script = [
            (action, "acceptance_tests/ изменены после лока (sha aaaa1111)"),
            (action, "acceptance_tests/ изменены после лока (sha bbbb2222)"),
        ]

        self.auto()

        detail = self.journal_detail("auto остановлен")
        self.assertIn(action, detail)


class Ac2DifferentActionClassesDoNotStopTheCycleTest(StallDetectionSandbox):
    """AC-2: два подряд отказа `advance` с РАЗНЫМ `action` не
    останавливают цикл по стоп-крану требования 1."""

    def setUp(self):
        super().setUp()
        self.write_plan()
        self.set_state("in_dev")
        self.advance = FakeAdvance()
        self.patch_object(fsm, "cmd_advance", self.advance)

    def test_ac2_two_different_refusal_classes_in_a_row_do_not_stop_the_cycle(self):
        """Два подряд отказа разных классов (гейт ёмкости diff, затем лок
        приёмочных тестов) — стоп-кран требования 1 их не останавливает,
        цикл проходит дальше второго шага без его подсказки.

        Утверждение — намеренно не «цикл идёт до `AUTO_MAX_STEPS`»: с этой
        же задачи независимо действует порог холостых шагов требования 2
        (AC-4/AC-9), который на полностью холостом продолжении сценария
        (без дальнейших отказов) может остановить цикл раньше — это его
        законная территория, не предмет AC-2. Предмет AC-2 — ровно то, что
        СТОП-КРАН (переиспользованный текст-подсказка «почини причину и
        повтори») здесь не сработал и не отрезал цикл сразу после второго
        шага.

        Ловит мутацию: сравнение отказов по общему префиксу «переход
        отклонён» вместо полного `action` — тогда два разных класса,
        начинающихся одинаково, ложно сочлись бы за один и тот же класс,
        и цикл остановился бы на втором шаге с этой же подсказкой.
        """
        self.advance.script = [
            "переход отклонён: гейт ёмкости diff",
            "переход отклонён: лок приёмочных тестов",
        ]

        out = self.auto()

        self.assertGreater(
            self.advance.calls, 2,
            "стоп-кран остановил цикл сразу после пары разных классов отказа")
        self.assertNotIn(
            f"почини причину и повтори artel.py advance {self.TASK}", out)


if __name__ == "__main__":
    unittest.main()
