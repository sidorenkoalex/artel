"""Приёмочный тест AC-8 задачи 01M1VBEHTDYPK3E4RRFHWYYYW3: повторный
вызов `note` (в т.ч. `note --flush`) допушивает удержанный коммит —
`doctor` перестаёт предупреждать после успешной отправки.

Красен до реализации: `orchestrator.notes` ещё не существует — импорт
падает `ModuleNotFoundError`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import doctor, notes  # noqa: E402
from _sandbox import NoteSandbox  # noqa: E402


class FlushPendingTest(NoteSandbox):

    def _hold_one_pending_note(self) -> None:
        self.break_origin_remote()
        try:
            notes.cmd_note(["копилка", "--text",
                            "9 | 09.09 | удержится | orchestrator/held.py"])
        except SystemExit:
            pass
        self.assertEqual(len(notes.pending_notes()), 1,
                         "предусловие: должна остаться ровно одна удержанная заметка")

    def test_ac8_flush_pushes_held_commit_and_doctor_stops_warning(self):
        """`note --flush` с восстановленным `origin` допушивает ранее
        удержанный коммит: строка появляется в origin, `pending_notes()`
        пустеет, `doctor.check_pending_notes()` возвращается к «ok».

        Ловит мутацию: `--flush` только читает состояние удержанных
        заметок, не пытается их допушить — `pending_notes()` остаётся
        непустым после вызова.
        """
        self._hold_one_pending_note()
        self.restore_origin_remote()

        notes.cmd_note(["--flush"])

        self.assertIn("удержится", self.origin_backlog())
        self.assertEqual(notes.pending_notes(), [])
        self.assertEqual(doctor.check_pending_notes().status, "ok")

    def test_ac8_plain_note_call_also_flushes_previously_pending(self):
        """Требование 7 SPEC: «повторный вызов note (в т.ч. note --flush,
        БЕЗ --text)» — обычный `note <раздел> --text ...` (не только
        `--flush`) тоже допушивает ранее удержанную заметку, если origin
        снова доступен: обе строки (старая удержанная и новая) в итоге
        оказываются в origin одним заходом.

        Ловит мутацию: обычный вызов `note` занимается только СВОЕЙ новой
        строкой и не трогает `pending_notes()` — старая заметка осталась
        бы удержанной после успешного нового вызова.
        """
        self._hold_one_pending_note()
        self.restore_origin_remote()

        notes.cmd_note(["очередь", "--text", "9 | новое действие"])

        text = self.origin_backlog()
        self.assertIn("удержится", text)
        self.assertIn("новое действие", text)
        self.assertEqual(notes.pending_notes(), [])


if __name__ == "__main__":
    unittest.main()
