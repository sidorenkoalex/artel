---
task: 01M4C954HBJWEGD3AZS7Q3EHA4
type: review
author_role: reviewer
status: approved
iteration: 4
schema_version: 5
---

# REVIEW: Дозор: позиции, просмотр, подтверждение, уведомление

## Соответствие SPEC

Фаза A (гейт плана): таблица покрытия охватывает требования 1–15, оба
прошлых возврата и новый возврат с приёмки (шаг 7, Д-1…Д-4, Д-6, текст
~486). Шаг 7 проверяем: каждое изменение закреплено тестом в отдельном
`tests/test_observation_acceptance_return.py`, а долгоживущие файлы задачи
не тронуты (хеши в пакете совпадают с итерацией 3). «Влияние на систему»
соответствует diff: затронуты `watch.py`, `store.py` (новые читающие
функции и необязательная верхняя граница `alerts_since` — прежние вызовы без
`max_id` работают как раньше), `doctor/observations.py` и документация.
Данные задач и lease не меняются.

Фаза B: ревью инкрементального diff `e953692c...HEAD`. Собственный код
итерации 4 — коммит 5dc7ca65. Коммиты 6a424b27 и e6b2f5b0 проверены в
итерации 3.
- Д-1: `_observation_events` снимает `journal_maxima` до чтения и читает
  `steps`/`alerts` в полуинтервале (старт, максимум]. Строка, закоммиченная
  после снятия максимума, получает id больше него: SQLite допускает только
  одного писателя. Значит, она не теряется и придёт следующим чтением.
  Позиция следует за журналом и при молчащем наборе, поэтому `observe add`
  не выводит заново историю добавленной задачи. `POSITION=` в `observe
  events` идёт за тем же максимумом и не превышает текущих максимумов,
  поэтому `acknowledge` эту пару примет.
- Д-2: `STATE=<state>` печатается в том же формате, что в прежнем цикле
  (`watch.py:775`), и при первом появлении задачи не печатается. Ход живого
  шага находит один агрегирующий запрос `store.observation_live_steps` на
  весь набор, а не запросы по задачам. Строки класса `pytest` и хода шага
  ограничены общим `_LineBudget`. Тело `_emit_progress` вынесено в
  `_emit_live_step_progress` без изменения логики, поэтому прежний `watch`
  не затронут (подтверждают зелёные `test_watch.py` и
  `test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`).
- Д-3: `osascript` вызывается с `timeout=10`, `TimeoutExpired` перехвачен и
  выводится одной строкой.
- Д-4: свой PID признаётся только при совпадении и PID, и хоста; запись с
  тем же PID на чужом хосте получает отказ с указанием `--takeover`.
- Д-6: `doctor` выдаёт `warn` при состояниях `dead`/`stale` и `ok` при
  `alive`/`fresh`.
- Документация: время отметки связи и раздел о ходе шага соответствуют
  коду.

У каждого нового теста есть заявка «Ловит мутацию» с наблюдаемым
расхождением. Две заявки я проверил временной мутацией (см. «Проверено
исполнением»). Утверждения существующих тестов не изменены. Для трёх
методов `test_watch.py::EmitStepsFiltersInSqlTest` раздел «Изменённые
утверждения» сообщает «утверждения не изменены».

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Схема и миграция в итерации не менялись. |
| 2 | OK | Одно упорядоченное чтение `steps` по набору до снятого максимума журнала; позиция продвигается и при молчащем наборе. |
| 3 | OK | `acknowledge` использует общий `journal_maxima`; граница и монотонность сохранены. |
| 4 | OK | Ролевой доступ и признак уведомлений не затронуты. |
| 5 | OK | Уведомление ограничено таймаутом; сбой и зависание не останавливают дозор. |
| 6 | OK | Свой PID сверяется вместе с хостом; `doctor` предупреждает о дозоре без процесса. |
| 7 | OK | Без изменений с итерации 3. |
| 8 | OK | Без изменений. |
| 9 | OK | Текст об отметке связи и ходе шага в `--observation` обновлён и соответствует коду. |
| 10 | OK | Тот же PID на чужом хосте теперь даёт отказ, а не перехват. |
| 11 | OK | Цикл по-прежнему завершают только `observe stop`/перехват. |
| 12 | OK | Отсеянные строки по-прежнему продвигают позицию; теперь продвигают и строки вне набора. |
| 13 | OK | `POSITION=` — пара максимумов просмотренного журнала, включая отсеянное. |
| 14 | OK | Без изменений. |
| 15 | OK | Без изменений. |

## Замечания

Нет.

## Реестр замечаний

Незакрытых замечаний нет. R1-F1 принят в итерации 2; новых записей в
итерации 4 нет.

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py:239-244 | Тестовый помощник временно очищает признак роли только для публичного `observe stop`. | Помощник останавливает дозор в среде роли, не снимая запрета команды для настоящей роли. | Принято в итерации 2; файл в итерации 4 прошёл адресный прогон. |

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tests/test_observation_acceptance_return.py tests/test_observation_notification.py tests/test_01m4c954hbjwegd3azs7q3eha4_doctor.py tests/test_01m4c954hbjwegd3azs7q3eha4_documentation.py tests/test_01m4c954hbjwegd3azs7q3eha4_observation.py tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py tests/test_watch.py tests/test_observation_edges.py tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py tests/test_doctor.py tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py -q -p no:cacheprovider -p timeout -o timeout=120` — 187 passed, 78 subtests passed.
- Временная мутация 1: `watch.py` `next_step = steps[-1]["id"] if steps else start_step` (позиция по последней строке набора) — покраснели `test_added_task_history_is_not_replayed_after_quiet_polls` и `test_events_position_reaches_journal_maximum_for_quiet_set`.
- Временная мутация 2: `doctor/observations.py` — условие `warn` заменено на `False` — покраснели подтесты `dead` и `stale` в `test_doctor_warns_for_dead_pid_and_stale_link`.
- После мутаций: `git checkout -- orchestrator/watch.py orchestrator/doctor/observations.py`, `git status --short` пуст.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4C954HBJWEGD3AZS7Q3EHA4` — 1 passed, код выхода pytest 0.

## Предложения системе

- Долгоживущий `test_ac2_steps_across_tasks_are_ordered_and_read_together` считает чтения `steps`, исключая запросы с `max(`. Поэтому агрегирующий запрос `observation_live_steps` проходит фильтр по признаку текста запроса, а не по смыслу «чтение потока событий». Счётчик чтений по тексту SQL хрупок: такие сторожа лучше формулировать через число вызовов функции чтения потока.
