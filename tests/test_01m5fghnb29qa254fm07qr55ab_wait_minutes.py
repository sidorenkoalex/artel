"""`zone_lock.wait_minutes`: ожидание зоны закрывают запись выхода и записи цикла `auto`; снятие Оператором входом не считается (AC-4).

Группа: долгоживущий
Красен до реализации: `zone_lock.wait_interrupted_action` ещё нет, а `wait_minutes` закрывает ожидание только записью «зона свободна через» — после «auto старт», «auto остановлен», «цикл оборван» возвращает минуты вместо `None`, и одиночная запись `RELEASE_ACTION` («ждёт зоны — снято …») считается входом в ожидание.

Журнал каждой задачи строится прямо через `store.journal`; время записи
входа сдвигается в прошлое на N минут правкой `steps.ts` (N — от зерна),
поэтому «минуты от последней записи входа» — ровно N без ожидания по
реальному времени. Посторонние записи между входом и закрытием и
параметры записей выхода — тоже от зерна; зерно печатается и входит в
текст каждого провала. Свойство — разбор журнала одной функцией, связка с
`auto` здесь не нужна: песочница — только БД пульта.
"""
import random
import unittest
from datetime import datetime, timedelta

from orchestrator import config, store, zone_lock
from tests.sandbox import InitializedTmpRootTest

TS_FORMAT = "%Y-%m-%d %H:%M:%SZ"
REASONS = ("штатная остановка — команда stop", "потолок ожидания зоны исчерпан",
           "lease задачи потерян во время ожидания зоны: lease держит sess-x")
# Записи, которые ожидание не закрывают: отказ `run` по зоне, шаг роли.
NOISE = ((zone_lock.REFUSAL_ACTION, "developer"), ("agent run started", "tester"),
         ("переход отклонён: PLAN.md не ready", "fsm"))


class WaitMinutesTest(InitializedTmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.counter = 0

    def note(self, task_id: str, text: str = "") -> str:
        journal = [f"{r['id']} {r['ts']} {r['actor']} | {r['action']}"
                   for r in store.task_steps(self.conn, task_id)]
        return f"зерно: {self.seed}; {text}; журнал: {journal}"

    def task(self) -> str:
        self.counter += 1
        task_id = f"T7{self.counter:03d}"
        store.insert_task(self.conn, task_id, f"Задача {task_id}", "in_dev",
                          f"task/{task_id.lower()}", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        return task_id

    def write(self, task_id: str, action: str, actor: str = "operator") -> None:
        store.journal(self.conn, task_id, actor, action, "")

    def noise(self, task_id: str) -> None:
        for action, actor in self.rng.sample(NOISE, self.rng.randint(0, len(NOISE))):
            self.write(task_id, action, actor)

    def enter(self, task_id: str, minutes_ago: int = 0) -> None:
        """Запись входа в ожидание; её время — `minutes_ago` минут назад."""
        self.write(task_id, zone_lock.wait_enter_action(
            "a/b.py", f"T9{self.rng.randrange(100, 999)}", "in_dev"))
        row = store.task_steps(self.conn, task_id)[-1]
        now = datetime.strptime(store.now(), TS_FORMAT)
        ts = (now - timedelta(minutes=minutes_ago)).strftime(TS_FORMAT)
        self.conn.execute("UPDATE steps SET ts=? WHERE id=?", (ts, row["id"]))
        self.conn.commit()

    def closing_records(self) -> list[tuple[str, str]]:
        """(название, текст) каждой записи, закрывающей ожидание."""
        holder = f"T9{self.rng.randrange(100, 999)}"
        minutes = self.rng.randrange(0, 600)
        return [
            ("зона свободна через", zone_lock.wait_exit_action(holder, minutes)),
            ("прерванный выход", zone_lock.wait_interrupted_action(
                self.rng.choice(REASONS), minutes, holder)),
            ("auto старт", "auto старт"),
            ("auto остановлен", "auto остановлен"),
            ("цикл оборван", "цикл оборван"),
        ]

    def test_ac4_any_closing_record_after_enter_gives_none(self):
        """Любая из пяти закрывающих записей после последнего входа — `None`; без закрытия — минуты от входа; новый вход после закрытия — снова минуты.

        Сценарий: для каждой закрывающей записи («зона свободна через…»,
        новая запись прерванного выхода, «auto старт», «auto остановлен»,
        «цикл оборван») — своя задача: вход N минут назад, посторонние
        записи (отказ `run` по зоне, шаг роли, отказ перехода), закрывающая
        запись — `wait_minutes` равно `None`; затем новый вход M минут
        назад — `wait_minutes` равно M. Отдельная задача: вход N минут назад
        и только посторонние записи после него — `wait_minutes` равно N.

        Ловит мутацию: `wait_minutes` закрывает ожидание только записью
        «зона свободна через» (новая запись выхода или записи цикла не
        распознаны) — вместо `None` минуты; закрытие сравнивается не с
        ПОСЛЕДНИМ входом — повторный вход после закрытия даёт `None`.
        """
        for name, text in self.closing_records():
            with self.subTest(closing=name):
                task_id = self.task()
                self.enter(task_id, self.rng.randint(1, 120))
                self.noise(task_id)
                self.write(task_id, text)
                self.noise(task_id)
                self.assertIsNone(zone_lock.wait_minutes(self.conn, task_id),
                                  self.note(task_id, f"закрыто «{text}»"))

                again = self.rng.randint(0, 120)
                self.enter(task_id, again)
                self.noise(task_id)
                self.assertEqual(zone_lock.wait_minutes(self.conn, task_id), again,
                                 self.note(task_id, "новый вход после закрытия"))

        task_id = self.task()
        waited = self.rng.randint(0, 600)
        self.noise(task_id)
        self.enter(task_id, waited)
        self.noise(task_id)
        self.assertEqual(zone_lock.wait_minutes(self.conn, task_id), waited,
                         self.note(task_id, "открытое ожидание"))

    def test_ac4_release_alone_and_no_enter_give_none(self):
        """Журнал с единственной записью `RELEASE_ACTION` и журнал без записи входа — `None`.

        Сценарий: задача, чей журнал несёт одну запись снятия ожидания
        Оператором (`zone_lock.RELEASE_ACTION`, «ждёт зоны — снято…»), —
        `wait_minutes` равно `None`; задача с посторонними записями без
        единой записи входа — `None`; задача без записей — `None`.

        Ловит мутацию: вход в ожидание распознаётся по общему началу «ждёт
        зоны» — запись снятия Оператором принята за вход, и `status`
        показывает «ждёт 0 мин» у задачи, снятой с ожидания.
        """
        released = self.task()
        self.write(released, zone_lock.RELEASE_ACTION)
        self.assertIsNone(zone_lock.wait_minutes(self.conn, released),
                          self.note(released, "только RELEASE_ACTION"))

        noisy = self.task()
        for action, actor in NOISE:
            self.write(noisy, action, actor)
        self.assertIsNone(zone_lock.wait_minutes(self.conn, noisy),
                          self.note(noisy, "без входа"))

        empty = self.task()
        self.assertIsNone(zone_lock.wait_minutes(self.conn, empty),
                          self.note(empty, "пустой журнал"))


if __name__ == "__main__":
    unittest.main()
