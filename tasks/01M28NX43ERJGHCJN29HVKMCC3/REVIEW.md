---
task: 01M28NX43ERJGHCJN29HVKMCC3
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: guard называет маркер AC-n с отступом, а не глотает его

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (детекция маркера с отступом, именованная ошибка «<файл>:<строка>: … с отступом …», отказ гейта) | OK | `INDENTED_AC_MARKER` (scripts/guard.py:198-199), `indented_ac_marker_errors_from_files`/`scan_indented_ac_markers` (scripts/guard.py:750-799), подключены в `acceptance_traceability_errors` (гейт `tests_writing -> in_dev`) и в `main()` для `--all`/`--all --artifact-branch` (scripts/guard.py:1730-1738). Текст ошибки совпадает с шаблоном SPEC дословно. Проверено прогоном `guard.py --all` на реальном дереве (пусто) и юнит/приёмочными тестами. |
| 2 (текст маркера внутри строкового литерала/докстринга — не нарушение) | OK | `_string_literal_lines` через `ast.parse`/`ast.Constant` (scripts/guard.py:730-748) исключает диапазон строк любого строкового литерала, включая многострочный докстринг; при `SyntaxError` — пустое множество, работает запасная эвристика (проверено `test_syntax_error_falls_back_to_the_plain_heuristic`). |
| 3 (тесты AC-3а/б/в/г) | Реализовано, но с замечанием | Поведенческое покрытие есть и подтверждено прогоном (см. «Проверено исполнением»), но докстринги большинства новых unit-тестов не несут обязательной заявки «Ловит мутацию: …» — см. R1-F1. |

## Замечания

- major — tests/test_acceptance_tests_flow.py:471, 485, 495, 509, 520, 523 (класс `IndentedAcMarkerTest`) — пять из шести методов (`test_indented_marker_still_leaves_the_criterion_untraced`, `test_marker_at_line_start_is_unaffected`, `test_docstring_mention_is_not_flagged`, `test_syntax_error_falls_back_to_the_plain_heuristic`, `test_non_test_file_is_not_scanned`) несут докстринг без обязательной заявки «Ловит мутацию: …» (skills/test-authoring.md, review-checklist Фаза B п.3: «докстринг обязан описывать сценарий и наблюдаемое свойство … пустой или пересказывающий тоже замечание»); `test_missing_directory_is_empty_not_an_error` (строка 520) вовсе без докстринга. Только `test_indented_marker_is_named_with_line_number` (строка 455) оформлен верно — его заявка («мутация «отступ разрешён» красная — если детекция снята, этот тест не находит ни ошибку про AC-2, ни текст «с отступом»») ровно того формата, который требуется от остальных. Для контраста: оба приёмочных теста этой же задачи (tasks/01M28NX43ERJGHCJN29HVKMCC3/acceptance_tests/test_ac1_indented_marker_blocks.py, test_ac2_docstring_mention_not_flagged.py) заявку несут корректно — образец уже есть в диффе. Предложение: дописать в каждый из шести методов явную заявку «Ловит мутацию: <какая конкретно мутация красит именно этот тест>» (например, для `test_marker_at_line_start_is_unaffected` — «регресс: маркер без отступа ошибочно начинает считаться нарушением»; для `test_missing_directory_is_empty_not_an_error` — «отсутствующий каталог трактуется как ошибка, а не как пустой список»).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_acceptance_tests_flow.py:471,485,495,509,520,523 | 5 из 6 новых unit-тестов класса `IndentedAcMarkerTest` без заявки «Ловит мутацию: …» (одна вовсе без докстринга) | нарушение обязательной конвенции test-authoring.md — ревьювер следующей итерации не может свериться с заявленной мутацией, тест теряет часть ценности как спецификация | дописать заявку «Ловит мутацию: …» в докстринг каждого из шести методов, по образцу `test_indented_marker_is_named_with_line_number` и обоих приёмочных тестов задачи |

## Вердикт
changes_requested — один major (R1-F1, докстринги новых unit-тестов без обязательной заявки «Ловит мутацию: …»). Функциональная реализация (детекция отступа, исключение строковых литералов/докстринга, подключение в гейт и в `--all`) корректна и полностью подтверждена прогонами; блокировать по функциональности нет оснований — правка нужна только в докстрингах тестов.

## Проверено исполнением
- `python3 -m unittest tests.test_acceptance_tests_flow -v` — 76 тестов, все зелёные (включая новый класс `IndentedAcMarkerTest`, 7/7).
- `python3 -m unittest discover -s tasks/01M28NX43ERJGHCJN29HVKMCC3/acceptance_tests -p "test_*.py" -v` — 2 приёмочных теста задачи (AC-1, AC-2), оба зелёные.
- `python3 -m py_compile scripts/guard.py tests/test_acceptance_tests_flow.py` — синтаксически корректны.
- `python3 scripts/guard.py --all` — «GUARD: ок (739 файлов)», 0 ошибок; вручную проверено, что закрытая задача `01M1THKWFXFYNW28HDJGYHQWH6` (несёт `docs/retro/…`) реально содержит исторический индентированный маркер AC-7 (acceptance_tests/test_ac7_invariant_wording.py:65) и корректно НЕ попадает в ошибки благодаря исключению по `RETRO_DIR` — подтверждает, что исключение в `main()` не декоративное, а действительно нужное (без него `--all` покраснел бы на main для любой ветки).
- `python3 scripts/codebase_map.py` — вывод идентичен закоммиченному `docs/codebase-map.md` с точностью до строки `built_at_sha` (регенерация приведена в соответствие, расхождений в содержимом нет); рабочее дерево возвращено в исходное состояние (`git checkout -- docs/codebase-map.md`) после сверки.
- Диф `tests/` сверен вручную построчно: изменение — только добавление нового класса `IndentedAcMarkerTest`, ни один существующий тест/утверждение не тронуты (AC-3г подтверждено и прогоном, и диффом).
- Zones/scope: diff ограничен `scripts/guard.py`, `tests/test_acceptance_tests_flow.py`, `docs/codebase-map.md` — совпадает с `zones: scripts/guard.py, tests/` SPEC (codebase-map — обязательный побочный эффект правки `.py` в scripts/, не превышение зоны).

## Предложения системе
- PLAN этой задачи сам называет два открытых класса для будущих задач (fallback `_tests_writing_ac_state` для «чужого чекаута» не получает детекцию отступа; `orchestrator/amend.py::_cmd_amend_tests*` не вызывает `acceptance_traceability_errors` вовсе) — оба обоснованы границей зоны текущей задачи, дублировать здесь не буду, но отмечаю, что ровно инцидент 11.09 (причина этой задачи) прошёл именно через `amend-tests`, то есть второй пробел стоит недалеко от корня проблемы.
