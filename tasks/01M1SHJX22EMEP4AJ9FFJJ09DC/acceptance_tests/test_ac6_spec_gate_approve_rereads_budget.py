"""AC-6 (tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/SPEC.md): «approve на гейте
spec_gate перечитывает `budget_usd` из SPEC артефактной ветки и
применяет прочитанное значение функцией `apply_spec_budget` с теми же
границами применения, что действуют у неё на момент мержа этой задачи.»

Настоящий git self/артели (`ApproveSandbox`): `enter_spec_gate()` заводит
задачу на `spec_gate` через обычный `advance` с SPEC БЕЗ поля
`budget_usd` (потолок остаётся дефолтным, `budget_source is None`) —
затем `write_spec_budget_on_artifact_branch` кладёт в артефактную ветку
НОВУЮ версию SPEC.md с полем `budget_usd`, той же правкой, какую сделал
бы Оператор прямо на гейте (SPEC «Контекст»). Sha фиксации (`task_dir()`)
не трогается — approve вызывается с ПРЕЖНИМ зафиксированным sha, потому
что предмет этого файла — перечитывание бюджета, а не сверка sha
(AC-1..AC-4, отдельные файлы).

Красен до реализации: сегодня `_cmd_approve` на `spec_gate` читает
`meta` из SPEC артефактной ветки только для решения tests_writing/
in_dev — `budget.apply_spec_budget` там не вызывается вовсе. Потолок
остаётся дефолтным после approve, `test_ac6_...` падает на
`assertAlmostEqual(row["budget_usd"], 20.0)`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, fsm, store  # noqa: E402

from _sandbox import ApproveSandbox  # noqa: E402


class ApproveOnSpecGateRereadsBudgetFromArtifactBranchTest(ApproveSandbox):

    def test_ac6_new_budget_usd_in_spec_is_applied_on_approve(self):
        """SPEC при входе на `spec_gate` не нёс `budget_usd` (потолок —
        дефолт). Прямо на гейте Оператор правит SPEC.md, добавляя
        `budget_usd: 20` (значение ниже дефолта — заведомо в границах,
        действующих независимо от ADR-0014, SPEC «Не входит»). `approve`
        обязан перечитать это значение и применить его тем же
        `apply_spec_budget`, что уже применяется на переходе
        spec_writing -> spec_gate.

        Ловит мутацию: если `_cmd_approve` продолжит игнорировать
        `budget_usd` из перечитанного `meta` (сегодняшнее поведение),
        потолок останется дефолтным — `assertAlmostEqual` ниже не пройдёт.
        """
        sha = self.enter_spec_gate()
        before = store.get_task(store.db(), self.TASK)
        self.assertAlmostEqual(before["budget_usd"], config.DEFAULT_BUDGET_USD,
                               msg="контроль: без budget_usd потолок — дефолт")
        self.assertIsNone(before["budget_source"])
        self.write_spec_budget_on_artifact_branch(20)

        self.capture(fsm.cmd_approve, self.TASK, sha)

        row = store.get_task(store.db(), self.TASK)
        self.assertAlmostEqual(row["budget_usd"], 20.0)
        self.assertEqual(row["budget_source"], config.BUDGET_SOURCE_SPEC)

    def test_ac6_applied_value_uses_apply_spec_budget_bounds(self):
        """Значение ВЫШЕ дефолта из перечитанного SPEC отклоняется той же
        границей, что несёт `apply_spec_budget` (инвариант 10: потолок
        руками правит только Оператор) — approve не обязан ослаблять эту
        границу только потому, что читает SPEC на другом шаге, чем
        обычный `advance`.

        Ловит мутацию: собственный, отдельный от `apply_spec_budget` путь
        применения бюджета на approve (например, применяющий сумму без
        проверки границы) поднял бы потолок сверх дефолта.
        """
        sha = self.enter_spec_gate()
        self.write_spec_budget_on_artifact_branch(
            f"{config.DEFAULT_BUDGET_USD * 10:g}")

        out = self.capture(fsm.cmd_approve, self.TASK, sha)

        row = store.get_task(store.db(), self.TASK)
        self.assertAlmostEqual(row["budget_usd"], config.DEFAULT_BUDGET_USD,
                               msg="потолок не поднялся выше дефолта")
        self.assertIsNone(row["budget_source"])
        self.assertIn("выше потолка ролей", out)


if __name__ == "__main__":
    unittest.main()
