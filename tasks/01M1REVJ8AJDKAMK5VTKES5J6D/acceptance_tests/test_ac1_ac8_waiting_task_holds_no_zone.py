"""AC-1, AC-8 (01M1REVJ8AJDKAMK5VTKES5J6D) — задача, ждущая зону сама (ни
одного `"agent run started"` роли developer в текущем пребывании, ни
`RELEASE_ACTION`), не считается занимающей эту зону для ДРУГИХ задач,
которые сканируют её как потенциального владельца (`blocking_conflict`,
цикл по `store.all_tasks`, zone_lock.py:198-205).

Красен до реализации: текущий цикл `blocking_conflict` по `store.
all_tasks` засчитывает окупантом ЛЮБУЮ задачу в `BLOCKING_STATES` с
пересекающейся зоной (zone_lock.py:201-205), не проверяя, стартовал ли у
НЕЁ код — то же условие, что уже применяется к САМОЙ проверяемой задаче
(`since_id`/`_visit_has_action`, zone_lock.py:193-197), кандидатам цикла
пока не применяется вовсе. Задача 01M1REVJ8AJDKAMK5VTKES5J6D добавляет
это условие для каждого кандидата — до её реализации оба теста этого
файла падают на положительном (не-`None`) результате там, где ждёт
`None`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import ZoneMechanicsSandbox  # noqa: E402


class Ac1Ac8Test(ZoneMechanicsSandbox):

    def test_ac1_waiting_task_does_not_block_third_task_sharing_only_its_zone(self):
        """Задача A ждёт зону x/y у реального владельца B (сама ни разу не
        журналировала `"agent run started"`) и одновременно держит
        собственную отдельную зону a/b. Третья задача C пересекается ТОЛЬКО
        с A (не с B) по a/b — A её не блокирует.

        Ловит мутацию: если проверка «стартовал ли код» для кандидата
        применяется только к задачам, у которых НЕТ никакого другого
        конфликта (то есть A пропускается как «уже разбирается с B», а не
        по признаку собственного старта), C всё равно ложно получит A
        окупантом a/b — мутация, отличная от полного отсутствия проверки,
        но с тем же наблюдаемым эффектом на этой паре.
        """
        owner = self.seed_task("TOWN", "in_dev", "x/y")
        self.mark_started(owner)
        a = self.seed_task("TA", "in_dev", "x/y,a/b")
        c = self.seed_task("TC", "in_dev", "a/b")

        self.assertIsNone(self.conflict_for(c))

    def test_ac8_waiting_task_with_several_zones_and_no_real_owner_blocks_none_of_its_neighbors(self):
        """Задача Y держит несколько путей зон (сценарий бэклога 05.09,
        B2 — «семь файлов зон, ни одного коммита кода»), ни разу не
        стартовала код и не имеет ни одного реального владельца-конкурента
        в системе вовсе. Каждая из задач Z1/Z2, пересекающихся с Y только
        по одному из её путей, не блокируется — ни `blocking_conflict`, ни
        сквозной `refusal` не называют Y.

        Ловит мутацию: `_shared_zone`/цикл `blocking_conflict` учитывает
        только ПЕРВЫЙ путь `zones` кандидата при решении «стартовал ли он»
        (например, читает единственный `since_id` для всей строки зон
        верно, но по ошибке применяет его только к первому найденному
        совпадению, а для второго пути той же ждущей задачи снова
        скатывается к прежней проверке «состояние+зона») — Z2 (второй
        путь Y) остался бы ложно заблокирован, даже если Z1 уже
        починен.
        """
        y = self.seed_task("TY", "in_dev", "a/one.py,a/two.py,a/three.py")
        z1 = self.seed_task("TZ1", "in_dev", "a/one.py")
        z2 = self.seed_task("TZ2", "in_dev", "a/two.py")

        for z in (z1, z2):
            with self.subTest(z=z):
                self.assertIsNone(self.conflict_for(z))
                self.assertIsNone(self.refusal_for(z))
