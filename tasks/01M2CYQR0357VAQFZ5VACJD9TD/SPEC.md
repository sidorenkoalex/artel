---
task: 01M2CYQR0357VAQFZ5VACJD9TD
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/gates/__init__.py, orchestrator/gates/_base.py, orchestrator/gates/zones.py, orchestrator/gates/capacity.py, orchestrator/gates/review.py, orchestrator/gates/acceptance.py, orchestrator/gates/tests_writing.py, orchestrator/fsm_advance.py, docs/codebase-map.md, tests/
budget_usd: 45
---

# SPEC: Рефакторинг fsm_advance.py — гейты в пакет orchestrator/gates/

## Контекст
`orchestrator/fsm_advance.py` разросся до 1564 строк и 39 функций (28
коммитов с 06.09) — находка ревизии №6 CR-2026-09-13-3 ★ (docs/audits/
code-revision-2026-09-13.md), ТЗ-черновик Р-3, третья волна
рефакторинга FSM после Р-1 (checkpoint.py, 01M2CN3VV9) и Р-2
(runner.py, 01M2CN3ZCS), обе уже смержены 13.09. Разбор на пакет
`orchestrator/gates/` без изменения поведения снижает размер файла и
разносит семейства гейтов по темам, продолжая практику Р-1/Р-2.

## Требования

1. Создать пакет `orchestrator/gates/` дословным переносом кода (без
   изменения логики) из `orchestrator/fsm_advance.py`:
   - `__init__.py`;
   - `_base.py` — `GateRefusal`, `_run_gates`;
   - `zones.py` — семейство `_zones_gate` и его прямые помощники;
   - `capacity.py` — семейство `_capacity_gate`, включая
     `_EMPTY_DIFF_TEXT`, `CAPACITY_GATE_REASON`;
   - `review.py` — `_review_escalation_sha_gate`, `_mutation_claim_gate`,
     `_review_rework_gate` и их помощники дат/sha;
   - `acceptance.py` — `_acceptance_lock_refuses`,
     `_acceptance_run_refuses`;
   - `tests_writing.py` — `_tests_writing_*`, `_origin_push_gate`,
     `_registry_gate`, `_freshness_refuses`.
2. В `orchestrator/fsm_advance.py` остаются обработчики состояний
   (`spec_writing`, `tests_writing`, `review`, `verifying`, `in_dev`),
   эффекты вердиктов (в т.ч. `_review_approved`, `_in_dev_plan_escalate`,
   `_apply_plan_budget`) и алиасы старых имён перенесённых функций —
   на одну волну. `orchestrator/answer.py` не правится (не в зонах
   задачи) и продолжает брать `_split_zone_paths`,
   `_plan_zones_extension_paths`, `_ZONES_MANDATE_MARKER` из
   `orchestrator/fsm_advance.py` через эти алиасы.
3. Поведение не меняется: тексты отказов гейтов, тексты и порядок
   записей журнала, коды выхода, схема БД — идентичны до и после
   переноса. Логика гейтов переносится дословно, включая обход
   `_run_gates` у `_acceptance_run_refuses` (докстринг фиксирует это
   решение). Полный набор `tests/` зелёный и до, и после переноса.
4. Только импорты и пути патчей (без изменения проверяемой логики)
   правятся в: `tests/test_zones_gate.py`, `tests/test_capacity_gate.py`,
   `tests/test_mutation_claim_gate.py`,
   `tests/test_fsm_review_rework_gate.py`,
   `tests/test_fsm_review_rework_sha_gate.py`,
   `tests/test_protected_paths_gate.py`,
   `tests/test_fsm_advance_gate_framework.py`,
   `tests/test_fsm_advance_gate_smoke.py`,
   `tests/test_review_registry_gate.py`.
5. `docs/codebase-map.md` регенерируется штатным
   `python3 scripts/codebase_map.py` тем же коммитом, что правит
   `*.py`. Ёмкость диффа снимка укладывается в текущий потолок гейта
   ёмкости (диф ~1100 строк, < 256 КиБ).
6. PLAN.md несёт: таблицу переносов (функция → файл-источник →
   файл-назначение), способ отката (revert одного merge-коммита) и
   смоук-проверку до/после переноса.

## Критерии приёмки

AC-1. Создан пакет `orchestrator/gates/` с файлами `__init__.py`,
`_base.py`, `zones.py`, `capacity.py`, `review.py`, `acceptance.py`,
`tests_writing.py`; перечисленные в требовании 1 функции/константы
физически перенесены дословно в соответствующий файл.

AC-2. `orchestrator/fsm_advance.py` сохраняет обработчики состояний,
эффекты вердиктов (`_review_approved`, `_in_dev_plan_escalate`,
`_apply_plan_budget`) и алиасы старых имён на все перенесённые
функции/константы; `orchestrator/answer.py` не изменён и продолжает
работать без правок.

AC-3. Тексты отказов гейтов, тексты и порядок записей журнала, коды
выхода и схема БД идентичны состоянию до переноса; обход `_run_gates`
у `_acceptance_run_refuses` сохранён; полный набор `tests/` зелёный.

AC-4. В перечисленных требованием 4 девяти тестовых файлах изменены
только импорты и пути патчей — проверяемая тестами логика не менялась.

AC-5. `docs/codebase-map.md` регенерирован командой
`python3 scripts/codebase_map.py` тем же коммитом, что правит `*.py`;
диф снимка задачи укладывается в действующий потолок ёмкости (< 256
КиБ).

AC-6. `PLAN.md` содержит таблицу переносов функций по файлам, способ
отката (revert одного merge-коммита) и описание смоук-проверки
до/после переноса.

## Не входит

- Изменение логики гейтов и текстов их отказов.
- Правки `orchestrator/answer.py`.
- Изменение порядка вызова гейтов.

## Материалы

- docs/audits/code-revision-2026-09-13.md — находка CR-2026-09-13-3 ★.
- Р-1 (01M2CN3VV9, checkpoint.py) и Р-2 (01M2CN3ZCS, runner.py) —
  предыдущие волны того же класса рефакторинга.
