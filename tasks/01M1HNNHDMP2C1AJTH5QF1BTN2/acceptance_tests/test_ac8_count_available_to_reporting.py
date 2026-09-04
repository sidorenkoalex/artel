"""AC-8 (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md): «Число событий
«правка планки» доступно существующему механизму отчётности.»

`orchestrator/report.py` не входит в зоны этой задачи (TZ.md, «Зоны»:
только artel.py/новый модуль/store.py точечно/alerts.py/tests) —
«существующий механизм отчётности» здесь буквально существующий: агрегатор
журнала `report._all_steps(conn, store.all_tasks(conn))`, который
`report.cmd_report()` уже зовёт сегодня (`orchestrator/report.py:443`) для
любой задачи программы. Публичного «счётчика по action» в store.py/
report.py нет (это НЕ придумано этим тестом — так исполнителю
подтвердило чтение кода перед написанием этих тестов); проверяется, что
события правки планки, записанные через штатный `store.journal`,
попадают в ЭТОТ уже существующий агрегатор program-wide и правильно
считаются по своей метке — то есть «доступны» ему без специального кода
под каждую новую задачу-потребителя.

Красен до реализации: `_sandbox.discover_amend_command_name()` падает
`AssertionError` — новой команды правки планки в таблице диспетчера ещё
нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import report, store  # noqa: E402

from _sandbox import (AC_TEST_AMENDED_V1, AC_TEST_AMENDED_V2,  # noqa: E402
                      AmendSandbox)

MARKER = "правка планки"


class ReportingCountTest(AmendSandbox):

    def test_ac8_amend_events_are_counted_via_existing_report_aggregator(self):
        """Два последовательных успешных аменда одной задачи — журнал
        несёт два события «правка планки»; существующий агрегатор
        отчётности `report._all_steps` (тот же вызов, что
        `report.cmd_report()` использует для программы целиком) видит
        обе записи program-wide и их можно посчитать по метке action,
        не читая журнал задачи напрямую в обход отчётности.

        Ловит мутацию: команда пишет запись правки планки НЕ через
        `store.journal` (например, в отдельную таблицу или файл) —
        общий агрегатор `report._all_steps`, читающий только `steps` via
        `store.task_steps`, тогда не увидит событие вовсе, и счётчик
        останется 0 после двух правок.
        """
        self.enter_in_dev()

        self.write_acceptance_tests(AC_TEST_AMENDED_V1)
        self.run_amend(reason="первая правка")
        conn = store.db()
        all_steps_after_first = report._all_steps(conn, store.all_tasks(conn))
        count_after_first = sum(
            1 for r in all_steps_after_first
            if r["task_id"] == self.TASK and MARKER in r["action"])
        self.assertEqual(
            count_after_first, 1,
            "агрегатор отчётности не видит событие правки планки после "
            "первой правки")

        self.write_acceptance_tests(AC_TEST_AMENDED_V2)
        self.run_amend(reason="вторая правка")
        all_steps_after_second = report._all_steps(conn, store.all_tasks(conn))
        count_after_second = sum(
            1 for r in all_steps_after_second
            if r["task_id"] == self.TASK and MARKER in r["action"])
        self.assertEqual(
            count_after_second, 2,
            "агрегатор отчётности не насчитал две правки планки после "
            "двух успешных амендов")


if __name__ == "__main__":
    unittest.main()
