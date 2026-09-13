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
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, fsm, gitcmd  # noqa: E402
from scripts import guard  # noqa: E402
from tests.sandbox import TmpDirTest  # noqa: E402
from tests.test_fsm_branch_correct_status_reads import (  # noqa: E402
    RealGitBranchTest)


def _id_format_sample() -> str:
    """Строит текст образца формата идентификатора задачи (raw-строка
    «T» + три цифры) значением, а не литералом в исходнике этого файла:
    иначе сама фикстура — новая строка диффа ЭТОЙ задачи — совпала бы с
    собственным предметом проверки (CI-job id-format-greplint сканирует
    ЛЮБОЙ добавленный `*.py`, включая тесты) и заблокировала бы
    собственный PR (REVIEW.md итерация 1, замечание R1-F1)."""
    return 'r"T' + chr(92) + 'd{3}"'


TEST_WITH_ID_SAMPLE = '''"""Красен до реализации: фикстура для юнит-теста guard-проверки образца
формата идентификатора задачи."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertRegex("T042", {sample})
'''.format(sample=_id_format_sample())

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
        """Ловит мутацию: если в scripts/id_format_patterns.txt попадёт
        пустая строка (например, случайный перенос при правке набора
        образцов), здесь assertTrue на непустоте каждой строки упадёт —
        иначе `grep -Ef` тихо превратил бы CI-job в «блокируй любой PR»."""
        raw = guard.ID_FORMAT_PATTERNS_PATH.read_text(encoding="utf-8")
        lines = raw.splitlines()

        self.assertTrue(lines, "источник образцов пуст")
        self.assertTrue(
            all(line.strip() for line in lines),
            f"пустая строка в {guard.ID_FORMAT_PATTERNS_PATH} — grep -Ef "
            f"прочитал бы её как пустой regex, совпадающий с ЛЮБОЙ "
            f"строкой diff'а: {lines}")

    def test_patterns_are_compiled_and_non_empty(self):
        """Ловит мутацию: если id_format_patterns вернёт нескомпилированные
        строки или пустые паттерны вместо `re.Pattern`, дальнейшие вызовы
        `p.search(...)` в id_format_sample_errors упали бы на первом же
        файле — здесь это отлавливается на уровне самого списка образцов."""
        patterns = guard.id_format_patterns()

        self.assertTrue(patterns)
        self.assertTrue(all(isinstance(p, re.Pattern) for p in patterns))
        self.assertTrue(all(p.pattern for p in patterns))


# --------------------------------------------------------------------------
# `guard.id_format_sample_errors` — ядро, без чтения файлов (тот же приём,
# что `redness_marker_errors_from_files`).

class IdFormatSampleErrorsFromFilesTest(unittest.TestCase):

    def test_sample_line_is_named_with_file_and_line_number(self):
        """Ловит мутацию: если формирование строки ошибки потеряет номер
        строки или имя файла (например, `enumerate` без `start=1`, или
        `label` не попадёт в текст), здесь ассерт на 'test_ac.py:2' в
        единственной ошибке не пройдёт."""
        source = ('self.assertTrue(True)\n'
                  'self.assertRegex("T042", {sample})\n').format(
            sample=_id_format_sample())

        errors = guard.id_format_sample_errors([("test_ac.py", source)])

        self.assertEqual(len(errors), 1, errors)
        self.assertIn("test_ac.py:2", errors[0])
        self.assertIn(guard.ID_FORMAT_HINT, errors[0])

    def test_clean_content_is_not_flagged(self):
        """Ловит мутацию: если проверка перестанет фильтровать по
        фактическому совпадению образца и станет сообщать на любую
        строку, здесь список ошибок перестанет быть пустым."""
        errors = guard.id_format_sample_errors([("test_ac.py", TEST_CLEAN)])

        self.assertEqual(errors, [])

    def test_multiple_files_are_checked_independently(self):
        """Ловит мутацию: если проверка остановится на первом файле
        (например, `return` вместо продолжения цикла по `files`), ошибка
        по test_b.py потеряется и список окажется пуст."""
        errors = guard.id_format_sample_errors([
            ("test_a.py", TEST_CLEAN),
            ("test_b.py", TEST_WITH_ID_SAMPLE),
        ])

        self.assertEqual(len(errors), 1, errors)
        self.assertIn("test_b.py", errors[0])

    def test_multiple_matching_lines_are_each_reported(self):
        """Ловит мутацию: если проверка остановится на первом совпадении
        внутри файла вместо прохода по каждой строке, вторая строка с
        образцом не попадёт в errors и длина списка окажется 1, а не 2."""
        source = ('self.assertRegex("T042", {sample})\n'
                  'self.assertRegex("T043", {sample})\n').format(
            sample=_id_format_sample())

        errors = guard.id_format_sample_errors([("test_ac.py", source)])

        self.assertEqual(len(errors), 2, errors)
        self.assertIn("test_ac.py:1", errors[0])
        self.assertIn("test_ac.py:2", errors[1])

    def test_empty_files_is_empty_not_an_error(self):
        """Ловит мутацию: если пустой список `files` всё же породит
        ошибку (например, неверная проверка на пустоту вместо цикла по
        пустой последовательности), assertEqual с [] упадёт."""
        self.assertEqual(guard.id_format_sample_errors([]), [])


