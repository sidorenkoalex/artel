"""AC-5 — второй `approve`, дождавшийся своего в очереди, забирает окно
и доводит себя дальше ОДНИМ заходом в тело гейта (несущее подтяжку
main), без отдельного повторного захода на промежуточном состоянии
(SPEC 01M291EPQ2VFGCHZTXXC81616V).

Красен до реализации: как и AC-1, второй approve сейчас `sys.exit`'ит
немедленно на занятом мьютексе (`orchestrator/fsm_merge_gate.py:697-699`)
— `start_waiting` не дождётся первого опроса очереди, тест падает по
`AssertionError` в `start_waiting`, не по опечатке.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import merge_lock, store  # noqa: E402

from _sandbox import QueueSandbox  # noqa: E402


class SinglePullAfterQueueTest(QueueSandbox):

    def test_ac5_body_is_not_called_while_queued_and_exactly_once_after_release(self):
        """Пока задача ждёт в очереди, тело гейта (несущее подтяжку main
        `_sync_main_or_wait`/`fsm._pull_main_or_escalate`) не вызывается
        вовсе; после освобождения окна первым удерживавшей задачей —
        вызывается РОВНО один раз, не два подряд («без отдельной
        повторной подтяжки на промежуточном состоянии»).

        Ловит мутацию: механика очереди, дождавшись своего, вызывает тело
        гейта дважды подряд (например, один раз для проверки «не устарел
        ли снимок» и второй раз штатно) — `self.body_calls` будет
        `[self.TASK_B, self.TASK_B]` вместо одного элемента.
        """
        self.seed_holder(self.TASK_A, "sess-a")

        thread = self.start_waiting(self.TASK_B)
        self.assertEqual(
            self.body_calls, [],
            "тело гейта не имеет права вызываться, пока задача только "
            "ждёт своего в очереди")

        merge_lock.release(store.db(), "sess-a")
        self.proceed[self.TASK_B].set()
        thread.join(timeout=5)

        self.assertIn(self.TASK_B, self.done,
                      "второй approve обязан сам довести себя до done "
                      "после освобождения окна")
        self.assertEqual(
            self.body_calls, [self.TASK_B],
            "тело гейта обязано вызываться РОВНО один раз после того, "
            "как окно освободилось — не отдельный повторный заход на "
            "промежуточном состоянии")


if __name__ == "__main__":
    unittest.main()
