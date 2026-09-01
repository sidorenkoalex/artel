"""AC-5 (tasks/T086/SPEC.md): потолок ожидания CI в `verifying` считается
от времени входа в состояние (`updated_at` перехода `-> verifying`), а
не от числа попыток `advance`: количество опросов, выполненных быстрее,
чем истекла конфиг-константа порядка 90 минут, к эскалации не приводит,
даже если оно больше прежних 20 попыток.

## Как тест «выполняет опросы быстрее 90 минут» без реального ожидания

`enter_verifying` (через `set_state`, `_sandbox.py`) не трогает
`tasks.updated_at` — она остаётся тем же значением, что задача получила
при заводе (секунды назад по часам теста, не намеренно состаренная).
Опросы внутри цикла `auto` идут через governed `time.sleep` (не
настоящий сон) — реальное время выполнения теста и, значит, реальный
интервал от `updated_at` остаётся исчезающе мал (доли секунды на
`OLD_ATTEMPT_LIMIT` быстрых итераций) — заведомо меньше «порядка 90
минут» из требования 3, каким бы малым ни оказался нижний край этого
«порядка». `OLD_ATTEMPT_LIMIT = 26` — на шесть больше прежнего
`LIMIT_VERIFYING_ATTEMPTS = 20` (orchestrator/config.py, до этой
задачи): переживание именно этого числа опросов без эскалации — прямая
цитата требования 3, «даже если оно больше прежних 20 попыток».

Красен до реализации: `verifying` не в `STATE_ROLE` сегодня — цикл не
делает ни одного опроса, `LoopGoverned` не бросается, `assertRaises`
падает первым же ассертом.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import auto  # noqa: E402
from _sandbox import LoopGoverned, RUNNING_RUNS, VerifyingTest  # noqa: E402

OLD_ATTEMPT_LIMIT = 26


class VerifyingTimeCeilingNotAttemptCountTest(VerifyingTest):

    def test_ac5_many_fast_polls_do_not_escalate(self):
        self.enter_verifying(RUNNING_RUNS, "[]")
        pauses = self.install_sleep_pause_governor(OLD_ATTEMPT_LIMIT)

        with self.assertRaises(LoopGoverned):
            auto.cmd_auto(self.TASK)

        self.assertGreaterEqual(len(pauses), OLD_ATTEMPT_LIMIT)
        self.assertEqual(
            self.state(), "verifying",
            f"{OLD_ATTEMPT_LIMIT} быстрых опросов (больше прежних 20 "
            f"попыток) не имеют права эскалировать задачу, пока реально "
            f"прошедшее время меньше потолка требования 3 (~90 минут) — "
            f"потолок считается по времени, не по числу advance")


if __name__ == "__main__":
    unittest.main()
