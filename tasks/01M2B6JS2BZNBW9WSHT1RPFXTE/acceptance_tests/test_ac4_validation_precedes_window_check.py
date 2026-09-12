"""Приёмочный тест AC-4 задачи 01M2B6JS2BZNBW9WSHT1RPFXTE (note: окно
тишины): отказы валидации (ключ не найден/найден многократно,
несовпадение числа колонок) происходят ДО проверки окна тишины — при
отказе валидации коммит не создаётся, `origin` не меняется, и файл в
`.artel/notes-pending/` не появляется, НЕЗАВИСИМО от того, открыто окно
или нет.

Зелёный с рождения: сегодняшний `cmd_note` (без понятия окна тишины
вовсе) уже отказывает валидацией раньше любого push независимо от
состояния задачи/держателя `merge_locks` — окно тишины эту проверку не
меняет, тест защищает существующий порядок операций от будущей
регрессии, когда реализация добавит проверку окна.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import NoteSandbox  # noqa: E402


class ValidationPrecedesWindowCheckTest(NoteSandbox):

    def test_ac4_unmatched_key_refuses_before_hold_even_with_window_open(self):
        """Окно тишины открыто (задача в `merge_gate`) и `--append`
        нацелен на ключ, которого нет в `docs/backlog.md`: отказ
        валидации происходит раньше любого удержания — `origin` не
        меняется, `.artel/notes-pending/` остаётся пустым.

        Ловит мутацию: реализация сначала проверяет окно тишины и
        держит запись независимо от её валидности (порядок операций
        AC-4/требование 2 нарушен) — тест красен на
        `len(notes.pending_notes()) == 1` вместо 0.
        """
        self.insert_task_in_state("merge_gate")
        before = self.origin_head()

        with self.assertRaises(SystemExit):
            notes.cmd_note(["--append", "НЕТТАКОГОКЛЮЧА", "--text", "текст"])

        self.assertEqual(before, self.origin_head())
        self.assertEqual(notes.pending_notes(), [])

    def test_ac4_column_count_mismatch_refuses_before_hold_even_with_window_open(self):
        """Тот же порядок для другого вида отказа валидации —
        несовпадение числа колонок вставки: окно открыто (живой
        держатель `merge_locks`), `origin` и `.artel/notes-pending/`
        остаются нетронутыми.

        Ловит мутацию: проверка числа колонок случайно перенесена
        ПОСЛЕ решения об удержании — тест красен на непустом
        `pending_notes()`.
        """
        self.set_live_merge_lock()
        before = self.origin_head()

        with self.assertRaises(SystemExit):
            notes.cmd_note(["копилка", "--text", "1 | 2 | 3"])

        self.assertEqual(before, self.origin_head())
        self.assertEqual(notes.pending_notes(), [])


if __name__ == "__main__":
    unittest.main()
