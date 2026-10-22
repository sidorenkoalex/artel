"""Учёт соединений `store.db()`: явно закрытое соединение выходит из учёта.

Песочница — `tests.sandbox.TmpRootTest` (БД пульта во временном каталоге).
Число закрытий — из `random`; зерно печатается и входит в текст провала.
"""
import contextlib
import gc
import random

from orchestrator import store
from tests.sandbox import TmpRootTest


class ExplicitCloseLeavesTrackingTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.calls = random.Random(self.seed).randrange(200, 600)
        gc.disable()
        self.addCleanup(gc.collect)
        self.addCleanup(gc.enable)

    def why(self, text: str) -> str:
        return f"{text} (зерно {self.seed})"

    def test_explicit_close_does_not_grow_tracking(self):
        """N соединений, закрытых `close()`, не растят `db_tracked_count()`.

        Сценарий: сборка мусора выключена; замер учёта; N раз
        `x = store.db(); x.execute("SELECT 1"); x.close()`. Учёт после цикла
        не больше замера до цикла.

        Ловит мутацию: `close()` соединения не выводит его из учёта —
        закрытое соединение разрывает свой цикл, число ссылок ниже эталона,
        просмотр его не узнаёт, и учёт растёт на N.
        """
        before = store.db_tracked_count()
        for _ in range(self.calls):
            conn = store.db()
            conn.execute("SELECT 1")
            conn.close()
        del conn
        self.assertLessEqual(store.db_tracked_count(), before, self.why(
            f"учёт был {before}, после {self.calls} явных close() — "
            f"{store.db_tracked_count()}"))

    def test_closing_wrapper_does_not_grow_tracking(self):
        """N соединений под `contextlib.closing` не растят `db_tracked_count()`.

        Сценарий: сборка мусора выключена; замер учёта; N раз
        `with closing(store.db()) as x: x.execute("SELECT 1")`. Учёт после
        цикла не больше замера до цикла; повторный `close()` закрытого
        соединения проходит без ошибки.

        Ловит мутацию: `close()` соединения не выводит его из учёта — учёт
        растёт на N.
        """
        before = store.db_tracked_count()
        for _ in range(self.calls):
            with contextlib.closing(store.db()) as conn:
                conn.execute("SELECT 1")
        conn.close()
        del conn
        self.assertLessEqual(store.db_tracked_count(), before, self.why(
            f"учёт был {before}, после {self.calls} closing() — "
            f"{store.db_tracked_count()}"))
