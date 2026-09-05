"""AC-5 (01M1REVJ8AJDKAMK5VTKES5J6D) — `zone_lock.queue_order`,
`zone_lock.cmd_zone_reorder`, `zone_lock.queue_position` ведут себя как в
частях 1-3 (сортировка по approve-маркеру/явной перестановке,
ранжирование среди конкурентов по конкретной зоне) — эта задача их не
меняет, только условие занятости внутри `blocking_conflict`, от которого
`queue_position` зависит косвенно.

Зелёный с рождения: `queue_order`/`cmd_zone_reorder` — чистые функции от
переданных id и `tasks.zone_queue_position`/маркера approve
(`_approve_marker_id`), их код эта задача не трогает вовсе (SPEC,
требование 3) — фикстура ниже уже проходит на сегодняшнем `zone_lock.py`.
Тест зафиксирован как приёмочная планка на случай, если разработчик,
чиня AC-1..AC-3 внутри `blocking_conflict`, случайно заденет и эту часть
модуля.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import ZoneMechanicsSandbox  # noqa: E402

from orchestrator import zone_lock  # noqa: E402
from orchestrator import store  # noqa: E402


class Ac5Test(ZoneMechanicsSandbox):

    def test_ac5_queue_order_and_position_stay_correct_alongside_the_new_occupancy_rule(self):
        """Владелец (стартовавший код) и два ждущих соседа делят зону
        a/b — владелец не входит в очередь ожидания (его собственная
        `blocking_conflict` возвращает `None`, он не «ждёт»), а два
        соседа ранжируются по возрастанию момента approve их SPEC, как и
        в частях 1-3; явная операторская перестановка (`cmd_zone_reorder`)
        по-прежнему имеет приоритет над этим порядком.

        Ловит мутацию: `queue_position`/`queue_order` начинают сами
        проверять `"agent run started"` кандидатов (вместо того, чтобы
        полагаться на уже исправленный `blocking_conflict`) и по ошибке
        причисляют владельца к конкурентам («он тоже в `in_dev`») —
        `total` вырос бы с 2 до 3, а `position` соседей сместился бы;
        либо `cmd_zone_reorder` перестаёт побеждать естественный порядок
        approve после правки, затронувшей соседний код модуля.
        """
        owner = self.seed_task("TOWN", "in_dev", "a/b")
        self.mark_started(owner)
        waiting1 = self.seed_task("TW1", "in_dev", "a/b")
        waiting2 = self.seed_task("TW2", "in_dev", "a/b")
        self.mark_approved(waiting2)
        self.mark_approved(waiting1)

        position1, total1 = zone_lock.queue_position(
            store.db(), waiting1, "a/b")
        position2, total2 = zone_lock.queue_position(
            store.db(), waiting2, "a/b")

        self.assertEqual(total1, 2)
        self.assertEqual(total2, 2)
        self.assertEqual(position2, 1)
        self.assertEqual(position1, 2)

        zone_lock.cmd_zone_reorder([waiting1, waiting2])
        order = zone_lock.queue_order(store.db(), [waiting1, waiting2])

        self.assertEqual(order, [waiting1, waiting2])
