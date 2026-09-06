"""Приёмочный тест AC-6: `tests/test_fsm_merge_conflict_note.py` не
изменён этой задачей (SPEC 01M1TKP45EM16ZMJGQKNZA5T7J, требование 2 —
по ANSWER-1, вопрос 1: файл назван в ТЗ по ошибке, требование 2 для
него считается выполненным без правки).

Зелёный с рождения: файл не входит в зону изменений этой задачи —
критерий проверяет ОТСУТСТВИЕ диффа с последнего слияния main в ветку
задачи, а не появившийся код; ничего в реализации задачи не обязано
менять этот файл, чтобы тест был зелёным с первого прогона (проверено
на диске в момент написания планки: `git diff --stat $(git merge-base
HEAD main) HEAD -- tests/test_fsm_merge_conflict_note.py` пуст).
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config  # noqa: E402

TARGET_REL = "tests/test_fsm_merge_conflict_note.py"


class MergeConflictNoteUntouchedTest(unittest.TestCase):

    def test_ac6_file_has_no_diff_since_last_main_merge(self):
        """Diff файла между последним смерженным в ветку задачи `main` и
        текущим `HEAD` пуст — задача не коснулась файла.

        Ловит мутацию: кто-то «заодно» переносит в этот файл копию
        `write_plan_ready`/`write_acceptance_plank`/`advance_from_in_dev`
        либо правит его докстринги — diff перестанет быть пустым, и
        `assertEqual` ниже поймает отличие.
        """
        merge_base = subprocess.run(
            ["git", "merge-base", "HEAD", config.MAIN_BRANCH],
            cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(merge_base.returncode, 0, merge_base.stderr)
        base_sha = merge_base.stdout.strip()

        diff = subprocess.run(
            ["git", "diff", "--stat", base_sha, "HEAD", "--", TARGET_REL],
            cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(diff.returncode, 0, diff.stderr)
        self.assertEqual(
            diff.stdout.strip(), "",
            f"{TARGET_REL} изменён относительно последнего слияния "
            f"{config.MAIN_BRANCH}: {diff.stdout}")


if __name__ == "__main__":
    unittest.main()
