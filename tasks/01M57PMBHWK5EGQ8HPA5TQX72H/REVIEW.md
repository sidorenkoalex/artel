---
task: 01M57PMBHWK5EGQ8HPA5TQX72H
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Несколько проектов: проект в report и алерты пульта в наблюдении внешнего проекта

## Фаза A — план
- Таблица покрытия PLAN полна: требования 1–9 привязаны к шагу 1, к долгоживущим тестам или к «Предложениям системе». Требование 9 выполнено — строка бэклога о смешении алертов под `DEFAULT_TARGET` в PLAN есть.
- Шаг один, но размером он с MR (две правки модуля). Деление по SPEC обосновано общим эталоном AC-8.
- Подход не конфликтует с архитектурой. ANSWER-2 учтён: NULL-задача приравнена к артели, имена проектов берутся из `targets.yaml`, неизвестное значение печатается в скобках, сигнатуры `_gate_ratio`/`_metrics_html` сохранены, сверка `status` записана в PLAN.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `report.py` `_project`/`_project_suffix`/`_project_label`: метка стоит за id в `_gate_queue_html`, `_closed_tasks_html`, `_tokens_by_task` (здесь метка без экранирования, потому что `_token_cost_row_html` экранирует адрес сам), `_friction_html` и `_test_author_row_html`. На плитке разметка `' [<span class="tile-project">…</span>]'`, `tile-id` прежний. NULL-задача показывается как артель. |
| 2 | OK | `_alert_label`: у NULL и артели метки нет. У id задачи, не являющегося именем проекта, метки нет. Остальные значения выводятся `[<target>]` (ANSWER-2 п.2). Доставку алерта задачи дозором держит `test_ac2_task_alert_delivered_to_observation_of_task`. |
| 3 | OK | `_metrics_html` разбивает блоки, только если `len({_project(row)}) > 1`. `_split_metrics_html` берёт задачи проекта и записи журнала только этих задач, окно `_gate_ratio` считается по записям проекта. Суммы равны `store.total_spent` (`SUM(tasks.spent_usd)`, `store.py:681-684`), так что разбивка совместима с общим итогом. |
| 4 | OK | `watch.py:308`: в набор допустимых `target` добавлен `None`. «Оповещено» — это `next_alert` строки наблюдения, т.е. позиция у каждого наблюдения своя. |
| 5 | OK | `item["target"] or "-"`. |
| 6 | OK | `observe events` использует тот же `_observation_events`; `artel.py` не тронут. |
| 7 | OK | Планка AC-8 зелёная (эталон снят до правки). Обычный `watch` без наблюдения не тронут. |
| 8 | OK | Долгоживущие тесты test_author и `tests/test_report_project_label.py` детерминированы, без сети, используют одну БД песочницы. |
| 9 | OK | Строка в «Предложениях системе» PLAN есть. |

Тесты. Долгоживущие `tests/test_01m57pmbhwk5egq8hpa5tqx72h_{report,watch}.py` помечены «Группа: долгоживущий» и проверяют свойства кода, а не факты задачи. Тест разработчика `tests/test_report_project_label.py` не повторяет их: он покрывает NULL-задачу в очереди гейтов и в закрытых задачах (ANSWER-2 п.1), а также неизвестное значение и значение из `targets.yaml` у алерта. Существующие тесты в `tests/` не изменены и не удалены: в диффе `tests/` только новый файл.

Наблюдение без влияния на вердикт. По `report.py::_alert_label` набор `projects` (то есть `_declared_projects()`) меняет вывод только тогда, когда `target` совпадает и с именем проекта, и с id задачи. Проект из `targets.yaml` без задач в выборке и так получает скобки по ветке «неизвестное значение». Поэтому часть заявки `test_alert_label_from_declared_projects_and_raw_value` про «проект `targets.yaml` без задач теряет скобки» тест не отличает: временная мутация `_declared_projects -> set()` оставила все тесты зелёными. Вторую половину заявки (метка только проектам — неизвестное значение теряет скобки) утверждение `m-odd` ловит, так что тест не пустой. Поведение совпадает с ANSWER-2 п.2, дефекта вывода нет.

## Замечания

Блокирующих и major-замечаний нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 …/artel.py plank-run 01M57PMBHWK5EGQ8HPA5TQX72H`: `test_ac8_artel_only_unchanged.py` — 1 passed, код выхода 0.
- `python3 -m pytest -q tests/test_01m57pmbhwk5egq8hpa5tqx72h_report.py tests/test_01m57pmbhwk5egq8hpa5tqx72h_watch.py tests/test_report_project_label.py tests/test_report.py tests/test_01m563e1sh9sb63s2mw4a9b82n_project_label.py tests/test_01m563e1sh9sb63s2mw4a9b82n_observation.py`: 94 passed, 90 subtests passed.
- Временная мутация `report._declared_projects` → `return set()`. Прогон `tests/test_report_project_label.py` и `tests/test_01m57pmbhwk5egq8hpa5tqx72h_report.py` дал 8 passed (мутацию никто не поймал, см. наблюдение выше). Код восстановлен через `git checkout`, дерево чистое.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`: без `built_at_sha` расхождений нет, карта свежая. Файл восстановлен.

## Предложения системе
- Рабочий набор ревьювера: запись в `/tmp` требует подтверждения, поэтому временную мутацию для проверки сторожа удобнее откатывать через `git checkout -- <файл>`. Стоит назвать этот приём в `skills/review-checklist.md`, в разделе «Сторож — проверен временной мутацией».
