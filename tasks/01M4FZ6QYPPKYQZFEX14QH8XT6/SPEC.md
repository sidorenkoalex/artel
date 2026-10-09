---
task: 01M4FZ6QYPPKYQZFEX14QH8XT6
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/artel.py, orchestrator/cycle_hint.py, orchestrator/store.py, orchestrator/doctor/, docs/operator-session.md, docs/stack.md, docs/codebase-map.md, tests/
budget_usd: 35
---

# SPEC: Запуск без привязки к чату

## Контекст
Отсоединённый `run`/`auto` сейчас отказывает без `--client codex|claude
--chat <ID>` (`orchestrator/artel.py::_cycle_args`, `_launch_detached`) и
выбирает наблюдение по паре клиент/чат (`store.matching_observation`);
`observe register` (`_cmd_observe`) тоже требует пару. Пара привязывает
запуск к чату, хотя наблюдение уже однозначно задаётся сессией пульта,
проектом и задачей. ТЗ — суженная замена части 2
01M4C956S0RYFZJVP6HZ17WY9C (ликвидирована 09.10); часть 1
(01M4C954HBJWEGD3AZS7Q3EHA4) уже в main. Задача делает пару
необязательными метаданными аудита, вводит явный выбор наблюдения флагом
`--observation <ID>` и приводит к одной форме подсказки запуска и строку
перезапуска `pin-update`.

## Требования
1. `run <id>` и `auto <id>` без `--attach` и `observe register` работают
   без `--client`/`--chat`. У `run`/`auto` есть необязательный флаг
   `--observation <ID>`:
   - с ним запуск идёт только в названное наблюдение;
   - без него — в самое свежее (по `last_seen_at`) активное наблюдение
     той же сессии пульта и того же проекта, в наборе которого есть
     задача; при равной свежести — в созданное позже.
   Гейт свежести связи (`config.OBSERVATION_STALE_SECONDS`, 90 с) не
   меняется и применяется к выбранному наблюдению: выбранное (в том
   числе названное) наблюдение со связью старше порога — отказ, даже если
   у задачи есть другое свежее наблюдение.
2. Переданная пара `--client`/`--chat` — только метаданные аудита и в
   выборе наблюдения не участвует: пара `observe register` записывается в
   наблюдение (колонки `observations.client`/`observations.chat`), пара
   `run`/`auto` — в журнал шагов задачи записью о запуске. Прежние вызовы
   с парой работают без изменений: вызов, который раньше запускал цикл,
   запускает его в то же наблюдение; вызов с неполной или неверной по
   форме парой (только один из двух флагов, пустое значение, клиент вне
   `codex|claude`) отказывает, как прежде.
3. Схема не пересобирается и миграции нет: отсутствие метаданных
   хранится пустой строкой в существующих колонках `NOT NULL`
   (`observations.client`, `observations.chat`). Наблюдения, созданные до
   задачи (с непустой парой), читаются и выбираются для запуска как
   прежде.
4. Подсказки запуска (`orchestrator/cycle_hint.py::launch_hint`/
   `launch_text`) и строка перезапуска `pin-update`
   (`cycle_hint.cycle_command`, место вызова
   `orchestrator/doctor/stale_cycles.py`) строятся одним `cycle_hint` и
   имеют одну форму: `artel.py <cmd> <id> --observation <ID>` при
   известном наблюдении, `artel.py <cmd> <id>` без него; ни подсказка, ни
   строка перезапуска не печатают `--client`/`--chat`. Подсказка
   по-прежнему ведёт к `observe add <ID> --tasks <id>`, если задачи нет в
   наборе наблюдения (или она в нём выключена), и к `observe register` +
   `watch --observation`, если подходящего наблюдения нет.
5. Отказы `run`/`auto` из-за наблюдения называют наблюдение и состояние
   связи: какое наблюдение (ID) выбрано или названо, что именно не так
   (не найдено / не активно / задачи нет в наборе / связи с watch ещё нет
   / связь устарела на N с) и какой `artel.py watch --observation <ID>`
   (пере)запустить; отказ «подходящего наблюдения нет» ведёт к
   `observe register`/`observe add`. Ни один отказ не требует пары
   `--client`/`--chat` и не предлагает её.
6. Отказавший запуск не меняет `tasks.state` и не берёт lease задачи;
   успешный не меняет `tasks.state` до старта цикла в дочернем процессе.
