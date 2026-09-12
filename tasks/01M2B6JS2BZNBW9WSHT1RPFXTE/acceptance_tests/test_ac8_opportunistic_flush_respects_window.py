"""Приёмочный тест AC-8 задачи 01M2B6JS2BZNBW9WSHT1RPFXTE (note: окно
тишины): оппортунистический допуш в начале КАЖДОГО `cmd_note`
(`_flush_pending`) уважает окно тишины — при открытом окне не
отправляет удержанные записи (они остаются нетронутыми в
`.artel/notes-pending/`), вне окна допушивает их, как и сегодня.

Красен до реализации: `_flush_pending` сегодня не смотрит на окно
вовсе — при открытом окне она всё равно допушивает старую удержанную
заметку (унаследованную от предыдущего вызова с недоступным origin);
тест красен на пустом `pending_notes()` там, где ожидается непустой.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import NoteSandbox  # noqa: E402


class OpportunisticFlushRespectsWindowTest(NoteSandbox):

    def test_ac8_open_window_leaves_previously_held_note_untouched(self):
        """Заметка уже удержана ДО этого вызова (`notes._hold_pending`
        напрямую, минуя `cmd_note» — предусловие независимо от того,
        как она попала в удержание). Окно тишины открыто (задача в
        `verifying`). Обычный вызов `note <раздел> --text …» (не
        `--flush`) не должен допушить старую удержанную заметку —
        новая тоже уходит в удержание, origin не сдвигается вовсе.

        Ловит мутацию: оппортунистический флаш безусловен (не проверяет
        окно) — тест красен на изменившемся `origin_head()` или на
        отсутствии старой заметки в `pending_notes()` после вызова.
        """
        notes._hold_pending({"kind": "insert", "section": "копилка",
                             "text": "9 | 09.09 | старая удержанная | orchestrator/old.py"})
        self.insert_task_in_state("verifying")
        before = self.origin_head()

        self.capture(
            notes.cmd_note,
            ["очередь", "--text", "9 | новая при открытом окне"])

        self.assertEqual(before, self.origin_head())
        pending = notes.pending_notes()
        self.assertEqual(len(pending), 2, pending)
        texts = [p.get("text", "") for p in pending]
        self.assertTrue(any("старая удержанная" in t for t in texts), pending)
        self.assertTrue(any("новая при открытом окне" in t for t in texts), pending)

    def test_ac8_closed_window_still_flushes_previously_held_note(self):
        """Та же предпосылка (старая удержанная заметка), но БЕЗ
        открытого окна — обычный вызов `note` допушивает старую заметку
        оппортунистически, как и до этой задачи: обе строки (старая и
        новая) в итоге в origin, `pending_notes()` пустеет.

        Ловит мутацию: реализация случайно инвертирует условие (флашит
        только когда окно ОТКРЫТО) — тест красен на непустом
        `pending_notes()` после вызова.
        """
        notes._hold_pending({"kind": "insert", "section": "копилка",
                             "text": "9 | 09.09 | старая без окна | orchestrator/old2.py"})

        self.capture(
            notes.cmd_note,
            ["очередь", "--text", "9 | новая без окна"])

        text = self.origin_backlog()
        self.assertIn("старая без окна", text)
        self.assertIn("новая без окна", text)
        self.assertEqual(notes.pending_notes(), [])


if __name__ == "__main__":
    unittest.main()
