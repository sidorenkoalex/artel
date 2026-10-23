"""Существующий тест досылки на переходе остаётся без правок (AC-9).

Группа: разовый

Зелёный с рождения: задача ещё не меняла `tests/test_artifact_ref_sync.py`; тест держит, что реализация не «чинит» досылку правкой существующего теста (само снятие `send_pending` и зелёный прогон существующего теста — `test_push_server_retry.py`, метод `test_ac9_…`).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import changed_paths  # noqa: E402

EXISTING = "tests/test_artifact_ref_sync.py"


class ExistingResendTestUntouchedTest(unittest.TestCase):

    def test_ac9_existing_resend_test_has_no_edits(self):
        """Дифф задачи от базы не несёт `tests/test_artifact_ref_sync.py`.

        Ловит мутацию: разработчик снял `send_pending` и подогнал
        `SendAfterCommitTest` (или его докстринг) под новый код — путь
        файла появляется в диффе задачи.
        """
        self.assertNotIn(EXISTING, changed_paths())


if __name__ == "__main__":
    unittest.main()
