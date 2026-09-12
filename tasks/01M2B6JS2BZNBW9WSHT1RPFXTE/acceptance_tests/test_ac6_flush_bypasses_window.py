"""Приёмочный тест AC-6 задачи 01M2B6JS2BZNBW9WSHT1RPFXTE (note: окно
тишины): `note --flush` отправляет все записи из
`.artel/notes-pending/` независимо от того, открыто ли в момент вызова
окно тишины (явный обход решением Оператора).

Красен до реализации: `--flush` сегодня уже отправляет всё удержанное
(без понятия окна) — но AC-8/требование 7 этой же задачи заставляет
оппортунистический допуш В НАЧАЛЕ `cmd_note` уважать окно и НЕ
отправлять удержанное, когда оно открыто; наивная реализация, которая
заводит окно ОДНОЙ проверкой на весь `cmd_note` (включая ветку
`--flush`), молча ломает именно этот АС — тест красен на непустом
`notes.pending_notes()` после `--flush`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import NoteSandbox  # noqa: E402


class FlushBypassesWindowTest(NoteSandbox):

    def test_ac6_flush_pushes_held_note_while_window_stays_open(self):
        """Заметка удержана (окно открыто задачей в `review`), окно
        ОСТАЁТСЯ открытым (та же задача, то же состояние) на момент
        вызова `--flush» — явный `--flush` всё равно допушивает её:
        origin несёт текст, `pending_notes()` пустеет.

        Ловит мутацию: `--flush` делегирует тому же оппортунистическому
        флашу, что уважает окно (требование 7/АС-8), вместо отдельного
        безусловного пути — тест красен на непустом `pending_notes()`
        после вызова.
        """
        self.insert_task_in_state("review")
        try:
            self.capture(
                notes.cmd_note,
                ["копилка", "--text",
                 "9 | 09.09 | удержится до флаша | orchestrator/f.py"])
        except SystemExit:
            pass
        self.assertEqual(len(notes.pending_notes()), 1,
                         "предусловие: запись должна быть удержана")

        self.capture(notes.cmd_note, ["--flush"])

        self.assertIn("удержится до флаша", self.origin_backlog())
        self.assertEqual(notes.pending_notes(), [])


if __name__ == "__main__":
    unittest.main()
