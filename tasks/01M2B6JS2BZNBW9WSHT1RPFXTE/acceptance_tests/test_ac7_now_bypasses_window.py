"""Приёмочный тест AC-7 задачи 01M2B6JS2BZNBW9WSHT1RPFXTE (note: окно
тишины): `note --now <раздел> --text …` записывает заметку и
отправляет её немедленно, в обход окна тишины, не кладя её в
`.artel/notes-pending/`.

Красен до реализации: `--now` сегодня не существует как флаг —
`argparse` отказывает `SystemExit`'ом «unrecognized arguments» раньше
любой логики команды; тест красен на этом же `SystemExit`, пойманном
`assertRaises` НЕ там, где ожидает тест (тест ожидает УСПЕШНОГО push,
а получает отказ разбора аргументов).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import NoteSandbox  # noqa: E402


class NowBypassesWindowTest(NoteSandbox):

    def test_ac7_now_pushes_immediately_while_window_open_and_does_not_hold(self):
        """Окно тишины открыто (задача в `acceptance`) — `--now копилка
        --text …» всё равно пушит немедленно: текст появляется в
        origin ЭТИМ ЖЕ вызовом, `.artel/notes-pending/` остаётся пустым
        (запись не удержана вовсе, не удержана-и-тут-же-отправлена).

        Ловит мутацию: `--now` записывает и удерживает как обычная
        запись при открытом окне (флаг принят, но обход не реализован)
        — тест красен на пустом `origin_backlog()` и непустом
        `pending_notes()`.
        """
        self.insert_task_in_state("acceptance")

        self.capture(
            notes.cmd_note,
            ["--now", "копилка", "--text",
             "9 | 09.09 | срочно в обход окна | orchestrator/now.py"])

        self.assertIn("срочно в обход окна", self.origin_backlog())
        self.assertEqual(notes.pending_notes(), [])


if __name__ == "__main__":
    unittest.main()
