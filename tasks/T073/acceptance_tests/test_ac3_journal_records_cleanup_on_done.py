"""AC-3 (tasks/T073/SPEC.md): уборка ветки и worktree при переходе в
`done` оставляет запись в журнале задачи.

Не проверяет конкретную формулировку строки журнала (это решает
разработчик) — только факт, что среди записей `steps` этой задачи
после `approve` есть хотя бы одна с ГЛАГОЛОМ уборки («убран»/«удал»),
называющая ветку, и хотя бы одна такая же, называющая worktree.
Просто упоминание ветки не считается: запись `state -> done` уже
сегодня несёт `детали "смержено: <ветка>"` — это объявление мержа,
не факт уборки, и щедрая проверка «ветка встречается в журнале где-то»
была бы зелёной уже сейчас, до кода этой задачи (см. прогон ниже).

Красен до реализации: сегодня журнал получает только запись «worktree
убран» (`orchestrator/fsm.py` `_cmd_approve_merge_gate`, T045) — записи
об уборке ветки нет вовсе, потому что ветку до этой задачи никто не
убирает (только упоминание в `state -> done`, которое эта проверка
намеренно не засчитывает).
"""
import unittest

from _sandbox import DoneTaskTest  # noqa: E402


class JournalRecordsCleanupOnDoneTest(DoneTaskTest):

    def test_ac3_journal_has_entries_for_branch_and_worktree_cleanup(self):
        out = self.approve()
        self.assertEqual(self.state(), "done", out)

        rows = self.journal_rows()
        # Запись про УБОРКУ, не любое упоминание ветки: `state -> done`
        # тоже называет self.branch в детали "смержено: <ветка>" — это
        # объявление мержа, а не факт уборки, и не должно засчитываться
        # (иначе проверка окажется зелёной уже сегодня, до кода задачи,
        # т.е. будет проверять не тот факт, что называет AC-3).
        cleanup_rows = [r for r in rows
                       if "убран" in r["action"].lower()
                       or "убран" in r["detail"].lower()
                       or "удал" in r["action"].lower()
                       or "удал" in r["detail"].lower()]
        blob = "\n".join(f"{r['action']} {r['detail']}" for r in rows)

        branch_cleanup = [r for r in cleanup_rows
                          if self.branch in r["detail"] or self.branch in r["action"]]
        self.assertTrue(
            branch_cleanup,
            f"журнал задачи обязан нести запись об УБОРКЕ ветки {self.branch} "
            f"(не просто её упоминание в объявлении мержа):\n{blob}")

        worktree_cleanup = [r for r in cleanup_rows
                            if "worktree" in (r["action"] + r["detail"]).lower()]
        self.assertTrue(
            worktree_cleanup,
            f"журнал задачи обязан нести запись об уборке worktree:\n{blob}")

    def test_ac3_journal_untouched_when_task_not_yet_done(self):
        """Отрицательный контроль: до approve записи об уборке нет —
        она не должна появляться раньше самого перехода."""
        rows = self.journal_rows()
        blob = "\n".join(f"{r['action']} {r['detail']}" for r in rows)
        self.assertNotIn(self.branch, blob)


if __name__ == "__main__":
    unittest.main()
