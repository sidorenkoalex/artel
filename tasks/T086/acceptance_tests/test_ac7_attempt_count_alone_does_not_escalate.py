"""AC-7 (tasks/T086/SPEC.md): `LIMIT_VERIFYING_ATTEMPTS` как жёсткое
условие эскалации из `verifying` в коде отсутствует: число попыток
`advance` в этом состоянии само по себе (без учёта прошедшего времени)
переход в `escalated` не вызывает.

Тест не читает `config.LIMIT_VERIFYING_ATTEMPTS` по имени — требование 3
SPEC прямо допускает, что константа-счётчик может либо исчезнуть из
кода, либо остаться информационной записью под другим именем
(«счётчик попыток... может сохраняться в БД/журнале, но только как
информационная запись»); тест не имеет права опираться на то, что имя
`LIMIT_VERIFYING_ATTEMPTS` вообще ещё существует в `config.py` после
реализации. `MANY_MANUAL_ADVANCES = 26` — на шесть больше прежнего
значения этой константы (20, до T086) буквальным числом, взятым из
SPEC (требование 3, «даже если оно больше прежних 20 попыток»), не из
чтения `config.*`.

Каждый вызов `advance` — быстрый (без паузы, AC-8), так что реальное
время между первым и последним вызовом остаётся исчезающе малым; ни
один разумный потолок «порядка 90 минут» (требование 3) им не задет —
единственная переменная, отличающая этот прогон от «застревания
навечно», это ЧИСЛО попыток, что и обязано ничего не решать (AC-7).

Красен до реализации: сегодняшний `_cmd_advance` (orchestrator/fsm.py)
эскалирует именно по числу попыток — `t["verifying_attempts"] >=
config.LIMIT_VERIFYING_ATTEMPTS` (20) при незелёном CI. 26 повторных
`advance` на CI, который никогда не зеленеет, эскалируют сегодня на
20-м вызове — `self.state()` станет `"escalated"` до конца цикла,
ассерт «osталась verifying» красный.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm  # noqa: E402
from _sandbox import RUNNING_RUNS, VerifyingTest  # noqa: E402

MANY_MANUAL_ADVANCES = 26


class VerifyingAttemptCountAloneDoesNotEscalateTest(VerifyingTest):

    def test_ac7_many_manual_advances_do_not_escalate_by_count_alone(self):
        self.enter_verifying(RUNNING_RUNS, "[]")

        for _ in range(MANY_MANUAL_ADVANCES):
            self.capture(fsm.cmd_advance, self.TASK)
            state = self.state()
            self.assertNotEqual(
                state, "escalated",
                f"эскалация случилась раньше {MANY_MANUAL_ADVANCES}-й "
                f"попытки — число попыток advance само по себе не имеет "
                f"права вызывать escalated (требование 3)")

        self.assertEqual(self.state(), "verifying")


if __name__ == "__main__":
    unittest.main()
