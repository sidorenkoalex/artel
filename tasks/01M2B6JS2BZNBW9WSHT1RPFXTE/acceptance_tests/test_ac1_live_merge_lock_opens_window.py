"""Приёмочный тест AC-1 задачи 01M2B6JS2BZNBW9WSHT1RPFXTE (note: окно
тишины): держатель мьютекса `merge_locks` живой И при этом НИ ОДНА
задача не в состояниях набора (`in_dev`/`verifying`/`review`/
`acceptance`/`merge_gate`) — окно тишины всё равно открыто (условие
ИЛИ, AC-1), валидная запись удерживается, а не пушится.

Красен до реализации: `orchestrator.notes.cmd_note` сегодня не смотрит
ни на `merge_locks`, ни на состояния задач вовсе — любая валидная
запись уходит в push немедленно независимо от держателя мьютекса; тест
красен на `self.assertEqual(before, self.origin_head())`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import NoteSandbox  # noqa: E402


class LiveMergeLockAloneOpensWindowTest(NoteSandbox):

    def test_ac1_live_merge_lock_without_any_task_in_state_set_holds_note(self):
        """Живой держатель `merge_locks` — единственный триггер окна
        тишины в этом сценарии (задач в БД нет вовсе, `store.all_tasks`
        пуст): валидная запись копилки не пушится, а кладётся в
        `.artel/notes-pending/`, origin не меняется.

        Ловит мутацию: реализация проверяет только `store.all_tasks` и
        игнорирует `merge_locks` (ветку ИЛИ теряет) — при пустом наборе
        задач такая версия ошибочно решает, что окно закрыто, и
        пушит немедленно; тест красен на неизменности `origin_head()`.
        """
        self.set_live_merge_lock()
        before = self.origin_head()

        self.capture(notes.cmd_note,
                     ["копилка", "--text",
                      "9 | 09.09 | новое при живом держателе | orchestrator/n.py"])

        self.assertEqual(before, self.origin_head(),
                         "origin не должен измениться при открытом окне")
        pending = notes.pending_notes()
        self.assertEqual(len(pending), 1, pending)
        self.assertEqual(pending[0]["kind"], "insert")


if __name__ == "__main__":
    unittest.main()
