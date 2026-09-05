"""AC-7 (tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/SPEC.md): «Потолок, выставленный
Оператором командой `budget` (`budget_source = operator`), approve на
spec_gate не перебивает — ни при совпадающем, ни при отличающемся
значении `budget_usd` в SPEC.» Этот файл — случай ОТЛИЧАЮЩЕГОСЯ значения;
случай совпадающего значения — отдельный файл `test_ac7_matching_spec_
budget_does_not_override.py` (уже сегодня зелёный по другой причине).

Настоящий git self/артели (`ApproveSandbox`). `budget.cmd_budget` ставит
`budget_source = operator` — та же функция, что уже несёт `tests/
test_spec_budget.py` для перечитывания на обычном `advance`; здесь
предмет — та же гарантия на ВТОРОЙ точке чтения SPEC (`approve` на
`spec_gate`, требование 4 SPEC этой задачи).

Красен до реализации: сегодня approve на spec_gate вообще не зовёт
`apply_spec_budget` — потолок, поставленный Оператором, уцелел бы
СЛУЧАЙНО (никто его не трогает), и одна лишь проверка «потолок не
изменился» была бы тавтологией. Тест ниже проверяет ещё и то, что
перечитывание вообще произошло (журнал «бюджет из SPEC не применён» с
явной причиной) — сегодня такой записи нет вовсе, `assertEqual` падает
на пустом списке.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import budget, config, fsm, store  # noqa: E402

from _sandbox import ApproveSandbox  # noqa: E402


class DifferingSpecBudgetDoesNotOverrideOperatorCeilingTest(ApproveSandbox):

    def test_ac7_differing_spec_budget_does_not_override_operator_ceiling(self):
        """Оператор поставил потолок $100 командой `budget` ПОСЛЕ входа
        на `spec_gate`; SPEC на артефактной ветке несёт другое значение
        ($30) — approve обязан оставить потолок Оператора нетронутым, но
        всё же зафиксировать в журнале, что перечитывание случилось и
        было отклонено именно по источнику.

        Ловит мутацию: перечитывание, реализованное вызовом `store.
        update_task(budget_usd=...)` напрямую (в обход `apply_spec_
        budget` и её проверки `budget_source`), перебило бы $100
        значением из SPEC и не оставило бы записи «не применён».
        """
        sha = self.enter_spec_gate()
        self.capture(budget.cmd_budget, self.TASK, "100")
        self.write_spec_budget_on_artifact_branch(30)

        self.capture(fsm.cmd_approve, self.TASK, sha)

        row = store.get_task(store.db(), self.TASK)
        self.assertAlmostEqual(row["budget_usd"], 100.0)
        self.assertEqual(row["budget_source"], config.BUDGET_SOURCE_OPERATOR)
        self.assertEqual(
            self.budget_journal("бюджет из SPEC не применён"),
            ["$30.00 — потолок задан Оператором, остаётся $100.00"])


if __name__ == "__main__":
    unittest.main()
