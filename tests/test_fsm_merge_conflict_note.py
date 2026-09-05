"""Юнит-тесты `orchestrator.fsm._merge_conflict_note` (SPEC
01M1REVMB50SND1KJ3CYQMV2ST, требование 1, AC-1..AC-3): формат `detail`
эскалации неразрешённого конфликта подтяжки — список конфликтных файлов
+ хвосты `stdout`/`stderr` `git merge`, без пустых частей.

Полный путь через `_pull_main_or_escalate` (мок FSM-песочницы, все
восемь сценариев AC-1/AC-2/AC-3/AC-5) кроют приёмочные тесты задачи
(`tasks/01M1REVMB50SND1KJ3CYQMV2ST/acceptance_tests/
test_pull_conflict_detail.py`, T023 — залочены); здесь — сама чистая
функция изолированно, без FSM-обвязки.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import fsm  # noqa: E402


def _merge(returncode: int, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(("git", "merge"), returncode, stdout, stderr)


class MergeConflictNoteTest(unittest.TestCase):

    def test_files_and_stdout_conflict_line(self):
        merge = _merge(1, stdout="CONFLICT (content): Merge conflict in module.py\n")
        note = fsm._merge_conflict_note(["module.py"], merge)
        self.assertIn("конфликтные файлы: module.py", note)
        self.assertIn("CONFLICT (content): Merge conflict in module.py", note)

    def test_multiple_files_joined_by_comma(self):
        merge = _merge(1, stdout="CONFLICT ...\n")
        note = fsm._merge_conflict_note(["docs/codebase-map.md", "other.py"], merge)
        self.assertIn("конфликтные файлы: docs/codebase-map.md, other.py", note)

    def test_stdout_truncated_to_500_chars(self):
        marker = "TAIL_END_MARKER"
        merge = _merge(1, stdout="CONFLICT (content): Merge conflict in module.py\n"
                                 + ("Z" * 600) + marker)
        note = fsm._merge_conflict_note(["module.py"], merge)
        self.assertNotIn(marker, note, "stdout не обрезан до 500 символов")
        self.assertIn("CONFLICT (content): Merge conflict in module.py", note)

    def test_nonempty_stderr_kept_alongside_stdout(self):
        merge = _merge(1, stdout="CONFLICT (content): Merge conflict in module.py\n",
                       stderr="STDERR_MARKER: warning\n")
        note = fsm._merge_conflict_note(["module.py"], merge)
        self.assertIn("STDERR_MARKER", note)
        self.assertIn("CONFLICT", note)

    def test_stderr_truncated_to_500_chars(self):
        marker = "TAIL_END_MARKER"
        merge = _merge(1, stdout="x", stderr=("Z" * 600) + marker)
        note = fsm._merge_conflict_note(["module.py"], merge)
        self.assertNotIn(marker, note, "stderr не обрезан до 500 символов")

    def test_all_empty_has_no_dangling_separators(self):
        merge = _merge(1, stdout="", stderr="")
        note = fsm._merge_conflict_note([], merge)
        self.assertFalse(note.rstrip().endswith((":", ";", ",")),
                         f"висящий разделитель в конце: {note!r}")
        self.assertNotIn("; ;", note)
        self.assertNotIn("конфликтные файлы:", note,
                         "пустой список файлов не имеет права породить "
                         "строку 'конфликтные файлы:' без имён")

    def test_merge_none_degrades_to_git_did_not_answer(self):
        note = fsm._merge_conflict_note([], None)
        self.assertEqual(note, "git не ответил")


if __name__ == "__main__":
    unittest.main()