7. `docs/operator-session.md`, раздел «Фоновые запуски под наблюдением»:
   порядок фоновых запусков описан без пары (наблюдатель, `observe add`,
   `run`/`auto`, затем `observe events` и `acknowledge` из любого чата),
   таблица отказов в подразделе «Отказы при запуске и что делать»
   соответствует требованию 5; ссылки внутри документа на его же места
   — по заголовкам разделов, а не по номерам строк. `docs/stack.md` —
   одна фраза о контракте запуска (наблюдение выбирается сессией,
   проектом и задачей либо флагом `--observation`; пара клиент/чат —
   необязательные метаданные).

## Критерии приёмки

AC-1. `auto <id>` и `run <id>` без `--client`/`--chat` и без `--attach`
при одном активном наблюдении текущей сессии и проекта с задачей в наборе
и связью не старше `config.OBSERVATION_STALE_SECONDS` порождают дочерний
процесс с `--attach` и записывают запуск в `observed_runs` этого
наблюдения.

AC-2. Тот же вызов при связи наблюдения старше
`config.OBSERVATION_STALE_SECONDS` отказывает (`SystemExit`, дочерний
процесс не порождён); текст отказа содержит ID наблюдения и
`watch --observation <этот ID>`.

AC-3. `auto <id> --client <c> --chat <x>` с полной корректной парой
запускает цикл в то же наблюдение, что и вызов без пары, в том числе
когда пара не совпадает с парой ни одного наблюдения; в журнале шагов
задачи после запуска есть запись, содержащая `<c>` и `<x>`. Вызовы с
неполной или неверной по форме парой (только `--client`, только `--chat`,
пустой `--chat`, клиент вне `codex|claude`) отказывают без дочернего
процесса.

AC-4. Два активных свежих наблюдения текущей сессии и проекта с задачей:
без `--observation` запуск записан в `observed_runs` наблюдения с более
поздним `last_seen_at`; при равном `last_seen_at` — созданного позже;
в `observed_runs` другого наблюдения записи нет.

AC-5. С `--observation <ID>` запуск записан только в `observed_runs`
названного наблюдения, даже если другое наблюдение свежее.

AC-6. Названное `--observation <ID>` наблюдение со связью старше
`config.OBSERVATION_STALE_SECONDS` — отказ без дочернего процесса, даже
если у задачи есть другое свежее наблюдение; текст отказа называет этот
ID.

AC-7. `observe register --tasks <id>` без `--client`/`--chat` создаёт
наблюдение (печатает JSON с `id`); в строке `observations` клиент и чат
— пустые строки; `observe show <ID> --json` возвращает его без ошибки с
пустыми `client`/`chat`.

AC-8. Наблюдение, созданное с непустой парой до изменения (строка
`observations` с клиентом и чатом), читается `observe show` с этой парой
и выбирается запуском без пары по правилу AC-4.

AC-9. Подсказка запуска (`launch_hint`) и строка перезапуска `pin-update`
(`cycle_command` и вывод `pin-update` для наблюдаемого цикла) имеют форму
`artel.py <cmd> <id> --observation <ID>` при наблюдении и
`artel.py <cmd> <id>` без него и не содержат `--client`/`--chat`;
при задаче, отсутствующей или выключенной в наборе наблюдения,
подсказка содержит `observe add <ID> --tasks <id>`.

AC-10. Отказавший `run`/`auto` (нет наблюдения, устаревшая связь,
названное наблюдение не найдено) оставляет `tasks.state` и таблицу
`leases` без изменений.

AC-11. `docs/operator-session.md` в разделе «Фоновые запуски под
наблюдением» не содержит команд `run`/`auto`/`observe register` с
`--client`/`--chat` как обязательной части порядка и не ссылается на
места документа номерами строк; `docs/stack.md` содержит фразу о
контракте запуска с `--observation`.

## Меняемое поведение
Пары «было → стало» по методам, которые ТЗ называет меняемыми (отказ без
пары, выбор по паре, форма подсказки с парой), и по методам, которые ТЗ
велит не ослаблять, но чьё конкретное значение меняется вместе с формой
строки (`test_restart_line_is_built_by_cycle_hint`,
`test_ac2_observed_cycle_gets_client_and_chat_unobserved_does_not`:
наблюдаемый цикл отличим от ненаблюдаемого теперь по ID наблюдения).
Строгость не снижается: вместо пары проверяется ID наблюдения.

