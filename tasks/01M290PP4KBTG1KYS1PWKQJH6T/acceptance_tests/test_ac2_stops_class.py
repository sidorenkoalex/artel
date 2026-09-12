"""Приёмочный тест AC-2 задачи 01M290PP4KBTG1KYS1PWKQJH6T — класс
событий `stops` печатает запись журнала «auto остановлен: …» (любой
`actor`, любая причина) и не печатает её, когда `stops` исключён из
`--events`.

Красен до реализации: `StopsClassIncludedTest` (класс `stops` включён) —
`stops` сегодня не входит в `orchestrator/watch.py::_EVENT_CLASSES`, и
уже `--events stops` отклоняется НА ЭТАПЕ РАЗБОРА аргументов (`SystemExit
"watch: неизвестные классы событий: stops"`) до входа в цикл опроса —
фоновый поток умирает почти сразу же, ни одна строка не печатается,
`_wait_until` падает таймаутом.

Зелёный с рождения: `StopsClassExcludedTest` (класс `stops` исключён) —
СЕГОДНЯ строка тоже не печатается, но по СЛУЧАЙНОЙ причине (класс
`stops` ещё не существует, а не потому, что он осознанно исключён из
`--events`) — тот же наблюдаемый результат, что и ПОСЛЕ реализации, где
исключение станет осознанным фильтром. Тест ловит мутацию «`stops`
печатается ВСЕГДА, на правах системной строки, независимо от `--events`»
(аналог `STATE=`) уже ПОСЛЕ реализации — сегодня он проходит потому, что
такой мутации ещё физически неоткуда взяться, что подтверждено прогоном
стаба ниже (валидация обоих тестов файла одной корректной реализацией).
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import WatchTestCase  # noqa: E402


class StopsClassIncludedTest(WatchTestCase):

    def test_ac2_stops_prints_any_reason_any_actor_when_included(self):
        """`--events stops` печатает запись «auto остановлен: …»
        НЕЗАВИСИМО от причины и от `actor`, записавшего строку.

        Ловит мутацию: фильтр `stops` сверяет `actor == "operator"`
        буквально (случайное сужение по самому частому вызывающему) —
        вторая строка с `actor="fsm"` не появится в потоке, второй
        `_wait_until` упадёт таймаутом.
        """
        conn = store.db()
        self._insert_task("T201")

        self._start(["--tasks", "T201", "--events", "stops", "--interval", "1"])
        self._settle()

        store.journal(conn, "T201", "operator", "auto остановлен",
                     "in_dev: маркер-stops-operator")
        self._wait_until(
            lambda: "маркер-stops-operator" in self._stream.getvalue())

        store.journal(conn, "T201", "fsm", "auto остановлен",
                     "review: маркер-stops-другой-actor")
        self._wait_until(
            lambda: "маркер-stops-другой-actor" in self._stream.getvalue())

        self._set_state("T201", "killed", "in_dev")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


class StopsClassExcludedTest(WatchTestCase):

    def test_ac2_stops_not_printed_when_explicitly_excluded(self):
        """`--events` без `stops` — запись «auto остановлен: …» не
        появляется в потоке, хотя цикл продолжает опрашивать (доказано
        второй, уже видимой строкой другого класса).

        Ловит мутацию: `--events` перестаёт влиять на класс `stops`
        (строка печатается всегда, «на правах системной») — маркер
        остановки окажется в выводе, `assertNotIn` покраснеет.
        """
        conn = store.db()
        self._insert_task("T202")

        self._start(["--tasks", "T202", "--events", "refusals",
                    "--interval", "1"])
        self._settle()

        store.journal(conn, "T202", "operator", "auto остановлен",
                     "in_dev: маркер-stops-скрыт")
        store.journal(conn, "T202", "fsm",
                     f"{store.REFUSAL_ACTION_PREFIX}: причина",
                     "маркер-после-stops")

        self._wait_until(
            lambda: "маркер-после-stops" in self._stream.getvalue())
        self.assertNotIn("маркер-stops-скрыт", self._stream.getvalue())

        self._set_state("T202", "killed", "in_dev")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


if __name__ == "__main__":
    unittest.main()
