"""Приёмочный тест AC-2 задачи 01M2B6JS2BZNBW9WSHT1RPFXTE (note: окно
тишины): при открытом окне тишины валидная запись ЛЮБОГО вида (раздел
с `--text`, `--append`, `--drop`, `--set-state`, `--set-priority`) не
пушится — уходит в `.artel/notes-pending/` вместо push, `origin` не
меняется ни разу.

Красен до реализации: `cmd_note` пушит немедленно для всех пяти видов
независимо от состояния задачи — тест красен на неизменности
`origin_head()` после первого же вызова.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import NoteSandbox  # noqa: E402


class AnyKindHeldWhenWindowOpenTest(NoteSandbox):

    def _hold(self, argv: list) -> None:
        try:
            self.capture(notes.cmd_note, argv)
        except SystemExit as exc:
            self.fail(f"валидная запись отказала на {argv}: {exc}")

    def test_ac2_all_five_kinds_held_not_pushed_when_task_in_in_dev(self):
        """Задача в `in_dev` (одно из состояний набора AC-1) держит окно
        тишины открытым на протяжении всего теста — по очереди
        выполняются все пять видов записи, каждый удерживается, origin
        не сдвигается ни на один коммит.

        Ловит мутацию: реализация проверяет окно только для вида
        `insert` (например, если ветка удержания добавлена только в
        `_apply_insert`/раннюю точку, а `--append`/`--drop`/
        `--set-state`/`--set-priority` продолжают звать `_attempt`
        напрямую) — тест красен на изменившемся `origin_head()` уже на
        втором вызове (`--append`).
        """
        self.insert_task_in_state("in_dev")
        before = self.origin_head()

        self._hold(["копилка", "--text",
                   "9 | 09.09 | вставка при окне | orchestrator/i.py"])
        self._hold(["--append", "УНИКАЛЬНЫЙКЛЮЧ", "--text", "доп-текст"])
        self._hold(["--drop", "ДРУГОЙКЛЮЧ"])
        self._hold(["--set-state", "УНИКАЛЬНЫЙКЛЮЧ", "--text", "новое состояние"])
        self._hold(["--set-priority", "УНИКАЛЬНЫЙКЛЮЧ", "--text", "3"])

        self.assertEqual(before, self.origin_head(),
                         "ни одна из пяти записей не должна дойти до push")
        pending = notes.pending_notes()
        self.assertEqual(len(pending), 5, pending)
        self.assertEqual([p["kind"] for p in pending],
                         ["insert", "append", "drop", "set-state",
                          "set-priority"])


if __name__ == "__main__":
    unittest.main()
