"""Юнит-тесты проверки образца формата идентификатора задачи в
acceptance_tests/ на выходе из tests_writing (SPEC
01M1H186VEVG6NF40YKH1338MD).

Дополняют залоченные приёмочные тесты
(tasks/01M1H186VEVG6NF40YKH1338MD/acceptance_tests/) сценариями, которые
они не покрывают: само ядро guard-функций в отрыве от FSM (AC-1/AC-2),
regression-защита общего источника образцов от катастрофы «пустая строка
в файле образцов — пустой regex — совпадает с любой строкой diff'а»
(AC-3, `grep -Ef`), более широкая область файлов, чем маркер красноты
(любой `*.py` под acceptance_tests/, не только `test_*.py` — требование
1 SPEC называет «содержимое acceptance_tests/», не конкретный шаблон
имени), и ветко-корректное чтение при чужом чекауте (SPEC T031,
тем же приёмом, что tests/test_fsm_branch_correct_status_reads.py).
"""
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, fsm, gitcmd  # noqa: E402
from scripts import guard  # noqa: E402
from tests.test_fsm_branch_correct_status_reads import (  # noqa: E402
    RealGitBranchTest)

TEST_WITH_ID_SAMPLE = '''"""Красен до реализации: фикстура для юнит-теста guard-проверки образца
формата идентификатора задачи."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertRegex("T042", r"T\\d{3}")
'''

TEST_CLEAN = '''"""Красен до реализации: фикстура для юнит-теста guard-проверки образца
формата идентификатора задачи — без образца."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)
'''


# --------------------------------------------------------------------------
# Общий источник образцов (SPEC требование 2, AC-3): файл, который читает
# и этот модуль, и CI-job id-format-greplint (.github/workflows/ci.yml,
# `grep -Ef`) — сам файл не должен содержать пустых строк: пустой regex
# у grep совпадает с ЛЮБОЙ строкой, что молча превратило бы линт в
# «отказывай всегда».

class IdFormatPatternsTest(unittest.TestCase):

    def test_patterns_file_has_no_blank_lines(self):
        raw = guard.ID_FORMAT_PATTERNS_PATH.read_text(encoding="utf-8")
        lines = raw.splitlines()

        self.assertTrue(lines, "источник образцов пуст")
        self.assertTrue(
            all(line.strip() for line in lines),
            f"пустая строка в {guard.ID_FORMAT_PATTERNS_PATH} — grep -Ef "
            f"прочитал бы её как пустой regex, совпадающий с ЛЮБОЙ "
            f"строкой diff'а: {lines}")

    def test_patterns_are_compiled_and_non_empty(self):
        patterns = guard.id_format_patterns()

        self.assertTrue(patterns)
        self.assertTrue(all(isinstance(p, re.Pattern) for p in patterns))
        self.assertTrue(all(p.pattern for p in patterns))


# --------------------------------------------------------------------------
# `guard.id_format_sample_errors` — ядро, без чтения файлов (тот же приём,
# что `redness_marker_errors_from_files`).

class IdFormatSampleErrorsFromFilesTest(unittest.TestCase):

    def test_sample_line_is_named_with_file_and_line_number(self):
        source = 'self.assertTrue(True)\nself.assertRegex("T042", r"T\\d{3}")\n'

        errors = guard.id_format_sample_errors([("test_ac.py", source)])

        self.assertEqual(len(errors), 1, errors)
        self.assertIn("test_ac.py:2", errors[0])
        self.assertIn(guard.ID_FORMAT_HINT, errors[0])

    def test_clean_content_is_not_flagged(self):
        errors = guard.id_format_sample_errors([("test_ac.py", TEST_CLEAN)])

        self.assertEqual(errors, [])

    def test_multiple_files_are_checked_independently(self):
        errors = guard.id_format_sample_errors([
            ("test_a.py", TEST_CLEAN),
            ("test_b.py", TEST_WITH_ID_SAMPLE),
        ])

        self.assertEqual(len(errors), 1, errors)
        self.assertIn("test_b.py", errors[0])

    def test_multiple_matching_lines_are_each_reported(self):
        source = ('self.assertRegex("T042", r"T\\d{3}")\n'
                  'self.assertRegex("T043", r"T\\d{3}")\n')

        errors = guard.id_format_sample_errors([("test_ac.py", source)])

        self.assertEqual(len(errors), 2, errors)
        self.assertIn("test_ac.py:1", errors[0])
        self.assertIn("test_ac.py:2", errors[1])

    def test_empty_files_is_empty_not_an_error(self):
        self.assertEqual(guard.id_format_sample_errors([]), [])


