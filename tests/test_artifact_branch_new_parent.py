"""Юнит-тест R2-F3 REVIEW.md 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH итерации 2:
прямая проверка ОТСУТСТВИЯ записи в журнал задачи при первом коммите
артефактной ветки в репозитории вовсе БЕЗ `origin` — планка приёмки
задачи (`acceptance_tests/test_ac2_local_main_fallback_parent.py`)
проверяет только родителя коммита, не журнал; регрессию этого класса до
сих пор ловил только посторонний `tests/test_branch_freshness_gate.py`,
косвенно (по отсутствию стороннего `fetch`-вызова).

ANSWER-2 (`tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/ANSWER-2.md`, пункт 3):
доработка разрешена в `tests/` (общий набор), не в `acceptance_tests/`
(планка залочена test_author'ом).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artifact_branch, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

TASK = "01ACNOORIGINSILENCE1"
REASON_PREFIX = "артефактная ветка от локального main:"


class NoOriginLeavesJournalUntouchedTest(RealGitSandbox):

    def test_no_origin_leaves_journal_without_fallback_entry(self):
        """`self.root` (`RealGitSandbox`) не заводит `origin` вовсе —
        `gitcmd.has_no_remote` обязан вернуть True, и `commit_files`
        обязан пропустить и `fetch`, и запись в журнал целиком (ANSWER-2,
        п.1: запись — только когда `origin` настроен, но недостижим).

        Ловит мутацию: запись в журнал распространили и на случай
        «origin вовсе не настроен» — регрессия к буквальному прочтению
        AC-2, отклонённому эмпирически в PLAN.md («Эскалация») из-за
        конфликта с `tests/test_doctor_fix_ignored_artifacts.py`.
        """
        sha = artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/SPEC.md": "спек"}, f"{TASK}: тест")
        self.assertTrue(sha, "коммит артефактной ветки не создан")

        steps = store.task_steps(store.db(), TASK)
        matching = [s for s in steps
                   if (s["detail"] or "").startswith(REASON_PREFIX)]
        self.assertEqual(
            matching, [],
            "журнал не должен нести запись фолбэка, когда origin вовсе "
            "не настроен")


if __name__ == "__main__":
    unittest.main()
