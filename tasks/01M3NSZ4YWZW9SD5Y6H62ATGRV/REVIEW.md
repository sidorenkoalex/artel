---
task: 01M3NSZ4YWZW9SD5Y6H62ATGRV
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: amend-tests для долгоживущих файлов в tests/ и исключение их из диффа ревью и меры гейта ёмкости

## Фаза A — план

- Таблица покрытия полна: требования 1–9 → шаги 1–5.
- Дефект итерации 1 закрыт. Шаг 4 теперь явно называет сторожей ядра
  требований 1–6 в `tests/` и объясняет почему: планка целиком разовая,
  после мержа её не гоняет никто, поэтому п.4 ADR-0020 («не повторять
  долгоживущие») здесь не мешает.
- «Влияние на систему» совпадает с фактическим диффом. Эта итерация
  (`cf552455..922c4a68`) трогает только `tests/test_amend_long_lived.py`
  (расширен), `tests/test_review_long_lived_exclude.py` (новый) и карту.
  Код `orchestrator/` не менялся.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Реализация прежняя (проверена в итерации 1). Сторожа: `WorktreeModeTest.test_modified_and_added_long_lived_relocked` (коммит ровно с правленными путями, перечень по новой голове, сверка сумм проходит) и `test_failed_check_refused_before_any_write` (5 нарушений — отказ без записей) |
| 2 | OK | Сторожа: `test_docs_write_failure_names_recovery_then_from_branch_relocks`, `FromBranchModeTest.test_violating_code_head_refused_without_writes`, `test_bypass_manifest_replaced_by_recomputed` |
| 3 | OK | Во всех новых сценариях проверяется `amend_events()`: 1 при успехе, 0 при отказе и при сбое между записями |
| 4 | OK | Сторожа: `test_out_of_bounds_and_hand_manifest_refused` (4 сценария AC-3), `DeletionRuleTest` (перенос проходит, потеря метода — отказ с файлом и методом) |
| 5 | OK | Сторожа: `test_exclude_is_literal_manifest_paths`, полный и инкрементальный дифф, `test_unreadable_manifest_keeps_file_in_diff`, `CapacityGateExcludeTest` (файл перечня не меряется, тот же текст вне перечня — меряется) |
| 6 | OK | Сторож: `test_component_before_stat_inside_boundaries` — компонент с путём в заголовке, внутри маркеров запуска, до стат-списка |
| 7 | OK | Код прежний. Прежние тесты `test_review_package*.py`, `test_capacity_gate*.py`, `test_amend.py` зелёные без правок |
| 8 | OK | Без изменений с итерации 1 |
| 9 | OK | Дифф `tests/` этой итерации удаляет только строки докстринга модуля, импорт (добавлено `plank_source`) и `lock_with_own()` → `lock_with_own(self.own_source())`. Ни одного ассерта не удалено и не ослаблено. CI коммита 922c4a68 зелёный |

## Замечания

Замечаний нет. Про тесты этой итерации:
- у каждого нового метода есть докстринг со сценарием и заявкой
  «Ловит мутацию: …»; каждая заявка называет наблюдаемое расхождение
  (сдвиг голов, лишний путь в диффе, отказ сверки сумм);
- ветвлений под литералы фикстур в коде нет — код в этой итерации не
  менялся.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_amend_long_lived.py; tests/test_review_long_lived_exclude.py | Ядро требований 1–6 держала только разовая планка | После мержа регресс не ловил никто | Принято. Сторожа (1)–(7) добавлены в `tests/`. Четыре временные мутации ревьювера (включая обе мутации итерации 1, которые тогда проходили незамеченными) теперь дают красные тесты — см. «Проверено исполнением» |

## Вердикт

approved. R1-F1 закрыт: свойства, обязанные держаться после мержа
(исключение перечня лока из диффа и меры гейта, компонент пакета,
порядок проверок и записей, правило удаления, восстановление через
`--from-branch`, границы, одно `AMEND_ACTION`), теперь держат тесты
`tests/`. Это проверено временными мутациями.

## Проверено исполнением

- `python3 -m pytest -q tests/test_amend_long_lived.py tests/test_review_long_lived_exclude.py` — 18 passed, 9 subtests.
- `python3 -m pytest -q tasks/01M3NSZ4YWZW9SD5Y6H62ATGRV/acceptance_tests tests/test_amend.py tests/test_review_package.py tests/test_review_package_map.py tests/test_capacity_gate.py tests/test_capacity_gate_map.py tests/test_multitarget.py tests/test_long_lived_transitions.py` — 280 passed, 264 subtests.
- Временные мутации. После каждой код возвращён `git checkout`, `git status orchestrator` пуст:
  1. В `review.snapshot_exclude` пути перечня не добавляются (`for rel in []`). `tests/test_review_long_lived_exclude.py`: 5 failed / 1 passed. Упали кортеж, полный дифф, инкрементальный дифф, компонент и гейт ёмкости. В итерации 1 та же мутация давала 190 passed.
  2. `_is_exclude_spec` оставлен только с `:!`. Упал `test_incremental_diff_excludes_manifest_file` (1 failed / 5 passed) — ловушка SPEC держится.
  3. В `amend._long_lived_errors` условие заменено на `if False and lost:`. Упал `DeletionRuleTest.test_lost_method_refused_naming_file_and_method`. В итерации 1 та же мутация давала 50 passed.
  4. В `_amend_with_long_lived` коммит (а) поставлен до `_long_lived_errors`. `test_failed_check_refused_before_any_write` красный во всех подсценариях (голова кодовой ветки сдвигается при отказе).
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`: расхождений нет, карта свежая. Файл возвращён.
- Полный набор `tests/` не запускался (решение Оператора 05.09). CI коммита 922c4a68 по пакету зелёный (14 проверок).

## Предложения системе

- `tests/test_review_long_lived_exclude.py` импортирует песочницу `_LockedSandbox` из `tests/test_amend_long_lived.py`, а та — из `tests/test_long_lived_transitions.py`. Получается цепочка «тест-модуль как библиотека фикстур». Её кандидат вынести в `tests/sandbox.py`, чтобы правка одного тест-модуля не ломала чужие.
