---
task: 01M4FZ6QYPPKYQZFEX14QH8XT6
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Запуск без привязки к чату

# ТЗ: Запуск без привязки к чату (суженный)

Источник: решение Оператора 09.10.2026. Заменяет часть 2
01M4C956S0RYFZJVP6HZ17WY9C родителя 01M4C62AEZ554ST1CGY4Y30160
(ликвидирована 09.10 на `spec_writing`, работы не было). Часть 1
(01M4C954HBJWEGD3AZS7Q3EHA4: позиции, `observe events`/`acknowledge`,
уведомление, PID дозора) смержена в main 09.10. Разбор ТЗ прежней части 2
сессией при Операторе 09.10 нашёл: пересборка таблицы `observations` ради
NULL — лишний риск; подсказка запуска расходится со строкой перезапуска
`pin-update` (`cycle_command`); не сказано, что значит переданная пара
`--client`/`--chat`; у `run`/`auto` нет флага `--observation`; ссылки на
строки документации устарели.

Факты (main после мержа 01M4C954, сверка 09.10):
- `orchestrator/artel.py::_cycle_args` отказывает без
  `--client codex|claude --chat <ID>`; `_launch_detached` ищет наблюдение
  по клиенту и чату (`store.matching_observation`: задача, проект, сессия
  пульта, клиент, чат) и отказывает, если связь старше
  `config.OBSERVATION_STALE_SECONDS`. `observe register` (`_cmd_observe`)
  требует `--client` и `--chat`.
- `observations.client`, `observations.chat` — `TEXT NOT NULL`
  (`orchestrator/schema.py`).
- Подсказки запуска строит `orchestrator/cycle_hint.py`; строку
  перезапуска для `pin-update` — `cycle_command` через тот же
  `cycle_hint` (`tests/test_pin_update_stale_cycles.py`).
- Поведение «без пары — отказ» и «выбор по паре» закреплено
  долгоживущими тестами: `tests/test_detached_cycle.py`,
  `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`,
  `tests/test_observation_edges.py`, `tests/test_cycle_hint.py`,
  `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`,
  `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_observe_extra_args.py`.

Требуется:
1. `run`/`auto` без `--attach` и `observe register` работают без
   `--client`/`--chat`. У `run`/`auto` появляется необязательный флаг
   `--observation <ID>`: с ним запуск идёт только в названное наблюдение;
   без него — в самое свежее активное наблюдение той же сессии пульта и
   проекта, в наборе которого есть задача; при равной свежести — в
   созданное позже. Гейт свежести (90 с) не меняется.
2. Переданная пара `--client`/`--chat` — только метаданные аудита: она
   записывается в наблюдение и в журнал запуска и в выборе наблюдения не
   участвует. Прежние вызовы с парой работают без изменений.
3. Схема без пересборки таблицы: отсутствие метаданных хранится пустой
   строкой в существующих колонках `NOT NULL`, миграция не нужна.
   Существующие наблюдения читаются как прежде.
4. Подсказки и строка перезапуска `pin-update` строятся одним
   `cycle_hint` и имеют одну форму: `artel.py <cmd> <id> --observation
   <ID>` при наблюдении, `artel.py <cmd> <id>` без него; пустых
   `--client`/`--chat` не печатают. Подсказки по-прежнему ведут к
   `observe add`, если задачи нет в наборе.
5. Отказы `run`/`auto` называют наблюдение и связь (что устарело, какой
   `watch --observation` перезапустить) и не требуют пары.
6. `docs/operator-session.md`: порядок фоновых запусков — без пары
   (наблюдатель, `observe add`, `run`/`auto`, `observe events` и
   `acknowledge` из любого чата), таблица отказов; ссылки — по
   заголовкам разделов, а не по номерам строк. `docs/stack.md` —
   одна фраза о контракте.

Меняемое поведение (SPEC объявляет пары «было → стало» по инварианту 38,
только тестовыми методами): отказ без пары и выбор наблюдения по паре —
`test_ac8_launch_requires_matching_client_and_chat`,
`test_two_chats_cannot_be_chosen_implicitly_for_one_task`,
`test_two_chats_allow_only_the_named_observation`; форма подсказки с
парой — методы `tests/test_cycle_hint.py` и
`tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`, которые её
проверяют. Не ослабляются:
`test_ac6_detached_launch_spawns_attach_child` (ребёнок с `--attach`),
`test_restart_line_is_built_by_cycle_hint`,
`test_ac2_observed_cycle_gets_client_and_chat_unobserved_does_not`
(наблюдаемый цикл отличим от ненаблюдаемого — теперь по ID наблюдения),
выбор свежайшего наблюдения в `test_ac5_…`.

Критерии приёмки (направление; планку пишет test_author):
- `auto` без пары при свежем наблюдении запускается, при устаревшем —
  отказ, называющий наблюдение; вызов с парой работает как прежде, и
  пара записана в журнал.
- Два свежих наблюдения с задачей: без `--observation` выбрано более
  свежее (при равенстве — созданное позже), с `--observation` — только
  названное; названное устаревшее — отказ, даже если есть другое свежее.
- `observe register` без пары создаёт наблюдение; `observe show`
  показывает пустые метаданные без ошибки; наблюдения, созданные до
  задачи, читаются.
- Подсказка запуска и строка перезапуска `pin-update` совпадают по форме
  и не содержат пустых `--client`/`--chat`.
- Запуск не меняет `tasks.state` до старта цикла и не берёт lease,
  если отказал.

Зоны: orchestrator/artel.py, orchestrator/cycle_hint.py,
orchestrator/store.py, orchestrator/doctor/, docs/operator-session.md,
docs/stack.md, docs/codebase-map.md, tests/.

Только чтение (не менять): orchestrator/schema.py, orchestrator/watch.py,
orchestrator/runner.py, orchestrator/auto.py, orchestrator/lease.py,
orchestrator/fsm.py, orchestrator/providers/, orchestrator/alerts.py,
docs/adr/, docs/invariants.md, tests/test_invariants.py, AGENTS.md,
CLAUDE.md, docs/backlog.md, .codex/ главной копии, ~/.codex/.

Не входит: позиции, просмотр, подтверждение, уведомления, PID дозора
(сделано в 01M4C954); служба launchd для дозора; панель (ADR-0004);
адаптеры возврата в чат; канарейка.

Рамка: $35.

Набор моделей: по умолчанию.
