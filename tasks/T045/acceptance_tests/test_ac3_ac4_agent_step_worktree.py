"""AC-3, AC-4 (tasks/T045/SPEC.md): агентный шаг задачи и её worktree.

AC-3. Агентный шаг задачи исполняется в её worktree: рабочая копия
пульта остаётся на `main` и не переключается запуском `run`/`auto`.
AC-4. Два `auto` разных задач работают одновременно без пересечения
рабочих поверхностей (проверяется смоук-тестом в песочнице).

Роль: analyst (TZ.md есть) — самый лёгкий реальный агентный шаг
(см. tests/test_analyst_role.py RunAnalystTest); `run` его и заводит
(orchestrator/runner.py `step_role`). `spawn_agent` подменён — реального
`claude` CLI нет, но git и файловая система настоящие
(tasks/T045/acceptance_tests/_sandbox.py).
"""
import threading
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import catalog, config, runner  # noqa: E402

from _sandbox import FakeProc, WorktreeRepoTest  # noqa: E402


class SingleRunWorktreeTest(WorktreeRepoTest):

    def test_ac3_agent_step_runs_in_task_worktree_root_stays_on_main(self):
        popen, _out = self.run_agent()

        popen.assert_called_once()
        cwd = popen.call_args.kwargs.get("cwd")
        self.assertIsNotNone(cwd, "агент обязан получить рабочий каталог")
        self.assertEqual(Path(cwd), self.worktree_path(),
                         "агентный шаг обязан исполняться в worktree "
                         "своей задачи, а не в рабочей копии пульта")

        root_branch = self.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.assertEqual(root_branch, config.MAIN_BRANCH,
                         "запуск run не имеет права переключать рабочую "
                         "копию пульта с main")


class TwoConcurrentAutoTest(WorktreeRepoTest):
    """AC-4: два run (эквивалент агентного шага auto/run) двух разных
    задач одновременно, без пересечения рабочих поверхностей."""

    TASK_A = "T001"
    TASK_B = "T002"

    def setUp(self):
        super().setUp()
        # Вторая задача — тем же лёгким путём (analyst, TZ.md).
        self.capture(catalog.cmd_new, "Worktree-норма Б")
        self.tdir_b = config.TASKS / self.TASK_B
        self.branch_b = self.task_row(self.TASK_B)["branch"]
        self.write_tz(task_id=self.TASK_B, tdir=self.tdir_b)

    def test_ac4_two_runs_at_once_do_not_cross_work_surfaces(self):
        barrier = threading.Barrier(2, timeout=10)
        errors: list[Exception] = []

        def fake_spawn(cmd, **kwargs):
            cwd = Path(kwargs["cwd"])
            # Заставляет оба «агентных» вызова реально пересечься во
            # времени — буквальная проверка «одновременно» из AC-4, не
            # последовательный вызов под видом параллельного.
            barrier.wait()
            (cwd / "agent-was-here.txt").write_text(str(cwd), encoding="utf-8")
            return FakeProc()

        def worker(task_id: str) -> None:
            try:
                runner.cmd_run(task_id)
            except Exception as exc:  # noqa: BLE001 — фиксируем в errors, не роняем поток
                errors.append(exc)

        with mock.patch.object(runner, "spawn_agent", fake_spawn):
            t1 = threading.Thread(target=worker, args=(self.TASK_A,))
            t2 = threading.Thread(target=worker, args=(self.TASK_B,))
            t1.start()
            t2.start()
            t1.join(timeout=15)
            t2.join(timeout=15)

        self.assertEqual(errors, [], f"агентные шаги упали: {errors}")
        self.assertFalse(t1.is_alive())
        self.assertFalse(t2.is_alive())

        marker_a = self.worktree_path(self.TASK_A) / "agent-was-here.txt"
        marker_b = self.worktree_path(self.TASK_B) / "agent-was-here.txt"
        self.assertTrue(marker_a.exists(),
                        "шаг задачи А не оставил след в СВОЕМ worktree")
        self.assertTrue(marker_b.exists(),
                        "шаг задачи Б не оставил след в СВОЕМ worktree")
        self.assertEqual(marker_a.read_text(encoding="utf-8"),
                         str(self.worktree_path(self.TASK_A)),
                         "агент задачи А получил чужой рабочий каталог")
        self.assertEqual(marker_b.read_text(encoding="utf-8"),
                         str(self.worktree_path(self.TASK_B)),
                         "агент задачи Б получил чужой рабочий каталог")

        root_marker = self.root / "agent-was-here.txt"
        self.assertFalse(root_marker.exists(),
                         "ни один агентный шаг не имеет права писать в "
                         "рабочую копию пульта")
        root_branch = self.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.assertEqual(root_branch, config.MAIN_BRANCH)


if __name__ == "__main__":
    unittest.main()
