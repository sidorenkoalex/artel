"""Планка AC-4, AC-5: дедупликация двух бюджетных предупреждений журнала
в пределах одного пребывания задачи в состоянии.

Красен до реализации: подавления повторов в `orchestrator/budget.py` ещё
нет — второй вызов `apply_spec_budget` и каждый вызов `enforce_budget`
после порога пишут свою запись журнала, счёт записей даёт 2 и 3 вместо 1.

Песочница — `tests.sandbox.SchemaConnTmpRootTest` (временный `config`,
схема БД, соединение `self.conn`): обе функции под тестом работают только
с БД, git и агент сюда не заходят. Пребывание в состоянии здесь одно по
построению — ни одной записи `state -> <состояние>` в журнале задачи нет
(задача заводится `store.insert_task`, минуя `set_state`), ровно тот
вырожденный случай «граница 0», который уже описан у
`store.refusal_history`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import budget, config, store  # noqa: E402
from tests.sandbox import SchemaConnTmpRootTest  # noqa: E402

from _util import (BUDGET_WARNING_ACTION,  # noqa: E402
                   SPEC_NOT_APPLIED_ACTION, spend_levels)


class BudgetWarningDedupTest(SchemaConnTmpRootTest):
    """Оба бюджетных предупреждения требования 1 SPEC: одна запись журнала
    на пребывание задачи в состоянии."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        store.insert_task(self.conn, self.TASK, "Шум журнала", "in_dev",
                          "task/t001-shum", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    # ------------------------------------------------------------ утилиты

    def journal(self, action: str) -> list[str]:
        """Детали записей журнала задачи с этим действием, по порядку."""
        return [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]

    def task_row(self):
        return store.get_task(self.conn, self.TASK)

    def set_task(self, **fields) -> None:
        store.update_task(self.conn, self.TASK, **fields)

    # ----------------------------------------------------------- сценарии

    def test_ac4_spec_budget_not_applied_is_journaled_once_per_state_visit(self):
        """Два прохода гейта с «бюджет из SPEC не применён» в одном
        пребывании в состоянии — одна запись журнала.

        Потолок задан Оператором (`budget_source=operator`), а SPEC несёт
        своё значение: `apply_spec_budget` на КАЖДОМ проходе гейта
        сообщает, что значение SPEC не применено. Второй проход — тот же
        текст предупреждения, то же пребывание в состоянии.

        Ловит мутацию: подавление подключено только к `pre-flight WARNING`
        (или только к ветке «уже применён» ниже по функции), а ветка
        «потолок задан Оператором» пишет запись как раньше — журнал
        получит две записи вместо одной.
        """
        self.set_task(budget_usd=config.DEFAULT_BUDGET_USD,
                      budget_source=config.BUDGET_SOURCE_OPERATOR)
        meta = {"budget_usd": f"{config.DEFAULT_BUDGET_USD / 2:g}"}

        for _ in range(2):
            self.capture(budget.apply_spec_budget, self.conn,
                         self.task_row(), meta)

        self.assertEqual(len(self.journal(SPEC_NOT_APPLIED_ACTION)), 1,
                         self.journal(SPEC_NOT_APPLIED_ACTION))

    def test_ac5_budget_alert_is_journaled_once_despite_changing_sums(self):
        """Несколько шагов подряд после порога `config.BUDGET_ALERT_RATIO`
        в одном пребывании в состоянии — одна запись «бюджет:
        предупреждение», хотя текст каждого срабатывания несёт свои суммы.

        Расход растёт между вызовами `enforce_budget`, оставаясь ниже
        потолка: порог пересечён один раз, текст предупреждения каждый раз
        новый. Различие печатей проверяется здесь же — им доказывается, что
        все три срабатывания случились и текст у них действительно разный,
        а не совпал случайно.

        Ловит мутацию: ключом подавления взят текст предупреждения (тот же
        приём, что у двух текстовых мест требования 3) — суммы в тексте
        разные, и журнал получит три записи вместо одной.
        """
        budget_usd = config.DEFAULT_BUDGET_USD
        levels = spend_levels(budget_usd, 3)
        self.set_task(budget_usd=budget_usd, budget_source=None)

        printed = []
        for spent in levels:
            self.set_task(spent_usd=spent)
            printed.append(self.capture(budget.enforce_budget, self.conn,
                                        self.TASK, "in_dev"))

        self.assertEqual(self.task_row()["state"], "in_dev",
                         "фикстура: расход ниже потолка, эскалации нет")
        self.assertEqual(len(set(printed)), 3,
                         "фикстура: текст каждого срабатывания свой")
        self.assertEqual(len(self.journal(BUDGET_WARNING_ACTION)), 1,
                         self.journal(BUDGET_WARNING_ACTION))


if __name__ == "__main__":
    unittest.main()
