"""AC-6 (tasks/01M1THKWFXFYNW28HDJGYHQWH6/SPEC.md, требование 6): PLAN.md с
`budget_usd` выше `ROLE_BUDGET_CAP` не проходит переход `in_dev` вовсе —
отказывает гейт guard, введённый частью 1 ADR-0014, раньше, чем логика
переоценки этой задачи успевает сработать; эта задача не добавляет для
такого случая отдельной обработки — только проверяет, что переход
действительно не проходит и потолок задачи не меняется.

Красен до реализации: по двум независимым причинам одновременно. (1)
`ROLE_BUDGET_CAP` — константа части 1 ADR-0014, которая на момент
написания этой планки ещё не смержена (её артефактная ветка несёт только
SPEC.md стадии analyst); тест ссылается на `config.ROLE_BUDGET_CAP` и до
мержа части 1 падает `AttributeError`. (2) `scripts/guard.py`, тоже зона
части 1, сегодня НЕ отказывает переходу по значению `budget_usd` PLAN.md
вовсе — до мержа части 1 переход `in_dev -> review` с любым `budget_usd`
пройдёт молча. Обе причины исчезают только после мержа части 1 — эта
задача (часть 2) намеренно НЕ реализует такую проверку сама (требование 6:
«эта задача не добавляет отдельной обработки»), поэтому тест правильно
опирается ЦЕЛИКОМ на инфраструктуру части 1, а не проверяет код этой
задачи напрямую. Проверено временным стабом guard-проверки части 1
(отказ guard при `budget_usd` PLAN выше `ROLE_BUDGET_CAP`) поверх стаба
части 2 — тест зеленеет.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import PlanBudgetSandbox  # noqa: E402
from orchestrator import config  # noqa: E402


class Ac6OverCapBlocksTransitionTest(PlanBudgetSandbox):

    def test_ac6_plan_budget_above_role_cap_refuses_transition(self):
        """PLAN.md несёт `budget_usd`, разбираемое как число строго выше
        `ROLE_BUDGET_CAP` — переход `in_dev -> review` не проходит (guard
        части 1 отказывает раньше логики переоценки), задача остаётся в
        `in_dev`, потолок задачи не меняется.

        Ловит мутацию: код части 2, который читает `budget_usd` из PLAN.md
        и клампит его до `ROLE_BUDGET_CAP` вместо того, чтобы положиться
        на отказ guard (то есть САМ добавляет обработку случая «выше
        потолка ролей», которую требование 6 явно запрещает добавлять
        здесь) — такой код пропустил бы переход и/или тихо поднял бы
        потолок до ROLE_BUDGET_CAP; тест поймает и то, и другое по
        неизменному состоянию/потолку задачи.
        """
        self.enter_in_dev()
        self.set_budget(45.0, "spec")

        self.submit_plan(budget_usd=config.ROLE_BUDGET_CAP + 1)

        self.assertEqual(self.state(), "in_dev",
                         "guard части 1 обязан отказать переходу — PLAN.md "
                         "budget_usd выше ROLE_BUDGET_CAP")
        row = self.task_row()
        self.assertEqual(row["budget_usd"], 45.0,
                         "потолок задачи не должен был измениться")
        self.assertEqual(row["budget_source"], "spec")


if __name__ == "__main__":
    import unittest
    unittest.main()
