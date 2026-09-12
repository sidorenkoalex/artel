"""Приёмочный тест AC-6 задачи 01M290PP4KBTG1KYS1PWKQJH6T — пустая
выборка `--mine` и `--tasks` с неизвестным id завершают `watch`
именованным отказом (ненулевой код, сообщение на stderr), не тихим
кодом 0 и не бесконечным пустым циклом.

Красен до реализации: `orchestrator/watch.py::cmd_watch` сегодня не
проверяет пустоту выборки нигде — пустая `--mine` уходит в бесконечный
`while True` (0 задач, 0 строк, `_should_stop` тривиально `True` только
если `selection` пуст — `all(...)` по пустому списку даёт `True` уже на
ПЕРВОЙ итерации, поэтому сегодня это тихий код 0, не зависание; правка
проверяется тем, что вместо тихого `exit_code == 0` тест ждёт именно
`SystemExit` с ненулевым кодом и непустым текстом).
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import WatchTestCase  # noqa: E402


class EmptyMineSelectionRefusesTest(WatchTestCase):

    def test_ac6_empty_mine_refuses_with_named_message_and_nonzero_code(self):
        """Обе существующие нетерминальные задачи взяты в lease ДРУГИМИ
        identity — `--mine` вызывающей сессии («sess-me») пуст. Ожидание:
        `SystemExit` ненулевым кодом, текст сообщения — буквально «watch
        --mine: у сессии sess-me нет живых задач (lease взят другой
        identity: …)», список называет ОБЕИХ других identity.

        Ловит мутацию: пустая выборка `--mine` по-прежнему трактуется как
        «нечего слушать — штатный тихий выход» (`exit_code == 0`, без
        исключения) — `assertRaises(SystemExit)` не сработает вовсе,
        тест упадёт на отсутствии ожидаемого исключения.
        """
        conn = store.db()
        self._insert_task("M001")
        self._insert_task("M002")
        store.journal(conn, "M001", "lease", "lease взят", "",
                     session_id="sess-other-alpha")
        store.journal(conn, "M002", "lease", "lease взят", "",
                     session_id="sess-other-beta")

        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "sess-me"}):
            self._start(["--mine", "--interval", "1"])
            self._join(timeout=5.0)

        self.assertNotEqual(self._watch_outcome.get("exit_code"), 0)
        message = self._watch_outcome.get("exit_message")
        self.assertIsInstance(message, str)
        self.assertTrue(
            message.startswith(
                "watch --mine: у сессии sess-me нет живых задач "
                "(lease взят другой identity: "),
            f"неожиданный текст отказа: {message!r}")
        self.assertIn("sess-other-alpha", message)
        self.assertIn("sess-other-beta", message)


class UnknownTasksIdRefusesTest(WatchTestCase):

    def test_ac6_unknown_tasks_id_refuses_not_silently_not_forever(self):
        """`--tasks НЕТТАКОЙ` (id, которого нет ни у одной задачи в БД) —
        отказ того же класса: именованное сообщение на stderr, ненулевой
        код, поток завершается за разумное время — не висит бесконечным
        пустым циклом и не выходит молча кодом 0.

        Ловит мутацию: неизвестный `--tasks` id трактуется как «выборка
        из одной несуществующей задачи, просто никогда не даст строк» —
        поток остаётся жив бесконечно, `_join` упадёт на
        `assertFalse(is_alive())`, либо (другой вариант той же мутации)
        завершается тихо кодом 0 без сообщения — `assertNotEqual(...,
        0)` или `assertIsInstance(message, str)` покраснеют.
        """
        self._insert_task("REAL01")

        self._start(["--tasks", "НЕТТАКОЙ", "--interval", "1"])
        self._join(timeout=5.0)

        self.assertNotEqual(self._watch_outcome.get("exit_code"), 0)
        message = self._watch_outcome.get("exit_message")
        self.assertIsInstance(message, str)
        self.assertTrue(message.strip(), "сообщение отказа пустое")


if __name__ == "__main__":
    unittest.main()
