"""Приёмочный тест AC-3 (tasks/01M1KCJGN61QT1M0PZKGMVA86Y/SPEC.md):
`tests/test_store_db_connection_close.py::DbConnectionAutoCloseTest::
test_no_resourcewarning_when_connection_is_used_inline_and_discarded`
(закрытие из своего потока, T090) остаётся зелёным без изменений
поведения.

Две проверки одного критерия: (1) метод по-прежнему проходит и (2) его
исходный код не тронут — «без изменений» в формулировке AC-3 запрещает
и провал теста, и «починку через переписывание теста» одновременно.

Зелёный с рождения: критерий требует, чтобы ничего не поменялось у
УЖЕ существующего, сегодня зелёного теста T090 — правка `__del__`
(AC-1/AC-2) не задевает путь «закрытие из своего потока» (там
`sqlite3.ProgrammingError` не возникает вовсе, перехватывать нечего),
так что до и после реализации этот файл проходит одинаково. Он
существует не для того, чтобы покраснеть, а чтобы поймать
РЕГРЕССИЮ: реализацию, которая случайно меняет поведение
`__del__` для «свого потока» пути или трогает исходный код
локализованного теста.
"""
import inspect
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from tests.test_store_db_connection_close import (  # noqa: E402
    DbConnectionAutoCloseTest,
)

EXPECTED_METHOD_SOURCE = '''    def test_no_resourcewarning_when_connection_is_used_inline_and_discarded(self):
        store.create_schema(store.db())

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            store.db().execute("SELECT 1")
            gc.collect()

        resource_warnings = [
            w for w in caught if issubclass(w.category, ResourceWarning)]
        self.assertEqual(
            resource_warnings, [],
            f"инлайн-вызов `store.db()` оставил незакрытое соединение: "
            f"{[str(w.message) for w in resource_warnings]}")
'''


class InlineThreadTestUnchangedTest(unittest.TestCase):

    def test_ac3_source_of_existing_test_method_is_unchanged(self):
        """Исходный код метода `test_no_resourcewarning_when_connection_is_
        used_inline_and_discarded` в `tests/test_store_db_connection_close.py`
        совпадает байт-в-байт с состоянием на момент постановки задачи.

        Ловит мутацию: правка тела этого метода (например, добавление
        `try/except` вокруг `store.db().execute(...)`, чтобы скрыть
        регрессию, вызванную реализацией AC-1/AC-2) — тогда исходники
        разойдутся и `assertEqual` ниже упадёт.
        """
        actual_source = inspect.getsource(
            DbConnectionAutoCloseTest
            .test_no_resourcewarning_when_connection_is_used_inline_and_discarded)

        self.assertEqual(
            actual_source, EXPECTED_METHOD_SOURCE,
            "тест T090 "
            "`test_no_resourcewarning_when_connection_is_used_inline_and_"
            "discarded` изменён — AC-3 требует оставить его как есть")

    def test_ac3_existing_test_still_passes(self):
        """Тест `test_no_resourcewarning_when_connection_is_used_inline_and_
        discarded` (T090) по-прежнему проходит после изменений `__del__`.

        Ловит мутацию: перехват `sqlite3.ProgrammingError` в `__del__`
        (AC-1/AC-2), реализованный неверно широко (например,
        `except sqlite3.Error` или `except Exception`) может незаметно
        глотать `ResourceWarning`-путь или иначе испортить поведение
        закрытия «из своего потока» — тогда этот прогон покраснеет.
        """
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName(
            "test_no_resourcewarning_when_connection_is_used_inline_and_discarded",
            DbConnectionAutoCloseTest)
        result = unittest.TestResult()
        suite.run(result)

        self.assertTrue(
            result.wasSuccessful(),
            f"T090-тест упал: "
            f"errors={result.errors}, failures={result.failures}")


if __name__ == "__main__":
    unittest.main()
