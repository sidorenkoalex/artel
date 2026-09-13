---
task: 01M2CYQR0357VAQFZ5VACJD9TD
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Рефакторинг: fsm_advance.py — гейты в пакет orchestrator/gates/

Источник: отчёт ревизии №6 docs/audits/code-revision-2026-09-13.md, находка
CR-2026-09-13-3 ★ и ТЗ-черновик Р-3. Решение Оператора 13.09: волна
рефакторинга, задача класса «рефакторинг» по правилам T015. Р-1 (01M2CN3VV9, checkpoint.py) и
Р-2 (01M2CN3ZCS, runner.py) смержены 13.09; тихое окно — параллельных
задач нет (конфликт-магнит).

Факты:
- orchestrator/fsm_advance.py — 1564 строки, 39 функций, 28 коммитов с
  06.09; гейты: `_zones_gate` :839 (123), `_capacity_gate` :584 (102),
  `_mutation_claim_gate` :1082 (93), `_review_rework_gate` :1177 (90),
  `_acceptance_run_refuses` :1363 (74), `_acceptance_lock_refuses` :1299
  (62), `_tests_writing_stray_plank_files_gate` :411 (59); обработчики
  состояний `spec_writing` :62, `tests_writing` :511, `in_dev` :1496;
  эффекты `_apply_plan_budget` :1439.
- Потребители имён снаружи: orchestrator/answer.py:31 берёт
  `_split_zone_paths`, `_plan_zones_extension_paths`,
  `_ZONES_MANDATE_MARKER`; 21 тестовый файл зовёт гейты напрямую
  (`_mutation_claim_gate` x13, `_run_gates` x9); единственный патч через
  модуль — tests/test_git_fixation.py:359 (`_capacity_gate_refuses`);
  `_acceptance_run_refuses` сознательно идёт мимо `_run_gates` (докстринг
  :1369); литералы префиксов :760 и :1038.

Требуется (поведение не меняется):
1. Пакет orchestrator/gates/: `__init__.py`; `_base.py` (`GateRefusal`,
   `_run_gates` — нужны всем семействам; оставить их в fsm_advance.py
   нельзя из-за цикла импортов); `zones.py`; `capacity.py` (с
   `_EMPTY_DIFF_TEXT`, `CAPACITY_GATE_REASON`); `review.py`
   (`_review_escalation_sha_gate`, `_mutation_claim_gate`,
   `_review_rework_gate`, помощники дат и sha); `acceptance.py`
   (`_acceptance_lock_refuses`, `_acceptance_run_refuses`);
   `tests_writing.py` (`_tests_writing_*`, `_origin_push_gate`,
   `_registry_gate`, `_freshness_refuses`). Перенос дословно.
2. В fsm_advance.py остаются обработчики состояний, эффекты вердиктов
   (`_review_approved`, `_in_dev_plan_escalate`, `_apply_plan_budget`) и
   алиасы старых имён на одну волну (answer.py не правится и в зонах нет;
   тесты, зовущие гейты через fsm_advance, продолжают работать).
3. Поверхности неизменности: тексты отказов гейтов, тексты и порядок
   записей журнала, коды выхода, схема БД. Логика гейтов — защита:
   дословно, включая обход `_run_gates` у приёмки. Зелёность полного
   набора tests/ = неизменность.
4. Тесты: только импорты и пути патчей в tests/test_zones_gate.py,
   tests/test_capacity_gate.py, tests/test_mutation_claim_gate.py,
   tests/test_fsm_review_rework_gate.py,
   tests/test_fsm_review_rework_sha_gate.py,
   tests/test_protected_paths_gate.py,
   tests/test_fsm_advance_gate_framework.py,
   tests/test_fsm_advance_gate_smoke.py, tests/test_review_registry_gate.py.
5. docs/codebase-map.md регенерируется штатно. Ёмкость диффа ~1100 строк
   (< 256 КиБ).
6. PLAN: таблица переносов, откат revert'ом одного merge, смоук до/после.

Зоны: orchestrator/gates/__init__.py, orchestrator/gates/_base.py,
orchestrator/gates/zones.py, orchestrator/gates/capacity.py,
orchestrator/gates/review.py, orchestrator/gates/acceptance.py,
orchestrator/gates/tests_writing.py, orchestrator/fsm_advance.py,
docs/codebase-map.md, tests/.

Приложением: orchestrator/answer.py:31 (потребитель алиасов — не правится).

Не входит: логика гейтов и тексты отказов; answer.py; порядок гейтов.

Рамка: $45.
