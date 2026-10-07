---
task: 01M4C62AEZ554ST1CGY4Y30160
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/watch.py, orchestrator/store.py, orchestrator/schema.py, orchestrator/artel.py, orchestrator/cycle_hint.py, orchestrator/config.py, orchestrator/doctor/, docs/operator-session.md, docs/stack.md, docs/codebase-map.md, tests/
budget_usd: 85
---

# SPEC: Независимый дозор: позиции событий, уведомления и запуск без привязки к чату

## Контекст

watch --observation хранит позицию чтения лишь в памяти процесса, а
отсоединённый запуск связан с чатом ассистента. Независимый дозор должен
сохранять события и уведомлять Оператора вне завершившегося чата. Оператор
08.10.2026 решил реализовывать это двумя самостоятельно мержимыми частями.

## Требования

1. Наблюдение хранит позиции «оповещено» и «разобрано», поддерживает
   просмотр, подтверждение, живость дозора и системные уведомления.
2. Отсоединённые run/auto и observe register работают без обязательных
   --client и --chat, связывая запуск со свежим наблюдением.
3. Документация описывает независимый дозор, запуск из терминала Оператора,
   просмотр и подтверждение событий из нового чата любого клиента.

## Критерии приёмки

AC-1. Первая часть самостоятельно сохраняет и показывает события, позволяет
их подтвердить, сообщает о живости дозора и доставляет уведомления при
неизменном контракте --client/--chat.

AC-2. Вторая часть после первой разрешает запуск и регистрацию без
--client/--chat, выбирает свежее наблюдение по установленному правилу и
сохраняет совместимость вызовов с этими метаданными.

AC-3. Каждая часть имеет собственные зоны и зелёную планку; вторая не
мержится до первой.

## Оценка объёма и деление

Сработали сигналы большого объёма: зон не меньше пяти, критериев не меньше
десяти и бюджет не ниже $30. Нарезка принята Оператором 08.10.2026: часть 1
даёт сохранность событий и уведомление сама по себе; изменения тестов
меняемого поведения, относящиеся к контракту запуска, — только в части 2.
Первая часть не меняет обязательность --client/--chat и мержима с прежним
контрактом. Вторая опирается на сохранённое наблюдение и поставляется после
первой.

## Деление

### Дозор: позиции, просмотр, подтверждение, уведомление

Зоны: orchestrator/watch.py, orchestrator/store.py, orchestrator/schema.py, orchestrator/artel.py, orchestrator/config.py, orchestrator/doctor/, docs/operator-session.md, docs/stack.md, docs/codebase-map.md, tests/
Порядок: первая, без зависимостей
Рамка: $70

# ТЗ: Дозор: позиции, просмотр, подтверждение, уведомление

Контракт запуска не меняется: --client и --chat остаются обязательными в
прежних местах. Отсоединённый запуск без включённых уведомлений лишь
предупреждает об этом.

Требования части 1:

1. Наблюдение хранит две монотонные позиции: «оповещено» и «разобрано» —
   пары максимальных id steps и alerts. При регистрации и миграции обе
   получают текущие максимумы. Миграция заполняет отсутствующие значения
   одним UPDATE ... WHERE ... IS NULL; INSERT в observations перечисляет
   колонки явно.
2. watch --observation <ID> читает steps одним запросом по полному набору
   наблюдаемых задач в порядке steps.id, а не по задачам: ранний выход не
   пропускает более раннее событие другой задачи. Позиция «оповещено»
   продвигается после выдачи; observe events --from <пара> возвращает
   максимумы просмотренных id, включая отсеянные фильтром. Обычный watch
   без --observation сохраняет прежнее поведение.
3. observe events <ID> выдаёт неподтверждённые события; observe acknowledge
   <ID> --through <пара> монотонно продвигает «разобрано». Подтверждение
   сверх текущих максимумов — отказ. Команды сверяют сессию пульта как
   watch; отказы внесены в таблицу. Роли разрешён только events;
   acknowledge запрещён. Конкурентные подтверждения не откатывают позицию.
   Эти команды и дозор не меняют данные задач и не берут lease.
4. В --observation и observe events класс alerts входит в набор по
   умолчанию. Отказы «роль ещё не закончила» не уведомляются. Признак
   уведомлений хранится в наблюдении и виден в observe show; запуск при
   наблюдении без уведомлений предупреждает.
5. watch --observation <ID> --notify уведомляет macOS о переходах в
   spec_gate, acceptance, merge_gate, escalated, отказах перехода и
   остановке цикла. Вывод watch и observe events экранирует ESC, OSC 52 и
   прочие управляющие символы недоверенного текста. osascript получает текст
   отдельными аргументами, с правилом для NUL и текста с начальным -. Вне
   macOS выводится одна строка; ошибка не останавливает дозор.
