"""Красен до реализации: `orchestrator/fsm.py::_pull_main_or_escalate`
сегодня прогоняет приёмочную планку через `acceptance.run(wt_path /
"tasks" / task_id)` — читает worktree КОДОВОЙ ветки задачи, не
артефактную ветку (SPEC «Требования» п.1-2). Оба теста этого файла кладут
ЗАВЕДОМО КРАСНЫЙ тест в worktree и ЗАВЕДОМО ЗЕЛЁНЫЙ — в артефактную
ветку: до правки задачи worktree-версия перекрывает артефактную, переход
красит/эскалирует; после правки источник — артефактная ветка, переход
обязан пройти зелёным.

AC-1 (approve из `acceptance`) и AC-2 (тот же узел, вызванный с
`state="merge_gate"` — так его вызывает `orchestrator/fsm_merge_gate.py`
изнутри окна гейта, `fsm._pull_main_or_escalate(conn, task_id, t,
state)`) — один и тот же узел `_pull_main_or_escalate`, проверенный с
двух точек входа, которые SPEC называет явно (AC-1, AC-2).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AcceptancePullSandbox, GREEN_TEST,  # noqa: E402
                      RED_TEST)
from orchestrator import fsm, store  # noqa: E402


class Ac1ApproveAcceptancePullSourceTest(AcceptancePullSandbox):

    def _seed_stale_worktree_and_green_artifact(self) -> None:
        wt = self.worktree_dir()
        tests_dir = wt / "tasks" / self.TASK / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_stale.py").write_text(RED_TEST, encoding="utf-8")

        files = dict(self.spec_requires_tests())
        files[f"tasks/{self.TASK}/acceptance_tests/test_x.py"] = GREEN_TEST
        self.commit_artifact(files)

    def test_ac1_approve_acceptance_uses_artifact_branch_not_worktree(self):
        """`approve` из `acceptance` (ветка позади main — подтяжка
        случается) читает планку из артефактной ветки задачи: worktree
        кодовой ветки несёт заведомо красный тест, артефактная ветка —
        заведомо зелёный. Переход обязан состояться (`merge_gate`),
        потому что источник — артефактная ветка.

        Ловит мутацию: `_pull_main_or_escalate` продолжает звать
        `acceptance.run(wt_path / "tasks" / task_id)` (worktree) вместо
        материализации из артефактной ветки — красный `test_stale.py`
        worktree'а эскалирует переход, и `assertEqual(self.state(),
        "merge_gate")` здесь покраснеет вместо `"escalated"`.
        """
        self._seed_stale_worktree_and_green_artifact()

        out = self.approve()

        self.assertEqual(
            self.state(), "merge_gate",
            f"переход обязан пройти по зелёной артефактной планке, "
            f"а не красной worktree-планке; вывод approve:\n{out}\n"
            f"журнал: {self.journal_details()}")

    def test_ac2_merge_gate_window_pull_uses_artifact_branch_not_worktree(self):
        """Тот же узел `_pull_main_or_escalate`, вызванный с
        `state="merge_gate"` — именно так его зовёт `orchestrator/
        fsm_merge_gate.py::_cmd_approve_merge_gate` изнутри окна гейта
        (строка `fsm._pull_main_or_escalate(conn, task_id, t, state)`).
        Тот же сценарий: красный worktree, зелёная артефактная ветка —
        исход обязан быть `"pulled"` (успех), не `"escalated"`.

        Ловит мутацию: правка применена только к точке входа `approve
        acceptance` (например, отдельной веткой кода внутри `_cmd_
        approve`, в обход общего узла), а сам `_pull_main_or_escalate`
        остался читать worktree — вызов с `state="merge_gate"` здесь
        по-прежнему вернёт `"escalated"` вместо `"pulled"`.
        """
        self._seed_stale_worktree_and_green_artifact()
        # Реалистичная предпосылка: задача уже стоит на merge_gate,
        # ровно так, как её нашёл бы `fsm_merge_gate._cmd_approve_merge_
        # gate` изнутри окна гейта — иначе `store.set_state`'s CAS
        # (expected_state=state) откажет несовпадением с фактическим
        # "acceptance", не долетев до предмета проверки этого теста.
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?",
                     ("merge_gate", self.TASK))
        conn.commit()
        t = store.get_task(conn, self.TASK)
        outcome = fsm._pull_main_or_escalate(conn, self.TASK, t,
                                             "merge_gate")

        self.assertEqual(
            outcome, "pulled",
            f"узел сверки внутри окна merge_gate обязан читать "
            f"артефактную ветку так же, как approve acceptance; "
            f"журнал: {self.journal_details()}")


if __name__ == "__main__":
    unittest.main()