- `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py::ObservationCliTest::test_ac8_launch_requires_matching_client_and_chat`: `все семь контекстов (без пары, только --client, только --chat, пустой --chat, клиент unknown, чужой клиент claude, чужой чат) -> SystemExit, Popen не вызван` → `без пары, чужой клиент claude, чужой чат -> запуск в свежее наблюдение (Popen вызван); только --client, только --chat, пустой --chat, клиент unknown -> SystemExit, Popen не вызван` (требование 2)
- `tests/test_observation_edges.py::ObservationEdgesTest::test_two_chats_cannot_be_chosen_implicitly_for_one_task`: `пара codex/chat-c при наблюдениях chat-a и chat-b -> SystemExit, Popen не вызван` → `запуск без выбора по паре -> Popen вызван, запись в observed_runs только у более свежего наблюдения` (требование 1)
- `tests/test_observation_edges.py::ObservationEdgesTest::test_two_chats_allow_only_the_named_observation`: `пара codex/chat-b выбирает второе наблюдение` → `--observation <ID второго> выбирает второе наблюдение; observed_runs первого пуст` (требование 1)
- `tests/test_cycle_hint.py::CycleHintTest::test_enabled_observation_wins_over_fresher_one_without_task`: `hint[0] содержит "--client codex --chat chat-enabled"` → `hint[0] содержит "--observation <enabled>" и не содержит "--client"` (требование 4)
- `tests/test_cycle_hint.py::CycleHintTest::test_task_removed_from_observation_suggests_observe_add`: `hint[0] содержит "--client claude --chat chat-removed"` → `hint[0] содержит "--observation <observation_id>" и не содержит "--client"` (требование 4)
- `tests/test_cycle_hint.py::CycleHintTest::test_launch_text_continues_caller_prefix_on_one_line`: `lines[0] начинается с "  дальше: artel.py auto <TASK> --client "` → `lines[0] начинается с "  дальше: artel.py auto <TASK>" и не содержит "--client"/"--chat"` (требование 4)
- `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::LaunchHintTest::test_ac1_shape_launch_line_then_first_steps`: `hint[0] начинается с "artel.py <cmd> <TASK> --client " и содержит "--chat " во всех случаях` → `случай «в»: hint[0] начинается с "artel.py <cmd> <TASK>" без "--client"/"--chat"/"--observation"; случаи «а»/«б»: hint[0] начинается с "artel.py <cmd> <TASK> --observation <ID>"` (требование 4)
- `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::LaunchHintTest::test_ac2_no_observation_register_then_watch_then_launch`: `строка запуска ищется по "artel.py <cmd> <TASK> --client"` → `строка запуска ищется по "artel.py <cmd> <TASK>" и не содержит "--client"` (требование 4)
- `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::LaunchHintTest::test_ac3_active_observation_with_task_gives_its_client_chat_and_watch`: `hint[0] содержит "--client <client> --chat <chat>"` → `hint[0] содержит "--observation <observation_id>" и не содержит "--client"` (требование 4)
- `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::LaunchHintTest::test_ac4_disabled_task_suggests_observe_add_before_watch`: `hint[0] содержит "--client <client> --chat <chat>"` → `hint[0] содержит "--observation <observation_id>" и не содержит "--client"` (требование 4)
- `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::LaunchHintTest::test_ac5_foreign_stopped_observations_ignored_freshest_chosen`: `строка запуска случая «в» ищется по "artel.py <cmd> <TASK> --client"; hint[0] содержит "--client <fresher client> --chat <fresher chat>"; чат staler в подсказке отсутствует` → `строка запуска случая «в» ищется по "artel.py <cmd> <TASK>"; hint[0] содержит "--observation <fresher ID>"; ID staler в подсказке отсутствует` (требование 4)
- `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::CommandHintEndToEndTest::test_ac9_new_tz_hint_registers_observation`: `вывод new содержит "run <task_id> --client"` → `вывод new содержит "artel.py run <task_id>" и не содержит "--client"` (требование 4)
- `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::CommandHintEndToEndTest::test_ac9_auto_stopped_by_stop_hints_observe_add`: `вывод auto содержит "--client <client> --chat <chat>"` → `вывод auto содержит "--observation <observation_id>" и не содержит "--client"` (требование 4)
- `tests/test_pin_update_stale_cycles.py::CycleCommandTest::test_restart_line_is_built_by_cycle_hint`: `cycle_command("auto", "T1", "codex", "c-9") == "artel.py auto T1 --client codex --chat c-9"; stale_cycle_lines зовёт cycle_command с ("auto", "T1", "codex", "c-9")` → `cycle_command с ID наблюдения <obs> == "artel.py auto T1 --observation <obs>"; stale_cycle_lines зовёт cycle_command с ("auto", "T1", <obs>); cycle_command("auto", "T1") == "artel.py auto T1"` (требование 4)
- `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py::PinUpdateNamesStaleCyclesTest::test_ac2_observed_cycle_gets_client_and_chat_unobserved_does_not`: `вывод и журнал pin-update содержат "auto <tid> --client <client> --chat <chat>"; клиент и чат наблюдения прежнего запуска отсутствуют` → `вывод и журнал pin-update содержат "auto <tid> --observation <ID наблюдения>"; ID наблюдения прежнего запуска отсутствует` (требование 4)

