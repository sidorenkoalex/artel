"""AC-5 — 01M3GKJ84XM5QPC6TK5EE307Q9: строка `in_dev` новой добавки не
получает, а существующий суффикс ожидания зоны печатается как прежде.

Источник — SPEC.md, «Критерии приёмки»:

AC-5. Строка `status` задачи в `in_dev` добавки «зона занята» не
получает, а существующий суффикс ожидания зоны по
`zone_lock.blocking_conflict` (держатель, позиция очереди, минуты
ожидания) печатается в точности как до задачи.

Ожидаемый текст суффикса выписан здесь ЛИТЕРАЛОМ, а не вызовом
`catalog._zone_wait_suffix` (это была бы тавтология — та же функция по
обе стороны ассерта): литерал списан с сегодняшнего поведения
(`orchestrator/catalog.py::_zone_wait_suffix`), и именно он обязан
пережить задачу. Очередь и минуты в нём отсутствуют намеренно —
сегодняшний код печатает очередь только при более чем одном конкуренте,
а минуты — только внутри цикла `auto --wait-zone`; сценарий не заводит
ни того, ни другого.

Зелёный с рождения: оба метода фиксируют СЕГОДНЯШНИЙ вывод `status` для
задачи в `in_dev` — сегодня «зона занята» не печатается ни в одной
строке, а суффикс ожидания зоны печатается ровно так, как сверяется
ниже; тест краснеет тогда, когда правка требования 3 тронет строку
`in_dev`, которую трогать не велено.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402

HOLDER = "T850"
WAITER = "T851"
SHARED_ZONE = "orchestrator/fsm.py"

#: Сегодняшний суффикс ожидания зоны (`catalog._zone_wait_suffix`) —
#: держатель без очереди и без минут ожидания.
EXPECTED_SUFFIX = f"  [ждёт зоны {SHARED_ZONE}: занята {HOLDER} (in_dev)]"


class InDevRowKeepsZoneWaitSuffixTest(_sandbox.ZoneOverlapSandbox):

    def setUp(self):
        super().setUp()
        self.seed_task(HOLDER, "in_dev", SHARED_ZONE, occupying=True)
        self.seed_task(WAITER, "in_dev", SHARED_ZONE)

    def test_ac5_in_dev_row_does_not_get_the_zone_taken_mark(self):
        """Задача в `in_dev`, ждущая занятую зону, получает СТАРЫЙ
        суффикс ожидания и не получает новой добавки «зона занята».

        Ловит мутацию: новая пометка добавлена в `cmd_status` без
        ограничения состояния (или её условие написано как «не в
        BLOCKING_STATES») — строка `in_dev` понесла бы обе пометки разом,
        и Оператор читал бы про один и тот же конфликт дважды.
        """
        line = self.status_lines().get(WAITER, "")

        self.assertNotIn(
            _sandbox.ZONE_TAKEN_PREFIX, line,
            f"строка задачи в in_dev не должна нести добавку "
            f"«{_sandbox.ZONE_TAKEN_PREFIX}…»: {line!r}")

    def test_ac5_existing_zone_wait_suffix_is_printed_verbatim(self):
        """Тот же вывод несёт существующий суффикс ожидания зоны
        буквально: «[ждёт зоны <путь>: занята <id> (<состояние>)]».

        Ловит мутацию: правка переписывает `_zone_wait_suffix` под общую
        с новой пометкой формулировку (скажем, «зона занята: T850») —
        текст, на который смотрят Оператор и существующие тесты
        `tests/test_zone_lock.py`, изменился бы молча.
        """
        line = self.status_lines().get(WAITER, "")

        self.assertIn(
            EXPECTED_SUFFIX, line,
            f"существующий суффикс ожидания зоны обязан печататься "
            f"неизменным: ожидалось {EXPECTED_SUFFIX!r}, строка {line!r}")


if __name__ == "__main__":
    unittest.main()
