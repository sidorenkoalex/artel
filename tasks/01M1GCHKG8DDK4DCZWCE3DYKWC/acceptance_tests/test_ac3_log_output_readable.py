"""AC-3: вывод `log` (`catalog.cmd_log`) остаётся читаемым — наличие
`session_id` в записи не превращает строку вывода в нечитаемый дамп
структуры.

Формулировка критерия имеет смысл только если `session_id` записи
вообще ПОПАДАЕТ в вывод `log` (иначе его наличие в записи не могло бы
влиять на читаемость строки вывода вовсе) — то есть AC-3 неявно
опирается на то, что AC-2 сделало identity видимой Оператору именно
через эту команду. Тест поэтому проверяет ОБЕ половины разом: искомая
identity обязана появиться в строке вывода `log`, соответствующей
записи (иначе критерий вообще не о чём — вывод либо не показывает
session_id, и AC-3 неприменим формально, но SPEC явно писался под
случай, когда показывает), и эта строка обязана остаться ОДНОЙ строкой
человекочитаемого текста, а не питоновским дампом (`Row(...)`,
`OrderedDict(...)`, фигурноскобочный `{'...': ...}`, многострочный
`pprint`).

Красный до реализации: сегодня журнал не несёт session_id вовсе (AC-2
ещё не реализовано в этом же коммите) — искомая identity не появляется
в выводе `log` ни в каком виде.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, pause  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import LeaseTaskTest, capture  # noqa: E402

DUMP_MARKERS = ("Row(", "OrderedDict(", "sqlite3.Row", "{'", '{"')


class LogOutputReadableTest(LeaseTaskTest):

    def test_ac3_session_identity_is_shown_as_a_single_readable_line(self):
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "sess-ac3-readable"}):
            capture(pause.cmd_pause, self.TASK)

        output = capture(catalog.cmd_log, self.TASK)

        lines = [ln for ln in output.splitlines() if ln.strip()]
        matching = [ln for ln in lines if "sess-ac3-readable" in ln]
        self.assertTrue(
            matching,
            f"identity сессии, записавшей событие, не появилась ни в "
            f"одной строке вывода `log` — Оператор не может узнать, кто "
            f"поставил паузу (AC-2/AC-3): {output!r}")

        for line in matching:
            for marker in DUMP_MARKERS:
                self.assertNotIn(
                    marker, line,
                    f"строка вывода `log` похожа на дамп структуры "
                    f"({marker!r} найден) — AC-3 запрещает это: {line!r}")
            self.assertRegex(
                line, r"^\S.*\s{2}\S+.*",
                f"строка вывода `log` потеряла человекочитаемый формат "
                f"«ts  actor  action[ | detail]»: {line!r}")


if __name__ == "__main__":
    unittest.main()
