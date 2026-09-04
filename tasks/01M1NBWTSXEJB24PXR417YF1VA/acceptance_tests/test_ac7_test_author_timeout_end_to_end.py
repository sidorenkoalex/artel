"""Приёмочный тест AC-7 — 01M1NBWTSXEJB24PXR417YF1VA: сценарий целиком
через реальный шаг `test_author`, оборванный таймаутом.

Источник — tasks/01M1NBWTSXEJB24PXR417YF1VA/SPEC.md, «Критерии приёмки»:

AC-7. Приёмочный тест демонстрирует: при таймауте шага `test_author` с
незакоммиченной правкой в `orchestrator/` — правка не попадает в
кодовую ветку задачи (откачена по AC-2/AC-3), а артефакты роли из
`tasks/<id>/` оказываются в артефактной ветке (AC-4).

В отличие от `test_ac2_*`/`test_ac4_*` (вызов `checkpoint.
commit_timeout_checkpoint` напрямую), здесь сценарий идёт через
НАСТОЯЩИЙ `runner.cmd_run`: задача реально доведена до состояния
`tests_writing` (`orchestrator/config.py::STATE_ROLE` — эта роль
запускается именно там), процесс агента — подложный
`TimeoutThenKilledProc`, чекпоинт вызывается ровно так, как его вызывает
`orchestrator/runner.py` на обрыве шага (`runner.py`, ветка `timed_out`).
Тот же приём и довод, что у `tasks/T041/acceptance_tests/
test_checkpoint_after_timeout.py` (докстринг модуля) — критерий говорит
именно про «таймаут шага `test_author`», а не про изолированный вызов
функции чекпоинта.

Красен до реализации: как и `test_ac2_*`/`test_ac4_*`, до этой задачи
`commit_timeout_checkpoint` не различает роль и не переносит `tasks/
<id>/` в артефактную ветку — правка `orchestrator/answer.py` осталась
бы в кодовой ветке, а `tasks/<TASK>/acceptance_tests/test_wip.py`
пропал бы из артефактной ветки (см. докстринги `test_ac1_*.py`,
`test_ac4_*.py` для того же класса дефекта по отдельности).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import MandateCheckpointTest, TimeoutThenKilledProc  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import gitcmd  # noqa: E402


class TestAuthorTimeoutEndToEndTest(MandateCheckpointTest):

    def leave_wip(self) -> None:
        orch_file = self.wt / "orchestrator" / "answer.py"
        orch_file.parent.mkdir(parents=True, exist_ok=True)
        orch_file.write_text(
            "# заглушка реализации, вне мандата test_author\n",
            encoding="utf-8")
        task_file = self.wt / "tasks" / self.TASK / "acceptance_tests" / "test_wip.py"
        task_file.parent.mkdir(parents=True, exist_ok=True)
        task_file.write_text("# черновик теста, не дописан\n",
                             encoding="utf-8")

    def test_ac7_test_author_timeout_discards_code_and_moves_task_dir(self):
        """Реальный шаг `test_author` (состояние `tests_writing`), процесс
        агента обрывается таймаутом, успев оставить правку в
        `orchestrator/` и черновик в `tasks/<id>/acceptance_tests/` —
        правка не попадает в кодовую ветку, черновик оказывается в
        артефактной ветке.

        Ловит мутацию: любая из двух половин связки не выполнена —
        `orchestrator/answer.py` остаётся в кодовой ветке ИЛИ
        `tasks/{self.TASK}/acceptance_tests/test_wip.py` не появляется в
        артефактной ветке.
        """
        self.enter_tests_writing()
        before = self.worktree_head()

        out = self.run_agent(TimeoutThenKilledProc(
            ["агент работает, потом молчит\n"], leaves_wip=self.leave_wip))

        self.assertIn("таймаут", out)
        self.assertEqual(
            self.worktree_head(), before,
            "AC-7: HEAD кодовой ветки не сдвинут — мандат test_author "
            "не несёт ни одного пути кодовой ветки")
        self.assertTrue(
            gitcmd.is_clean(repo=self.wt),
            "AC-7: рабочее дерево кодовой ветки снова чистое — правка "
            "вне мандата откачена, а не оставлена висеть")

        files = self.artifact_branch_task_files()
        self.assertIn(
            f"tasks/{self.TASK}/acceptance_tests/test_wip.py", files,
            f"AC-7: черновик артефакта роли обязан оказаться в "
            f"артефактной ветке — фактически там: {files}")


if __name__ == "__main__":
    import unittest
    unittest.main()
