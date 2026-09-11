"""AC-8 (tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/SPEC.md): «Перечитывание на
approve spec_gate меняет потолок задачи — в журнал задачи пишется запись
об изменении...» Случай «не меняет» — отдельный файл
`test_ac8_unchanged_value_no_duplicate_journal_record.py`.

Настоящий git self/артели (`ApproveSandbox`). «Запись об изменении» —
действие журнала `бюджет из SPEC` (та же семантика, что уже несёт
`apply_spec_budget` на обычном `advance`, `tests/test_spec_budget.py`).

Красен до реализации: сегодня approve на spec_gate не зовёт `apply_spec_
budget` вовсе — список записей действия «бюджет из SPEC» остаётся
пустым. Прогнано: `assertEqual(len(records), 1, ...)` падает на `0 != 1`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fsm  # noqa: E402

from _sandbox import ApproveSandbox  # noqa: E402


class SpecGateApproveJournalsChangedBudgetTest(ApproveSandbox):

    def test_ac8_changed_value_is_journaled_as_a_change(self):
        """SPEC при входе на `spec_gate` без `budget_usd` (потолок —
        дефолт, `budget_source is None`); на гейте Оператор добавляет
        `budget_usd: 20` — approve обязан записать РОВНО одну запись об
        изменении потолка.

        Ловит мутацию: перечитывание, которое меняет `tasks.budget_usd`
        напрямую без прохода через `apply_spec_budget` (и, значит, без
        её журналирования), оставит список записей пустым.
        """
        sha = self.enter_spec_gate()
        self.write_spec_budget_on_artifact_branch(20)

        self.capture(fsm.cmd_approve, self.TASK, sha)

        records = self.budget_journal("бюджет из SPEC")
        self.assertEqual(len(records), 1,
                         f"ожидалась ровно одна запись об изменении: {records}")
        self.assertIn("$20.00", records[0])


if __name__ == "__main__":
    unittest.main()
