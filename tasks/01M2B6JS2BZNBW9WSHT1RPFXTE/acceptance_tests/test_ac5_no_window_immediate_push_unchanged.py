"""Приёмочный тест AC-5 задачи 01M2B6JS2BZNBW9WSHT1RPFXTE (note: окно
тишины): без открытого окна тишины (нет живого держателя `merge_locks`
и ни одна задача не в состояниях набора АС-1) поведение `note` не
меняется — немедленный push в `origin`, как сегодня.

Зелёный с рождения: без единого написанного изменения `cmd_note` уже
пушит немедленно в отсутствие держателя `merge_locks` и задач в БД —
это байт-в-байт сегодняшнее поведение, тест защищает его от регрессии,
которую могла бы внести будущая реализация окна тишины (например,
слишком широкая проверка состояний).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import NoteSandbox  # noqa: E402


class NoWindowImmediatePushTest(NoteSandbox):

    def test_ac5_no_tasks_no_merge_lock_pushes_immediately(self):
        """Пустая БД (ни задач, ни держателя мьютекса) — вставка уходит
        в origin тем же вызовом, `.artel/notes-pending/` остаётся
        пустым.

        Ловит мутацию: реализация держит запись всегда, независимо от
        окна (перевёрнутое условие удержания) — тест красен на
        отсутствии текста в `origin_backlog()`.
        """
        self.capture(notes.cmd_note,
                     ["копилка", "--text",
                      "9 | 09.09 | без окна | orchestrator/no-window.py"])

        self.assertIn("без окна", self.origin_backlog())
        self.assertEqual(notes.pending_notes(), [])

    def test_ac5_task_in_escalated_state_does_not_open_window(self):
        """`escalated` НЕ входит в набор состояний АС-1 (тот набор — ровно
        `in_dev`/`verifying`/`review`/`acceptance`/`merge_gate`) — задача
        в этом состоянии, без держателя `merge_locks`, не открывает окно:
        push всё равно немедленный.

        Ловит мутацию: реализация по ошибке берёт готовый набор
        `zone_lock.BLOCKING_STATES` (тот несёт ШЕСТЬ состояний, включая
        `escalated`) вместо отдельной константы АС-1 — тест красен на
        удержанной записи в `pending_notes()`.
        """
        self.insert_task_in_state("escalated")

        self.capture(notes.cmd_note,
                     ["копилка", "--text",
                      "9 | 09.09 | эскалация не окно | orchestrator/esc.py"])

        self.assertIn("эскалация не окно", self.origin_backlog())
        self.assertEqual(notes.pending_notes(), [])


if __name__ == "__main__":
    unittest.main()
