"""AC-5 (tasks/T050/SPEC.md): вызыватели `set_state` в `orchestrator/
fsm.py` (advance, approve, эскалации, возвраты, merge) передают
состояние, прочитанное на входе в свою команду, а не свежепрочитанное
прямо перед вызовом `set_state`.

## Как проверяется без знания внутренностей реализации

В однопоточном прогоне «прочитать состояние в начале функции» и
«перечитать состояние прямо перед вызовом `set_state`» дают ОДИНАКОВОЕ
значение — разница проявляется только под гонкой. Поэтому здесь
имитируется гонка: `_race.single_shot_state_race` (см. этот файл)
патчит `store.get_task` так, что первый же его вызов внутри команды
переводит `tasks.state` в decoy-значение — как будто конкурентная
сессия успела сходить между чтением состояния командой и вызовом
`set_state`.

- Вызыватель, использующий состояние, прочитанное ПЕРВЫМ вызовом
  `store.get_task` (требование 5 соблюдено), передаёт его в
  `expected_state`; фактическое состояние в БД к этому моменту уже decoy
  — CAS расходится, переход не применяется, decoy остаётся нетронутым.
- Вызыватель, который читает состояние ЕЩЁ РАЗ прямо перед `set_state`
  (нарушение требования 5), увидит decoy как «текущее», передаст его как
  `expected_state`, CAS совпадёт с самим собой — и переход молча
  применится ПОВЕРХ decoy, будто гонки не было.

Итоговое состояние строки после вызова однозначно отличает эти два
случая — тест смотрит только на него, а не на то, как вызыватель нашёл
`expected_state`.

Песочница — `tests.test_invariants.FsmTest` (git заглушен целиком,
`orchestrator/fsm.py` работает по-настоящему) тем же приёмом, что
`tasks/T044/acceptance_tests/test_lease_enforcement.py`.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402

from _race import single_shot_state_race  # noqa: E402

DECOY = "spec_writing"


def _invoke_ignoring_failure(call) -> None:
    """Отказ CAS уходит либо исключением, либо возвратом (SPEC требование
    3 не фиксирует форму) — тест интересует только итоговое состояние
    строки в БД, не то, как именно вызыватель сообщил об отказе."""
    try:
        call()
    except BaseException:
        pass


class Ac5NoStaleRereadBeforeSetStateTest(FsmTest):

    def test_ac5_reject_uses_the_state_read_at_entry(self):
        """«Возврат»: reject из acceptance -> in_dev."""
        self.set_state("acceptance", accept_rejects=0)

        with single_shot_state_race(self.TASK, DECOY):
            _invoke_ignoring_failure(
                lambda: fsm.cmd_reject(self.TASK, "причина"))

        self.assertEqual(
            self.state(), DECOY,
            "reject применил переход поверх состояния, прочитанного "
            "заново прямо перед CAS, а не того, что было на входе")

    def test_ac5_advance_escalation_uses_the_state_read_at_entry(self):
        """«Эскалация»: advance из review со статусом escalate."""
        self.set_state("review", reviewed_iter=0)
        self.write_review("escalate", 1)

        with single_shot_state_race(self.TASK, DECOY):
            _invoke_ignoring_failure(lambda: fsm.cmd_advance(self.TASK))

        self.assertEqual(self.state(), DECOY)

    def test_ac5_advance_uses_the_state_read_at_entry(self):
        """«advance»: review -> acceptance по approved-вердикту."""
        self.set_state("review", reviewed_iter=0)
        self.write_review("approved", 1)

        with single_shot_state_race(self.TASK, DECOY):
            _invoke_ignoring_failure(lambda: fsm.cmd_advance(self.TASK))

        self.assertEqual(self.state(), DECOY)

    def test_ac5_approve_uses_the_state_read_at_entry(self):
        """«approve»: spec_gate -> in_dev (SPEC schema_version 1, без
        AC-разметки — простейшая ветка approve, без лишней подготовки)."""
        self.set_state("spec_gate")
        self.write_spec("ready")

        with single_shot_state_race(self.TASK, DECOY):
            _invoke_ignoring_failure(lambda: fsm.cmd_approve(self.TASK))

        self.assertEqual(self.state(), DECOY)

    def test_ac5_merge_uses_the_state_read_at_entry(self):
        """«merge»: merge_gate -> done, тем же сценарием, что
        tests/test_invariants.py::MergeOnlyFromMergeGateTest
        .test_merge_gate_approve_is_that_path."""
        self.write_spec("ready")
        self.write_plan("ready")
        self.write_review("approved", 1)
        self.set_state("merge_gate")

        with single_shot_state_race(self.TASK, DECOY):
            _invoke_ignoring_failure(lambda: fsm.cmd_approve(self.TASK))

        self.assertEqual(self.state(), DECOY)


if __name__ == "__main__":
    unittest.main()
