---
task: 01M1RGQV4DG2FX1B90W4EEETTR
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 4
---

# REVIEW: Наблюдатель роста карты, часть 2: блок report и оценка в деньгах

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (оценка «стоимость карты за шаг developer») | OK | `map_growth_cost_estimate`/`_map_growth_calls_estimate` (orchestrator/report.py) — `tokens` от `bytes_projection`/`bytes_total` последней записи (`"bytes_projection" in latest`), `calls` — медиана суммарного числа вызовов инструментов по логам `developer` последних 10 задач глобально (`store.all_tasks(conn)[-MAP_GROWTH_CALLS_TASK_WINDOW:]`, порядок по возрастанию id — подтверждено чтением `store.all_tasks`), фолбэк `config.MAP_GROWTH_CALLS_ESTIMATE`, `cost_usd` по формуле AC-4. AC-1..AC-4 — зелёные (`acceptance_tests/test_map_growth_cost_estimate.py`, 10/10). |
| 2 (не влияет на алерты/FSM) | OK | Ни одного вызова `alerts.*` в новом коде `report.py` (грep + AC-5 тест с подменой модуля `alerts`); `fsm.py`/`fsm_advance.py`/`fsm_autogate.py` не импортируют `report` — перепроверено `grep -n "import report"` по всем трём файлам, совпадений нет. |
| 3 (блок в `artel report`) | OK | `_map_growth_html`/`_map_growth_target_html` — таблица последних 12 записей, медиана калибровки, открытые алерты `map.growth`, денежная оценка по каждому target из `store.all_tasks`; встроено в `_render`/`cmd_report` последней панелью, не влияет на прежние (diff `_render` только добавляет параметр и секцию). |
| 4 (target без данных — «измерений нет») | OK | `_map_growth_target_html` коротко замыкается на пустом `rows` до обращения к `config.MAP_GROWTH_CALIBRATION_MERGES` — подтверждено: `grep MAP_GROWTH_CALIBRATION_MERGES orchestrator/config.py` пусто (часть 1 ещё не смержена) и тест `test_target_without_a_single_record_shows_fixed_message` зелёный именно на этом дереве. |
| 5 (тесты) | OK | Итерация 1 отметила отсутствие докстрингов «Ловит мутацию» у 7 новых методов `tests/test_report.py` (R1-F1) — в этой итерации все 7 несут содержательный докстринг с конкретной мутацией и наблюдаемым ассертом (проверено построчно, см. «Реестр замечаний»). Существующие тесты `tests/test_report.py` не тронуты (diff — чистое добавление после строки 467), 50/50 зелёных. `acceptance_tests/` — 21/21, константы читаются через `config`/`mock.patch(..., create=True)`, не литералами. |

## Замечания

Пусто — единственное замечание прошлой итерации (R1-F1) закрыто, новых
блокеров/major не найдено.

Отдельно, вне реестра (не требует действия разработчика, не блокирует
approve): `orchestrator/report.py::_map_growth_calls_estimate` перепроверяет
`config.LOGS.exists()` на каждой из до 10 итераций цикла, хотя результат от
`row` не зависит — чисто вкусовое упрощение (вынести проверку перед циклом),
не влияет на корректность (`test_missing_logs_dir_falls_back_to_named_constant`
зелёный).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_report.py (7 методов, см. iteration 1) | 7 новых тестовых методов без докстринга «Ловит мутацию: …» | нарушение конвенции test-authoring.md | Проверено построчно в этой итерации: все 7 методов (`test_counts_tool_use_blocks_across_lines`, `test_ignores_non_json_and_non_assistant_lines`, `test_missing_logs_dir_falls_back_to_named_constant`, `test_unparsable_detail_json_is_skipped_not_raised`, `test_ignores_entries_of_other_actions`, `test_no_tasks_at_all_reports_empty`, `test_target_without_a_single_record_shows_fixed_message`) несут докстринг «Ловит мутацию: <конкретная порча> → <какой ассерт падает>», сценарий и наблюдаемое свойство описаны, не пересказ имени метода. Прогон `tests.test_report` — 50/50 зелёных. Закрыто. |

## Вердикт

approved

## Проверено исполнением

