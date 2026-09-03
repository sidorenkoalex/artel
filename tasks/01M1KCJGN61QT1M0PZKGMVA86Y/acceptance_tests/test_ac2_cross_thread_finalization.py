"""Приёмочный тест AC-2 (tasks/01M1KCJGN61QT1M0PZKGMVA86Y/SPEC.md):
соединение создано в одном потоке, ссылки на него сняты, а сборка
мусора (`gc.collect()`) объекта выполнена в ДРУГОМ потоке — прогон не
печатает «Exception ignored» в stderr.

Красен до реализации: воспроизведение (см. ниже) эмпирически
подтверждено перед записью этого файла — текущий `__del__`
(orchestrator/store.py:89-90, `self.close()` без перехвата) печатает
в stderr ровно «Exception ignored in: <function
_AutoClosingConnection.__del__ ...>» с трейсбеком
`sqlite3.ProgrammingError: SQLite objects created in a thread can
only be used in that same thread.», когда объект уничтожается не в
породившем его потоке. После обёртки `__del__` узким
`except sqlite3.ProgrammingError` (AC-1) `close()` внутри всё равно
поднимает то же исключение при кросс-поточном финализировании — но
перехват гасит его до печати в stderr, и этот тест зеленеет.

## Устройство воспроизведения

Наивная версия («создать в потоке A, дождаться его завершения (join),
снять ссылку и вызвать `gc.collect()` в потоке B») ненадёжна: после
`join()` ОС вправе переиспользовать идентификатор завершившегося
потока для следующего — тогда проверка sqlite3 «тот же ли это поток»
видит СОВПАДЕНИЕ идентификаторов и бага не воспроизводит (эмпирически
подтверждено при подготовке теста: `join()` до старта потока B —
воспроизведения нет). Здесь поток-создатель (`creator`) держится
живым (`threading.Event.wait`) до тех пор, пока поток-финализатор
(`finalizer`) не отработает и не выйдет из `redirect_stderr` — гарантия,
что оба потока существуют ОДНОВРЕМЕННО и их идентификаторы различны на
момент фактического уничтожения объекта. `creator` явно снимает СВОЙ
локальный `conn` (`del conn`) сразу после сохранения его в разделяемый
словарь: иначе ссылка в кадре `creator` пережила бы `finalizer`, и
объект уничтожился бы только при возврате из `creator` — в СВОЁМ же
потоке, без нарушения.
"""
import gc
import io
import sys
import threading
import unittest
from contextlib import redirect_stderr
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class CrossThreadFinalizationTest(TmpRootTest):

    def test_ac2_gc_in_foreign_thread_does_not_print_exception_ignored(self):
        """Соединение создаётся в потоке A, теряет последнюю ссылку и
        собирается сборщиком мусора в потоке B — вывод в stderr не
        содержит «Exception ignored».

        Ловит мутацию: снятие перехвата `sqlite3.ProgrammingError`
        вокруг `self.close()` в `_AutoClosingConnection.__del__`
        (возврат к простому `self.close()`, как до задачи) — тогда
        `sqlite3.ProgrammingError` при закрытии из чужого потока
        снова уходит в stderr как «Exception ignored», и `assertNotIn`
        ниже падает.
        """
        holder = {}
        created = threading.Event()
        release = threading.Event()

        def creator():
            conn = store.db()
            conn.execute("SELECT 1")
            holder["conn"] = conn
            del conn  # единственная оставшаяся ссылка — в holder
            created.set()
            release.wait(timeout=5)

        creator_thread = threading.Thread(target=creator)
        creator_thread.start()
        self.assertTrue(created.wait(timeout=5),
                         "поток-создатель не успел создать соединение")

        captured_stderr = io.StringIO()

        def finalizer():
            del holder["conn"]
            gc.collect()

        with redirect_stderr(captured_stderr):
            finalizer_thread = threading.Thread(target=finalizer)
            finalizer_thread.start()
            finalizer_thread.join(timeout=5)

        release.set()
        creator_thread.join(timeout=5)

        self.assertNotIn(
            "Exception ignored", captured_stderr.getvalue(),
            f"финализация соединения из чужого потока напечатала в "
            f"stderr:\n{captured_stderr.getvalue()}")


if __name__ == "__main__":
    unittest.main()
