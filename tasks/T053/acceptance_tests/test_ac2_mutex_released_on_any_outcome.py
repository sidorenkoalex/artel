"""AC-2 (tasks/T053/SPEC.md): мьютекс освобождается при любом исходе окна
— проверены как минимум успешный merge и один отказный путь (красный CI,
конфликт подтяжки или красные приёмочные) — после которого мьютекс
свободен для следующего взятия.

Красный CI выбран как отказной путь: единственный из трёх, не требующий
настоящего git (`gitcmd.commits_behind` в песочнице `FsmTest` без
реального git молча деградирует к «не отстала», SPEC T051 AC-6 — тот же
приём, что `tasks/T052/acceptance_tests/test_ac5_red_ci_keeps_task_in_gate.py`
уже применила к соседнему критерию). Конфликт подтяжки и красные
приёмочные — тот же принцип try/finally (требование 3 SPEC), отдельным
сценарием здесь не дублируются: критерий требует «как минимум» одного
отказного пути, а не исчерпывающего перечня.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fsm  # noqa: E402

from _mutex_sandbox import MergeLockFsmTest, invoke  # noqa: E402

RED_CI = json.dumps({"total_count": 1, "check_runs": [
    {"name": "python", "status": "completed", "conclusion": "failure"}]})


class Ac2MutexFreeAfterSuccessfulMergeTest(MergeLockFsmTest):

    def test_ac2_mutex_free_after_successful_merge(self):
        invoke(lambda: fsm.cmd_approve(self.TASK))

        self.assertEqual(self.state(), "done",
                         "предпосылка теста: merge обязан пройти")
        self.assertEqual(
            self.merge_lock_rows(), [],
            "мьютекс обязан быть свободен после успешного merge")


class Ac2MutexFreeAfterRedCiRefusalTest(MergeLockFsmTest):

    def test_ac2_mutex_free_after_red_ci_refusal(self):
        self.set_ci(RED_CI)

        invoke(lambda: fsm.cmd_approve(self.TASK))

        self.assertEqual(
            self.state(), "merge_gate",
            "предпосылка теста: красный CI не должен сдвигать задачу")
        self.assertEqual(
            self.merge_lock_rows(), [],
            "мьютекс обязан освободиться и при отказе по красному CI "
            "(try/finally, требование 3)")


if __name__ == "__main__":
    import unittest
    unittest.main()
