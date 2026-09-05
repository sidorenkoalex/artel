"""Приёмочные тесты 01M1P9QAG65GVF69YJEV0V18D9 — AC-8, AC-9 (SPEC.md).

## Допущение интерфейса — `orchestrator/zone_lock.py::queue_order`/
`cmd_zone_reorder`

Ни SPEC, ни ТЗ не называют ни структуру данных очереди, ни имя функции,
которая её вычисляет, ни CLI-глагол команды перестановки — все три
решает этот файл (тот же приём допущения интерфейса, что и AC-7, см.
докстринг `_sandbox.py` и `test_ac7_...py`):

- `zone_lock.queue_order(conn, task_ids: list[str]) -> list[str]` — те же
  id, что и на входе, отсортированные по возрастанию времени approve их
  SPEC (AC-8, требование 7 буквально «раньше approve — раньше в
  очереди»). Источник времени approve — выбор разработчика; тест
  фиксирует его для задач, заведённых НАПРЯМУЮ в БД (`ZoneSandbox.
  seed_task`, без прохода через `spec_gate`) через `tasks.updated_at` в
  момент, когда задача встала в очередь, — единственный момент, когда обе
  величины совпадают по построению фикстуры (см. докстринг `_sandbox.py`,
  раздел «Допущения интерфейса», пункт про `queue_order`). Тест лочит
  НАБЛЮДАЕМЫЙ порядок результата, не место хранения времени approve.
- `zone_lock.cmd_zone_reorder(task_ids_in_order: list[str]) -> None` —
  явная команда Оператора (AC-9): после вызова `queue_order` для ТОГО ЖЕ
  множества id возвращает переданный порядок вместо порядка по времени
  approve.
Красен до реализации: `orchestrator/zone_lock.py` не существует —
прогон падает `ModuleNotFoundError: No module named 'orchestrator.
zone_lock'` уже на импорте модуля (skills/test-authoring: «падать на
отсутствующей пока реализации — нормально»), не брак теста.

Обе задачи AC-8 в фикстуре сидятся в `in_dev` с одной и той же зоной,
занятой третьей (`OCCUPIER`) — «заблокированы пересечением ОДНОЙ и той же
зоны» дословно (требование 7); порядок вычисляется как чистая функция от
переданных id, без повторного вывода факта блокировки — `queue_order`
не обязана сама искать, кто чем заблокирован (это уже AC-1..AC-3).
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import ZoneSandbox  # noqa: E402

from orchestrator import store, zone_lock  # noqa: E402

CONFLICT_PATH = "orchestrator/foo_zone.py"
OCCUPIER = "T901"
FIRST = "T910"
SECOND = "T911"
THIRD = "T912"


def _ts(minutes_ago: float) -> str:
    dt = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%fZ")


class Ac8QueueOrderedByApproveTimeTest(ZoneSandbox):
    """AC-8: очередь задач, заблокированных пересечением одной и той же
    зоны, упорядочена по времени approve их SPEC — раньше approve, раньше
    в очереди.

    Ловит мутацию: `queue_order` возвращает id в том порядке, в каком они
    были переданы (или в порядке их появления в БД/id), а не отсортированы
    по времени — фикстура намеренно передаёт id в порядке, ОБРАТНОМ
    времени approve (THIRD, SECOND, FIRST на входе — FIRST, SECOND, THIRD
    на выходе), так что тождественная/произвольная перестановка на входе
    не даёт случайно верный результат.
    """

    def setUp(self):
        super().setUp()
        self.reset_task()
        self.seed_task(OCCUPIER, "Занявшая общую зону", "in_dev", CONFLICT_PATH)
        # approve FIRST раньше всех (90 минут назад), THIRD — позже всех
        # (30 минут назад) — интервалы намеренно большие, чтобы не
        # зависеть от точности хранения времени в конкретной реализации.
        self.seed_task(FIRST, "Первая по approve", "in_dev", CONFLICT_PATH,
                       updated_at=_ts(90))
        self.seed_task(SECOND, "Вторая по approve", "in_dev", CONFLICT_PATH,
                       updated_at=_ts(60))
        self.seed_task(THIRD, "Третья по approve", "in_dev", CONFLICT_PATH,
                       updated_at=_ts(30))

    def test_ac8_queue_order_sorts_ascending_by_approve_time(self):
        order = zone_lock.queue_order(store.db(), [THIRD, SECOND, FIRST])

        self.assertEqual(
            order, [FIRST, SECOND, THIRD],
            f"queue_order не отсортировал задачи по возрастанию времени "
            f"approve их SPEC (раньше approve — раньше в очереди): {order!r}")


class Ac9OperatorReordersQueueTest(ZoneSandbox):
    """AC-9: Оператор может явной командой переставить порядок очереди.

    Ловит мутацию: `cmd_zone_reorder` меняет что-то ещё (например саму
    занятость/блокировку), но не влияет на результат `queue_order` —
    следующий вызов `queue_order` продолжал бы возвращать порядок по
    времени approve, будто команды не было.
    """

    def setUp(self):
        super().setUp()
        self.reset_task()
        self.seed_task(OCCUPIER, "Занявшая общую зону", "in_dev", CONFLICT_PATH)
        self.seed_task(FIRST, "Первая по approve", "in_dev", CONFLICT_PATH,
                       updated_at=_ts(90))
        self.seed_task(SECOND, "Вторая по approve", "in_dev", CONFLICT_PATH,
                       updated_at=_ts(60))
        self.seed_task(THIRD, "Третья по approve", "in_dev", CONFLICT_PATH,
                       updated_at=_ts(30))

    def test_ac9_explicit_reorder_overrides_approve_time_order(self):
        natural = zone_lock.queue_order(store.db(), [FIRST, SECOND, THIRD])
        self.assertEqual(
            natural, [FIRST, SECOND, THIRD],
            f"предусловие теста не выполнено — естественный порядок по "
            f"времени approve не тот, что фикстура ожидает: {natural!r}")

        zone_lock.cmd_zone_reorder([THIRD, FIRST, SECOND])

        reordered = zone_lock.queue_order(store.db(), [FIRST, SECOND, THIRD])
        self.assertEqual(
            reordered, [THIRD, FIRST, SECOND],
            f"queue_order не отразил явную перестановку Оператора "
            f"(cmd_zone_reorder): {reordered!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
