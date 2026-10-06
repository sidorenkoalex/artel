---
task: 01M490TDWEMDQ700VXTKYANF7K
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: guard --all принимает паспорт задачи артели без frontmatter

## Подход
Один признак паспорта в `scripts/guard.py` — `is_task_passport(path)`: имя
`PASSPORT.md` и каталог файла лежит прямо в каталоге `tasks`
(`path.parent.parent.name == "tasks"`). Признак по имени и уровню, не по
содержимому — `JOURNAL.md` с тем же текстом остаётся посторонним (AC-2).

- `main`, режим `--all`: паспорт первого уровня исключается из списка
  файлов, идущих в `check` (рядом с исключением посторонних файлов).
  Белый список первого уровня `TASK_ROOT_ALLOWED_MD` не меняется —
  `PASSPORT.md` в нём уже был; посторонние `.md` первого уровня и любой
  файл вложенного каталога по-прежнему отказ (AC-2, AC-5).
- `main`, одиночный файл: для паспорта печатается
  `<путь>: паспорт задачи, не артефакт роли — пропущен`, `check`/
  `spec_path_errors`/`plan_appendix_errors` не зовутся, код 0 (AC-6).
  `PASSPORT.md` не первого уровня идёт в `check` как прежде (AC-7).
- `is_extraneous_acceptance_test_file`: `PASSPORT.md` в
  `acceptance_tests/` — посторонний файл планки. SPEC (требование 1)
  исходил из того, что он уже посторонний, но белый список планки
  `.+\.md` его пускал, и выходило «нет frontmatter» вместо именованной
  причины; AC-4 и долгоживущий тест требуют именованную причину. Это
  ужесточение, не ослабление.

Бюджет SPEC не пересматривается.

## Шаги
1. `scripts/guard.py`: `TASK_PASSPORT_NAME`, `PASSPORT_SKIP_NOTE`,
   `is_task_passport`; исключение паспорта в `--all`; пропуск с пометкой в
   одиночном режиме; `PASSPORT.md` посторонний в `acceptance_tests/`.
   Регенерация `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (исключение в `--all`, прочие проверки без изменений; AC-1..AC-5) |
| 2 | 1 (пропуск с пометкой в одиночном режиме; AC-6, AC-7) |
| 3 | долгоживущий `tests/test_01m490tdwemdq700vxtkyanf7k_passport_guard.py` (ADR-0020), отдельные тесты не дописаны — SPEC: «повторять те же свойства не нужно» |

Прогоны:
- `python3 -m pytest tests/test_01m490tdwemdq700vxtkyanf7k_passport_guard.py tests/test_guard_extraneous_acceptance_files.py tests/test_guard_task_root_subdirectory.py tests/test_checkpoint_stray_acceptance_files.py tests/test_guard_schema.py tests/test_advance_guard.py -p no:cacheprovider -p timeout -o timeout=120` — 90 passed, 47 subtests passed (долгоживущий файл — 7/7 зелёный).
- `python3 scripts/guard.py --all` на дереве рабочей копии — `GUARD: ок (1502 файлов)`.
- Полный набор `suite-run` — см. «Риски».

## Влияние на систему
- Гейт мержа (`orchestrator/fsm_merge_gate.py::_guard_all_violations`)
  зовёт `guard --all` — после правки мерж задач артели с паспортом не
  отказывает; правка действует уже на мерже этой задачи.
- Ослабления нет: пропуск — только файл с именем `PASSPORT.md` прямо в
  `tasks/<id>/`; паспорт и раньше был в белом списке первого уровня, у
  пульта он не артефакт роли. Соседние артефакты проверяются полностью
  (AC-3). В `acceptance_tests/` правило строже прежнего.
- Инвариант «guard структуры артефактов» (`docs/invariants.md`) не
  меняется по смыслу: проверяются артефакты ролей.
- Откат — revert коммита задачи.

## Риски
- `orchestrator/checkpoint.py::_is_stray_acceptance_test_file` повторяет
  белый список планки той же регуляркой независимо (вне зоны задачи):
  автокоммит не сочтёт `acceptance_tests/PASSPORT.md` случайным файлом, а
  guard назовёт его посторонним. Расхождение безвредно (отказ guard
  громкий), но копии разошлись — см. «Предложения системе».
- Полный набор в шаге не прогнан: все три вызова `suite-run` отказали —
  «на машине уже идёт прогон гейта задачи 01M48WR0HKZW8KJCBWDZTFC4ZY
  (pid 98900)». Вместо него прогнаны модули guard по одному вызову:
  `tests/test_guard_{artifact_branch_mode,artifact_disk_read,assertion_changes,division_section,mutation_claim,path_mentions,split_signals,test_ast,test_groups,zones}.py tests/test_invariants.py tests/test_codebase_map.py`
  — 255 passed, 293 subtests passed. Полный набор прогонят гейты пульта.

## Предложения системе
- Белый список `acceptance_tests/` живёт в двух копиях
  (`scripts/guard.py::ACCEPTANCE_TESTS_ALLOWED_TOP_LEVEL` и
  `orchestrator/checkpoint.py::_is_stray_acceptance_test_file`) — эта
  задача уже развела их по `PASSPORT.md`; стоит сторож на совпадение или
  общий источник.
- SPEC-автор утверждал «по-прежнему посторонний» про
  `acceptance_tests/PASSPORT.md`, не сверив с регуляркой; поймал это
  только долгоживущий тест (AC-4 красен до реализации) — полезно, чтобы
  analyst сверял «прежнее поведение» прогоном guard.
