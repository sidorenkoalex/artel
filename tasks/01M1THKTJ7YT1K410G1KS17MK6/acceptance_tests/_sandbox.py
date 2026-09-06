"""Общие фикстуры приёмочных тестов 01M1THKTJ7YT1K410G1KS17MK6 (SPEC:
«ADR-0014, часть 1 — потолок ролей и обязательный budget_usd в SPEC»).

Два независимых угла проверки, оба уже применялись прежними задачами:

- Guard — чёрный ящик над `scripts.guard.check_content` (текст SPEC/PLAN
  строится строкой, без импорта ещё не написанной реализации новых
  правил) — тот же приём, что tasks/01M1KS8K9RXWHX2PW3ZKB0P903/
  acceptance_tests/_sandbox.py уже держит для сигналов объёма.
- Потолок задачи — прямой вызов `budget.spec_budget`/
  `budget.apply_spec_budget` над строкой `tasks`, заведённой напрямую
  `store.insert_task` (без `catalog.cmd_new`/git — самому механизму
  потолка ветка/worktree задачи не нужны), тот же приём, что
  tasks/01M1NWCM3TDY0YABEKE8DYQA1C/acceptance_tests/_sandbox.py
  (`CostTmpRootTest`) уже держит для похожего угла бюджета.

Не `test_*.py` — guard.py читает AC-разметку и маркер красноты только из
`test_*.py` (scripts/guard.py::scan_acceptance_tests/scan_redness_markers)
— этот файл вспомогательный, не сам критерий.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import budget, config, store  # noqa: E402
from scripts import guard  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

FIXTURE_TASK_ID = "01M1THKTJ7YT1K410G1KS17MK6-FIXTURE"

# Формат budget_usd управляется отдельно (`budget_field`) — `None` убирает
# строку поля целиком (для сценариев «поля нет вовсе»).
SPEC_TEMPLATE = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: {schema_version}
{budget_field}zones: orchestrator/config.py
---

# SPEC: фикстура потолка ролей

## Контекст
Фикстура приёмочного теста задачи 01M1THKTJ7YT1K410G1KS17MK6 — короткий
безобидный текст, не связанный с реальной механикой пульта.

## Требования
1. Первое требование фикстуры.

## Критерии приёмки
AC-1. Первый критерий фикстуры.
AC-2. Второй критерий фикстуры.

## Не входит
- Всё остальное.
"""

PLAN_TEMPLATE = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: {schema_version}
{budget_field}---

# PLAN: фикстура потолка ролей

## Подход
Фикстура.

## Шаги
1. Единственный шаг фикстуры.

## Покрытие требований
| Требование | Шаг |
|---|---|
| 1 | 1 |

## Влияние на систему
Фикстура не затрагивает ничего за пределами себя.
"""


def _budget_field(value) -> str:
    """Строка `budget_usd: <value>\\n` фронтматтера — `None` убирает поле
    целиком (не путать со значением `""`, которое пишет ПУСТУЮ строку
    поля — YAML читает её как None, что для guard/`spec_budget` эквивалентно
    «поле есть, но не число»)."""
    if value is None:
        return ""
    return f"budget_usd: {value}\n"


def spec_text(*, schema_version=5, budget=25, task=FIXTURE_TASK_ID) -> str:
    return SPEC_TEMPLATE.format(task=task, schema_version=schema_version,
                                budget_field=_budget_field(budget))


def plan_text(*, schema_version=4, budget=25, task=FIXTURE_TASK_ID) -> str:
    return PLAN_TEMPLATE.format(task=task, schema_version=schema_version,
                                budget_field=_budget_field(budget))


def check_spec(**kwargs) -> list[str]:
    return guard.check_content("SPEC.md", spec_text(**kwargs))


def check_plan(**kwargs) -> list[str]:
    return guard.check_content("PLAN.md", plan_text(**kwargs))


class BudgetCeilingTest(TmpRootTest):
    """Схема БД + одна задача (`self.TASK`), заведённая напрямую
    `store.insert_task` — потолку не нужны ни ветка, ни git (тот же
    приём, что `tasks/01M1NWCM3TDY0YABEKE8DYQA1C/acceptance_tests/
    _sandbox.py::CostTmpRootTest`)."""

    TASK = "T900"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Задача для теста потолка",
                          "spec_writing", "task/t900-x",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def set_task(self, **fields) -> None:
        assignments = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(f"UPDATE tasks SET {assignments} WHERE id=?",
                          (*fields.values(), self.TASK))
        self.conn.commit()

    def journal(self, action: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK,))]

    def apply(self, budget_usd) -> None:
        """`apply_spec_budget` над текущей строкой `self.TASK` и
        `meta={'budget_usd': budget_usd}` — то же самое, что вызвал бы
        `fsm_advance` на переходе spec_writing -> spec_gate."""
        budget.apply_spec_budget(self.conn, self.task_row(),
                                 {"budget_usd": budget_usd})
