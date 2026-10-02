"""Юнит-тесты `scripts/test_rule_stats.py` (SPEC 01M3XR84299TD6V6E16D2PNXH4)
на свойства, не покрытые долгоживущим файлом задачи
`tests/test_01m3xr84299td6v6e16d2pnxh4_rule_stats.py`: отказ при
непрочитанной БД, отказ на неверной дате окна и мержи без id задачи в теме.
"""
import contextlib
import io
import runpy
from datetime import timedelta
from pathlib import Path
from unittest import mock

from orchestrator import config
from tests.test_01m3xr84299td6v6e16d2pnxh4_rule_stats import (
    SCRIPT, RuleStatsSandbox, group_blocks)


def _program():
    return runpy.run_path(str(SCRIPT), run_name="test_rule_stats")


class FailClosedTest(RuleStatsSandbox):

    def test_missing_db_is_exit_2_without_summary(self):
        """Нет БД пульта — код возврата 2 и причина в stderr, сводки нет.

        Ловит мутацию: отсутствие БД трактуется как пустой журнал (или
        `mode=ro` снят и SQLite молча создаёт пустой файл) — программа
        печатает сводку с нулями и возвращает 0, «правило работает».
        """
        self.publish()
        missing = Path(self.root) / ".artel" / "absent.db"
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(config, "DB", missing), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = _program()["main"](["--since", self.since.isoformat()])
        self.assertEqual(2, code, out.getvalue())
        self.assertIn(str(missing), err.getvalue())
        self.assertEqual({}, group_blocks(out.getvalue()))
        self.assertFalse(missing.exists(), "программа создала файл БД")

    def test_malformed_since_is_rejected(self):
        """`--since` не в форме YYYY-MM-DD — ошибка разбора аргументов (код 2).

        Ловит мутацию: дата окна сравнивается как сырая строка — «1.10.2026»
        молча даёт окно «с начала времён» (или пустое) вместо отказа.
        """
        err = io.StringIO()
        with contextlib.redirect_stderr(err), \
                self.assertRaises(SystemExit) as raised:
            _program()["main"](["--since", "1.10.2026"])
        self.assertEqual(2, raised.exception.code)
        self.assertIn("YYYY-MM-DD", err.getvalue())


class MergeSubjectTest(RuleStatsSandbox):

    def test_merge_without_task_id_subject_is_not_background(self):
        """Мерж первой линии без «<id>: » в теме не попадает в фон.

        В окне два мержа с правкой существующего файла `tests/`: мерж
        задачи F с темой пульта и ручной мерж с темой «Merge branch …».
        Группа 2 — ровно одна строка задачи, F.

        Ловит мутацию: id задачи берётся как всё до первого двоеточия
        темы (черновик ТЗ) — ручной мерж даёт в группе 2 вторую строку с
        мусорным «id».
        """
        task = self.new_id()
        t = self.inside()
        self.merge_touching_existing_tests(task, t)
        self.checkout("hand", create=True)
        self.commit_files({"tests/test_existing_rule.py":
                           "def test_old():\n    assert 'hand'\n"},
                          t + timedelta(minutes=30), "ручная правка")
        self.checkout("work")
        with self.dated(t + timedelta(hours=1)):
            self.git("merge", "-q", "--no-ff", "hand", "-m",
                     "Merge branch 'hand': ручной мерж")
        self.publish()

        output = self.run_stats()

        block = group_blocks(output).get(2, "")
        entries = [line.strip() for line in block.splitlines()[1:]]
        self.assertEqual([task], entries, self.msg(output))
