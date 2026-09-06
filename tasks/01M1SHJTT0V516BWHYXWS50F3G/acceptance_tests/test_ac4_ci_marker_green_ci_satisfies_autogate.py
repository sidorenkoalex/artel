"""AC-4: автогейт считает критерий с пометкой `ci` исполненным, если CI
головы КОДОВОЙ ветки задачи зелёный по данным, которые уже собирает
`orchestrator/ci.py` (sha головы ветки — той, для которой CI зелёный) —
без повторного запуска `tests/` самим пультом.

Красен до реализации: сегодня `_autogate_conditions` не обращается к
`orchestrator/ci.py` вовсе (модуль даже не импортирован в
`fsm_autogate.py`, `guard.scan_ac_content` до AC-1 не распознаёт пометку
`ci` как валидный `kind`) — переход `acceptance -> merge_gate` в этом
тесте сегодня ФОРМАЛЬНО тоже происходит (нераспознанная пометка читается
как отсутствие пометки, условие «а» пусто проходит), но проверка ниже
намеренно ловит не только конечное состояние, а и сам факт обращения к
`ci.gh` — до реализации AC-4 этот вызов не происходит вовсе, и
`self.assertTrue(gh_mock.called, ...)` красит тест.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AutogateCiMarkerSandbox, ci_only_planka  # noqa: E402


class Ac4CiMarkerGreenCiSatisfiesAutogateTest(AutogateCiMarkerSandbox):

    def test_ac4_green_ci_of_code_branch_head_satisfies_ci_marker(self):
        """Планка несёт единственную пометку `# AC-2: ci`, а CI
        головного коммита КОДОВОЙ ветки задачи (`self.branch`, не
        артефактной) зелёный — автогейт РЕАЛЬНО спрашивает
        `orchestrator/ci.py` (не молчит по умолчанию) и проходит целиком
        (условия б/в/г/д заглушены на «выполнено» в `autogate()`),
        задача переходит `acceptance -> merge_gate`.

        Ловит мутацию: реализация, которая считает критерий `ci`
        исполненным ТОЛЬКО когда данных CI нет вовсе (перепутанная
        полярность проверки — «нет данных» вместо «CI зелёный»), либо
        никогда не считает его исполненным (безусловный отказ) — оба
        варианта не дают перехода в `merge_gate`; отдельно ловит
        мутацию «пометка `ci` принимается на веру без обращения к CI
        вовсе» — `gh_mock.called` останется `False`.
        """
        self.seed_planka(ci_only_planka(2))

        with self.gh_check_runs(conclusion="success") as gh_mock:
            self.autogate()

        self.assertTrue(gh_mock.called,
                        "критерий ci обязан спрашивать статус CI кодовой "
                        "ветки, а не проходить молча")
        self.assertEqual(self.state(), "merge_gate")


if __name__ == "__main__":
    unittest.main()
