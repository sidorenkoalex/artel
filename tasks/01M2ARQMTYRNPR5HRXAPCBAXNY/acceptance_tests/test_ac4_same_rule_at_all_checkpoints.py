"""AC-4 (tasks/01M2ARQMTYRNPR5HRXAPCBAXNY/SPEC.md): правило из AC-1..AC-2
действует одинаково на всех трёх точках сверки свежести (`in_dev ->
review`, `acceptance -> merge_gate`, `merge_gate -> done`) за счёт
реализации в общей `pull.evaluate`, без правок `fsm.py`/
`fsm_merge_gate.py`.

Часть требования «без правок fsm.py/fsm_merge_gate.py» проверяется не
здесь: `pull.evaluate` не зависит от вызывающей точки, единственный
наблюдаемый параметр диспетчеризации, который передают все три точки, —
`state` (документировано `orchestrator/pull.py::evaluate`) — сама правка
файлов fsm.py/fsm_merge_gate.py вне зон этой задачи (SPEC «Зоны») и
проверяется системным гейтом зон/ревью диффа, не приёмочным тестом.

Красен до реализации: правило AC-1 ещё не реализовано в `pull.evaluate`
— она безусловно идёт в `git merge` при `behind > 0` независимо от
`state`, поэтому все три прогона цикла возвращают `Refused`/`Pulled`, не
`Fresh` (`grep -n "свежесть:" orchestrator/pull.py` пуст).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import PullFreshnessSandbox  # noqa: E402
from orchestrator import pull  # noqa: E402


class SameFreshnessRuleAtAllThreeCheckpointsTest(PullFreshnessSandbox):

    def test_ac4_fresh_outcome_and_journal_are_state_independent(self):
        """Один и тот же документный доскок main (`docs/backlog.md`, не
        пересекающийся с диффом ветки), прогнанный через `pull.evaluate`
        со `state` из всех трёх точек сверки (`in_dev`, `acceptance`,
        `merge_gate`), обязан дать `Fresh` и журнальную запись «свежесть:
        …» на КАЖДОЙ из них — единая реализация, без ветвления по точке
        вызова.

        Ловит мутацию: `evaluate` применяет новое правило только при
        каком-то одном/двух значениях `state` (частичное внедрение,
        прямо запрещённое обоснованием монолита SPEC) — цикл по трём
        `state` поймает несовпадающий исход `assertEqual`'ом, а счётчик
        журнальных записей поймает пропущенную запись хотя бы на одной
        точке."""
        self.branch_off_main()
        self.commit_on_branch({"orchestrator/ac4_marker.py": "# ветка\n"},
                              f"{self.TASK}: правка ветки")
        self.add_main_commit({"docs/backlog.md": "строка копилки\n"},
                             "оператор: копилка")

        for state in ("in_dev", "acceptance", "merge_gate"):
            outcome = self.evaluate(state=state)
            self.assertEqual(outcome, pull.Fresh(), f"state={state}")

        freshness_records = [r for r in self.journal_rows()
                             if r["action"].startswith("свежесть: ")]
        self.assertEqual(
            len(freshness_records), 3,
            "каждая из трёх точек сверки обязана журналировать пропуск "
            "подтяжки одинаково")


if __name__ == "__main__":
    unittest.main()
