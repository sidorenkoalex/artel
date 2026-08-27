"""AC-8 (tasks/T045/SPEC.md): мутирующая команда не в своей рабочей
поверхности — отказ с подсказкой, а не выполнение.

Критерий называет обе стороны разом: «worktree своей задачи — для
агентных шагов, главная копия на main — для команд оркестратора»
(SPEC, требования 3-4 явно называют `run`/`auto` и `cmd_new`/
`merge_gate` как примеры каждой стороны) — отсюда два сценария:

1. Агентный шаг (`run`) видит worktree своей задачи, стоящий не на её
   ветке (кто-то переключил его руками) — отказ вместо запуска агента
   на чужой ветке.
2. Команда оркестратора (`approve` на гейте `merge_gate`) видит главную
   копию пульта не на `main` — отказ вместо слияния из чужого места.
"""
import unittest
from unittest import mock

from orchestrator import config, runner  # noqa: E402

from _sandbox import FakeProc, MergeGateReadyTest, WorktreeRepoTest  # noqa: E402


class AgentStepWrongBranchRefusesTest(WorktreeRepoTest):

    def test_ac8_run_refuses_when_task_worktree_is_on_a_foreign_branch(self):
        path = self.make_worktree()
        # Worktree существует по стандартному пути задачи, но кто-то
        # переключил его на постороннюю ветку — не ветку задачи.
        self.git("checkout", "-b", "intruder", cwd=path)

        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc()
            try:
                self.capture(runner.cmd_run, self.TASK)
            except SystemExit:
                pass

        popen.assert_not_called()
        branch_after = self.git("-C", str(path), "rev-parse",
                                "--abbrev-ref", "HEAD").stdout.strip()
        self.assertEqual(branch_after, "intruder",
                         "отказ не имеет права сам чинить рабочую "
                         "поверхность — только останавливать шаг")


class OrchestratorCommandWrongBranchRefusesTest(MergeGateReadyTest):

    def test_ac8_merge_gate_refuses_when_root_is_not_on_main(self):
        self.git("checkout", "-b", "operator-scratch")

        out = self.approve()

        self.assertNotEqual(self.state(), "done",
                            f"merge не должен пройти из чужой ветки "
                            f"главной копии; вывод: {out}")
        self.assertEqual(self.state(), "merge_gate",
                         "задача обязана остаться на гейте merge_gate")
        root_branch = self.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.assertEqual(root_branch, "operator-scratch",
                         "отказ не имеет права сам переключать главную "
                         "копию — только останавливать команду")
        self.assertEqual(
            self.origin_main_sha(),
            self.git("rev-parse", f"refs/heads/{config.MAIN_BRANCH}").stdout.strip(),
            "main не должен был сдвинуться — merge не выполнялся")


if __name__ == "__main__":
    unittest.main()
