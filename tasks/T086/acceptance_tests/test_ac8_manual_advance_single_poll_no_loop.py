"""AC-8 (tasks/T086/SPEC.md): ручной `artel.py advance <id>` из
`verifying` выполняет ровно один опрос статуса CI и завершается (без
цикла и без ожидания паузы) — поведение однократного вызова вне `auto`
не меняется относительно текущего.

`fsm.cmd_advance` — та же точка входа, что зовёт `artel.py advance`
(CLI не инсценируется отдельно, тем же приёмом, что и весь набор
`tasks/T079/acceptance_tests`). CI никогда не зеленеет (`RUNNING_RUNS`)
— если бы `advance` зациклился внутри самого себя (нарушение этого AC),
единственный вызов теста завис бы или отчитался бы несколькими опросами;
тест засекает оба симптома явно, не полагаясь на таймаут unittest.

Зелёный с рождения: сегодняшний `_cmd_advance` (orchestrator/fsm.py)
уже опрашивает `ci.verifying_status` РОВНО один раз за вызов и не знает
про `time.sleep` вовсе — этот критерий описывает поведение, которое
требование 5 SPEC прямо просит СОХРАНИТЬ, а не создать заново. Тест
существует, чтобы у реализации требования 1 (опрос внутри `auto`) не
было соблазна протащить цикл/паузу и в путь ручного `advance` — если
это случится, тест покраснеет и укажет на регресс.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm  # noqa: E402
from _sandbox import RUNNING_RUNS, VerifyingTest  # noqa: E402


class VerifyingManualAdvanceSinglePollNoLoopTest(VerifyingTest):

    def test_ac8_manual_advance_polls_exactly_once_and_returns(self):
        self.enter_verifying(RUNNING_RUNS, "[]")
        status_calls = self.install_verifying_status_spy()

        with mock.patch("time.sleep") as sleep_spy:
            self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            len(status_calls), 1,
            f"ручной advance обязан опросить статус CI ровно один раз, "
            f"опрошено {len(status_calls)}")
        sleep_spy.assert_not_called()
        self.assertEqual(
            self.state(), "verifying",
            "незавершённый CI (RUNNING) не имеет права сдвинуть задачу "
            "за один ручной advance")


if __name__ == "__main__":
    unittest.main()
