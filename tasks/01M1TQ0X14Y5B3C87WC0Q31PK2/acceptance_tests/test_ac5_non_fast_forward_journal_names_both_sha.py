"""Приёмочный тест AC-5 задачи 01M1TQ0X14Y5B3C87WC0Q31PK2: запись журнала
об отказе push при non-fast-forward называет оба sha — локальный ref
артефактной ветки и `origin/artifact/<id>` — и подсказку Оператору
«свести merge-коммитом».

Красен до реализации: `artifact_branch.push` сегодня
(`orchestrator/artifact_branch.py:130-137`) не пишет в журнал вообще
ничего ни при каком отказе — записи «push артефактной ветки FAILED» с
классификацией `non-fast-forward` в журнале нет и быть не может; тест
падает на `assertEqual(len(failed), 1, ...)` с пустым списком `failed`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import gitcmd  # noqa: E402
from _sandbox import DivergedArtifactBranchSandbox  # noqa: E402

FAILED_ACTION = "push артефактной ветки FAILED"


class NonFastForwardJournalNamesBothShaTest(DivergedArtifactBranchSandbox):

    def test_ac5_non_fast_forward_journal_names_both_sha_and_the_merge_hint(self):
        """Запись журнала об отказе non-fast-forward обязана называть И
        локальный sha артефактной ветки, И sha `origin/artifact/<id>`, И
        подсказку Оператору «свести merge-коммитом» — так, чтобы Оператор
        мог свести расхождение без раскопок git руками (приём 06.09).

        Ловит мутацию: классификация отказа сворачивает non-fast-forward
        в ту же запись/причину, что «нет origin»/«сеть» (не различает три
        случая требования 1) — тогда в `detail` не найдётся литерала
        `non-fast-forward` (или найдётся, но без одного из двух sha/без
        подсказки), тест покраснеет на соответствующей проверке
        `assertIn`.
        """
        self.run_reviewer_autocommit()

        local_sha = gitcmd.branch_head_sha(self.branch)
        origin_sha = self.origin_branch_sha(self.branch)
        self.assertNotEqual(local_sha, origin_sha,
                            "проверка бессмысленна без настоящего "
                            "расхождения локального ref и origin")

        rows = self.journal_rows(self.TASK)
        failed = [r for r in rows
                 if r["action"] == FAILED_ACTION
                 and "non-fast-forward" in r["detail"]]
        self.assertEqual(len(failed), 1,
                         f"записи журнала задачи: {[dict(r) for r in rows]}")
        detail = failed[0]["detail"]
        self.assertIn(local_sha, detail)
        self.assertIn(origin_sha, detail)
        self.assertIn("merge-коммитом", detail)


if __name__ == "__main__":
    unittest.main()
