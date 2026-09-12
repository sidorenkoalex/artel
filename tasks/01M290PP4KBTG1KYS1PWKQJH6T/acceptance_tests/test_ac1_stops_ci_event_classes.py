"""Приёмочный тест AC-1 задачи 01M290PP4KBTG1KYS1PWKQJH6T — классы
событий `stops`/`ci` в наборе допустимых и в наборе по умолчанию `watch`.

Красен до реализации: `orchestrator/watch.py` сегодня несёт
`_EVENT_CLASSES = {"transitions", "refusals", "gates", "steps", "budget",
"alerts"}` (без `stops`/`ci`) и сообщение об ошибке `f"watch: неизвестные
классы событий: {', '.join(sorted(unknown))}"`, которое перечисляет
только САМИ неизвестные классы, а не список доступных — `--events stops`
today падает `SystemExit`, а текст ошибки неизвестного класса не
содержит ни `stops`, ни `ci`.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import watch  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import WatchTestCase  # noqa: E402


class NewEventClassesAcceptedTest(WatchTestCase):

    def test_ac1_stops_and_ci_events_accepted_without_error(self):
        """`--events stops` и `--events ci` не дают отказа использования —
        задача уже терминальна (`state="done"`), поэтому `cmd_watch`
        возвращается обычным образом первой же итерацией, без сна.

        Ловит мутацию: `stops`/`ci` не добавлены в множество допустимых
        классов `watch` — вызов упал бы `SystemExit` («неизвестные классы
        событий: stops» / «...: ci»), и `assertIsNone` по перехваченному
        исключению покраснеет.
        """
        self._insert_task("T101", state="done")
        self._insert_task("T102", state="done")

        exc_stops = None
        try:
            watch.cmd_watch(["--tasks", "T101", "--events", "stops",
                            "--interval", "0.01"])
        except SystemExit as exc:  # noqa: BLE001 — сама поимка и есть проверка
            exc_stops = exc
        self.assertIsNone(exc_stops,
                          f"--events stops отклонён: {exc_stops}")

        exc_ci = None
        try:
            watch.cmd_watch(["--tasks", "T102", "--events", "ci",
                            "--interval", "0.01"])
        except SystemExit as exc:  # noqa: BLE001
            exc_ci = exc
        self.assertIsNone(exc_ci, f"--events ci отклонён: {exc_ci}")

    def test_ac1_stops_and_ci_are_in_the_default_event_set(self):
        """Без явного `--events` набор по умолчанию уже включает и
        `stops`, и `ci` — проверено косвенно: запись «auto остановлен: …»
        и «не зелёная» запись «статус CI ветки …» обе печатаются без
        единого флага `--events`.

        Ловит мутацию: `stops`/`ci` добавлены в множество ДОПУСТИМЫХ
        классов, но не в `_DEFAULT_EVENTS` — обе строки остались бы вне
        потока по умолчанию, `_wait_until` упадёт таймаутом.
        """
        conn = watch.store.db()
        self._insert_task("T103")

        self._start(["--tasks", "T103", "--interval", "1"])
        self._settle()

        watch.store.journal(conn, "T103", "operator", "auto остановлен",
                            "in_dev: маркер-default-stops")
        watch.store.journal(
            conn, "T103", "orchestrator", "статус CI ветки (verifying)",
            "CI коммита abc0001 не зелёный: unit=failure — маркер-default-ci")

        self._wait_until(
            lambda: "маркер-default-stops" in self._stream.getvalue()
            and "маркер-default-ci" in self._stream.getvalue())

        self._set_state("T103", "killed", "in_dev")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


class UnknownEventClassErrorTest(WatchTestCase):

    def test_ac1_unknown_class_error_lists_available_classes_including_stops_ci(self):
        """Неизвестный класс в `--events` по-прежнему даёт именованный
        `SystemExit`, и его текст ТЕПЕРЬ перечисляет доступные классы,
        включая `stops` и `ci` (не только сам неизвестный класс).

        Ловит мутацию: сообщение об ошибке оставлено прежним (только
        список неизвестных классов, без списка доступных) — `assertIn`
        по `"stops"`/`"ci"` в тексте ошибки покраснеет, потому что
        неизвестный класс в этом вызове — `"bogus-class"`, не `stops`/`ci`.
        """
        self._insert_task("T104")

        with self.assertRaises(SystemExit) as cm:
            watch.cmd_watch(["--tasks", "T104", "--events", "bogus-class"])

        message = str(cm.exception)
        self.assertIn("stops", message)
        self.assertIn("ci", message)
        for known in ("transitions", "refusals", "gates", "steps", "budget"):
            self.assertIn(known, message,
                          f"текст ошибки не перечисляет известный класс {known!r}")


if __name__ == "__main__":
    unittest.main()
