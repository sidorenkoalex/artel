"""AC-5 (SPEC: «Стоимость частичного шага при таймауте: курс токенов
вместо тишины») — «enforce_budget/budget_block сравнивают с потолком
задачи сумму spent_usd + spent_estimate_usd: задача с ненулевым
spent_estimate_usd, чья сумма spent_usd + spent_estimate_usd достигла
потолка, эскалируется по бюджету так же, как если бы эта сумма целиком
лежала в spent_usd.»

Красен до реализации: `budget.budget_block`/`budget.enforce_budget`
(orchestrator/budget.py:91,106) сегодня читают только `t["spent_usd"]`
— колонки `spent_estimate_usd` в схеме нет вовсе (появится миграцией
requirement 1), сценарий ниже падает уже на `self.set_task(...
spent_estimate_usd=8.0)` (`sqlite3.OperationalError: no such column`),
а после появления колонки — на самом сравнении с потолком, пока оно
не станет суммой обеих колонок.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import budget, store  # noqa: E402
from _sandbox import CostTmpRootTest  # noqa: E402


class BudgetGateIncludesEstimateTest(CostTmpRootTest):

    def test_ac5_budget_block_counts_the_estimate_toward_the_ceiling(self):
        """`budget_block` блокирует `run`, когда `spent_usd +
        spent_estimate_usd` достиг потолка — даже если один только
        `spent_usd` ниже него.

        Ловит мутацию: сравнение с потолком оставлено по одному
        `spent_usd` (`spent_estimate_usd` не прибавлен) — при
        `spent_usd=3.0 < budget_usd=10.0` блок не сработает,
        `budget_block` вернёт `None`, тест покраснеет.
        """
        self.set_task(budget_usd=10.0, spent_usd=3.0, spent_estimate_usd=8.0)

        msg = budget.budget_block(self.task_row())

        self.assertIsNotNone(
            msg, "3.0 (spent_usd) + 8.0 (spent_estimate_usd) = 11.0 >= "
            "потолка 10.0 — run обязан быть заблокирован")

    def test_ac5_enforce_budget_escalates_when_the_estimate_pushes_it_over(self):
        """`enforce_budget` уводит задачу в `escalated`, когда сумму
        обеих колонок достигла потолка — по требованию 5, «так же, как
        если бы эта сумма целиком лежала в spent_usd».

        Ловит мутацию: та же неполная сумма в `enforce_budget` —
        `spent >= budget` сравнивается по одному `spent_usd` (3.0 < 10.0,
        не эскалирует), задача останется в `in_dev`, тест покраснеет.
        """
        self.set_task(state="in_dev", budget_usd=10.0, spent_usd=3.0,
                      spent_estimate_usd=8.0)

        escalated = budget.enforce_budget(store.db(), self.TASK, "in_dev")

        self.assertTrue(escalated)
        self.assertEqual(self.task_row()["state"], "escalated")

    def test_ac5_budget_block_allows_run_when_the_sum_is_still_under_the_ceiling(self):
        """Обратная сторона: сумма НИЖЕ потолка — блока нет.

        Ловит мутацию: `spent_estimate_usd` учитывается ПОВЕРХ суммы
        второй раз (например, потолок сравнивается с
        `spent_usd + 2 * spent_estimate_usd` из-за опечатки) —
        `3.0 + 2*4.0 = 11.0 >= 10.0` ошибочно заблокировал бы run,
        хотя корректная сумма `3.0 + 4.0 = 7.0` ниже потолка.
        """
        self.set_task(budget_usd=10.0, spent_usd=3.0, spent_estimate_usd=4.0)

        msg = budget.budget_block(self.task_row())

        self.assertIsNone(msg, "3.0 + 4.0 = 7.0 < 10.0 — run не блокируется")
