"""Родитель параллельного прогона и дочерний без строки (AC-4): сообщение
«строка прогона не записана: …» из журнала дочернего попадает в вывод
родителя, строка БД родителя — прежняя `drive_failed`.

Группа: разовый
Зелёный с рождения: родитель по SPEC не меняется (требование 3) — `_finish_child` уже печатает журнал дочернего целиком и пишет `drive_failed` за шаблон без строки; тест держит это поведение рядом с новым сообщением дочернего.

Разовый, хотя проверяет свойство кода: критерий предписывает вызов
закрытого `canary._finish_child` с поддельным дочерним, что правила
долгоживущего файла запрещают.
"""
import contextlib
import io
from pathlib import Path
from unittest import mock

from orchestrator import canary, store
from tests.sandbox import InitializedTmpRootTest

STAMP = "20261023T120000Z"
SET_NAME = "nabor-kedr"
SUMMARY = "developer → model-pihta; источник: набор"
REPORT = ("строка прогона не записана: sqlite3.OperationalError: database "
          "is locked")


class FinishChildTest(InitializedTmpRootTest):
    def test_ac4_child_report_reaches_parent_output_and_row_is_drive_failed(self):
        """Дочерний вышел с кодом 143 без строки, в журнале — отчёт о сбое записи.

        Сценарий: поддельный дочерний `alfa` (код 143, процесс завершён),
        журнал которого содержит строку «строка прогона не записана: …» и
        стек; `_finish_child` без причины. В выводе родителя есть эта
        строка журнала; итог — `False`; у шаблона в БД ровно одна строка —
        `drive_failed`, красная, набора прогона.

        Ловит мутацию: родитель печатает журнал дочернего только при коде 0
        (или не печатает при коде `128 + сигнал`) — отчёта в выводе нет;
        либо при ненулевом коде без строки красная строка родителя не
        пишется — строки `drive_failed` нет.
        """
        log = Path(self.root) / "alfa.log"
        log.write_text(f"{REPORT}\nTraceback (most recent call last):\n"
                       f"  File \"canary.py\", line 1, in <module>\n"
                       f"sqlite3.OperationalError: database is locked\n",
                       encoding="utf-8")
        live = Path(self.root) / "live"
        live.mkdir()
        proc = mock.Mock(returncode=143, pid=424242)
        child = canary._Child(Path(self.root) / "pool" / "alfa.md", proc, log)
        plan = canary.CanarySetPlan(SET_NAME, {}, None, SUMMARY, ())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            passed = canary._finish_child(child, STAMP, plan, live)
        self.assertIn(REPORT, out.getvalue().splitlines(), out.getvalue())
        self.assertIs(passed, False, out.getvalue())
        rows = [(r["run_stamp"], r["outcome"], r["verdict"], r["set_name"])
                for r in store.all_canary_runs(store.db())
                if r["title"] == "alfa"]
        self.assertEqual(rows, [(STAMP, "drive_failed", "red", SET_NAME)],
                         out.getvalue())
