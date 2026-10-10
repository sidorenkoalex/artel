---
task: 01M4KAJ0BJ9EC37RWXNFKQN7DW
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: amend-tests: признак сетевых адресов только для артели

# ТЗ: amend-tests — признак сетевых адресов только для артели

Источник: строка бэклога 10.10 «amend-tests: признак сетевых адресов
только для артели» (приоритет 3, остаток ревью 01M4JN2EDQP8Q3WVYK0TS95ZVC,
замечание R1-F1); решение Оператора 10.10.2026 — заводить тестовой задачей
сессии ассистента в Codex.

Факты (main c7cc23db, сверка 10.10):
- `scripts/guard.py::long_lived_errors_from_files` (~2766) принимает
  именованный параметр `network_addresses: bool = True`: при `True` в
  ошибки долгоживущих файлов входит признак адреса по DNS-имени
  (инвариант 35, функция `guard.network_address_hits`).
- Выход из `tests_writing` передаёт `network_addresses =
  repo_context.is_artel(target)` (`orchestrator/fsm_advance.py` ~468,
  `orchestrator/advance_gates/tests_writing.py`): у чужого проекта признака
  нет.
- `orchestrator/amend.py::_long_lived_errors` (~493) зовёт
  `guard.long_lived_errors_from_files(sorted(files.items()), task_id)` без
  параметра (~510): `amend-tests` чужого проекта отказывает долгоживущему
  тесту с адресом вроде `https://api.stripe.com/v1` со ссылкой на
  неприменимый к нему инвариант 35, обхода у Оператора нет.

Требуется:
1. `amend-tests` передаёт узлу признак проекта так же, как выход из
   `tests_writing`: у артели признак адресов действует, у чужого проекта —
   нет. Остальные проверки долгоживущих файлов в `amend-tests` не меняются.
2. Ослабления для артели нет: долгоживущий файл артели с адресом по
   DNS-имени по-прежнему даёт отказ `amend-tests` с файлом и строкой.
3. Смена поведения существующих тестов — только разделом SPEC
   «Меняемое поведение» (инвариант 38).

Критерии приёмки (направление; планку пишет test_author):
- `amend-tests` задачи артели: долгоживущий файл с `https://example.test/x`
  — отказ, в тексте файл, строка и инвариант 35.
- `amend-tests` задачи чужого проекта (подменённый `is_artel` либо target
  песочницы): тот же файл — признака адресов нет; прочие ошибки файла,
  если есть, остаются.
- Мутация «amend-tests зовёт узел без признака проекта» ловится тестом.

Зоны: orchestrator/amend.py, docs/codebase-map.md, tests/.

Только чтение (не менять): scripts/guard.py,
orchestrator/advance_gates/tests_writing.py, orchestrator/fsm_advance.py,
orchestrator/repo_context.py, orchestrator/acceptance.py,
orchestrator/notes.py, orchestrator/suite_lock.py, orchestrator/config.py,
orchestrator/store.py, tests/test_invariants.py, .github/workflows/ci.yml,
docs/invariants.md, docs/triggers.md, docs/adr/, docs/roadmap.md,
docs/backlog.md, docs/operator-session.md, templates/, skills/, CLAUDE.md,
models.yaml, roles.yaml, targets.yaml, .artel/.

Не входит: действие отказа рубежа адресов (общее «переход отклонён», R1-F2
ревью 01M4JN2EDQ); полный прогон и его сигнал
(01M4K2767FXKZ8EW7AME81SZ9N); адреса вне tests/.

Рамка: $10.

Набор моделей: по умолчанию.
