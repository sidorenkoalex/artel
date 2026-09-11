"""AC-8 (tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/SPEC.md) — вторая половина
критерия: «...значение совпало с уже применённым — новой записи об
изменении нет.» Случай «меняет» — отдельный файл `test_ac8_changed_
value_is_journaled.py` (там же — обоснование красноты обоих файлов).

Зелёный с рождения: сегодня approve на spec_gate не зовёт `apply_spec_
budget` вовсе — журнал действия «бюджет из SPEC» и так не пополняется
вторым разом (некому пополнять), независимо от того, совпадает ли
значение. Наблюдаемый исход («записей по-прежнему одна») здесь тот же
самый что до, что после реализации требования 5 — ценность теста не в
сегодняшней красноте, а в том, что он ловит будущий регресс:
перечитывание, не проверяющее, изменилось ли значение относительно уже
применённого (пишет запись при КАЖДОМ approve на spec_gate безусловно),
задвоило бы запись «бюджет из SPEC». Прогнано: тест уже проходит на
сегодняшнем коде.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fsm, store  # noqa: E402

from _sandbox import ApproveSandbox  # noqa: E402


class SpecGateApproveDoesNotDuplicateUnchangedBudgetRecordTest(ApproveSandbox):

    def test_ac8_value_already_applied_leaves_no_new_change_record(self):
        """SPEC при входе на `spec_gate` уже несёт `budget_usd: 20`
        (применяется на обычном `advance` -> `apply_spec_budget`,
        `budget_source` становится `spec`). На гейте перечитанное значение
        — то же самое $20 — approve НЕ обязан писать вторую запись об
        изменении: значение совпадает с уже применённым.

        Ловит мутацию: перечитывание, не проверяющее, изменилось ли
        значение относительно уже применённого (пишет запись об
        изменении при КАЖДОМ approve на spec_gate безусловно), задвоило
        бы запись «бюджет из SPEC».
        """
        self.task_dir().mkdir(parents=True, exist_ok=True)
        spec_text_with_budget = (
            "---\ntask: {task}\ntype: spec\nauthor_role: analyst\n"
            "status: ready\nschema_version: 1\nbudget_usd: 20\n---\n\n"
            "# SPEC: перечитывание бюджета на гейте\n\n## Контекст\n\n"
            "## Требования\n\n## Критерии приёмки\n\n## Не входит\n"
        ).format(task=self.TASK)
        (self.task_dir() / "SPEC.md").write_text(
            spec_text_with_budget, encoding="utf-8")
        self._seed_artifact_branch(
            f"tasks/{self.TASK}/SPEC.md", spec_text_with_budget,
            f"{self.TASK}: SPEC готов с budget_usd")
        self.capture(fsm.cmd_advance, self.TASK)
        sha = self.head()
        self.assertEqual(
            store.get_task(store.db(), self.TASK)["state"], "spec_gate")
        self.assertEqual(len(self.budget_journal("бюджет из SPEC")), 1,
                         "контроль: advance уже применил значение один раз")

        self.capture(fsm.cmd_approve, self.TASK, sha)

        self.assertEqual(
            len(self.budget_journal("бюджет из SPEC")), 1,
            "совпадающее значение не должно добавлять вторую запись")


if __name__ == "__main__":
    unittest.main()
