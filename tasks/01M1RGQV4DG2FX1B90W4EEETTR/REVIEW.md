---
task: 01M1RGQV4DG2FX1B90W4EEETTR
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 4
---

# REVIEW: Наблюдатель роста карты, часть 2: блок report и оценка в деньгах

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (оценка «стоимость карты за шаг developer») | OK | `map_growth_cost_estimate` (orchestrator/report.py) — `tokens` от `bytes_projection`/`bytes_total` ПОСЛЕДНЕЙ записи (проверка `"bytes_projection" in latest`, не `.get(...) or`), `calls` — медиана по логам `developer` последних 10 задач глобально с фолбэком на `config.MAP_GROWTH_CALLS_ESTIMATE`, `cost_usd` по формуле AC-4. Покрыто AC-1..AC-4, все зелёные. |
| 2 (не влияет на алерты/FSM) | OK | Ни одного вызова `alerts.*` в `map_growth_cost_estimate`/соседних функциях; `fsm.py`/`fsm_advance.py`/`fsm_autogate.py` не импортируют `report` (проверено и тестом AC-5, и отдельным grep). |
| 3 (блок в `artel report`) | OK | `_map_growth_html`/`_map_growth_target_html` — таблица последних 12 записей, медиана калибровки, открытые алерты `map.growth`, денежная оценка — по каждому target из `store.all_tasks`. |
| 4 (target без данных — «измерений нет») | OK | `_map_growth_target_html` короткое замыкание на пустом `rows` — не обращается к `config.MAP_GROWTH_CALIBRATION_MERGES` (её ещё нет в `config.py` до мержа части 1 — проверено: `grep MAP_GROWTH_CALIBRATION_MERGES orchestrator/config.py` пусто). |
| 5 (тесты) | Частично | Приёмочные (`acceptance_tests/`) полностью покрывают AC-1..AC-12 фикстурным рядом и константами `config.MAP_*`/`MAP_GROWTH_CALLS_ESTIMATE` через `mock.patch(..., create=True)`, не литералами — соответствует требованию буквально. Существующие `tests/test_report.py` зелёные без правки ассертов (50/50, включая 7 новых). Но 7 из 7 новых тестовых методов в `tests/test_report.py` (не в приёмочных) не несут докстринг с заявкой «Ловит мутацию: …» — см. замечание R1-F1 (major). |

## Замечания

- major — tests/test_report.py:484, tests/test_report.py:492, tests/test_report.py:508, tests/test_report.py:533, tests/test_report.py:545, tests/test_report.py:565, tests/test_report.py:570 — все 7 новых тестовых МЕТОДОВ (`MapGrowthToolCallCountTest.test_counts_tool_use_blocks_across_lines`/`test_ignores_non_json_and_non_assistant_lines`, `MapGrowthCallsEstimateTest.test_missing_logs_dir_falls_back_to_named_constant`, `MapSizeEntriesTest.test_unparsable_detail_json_is_skipped_not_raised`/`test_ignores_entries_of_other_actions`, `MapGrowthHtmlTest.test_no_tasks_at_all_reports_empty`/`test_target_without_a_single_record_shows_fixed_message`) не несут собственного докстринга с заявкой «Ловит мутацию: …» (skills/test-authoring.md, review-checklist п. Фаза B.3) — есть только докстринг класса, описывающий предмет теста в целом, но не сценарий/наблюдаемое свойство и не мутацию, которую ловит именно этот метод. Приёмочные тесты той же задачи (`acceptance_tests/test_map_growth_*.py`) конвенцию соблюдают образцово — расхождение именно в новых `tests/*.py`, тот же класс, что уже отмечался в проекте раньше (docstring-конвенция «проседает» в разработческих unit-тестах при исправной приёмочной планке). Последствие: ревьювер следующей итерации/итератор мутационного тестирования не может свериться с заявленным сценарием — не проверить, действительно ли тест ловит мутацию, или проходит «случайно». Предложение: добавить в каждый из 7 методов докстринг вида «Ловит мутацию: <конкретная порча кода> → <какой ассерт падает>», по образцу уже имеющихся в этом же файле (например, `test_report_sums_the_upper_estimate_across_tasks`, строка 274) и в `acceptance_tests/`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_report.py:484,492,508,533,545,565,570 | 7 новых тестовых методов без докстринга «Ловит мутацию: …» (есть только докстринг класса) | нарушение конвенции test-authoring.md; будущий ревьювер/мутационная проверка не может свериться с заявленным сценарием каждого теста | добавить методу-докстринг с явной заявкой «Ловит мутацию: …», описывающей конкретную порчу кода и то, какой ассерт её ловит — по образцу существующих в том же файле/в acceptance_tests этой же задачи |

## Вердикт

changes_requested — единственное, что нужно исправить: добавить докстринги «Ловит мутацию: …» к 7 новым тестовым методам `tests/test_report.py` (R1-F1, major). Функциональность и покрытие SPEC вопросов не вызывают — блокеров не найдено, само поведение AC-1..AC-12 реализовано и протестировано корректно.

## Проверено исполнением

- `python3 -m unittest tests.test_report -v` — 50 тестов, все зелёные (включая 7 новых юнит-тестов этой задачи: `MapGrowthToolCallCountTest`, `MapGrowthCallsEstimateTest`, `MapSizeEntriesTest`, `MapGrowthHtmlTest`).
- `python3 -m unittest discover -s tasks/01M1RGQV4DG2FX1B90W4EEETTR/acceptance_tests -p "test_*.py" -v` — 21 приёмочный тест (AC-1..AC-12), все зелёные.
- `python3 scripts/codebase_map.py` с последующим `git diff docs/codebase-map.md | grep -v built_at_sha` — расхождение только в строке `built_at_sha` (метка коммита регенерации), содержимое карты идентично закоммиченному в диффе; артефакт регенерации откачен `git checkout -- docs/codebase-map.md`, дерево чистое.
- `grep -n "import report" orchestrator/fsm.py orchestrator/fsm_advance.py orchestrator/fsm_autogate.py` — совпадений нет (AC-5 подтверждено независимо от теста-заявки).
- `grep -n "MAP_GROWTH_CALIBRATION_MERGES" orchestrator/config.py` — константа части 1 в `config.py` сегодня отсутствует; подтверждает, что короткое замыкание в `map_growth_calibration_median`/`_map_growth_target_html` на пустом ряде (AC-10) действительно не даёт `AttributeError` до мержа части 1 (проверено чтением кода + прогоном `NoMeasurementsTest`/`MapGrowthHtmlTest`, оба зелёные).
- Чтение diff `orchestrator/report.py`/`orchestrator/config.py` целиком построчно; сверка именования файлов логов `{task_id}-{role}-{n}.log` с `orchestrator/agent_log.py` (совпадает); сверка формата события `stream-json`/`tool_use` в `_map_growth_tool_call_count` с `agent_log._parse_stream_event`/`_tool_use_calls` (эквивалентно, независимая копия обоснована зоной SPEC).

## Предложения системе

- Докстринг «Ловит мутацию» продолжает проседать именно в разработческих `tests/*.py` при исправных приёмочных — уже отмечалось раньше по другим задачам; возможно, стоит завести guard-проверку (аналог `registry_errors`/`requires_registry` в `scripts/guard.py`) на наличие подстроки «Ловит мутацию» в докстринге каждого нового/изменённого метода `test_*`, а не полагаться на ревьювера каждый раз.
