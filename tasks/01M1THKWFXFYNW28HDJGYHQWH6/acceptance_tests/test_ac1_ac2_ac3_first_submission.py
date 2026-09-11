"""AC-1, AC-2, AC-3 (tasks/01M1THKWFXFYNW28HDJGYHQWH6/SPEC.md, требование 1-3):
первая сдача PLAN.md со `status: ready` (`review_iters == 0`, переоценка по
PLAN ещё ни разу не срабатывала) — три исхода в зависимости от значения
`budget_usd` в PLAN.md относительно текущего потолка задачи.

Красен до реализации: `orchestrator/fsm_advance.py::in_dev` этой ветки ещё
не несёт логики однократной переоценки бюджета на PLAN (часть 2 ADR-0014,
предмет этой задачи) — переход `in_dev -> review` сегодня применяет только
факт `status: ready`/`approved`/`escalate` PLAN.md, значение `budget_usd`
из него никак не читает: `Ac1RaisesCeilingOnFirstSubmissionTest.
test_ac1_higher_plan_budget_raises_ceiling_on_first_submission` и
`Ac3LowerBudgetNotAppliedTest` падают ассертом (потолок остаётся прежним
вместо ожидаемого подъёма/записи в журнал). Дополнительно
`test_ac1_ceiling_never_exceeds_role_budget_cap` привязан к
`ROLE_BUDGET_CAP` (константа части 1 ADR-0014, `orchestrator/config.py`) —
на момент написания этой планки часть 1 (задача
01M1THKTJ7YT1K410G1KS17MK6) ещё не смержена (её артефактная ветка несёт
только SPEC.md стадии analyst, кода нет), так что `config.ROLE_BUDGET_CAP`
сегодня не существует вовсе и тест падает `AttributeError` уже на
`submit_plan`. Все три состояния — легитимная краснота «кода задачи ещё
нет», не дефект теста: он проверен временным стабом обеих частей ADR-0014
(см. журнал шага test_author) — стаб зеленил все методы, включая эти три.

Зелёный с рождения: `Ac2MissingBudgetFieldTest.
test_ac2_missing_budget_usd_field_leaves_ceiling_unchanged` — без поля
`budget_usd` в PLAN.md сегодняшний код и так ничего не читает из него и
потолок не меняет; тест ловит будущую РЕГРЕССИЮ (код части 2, который
начнёт трактовать отсутствие поля как «применить дефолт» или «0»), не
сегодняшний дефект — тем же приёмом, что
`tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/acceptance_tests/
test_ac1_head_already_pushed_unchanged.py`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import PlanBudgetSandbox  # noqa: E402
from orchestrator import config  # noqa: E402


class Ac1RaisesCeilingOnFirstSubmissionTest(PlanBudgetSandbox):

    def test_ac1_higher_plan_budget_raises_ceiling_on_first_submission(self):
        """PLAN.md первой сдачи (`review_iters == 0`) несёт `budget_usd: 90`
        при текущем потолке задачи $45 — потолок поднимается до $90,
        `budget_source` становится `plan`, в журнал попадает запись со
        старым потолком, новым потолком и источником `plan`.

        Ловит мутацию: код, который читает `budget_usd` из PLAN.md, но не
        поднимает потолок задачи (`store.update_task` для `budget_usd`
        пропущен) — тест поймает по неизменному `budget_usd` в строке
        задачи после перехода.
        """
        self.enter_in_dev()
        self.set_budget(45.0, "spec")
        since = len(self.steps())

        self.submit_plan(budget_usd=90)

        self.assertEqual(self.state(), "review",
                         "переход in_dev -> review обязан пройти: PLAN.md "
                         "status: ready, budget_usd в пределах ROLE_BUDGET_CAP")
        row = self.task_row()
        self.assertEqual(row["budget_usd"], 90.0)
        self.assertEqual(row["budget_source"], "plan")
        tail = self.journal_tail(since)
        self.assertIn("$45.00", tail, f"журнал обязан назвать старый потолок: {tail!r}")
        self.assertIn("$90.00", tail, f"журнал обязан назвать новый потолок: {tail!r}")
        self.assertIn("plan", tail, f"журнал обязан назвать источник plan: {tail!r}")

    def test_ac1_ceiling_never_exceeds_role_budget_cap(self):
        """PLAN.md первой сдачи несёт `budget_usd`, значение которого (если
        бы его применили буквально) превышало бы `ROLE_BUDGET_CAP` — но
        сама передача такого PLAN.md проверяется гейтом guard части 1
        (AC-6), не этим тестом; здесь фиксируется зеркальное свойство
        части 2: значение РОВНО на потолке ролей — предельный легальный
        случай — применяется целиком, без искусственного занижения.

        Ловит мутацию: код части 2, который поднимает потолок PLAN'ом
        безусловно (без проверки `<= ROLE_BUDGET_CAP`) ИЛИ который,
        наоборот, всегда режет значение произвольным меньшим числом —
        оба варианта разойдутся с ожиданием «потолок = ROLE_BUDGET_CAP
        ровно» на предельном значении.
        """
        self.enter_in_dev()
        self.set_budget(45.0, "spec")

        self.submit_plan(budget_usd=config.ROLE_BUDGET_CAP)

        self.assertEqual(self.state(), "review")
        row = self.task_row()
        self.assertEqual(row["budget_usd"], config.ROLE_BUDGET_CAP)
        self.assertEqual(row["budget_source"], "plan")


class Ac2MissingBudgetFieldTest(PlanBudgetSandbox):

    def test_ac2_missing_budget_usd_field_leaves_ceiling_unchanged(self):
        """PLAN.md первой сдачи не несёт поля `budget_usd` вовсе — потолок
        задачи и его источник остаются прежними.

        Ловит мутацию: код, который трактует отсутствие поля как «0» или
        «применить дефолт», вместо того чтобы оставить потолок нетронутым
        — тест поймает по изменившемуся `budget_usd`/`budget_source`.
        """
        self.enter_in_dev()
        self.set_budget(45.0, "spec")

        self.submit_plan(budget_usd=None)

        self.assertEqual(self.state(), "review")
        row = self.task_row()
        self.assertEqual(row["budget_usd"], 45.0)
        self.assertEqual(row["budget_source"], "spec")


class Ac3LowerBudgetNotAppliedTest(PlanBudgetSandbox):

    def test_ac3_plan_budget_not_above_ceiling_is_not_applied(self):
        """PLAN.md первой сдачи несёт `budget_usd: 30` при текущем потолке
        $45 (не выше потолка) — потолок остаётся прежним, а в журнал
        попадает запись «не применён: ниже потолка».

        Ловит мутацию: код, который поднимает потолок ДО значения из PLAN
        даже когда оно не выше текущего (например, сравнение `<` вместо
        `<=`, или отсутствие сравнения вовсе) — тест поймает по
        изменившемуся `budget_usd` строки задачи.
        """
        self.enter_in_dev()
        self.set_budget(45.0, "spec")
        since = len(self.steps())

        self.submit_plan(budget_usd=30)

        self.assertEqual(self.state(), "review")
        row = self.task_row()
        self.assertEqual(row["budget_usd"], 45.0)
        self.assertEqual(row["budget_source"], "spec")
        tail = self.journal_tail(since)
        self.assertIn("не применён: ниже потолка", tail,
                     f"журнал обязан нести ровно эту фразу (SPEC AC-3): {tail!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
