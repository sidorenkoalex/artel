"""AC-8, часть об ожидании зоны `auto`: отказ очереди держит `auto._wait_for_zone` в ожидании, пока задача впереди не займёт и не освободит зону.

Группа: разовый
Красен до реализации: на свободной зоне `zone_lock.blocking_conflict` задачи не впереди очереди возвращает `None` — `auto._wait_for_zone` выходит сразу, без единого опроса, хотя впереди стоит живая задача.

Почему разовый: AC-8 называет наблюдаемую точку буквально —
`auto._wait_for_zone`, закрытое имя модуля `orchestrator/auto.py`, который
эта задача только читает (SPEC, требование 7 и «Не входит»). Долгоживущий
файл `tests/` обязан держаться публичного интерфейса и закрытых имён
`orchestrator` не касается, поэтому проверка через эту точку живёт в
планке задачи. Часть AC-8 об отказе `run` — в долгоживущем файле задачи
(`RunRefusalTest`).

Сценарий: живые A и B в `in_dev` с пересекающимися зонами, SPEC A
утверждён раньше, зона свободна; B входит в `_wait_for_zone` своей
сессией. Паузы опроса подменены (`tests.sandbox.patch_sleep`): на второй
паузе A получает зону (`zone_lock.claim`), на четвёртой — закрыта
(`done`). Пути зон и id порождаются модулем `random`; зерно печатается и
входит в текст провала.
"""
import random
import string
import unittest
from unittest import mock

from orchestrator import auto, config, lease, store, zone_lock
from tests.sandbox import InitializedTmpRootTest, patch_sleep

ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
POLL_LIMIT = 12


class AutoWaitForQueueTest(InitializedTmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def msg(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def zones(self) -> list[str]:
        word = "".join(self.rng.choices(string.ascii_lowercase, k=7))
        file = "".join(self.rng.choices(string.ascii_lowercase, k=5))
        pair = self.rng.choice([[f"src/{word}/", f"src/{word}/{file}.py"],
                                [f"lib/{word}.py", f"lib/{word}.py"]])
        self.rng.shuffle(pair)
        return pair

    def seed_task(self, zones: str) -> str:
        task_id = "01" + "".join(self.rng.choices(ULID_ALPHABET, k=24))
        conn = store.db()
        store.insert_task(conn, task_id, f"Задача {task_id[-6:]}", "in_dev",
                          f"task/{task_id.lower()}-zona", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        store.update_task(conn, task_id, zones=zones)
        refusal, _ = lease.acquire(conn, task_id, f"sess-{task_id}")
        self.assertIsNone(refusal, self.msg(f"lease {task_id}: {refusal}"))
        return task_id

    def test_ac8_auto_wait_for_zone_holds_until_task_ahead_took_and_freed_zone(self):
        """B не выходит из ожидания зоны ни на свободной зоне при A впереди, ни пока A держит зону; выходит после закрытия A.

        Сценарий: см. докстринг модуля. Опросов до выхода ровно четыре:
        после первой паузы зона свободна, но впереди A — ожидание
        продолжается; после второй и третьей зону держит A; после
        четвёртой A закрыта, B впереди всех — выход, `_wait_for_zone`
        возвращает `None`. На второй паузе `claim` A проходит (A — первая
        по очереди).

        Ловит мутацию: отказ очереди вычисляется вне `zone_lock.
        blocking_conflict` (только в `claim`) — `_wait_for_zone` видит
        `None` на свободной зоне и возвращается без опросов, хотя A
        впереди.
        """
        zone_a, zone_b = self.zones()
        a = self.seed_task(zone_a)
        b = self.seed_task(zone_b)
        conn = store.db()
        for task_id in (a, b):
            store.journal(conn, task_id, "fsm", "state -> spec_gate")
            store.journal(conn, task_id, "fsm", "state -> tests_writing")
        for task_id in (a, b):
            store.journal(conn, task_id, "fsm", "state -> in_dev")
        polls = []

        def fake_sleep(_seconds):
            polls.append(len(polls) + 1)
            if len(polls) == 2:
                refusal, _ = zone_lock.claim(store.db(), a,
                                             store.get_task(store.db(), a))
                self.assertIsNone(refusal, self.msg(
                    f"claim A (первая по очереди) отказал: {refusal}"))
            elif len(polls) == 4:
                store.update_task(store.db(), a, state="done")
            elif len(polls) > POLL_LIMIT:
                raise AssertionError(self.msg(
                    f"B не вышла из ожидания за {POLL_LIMIT} опросов"))

        with patch_sleep(auto, fake_sleep), \
                mock.patch.object(config, "ZONE_WAIT_MAX_SEC",
                                  config.ZONE_WAIT_POLL_SEC * POLL_LIMIT * 10):
            result = auto._wait_for_zone(store.db(), b, f"sess-{b}", "in_dev")

        self.assertIsNone(result, self.msg(f"ожидание остановлено: {result}"))
        self.assertEqual(len(polls), 4, self.msg(
            f"B вышла из ожидания после {len(polls)} опросов, ожидалось 4: "
            f"не раньше, чем A заняла и освободила зону"))


if __name__ == "__main__":
    unittest.main()
