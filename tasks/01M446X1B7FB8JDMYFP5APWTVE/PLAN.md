---
task: 01M446X1B7FB8JDMYFP5APWTVE
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Дозор показывает ход шага роли

## Подход
- **Запись строки pytest (треб. 1).** Оба провайдера уже отдают результат
  инструмента общим полем `StreamEvent.tool_results` (Claude —
  `_user_event`, Codex — `_tool_result_event`), поэтому распознавание стоит
  одно, в `OutputPump.catch_event` (`orchestrator/agent_log.py`), а не в
  каждом провайдере. `agent_log.pytest_summaries(text)` ищет строки вида
  «<N> <исход>[, <N> <исход>…] in X.XXs», снимает рамку «=» и ANSI; одна
  итоговая строка = один прогон. Получатель — колбэк
  `on_pytest_summary`, который `runner._spawn_and_wait` задаёт записью
  `store.journal(store.db(), task_id, role, "прогон pytest", строка)`:
  своё соединение, потому что насос — отдельный поток, а sqlite не
  отдаёт соединение `conn` другому потоку. Сбой записи перехвачен в
  насосе — перекачка пайпа не прерывается. Лог шага не меняется
  (результаты инструментов в него не шли и не идут).
- **Класс `pytest` (треб. 2).** `_EVENT_CLASSES` и `_DEFAULT_EVENTS`
  дополнены, `_matches_class` сверяет действие точным равенством с
  `agent_log.PYTEST_RUN_ACTION`.
- **Ход шага (треб. 3-7)** — в `orchestrator/watch.py`: на каждой итерации
  по задаче после `_emit_steps` зовётся `_emit_progress`. Живой шаг —
  `store.last_task_step_of` (новая функция: последняя запись задачи из
  набора действий, одна запись SQL-ом) по «agent run started» и по
  записям завершения. Состояние шага (`_LiveStep`: выданная отметка k,
  выданные виды предупреждений) заводится заново при новой «agent run
  started». Отметка k = ⌊прошло / N⌋; печатается, если k ≥ 1 и больше
  выданной — пропущенные k задним числом не печатаются. Сводка: «M/45
  мин» (`AGENT_TIMEOUT_SEC // 60`), `git status --porcelain
  --untracked-files=all` рабочей копии задачи, три последних строки
  «· <Tool> …» из хвоста (64 КиБ) лога шага, каждая ≤ 40 символов,
  строка целиком ≤ 240. «Нет коммитов»: `git log -1 --since=@<начало>
  <ветка>` в клоне задачи; git не ответил — не предупреждаем. «Стоимость
  шага»: `spend.partial_tokens_from_log` + `spend.partial_cost_usd(role,
  tokens, task_row)`, лог перечитывается только когда вырос; `None` —
  предупреждения нет. Граница (`_LineBudget`) — общий счётчик строк
  `pytest`/сводок/предупреждений на задачу, скользящее окно 3600 с по
  `time.monotonic`; невыданное из-за границы считается выданным.
- Константы — `orchestrator/config.py`; описание — раздел «Ход шага роли
  в дозоре» в `docs/operator-session.md`.

## Шаги
1. `agent_log.pytest_summaries`, `PYTEST_RUN_ACTION`, колбэк
   `OutputPump(on_pytest_summary=…)`; подключение в `runner._spawn_and_wait`.
2. Константы `config.WATCH_*`; `store.last_task_step_of`; класс `pytest`,
   `_LineBudget`, `_LiveStep`, `_emit_progress` в `watch.py`.
3. `docs/operator-session.md`; юнит-тесты `tests/test_pytest_summary_pump.py`;
   регенерация `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2 |
| 3 | 2 |
| 4 | 2 |
| 5 | 2 |
| 6 | 2 |
| 7 | 2 |
| 8 | 3 |
| 9 | 3 (долгоживущие файлы задачи + `tests/test_pytest_summary_pump.py`) |

Прогоны (передний план, `-p timeout -o timeout=120`):
- `tests/test_01m446x1b7fb8jdmyfp5apwtve_pytest_journal.py` — 4 passed;
- `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py` — 13 passed;
- `plank-run 01M446X1B7FB8JDMYFP5APWTVE` — 2 passed, код 0;
- `tests/test_pytest_summary_pump.py tests/test_watch.py tests/test_agent_log.py
  tests/test_store_journal.py tests/test_step_cost.py tests/test_agent_failure.py
  tests/test_providers.py tests/test_providers_codex.py` — 252 passed;
- `tests/test_runner_role_model.py tests/test_invariants.py
  tests/test_multitarget_invariants.py` + файлы задачи — 113 passed.
- Мутации своих тестов: снято удаление ANSI — красный
  `test_real_pytest_forms_are_recognised_without_frame`; перехват сбоя
  колбэка сужен — красный `test_summary_callback_failure_keeps_pump_reading`;
  код возвращён.

## Влияние на систему
- Новое действие журнала «прогон pytest» не начинается с «agent run» и
  не входит в `_GATE_ACTIONS`/`state -> `: потребители журнала (`auto.py`,
  `advance_gates/review.py`, `zone_lock.py`, `models.py`, класс `steps`
  дозора) сверяют свои действия точным равенством/префиксом и его не
  видят. Состояний FSM и гейтов не добавлено.
- `OutputPump` получил необязательный параметр; прежние вызовы (тесты
  `test_agent_log.py`) без него ведут себя как раньше. Запись из потока
  насоса идёт своим соединением `store.db()` (WAL) и перехвачена — учёт
  стоимости, трение и лог шага не затронуты.
- `_emit_steps` получил необязательный `budget`; без него (существующие
  тесты `test_watch.py`) поведение прежнее. Формат существующих строк
  `watch` не менялся; строки хода печатаются `_print_line`.
- Существующие тесты не правились. Откат — revert merge-коммита.

## Риски
- «Стоимость шага» по usage лога: живой лог шага несёт РЕНДЕР
  (`tee_lines` пишет `event.log_text`), сырых usage-событий в нём нет —
  `partial_tokens_from_log` на живом логе почти всегда даёт «usage не
  видели», и предупреждение молчит. Реализовано буквально по SPEC
  (требование 5 называет именно эти функции); см. «Предложения системе».
- Распознавание итоговой строки по тексту: `cat` старого лога pytest в
  шаге тоже даст запись «прогон pytest». Граница строк дозора держит
  поток; журнал от этого растёт на одну запись на строку.

## Предложения системе
- `orchestrator/agent_log.py::tee_lines` пишет в лог шага только рендер,
  поэтому `spend.partial_tokens_from_log` на живом логе usage не находит —
  это касается и предупреждения «стоимость шага» дозора, и `pause --now`
  (SPEC T074). Стоимость по ходу шага надёжнее писать насосом в журнал/
  побочный файл (как трение), задача на отдельный ТЗ.
- Насос `OutputPump` пишет в журнал из своего потока — первый такой
  писатель; если писателей из потока станет больше, общий помощник «запись
  журнала из потока» уберёт повтор `store.journal(store.db(), …)`.
