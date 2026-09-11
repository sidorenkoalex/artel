"""Приёмочные тесты 01M1VBEDGMEXHVGWAH42FTDZ4X — AC-5, AC-6, AC-7: рубеж
«возврат не отработан» цикла `auto` (`orchestrator/auto.py::
_role_step_since_state_entry`, `_rework_gate_blocks`) сверяет сданный шаг
роли с моментом ПОСЛЕДНЕГО возврата `review -> in_dev` (`changes_requested`),
а не с моментом самой записи возврата из `escalated` (требование 2).

Все три теста ведут состояние `in_dev` через цикл `auto` (`self.auto()`),
не ручной `advance`: `_rework_gate_blocks` — механизм ИМЕННО цикла
`auto` (`orchestrator/auto.py::_cmd_auto`, вызывается только там); для
`in_dev` у ручного `advance` есть СВОЙ, git-временной гейт
(`fsm_advance.py::_review_rework_gate`), который в лёгкой песочнице этого
файла (`fake_git`, без настоящих коммитов) не может дать содержательного
git-сигнала и потому не иллюстрирует требование 2 — предмет этих трёх
тестов сам SPEC называет «общим узлом auto.py/fsm_advance.py», и
`_role_step_since_state_entry` — именно та функция, которую делят оба
места; проверка через `auto` покрывает её напрямую и переносится на
ручной путь тем же кодом (AC-6 явно называет оба пути равноправными).

Красен до реализации: `_role_step_since_state_entry` (orchestrator/
auto.py, строки 133-165) ищет ПОСЛЕДНЮЮ запись `state -> in_dev` и
сверяет шаг роли ТОЛЬКО с ней — запись возврата из `escalated`
(«эскалация разрешена, продолжаем») моложе записи `review -> in_dev`
(«замечания ревью, итерация N») и подменяет её как точку отсчёта.
AC-5 покраснеет: шаг developer, сданный ДО эскалации, окажется СТАРШЕ
этой последней записи, и гейт потребует ещё один — цикл вызовет
developer повторно вместо немедленного `advance` по готовому PLAN.md.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AutoCycleTest, agent_run_finished_actors,  # noqa: E402
                      journal_agent_run_finished)
from orchestrator import budget, config, fsm, store  # noqa: E402


class DeveloperStepDoneBeforeTheEscalationIsNotForgottenTest(AutoCycleTest):
    """AC-5: рубеж сверяет с моментом ПОСЛЕДНЕГО возврата `review ->
    in_dev` (changes_requested), не с моментом самой записи возврата из
    `escalated` — типичный случай ТЗ: эскалация по бюджету ловит
    завершившийся шаг developer до того, как он успел продвинуть задачу.
    """

    def test_ac5_gate_keys_off_the_review_return_not_the_escalation_return(self):
        """developer уже отработал после `review -> in_dev`, затем задачу
        уронил бюджет (ДРУГАЯ запись `state -> in_dev`, оставленная
        возвратом из `escalated`, моложе шага developer) — `auto` после
        `approve` обязан продвинуть задачу по готовому PLAN.md, не звать
        developer ещё раз.

        Ловит мутацию: гейт сверяет шаг роли с ПОСЛЕДНЕЙ записью
        `state -> in_dev` буквально (включая запись возврата из
        `escalated`), а не с последним возвратом ИМЕННО из `review` —
        `agent_run_finished_actors` покажет ВТОРОЙ `developer` после
        нашего единственного заранее сданного шага.
        """
        conn = store.db()
        self.write_plan("ready")
        self.set_state("review")
        store.set_state(conn, self.TASK, "in_dev", "fsm",
                        expected_state="review",
                        detail="замечания ревью, итерация 1")
        journal_agent_run_finished(conn, self.TASK)  # developer уже отработал

        # Эскалация по бюджету ловит уже завершившийся шаг (SPEC «Контекст»).
        store.update_task(conn, self.TASK, escalated_from="in_dev",
                          budget_usd=10.0, spent_usd=12.0)
        self.assertTrue(budget.enforce_budget(conn, self.TASK, "in_dev"))
        self.assertEqual(self.state(), "escalated")

        self.capture(budget.cmd_budget, self.TASK, "50")
        self.assertEqual(
            self.state(), "in_dev",
            "budget не вернул задачу в in_dev — сценарий не воспроизведён")

        self.agent.script = [lambda: None]
        self.auto()

        developer_steps = [a for a in agent_run_finished_actors(conn, self.TASK)
                          if a == "developer"]
        self.assertEqual(
            len(developer_steps), 1,
            "developer отработал больше одного раза — pre-advance не "
            "продвинул задачу по уже готовому PLAN.md")


class DeveloperStepDoneAfterTheEscalationStillWorksTest(AutoCycleTest):
    """AC-6: то же правило симметрично работает и когда шаг роли случился
    ПОСЛЕ возврата из `escalated` (не только до, как AC-5) — ровно один
    шаг развивается роли достаточно независимо от того, по какую сторону
    эскалации он пришёлся.

    Зелёный с рождения: сегодняшний (до этой задачи) `_role_step_since_
    state_entry` уже сверяет шаг роли с ПОСЛЕДНЕЙ записью `state ->
    in_dev` — а это ровно запись возврата из `escalated` в этом сценарии
    (шага ДО неё не было вовсе) — поэтому шаг ПОСЛЕ неё уже удовлетворяет
    рубежу и до фикса требования 2. AC-5 меняет это только для шага ДО
    записи возврата, не после.
    """

    def test_ac6_pre_advance_after_a_post_escalation_developer_step(self):
        """Эскалация случилась ДО единственного шага developer (упавший
        агент, не бюджет — основание эскалации требованием 2 не сужено);
        после `approve` developer отрабатывает один раз, и `auto`
        продвигает задачу дальше без повторного вызова.

        Ловит мутацию: рубеж требования 2 реализован НАСТОЛЬКО широко,
        что перестаёт признавать вообще любой шаг роли (например, всегда
        требует шаг СТРОГО после escalated, отбрасывая эту, и без того
        рабочую, ветку) — `developer` не появится в
        `agent_run_finished_actors` вовсе, а задача останется в `in_dev`.
        """
        conn = store.db()
        self.write_plan("ready")
        self.set_state("review")
        store.set_state(conn, self.TASK, "in_dev", "fsm",
                        expected_state="review",
                        detail="замечания ревью, итерация 1")
        # никакого шага developer до эскалации
        store.update_task(conn, self.TASK, escalated_from="in_dev")
        store.set_state(conn, self.TASK, "escalated", "fsm",
                        expected_state="in_dev", detail="агент упал")

        self.capture(fsm.cmd_approve, self.TASK)
        self.assertEqual(self.state(), "in_dev")

        self.agent.script = [lambda: None]
        self.auto()

        developer_steps = [a for a in agent_run_finished_actors(conn, self.TASK)
                          if a == "developer"]
        self.assertEqual(len(developer_steps), 1)
        self.assertNotEqual(
            self.state(), "in_dev",
            "задача осталась в in_dev несмотря на отработанный шаг developer")


class NoDeveloperStepAtAllStillRequiresOneTest(AutoCycleTest):
    """AC-7: если шаг роли ПОСЛЕ момента AC-5 ещё не сдан вовсе (ни до, ни
    после эскалации), рубеж по-прежнему держит `auto` — цикл обязан
    позвать роль, не проскочить мимо неё по уже готовому PLAN.md.

    Зелёный с рождения: этот класс не меняется требованием 2 (SPEC,
    требование 2: «если шаг ещё не сдан — отказ остаётся прежним») —
    рубеж, введённый 01M1RHFRQ2C0P4A57XJJ1WZV8N, уже требует шаг роли
    после ЛЮБОЙ записи возврата, включая возврат из `escalated`, когда
    такого шага не было ни разу.
    """

    def test_ac7_pre_advance_still_calls_the_role_without_any_step(self):
        """Ни до эскалации, ни между эскалацией и возвратом developer не
        отрабатывал ни разу — `auto` обязан вызвать его, а не продвинуть
        задачу мимо него по уже готовому PLAN.md.

        Ловит мутацию: требование 2 реализовано так, что снимает рубеж
        целиком (любой возврат из `escalated` считается «шаг не нужен») —
        `self.agent.calls` останется пустым, задача уйдёт в `review` без
        единого вызова developer.
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

        self.assertTrue(
            self.agent.calls,
            "цикл не вызвал агента вовсе — рубеж требования 2 пропустил "
            "переход без единого шага developer")


if __name__ == "__main__":
    import unittest
    unittest.main()
