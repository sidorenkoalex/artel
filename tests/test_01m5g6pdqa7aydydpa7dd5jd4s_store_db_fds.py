"""Соединения `store.db()`, брошенные без `close()`, не копят дескрипторы процесса и без сборки циклов; соединение с живой внешней ссылкой остаётся рабочим.

Группа: долгоживущий

Красен до реализации: соединение `store.db()` в CPython 3.11+ сидит в цикле ссылок и закрывается только сборкой циклов — при `gc.disable()` 2000 брошенных соединений оставляют тысячи открытых дескрипторов (AC-1); функции `store.db_tracked_count` ещё нет — сценарий другого потока падает `AttributeError` (AC-3).

Песочница — `tests.sandbox.TmpRootTest` (БД пульта во временном каталоге).
Число открытых дескрипторов — число записей `/dev/fd`. Порядок держателей
ссылок, число промежуточных вызовов `db()`, число потоков и вставляемые
значения — из `random`; зерно печатается и входит в текст каждого провала.
"""
import contextlib
import gc
import os
import random
import sqlite3
import threading

from orchestrator import store
from tests.sandbox import TmpRootTest

CALLS = 2000
FD_SLACK = 16


def open_fds() -> int:
    return len(os.listdir("/dev/fd"))


class StoreDbDescriptorsTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def why(self, text: str) -> str:
        return f"{text} (зерно {self.seed})"

    def disable_gc(self) -> None:
        gc.disable()
        self.addCleanup(gc.collect)
        self.addCleanup(gc.enable)

    def test_ac1_abandoned_connections_do_not_accumulate_fds_without_gc(self):
        """2000 брошенных соединений `db()` при выключенной сборке мусора добавляют не больше 16 дескрипторов.

        Сценарий: сборка мусора выключена (включение и `gc.collect()` — в
        `addCleanup`); первый вызов `db()` создаёт файл БД и его спутники;
        затем 2000 раз `store.db().execute("SELECT 1")` без сохранения
        соединения. Число записей `/dev/fd` после цикла больше замера до
        цикла не более чем на 16.

        Ловит мутацию: просмотр учёта в `db()` снят (или сравнивает число
        ссылок с эталоном, завышенным на единицу, — брошенное соединение
        никогда не равно эталону) — каждое брошенное соединение держит
        свои дескрипторы БД и WAL до сборки циклов, после цикла их тысячи.
        """
        self.disable_gc()
        store.db().execute("SELECT 1")
        before = open_fds()
        for _ in range(CALLS):
            store.db().execute("SELECT 1")
        after = open_fds()
        self.assertLessEqual(after - before, FD_SLACK, self.why(
            f"дескрипторов было {before}, после {CALLS} вызовов db() — "
            f"{after}"))

    def test_ac2_connection_with_external_reference_stays_open(self):
        """Соединение, на которое ссылается переменная, курсор, связанный метод или `closing`, рабочее после последующих вызовов `db()`.

        Сценарий: первое соединение сохранено в переменной, затем 2000
        вызовов `db()` с отброшенным результатом — оно выполняет
        `SELECT 1`. Затем в случайном порядке заводятся держатели
        соединения — курсор (`db().execute(...)`), связанный метод
        (`db().execute`), обёртка `contextlib.closing(db())`; после каждого
        — случайное число брошенных вызовов `db()`; в конце каждое
        соединение через своего держателя выполняет `SELECT` и отдаёт
        записанное в него значение.

        Ловит мутацию: просмотр учёта считает брошенным соединение с числом
        ссылок не больше эталона плюс один (`<=` вместо `==` либо эталон,
        снятый до постановки в учёт) — соединение с единственной внешней
        ссылкой закрывается, и `SELECT` через держателя падает
        `ProgrammingError: Cannot operate on a closed database`.
        """
        first = store.db()
        for _ in range(CALLS):
            store.db()
        self.assertEqual(first.execute("SELECT 1").fetchone()[0], 1,
                         self.why("первое соединение после 2000 вызовов db()"))

        kinds = ["cursor", "bound", "closing"]
        self.rng.shuffle(kinds)
        holders = []
        for kind in kinds:
            value = self.rng.randrange(10 ** 9)
            if kind == "cursor":
                holder = store.db().execute(f"SELECT {value}")
                use = (lambda h: lambda: h.connection.execute(
                    "SELECT ?", (h.fetchone()[0],)).fetchone()[0])(holder)
            elif kind == "bound":
                holder = store.db().execute
                use = (lambda h, v: lambda: h(f"SELECT {v}").fetchone()[0])(
                    holder, value)
            else:
                holder = contextlib.closing(store.db())
                use = (lambda h, v: lambda: h.thing.execute(
                    f"SELECT {v}").fetchone()[0])(holder, value)
            holders.append((kind, value, holder, use))
            for _ in range(self.rng.randrange(50, 300)):
                store.db()
        for kind, value, _holder, use in holders:
            with self.subTest(holder=kind):
                try:
                    got = use()
                except sqlite3.ProgrammingError as exc:
                    self.fail(self.why(f"соединение с держателем {kind} "
                                       f"закрыто: {exc}"))
                self.assertEqual(got, value, self.why(
                    f"держатель {kind}: SELECT вернул не то значение"))

    def test_ac3_connection_abandoned_in_other_thread_leaves_tracking(self):
        """Соединения, брошенные в других потоках, не поднимают исключений и не остаются в учёте после `db()` главного потока.

        Сценарий: замер `store.db_tracked_count()`; случайное число потоков
        (1…5) по очереди создают соединение `db()`, выполняют на нём
        `SELECT 1` и бросают его; затем `db()` в главном потоке. Исключений
        нет ни в потоках, ни в главном потоке; размер учёта после вызова
        не больше замера плюс одно соединение, выданное этим вызовом.

        Ловит мутацию: `sqlite3.ProgrammingError` закрытия соединения
        чужого потока не перехвачен — `db()` главного потока поднимает его;
        либо соединение, чьё закрытие отказало, оставлено в учёте — размер
        учёта растёт на число потоков.
        """
        store.db().execute("SELECT 1")
        before = store.db_tracked_count()
        errors = []

        def abandon():
            try:
                store.db().execute("SELECT 1")
            except Exception as exc:  # noqa: BLE001 — исключение потока — провал
                errors.append(repr(exc))

        threads = self.rng.randrange(1, 6)
        for _ in range(threads):
            worker = threading.Thread(target=abandon)
            worker.start()
            worker.join()
        self.assertEqual(errors, [], self.why("исключение в потоке"))
        try:
            conn = store.db()
        except Exception as exc:  # noqa: BLE001
            self.fail(self.why(f"db() главного потока после {threads} "
                               f"потоков: {exc!r}"))
        after = store.db_tracked_count()
        self.assertEqual(conn.execute("SELECT 1").fetchone()[0], 1,
                         self.why("соединение главного потока"))
        self.assertLessEqual(after, before + 1, self.why(
            f"учёт был {before}, после {threads} потоков и db() — {after}"))

    def test_ac4_connection_type_backup_and_transaction_context(self):
        """`db()` — экземпляр `sqlite3.Connection`; `backup` и `with conn:` фиксируют и откатывают как прежде.

        Сценарий: `isinstance(store.db(), sqlite3.Connection)`; таблица со
        случайным именем; `with conn:` со вставкой случайного значения —
        другое соединение `db()` его видит (фиксация); `with conn:` со
        вставкой второго значения и исключением — исключение выходит
        наружу, второе значение другим соединением не видно (откат);
        `backup` в соединение `:memory:` переносит таблицу с
        зафиксированным значением.

        Ловит мутацию: `db()` отдаёт обёртку-посредника над соединением
        (ради учёта) вместо подкласса `sqlite3.Connection` — `isinstance`
        ложен, а `backup` падает `TypeError` на цели-обёртке; либо обёртка
        глотает исключение `with` — откат не происходит, второе значение
        видно.
        """
        conn = store.db()
        self.assertIsInstance(conn, sqlite3.Connection, self.why("тип db()"))
        table = f"t_fds_{self.rng.randrange(10 ** 6)}"
        kept, dropped = self.rng.sample(range(10 ** 9), 2)
        conn.execute(f"CREATE TABLE {table}(v INTEGER)")
        conn.commit()
        with conn:
            conn.execute(f"INSERT INTO {table}(v) VALUES (?)", (kept,))
        with self.assertRaises(RuntimeError):
            with conn:
                conn.execute(f"INSERT INTO {table}(v) VALUES (?)", (dropped,))
                raise RuntimeError("откат")
        seen = [row[0] for row in
                store.db().execute(f"SELECT v FROM {table} ORDER BY v")]
        self.assertEqual(seen, [kept], self.why("фиксация и откат with conn"))

        target = sqlite3.connect(":memory:")
        self.addCleanup(target.close)
        store.db().backup(target)
        copied = [row[0] for row in target.execute(f"SELECT v FROM {table}")]
        self.assertEqual(copied, [kept], self.why("backup"))
