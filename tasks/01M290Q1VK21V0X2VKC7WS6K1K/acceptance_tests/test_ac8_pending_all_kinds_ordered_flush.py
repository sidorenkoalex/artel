"""Приёмочный тест AC-8 задачи 01M290Q1VK21V0X2VKC7WS6K1K: удержанные
операции ВСЕХ ПЯТИ видов (`insert`, `append`, `drop`, `set-state`,
`set-priority`) сериализуются в `.artel/notes-pending` одним общим
форматом и допушиваются `--flush` В ПОРЯДКЕ СОЗДАНИЯ; `doctor` считает
их все через `notes.pending_notes()` без отдельной правки doctor.

Красен до реализации: `orchestrator.notes.cmd_note` ещё не понимает флаги
`--drop`/`--set-state`/`--set-priority` — три из пяти операций падают
до удержания вовсе.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import doctor, notes  # noqa: E402
from _sandbox import NoteSandbox, SECTION_HEADINGS, row_cells, section_rows  # noqa: E402


class AllFiveKindsPendAndFlushInOrderTest(NoteSandbox):

    def _hold(self, argv: list) -> None:
        try:
            notes.cmd_note(argv)
        except SystemExit:
            pass

    def test_ac8_five_kinds_pending_together_and_flush_applies_in_creation_order(self):
        """С недоступным `origin` по очереди выполняются `insert`,
        `--append`, `--drop`, `--set-state`, `--set-priority» — все пять
        остаются удержанными одним общим списком (`notes.pending_notes()`
        — 5 записей, ровно по одной каждого вида, в порядке создания),
        `doctor` предупреждает с числом «5» в тексте. После восстановления
        `origin` один вызов `note --flush` допушивает ВСЕ пять — origin
        несёт по одному новому коммиту на каждую операцию, В ТОМ ЖЕ
        ПОРЯДКЕ, в котором они были удержаны, и итоговое содержимое файла
        отражает все пять правок разом; `doctor` возвращается к «ok».

        Ловит мутацию: `--flush` знает только про `insert`/`append` (три
        новых вида остаются висеть после `--flush`) — тест красен на
        `assertEqual(notes.pending_notes(), [])`; либо `--flush`
        допушивает удержанные заметки не в порядке создания (например,
        группируя по виду) — тест красен на порядке `subjects`.
        """
        base_head = self.origin_head()
        self.break_origin_remote()

        self._hold(["очередь", "--text", "9 | новое действие"])
        self._hold(["--append", "КЛЮЧАППЕНД", "--text", "доп-АППЕНД-ХВОСТ"])
        self._hold(["--drop", "КЛЮЧСНЯТЬ"])
        self._hold(["--set-state", "КЛЮЧСОСТОЯНИЕ", "--text",
                   "состояние-ХВОСТ-СОСТ"])
        self._hold(["--set-priority", "КЛЮЧПРИОРИТЕТ", "--text", "2"])

        pending = notes.pending_notes()
        self.assertEqual(len(pending), 5, pending)
        self.assertEqual([p["kind"] for p in pending],
                         ["insert", "append", "drop", "set-state",
                          "set-priority"])

        check_before = doctor.check_pending_notes()
        self.assertEqual(check_before.status, "warn", check_before)
        self.assertIn("5", check_before.detail)

        self.restore_origin_remote()
        notes.cmd_note(["--flush"])

        self.assertEqual(notes.pending_notes(), [])
        self.assertEqual(doctor.check_pending_notes().status, "ok")

        subjects = self.origin_log_subjects_since(base_head)
        self.assertEqual(len(subjects), 5, subjects)
        self.assertIn("новое действие", subjects[0])
        self.assertIn("доп-АППЕНД-ХВОСТ", subjects[1])
        self.assertIn("снята:", subjects[2])
        self.assertIn("КЛЮЧСНЯТЬ", subjects[2])
        self.assertIn("состояние:", subjects[3])
        self.assertIn("состояние-ХВОСТ-СОСТ", subjects[3])

        text = self.origin_backlog()
        queue_rows = section_rows(text, SECTION_HEADINGS["очередь"])
        self.assertTrue(any("новое действие" in row for row in queue_rows))

        stash_rows = section_rows(text, SECTION_HEADINGS["копилка"])
        appended = [row for row in stash_rows if "КЛЮЧАППЕНД" in row]
        self.assertEqual(len(appended), 1)
        self.assertIn("доп-АППЕНД-ХВОСТ", row_cells(appended[0])[-1])

        self.assertFalse(any("КЛЮЧСНЯТЬ" in row for row in stash_rows))

        state_rows = [row for row in stash_rows if "КЛЮЧСОСТОЯНИЕ" in row]
        self.assertEqual(len(state_rows), 1)
        self.assertEqual(row_cells(state_rows[0])[-1], "состояние-ХВОСТ-СОСТ")

        prio_rows = [row for row in stash_rows if "КЛЮЧПРИОРИТЕТ" in row]
        self.assertEqual(len(prio_rows), 1)
        self.assertEqual(row_cells(prio_rows[0])[0], "2")


if __name__ == "__main__":
    unittest.main()
