"""AC-4, AC-6 (01M1REVJ8AJDKAMK5VTKES5J6D) — `zone_lock.refusal` называет
id и состояние ФАКТИЧЕСКОГО владельца зоны (задача, у которой в текущем
пребывании был `"agent run started"`), не первую попавшуюся задачу
блокирующего диапазона той же зоны, даже если она встречается раньше
владельца при переборе `store.all_tasks` (порядок — `ORDER BY id`,
лексикографический по id задачи, не порядок заведения в БД).

Красен до реализации: test_ac4 падает уже сегодня — цикл
`blocking_conflict` (zone_lock.py:198-205) возвращает конфликт на
ПЕРВОЙ подходящей по состоянию+зоне строке `store.all_tasks`, не
разбирая, кто из кандидатов реально стартовал код, поэтому при id
ждущей задачи, лексикографически предшествующем id владельца
(подробности в докстринге метода), называет неактуального владельца
вместо реального; test_ac6 зелёный уже сегодня по независимой от этой
правки причине (см. докстринг метода) и оставлен здесь приёмочной
планкой на случай регрессии.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import ZoneMechanicsSandbox  # noqa: E402


class Ac4Ac6Test(ZoneMechanicsSandbox):

    def test_ac4_refusal_names_the_actual_owner_not_an_earlier_waiting_neighbor(self):
        """Задача TC проверяется на конфликт по зоне a/b. В БД есть две
        другие задачи с той же зоной: TA — сама ждёт (`in_dev`),
        `"agent run started"` не журналировала, id лексикографически
        ПРЕДШЕСТВУЕТ id владельца (`store.all_tasks` — `ORDER BY id`);
        TZ — реальный владелец (стартовал код), сейчас в `review`, id
        лексикографически позже TA. `refusal` для TC называет id и
        состояние TZ, не TA.

        Красен до реализации: цикл `blocking_conflict` (zone_lock.py:198-
        205) возвращает конфликт на ПЕРВОЙ подходящей по состоянию+зоне
        строке `store.all_tasks` — TA идёт раньше TZ в этом порядке и сама
        удовлетворяет `state in BLOCKING_STATES` + пересечение зоны,
        поэтому текущая реализация называет TA, хотя TA не является
        реальным владельцем.
        """
        checked = self.seed_task("TC", "in_dev", "a/b")
        waiting = self.seed_task("TA", "in_dev", "a/b")
        owner = self.seed_task("TZ", "review", "a/b")
        self.mark_started(owner)

        text = self.refusal_for(checked)

        self.assertIsNotNone(text)
        self.assertIn(owner, text)
        self.assertIn("review", text)
        self.assertNotIn(waiting, text)

    def test_ac6_first_to_actually_start_becomes_owner_second_gets_refused_naming_it(self):
        """Две задачи в `in_dev` делят зону a/b, ни одна ещё не
        журналировала `"agent run started"`. Первая (TF) фактически
        запускает разработческий шаг — журналирует `"agent run started"`
        — и после этого проходит без отказа по зоне. Вторая (TS), всё ещё
        без собственного старта, получает от `refusal` отказ, называющий
        именно первую.

        Зелёный с рождения: `blocking_conflict` части 1-3 УЖЕ исключает
        саму себя из проверки, если она первой стартовала код
        (`since_id`/`_visit_has_action`, самопроверка задачи 1-3 не
        менялась этой задачей) — а поскольку TF единственный кандидат с
        пересекающейся зоной у TS, цикл называет её независимо от правки
        AC-1 (сравнивает лишь состояние+зону, чего здесь достаточно для
        верного ответа уже сегодня). Тест фиксирует этот сценарий
        приёмочной планкой на случай, если правка AC-1 случайно
        затронет и эту ветку (см. «Ловит мутацию» ниже).

        Ловит мутацию: правка AC-1 требует от кандидата не только
        `"agent run started"`, но и буквального совпадения `row["state"]
        == "in_dev"` (не всего диапазона `BLOCKING_STATES`) — TF, уже
        стартовавшая и всё ещё в `in_dev`, продолжала бы называться, но
        эквивалентная мутация, привязывающая признак «стартовал» к
        неверному действию (например ищущая `zone_lock.RELEASE_ACTION`
        вместо `_AGENT_STARTED_ACTION`), сделала бы TF неотличимой от TS
        и либо обеих заблокировала, либо обеих пропустила.
        """
        first = self.seed_task("TF", "in_dev", "a/b")
        second = self.seed_task("TS", "in_dev", "a/b")

        self.mark_started(first)

        self.assertIsNone(self.conflict_for(first))
        text = self.refusal_for(second)
        self.assertIsNotNone(text)
        self.assertIn(first, text)
        self.assertIn("in_dev", text)
