---
task: 01M1THKTJ7YT1K410G1KS17MK6
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: ADR-0014, часть 1 — потолок ролей и обязательный budget_usd в SPEC

Родительская задача: 01M1SHDCW7FGJPTMD0FSFWGZ5S — бюджет задачи по ADR-0014: дефолт, потолок ролей, обязательный budget_usd в SPEC, переоценка на PLAN

# ТЗ: ADR-0014, часть 1 — потолок ролей и обязательный budget_usd в SPEC

Деление по решению Оператора 06.09 (гейт SPEC родителя, «Оценка объёма
и деление», часть 1). Нормативные тексты — ADR-0014
(`docs/adr/0014-budget-default-and-role-cap.md`) и SPEC родителя на
его артефактной ветке (`artifact/01m1shdcw7fgjptmd0fsfwgz5s`,
`tasks/01M1SHDCW7FGJPTMD0FSFWGZ5S/SPEC.md`): требования 1–5, 9,
SPEC-половина 7–8, часть 10 (шаблоны и скил аналитика); критерии
AC-1..AC-5, AC-10 (SPEC-сторона), AC-11 (первое предложение), AC-13,
AC-14 (SPEC-сценарии), AC-15 (дифы шаблонов и skills/spec-authoring.md).

Кратко:
1. `config.py`: `DEFAULT_BUDGET_USD` остаётся 50; новая
   `ROLE_BUDGET_CAP = 100.0` со ссылкой на ADR-0014.
2. `scripts/guard.py`: `SUPPORTED_SCHEMA_VERSION` → 5; для SPEC с
   `schema_version >= 5` поле `budget_usd` обязательно и должно
   разбираться как число (SPEC версии ниже 5 не проверяются); для SPEC и
   PLAN любой версии значение выше `ROLE_BUDGET_CAP` — отказ guard с
   подсказкой поделить задачу либо эскалировать вопрос бюджета.
3. `budget.spec_budget`/`apply_spec_budget`: на `spec_writing ->
   spec_gate` значение применяется в обе стороны при
   `0 < value <= ROLE_BUDGET_CAP`; потолок `budget_source = operator` не
   перебивается. Справка `orchestrator/artel.py` — по новой семантике.
4. `config.SPLIT_SIGNAL_BUDGET_USD` пересчитан: строго больше $45 и не
   больше $70, константа с обоснованием (SPEC $45 сигнал не поднимает,
   $70 — поднимает).
5. `docs/invariants.md`, инвариант 10 — SPEC-часть новой формулировки;
   `tests/test_invariants.py`: SPEC выше `ROLE_BUDGET_CAP` потолок не
   поднимает; потолок Оператора SPEC не перебивается.
6. Приложением к PLAN (защищённые пути, `git apply --check`): дифы
   `templates/SPEC.md` (новая семантика поля), синхронный подъём
   `schema_version: 4 -> 5` во всех четырёх шаблонах (SPEC, PLAN, REVIEW,
   TEST_REPORT) с полем `budget_usd` в `templates/PLAN.md` (само поле
   PLAN потребляет часть 2), `skills/spec-authoring.md` (калибровка
   ADR-0014 п.7, поле обязательно).
7. Тесты: guard отказывает SPEC v5 без поля; SPEC $80 даёт потолок $80
   (`spec`); SPEC $120 — отказ; потолок Оператора $60 не перебивается;
   существующие `test_spec_budget.py`, `test_step_cost.py`,
   `test_invariants.py` зелёные, с пересмотром тестов старой семантики
   «выше дефолта — отказ» на «выше потолка ролей — отказ».

Зоны: orchestrator/config.py, scripts/guard.py, orchestrator/budget.py,
orchestrator/artel.py, docs/invariants.md, tests/.
Порядок: первая, без зависимостей.
Не входит: переоценка на PLAN (часть 2); авто-подъём при исчерпании;
стоп-лосс программы; прямая правка шаблонов и скилов.
Рамка: $40.
