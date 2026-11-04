---
task: 01M6HVPMYY2Q56JZ64KD28FTWK
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Надзор эпика: перезапуск остановленных задач, места параллельности, завершение, answer при ожидании зоны

## Фаза A: план

- Таблица покрытия полна: требования 1–13 разнесены по шагам 1–4; шаг 4 (тесты) соответствует мандатам ANSWER-1/ANSWER-3, ANSWER-4 учтён в «Подходе» (окно запуска по pid, пересчёт исхода на каждом опросе).
- Шаги — единицы размера MR по файлам зон (`auto.py`, `pause.py`, `answer.py`, тесты); деление обосновано в SPEC («Оценка объёма и деление», монолит).
- «Влияние на систему» сходится с диффом: `lease.py`, `zone_lock.py`, `store.py`, `canary.py`, `epics.py`, `fsm.py` не тронуты (stat-список — 3 файла кода в зонах + 3 файла тестов); откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_child_hold` (`orchestrator/auto.py`): штатная остановка держит до действия из прежнего `_operator_actions` после первой записи остановки (`run.anchor`); `resume` при живом дочернем засчитывается только если якорь — остановка паузой или запись `pause --now` (resume после якоря); пауза — `_HELD` до всего прочего. Живой дочерний уходит в `_RUNNING` раньше `_child_hold` — второй запуск и запись потери для живого невозможны. |
| 2 | OK | `pause._last_cycle_stop_is_stop_command`: первая запись остановки после последнего «auto старт», причина через `partition(": ")[2] == auto._STOP_COMMAND_REASON`; иначе прежний путь без журнала. Правка `pause.py` — только эта ветка. |
| 3 | OK | `cmd_auto`: флаг `entered` в теле `run_locked`, запись `AUTO_LEASE_REFUSED_ACTION` только если тело не звано (`lease.py:367-371` — единственный путь без вызова тела). Имя вне `_operator_actions` и префиксов; `UNSUPPORTED_PROJECT_ACTION` — в `_NAMED_REFUSAL_ACTIONS`. Отказ по глобальному лимиту — `None` (очередь), как раньше. |
| 4 | OK | `_child_runs`: исход по первой записи остановки окна без записей надзора; три вида аварии; именованный отказ приоритетен. Якорь паузы — `_SupervisorMemory.noticed` (на опросе, заметившем выход, `_CRASH_WAIT`). Счёт — `_crash_streak` по журналу (переживает перезапуск надзора); сброс — `_resets_crash_count` (epic retry, answer кроме формы zones-extend, state-> оператора кроме подъёма бюджета — деталь сверена с `budget.py:592`, amend, resume). Предел — одна запись (`EPIC_CRASH_LIMIT_ACTION`, актор надзора) и одна тревога на окно запуска. |
| 5 | OK | Запись `pause --now` в окне → `_RUN_PAUSE_NOW`, не авария; исход пересчитывается на каждом опросе (ANSWER-4 п.2) — проверено юнит-тестом и мутацией. |
| 6 | OK | `_zone_wait_lifted` через `zone_lock.blocking_conflict` (окончательный, вне BLOCKING_STATES, `zone-release`, `awaiting_holds_zones: false`); порядок — `_first_in_zone_queue` по `queue_order`, очередь не держат задачи вне `view.status` (вне эпика/другой эпик) и `view.queue_free` (пауза, stop/пауза в ожидании, предел аварий, именованный отказ); `_CRASH_WAIT` очередь держит. `zone_lock.py` не правлен. |
| 7 | OK | `_takes_place`: место только вне гейтов/эскалации/`verifying` и без открытого ожидания зоны (`zone_lock.wait_minutes`, закрывается и «auto старт»). Перезапуски идут тем же `view.ready[:view.free]`. |
| 8 | OK | Глобальная часть `view.free` прежняя: `MAX_PARALLEL_TASKS - len(running) - len(others)`. |
| 9 | OK | `_supervise`: `idle = not view.status and epic["state"] == "open"` — не завершается, сон `EPIC_IDLE_POLL_SEC = 300`; иначе `EPIC_POLL_SEC`; самозавершение при заблокированных сохранено (`not view.live and not idle`). |
| 10 | OK | Закрытый эпик без неокончательных задач — `_end_supervision` с записью и тревогой, как раньше (текст причины уточнён). |
| 11 | OK | Деталь «auto старт» — «состояние …, лимит N шагов, pid <os.getpid()>» с `session_id` цикла. `answer._cycle_waits_zone`: `in_dev`, живой lease на этом host, pid и сессия совпадают с последним стартом, вход в ожидание открыт и шага роли после него нет; иначе прежний `run_locked`. `verifying` — сразу `False`, поведение прежнее. Подсказка вынесена в `_NEXT_STEP_HINT`, текст прежний. |
| 12 | OK | Надзор не зовёт approve/reject и не пишет `state -> …`; гейт/эскалация/ручная проверка — `_WAITING` до `_child_hold`. |
| 13 | OK | В `tests/test_01m5tbf7jrz6fgrr4k53kpajds_epic_supervisor.py` изменены только ac9, ac18, ac27, ac30[все окончательны] + импорт `auto` и новый помощник `end_records`; `final_epic`/`supervisor_ends_itself`, ac28/ac29 не тронуты. Минимум проверок ANSWER-1 присутствует (ac18: запуски 2 и 3 ≤ 3 опросов, нет четвёртого за `IDLE`, одна запись предела с деталью от надзора, тревога, `epic retry` → четвёртый запуск; ac27/ac30: `exit == "сценарий"`, нет запусков/записи/тревоги, новая задача запущена, `epic stop`/`epic close` завершают). `tests/test_auto_cycle.py` — только ожидаемая деталь «auto старт» целиком с `pid {os.getpid()}` (ANSWER-3), плюс докстринг и `import os`. Ослаблений, skip/xfail, подъёма пределов нет. |

Изменённые утверждения тестов (раздел пакета): три метода — сверены с base по диффу; смены покрыты мандатами ANSWER-1 (ac9, ac27) и ANSWER-3 (`test_start_and_stop_are_journalled_by_the_operator`), значения соответствуют требованиям 9, 11, 13. Сужения данных под неизменными утверждениями (setUp, фикстуры) в диффе нет.

Новый `tests/test_epic_crash_series_units.py`: свойства ANSWER-4 (сопоставление по pid, пересчёт после `pause --now`) и подъём бюджета — вне долгоживущих файлов задачи; `test_third_crash_counted_on_next_poll_once` пересекается с AC-3 долгоживущего файла, но служит положительным контролем к `test_pause_now_record_after_notice_is_not_a_crash` на том же стенде (без него тест `pause --now` мог бы проходить вхолостую) — не повтор ради повтора.

## Замечания

Замечаний blocker/major/minor нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest -q -p no:cacheprovider tests/test_01m6hvpmyy2q56jz64kd28ftwk_answer_wait.py tests/test_01m6hvpmyy2q56jz64kd28ftwk_epic_restart.py tests/test_epic_crash_series_units.py tests/test_01m5tbf7jrz6fgrr4k53kpajds_epic_supervisor.py tests/test_auto_cycle.py tests/test_pause.py tests/test_epic_supervisor_units.py` — 211 passed, 33 subtests passed (44 с).
- Тесты `answer`/`lease`/ожидания зоны и verify_flow (16 файлов: test_01m443bp…operator_instruction, test_01m44enw…, test_01m4kaym…, test_01m4r4jk…, test_01m4r4jq…answer_spec_gate, test_01m4xv9x…lease, test_01m5d02n…, test_01m5fghn…wait_minutes, test_01m5fghn…zone_wait_exit, test_answer, test_answer_gate, test_answer_mandate, test_lease, test_lease_run_task_command, test_canary_synthetic_answer, test_01m6f3dk…verify_flow) — 215 passed, 393 subtests passed.
- `artel.py plank-run 01M6HVPMYY2Q56JZ64KD28FTWK` — отказ «планки нет» (в зафиксированной планке нет test_*.py; планка задачи — долгоживущие файлы `tests/test_01m6hvpm*`, прогнаны выше).
- Временная мутация 1: в `auto._run_begins` сверка pid старта выключена (`if pid is None`) — `test_fast_child_start_before_launch_record_counts_by_pid` красный; код возвращён.
- Временная мутация 2: в `auto._resets_crash_count` любой `state -> …` оператора сбрасывает счёт — `test_budget_return_from_escalated_does_not_reset[бюджет поднят, продолжаем]` красный; код возвращён, `git status` чистый.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — расхождений нет (карта свежая), файл восстановлен.

## Предложения системе

- Сторож Bash отклоняет `xargs` и подстановку `$VAR` для списка файлов pytest — ревьюверу приходится выписывать файлы руками; стоит упомянуть в review-checklist рядом с правилом «прогоняй по файлам».
