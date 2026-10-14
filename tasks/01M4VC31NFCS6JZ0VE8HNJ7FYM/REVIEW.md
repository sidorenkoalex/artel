---
task: 01M4VC31NFCS6JZ0VE8HNJ7FYM
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Чистый прогон канарейки учитывает эскалацию аудитора SPEC по той же ловушке

## Фаза A — план
- Таблица покрытия полна (требования 1–6). Новый шаг 6 закрывает R1-F1,
  шаги размера MR. «Влияние на систему» соответствует diff: инкремент
  итерации 2 касается только `tests/test_canary_escalation_roles_storage.py`.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | логика без изменений с итерации 1. Связку `_run_one_task` → колонка `escalation_roles` теперь держит `tests/test_canary_escalation_roles_storage.py::RunOneTaskRecordsEscalationRolesTest`: подменён только `_run_task_in_ephemeral_clone`, маркеры стоят за фиксацией |
| 2 | OK | без изменений с итерации 1 |
| 3 | OK | без изменений с итерации 1 |
| 4 | OK | без изменений с итерации 1 |
| 5 | OK | без изменений с итерации 1 |
| 6 | OK | долгоживущий файл задачи и `tests/test_canary_escalation_roles_storage.py` (два класса) |

## Замечания

Новых замечаний нет. Новый тест сверен с заявкой «Ловит мутацию»: мутация
`escalation_roles=None` в `canary.py:2633` — тест красный (подробности ниже).
Заявка называет наблюдаемое расхождение: колонка `NULL` вместо
`'analyst,spec_auditor'`. Долгоживущий файл задачи этой связки не держит,
поэтому тест её не повторяет. Утверждения тестов, существовавших в базе, не
менялись: дифф итерации 2 только добавляет класс и меняет импорт.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/canary.py:2633 | передачу ролей из `_run_one_task` в строку `canary_runs` проверяла только разовая планка | после мержа потеря аргумента молча вернула бы строки к `NULL` | сторож добавлен (`RunOneTaskRecordsEscalationRolesTest::test_row_carries_roles_computed_from_clone_steps`). Ревьювер проверил его временной мутацией: тест красный |

## Вердикт
approved — R1-F1 закрыто, блокеров и major нет.

## Проверено исполнением
- `python3 -m pytest -q tests/test_canary_escalation_roles_storage.py tests/test_01m4vc31nfcs6jz0ve8hnj7fym_escalation_roles.py tests/test_canary_drive.py tests/test_model_sets.py` — 46 passed, 32 subtests passed.
- Временная мутация `orchestrator/canary.py:2633` `escalation_roles=escalation_roles(steps)` → `escalation_roles=None`. Прогон `tests/test_canary_escalation_roles_storage.py` — 1 failed (`test_row_carries_roles_computed_from_clone_steps`, AssertionError на строке 100), 1 passed. Код возвращён `git checkout`, `git status` чист.
- `artel.py plank-run 01M4VC31NFCS6JZ0VE8HNJ7FYM` — 3 passed, код выхода pytest 0.
- `python3 scripts/codebase_map.py` — вне строки `built_at_sha` расхождений с `docs/codebase-map.md` нет, карта свежая; файл возвращён.

## Предложения системе
