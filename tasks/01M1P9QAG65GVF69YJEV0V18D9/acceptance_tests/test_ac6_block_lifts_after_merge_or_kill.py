"""Приёмочные тесты 01M1P9QAG65GVF69YJEV0V18D9 — AC-6 (SPEC.md).

Допущения интерфейса — см. докстринг `_sandbox.py` (тест бьёт по
наблюдаемому поведению `runner.cmd_run`/`auto.cmd_auto`, без внутренней
точки входа).

Красен до реализации: сегодня зоны не проверяются вовсе (см. докстринг
`test_ac1_ac2_ac3_...py`) — эти тесты сами по себе прошли бы уже сейчас
(отказа никогда не было, значит и «снятие блокировки» тривиально верно),
поэтому КАЖДЫЙ тест этого файла СНАЧАЛА подтверждает, что блокировка была
(`popen.assert_not_called()` на первом вызове), и только потом проверяет
её снятие — без этой первой половины тест был бы тавтологией, зелёной и
до, и после реализации, и не ловил бы отсутствие механики вовсе.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import ZoneSandbox  # noqa: E402

from orchestrator import runner  # noqa: E402

CONFLICT_PATH = "orchestrator/foo_zone.py"
OCCUPIER = "T901"


class Ac6BlockLiftsAfterMergeOrKillTest(ZoneSandbox):
    """AC-6: после `merge_gate -> done` (мерж) или `kill` занявшей зону
    задачи следующий `run`/`auto` заблокированной задачи проходит без
    отказа по пересечению зон.

    Ловит мутацию: диапазон блокирующих фаз читается один раз при первой
    проверке и кэшируется (занявшая задача, ушедшая из `in_dev`…
    `merge_gate`, всё ещё считается занятой) — второй вызов `run` после
    перевода занявшей задачи в `done`/`killed` продолжал бы отказывать.
    """

    def _seed_conflict(self, occupier_state: str = "in_dev") -> None:
        self.reset_task()
        self.set_own_zones(CONFLICT_PATH)
        self.seed_task(OCCUPIER, "Занявшая зону", occupier_state, CONFLICT_PATH)

    def test_ac6_run_passes_after_occupier_reaches_done(self):
        self._seed_conflict("merge_gate")

        out1, popen1 = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))
        popen1.assert_not_called()
        self.assertEqual(self.task_state(self.TASK), "in_dev",
                         f"предусловие теста не выполнено — run не был "
                         f"заблокирован занявшей зону задачей: {out1!r}")

        self.set_task_state(OCCUPIER, "done")

        out2, popen2 = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))
        self.assertTrue(
            popen2.called,
            f"run продолжает отказывать после того, как занявшая зону "
            f"задача {OCCUPIER} перешла в done: {out2!r}")

    def test_ac6_auto_passes_after_occupier_is_killed(self):
        self._seed_conflict("in_dev")

        out1, popen1 = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))
        popen1.assert_not_called()
        self.assertEqual(self.task_state(self.TASK), "in_dev",
                         f"предусловие теста не выполнено — run не был "
                         f"заблокирован занявшей зону задачей: {out1!r}")

        self.set_task_state(OCCUPIER, "killed")

        out2, popen2 = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))
        self.assertTrue(
            popen2.called,
            f"run продолжает отказывать после того, как занявшая зону "
            f"задача {OCCUPIER} убита (killed): {out2!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
