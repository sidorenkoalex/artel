"""AC-5 (tasks/01M3EM7EFQ4X4CAYMNG35P9D7Y/SPEC.md): `kill` задачи, чья
ветка целиком содержится в main, удаляет её — и для пустой ветки (без
собственных коммитов относительно main), и для ветки, влитой мержем;
ветки нет среди локальных веток, а вывод и запись «уборка» в журнале
говорят «удалена влитая ветка <branch>».

Два независимых способа оказаться «целиком в main» — два метода:
пустая ветка (топология двух висящих поделённых родителей из
«Контекста» SPEC) и ветка, влитая `git merge --no-ff` (путь `done`).

Красен до реализации: `orchestrator/cleanup.py::drop_task_branch`
(строки 74-75) на влитой ветке возвращает «ветка <branch> оставлена:
смержена в main» и НЕ зовёт `git branch` вовсе — в обоих сценариях
ветка остаётся среди локальных, а текста «удалена влитая ветка» нет ни
в выводе, ни в журнале.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CLEANUP_ACTION, KillBranchSandbox  # noqa: E402
from orchestrator import cleanup  # noqa: E402
from tests.sandbox import capture  # noqa: E402


class KillDropsBranchContainedInMainTest(KillBranchSandbox):

    def assert_dropped_as_merged(self, out: str) -> None:
        expected = f"удалена влитая ветка {self.BRANCH}"
        self.assertNotIn(
            self.BRANCH, self.branches(),
            f"ветка, целиком содержащаяся в main, осталась среди "
            f"локальных после kill (AC-5): {self.branches()}")
        self.assertIn(
            expected, out,
            f"вывод kill не говорит «{expected}» (AC-5): {out!r}")
        notes = " | ".join(self.cleanup_notes())
        self.assertIn(
            expected, notes,
            f"запись «{CLEANUP_ACTION}» в журнале не говорит "
            f"«{expected}» (AC-5): {notes!r}")

    def test_ac5_empty_branch_is_dropped_and_named_merged(self):
        """Ветка без собственных коммитов относительно main (ровно
        ветка поделённого родителя) снимается вместе с worktree, и
        исход назван «удалена влитая ветка».

        Ловит мутацию: новое правило требования 4 применено только к
        ветке, влитой НАСТОЯЩИМ мержем (например, через `gitcmd.
        merges_between`/сравнение sha с main вместо `branch --merged`) —
        пустая ветка, формально влитая, снова остаётся на месте, и
        `doctor` (`orphans-branches`) краснеет ровно как до задачи.
        """
        self.ensure_code_worktree()

        out = capture(cleanup.cmd_kill, self.TASK)

        self.assert_dropped_as_merged(out)

    def test_ac5_branch_merged_by_a_merge_commit_is_dropped(self):
        """Ветка с собственным коммитом, влитая в main `merge --no-ff`,
        снимается тем же путём и с тем же текстом.

        Ловит мутацию: `drop_task_branch` оставлен как есть для влитой
        ветки (ранний `return` «оставлена: смержена в main» не снят), а
        новое поведение прикручено только к пути деления — kill влитой
        ветки по-прежнему не удаляет её.
        """
        self.ensure_code_worktree()
        self.commit_in_worktree("work.txt", "работа ветки задачи\n")
        self.merge_branch_into_main()

        out = capture(cleanup.cmd_kill, self.TASK)

        self.assert_dropped_as_merged(out)


if __name__ == "__main__":
    unittest.main()