6. Дозор пишет PID, хост и время старта. Захват атомарен (BEGIN IMMEDIATE и
   условие на прежний PID); собственный PID перехватываем, чужой хост даёт
   именованный отказ с добавленной командой принудительного перехвата. PID
   очищается в finally. observe stop завершает процесс с кодом 0 не позже
   следующего опроса. observe show и doctor различают живой процесс, мёртвый
   PID и свежую связь без PID.
7. run/auto из песочницы Codex без сети и записи вне каталога распознают это
   обоснованным способом и отказывают с объяснением. Дозор запоминает HEAD
   главной копии и при смене пина предупреждает о перезапуске.
8. doctor проверяет .codex/hooks.json главной копии и ~/.codex/hooks.json,
   распознаёт guard-artel-bg и называет hook-migrate; распознаватель при
   необходимости в orchestrator/doctor/. Сами файлы .codex/ не меняются.
9. docs/operator-session.md описывает правило «дозор в терминале Оператора,
   не инструментом ассистента» и перезапуск после pin-update; обновляет
   шаг 4 (~44–56), фоновые запуски и ~437, «Когда наблюдатель завершается
   сам» (~538–549), урок о 30 минутах Monitor (~648–653) и таблицу отказов.
   docs/stack.md описывает независимый дозор.

Критерии приёмки части 1:

AC-4. Повторный дозор после остановки печатает новые steps и alerts после
позиции «оповещено» ровно раз; регистрация и миграция ставят позиции в
текущие максимумы.

AC-5. Для нескольких задач steps читаются одним запросом в порядке id; ранний
выход не пропускает более раннее событие другой задачи.

AC-6. events выдаёт неподтверждённое, acknowledge не понижает позицию при
повторном, запоздалом и конкурентном вызове и отказывает выше максимума.

AC-7. Роли разрешён events и запрещён acknowledge; обе операции сверяют
сессию, не меняют tasks.state и не берут lease.

AC-8. Уведомление вызывается только для требуемых событий, не вызывается для
«роль ещё не закончила», а его сбой не завершает дозор.

AC-9. Текст с кавычками, ESC и OSC 52 безопасно передаётся отдельным
аргументом; вывод экранирован, вне macOS — одна строка.

AC-10. show и doctor различают живой процесс, мёртвый PID и свежую связь без
PID; захват соблюдает все правила требования 6.

AC-11. observe stop завершает дозор с кодом 0 не позднее следующего опроса и
очищает PID; после смены пина появляется предупреждение.

AC-12. run/auto из песочницы Codex отказывают с объяснением; отсутствие
уведомлений даёт предупреждение.

AC-13. doctor распознаёт guard-artel-bg в обоих файлах и называет
hook-migrate; документация содержит требуемый порядок и правила.

Меняемое поведение части 1:

- `tests/test_watch.py::EmitStepsFiltersInSqlTest::test_only_the_single_new_row_comes_from_sql`: `_emit_steps вызывается для одной задачи` → `_emit_steps читает все задачи наблюдения одним упорядоченным запросом` (требование 2)
- `tests/test_watch.py::EmitStepsFiltersInSqlTest::test_prints_the_new_rows_of_the_asked_classes_and_moves_the_cursor`: `курсор одной задачи передаётся в _emit_steps` → `позиция наблюдения продвигается по общему набору` (требование 2)
- `tests/test_watch.py::EmitStepsFiltersInSqlTest::test_the_already_shown_row_is_not_printed_a_second_time`: `граница повторного чтения хранится для одной задачи` → `граница следует сохранённой позиции наблюдения` (требование 2)

Очистка tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py::WatchProgressSandbox::force_stop, прежде переводившая задачи в killed, останавливает живой дозор через observe stop, не изменяя состояние задач.

Не входит в часть 1:

- Необязательность --client/--chat, выбор наблюдения при запуске, NULL-миграция
  клиентских полей и новые подсказки — часть 2.
- launchd, панель ADR-0004, адаптеры возврата в чат, канарейка.
- orchestrator/runner.py, orchestrator/auto.py, orchestrator/lease.py,
  orchestrator/fsm.py, orchestrator/providers/, orchestrator/alerts.py,
  docs/adr/, docs/invariants.md, tests/test_invariants.py, AGENTS.md,
  CLAUDE.md, docs/backlog.md, .codex/ главной копии и ~/.codex/.

### Запуск без привязки к чату

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

## Не входит

- Служба launchd для наблюдателя, панель ADR-0004 и адаптеры возврата в чат.
- Роли конвейера на моделях Codex, ошибка suite-run у роли Codex и канарейка.
- orchestrator/runner.py, orchestrator/auto.py, orchestrator/lease.py,
  orchestrator/fsm.py, orchestrator/providers/, orchestrator/alerts.py,
  docs/adr/, docs/invariants.md, tests/test_invariants.py, AGENTS.md,
  CLAUDE.md, docs/backlog.md, .codex/ главной копии и ~/.codex/.

## Материалы

- TZ.md: решение Оператора от 07.10.2026.
- Решение Оператора от 08.10.2026 о нарезке и замечания независимого ревью.
