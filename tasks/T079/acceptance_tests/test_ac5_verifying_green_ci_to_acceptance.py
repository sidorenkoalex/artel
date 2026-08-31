"""AC-5 (tasks/T079/SPEC.md): `advance` из `verifying` при зелёном CI
головного коммита ветки задачи переводит задачу `verifying ->
acceptance`, включая попытку автогейта `acceptance` по политике
`gates.yaml` — так же, как это происходило при входе в `acceptance` до
этой задачи.

Красен до реализации: состояния `verifying` в коде сегодня нет —
`_cmd_advance` (orchestrator/fsm.py) не содержит ветки `state ==
"verifying"` и падает в `else` («состояние {state} двигается через
approve/reject/run»), задача остаётся в `verifying`, не переходит
в `acceptance` — первый ассерт красный.

Автогейт (второй ассерт) — не мокается: `_maybe_autogate_acceptance`
(orchestrator/fsm.py) уже существует, и её точка вызова — материал этой
задачи («меняется только момент входа», требование 4), а не новый код.
Тест проверяет тот же наблюдаемый факт, что и штатный вызов на `review
-> acceptance`: журнал получает запись `"автогейт acceptance не
пройден"` с первой невыполненной причиной автогейта (пустой/отсутствующий
каталог `acceptance_tests/` — фикстура этого теста намеренно его не
заводит), дословно тем же текстом, что и существующий путь `review ->
acceptance` (`orchestrator/fsm.py::_autogate_conditions`), — без домысла
нового интерфейса.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm  # noqa: E402
from _sandbox import GREEN_RUNS, VerifyingTest  # noqa: E402


class VerifyingGreenCiToAcceptanceTest(VerifyingTest):

    def test_ac5_green_ci_transitions_to_acceptance(self):
        self.enter_verifying(GREEN_RUNS)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "acceptance",
            "зелёный CI обязан перевести verifying -> acceptance")

    def test_ac5_autogate_is_attempted_the_same_way_as_existing_entry(self):
        self.enter_verifying(GREEN_RUNS)
        since = self.last_step_id()

        self.capture(fsm.cmd_advance, self.TASK)

        details = "\n".join(self.journal_details_since(since))
        self.assertIn(
            "автогейт acceptance не пройден", details,
            "вход в acceptance из verifying обязан пытаться автогейт "
            "по gates.yaml так же, как и вход из review — журнал не "
            "несёт следов попытки")
        self.assertIn(
            "каталог приёмочных тестов пуст или отсутствует", details,
            "первая причина невыполненного автогейта (пустой "
            "acceptance_tests/ фикстуры) обязана попасть в журнал")


if __name__ == "__main__":
    unittest.main()
