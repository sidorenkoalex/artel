---
task: 01M4FZ6QYPPKYQZFEX14QH8XT6
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Запуск без привязки к чату

## Подход
Наблюдение для отсоединённого `run`/`auto` выбирается сессией пульта,
проектом и задачей либо явно флагом `--observation <ID>`; пара
`--client`/`--chat` становится необязательными метаданными аудита.

- `orchestrator/store.py::matching_observation(conn, task_id, target,
  session_id)` — без пары: самое свежее (`last_seen_at DESC`) активное
  наблюдение сессии и проекта с включённой задачей, при равенстве —
  созданное позже (`created_at DESC, rowid DESC`). Имя функции
  сохраняется: его подменяет `test_ac6_detached_launch_spawns_attach_child`.
  `session_observations` получает тот же тай-брейк, чтобы подсказка и
  запуск выбирали одно наблюдение.
- `store.journal` — необязательный keyword `target`: запись о запуске
  пишется с уже известным проектом задачи, без повторного чтения
  `tasks` (в `test_ac6_detached_launch_spawns_attach_child` соединение
  БД — мок, чтение строки из него невозможно).
- `orchestrator/artel.py`:
  - `_cycle_args` разбирает `--observation <ID>` (значение обязательно)
    и пару; пара необязательна, но если передан хотя бы один из флагов —
    оба обязательны, клиент `codex|claude`, чат непустой (иначе отказ,
    как прежде). Возвращает `(task_id, attach, client, chat,
    observation_id)`.
  - `_launch_detached(cmd, task_id, client=None, chat=None, extra=(),
    observation_id=None)` — позиционная форма прежних вызовов
    (`tests/test_detached_cycle.py`) остаётся рабочей. Порядок проверок до
    `Popen`: форма пары → выбор наблюдения (названное: найдено / та же
    сессия и проект / активно / задача в наборе; иначе
    `matching_observation`) → связь есть → связь не старше
    `config.OBSERVATION_STALE_SECONDS` → `lease.is_live`. Тексты отказов
    называют ID наблюдения, состояние связи и `artel.py watch
    --observation <ID>` либо `observe register`/`observe add`; ни один не
    предлагает пару. Lease и `tasks.state` до `Popen` не трогаются (как
    прежде). После `Popen` и `record_observed_run` — запись журнала шагов
    задачи «отвязанный запуск» с pid, наблюдением и, если передана, парой
    `client=…, chat=…` (действие не попадает ни в один класс событий
    `watch._matches_class`).
  - `observe register` — `--client`/`--chat` необязательны, пустая строка
    при отсутствии; неполная/кривая пара — отказ, как прежде.
  - Строки usage/докстринг модуля — без обязательной пары.
- `orchestrator/cycle_hint.py`: `cycle_command(cmd, task_id,
  observation_id=None)` — `artel.py <cmd> <id> [--observation <ID>]`;
  `launch_hint` строит строку запуска через `cycle_command`; шаг
  регистрации — `observe register --tasks <id>` без пары.
- `orchestrator/doctor/stale_cycles.py::_observation_args` возвращает
  `(observation_id,)` наблюдения этого запуска или `()`.
- Документация: `docs/operator-session.md` раздел «Фоновые запуски под
  наблюдением» (порядок без пары, таблица отказов под требование 5,
  ссылки по заголовкам), `docs/stack.md` — фраза о контракте запуска.
- Существующие тесты — только методы из раздела SPEC «Меняемое
  поведение», значения «было → стало» той же строки.

Оценка SPEC ($35) не расходится с планом — `budget_usd` не поднимается.

## Шаги
1. `store.py`: `matching_observation` без пары с тай-брейком по
   `created_at`; тот же тай-брейк в `session_observations`; `journal(...,
   target=None)`.
2. `artel.py`: разбор `--observation` и необязательной пары в
   `_cycle_args`; выбор/отказы/журнал в `_launch_detached`; `observe
   register` без пары; usage и докстринг.
3. `cycle_hint.py` + `doctor/stale_cycles.py`: форма `--observation <ID>`.
4. Тесты: методы «Меняемого поведения» в `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`,
   `tests/test_observation_edges.py`, `tests/test_cycle_hint.py`,
   `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`,
   `tests/test_pin_update_stale_cycles.py`,
   `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`; новые юнит-тесты
   отказов (тексты требования 5 для названного наблюдения: не найдено, не
   активно, задачи нет в наборе, чужая сессия, связи ещё нет; отказ
   «подходящего наблюдения нет»; запись аудита запуска без пары) —
   `tests/test_launch_observation_refusals.py`, сторожа проверены
   временной мутацией (снятая проверка «не активно»; пара в журнале
   безусловно) — оба красные.
5. Документация `docs/operator-session.md`, `docs/stack.md`; регенерация
   `docs/codebase-map.md`; прогон тестов затронутых модулей и планки
   (`plank-run`), `scripts/guard.py`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1, 2 |
| 3 | 2 |
| 4 | 3 |
| 5 | 2 |
| 6 | 2 |
| 7 | 5 |

## Влияние на систему
- Гейт свежести связи не меняется: порог `config.OBSERVATION_STALE_SECONDS`
  тот же и применяется к выбранному (в том числе названному) наблюдению —
  отката на другое свежее нет.
- Изоляция по сессии и проекту сохраняется: неявный выбор — только среди
  наблюдений текущей сессии и проекта; названное наблюдение чужой сессии
  или проекта — отказ.
- Схема (`orchestrator/schema.py`) не трогается: отсутствие пары — пустая
  строка в существующих `NOT NULL` колонках; старые наблюдения с парой
  читаются и выбираются как прежде.
- `watch.py` не меняется; новая запись журнала «отвязанный запуск» не
  попадает в классы событий дозора (`transitions`/`refusals`/`steps`/…),
  уведомлений не порождает.
- Проверки существующих тестов не ослабляются: меняются только значения,
  перечисленные в SPEC «Меняемое поведение»; где раньше проверялась пара,
  теперь проверяется ID наблюдения.
- Откат — revert merge-коммита задачи; данных в новом формате нет (пустые
  строки в `client`/`chat` прежний код читает, но для запуска без пары не
  выберет — это и есть прежнее поведение).

## Риски
- Сортировка `last_seen_at` строкой ISO: `isoformat()` без микросекунд
  при нулевой дробной части — порядок всё равно верный (`+` < `.`).
- Позиционные вызовы `_launch_detached(cmd, id, client, chat)` в тестах
  сохраняют сигнатуру.

## Проверка
- Долгоживущие тесты задачи и тесты затронутых модулей (15 файлов) —
  зелёные; планка `plank-run` — 1 passed.
- `suite-run` №1: новых падений на ветке 0; одно падение есть и на базе
  c7a16091 — `tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`
  (повтор №2 — то же; модуль `liveness` задачей не затронут).

## Предложения системе
- `suite-run --wait` полного прогона печатает сводку «прошло: 1, упало: 0»
  при тысячах выполненных тестов и одном падении на базе — счётчики
  сводки, похоже, считаются не по тому прогону (`orchestrator/suite_run.py::render`).
