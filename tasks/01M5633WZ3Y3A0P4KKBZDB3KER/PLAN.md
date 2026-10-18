---
task: 01M5633WZ3Y3A0P4KKBZDB3KER
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Долгоживущие тесты внешнего проекта: правило импортов по профилю

## Подход
Одна механика, монолитом (как в SPEC «Оценка объёма»):

- `orchestrator/targets.py` — подполе `test_profile.long_lived_imports`
  вида `identifiers` (список идентификаторов Python, `str.isidentifier`,
  возможно пустой), необязательное (`PROFILE_OPTIONAL`). У артели
  (`name == config.DEFAULT_TARGET`) присутствие подполя — отказ
  (`PROFILE_EXTERNAL_ONLY`) в `check`.
- `orchestrator/project_profile.py` — поле `Profile.long_lived_imports:
  tuple = ()`, `from_values` переносит его; функция
  `long_lived_imports(target, profile)` — единый источник правила для всех
  мест: `None` у артели (`repo_context.is_artel`), иначе перечень профиля
  (пустой без подполя).
- `scripts/guard.py` — `long_lived_errors_from_files(…,
  project_imports=None)` и `long_lived_sign_hits(…, project_imports=())`:
  имена перечня добавляются к прежнему набору `_allowed_import_tops`
  (сравнение — членство во frozenset, т.е. точное). Пояснение признака
  «импорт вне перечня» — `_foreign_import_explanation`: `None` — прежний
  литерал `_SIGN_EXPLANATIONS` (у артели текст не меняется), непустой
  перечень — «… и перечень проекта test_profile.long_lived_imports: <имена>»,
  пустой — подсказка заполнить `test_profile.long_lived_imports`.
  Новых публичных функций guard на рубежах нет — сторож «функции guard
  перехода = функции предпроверки»
  (`tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py::SentryTest`) не
  задет.
- Рубежи: `tests_writing.py` — помощник `_project_imports(task_id,
  profile)` по `workspace.task_target(task_id)` в обоих гейтах (`:361`,
  `:482`); `preflight.py` — по `target` строки задачи (БД предпроверка не
  открывает — `RoleAndDatabaseTest::test_ac8_no_store_db_and_db_file_unchanged`),
  значение передаётся в `_groups` и `_long_lived` рядом с
  `network_addresses`; `amend.py:_long_lived_errors` — по тому же
  `workspace.task_target`, что и `network_addresses`.
  `orchestrator/fsm_advance.py` не правится (требование 6).

## Шаги
1. Подполе профиля, поле `Profile`, правило в guard, передача на пяти местах;
   регенерация `docs/codebase-map.md`. Один MR.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (`targets.py`, `project_profile.py`) |
| 2 | 1 (`targets.check` — отказ у артели; `project_imports=None` — прежний текст) |
| 3 | 1 (`guard._allowed_import_tops`, `_foreign_import_explanation`) |
| 4 | 1 (пустой перечень — прежний набор и подсказка подполя) |
| 5 | 1 (`tests_writing.py` ×2, `preflight.py` ×2, `amend.py`) |
| 6 | 1 (`project_profile.long_lived_imports` через `repo_context.is_artel`; `fsm_advance.py` не тронут) |
| 7 | долгоживущие файлы test_author |

Тесты: AC-1…AC-8 покрыты долгоживущими файлами задачи
`tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py` и
`tests/test_01m5633wz3y3a0p4kkbzdb3ker_profile_imports_field.py` — 12
тестов зелёные; своих тестов сверх них не добавлено: непокрытых свойств
нет. Прогнаны соседние файлы (preflight, network_address, amend,
long_lived_*, project_profile, targets_*, test_groups, multitarget) —
зелёные.

## Влияние на систему
- Артель: правило импортов и текст отказа побайтно прежние (`project_imports
  is None` → `_SIGN_EXPLANATIONS`), подполе в её записи — отказ проверки;
  набор разрешённых имён у неё не расширяется.
- Внешний проект без подполя — прежний набор; меняется только текст
  пояснения (подсказка подполя). С подполем набор расширяется лишь
  перечнем из защищённого `targets.yaml` (пишет Оператор).
- Сигнатуры guard расширены keyword-аргументами со значением по умолчанию —
  прежние вызовы и обёртки `(files, task_id, **kwargs)` работают как раньше.
- `preflight._groups`/`_long_lived` получили параметр — внутренние, прямых
  вызовов в tests/ нет.
- Откат — revert одного merge-коммита.

## Риски
- `tests_writing` гейты зовут `workspace.task_target` (чтение БД); без
  пригодной БД он деградирует к артели — для артели правило прежнее.

## Предложения системе
- Признак артели доходит до рубежей тремя путями (флаг `network_addresses`
  из `fsm_advance.py`, `repo_context.is_artel` в `amend.py`, теперь
  `project_profile.long_lived_imports`) — кандидат на один узел «правила
  долгоживущих файлов проекта», передаваемый целиком.
