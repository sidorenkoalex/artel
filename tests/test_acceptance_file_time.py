"""Время долгоживущих файлов из одного отчёта общего прогона pytest."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, fsm_autogate, store


class FileTimeCollectionTest(unittest.TestCase):
    def test_testcase_times_are_grouped_by_file(self):
        """Два файла общего прогона получают отдельные суммы своих тестов.

        Ловит мутацию: время всех testcase приписано первому файлу —
        второй теряет свои 4.5 секунды, а первый получает лишнее.
        """
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "junit.xml"
            report.write_text(
                '<testsuites><testsuite>'
                '<testcase classname="tests.test_alpha.Case" time="1.25" />'
                '<testcase classname="tests.test_beta.Case" time="4.5" />'
                '<testcase classname="tests.test_alpha.Case" time="2.75" />'
                '<testcase classname="tasks.plank.Case" time="8" />'
                '</testsuite></testsuites>', encoding="utf-8")
            times = acceptance._junit_file_times(
                report, ["tests/test_alpha.py", "tests/test_beta.py"])

        self.assertEqual(times, {"tests/test_alpha.py": 4.0,
                                 "tests/test_beta.py": 4.5})

    def test_checklist_journals_latest_measurement_before_final_group(self):
        """Карточка берёт последний замер и сохраняет последнюю группу.

        Ловит мутацию: карточка берёт первый замер — запись журнала
        содержит устаревший путь вместо файла последнего прогона.
        """
        rows = [
            {"action": acceptance.LONG_LIVED_FILE_REPORT_ACTION,
             "detail": "tests/test_old.py — 2 с"},
            {"action": acceptance.LONG_LIVED_FILE_REPORT_ACTION,
             "detail": "tests/test_new.py — 61 с\nпредупреждение: порог 60 с"},
        ]
        detail = "автоматически при approve: набор | уже проверено: планка | автогейт пройдёт сам"
        with mock.patch.object(fsm_autogate, "_acceptance_checklist_detail",
                               return_value=detail), \
             mock.patch.object(store, "task_steps", return_value=rows), \
             mock.patch.object(store, "journal") as journal:
            fsm_autogate._log_acceptance_checklist(
                object(), "T001", {"tests_locked_sha": "a" * 40}, 1)

        saved = journal.call_args.args[4]
        self.assertIn("tests/test_new.py — 61 с", saved)
        self.assertIn("предупреждение: порог 60 с", saved)
        self.assertNotIn("tests/test_old.py", saved)
        self.assertTrue(saved.endswith("автогейт пройдёт сам"))

    def test_missing_pytest_case_does_not_claim_zero_seconds(self):
        """При прерванном отчёте файл назван без выдуманной длительности.

        Ловит мутацию: отсутствие testcase превращено в нулевой замер —
        журнал выдаёт недоступное время за измеренные 0.000 с.
        """
        report = acceptance.long_lived_file_report(
            [("tests/test_missing.py", None)], 60)

        self.assertIn("tests/test_missing.py", report)
        self.assertIn("не измерено", report)
        self.assertNotIn("0.000", report)
