"""Юнит-тесты подтипа не-зелёного статуса CI на гейте `merge_gate`
(SPEC T082, ревью итерации 2, замечание major 1).

`tasks/T082/acceptance_tests/test_ci_flake_rerun.py` (AC-14..17) кроет
только сценарий, где `ci.branch_status` возвращает РЕАЛЬНО красный статус
(«не зелёный: python=failure») — ре-ран и flake-rate там уместны. Этот
модуль кроет случаи, которые до итерации 2 попадали в ту же ветку кода
ошибочно: «CI ещё идёт» и «статус неизвестен» — для них нет что
подтверждать ре-раном, гейт обязан отказать как раньше, БЕЗ вызова
`ci.trigger_rerun` и БЕЗ записи «подтверждённый красный» в flake-rate.

С SPEC 01M1NBWPKNBXP9ZXXQDJM7AXPJ (AC-5..AC-7) путь "fresh" на входе в
merge_gate больше не отказывает по ОДНОМУ опросу `ci.branch_status`, а
ждёт циклом `_wait_for_branch_ci_green` (как и путь "pulled") до истечения
`config.MERGE_GATE_CI_WAIT_CEILING_SEC` — `time.sleep`/`time.monotonic`
здесь заглушены `FakeClock` (тот же приём, что `tests/
test_merge_gate_ci_wait.py`), иначе тест реально ждал бы часами. Итог
неизменного класса поведения («running»/«unknown» не подлежат ре-рану,
flake-rate не пишется) сохраняется — меняется только то, что перед
финальным отказом гейт теперь опрашивает статус многократно, не единожды.
"""
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import ci, fsm, store  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402

RUNNING = (False, "CI коммита abc12345 ещё идёт: guard")
UNKNOWN = (False, "статус CI коммита abc12345 неизвестен: gh не ответил")


class FakeClock:
    """Тот же приём, что `tests/test_merge_gate_ci_wait.py::FakeClock`:
    `sleep(s)` продвигает `monotonic()` на `s` вместо настоящего ожидания."""

    def __init__(self, start: float = 0.0):
        self.value = start

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class NonRedStatusSkipsRerunTest(FsmTest):

    def setUp(self):
        super().setUp()
        self.write_spec("ready")
        self.write_plan("ready")
        self.write_review("approved", 1)
        self.set_state("merge_gate")
        self.clock = FakeClock()
        sleep_patcher = mock.patch.object(time, "sleep", self.clock.sleep)
        sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)
        monotonic_patcher = mock.patch.object(time, "monotonic",
                                              self.clock.monotonic)
        monotonic_patcher.start()
        self.addCleanup(monotonic_patcher.stop)

    def journal_blob(self) -> str:
        rows = store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,)).fetchall()
        return "\n".join(f"{r['action']} | {r['detail']}" for r in rows).lower()

    def approve_with(self, status: tuple) -> mock.Mock:
        mocked = mock.Mock(return_value=status)
        status_patcher = mock.patch.object(ci, "branch_status", mocked)
        status_patcher.start()
        self.addCleanup(status_patcher.stop)
        rerun_patcher = mock.patch.object(
            ci, "trigger_rerun",
            mock.Mock(side_effect=AssertionError(
                "ci.trigger_rerun не должен звонить для не-красного "
                "статуса (running/unknown) — там нечего подтверждать")))
        rerun_patcher.start()
        self.addCleanup(rerun_patcher.stop)
        with self.assertRaises(SystemExit):
            self.capture(fsm.cmd_approve, self.TASK)
        return mocked

    def test_still_running_does_not_trigger_a_rerun(self):
        mocked = self.approve_with(RUNNING)

        self.assertGreater(
            mocked.call_count, 1,
            "«CI ещё идёт» не подлежит ре-рану, но обязано ждать циклом "
            "(SPEC 01M1NBWPKNBXP9ZXXQDJM7AXPJ, AC-7): один опрос "
            "означало бы возврат к немедленному отказу")
        self.assertEqual(self.state(), "merge_gate")
        self.assertNotIn("flake-rate", self.journal_blob())

    def test_unknown_status_does_not_trigger_a_rerun(self):
        mocked = self.approve_with(UNKNOWN)

        self.assertGreater(
            mocked.call_count, 1,
            "статус «неизвестен» не подлежит ре-рану, но обязан ждать "
            "циклом (SPEC 01M1NBWPKNBXP9ZXXQDJM7AXPJ, AC-7): один опрос "
            "означало бы возврат к немедленному отказу")
        self.assertEqual(self.state(), "merge_gate")
        self.assertNotIn("flake-rate", self.journal_blob())


if __name__ == "__main__":
    unittest.main()
