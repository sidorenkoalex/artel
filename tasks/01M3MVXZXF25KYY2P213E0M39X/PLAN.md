---
task: 01M3MVXZXF25KYY2P213E0M39X
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Защищённые пути — настройки сбора тестов (conftest.py, pyproject.toml и родственные)

## Подход

Сравнение пути с перечнем защищённых путей сводится к одному помощнику
`config.is_protected_path(path, protected=None)` в `orchestrator/config.py`
(без импортов пульта — модуль и сегодня импортирует только `pathlib`).
Смысл записи:
- запись вида `**/<имя>` — совпадение последнего компонента пути с `<имя>`
  (`path.rsplit("/", 1)[-1] == имя`), в любом каталоге, включая корень;
- любая другая запись — сегодняшняя префиксная формула `path == запись or
  path.startswith(запись)`.

`protected=None` — перечень `config.PROTECTED_PATHS`, прочитанный В МОМЕНТ
вызова (тесты подменяют его `mock.patch.object(config, "PROTECTED_PATHS")`,
`ModelsCatalogIsProtectedTest.test_gate_reads_the_list_at_call_time_not_at_import`).
Явный `protected` нужен `ci_protected_paths.is_violation` (перечень базы
сравнения, требование 8) и условию полного прогона (требование 10).

Перечень пополняется пятью строковыми литералами в конце кортежа — разбор
`protected_paths_from_source` модульным `ast` не меняется.

`scripts/ci_protected_paths.py` запускается как скрипт (`sys.path[0]` —
`scripts/`), поэтому для импорта `orchestrator.config` добавляет корень
репозитория в `sys.path` тем же приёмом, что `scripts/guard.py:45`.
Модуль остаётся stdlib-only: `orchestrator/config.py` сторонних пакетов не
тянет.

Условие полного прогона (`fsm_merge_gate._appendix_needs_full_suite`):
перечень `_FULL_SUITE_APPENDIX_PREFIXES` пополняется записями
`**/conftest.py`, `pyproject.toml`, `pytest.ini`, `setup.cfg`, `tox.ini`, а
сверка идёт тем же помощником с явным перечнем — для `tests/`/`.github/`
вердикт прежний (префикс), новые пути требуют полного прогона.

Бюджет SPEC ($45) не переоцениваю: объём совпадает с оценкой SPEC.

## Шаги

1. `orchestrator/config.py`: помощник `is_protected_path` и пять новых
   записей `PROTECTED_PATHS` (17 всего, прежние 12 на местах).
2. Шесть мест сверки зовут помощника, имена и сигнатуры сохраняются:
   `fsm_merge_gate._touches_protected_path`,
   `advance_gates/zones._protected_paths_touched`,
   `ci_protected_paths.is_violation`,
   `guard._appendix_path_is_protected`, `guard.protected_zones`,
   `github_adapter._touched_protected_paths`.
3. `fsm_merge_gate._FULL_SUITE_APPENDIX_PREFIXES`/`_appendix_needs_full_suite`
   — новые пути требуют полного прогона.
4. `docs/stack.md`, раздел «Паритет безопасности роли…» — строка прозы
   после таблицы (таблица не меняется).
5. Тесты: новый `tests/test_protected_test_settings.py` (AC-1..AC-11);
   сторожа долгоживущих свойств (состав перечня, условие полного прогона,
   маска в шести местах) — на реальном перечне в `tests/`, не только в
   планке (R1-F1); прогон затронутых модулей; регенерация карты
   `python3 scripts/codebase_map.py`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 2 |
| 6 | 1, 2 |
| 7 | 2 |
| 8 | 1, 2 |
| 9 | 2 |
| 10 | 3 |
| 11 | 4 |
| 12 | 5 |

## Влияние на систему

- Гейты защищённых путей (зоны `in_dev → review`, дифф на мерже, джоб CI
  `protected-paths`, допуск приложения PLAN, подсветка Draft MR, пометка
  защищённых зон SPEC) — только усиливаются: на прежних 12 записях вердикт
  пяти мест не меняется (формула та же), `guard.protected_zones`
  расходится с прежним `zone_lock._covered_by` только на путях «файл-запись
  плюс суффикс» (`CLAUDE.md.bak`) и только в сторону «защищён» (требование
  6 SPEC).