## Оценка объёма и деление
Сработавшие сигналы: зон в frontmatter 8 (≥ 5); критериев приёмки 11
(≥ 10); `budget_usd` $35 (≥ $30, рамка ТЗ).

Решение — **обоснование монолита** (материал для Оператора; решение — на
гейте SPEC).

Разрез по зонам возможен: часть А — механика запуска и регистрации
(`orchestrator/artel.py`, `orchestrator/store.py`, требования 1–3, 5–6),
часть Б — подсказки, строка перезапуска и документация
(`orchestrator/cycle_hint.py`, `orchestrator/doctor/`, `docs/`,
требования 4, 7) после А. Часть А сама по себе мержима (прежние
подсказки с парой продолжают работать — требование 2). Против разреза:
- контракт «строка подсказки исполняется командой как есть»
  (`test_ac6_case_a_launch_line_is_accepted_by_cycle_command`) связывает
  форму `--observation <ID>` в `cycle_hint` с её разбором в `artel.py` —
  обе стороны одного флага проверяются одним набором тестов;
- перечень «Меняемое поведение» делится по частям неравномерно, а
  документация (требование 7) описывает обе половины разом;
- ТЗ уже суженная замена ликвидированной части 2 с рамкой $35; две
  подзадачи — минимум две планки по $25 (≥ $50) против рамки.

## Не входит
- Позиции, просмотр (`observe events`), подтверждение (`acknowledge`),
  уведомления, PID дозора — сделано в 01M4C954HBJWEGD3AZS7Q3EHA4.
- Служба launchd для дозора; панель (ADR-0004); адаптеры возврата в чат;
  канарейка.
- Пересборка таблицы `observations`, NULL в `client`/`chat`, миграция
  схемы; правка `orchestrator/schema.py`.
- Изменение порога свежести `config.OBSERVATION_STALE_SECONDS`.
- Правка путей «только чтение» ТЗ: `orchestrator/schema.py`,
  `orchestrator/watch.py`, `orchestrator/runner.py`, `orchestrator/auto.py`,
  `orchestrator/lease.py`, `orchestrator/fsm.py`, `orchestrator/providers/`,
  `orchestrator/alerts.py`, `docs/adr/`, `docs/invariants.md`,
  `tests/test_invariants.py`, `AGENTS.md`, `CLAUDE.md`, `docs/backlog.md`,
  `.codex/` главной копии, `~/.codex/`.
- Ослабление тестов, которые ТЗ велит не ослаблять:
  `test_ac6_detached_launch_spawns_attach_child` (ребёнок с `--attach`,
  вызов с парой не отказывает), `test_restart_line_is_built_by_cycle_hint`
  (строка собирается `cycle_hint`),
  `test_ac2_observed_cycle_gets_client_and_chat_unobserved_does_not`
  (наблюдаемый цикл отличим от ненаблюдаемого), выбор свежайшего
  наблюдения в `test_ac5_foreign_stopped_observations_ignored_freshest_chosen`
  — их меняемые значения перечислены выше, свойства сохраняются.
- Регенерация `docs/codebase-map.md` и зелёный полный набор `tests/` —
  их держит пульт.

## Материалы
- ТЗ: `tasks/01M4FZ6QYPPKYQZFEX14QH8XT6/TZ.md`.
- Код (main): `orchestrator/artel.py::_cycle_args`, `_launch_detached`,
  `_cmd_run_or_detach`, `_cmd_auto_or_detach`, `_cmd_observe`;
  `orchestrator/store.py::matching_observation`, `session_observations`
  (уже упорядочивает `last_seen_at DESC, rowid DESC`);
  `orchestrator/cycle_hint.py`; `orchestrator/doctor/stale_cycles.py::_observation_args`.
- «Журнал запуска» требования 2 прочитан как журнал шагов задачи
  (`store.journal`, виден в `artel.py log <id>`): в `observed_runs` колонок
  для пары нет, а схема — только чтение.
- `test_ac6_detached_launch_spawns_attach_child`
  (`tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`) подменяет
  `store.matching_observation`; ТЗ велит его не ослаблять.
