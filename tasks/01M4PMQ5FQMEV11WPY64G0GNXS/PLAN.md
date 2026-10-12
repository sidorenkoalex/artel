---
task: 01M4PMQ5FQMEV11WPY64G0GNXS
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Итог прогона и провал внутри subTest — в отчёте suite-run и в перечнях упавших гейтов

## Подход
Один механизм в двух модулях зоны, без новых команд и без смены формата
записей кроме содержимого перечней.

- `acceptance.run_summary_line` — последнее совпадение `_RUN_SUMMARY`
  (`finditer`, последний элемент), без привязки к рамке «=» (требование 1).
- Единица упавшего подтеста — `acceptance.subtest_unit(node, label)` →
  `<nodeid> <метка>` (метка обрезается по краям, внутри не меняется — вид
  метки xdist/без xdist НЕ нормализуется, расхождение на базе даёт «новый»,
  AC-7). Один помощник для короткого итога и строк хода — ключ одного вида
  (требование 2, последний абзац).
- `acceptance._FAILED_LINE`: `^(?:(?:FAILED|ERROR) \S|SUBFAILED\S).*$` —
  прежняя ветка FAILED/ERROR эквивалентна старому `\S+.*` (AC-2, AC-10).
- `acceptance._SUBFAILED_ENTRY`: `^SUBFAILED(.*?) ?(\S*::\S*)(?: - (.*))?$` —
  nodeid — слово с `::` перед « - », метка — всё между. `failed_entries`
  сливает совпадения `_FAILED_ENTRY` (не тронут) и `_SUBFAILED_ENTRY` в
  порядке позиции в блоке; через него единицы получают `save_suite_result`
  (`gate`/`base`) и `save_failures` без правки этих функций (AC-3).
  `acceptance.subtest_parents` — единица → nodeid родителя для повтора.
- `suite_run._SUBFAILED_PROGRESS` — строки хода обоих видов по правилу SPEC
  (xdist: nodeid — последнее слово; без xdist: nodeid — первое слово, метка
  до `[NN%]`). `_progress` (счёт «выполнено тестов по логу», AC-4) не
  меняется и подтестов не видит; новый `_subtest_progress` даёт единицы
  отдельно, поэтому `PASSED <nodeid>` родителя их не снимает (требование 5).
- `suite_run.parse`: единицы из строк хода всегда, из короткого итога — у
  завершённого прогона (`dict` — одна единица на подтест, AC-5); у
  оборванного прогона «упало» = FAILED/ERROR + единицы подтестов. Новое поле
  `Parsed.rerun` (по умолчанию `()`) — nodeid для повтора: родитель вместо
  единицы, без повторов; его пишет `failed.json` (AC-8).
- `suite_run.render`: у завершённого прогона при `len(failures) < failed`
  строка «итог pytest: N упавших, разобрано M» (AC-6); «упало» по-прежнему
  из итоговой строки.
- Вердикт — `acceptance._full_suite_outcome` по коду выхода, не тронут (AC-9).

Бюджет SPEC ($40) не пересматривается.

## Шаги
1. `orchestrator/acceptance.py`: последнее совпадение итога, `SUBFAILED` в
   `_FAILED_LINE`, `_SUBFAILED_ENTRY`, `subtest_unit`, `subtest_parents`,
   слияние в `failed_entries`.
2. `orchestrator/suite_run.py`: `_SUBFAILED_PROGRESS`, `_progress_part`,
   `_subtest_progress`, `Parsed.rerun`, подсчёт в `parse`, строка сверки в
   `render`, `failed.json` из `rerun`.
3. Тест `tests/test_suite_run.py::RenderTest::test_summary_mismatch_line_only_when_parsed_fewer`
   (строка сверки не печатается при полном разборе — свойство, не покрытое
   долгоживущим файлом); мутация `<` → `<=` проверена — тест красный.
4. `python3 scripts/codebase_map.py` — карта регенерирована.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1, 2 |
| 3 | 1, 2 (прежние `_FAILED_ENTRY`/`_PROGRESS` не тронуты) |
| 4 | 1, 2 |
| 5 | 2 |
| 6 | 2 |
| 7 | 2 (вердикт не тронут) |
| 8 | долгоживущий `tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`, шаг 3 |
| 9 | раздел «Меняемое поведение» SPEC; потребители не правятся |

Проверка: `python3 -m pytest tests/test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py tests/test_suite_run.py` — 30 passed (включая настоящий прогон под `-n 2 -p xdist`); тесты затронутых модулей (`test_acceptance`, `test_full_suite_reuse`, `test_amend*`, `test_*suite_run*`, `test_*plank_run*`, `test_suite_lock` и др., 17 файлов) — 204 passed, 113 subtests passed.
Полный набор (`artel.py suite-run`) дважды отказан: замок машины держит
прогон задачи 01M4PMPMZ7PPCN3JWX75RTJZQN — его выполнят CI и гейт приёмки.

## Влияние на систему
- Потребители `run_summary_line` (метрика «прогон: время», `plank-run`,
  `amend-tests`, `run_digest`, `save_suite_result`,
  `_remember_gate_failures`) получают последнюю итоговую строку; на выводе с
  одной итоговой строкой результат прежний.
- `amend.py:551` видит строки `SUBFAILED` — маркер требуется от файла
  упавшего подтеста, как у обычного упавшего (записано в SPEC).
- Перечни упавших только расширяются; вердикт гейтов и `suite-run` по коду
  выхода не тронут; ни один существующий тест не правился (добавлен один).
- `failed.json` несёт nodeid (для теста без подтестов — как прежде).
- Откат — revert коммита ветки.

## Риски
- nodeid с пробелом в id параметризации у теста с подтестами: правило SPEC
  «слово с `::`» берёт часть id — такой подтест разберётся неточно (повтор
  `--failed` получит обрезанный id). Обычные FAILED/ERROR с пробелом
  разбираются целиком (AC-10).
- Метка без скобок вида `SUBFAILED tests/…` (пустая) — единица равна nodeid
  родителя.

## Предложения системе
- Песочница шага разработчика отказывает в `mkdir`/`cat`/`ls` и в
  `pytest` во временном каталоге — замер формата вывода pytest пришлось
  отдать настоящему прогону долгоживущего теста; заодно `-n`/`-p xdist`
  на тестах модулей роняет воркеров («node down: Not properly
  terminated») — шаг гоняет тесты модулей только последовательно и
  упирается в 10 минут инструмента.