# --------------------------------------------------------------------------
# `guard.scan_id_format_samples` — рабочая копия, ЛЮБОЙ `*.py` под
# acceptance_tests/ (шире `scan_redness_markers`, который смотрит только
# `test_*.py` — SPEC требование 1 говорит о содержимом каталога целиком).

class ScanIdFormatSamplesTest(TmpDirTest):

    def write(self, content: str, name: str) -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / name).write_text(content, encoding="utf-8")

    def test_missing_directory_is_empty_not_an_error(self):
        """Ловит мутацию: если отсутствие acceptance_tests/ станет
        трактоваться как ошибка (например, `tests_dir.is_dir()` заменят
        на исключение без перехвата), здесь assertEqual с [] упадёт."""
        self.assertEqual(guard.scan_id_format_samples(self.tdir), [])

    def test_test_file_with_sample_is_flagged(self):
        """Ловит мутацию: если scan_id_format_samples перестанет читать
        файлы под acceptance_tests/ (например, неверный `rglob`-паттерн),
        здесь ни одна ошибка не назовёт test_ac.py."""
        self.write(TEST_WITH_ID_SAMPLE, "test_ac.py")

        errors = guard.scan_id_format_samples(self.tdir)

        self.assertTrue(any("test_ac.py" in e for e in errors), errors)

    def test_helper_file_with_sample_is_also_flagged(self):
        """В отличие от маркера красноты (T064, только `test_*.py`) —
        образец формата может утечь и во вспомогательный файл вроде
        `_sandbox.py` (SPEC требование 1: «содержимое acceptance_tests/»,
        не ограничено шаблоном имени `test_*.py`).

        Ловит мутацию: если область файлов сузят до `test_*.py` (тем же
        приёмом, что `scan_redness_markers`), здесь ни одна ошибка не
        назовёт _sandbox.py — расширенная область перестанет работать."""
        self.write(TEST_WITH_ID_SAMPLE, "_sandbox.py")

        errors = guard.scan_id_format_samples(self.tdir)

        self.assertTrue(any("_sandbox.py" in e for e in errors), errors)

    def test_clean_files_are_not_flagged(self):
        """Ловит мутацию: если проверка перестанет фильтровать по
        фактическому совпадению и начнёт сообщать на любой `*.py` под
        acceptance_tests/, здесь список ошибок перестанет быть пустым."""
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
        # образца формата идентификатора (raw-строка «T» + три цифры в
        # фигурных скобках) для НЕГО читались бы как поле форматирования;
        # удваиваем их только для этого пути записи, исходная константа
        # для прямых вызовов guard-функций не трогается.
        escaped = content.replace("{", "{{").replace("}", "}}")
        self.write_on_task_branch("acceptance_tests/test_ac.py", escaped)

    def test_id_format_sample_on_task_branch_blocks_transition(self):
        """Ловит мутацию: если `_tests_writing_ac_state` при чужом
        чекауте перестанет вызывать проверку образца формата (или
        продолжит читать её с диска рабочей копии вместо ВЕТКИ задачи),
        переход прошёл бы в `in_dev`, а не остался в `tests_writing`."""
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
        """Ловит мутацию: если проверка образца формата станет ложно
        срабатывать на чистом содержимом при чтении с ВЕТКИ задачи
        (регресс AC-2 в ветко-корректном пути), переход не дойдёт до
        `in_dev` даже без единого образца формата идентификатора."""
        self.write_on_task_branch("SPEC.md", SPEC_TESTS_WRITING)
        self.set_state("tests_writing")
        self._write_acceptance_test_on_branch(TEST_CLEAN)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "in_dev")


if __name__ == "__main__":
    unittest.main()
