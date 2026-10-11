"""AC-7 (tasks/T087/SPEC.md): подтверждённо красный статус CI (после
однократного авто-ре-рана T082) в любой точке цикла ожидания
останавливает `approve` отказом; задача остаётся в состоянии
`merge_gate`.

Источник — tasks/T087/SPEC.md, «Критерии приёмки», AC-7.

«Подтверждённо красный» — тот же критерий, что уже вводит T082
(`ci.status_kind(note) == "red"` плюс ре-ран, всё ещё красный): требование
12 переиспользует его без изменений, тест мокает `ci.branch_status`
(красный первый ответ, красный ре-ран) и `ci.trigger_rerun` (не даёт
уйти в реальный `gh`) — тот же боундари, что `tasks/T082/
acceptance_tests/test_ci_flake_rerun.py::test_ac16_...` уже проверяет
для одноразового (без цикла ожидания) варианта гейта; здесь предмет —
что то же самое верно и «в любой точке цикла ожидания» (после нескольких
«идёт»/«неизвестен» итераций, не только на первом чтении).

Красен до реализации: сегодня нет цикла ожидания вовсе — после
"pulled" `approve` останавливается СРАЗУ сообщением "дождись зелёного
CI... и повтори", `ci.branch_status`/`ci.trigger_rerun` не вызываются в
этом вызове (`orchestrator/fsm.py`). `assertGreaterEqual(calls, N)` ниже
ловит это явно (0 вызовов < ожидаемых), а не молча пропускает как
«и так вроде осталось на гейте».
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import MergeGateCiWaitTest, RED, RUNNING  # noqa: E402


class Ac7ConfirmedRedStopsWaitTest(MergeGateCiWaitTest):

    def setUp(self):
        super().setUp()
        self.enter_merge_gate()
        self.patch_trigger_rerun()

    def test_ac7_red_on_first_check_stops_approve(self):
        self.add_main_commit()
        self.patch_branch_status(lambda branch: RED)

        with self.assertRaises(SystemExit) as exit_:
            self.approve()

        self.assertIn(
            "отклонён", str(exit_.exception),
            f"AC-7: отказ обязан быть именованным ({str(exit_.exception)!r})")
        self.assertEqual(
            self.state(), "merge_gate",
            "AC-7: подтверждённо красный статус обязан оставить задачу "
            "на гейте merge_gate, не сдвигать её в done")

    def test_ac7_red_after_several_running_iterations_stops_approve(self):
        self.add_main_commit()
        responses = [RUNNING, RUNNING, RED, RED]
        calls = {"n": 0}

        def sequenced(branch):
            resp = responses[min(calls["n"], len(responses) - 1)]
            calls["n"] += 1
            return resp

        self.patch_branch_status(sequenced)

        with self.assertRaises(SystemExit):
            self.approve()

        self.assertGreaterEqual(
            calls["n"], 3,
            f"AC-7: отказ обязан наступить ПОСЛЕ нескольких «ещё идёт» "
            f"итераций, не вместо них — прочитано {calls['n']} статусов")
        self.assertEqual(
            self.state(), "merge_gate",
            "AC-7: подтверждённо красный статус в любой точке цикла "
            "ожидания обязан оставить задачу на гейте merge_gate")


if __name__ == "__main__":
    import unittest
    unittest.main()
