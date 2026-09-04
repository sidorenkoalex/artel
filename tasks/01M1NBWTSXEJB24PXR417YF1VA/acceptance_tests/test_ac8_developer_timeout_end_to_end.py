"""Приёмочный тест AC-8 — 01M1NBWTSXEJB24PXR417YF1VA: сценарий целиком
через реальный шаг `developer`, оборванный таймаутом.

Источник — tasks/01M1NBWTSXEJB24PXR417YF1VA/SPEC.md, «Критерии приёмки»:

AC-8. Приёмочный тест демонстрирует: при таймауте шага `developer` —
правки кода закоммичены в кодовую ветку задачи (AC-1), а `tasks/<id>/`
— в артефактной ветке, не в кодовой (AC-4).

Тот же приём, что AC-7 (`test_ac7_test_author_timeout_end_to_end.py`) и
`tasks/T041/acceptance_tests/test_checkpoint_after_timeout.py`: реальный
`runner.cmd_run` (состояние `in_dev`, `orchestrator/config.py::
STATE_ROLE`), подложный процесс агента `TimeoutThenKilledProc`.

Красен до реализации: до этой задачи `tasks/<TASK>/PLAN.md`,
недописанный агентом, коммитится в кодовую ветку ТЕМ ЖЕ коммитом, что и
`orchestrator/impl.py` (безусловный `git add -A`), и в артефактную ветку
не переносится вовсе — тест ниже ловит оба симптома по отдельности.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import MandateCheckpointTest, TimeoutThenKilledProc  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import gitcmd  # noqa: E402


class DeveloperTimeoutEndToEndTest(MandateCheckpointTest):

    def leave_wip(self) -> None:
        impl_file = self.wt / "orchestrator" / "impl.py"
        impl_file.parent.mkdir(parents=True, exist_ok=True)
        impl_file.write_text("# реализация, недописанная до таймаута\n",
                             encoding="utf-8")
        plan_file = self.wt / "tasks" / self.TASK / "PLAN.md"
        plan_file.parent.mkdir(parents=True, exist_ok=True)
        plan_file.write_text("# PLAN, недописан до таймаута\n",
                             encoding="utf-8")

    def test_ac8_developer_timeout_commits_code_and_moves_task_dir(self):
        """Реальный шаг `developer` (состояние `in_dev`), процесс агента
        обрывается таймаутом, успев оставить правку кода и черновик
        `PLAN.md` в `tasks/<id>/` — код закоммичен в кодовую ветку без
        `tasks/<id>/`, черновик `PLAN.md` оказывается в артефактной
        ветке.

        Ловит мутацию: `tasks/{self.TASK}/PLAN.md` остаётся частью
        код-коммита (мандат developer «всё кроме tasks/<id>/» перепутан
        с «вообще всё») ИЛИ вовсе не попадает в артефактную ветку.
        """
        self.enter_in_dev()
        before = self.worktree_head()

        out = self.run_agent(TimeoutThenKilledProc(
            ["агент работает, потом молчит\n"], leaves_wip=self.leave_wip))

        self.assertIn("таймаут", out)
        after = self.worktree_head()
        self.assertNotEqual(
            after, before,
            "AC-8: правка кода developer обязана попасть в кодовую "
            "ветку отдельным коммитом")
        committed = self.code_branch_committed_paths(after)
        self.assertIn(
            "orchestrator/impl.py", committed,
            f"AC-8: правка кода обязана быть в коммите — фактически "
            f"закоммичено: {committed}")
        task_paths = [p for p in committed
                     if p.startswith(f"tasks/{self.TASK}/")]
        self.assertEqual(
            task_paths, [],
            f"AC-8: tasks/<id>/ не в кодовой ветке — фактически найдено "
            f"в коммите {after}: {task_paths}")
        self.assertTrue(gitcmd.is_clean(repo=self.wt),
                        "AC-8: рабочее дерево кодовой ветки снова чистое")

        files = self.artifact_branch_task_files()
        self.assertIn(
            f"tasks/{self.TASK}/PLAN.md", files,
            f"AC-8: черновик PLAN.md обязан оказаться в артефактной "
            f"ветке — фактически там: {files}")


# AC-9: manual — CI (`.github/workflows/ci.yml`, шаг `unittest discover -s
# tests -v`) уже гоняет полный набор `tests/` на каждый пуш; дублировать
# прогон подпроцессом внутри acceptance_tests того же смысла не добавляет
# и рискует ложным красным из-за окружения этой машины (тот же довод, что
# у `tasks/T041/acceptance_tests/test_checkpoint_after_timeout.py`, AC-5,
# и у `tasks/T040/acceptance_tests`, AC-4). Число тестов «до этой задачи»
# — 1352 (`python3 -c "import unittest; print(unittest.TestLoader().
# discover('tests').countTestCases())"`, ветка
# task/01m1nbwtsxejb24pxr417yf1va-... от свежего main, 04.09.2026) —
# планка для сверки Оператором/ревьювером на приёмке, что набор не
# уменьшился и не покраснел, без повторного авто-подсчёта здесь.


if __name__ == "__main__":
    import unittest
    unittest.main()