- Инкрементальный diff пакета (от sha `9bdee5b4…` до HEAD ветки) оказался бесполезен для ревью: `9bdee5b4` — это сам коммит-фикс R1-F1 этой задачи, а три коммита после него — «подтяжка main» (мерж стороннего hotfix'а зон, задача 01M1RR1PZC926T13NB1JSZ7F8T). Пакет показал diff зоны `orchestrator/zone_lock.py`/`docs/retro/`/`tasks/01M1RR1PZC…` — файлы ЧУЖОЙ задачи, не имеющие отношения к SPEC этой задачи. Собрал реальный diff вручную: `git diff main...task/01m1rgqv4dg2fx1b90w4eeettr-nablyudatel-rosta-karty-chast --stat` — подтвердил, что фактически изменены только `docs/codebase-map.md`, `orchestrator/config.py`, `orchestrator/report.py`, `tests/test_report.py` (420 строк), зона не нарушена.
- SPEC.md/PLAN.md этой задачи не были показаны пакетом («не показан» и в ветке, и в дереве) — прочитал их напрямую из рабочего каталога (`tasks/01M1RGQV4DG2FX1B90W4EEETTR/SPEC.md`, `PLAN.md`, `REVIEW.md`), они там присутствуют (материализованы из артефактной ветки).
- `python3 -m unittest tests.test_report -v` — 50 тестов, все зелёные (включая 7 методов R1-F1 с докстрингами «Ловит мутацию»).
- `python3 -m unittest discover -s tasks/01M1RGQV4DG2FX1B90W4EEETTR/acceptance_tests -p "test_*.py" -v` — 21 приёмочный тест (AC-1..AC-12), все зелёные.
- `git diff main...task/01m1rgqv4dg2fx1b90w4eeettr-nablyudatel-rosta-karty-chast -- docs/codebase-map.md` — расхождение только в `built_at_sha` и в списке публичных функций `report.py` (корректно добавились 4 новые), регенерация верна.
- `git diff main...task/01m1rgqv4dg2fx1b90w4eeettr-nablyudatel-rosta-karty-chast -- tasks/01M1RGQV4DG2FX1B90W4EEETTR/ --stat` — пусто: артефакты задачи в кодовую ветку не закоммичены (конвенция соблюдена).
- `grep -n "import report" orchestrator/fsm.py orchestrator/fsm_advance.py orchestrator/fsm_autogate.py` — совпадений нет (AC-5).
- `grep -n "MAP_GROWTH_CALIBRATION_MERGES" orchestrator/config.py` — константа части 1 отсутствует, короткое замыкание AC-10 подтверждено кодом и тестом.
- `grep -n "def all_tasks" -A2 orchestrator/store.py` и `grep -n "prefix = " orchestrator/agent_log.py` — подтверждена сортировка по возрастанию id (последние 10 = `[-10:]`) и формат имени лог-файла `{task_id}-{role}-{n}.log`, совпадающий с `config.LOGS.glob(f"{row['id']}-developer-*.log")`.
- Построчное чтение diff `orchestrator/report.py`/`orchestrator/config.py`/`tests/test_report.py` целиком; сверка `_map_growth_tool_call_count` с `agent_log._parse_stream_event`/`_tool_use_calls` (orchestrator/agent_log.py:203-239) — независимая копия эквивалентна (тот же формат `type=="assistant"`, `content` список, `block["type"]=="tool_use"`).

## Предложения системе

- Ревью-пакет строит инкрементальный diff по sha предыдущего вердикта до HEAD — в этой задаче sha (`9bdee5b4`) указывал на коммит-фикс самого developer'а, а между ним и HEAD легли три «подтяжки main», принёсшие merge стороннего hotfix'а (01M1RR1PZC926T13NB1JSZ7F8T). Пакет показал diff и SPEC/PLAN «не показаны» — пришлось полностью восстанавливать контекст ревью вручную (`git diff main...branch`, чтение SPEC/PLAN из рабочего каталога). Тот же класс, что уже в бэклоге («Гейт зон сверяет дифф с локальным main (пином)»/«Инкрементальный diff пакета» в skills/review-checklist.md) — но здесь пострадала генерация самого ревью-пакета, не только гейт зон; стоит явно включить генератор пакета в область фикса той регрессии.