# --------------------------------------------------------------------------
# `guard.scan_id_format_samples` — рабочая копия, ЛЮБОЙ `*.py` под
# acceptance_tests/ (шире `scan_redness_markers`, который смотрит только
# `test_*.py` — SPEC требование 1 говорит о содержимом каталога целиком).

class ScanIdFormatSamplesTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)

    def write(self, content: str, name: str) -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / name).write_text(content, encoding="utf-8")

    def test_missing_directory_is_empty_not_an_error(self):
        self.assertEqual(guard.scan_id_format_samples(self.tdir), [])

    def test_test_file_with_sample_is_flagged(self):
        self.write(TEST_WITH_ID_SAMPLE, "test_ac.py")

        errors = guard.scan_id_format_samples(self.tdir)

        self.assertTrue(any("test_ac.py" in e for e in errors), errors)

    def test_helper_file_with_sample_is_also_flagged(self):
        """В отличие от маркера красноты (T064, только `test_*.py`) —
        образец формата может утечь и во вспомогательный файл вроде
        `_sandbox.py` (SPEC требование 1: «содержимое acceptance_tests/»,
        не ограничено шаблоном имени `test_*.py`)."""
        self.write(TEST_WITH_ID_SAMPLE, "_sandbox.py")

        errors = guard.scan_id_format_samples(self.tdir)

        self.assertTrue(any("_sandbox.py" in e for e in errors), errors)

    def test_clean_files_are_not_flagged(self):
        self.write(TEST_CLEAN, "test_ac.py")

        self.assertEqual(guard.scan_id_format_samples(self.tdir), [])


# --------------------------------------------------------------------------
# Ветко-корректное чтение при чужом чекауте (SPEC T031): та же проверка
# обязана видеть содержимое ВЕТКИ задачи, а не диска — тем же приёмом, что
# tests/test_fsm_branch_correct_status_reads.py для QUESTIONS.md/SPEC.md.

SPEC_TESTS_WRITING = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: проверка образца формата идентификатора — ветка

## Контекст

## Требования

1. ...

## Критерии приёмки

AC-1. Критерий.

## Не входит
"""


class IdFormatSampleOnForeignBranchTest(RealGitBranchTest):

    def _write_acceptance_test_on_branch(self, content: str) -> None:
        # `write_on_task_branch` зовёт `.format(task=...)` на содержимом
        # (SPEC.md/QUESTIONS.md-шаблоны несут `{task}`) — фигурные скобки
        # образца формата идентификатора (`r"T\d{3}"`) для НЕГО читались бы
        # как поле форматирования; удваиваем их только для этого пути записи,
        # исходная константа для прямых вызовов guard-функций не трогается.
        escaped = content.replace("{", "{{").replace("}", "}}")
        (self.wt_dir / "acceptance_tests").mkdir(parents=True, exist_ok=True)
        self.write_on_task_branch("acceptance_tests/test_ac.py", escaped)

    def test_id_format_sample_on_task_branch_blocks_transition(self):
        self.write_on_task_branch("SPEC.md", SPEC_TESTS_WRITING)
        self.set_state("tests_writing")
        self._write_acceptance_test_on_branch(TEST_WITH_ID_SAMPLE)
        self.assertEqual(gitcmd.current_branch(), config.MAIN_BRANCH)

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "tests_writing",
            "образец формата идентификатора закоммичен только на ветке "
            "задачи — переход обязан отказать без ручного чекаута (тем "
            "же приёмом, что T047 для QUESTIONS.md/SPEC.md)")
        self.assertIn("test_ac.py", out)
        self.assertIn(guard.ID_FORMAT_HINT, out)

    def test_clean_content_on_task_branch_advances_as_before(self):
        self.write_on_task_branch("SPEC.md", SPEC_TESTS_WRITING)
        self.set_state("tests_writing")
        self._write_acceptance_test_on_branch(TEST_CLEAN)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "in_dev")


if __name__ == "__main__":
    unittest.main()
