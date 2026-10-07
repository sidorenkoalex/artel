---
task: 01M4C956S0RYFZJVP6HZ17WY9C
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Запуск без привязки к чату

Родительская задача: 01M4C62AEZ554ST1CGY4Y30160 — Независимый дозор: позиция в журнале, системное уведомление, запуск без привязки к чату
Зоны: orchestrator/artel.py, orchestrator/cycle_hint.py, orchestrator/store.py, orchestrator/schema.py, orchestrator/doctor/, docs/operator-session.md, docs/stack.md, docs/codebase-map.md, tests/
Порядок: после части 1
Рамка: $60

# ТЗ: Запуск без привязки к чату

Эта часть выполняется после части 1. Переданные --client и --chat остаются
необязательными метаданными; гейт свежести наблюдения сохраняется.

Требования части 2:

1. run/auto без --attach и observe register принимают отсутствие
   --client/--chat. Запуск выбирает свежее активное наблюдение той же сессии,
   проекта и задачи; с --observation <ID> — только названное. При равной
   свежести выбирается большее rowid, не UUID.
2. observations.client и observations.chat допускают NULL после пересборки
   таблицы. Миграция безопасна при параллельных store.db(). doctor/stale_cycles.py
   и cycle_command не печатают пустых --client/--chat.
3. Подсказки дословны: с наблюдением — artel.py <cmd> <id> --observation <ID>,
   без него — artel.py <cmd> <id>. Проверка выбора свежайшего наблюдения в
   test_ac5 сохраняется.
4. Отказы run/auto сохраняют корни «наблюд» и «связ». Сигнатура
   artel._launch_detached(cmd, task, client, chat) совместима с вызовами
   tests/test_detached_cycle.py.
5. docs/operator-session.md описывает продолжение после stop (~259,
   ~273–276, ~291), правило run_in_background (~499–501), подсказки
   (~614–617), таблицу отказов; docs/stack.md согласован с контрактом.

Критерии приёмки части 2:

AC-14. observe register, run и auto без --attach работают без --client/--chat;
прежние вызовы с парой продолжают работать.

AC-15. Явный --observation запускает только названное наблюдение; без него
выбирается свежее, а при равенстве — с большим rowid.

AC-16. NULL-миграция безопасна при параллельном открытии БД и сохраняет
читаемость существующих наблюдений.

AC-17. cycle_command и doctor/stale_cycles.py не выводят пустых клиентских
флагов; отказы содержат «наблюд» и «связ».

AC-18. Подсказка с наблюдением дословно имеет форму artel.py <cmd> <id>
--observation <ID>, без него — artel.py <cmd> <id>; test_ac5 сохраняет
проверку свежайшего наблюдения.

AC-19. Документация содержит продолжение после stop, run_in_background,
подсказки и таблицу отказов.

Меняемое поведение части 2:

- `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py::ObservationCliTest::test_ac8_launch_requires_matching_client_and_chat`: `запуск без пары или с несовпадающей парой отказывает` → `запуск выбирает свежее наблюдение независимо от пары` (требование 1)
- `tests/test_observation_edges.py::ObservationEdgesTest::test_two_chats_cannot_be_chosen_implicitly_for_one_task`: `два свежих наблюдения дают отказ` → `без ID выбирается свежее, при ничьей — большее rowid` (требование 1)
- `tests/test_observation_edges.py::ObservationEdgesTest::test_two_chats_allow_only_the_named_observation`: `выбор задаёт client/chat` → `выбор задаёт --observation` (требование 1)
- `tests/test_cycle_hint.py::CycleHintTest::test_enabled_observation_wins_over_fresher_one_without_task`: `подсказка содержит client/chat` → `подсказка содержит --observation ID` (требование 3)
- `tests/test_cycle_hint.py::CycleHintTest::test_task_removed_from_observation_suggests_observe_add`: `подсказка требует client/chat` → `подсказка не требует client/chat` (требование 3)
- `tests/test_cycle_hint.py::CycleHintTest::test_launch_text_continues_caller_prefix_on_one_line`: `строка содержит --client` → `строка не требует --client` (требование 3)
- `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::LaunchHintTest::test_ac1_shape_launch_line_then_first_steps`: `первая строка содержит --client и --chat` → `первая строка использует --observation ID либо не содержит пару` (требование 3)
- `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::LaunchHintTest::test_ac2_no_observation_register_then_watch_then_launch`: `register и запуск требуют client/chat` → `register и запуск допускают отсутствие client/chat` (требование 1)
- `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::LaunchHintTest::test_ac3_active_observation_with_task_gives_its_client_chat_and_watch`: `наблюдение подставляет client/chat` → `наблюдение подставляет ID` (требование 3)
- `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::LaunchHintTest::test_ac4_disabled_task_suggests_observe_add_before_watch`: `подсказка содержит client/chat` → `подсказка не требует client/chat` (требование 1)
- `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::LaunchHintTest::test_ac5_foreign_stopped_observations_ignored_freshest_chosen`: `подсказка идентифицирует client/chat` → `подсказка идентифицирует ID и сохраняет выбор свежайшего` (требование 3)
- `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::CommandHintEndToEndTest::test_ac9_new_tz_hint_registers_observation`: `подсказка содержит run --client` → `подсказка не требует --client` (требование 3)
- `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::CommandHintEndToEndTest::test_ac9_auto_stopped_by_stop_hints_observe_add`: `подсказка содержит client/chat` → `подсказка не требует client/chat` (требование 3)

Следующие утверждения сохраняются и не ослабляются:
tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py::DetachedLaunchTest::test_ac6_detached_launch_spawns_attach_child по-прежнему требует ребёнка с --attach;
tests/test_pin_update_stale_cycles.py::CycleCommandTest::test_restart_line_is_built_by_cycle_hint по-прежнему требует строить строку через cycle_hint;
tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py::PinUpdateNamesStaleCyclesTest::test_ac2_observed_cycle_gets_client_and_chat_unobserved_does_not по-прежнему различает наблюдаемый и ненаблюдаемый цикл.

Не входит в часть 2:

- Позиции, просмотр/подтверждение, уведомления, PID/живость, экранирование,
  песочница Codex, смена пина и guard-artel-bg — часть 1.
- launchd, панель ADR-0004, адаптеры возврата в чат, канарейка.
- orchestrator/runner.py, orchestrator/auto.py, orchestrator/lease.py,
  orchestrator/fsm.py, orchestrator/providers/, orchestrator/alerts.py,
  docs/adr/, docs/invariants.md, tests/test_invariants.py, AGENTS.md,
  CLAUDE.md, docs/backlog.md, .codex/ главной копии и ~/.codex/.