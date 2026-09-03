"""Приёмочный тест AC-1 (tasks/01M1KCJGN61QT1M0PZKGMVA86Y/SPEC.md):
`_AutoClosingConnection.__del__` (orchestrator/store.py) обёрнут узким
перехватом `sqlite3.ProgrammingError` вокруг вызова `close()`; любое
другое исключение в этом месте перехватом не гасится.

Оба теста вызывают `__del__()` напрямую как обычный метод (тот же
приём, что `tests/test_store_db_connection_close.py::
test_del_closes_the_connection`): прямой вызов не подчиняется
особому протоколу деструктора интерпретатора («Exception ignored…» —
эффект именно НЕАВНОГО вызова через GC/потерю ссылки), поэтому
исключение, не перехваченное телом `__del__`, здесь просто
пробрасывается наружу как из любого обычного метода — это и отличает
«перехвачено» от «не перехвачено» без обращения к перехвату stderr.

Красен до реализации: сейчас `__del__` — это `self.close()` без
`try/except` (orchestrator/store.py:89-90). `test_ac1_programmingerror_from_close_is_swallowed`
падает, потому что смоделированный `sqlite3.ProgrammingError` из
`close()` сегодня пробрасывается наружу `__del__()` вместо того, чтобы
быть перехваченным. `test_ac1_other_exception_from_close_is_not_swallowed`
уже сегодня проходит «случайно» (нечего перехватывать — эта половина
критерия станет содержательной только после того, как реализация
обзаведётся `try/except`, который не должен зацепить лишнего) —
оставлена в файле, потому что без него первый тест не доказывает
«узость» перехвата, только сам факт перехвата.
"""
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class NarrowExceptionScopeTest(TmpRootTest):

    def test_ac1_programmingerror_from_close_is_swallowed(self):
        """`close()`, бросающий `sqlite3.ProgrammingError`, не приводит к
        исключению из `__del__()`.

        Ловит мутацию: удаление `try/except` вокруг `self.close()` в
        `__del__` (orchestrator/store.py) — тогда `conn.__del__()` ниже
        поднимет `sqlite3.ProgrammingError` вместо тихого возврата.
        """
        conn = store.db()
        conn.close = mock.Mock(
            side_effect=sqlite3.ProgrammingError(
                "SQLite objects created in a thread can only be used in "
                "that same thread."))

        conn.__del__()  # не должно бросить

        del conn.close  # снимаем подмену — финальный __del__ реального
                         # объекта при потере ссылки закроет БД по-настоящему,
                         # без шума в конце прогона
        conn.close()

    def test_ac1_other_exception_from_close_is_not_swallowed(self):
        """`close()`, бросающий исключение, отличное от
        `sqlite3.ProgrammingError`, продолжает пробрасываться из
        `__del__()` — перехват не шире одного конкретного класса.

        Ловит мутацию: перехват, расширенный до `except Exception`
        (или до `sqlite3.Error`, родителя `ProgrammingError`) вместо
        точечного `except sqlite3.ProgrammingError` — тогда
        `RuntimeError` ниже был бы молча проглочен и тест не поднял бы
        исключение там, где `assertRaises` его ожидает.
        """
        conn = store.db()
        conn.close = mock.Mock(side_effect=RuntimeError("не sqlite-ошибка"))

        with self.assertRaises(RuntimeError):
            conn.__del__()

        del conn.close  # снимаем подмену — финальный __del__ реального
                         # объекта при потере ссылки закроет БД по-настоящему,
                         # без шума в конце прогона
        conn.close()


if __name__ == "__main__":
    unittest.main()
