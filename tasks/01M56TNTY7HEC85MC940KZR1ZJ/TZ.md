---
task: 01M56TNTY7HEC85MC940KZR1ZJ
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Гейт неослабления: помощники по области ослабления проекта

Родительская задача: 01M56P60XS9AP4BH01YK35220D — Гейт неослабления на чужом стеке: пропуск через метку, помощники, параметризация, async
Зоны: scripts/guard.py, orchestrator/advance_gates/test_integrity.py, tests/
Порядок: первая, без зависимостей
Рамка: $25

Часть задачи 01M56P60XS9AP4BH01YK35220D (требования 6, 10, 11 её SPEC в
части помощников).

Факты: поиск вызывающих ослабленного помощника — только в `tests/`
(`orchestrator/advance_gates/test_integrity.py:631-650`), перевод имени
модуля `tests.x` → `tests/x.py` (`scripts/guard.py:1013-1019`),
импортированные функции прослеживаются только из `tests/sandbox.py`
(`guard.py:1087`); помощники sled (`backend/tests/rbac_support.py` и т. п.)
гейту невидимы. Вызовы узла из `orchestrator/review.py:650-652` и
`orchestrator/fsm_merge_gate.py:144-146` передают только предикат области;
у `review_lines`, `merge_gate_escalates`, `_test_integrity_gate` есть
`task_id`, профиль читается `project_profile.decide`.

Требуется:
1. Режим — по признаку `repo_context.is_artel`. У внешнего проекта поиск
   вызывающих и прослеживание помощников — по области ослабления профиля
   проекта задачи (`weakening_scope`), импортированная функция — из любого
   модуля области, перевод имени модуля в путь от корня проекта с учётом
   `workdir`; у артели — как сейчас (вызывающие в `tests/`, импорт только
   из `tests/sandbox.py`). Профиль узел получает внутри зон; вызовы из
   `review.py` и `fsm_merge_gate.py` не меняются (иначе — эскалация).
   `guard.TestModules`/`guard.method_literal_keys` — обратно совместимо:
   `workdir` необязателен, без него поведение прежнее; вызов в
   `orchestrator/fsm.py:1053-1060` не правится.
2. У артели прежние исходы фиксируются тестами до правки: функция своего
   модуля без `test_` — находка на вызывающем; функция `tests/sandbox.py` —
   находка; функция другого модуля `tests/` — находки нет; функция своего
   модуля с `test_` — не помощник; вызывающие ищутся только в `tests/`.
3. Тесты детерминированы, без сети, на учебном проекте с `workdir:
   backend` и `weakening_scope: [backend/tests/**/*.py]`.

Критерии приёмки: AC-9, AC-10 SPEC задачи 01M56P60XS9AP4BH01YK35220D.

Только чтение: `orchestrator/project_profile.py`, `orchestrator/advance_gates/mandate.py`,
`orchestrator/acceptance.py`, `orchestrator/review.py`, `orchestrator/fsm_merge_gate.py`,
`orchestrator/fsm.py`, `orchestrator/repo_context.py`, `targets.yaml`,
`docs/backlog.md`. Правка вне зон — эскалация.
Не входит: правило импортов долгоживущих файлов (01M5633WZ3Y3A0P4KKBZDB3KER);
не-Python стек; сверка «Меняемого поведения» на гейте SPEC
(`orchestrator/fsm.py:1053-1060`) для внешних проектов — она по-прежнему
не видит помощников вне `tests/`; пропуски, async и параметризация
(другие части).