- Джоб CI читает перечень БАЗЫ: на этой ветке база ещё несёт 12 записей,
  поэтому собственный PR задачи новыми путями не красится (сама ветка
  `conftest.py`/`pyproject.toml` не трогает).
- `zone_lock._covered_by` не меняется — общие зоны сверяются как прежде.
- Полный прогон на мерже расширяется на приложения к настройкам сбора
  тестов — дороже мерж только для таких приложений.
- Откат — revert одного merge-коммита.

## Риски

- Импорт `orchestrator.config` из `scripts/ci_protected_paths.py`:
  скрипт в CI запускается `python3 scripts/ci_protected_paths.py` — без
  вставки корня в `sys.path` импорт упадёт. Закрыто вставкой корня тем же
  приёмом, что у `guard.py`; проверено тестами, которые запускают модуль.
- `docs/invariants.md:84` отстаёт от перечня ещё на пять записей —
  защищённый путь, вне зоны (SPEC «Материалы»).

## Проверка

Коммит `6cb9ae0f`. Прогоны (в переднем плане, `-p timeout -o timeout=120`):
- планка задачи `tasks/01M3MVXZXF25KYY2P213E0M39X/acceptance_tests/` и
  планка `tasks/01M31DRD81092HB69J0MAKZMGH/acceptance_tests/` (джоб CI как
  скрипт) плюс `tests/test_protected_test_settings.py`,
  `test_protected_paths_gate`, `test_ci_protected_paths`,
  `test_plan_appendix`, `test_guard_path_mentions`, `test_zones_gate`,
  `test_github_adapter`, `test_stack_parity_table`,
  `test_catalog_tz_path_check`, `test_fsm_spec_gate_path_check` — 168
  passed, 97 subtests;
- `test_invariants`, `test_guard_zones`, `test_test_integrity_gate`,
  `test_fsm_advance_gate_smoke`, `test_conftest_role_guard`,
  `test_codebase_map` — 168 passed, 221 subtests.
Карта регенерирована тем же коммитом.

Итерация 2 (R1-F1), коммит `ff0bd09a`: в
`tests/test_protected_test_settings.py` добавлены сторожа долгоживущих
свойств на РЕАЛЬНОМ перечне, без подмены — состав `PROTECTED_PATHS`
(прежние 12 на местах + 5 новых, всего 17) и те же записи в тексте
`orchestrator/config.py` через `protected_paths_from_source`;
`_appendix_needs_full_suite` на `conftest.py`, `tests/conftest.py`,
`tests/sub/conftest.py`, `pyproject.toml`, `pytest.ini`, `setup.cfg`,
`tox.ini` (и ложь на `skills/spec-authoring.md`); каждое из шести мест
требования 5 признаёт эти пути и не признаёт `tests/test_store.py`,
`orchestrator/store.py`, `tests/test_conftest_role_guard.py`,
`docs/pyproject.md`, `tests/pytest.ini`. Докстринг модуля переписан.
Мутанты (в процессе): перечень 12 записей + прежнее условие полного
прогона — красные 7 тестов (состав, полный прогон, пять мест на реальном
перечне; CI-место краснеет при правке исходника — его тест читает текст
`config.py`); откат `_touches_protected_path` к префиксной формуле —
красный `test_merge_gate_diff_check`. Прогон
`test_protected_test_settings`, планка задачи, `test_protected_paths_gate`,
`test_ci_protected_paths`, `test_guard_mutation_claim` — 68 passed, 167
subtests; `test_protected_test_settings`, `test_codebase_map`,
`test_plan_appendix`, `test_zones_gate`, `test_github_adapter`,
`test_guard_zones` — 146 passed, 95 subtests. Карта регенерирована тем же
коммитом.

## Предложения системе

- `docs/invariants.md:84` перечисляет состав `PROTECTED_PATHS` прозой и
  отстаёт от кода уже на шесть записей (`models.yaml` и пять новых) —
  прозу стоит заменить ссылкой на `config.PROTECTED_PATHS` (правит
  Оператор: путь защищённый).
