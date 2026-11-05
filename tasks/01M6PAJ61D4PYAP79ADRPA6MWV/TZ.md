---
task: 01M6PAJ61D4PYAP79ADRPA6MWV
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Ядро раннера compose

Родительская задача: 01M6P22XBCQS49HE92YGAB25N9 — Раннер тестов внешнего проекта в контейнере Docker Compose
Зоны: orchestrator/targets.py, orchestrator/project_profile.py, orchestrator/acceptance.py, orchestrator/advance_gates/two_sided.py, orchestrator/advance_gates/test_integrity.py, orchestrator/config.py, docs/codebase-map.md, tests/
Порядок: первая, без зависимостей
Рамка: $60

Ввести вид раннера `runner: compose` для доверенного внешнего проекта
(ADR-0023, поправка 05.11.2026, пп. 1–2): тесты исполняются в контейнере
сервиса Compose-файла проекта, стенд поднимается на каждый прогон и
всегда снимается. Требования 1–11, 16, 17 и критерии AC-1…AC-16, AC-22
(часть прогона вымышленного Compose-файла) SPEC
01M6P22XBCQS49HE92YGAB25N9 (с ответом Оператора ANSWER-1.md, вопросы 1,
2, 4, 5 и часть вопроса 3 о процессе роли, и решениями гейта SPEC 05.11
2–4, 6–9, 13, 2.2–2.4, 2.6, 3.1 в части вызовов места, 3.2) — переносятся дословно. Помощники, которые
берёт часть 2 (поиск `docker`, окружение вызова, префикс имени проекта,
имена меток), — публичные имена `acceptance` (требование 3).
Только чтение: `orchestrator/suite_run.py`, `orchestrator/mutation_run.py`,
`orchestrator/advance_gates/outcome_integrity.py`,
`orchestrator/reporters/outcome.py`, `orchestrator/fsm_merge_gate.py`,
`orchestrator/stack.py`, `orchestrator/runner.py` (`in_role_environment`
— вызывается, не правится). Не входит: окружение шага роли и `doctor`
(часть 2), сборка и кэш образов, `mutation_run` в контейнере, правки
ADR-0023/0026, раннеры не на pytest, недоверенные проекты (D1б).
Существующий тест краснеет — эскалация с именем теста, без правки.