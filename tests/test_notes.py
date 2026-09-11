"""Юнит-тесты чистых функций `orchestrator/notes.py` (tasks/
01M1VBEHTDYPK3E4RRFHWYYYW3): разбор таблицы раздела, вставка/`--append`,
хранилище удержанных заметок, разбор аргументов `cmd_note`.

Полный сценарий (fetch/commit/push от `origin/main`, повтор
non-fast-forward, удержание при сетевом отказе, журнал) — приёмочные
тесты `tasks/01M1VBEHTDYPK3E4RRFHWYYYW3/acceptance_tests/` через
настоящий git (`NoteSandbox`); здесь — функции, для которых реальный
git не нужен, быстрым `TmpRootTest`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import doctor, notes  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

BACKLOG_TEXT = """## Копилка

| П | Дата | Наблюдение | Где |
|---|---|---|---|
| 1 | 01.01 | старое УНИКАЛЬНЫЙКЛЮЧ | orchestrator/x.py |
| 2 | 01.01 | повтор ПОВТОРКЛЮЧ один | orchestrator/y.py |
| 2 | 01.01 | повтор ПОВТОРКЛЮЧ два | orchestrator/z.py |

## Бэклог

| П | Кандидат | Суть | Рамка | Зоны | Условие старта | Заметка |
|---|---|---|---|---|---|---|
| 1 | Кандидат A | Суть A | $10 | orchestrator/a.py | сразу | — |
"""


class RowCellsTest(unittest.TestCase):

    def test_strips_outer_pipes_and_whitespace(self):
        self.assertEqual(notes._row_cells("| 1 | два | 3 |"), ["1", "два", "3"])


class ApplyInsertTest(unittest.TestCase):

    def test_inserts_right_after_separator(self):
        new_text, section_key = notes._apply_insert(
            BACKLOG_TEXT, "копилка",
            "9 | 09.09 | новое | orchestrator/new.py")
        self.assertEqual(section_key, "копилка")
        lines = new_text.splitlines()
        sep_idx = lines.index("|---|---|---|---|")
        self.assertEqual(lines[sep_idx + 1],
                         "| 9 | 09.09 | новое | orchestrator/new.py |")
        # Прежняя первая строка данных сдвинута, не потеряна.
        self.assertIn("старое УНИКАЛЬНЫЙКЛЮЧ", lines[sep_idx + 2])

    def test_column_count_mismatch_refuses_naming_expected_count(self):
        with self.assertRaises(SystemExit) as cm:
            notes._apply_insert(BACKLOG_TEXT, "копилка", "1 | 2 | 3")
        self.assertIn("4", str(cm.exception))

    def test_unknown_section_heading_refuses(self):
        with self.assertRaises(SystemExit):
            notes._apply_insert("без разделов вовсе", "копилка", "1|2|3|4")


class ApplyAppendTest(unittest.TestCase):

    def test_unique_key_appends_to_last_column_only(self):
        new_text, section_key = notes._apply_append(
            BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ", "доп. текст")
        self.assertEqual(section_key, "копилка")
        matched = [ln for ln in new_text.splitlines()
                  if "УНИКАЛЬНЫЙКЛЮЧ" in ln][0]
        self.assertIn("orchestrator/x.py", matched)
        self.assertIn("доп. текст", matched)
        # Остальные строки раздела не задеты байт-в-байт.
        untouched = [ln for ln in BACKLOG_TEXT.splitlines()
                    if "ПОВТОРКЛЮЧ один" in ln][0]
        self.assertIn(untouched, new_text)

    def test_zero_matches_refuses_without_changing_text(self):
        with self.assertRaises(SystemExit):
            notes._apply_append(BACKLOG_TEXT, "НЕТТАКОГОКЛЮЧА", "текст")

    def test_multiple_matches_refuses_without_changing_text(self):
        with self.assertRaises(SystemExit):
            notes._apply_append(BACKLOG_TEXT, "ПОВТОРКЛЮЧ", "текст")


class ApplyDropTest(unittest.TestCase):

    def test_removes_matched_row_only_neighbours_untouched(self):
        new_text, section_key, observation = notes._apply_drop(
            BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ")
        self.assertEqual(section_key, "копилка")
        self.assertNotIn("УНИКАЛЬНЫЙКЛЮЧ", new_text)
        self.assertIn("orchestrator/x.py", observation)
        # Соседние строки раздела остаются байт-в-байт прежними.
        for marker in ("ПОВТОРКЛЮЧ один", "ПОВТОРКЛЮЧ два"):
            untouched = [ln for ln in BACKLOG_TEXT.splitlines()
                        if marker in ln][0]
            self.assertIn(untouched, new_text)
        # Другой раздел не задет.
        self.assertIn("Кандидат A", new_text)

    def test_zero_matches_refuses_without_changing_text(self):
        with self.assertRaises(SystemExit):
            notes._apply_drop(BACKLOG_TEXT, "НЕТТАКОГОКЛЮЧА")

    def test_multiple_matches_refuses_without_changing_text(self):
        with self.assertRaises(SystemExit):
            notes._apply_drop(BACKLOG_TEXT, "ПОВТОРКЛЮЧ")


class ApplySetStateTest(unittest.TestCase):

    def test_replaces_last_column_entirely_not_appends(self):
        new_text, section_key = notes._apply_set_state(
            BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ", "новое состояние")
        self.assertEqual(section_key, "копилка")
        matched = [ln for ln in new_text.splitlines()
                  if "УНИКАЛЬНЫЙКЛЮЧ" in ln][0]
        cells = notes._row_cells(matched)
        self.assertEqual(cells[-1], "новое состояние")
        self.assertNotIn("orchestrator/x.py", cells[-1])

    def test_multiple_matches_refuses_without_changing_text(self):
        with self.assertRaises(SystemExit):
            notes._apply_set_state(BACKLOG_TEXT, "ПОВТОРКЛЮЧ", "текст")


class ApplySetPriorityTest(unittest.TestCase):

    def test_replaces_first_column_with_valid_value(self):
        new_text, section_key = notes._apply_set_priority(
            BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ", "3")
        self.assertEqual(section_key, "копилка")
        matched = [ln for ln in new_text.splitlines()
                  if "УНИКАЛЬНЫЙКЛЮЧ" in ln][0]
        cells = notes._row_cells(matched)
        self.assertEqual(cells[0], "3")

    def test_value_above_range_refuses_without_changing_text(self):
        with self.assertRaises(SystemExit):
            notes._apply_set_priority(BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ", "5")

    def test_value_below_range_refuses_without_changing_text(self):
        with self.assertRaises(SystemExit):
            notes._apply_set_priority(BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ", "0")

    def test_non_numeric_value_refuses_without_changing_text(self):
        with self.assertRaises(SystemExit):
            notes._apply_set_priority(BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ", "х")


class PendingNotesStorageTest(TmpRootTest):

    def test_empty_by_default(self):
        self.assertEqual(notes.pending_notes(), [])

    def test_hold_then_read_back_round_trips(self):
        request = {"kind": "insert", "section": "копилка", "text": "x"}
        notes._hold_pending(request)
        pending = notes.pending_notes()
        self.assertEqual(pending, [request])

    def test_two_holds_are_both_visible(self):
        notes._hold_pending({"kind": "insert", "section": "копилка", "text": "a"})
        notes._hold_pending({"kind": "append", "key": "k", "text": "b"})
        self.assertEqual(len(notes.pending_notes()), 2)


class CmdNoteArgumentValidationTest(TmpRootTest):
    """Отказы разбора аргументов, не доходящие до git вовсе (пустая
    `pending_notes()` — оппортунистический flush внутри `cmd_note` не
    находит, что отправлять, и не трогает сеть)."""

    def test_no_arguments_at_all_refuses(self):
        with self.assertRaises(SystemExit):
            notes.cmd_note([])

    def test_section_without_text_refuses(self):
        with self.assertRaises(SystemExit):
            notes.cmd_note(["копилка"])

    def test_append_without_text_refuses(self):
        with self.assertRaises(SystemExit):
            notes.cmd_note(["--append", "ключ"])

    def test_set_state_without_text_refuses(self):
        with self.assertRaises(SystemExit):
            notes.cmd_note(["--set-state", "ключ"])

    def test_set_priority_without_text_refuses(self):
        with self.assertRaises(SystemExit):
            notes.cmd_note(["--set-priority", "ключ"])

    def test_flush_with_nothing_pending_is_a_noop(self):
        notes.cmd_note(["--flush"])  # не должно поднять исключение


class CheckPendingNotesTest(TmpRootTest):

    def test_ok_when_nothing_pending(self):
        self.assertEqual(doctor.check_pending_notes().status, "ok")

    def test_warn_when_something_pending(self):
        notes._hold_pending({"kind": "insert", "section": "копилка", "text": "x"})
        check = doctor.check_pending_notes()
        self.assertEqual(check.status, "warn")
        self.assertIn("note --flush", check.detail)


if __name__ == "__main__":
    unittest.main()
