"""AC-1 (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md): «При успешной правке
команда коммитит изменения каталога acceptance_tests/ в ветку задачи,
обновляет tests_locked_sha на sha нового коммита и пишет журнальное
событие (actor=operator) с прежним sha, новым sha и основанием
(--reason).»

Красен до реализации: `_sandbox.discover_amend_command_name()` падает
`AssertionError` — новой команды правки планки в таблице диспетчера
`orchestrator/artel.py::main` ещё нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AC_TEST_AMENDED_V1, AmendSandbox  # noqa: E402


class SuccessfulAmendTest(AmendSandbox):

    def test_ac1_amend_commits_updates_lock_and_journals_reason(self):
        """Задача доведена до in_dev (лок стоит), Оператор правит
        содержимое acceptance_tests/test_ac.py прямо в worktree (без
        коммита) и вызывает команду с непустым основанием — правка
        обязана: (1) появиться новым коммитом на ветке задачи, (2)
        сдвинуть tests_locked_sha на sha этого коммита, (3) оставить в
        журнале запись actor=operator, называющую и старый, и новый sha,
        и переданное основание.

        Ловит мутацию: команда коммитит правку, но забывает вызвать
        `store.update_task(..., tests_locked_sha=...)` (лок остаётся на
        старом sha) — либо пишет журнал без основания/старого-нового sha,
        либо журналирует actor, отличный от "operator".
        """
        old_locked = self.enter_in_dev()
        self.write_acceptance_tests(AC_TEST_AMENDED_V1)
        reason = "правка опечатки теста (инцидент 03.09)"

        self.run_amend(reason=reason)

        new_locked = self.row()["tests_locked_sha"]
        self.assertNotEqual(
            new_locked, old_locked,
            "tests_locked_sha не сдвинулся на новый коммит правки")
        self.assertEqual(
            new_locked, self.head(),
            "tests_locked_sha должен указывать на sha нового коммита"
            " HEAD ветки задачи")

        journal_entries = self.conn.execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? "
            "ORDER BY id DESC", (self.TASK,)).fetchall()
        candidates = [r for r in journal_entries if r["actor"] == "operator"
                     and old_locked in (r["detail"] or "")
                     and new_locked in (r["detail"] or "")]
        self.assertTrue(
            candidates,
            "нет журнальной записи actor=operator, называющей и старый "
            f"({old_locked}), и новый ({new_locked}) sha; записи: "
            f"{[dict(r) for r in journal_entries]}")
        self.assertTrue(
            any(reason in (r["detail"] or "") for r in candidates),
            "журнальная запись правки не несёт переданное основание "
            f"«{reason}»")


if __name__ == "__main__":
    unittest.main()
