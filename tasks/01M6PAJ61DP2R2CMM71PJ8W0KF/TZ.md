---
task: 01M6PAJ61DP2R2CMM71PJ8W0KF
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Окружение роли и doctor для compose

Родительская задача: 01M6P22XBCQS49HE92YGAB25N9 — Раннер тестов внешнего проекта в контейнере Docker Compose
Зоны: orchestrator/runner.py, orchestrator/doctor/project_checks.py, orchestrator/doctor/orphans.py, orchestrator/doctor/cli.py, orchestrator/doctor/__init__.py, docs/codebase-map.md, tests/
Порядок: после части 1
Рамка: $30

Опирается на раннер `compose` части 1 (ADR-0023, поправка 05.11.2026,
пп. 3–4; ANSWER-1.md, вопрос 3, вариант Г; вопрос 5; решения гейта SPEC
05.11 1, 2, 3, 5, 10–12, 2.1, 2.5, 2.6, 3.1 в части вызовов `doctor` и
`context inspect`). Требования 12–17 и критерии AC-17…AC-21, AC-22
(часть `docker compose version` в окружении шага роли) SPEC
01M6P22XBCQS49HE92YGAB25N9 — переносятся дословно. Поиск `docker`,
окружение вызова, имя проекта и метки живого прогона — из
`orchestrator/acceptance.py` части 1, только чтение. В
`orchestrator/doctor/__init__.py` — только экспорт новой строки и её
починки. Только чтение: `orchestrator/stack.py`,
`orchestrator/acceptance.py`.
Существующий тест краснеет — эскалация с именем теста, без правки.