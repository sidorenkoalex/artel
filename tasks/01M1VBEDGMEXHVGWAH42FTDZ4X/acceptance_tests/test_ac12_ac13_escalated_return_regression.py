"""Приёмочные тесты 01M1VBEDGMEXHVGWAH42FTDZ4X — AC-12, AC-13: дежурные
регресс-тесты требования 2, дополняющие test_ac5_ac6_ac7_
escalated_return_gate.py интеграционным углом (AC-12 — полная
прогонка `auto` от возврата до следующего состояния, не только счётчик
шагов роли) и явным мутационным замком (AC-13 — рубеж не должен исчезнуть
ЦЕЛИКОМ, не только ослабнуть).

Красен до реализации: AC-12 — тот же класс дефекта, что и AC-5 в соседнем
файле (гейт сверяет с записью возврата из `escalated`, не с записью
возврата из `review`) — `auto` вызовет developer повторно и не дойдёт до
`review` в рамках лимита сценария теста. AC-13 не меняется этой задачей
(рубеж остаётся) — зелёный уже сегодня, см. докстринг класса ниже.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AutoCycleTest, agent_run_finished_actors,  # noqa: E402
                      journal_agent_run_finished)
from orchestrator import auto, budget, ci, fsm, store  # noqa: E402


class ReturnAfterAnAlreadyFinishedDeveloperStepAdvancesTest(AutoCycleTest):
    """AC-12: возврат из `escalated` после уже сданного шага developer
    (AC-5/AC-6) переходит без нового шага роли — интеграционная сверка:
    задача обязана ДОЙТИ до `review`, не просто не позвать developer
    дважды."""

    def test_ac12_auto_reaches_review_without_a_second_developer_step(self):
        """PLAN.md уже `ready`, developer отработал ДО эскалации (по
        бюджету) — после `budget` (подъём потолка) `auto` обязан
        продвинуть задачу до `review`, использовав уже готовый PLAN.md, а
        не тратить ещё один шаг developer.

        Ловит мутацию: рубеж требования 2 продолжает сверяться с записью
        `state -> in_dev`, оставленной ВОЗВРАТОМ из `escalated`
        («эскалация разрешена, продолжаем»), а не с записью возврата
        именно из `review` («замечания ревью, итерация N») — задача
        застрянет в `in_dev`, повторно позвав developer, и не дойдёт до
        `review` в границах одного вызова `auto`.
        """
        self.patch_object(ci, "verifying_status",
                          lambda branch: (ci.VERIFYING_GREEN,
                                          "CI коммита aaaaaaaa зелёный (2 проверок)"))
        conn = store.db()
        self.write_plan("ready")
        self.set_state("review")
        store.set_state(conn, self.TASK, "in_dev", "fsm",
                        expected_state="review",
                        detail="замечания ревью, итерация 1")
        journal_agent_run_finished(conn, self.TASK)

        store.update_task(conn, self.TASK, escalated_from="in_dev",
                          budget_usd=10.0, spent_usd=12.0)
        budget.enforce_budget(conn, self.TASK, "in_dev")
        self.assertEqual(self.state(), "escalated")

        self.capture(budget.cmd_budget, self.TASK, "50")
        self.assertEqual(self.state(), "in_dev")

        self.agent.script = [lambda: None]
        self.auto()

        self.assertEqual(
            self.state(), "review",
            "auto не продвинул задачу до review по уже готовому PLAN.md")
        developer_steps = [a for a in agent_run_finished_actors(conn, self.TASK)
                          if a == "developer"]
        self.assertEqual(len(developer_steps), 1)


class TheReworkGateCannotBeRemovedOutrightTest(AutoCycleTest):
    """AC-13: мутационный замок — рубеж «возврат не отработан» обязан
    остаться ИМЕННО как отказ перехода (журнальная запись `auto.
    REWORK_REFUSAL_ACTION`), не только «в среднем» реже пропускать шаг:
    ослабление до «пропускать шаг всегда» проходит мимо AC-5/AC-6/AC-12
    незаметно только тогда, когда сам факт отказа больше не проверяется
    напрямую.

    Зелёный с рождения: требование 2 сужает рубеж только для шага,
    сданного ДО момента возврата, — случай «шага не было вовсе» этой
    задачей не меняется (SPEC, требование 2: «если шаг ещё не сдан —
    отказ остаётся прежним»), и сегодняшний код уже журналирует этот
    отказ (01M1RHFRQ2C0P4A57XJJ1WZV8N).
    """

    def test_ac13_refusal_is_journalled_when_the_gate_is_intact(self):
        """Без единого шага developer после возврата из `escalated` `auto`
        обязан журналировать ИМЕННО `auto.REWORK_REFUSAL_ACTION`, не
        просто воздержаться от перехода по другой причине.

        Ловит мутацию: рубеж требования 2 снят целиком (а не только
        сужен для шага «до» эскалации) — журнал не будет нести запись
        `auto.REWORK_REFUSAL_ACTION` вовсе, потому что пред-advance
        пройдёт по уже готовому PLAN.md без единого отказа.
        """
        conn = store.db()
        self.write_plan("ready")
        self.set_state("review")
        store.set_state(conn, self.TASK, "in_dev", "fsm",
                        expected_state="review",
                        detail="замечания ревью, итерация 1")
        store.update_task(conn, self.TASK, escalated_from="in_dev")
        store.set_state(conn, self.TASK, "escalated", "fsm",
                        expected_state="in_dev", detail="агент упал")

        self.capture(fsm.cmd_approve, self.TASK)
        self.assertEqual(self.state(), "in_dev")

        self.agent.script = [lambda: None]
        self.auto()

        refusals = [(a, d) for _, a, d in self.journal_rows()
                   if a == auto.REWORK_REFUSAL_ACTION]
        self.assertTrue(
            refusals, "рубеж не отказал переходу ни разу — журнал не "
            "несёт запись auto.REWORK_REFUSAL_ACTION")


if __name__ == "__main__":
    import unittest
    unittest.main()
