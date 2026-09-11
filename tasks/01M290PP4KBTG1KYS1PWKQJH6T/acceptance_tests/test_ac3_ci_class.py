"""Приёмочный тест AC-3 задачи 01M290PP4KBTG1KYS1PWKQJH6T — класс
событий `ci` печатает запись журнала «статус CI ветки …», чей текст
называет вердикт НЕ зелёным, и не печатает такую же запись с зелёным
вердиктом.

Красен до реализации: `ci` сегодня не входит в
`orchestrator/watch.py::_EVENT_CLASSES` — уже `--events ci` отклоняется
НА ЭТАПЕ РАЗБОРА аргументов (`SystemExit "watch: неизвестные классы
событий: ci"`) до входа в цикл опроса: фоновый поток умирает почти сразу
же, ни одна строка (включая независимую от `--events` строку `STATE=`)
не успевает напечататься, оба теста падают таймаутом `_wait_until`.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import WatchTestCase  # noqa: E402


class CiClassNonGreenTest(WatchTestCase):

    def test_ac3_ci_prints_non_green_verdict_record(self):
        """`--events ci`: запись «статус CI ветки (verifying)» с текстом,
        называющим CI НЕ зелёным (реальный формат `orchestrator/ci.py::
        verifying_status` для красного исхода — «… не зелёный: …»),
        появляется в потоке.

        Ловит мутацию: класс `ci` не добавлен в `_matches_class` — строка
        никогда не печатается, `_wait_until` упадёт таймаутом.
        """
        conn = store.db()
        self._insert_task("T301")

        self._start(["--tasks", "T301", "--events", "ci", "--interval", "1"])
        self._settle()

        store.journal(
            conn, "T301", "orchestrator", "статус CI ветки (verifying)",
            "CI коммита abc0011 не зелёный: unit=failure")

        self._wait_until(
            lambda: "CI коммита abc0011 не зелёный: unit=failure"
            in self._stream.getvalue())

        self._set_state("T301", "killed", "in_dev")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


class CiClassGreenExcludedTest(WatchTestCase):

    def test_ac3_ci_does_not_print_green_verdict_record(self):
        """`--events ci`: та же запись «статус CI ветки (verifying)», но
        с зелёным вердиктом (реальный формат `ci.verifying_status` для
        зелёного исхода — «… зелёный (N проверок)»), в поток не попадает —
        доказано отдельной строкой `STATE=`, которая печатается независимо
        от `--events` и подтверждает, что цикл продолжил опрос дальше.

        Ловит мутацию: класс `ci` сверяет только `action`, игнорируя
        вердикт в тексте записи (печатает ЛЮБУЮ «статус CI ветки …») —
        зелёная строка окажется в выводе, `assertNotIn` покраснеет.
        """
        conn = store.db()
        self._insert_task("T302")

        self._start(["--tasks", "T302", "--events", "ci", "--interval", "1"])
        self._settle()

        store.journal(
            conn, "T302", "orchestrator", "статус CI ветки (verifying)",
            "CI коммита abc0022 зелёный (3 проверок)")
        self._set_state("T302", "review", "in_dev")

        self._wait_until(
            lambda: "STATE=review" in self._stream.getvalue())
        self.assertNotIn("CI коммита abc0022 зелёный", self._stream.getvalue())

        self._set_state("T302", "killed", "review")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


if __name__ == "__main__":
    unittest.main()
