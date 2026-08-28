"""AC-1 (tasks/T053/SPEC.md): два конкурентных `approve` из `merge_gate`
для разных задач: ровно один исполняет merge-окно; второй получает
немедленный отказ с именем держателя (session_id) и задачей, которую он
держит; после освобождения мьютекса повторный `approve` второй задачи
проходит.

Настоящая параллельность (два процесса, зовущие `approve` одновременно)
не воспроизводима детерминированно в unittest — тот же довод, что уже
применён к самому lease в `tasks/T044/acceptance_tests/
test_lease_enforcement.py`: другая сессия, УЖЕ держащая окно, симулируется
прямой строкой в `merge_locks` (`_mutex_sandbox.py::seed_merge_lock`), а
не настоящим потоком/процессом — критерию важен наблюдаемый исход
(немедленный именованный отказ, затем успех после освобождения), не
способ порождения второй сессии.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fsm, store  # noqa: E402

from _mutex_sandbox import (CALLER_SESSION, HOLDER_HOST, HOLDER_PID,  # noqa: E402
                            HOLDER_SESSION, HOLDER_TASK, MergeLockFsmTest,
                            invoke)


class Ac1SecondApproveRefusedByNameTest(MergeLockFsmTest):

    def test_ac1_second_approve_refused_by_holder_name_and_task(self):
        self.seed_merge_lock(HOLDER_SESSION, HOLDER_PID, HOLDER_HOST,
                             store.now(), HOLDER_TASK)
        before_lock = self.merge_lock_rows()
        mark = len(self.git_spy.calls)

        output = invoke(lambda: fsm.cmd_approve(
            self.TASK, session_id=CALLER_SESSION))

        self.assertIn(
            HOLDER_SESSION, output,
            f"отказ не назвал session_id держателя мьютекса merge: {output!r}")
        self.assertIn(
            HOLDER_TASK, output,
            f"отказ не назвал задачу, которую держит мьютекс: {output!r}")
        self.assertEqual(
            self.state(), "merge_gate",
            "отказанный approve не имеет права сдвинуть задачу с гейта")
        # `confirm_fixation` (требование 1 SPEC не включает её в перечень
        # операций окна — та выполняется ДО мьютекса) сама зовёт git
        # (rev-parse/diff) даже на отказанном пути, поэтому не годится
        # сверять на ПОЛНОЕ отсутствие git-вызовов — сверяем именно на
        # отсутствие подкоманд самого окна: без них отказ обязан быть
        # немедленным (до checkout/pull/merge/push), не после.
        window_subcommands = {"checkout", "pull", "merge", "push"}
        self.assertFalse(
            window_subcommands & set(self.git_subcommands_since(mark)),
            f"отказ обязан наступить ДО операций merge-окна: "
            f"{self.git_subcommands_since(mark)!r}")
        self.assertEqual(
            self.merge_lock_rows(), before_lock,
            "отказанный вызов не имеет права взять или иначе тронуть "
            "чужой мьютекс")


class Ac1SecondApproveSucceedsAfterReleaseTest(MergeLockFsmTest):

    def test_ac1_second_approve_succeeds_once_mutex_is_released(self):
        self.seed_merge_lock(HOLDER_SESSION, HOLDER_PID, HOLDER_HOST,
                             store.now(), HOLDER_TASK)

        invoke(lambda: fsm.cmd_approve(self.TASK, session_id=CALLER_SESSION))
        self.assertEqual(
            self.state(), "merge_gate",
            "предпосылка теста: первая попытка обязана быть отказана, "
            "пока мьютекс занят")

        self.clear_merge_lock()

        invoke(lambda: fsm.cmd_approve(self.TASK, session_id=CALLER_SESSION))

        self.assertEqual(
            self.state(), "done",
            "после освобождения мьютекса повторный approve обязан "
            "выполнить merge-окно")


if __name__ == "__main__":
    import unittest
    unittest.main()
