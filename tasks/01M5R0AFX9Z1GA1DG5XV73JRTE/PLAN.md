---
task: 01M5R0AFX9Z1GA1DG5XV73JRTE
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Сведение тестов, волна 3м-2 — мьютекс по проекту и зависимости мержа в файлы модулей pytest

## Подход

Перенос без улучшений: 17 тестов долгоживущего
`tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py` — функциями
в конец `tests/test_merge_lock_module.py` (классы `AcquireByProjectTest`,
`ReleaseAndHeartbeatTest`, `StoreMergeLockTest`) и `tests/test_merge_queue.py`
(`QueueByProjectTest`, `WaitTextsByProjectTest`); 20 тестов
`tests/test_merge_after.py`, `tests/test_merge_after_declared.py`,
`tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py`,
`tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py` — в новый
`tests/test_merge_after_module.py`. Ожидания — дословно в форме `assert …`
(соответствие требования 12), сообщение — вторым операндом, наборы `subTest`
— прежним циклом с ярлыком `+ "; " + f"<ключ>={<значение>!r}, …"` в каждом
сообщении подслучая. Пять исходных файлов удалены (мандат ANSWER-1).

Доказательство неослабления — 52 патча мутаций `mutation-001.diff` …
`mutation-052.diff` (генератор `make_patches.py` в каталоге документов —
замены текста в `orchestrator/` и `git apply --check`), прогнанных
`mutation-run` «до» (`--ref base`, пять файлов волны) и «после»
(`--ref worktree`, три файла модулей) одними диапазонами `--patches`:
1-5, 6-10 (патчи пути взятия окна и цикла `wait_for_window` — части по 5,
решение 3 ANSWER-1), 11-30, 31-50, 51-52. Строки падения и соответствие
«до → после» собраны из логов прогонов (`fail_lines.py`, `make_plan.py`).

Удалённых дублей нет: каждый из 37 тестов перенесён своей функцией с тем же
именем (тест каждого из пяти файлов держит хотя бы одну мутацию, которую в
своём файле убивает только он, либо дубль не проходит условие (б)).

## Шаги

1. Патчи мутаций по 37 заявкам (52 патча, раздел «Мутации: патчи и заявки»),
   прогоны «до» частями.
2. Свод mutex_by_project в файлы замка и очереди: фикстура
   `project_mutex_stand`, помощники-функции, тесты в конец файлов, абзац о
   волне 3м-2 в докстрингах, недостающие импорты.
3. Свод четырёх файлов merge_after в `tests/test_merge_after_module.py`:
   фикстуры `merge_after_stand`, `loss_stand`, `declared_path_stand`,
   `division_sandbox`/`division_stand`, класс `DivisionSandbox`.
4. Удаление пяти файлов волны, регенерация `docs/codebase-map.md`.
5. Прогоны «после» теми же частями, соответствие «до → после», замеры.

## Мутации: патчи и заявки

Каждая строка — патч, файл его правки, что он меняет и чьи заявки
(альтернативы «либо …») он воплощает. Одинаковые по смыслу альтернативы
разных тестов сведены в одну мутацию со списком тестов.

- mutation-001 — `orchestrator/merge_lock.py`: `acquire` берёт строку мьютекса всего пульта `store.merge_lock_row(conn)` вместо строки проекта задачи. Заявки: AcquireByProjectTest::test_ac1_other_project_holder_does_not_block_acquire — «acquire читает одну строку на пульт»; AcquireByProjectTest::test_ac4_dead_holder_of_other_project_is_left_intact — «перехватывает любую мёртвую строку таблицы»; AcquireByProjectTest::test_ac4_dead_holder_of_same_project_is_taken_over — «перехват ищет мёртвую строку не своего проекта» — тот же смысл; этот тест её не убивает: в его таблице одна строка; QueueByProjectTest::test_ac2_other_project_holder_does_not_delay_wait_for_window — «acquire ждёт освобождения мьютекса всего пульта».
- mutation-002 — `orchestrator/merge_lock.py`: `acquire` ищет держателя по проекту `task_id` (никогда не совпадает) — держатель того же проекта считается чужим. Заявки: AcquireByProjectTest::test_ac3_live_holder_of_same_project_refuses_with_old_text — «проект сверяется не по target задачи держателя».
- mutation-003 — `orchestrator/merge_lock.py`: текст отказа `acquire`: «дождись освобождения» → «жди освобождения». Заявки: AcquireByProjectTest::test_ac3_live_holder_of_same_project_refuses_with_old_text — «текст отказа собран иначе».
- mutation-004 — `orchestrator/merge_lock.py`: перехват мёртвого держателя в `acquire` без записи журнала «мьютекс merge перехвачен». Заявки: AcquireByProjectTest::test_ac4_dead_holder_of_same_project_is_taken_over — «перехват идёт без записи журнала».
- mutation-005 — `orchestrator/store.py`: `set_merge_lock` стирает всю таблицу `merge_locks` (`DELETE` без `WHERE`). Заявки: AcquireByProjectTest::test_ac1_other_project_holder_does_not_block_acquire — «set_merge_lock делает DELETE без WHERE»; AcquireByProjectTest::test_ac4_dead_holder_of_other_project_is_left_intact — «set_merge_lock стирает строки других проектов»; StoreMergeLockTest::test_ac11_set_merge_lock_keeps_other_project_row — «set_merge_lock оставлен с DELETE без WHERE».
- mutation-006 — `orchestrator/store.py`: `set_merge_lock` добавляет строку, не снося прежнюю строку проекта. Заявки: AcquireByProjectTest::test_ac4_dead_holder_of_same_project_is_taken_over — «set_merge_lock добавляет строку, не снося прежнюю строку проекта».
- mutation-007 — `orchestrator/store.py`: `task_target` отдаёт сырую колонку `target` (пустую, `NULL`, `None` для задачи без строки) без нормализации. Заявки: AcquireByProjectTest::test_ac16_artel_holder_excludes_empty_null_and_missing_target — «проект задачи берётся сырой колонкой target».
- mutation-008 — `orchestrator/merge_queue.py`: `wait_for_window`: голова — первая запись всей очереди `_head_task_id(conn)` без проекта. Заявки: QueueByProjectTest::test_ac8_head_is_earliest_entry_of_own_project — «голова очереди — первая запись всего пульта»; QueueByProjectTest::test_ac8_same_project_tasks_enter_in_fifo_order — «голова считается по всей очереди»; QueueByProjectTest::test_ac9_dead_entry_of_project_does_not_hold_its_head — «голова по всей очереди».
- mutation-009 — `orchestrator/merge_queue.py`: `wait_for_window`: условие «голова очереди своего проекта» заменено на `True` — FIFO внутри проекта снят. Заявки: QueueByProjectTest::test_ac8_same_project_tasks_enter_in_fifo_order — «FIFO внутри проекта снят (голова — любая запись своего проекта либо своя)».
- mutation-010 — `orchestrator/merge_queue.py`: `wait_for_window` не зовёт `_prune_dead_entries` до определения головы. Заявки: QueueByProjectTest::test_ac9_dead_entry_of_project_does_not_hold_its_head — «пруна мёртвых записей не идёт до определения головы проекта».
- mutation-011 — `orchestrator/store.py`: `_ROW_TARGET_SQL` (проект строки мьютекса для `merge_lock_rows`): `COALESCE(t.target, ?)` — пустой target не нормализуется. Заявки: AcquireByProjectTest::test_ac16_empty_or_null_target_holder_excludes_artel_task — «проект держателя берётся сырой колонкой target».
- mutation-012 — `orchestrator/store.py`: `release_merge_lock` снимает строки по одному `session_id`. Заявки: ReleaseAndHeartbeatTest::test_ac5_release_removes_only_own_process_row — «release сносит строки по одному session_id».
- mutation-013 — `orchestrator/store.py`: `release_merge_lock` снимает всю таблицу `merge_locks`. Заявки: ReleaseAndHeartbeatTest::test_ac5_release_removes_only_own_process_row — «release сносит всю таблицу»; StoreMergeLockTest::test_ac11_set_merge_lock_keeps_other_project_row — «release_merge_lock снимает строки по проекту/всю таблицу».
- mutation-014 — `orchestrator/merge_lock.py`: `_own_rows` с `task_id`: продлеваются все строки таблицы. Заявки: ReleaseAndHeartbeatTest::test_ac6_touch_heartbeat_renews_only_callers_project_row — «продлевает все строки».
- mutation-015 — `orchestrator/merge_lock.py`: `_own_rows` с `task_id`: «своя» строка сверяется только по проекту. Заявки: ReleaseAndHeartbeatTest::test_ac7_touch_heartbeat_does_not_renew_intercepted_row — «продление сверяет только проект строки».
- mutation-016 — `orchestrator/merge_lock.py`: `_own_rows` с `task_id`: «своя» строка сверяется по проекту и задаче, без сессии. Заявки: ReleaseAndHeartbeatTest::test_ac7_touch_heartbeat_does_not_renew_intercepted_row — «или только задачу».
- mutation-017 — `orchestrator/merge_lock.py`: `_own_rows` без `task_id` при одной строке: «своя» строка сверяется по `task_id is None` — ничего не продлевается. Заявки: ReleaseAndHeartbeatTest::test_ac17_touch_heartbeat_without_args_keeps_old_behaviour — «прежняя форма без task_id превращена в ничего не делающую».
- mutation-018 — `orchestrator/merge_queue.py`: `_holder_row`: держатель для текстов ожидания — первая строка таблицы `merge_lock_row`. Заявки: WaitTextsByProjectTest::test_ac10_wait_texts_name_holder_of_waiting_task_project — «тексты собираются по первой строке таблицы».
- mutation-019 — `orchestrator/merge_queue.py`: `_current_holder_label`: метка «(pid <pid>, проект <target>)». Заявки: WaitTextsByProjectTest::test_ac10_single_project_texts_are_unchanged — «тексты получили метку проекта или иной формат».
- mutation-020 — `orchestrator/idgen.py`: `is_task_id_form`: проверка длины снята. Заявки: TaskIdFormTest::test_form_accepts_ids_prefixes_and_legacy_rejects_rest — «проверка длины снята».
- mutation-021 — `orchestrator/idgen.py`: `is_task_id_form`: алфавит не сверяется, только длина. Заявки: TaskIdFormTest::test_form_accepts_ids_prefixes_and_legacy_rejects_rest — «алфавит не сверяется».
- mutation-022 — `orchestrator/store.py`: `task_id_matches`: точное совпадение не проверяется первым. Заявки: TaskIdMatchesTest::test_exact_match_wins_over_longer_ids_with_same_prefix — «точное совпадение не проверяется первым».
- mutation-023 — `orchestrator/merge_after.py`: `check`: повтор сверяется по буквальному тексту элемента, не по разрешённому id. Заявки: CheckTest::test_prefix_and_full_id_of_same_task_is_a_repeat — «повтор сверяется только по буквальному тексту элемента».
- mutation-024 — `orchestrator/merge_after.py`: `check`: зависимость в `done` отказывается как `killed`. Заявки: CheckTest::test_done_dependency_is_valid — «done спутан с killed».
- mutation-025 — `orchestrator/merge_after.py`: `merge_gate_refuses`: пропавшая из БД зависимость — в ветке незавершённых (подсказка повтора `approve`). Заявки: MergeGateMissingDependencyTest::test_dependency_missing_from_db_refuses_with_answer_channel — «пропавшая зависимость обрабатывается как незавершённая».
- mutation-026 — `orchestrator/merge_after.py`: `value_refusals`: «нет» молча отбрасывается из элементов строки мандата до проверки. Заявки: MandateLineTest::test_none_word_mixed_with_ids_refused — «нет молча отбрасывается из перечня до проверки».
- mutation-027 — `orchestrator/merge_after.py`: `lines_refusal`: считается только первая строка мандата — повтор не замечается. Заявки: MandateLineTest::test_two_mandate_lines_refused — «берётся первая строка, вторая молча теряется».
- mutation-028 — `orchestrator/merge_after.py`: `apply_plan`: совпадение с БД сверяется по сырому тексту PLAN, не по разрешённым id. Заявки: PlanChannelSameValueTest::test_plan_value_equal_to_db_after_resolution_is_silent — «сравнение идёт по сырому тексту PLAN».
- mutation-029 — `orchestrator/merge_after.py`: `replace_divided`: фильтр «родитель в значении» снят — переписывается каждая задача. Заявки: ReplaceDividedTest::test_task_not_depending_on_parent_is_untouched — «фильтр «родитель в значении» снят».
- mutation-030 — `orchestrator/schema.py`: `migrate` не добавляет колонку `merge_after`. Заявки: MigrationTest::test_migrate_adds_merge_after_to_old_tasks_table — «колонка добавлена только в DDL».
- mutation-031 — `orchestrator/merge_after.py`: `_ORDER_LINE_RE` без `^` — метка ищется в любом месте строки. Заявки: DeclaredFromTzTest::test_label_must_start_line_and_word_must_be_whole — «метка ищется в любом месте строки (без ^)».
- mutation-032 — `orchestrator/merge_after.py`: `_ORDER_LINE_RE` без `(?!\w)` — слово «после» сверяется префиксом. Заявки: DeclaredFromTzTest::test_label_must_start_line_and_word_must_be_whole — «слово «после» сверяется префиксом».
- mutation-033 — `orchestrator/merge_after.py`: `declared_from_tz`: пустой перечень возвращается как `([], [])`. Заявки: DeclaredFromTzTest::test_empty_list_is_refused — «пустой перечень возвращается как ([], [])».
- mutation-034 — `orchestrator/merge_after.py`: `check`: target заводимой задачи берётся из БД (`store.task_target(conn, None)`), не явный. Заявки: DeclaredFromTzTest::test_explicit_target_of_new_task_is_used — «check берёт target из строки БД несуществующей задачи».
- mutation-035 — `orchestrator/merge_after.py`: `spec_gate_declared_refusal`: признак «гейт SPEC уже пройден» (`_declared_in_force`) снят. Заявки: SpecGateDeclaredRefusalTest::test_no_check_after_spec_gate_was_passed — «признак «гейт SPEC уже пройден» снят».
- mutation-036 — `orchestrator/merge_after.py`: `_justified`: обоснование ищется подстрокой, не словом целиком. Заявки: SpecGateDeclaredRefusalTest::test_short_prefix_inside_other_id_is_not_justification — «обоснование ищется подстрокой».
- mutation-037 — `orchestrator/fsm.py`: деление на гейте SPEC подставляет первую подзадачу `new_ids[0]` вместо последней. Заявки: DivisionRewritesDependentsTest::test_ac1_parent_replaced_by_last_subtask_in_every_dependent — «вместо последней подзадачи подставлена первая».
- mutation-038 — `orchestrator/merge_after.py`: `replace_divided`: элемент-родитель удаляется вместо замены. Заявки: DivisionRewritesDependentsTest::test_ac1_parent_replaced_by_last_subtask_in_every_dependent — «элемент P удалён вместо замены».
- mutation-039 — `orchestrator/merge_after.py`: `replace_divided`: переписывается только первая найденная зависящая задача. Заявки: DivisionRewritesDependentsTest::test_ac1_parent_replaced_by_last_subtask_in_every_dependent — «переписана только первая найденная зависящая задача».
- mutation-040 — `orchestrator/merge_after.py`: `replace_divided`: значение — один Sn, соседи X отброшены. Заявки: DivisionRewritesDependentsTest::test_ac1_parent_replaced_by_last_subtask_in_every_dependent — «соседи X отброшены».
- mutation-041 — `orchestrator/merge_after.py`: `replace_divided`: колонка переписывается прямым `store.update_task` мимо `rewrite` (без журнала). Заявки: DivisionRewritesDependentsTest::test_ac2_dependent_journal_names_old_and_new_value — «колонка D переписана прямым store.update_task мимо merge_after.rewrite».
- mutation-042 — `orchestrator/merge_after.py`: `replace_divided`: запись «merge_after изменён» идёт в журнал родителя, не зависящей задачи. Заявки: DivisionRewritesDependentsTest::test_ac2_dependent_journal_names_old_and_new_value — «запись сделана в журнал родителя P вместо журнала D».
- mutation-043 — `orchestrator/fsm.py`: деление на гейте SPEC не зовёт `replace_divided`. Заявки: DivisionRewritesDependentsTest::test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent — «деление не переписывает merge_after зависящих задач».
- mutation-044 — `orchestrator/merge_after.py`: `replace_divided`: переписывается только строка самого родителя. Заявки: DivisionRewritesDependentsTest::test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent — «переписывает только колонку родителя».
- mutation-045 — `orchestrator/merge_after.py`: отказ о потере заявленной зависимости — с прежним хвостом «снять заявленную может только Оператор …». Заявки: LossRefusalTextTest::test_ac8_loss_refusal_leads_through_reject_and_escalated_answer — «хвост отказа не заменён».
- mutation-046 — `orchestrator/merge_after.py`: отказ о потере: «answer» стоит раньше «reject». Заявки: LossRefusalTextTest::test_ac8_loss_refusal_leads_through_reject_and_escalated_answer — «новый текст называет answer раньше reject».
- mutation-047 — `orchestrator/merge_after.py`: начало отказа о потере: «merge_after в SPEC теряет …». Заявки: LossRefusalTextTest::test_ac8_loss_refusal_leads_through_reject_and_escalated_answer — «правка задела начало отказа».
- mutation-048 — `orchestrator/merge_after.py`: отказ о добавке: «без обоснования» → «без причины». Заявки: DeclaredPathTest::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged — «отказ о добавке без обоснования сменил текст».
- mutation-049 — `orchestrator/merge_after.py`: отказ гейта мержа по убитой зависимости: «сними или замени её» → «замени её». Заявки: DeclaredPathTest::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged — «отказы гейта мержа сменили текст».
- mutation-050 — `orchestrator/merge_after.py`: `mandate_value`: строка мандата в ответе не находится — `answer` в escalated колонку не меняет. Заявки: DeclaredPathTest::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged — «answer в escalated перестал менять колонку».
- mutation-051 — `orchestrator/merge_lock.py`: `_own_rows` с `task_id`: продлевается первая строка таблицы. Заявки: ReleaseAndHeartbeatTest::test_ac6_touch_heartbeat_renews_only_callers_project_row — «продление берёт первую строку таблицы».
- mutation-052 — `orchestrator/merge_queue.py`: `wait_for_window`: пруна убирает только мёртвые записи других проектов. Заявки: QueueByProjectTest::test_ac9_dead_entry_of_project_does_not_hold_its_head — «или убирает только записи другого проекта».

Альтернатива заявки `ReleaseAndHeartbeatTest::test_ac17_touch_heartbeat_without_args_keeps_old_behaviour`
«либо пустая таблица роняет вызов исключением» патчем не воплощена: тест
ловит её только исключением без падения утверждения (требование 4 — не
доказательство); см. раздел «Находки».

## Перенос: метод → функция

Стенды (тело `setUp` дословно без `super().setUp()`, `self.` → параметр,
хвост `return <параметр>`):
- `_ProjectMutexBase.setUp` → `project_mutex_stand(tmp_root)` — в обоих
  файлах `tests/test_merge_lock_module.py` и `tests/test_merge_queue.py`,
  тела одинаковы;
- `MergeAfterDbSandbox.setUp` и `DeclaredSandbox.setUp` (тела равны) →
  `merge_after_stand(light_transition)`;
- `LossRefusalTextTest.setUp` → `loss_stand(initialized_tmp_root)`;
- `DeclaredPathTest.setUp` → `declared_path_stand(light_transition)`,
  `self.addCleanup(env.stop)` → `light_transition.addCleanup(env.stop)`;
- `DivisionRewritesDependentsTest.TASK_TITLE` → класс
  `DivisionSandbox(LightTransitionSandbox)` с тем же литералом, фикстура
  `division_sandbox()` = `yield from _sandbox(DivisionSandbox)`;
  `DivisionRewritesDependentsTest.setUp` → `division_stand(division_sandbox)`.

Помощники `_ProjectMutexBase` (первый параметр — стенд `stand`):
- в обоих файлах: `token` → `token`, `new_project` → `new_project`,
  `new_task` → `project_mutex_new_task`, `session` → `session`,
  `foreign_pid` → `foreign_pid`, `seed_lock` → `project_mutex_seed_lock`,
  `live_holder` → `live_holder`, `actions` → `project_mutex_actions`,
  `msg` → `msg`, `project_pairs` → `project_pairs`;
- только в файле замка: `assert_fresh` → `assert_fresh` (помощник с
  утверждением, тест зовёт голым именем, ярлык подслучая — через `ctx`);
- только в файле очереди: `queue_task_ids` → `queue_task_ids`, `enqueue` →
  `project_mutex_enqueue`, `run_wait` → `run_wait`;
  `WaitTextsByProjectTest.wait_texts` → `wait_texts` с последним параметром
  `case: str = ""` и сообщением `… + case`;
- не перенесены, тесты зовут функции модуля: `lock_by_task` → `locks`,
  `clear` → `clear` (тела совпадают после замены `self.` параметром).
- Константы модуля: файл замка — `TS_FORMAT`, `TAKEOVER_ACTION`, `_ALPHABET`,
  `refusal_pattern`; файл очереди — `_ALPHABET`, `refusal_pattern`
  (литералы и тела те же); `OTHER_HOST` не переопределён.
- Префикс `project_mutex_`: одноимённые с иным телом (`new_task`,
  `seed_lock`, `enqueue` 3м-1) и совпадающий с локальной переменной
  (`actions` в `wait_texts`).

Помощники merge_after:
- `MergeAfterDbSandbox.insert` → `merge_after_db_insert`,
  `MergeAfterDbSandbox.set_deps` → `set_deps`;
- `DeclaredSandbox.insert` → `declared_insert`;
- `SpecGateDeclaredRefusalTest.spec_text` → `spec_gate_declared_refusal_spec_text`
  (функция модуля `spec_text` бывшего spec_gate_hint сохраняет имя);
- `DivisionRewritesDependentsTest`: `new_task` → `new_task`, `msg` → `msg`,
  `divide` → `divide`, `stored_deps` → `stored_deps`, `journal` → `journal`;
- `LossRefusalTextTest.task` → `task`;
- `DeclaredPathTest`: `note` → `declared_path_note`, `run_cmd` → `run_cmd`,
  `live_task` → `live_task`, `declared_task` → `declared_task`,
  `refusal` → `refusal`, `no_code_tree` → `no_code_tree` (без параметра
  стенда; передаётся заменой в `mock.patch`).
- Локальная `note` в `test_ac8` и `test_ac9` бывшего spec_gate_hint
  переименована в `failure_note`.
- Совпадения тел: `msg` деления и `declared_path_note` — одно тело, но
  функции разных стендов, не объединены; `clear`/`lock_by_task` — с
  `clear`/`locks` файлов 3м-1 (не перенесены).

## Строки падения и соответствие «до → после»

Строка — мутация, убивший её «до» тест T и место упавшего утверждения в
прежнем файле, функция, в которую перенесён T, и место того же утверждения
в файле модуля по логу прогона «после».

- mutation-001: AcquireByProjectTest::test_ac1_other_project_holder_does_not_block_acquire — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:181 → test_merge_lock_module.py::test_ac1_other_project_holder_does_not_block_acquire — tests/test_merge_lock_module.py:687 (то же утверждение)
- mutation-001: AcquireByProjectTest::test_ac4_dead_holder_of_other_project_is_left_intact — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:262 → test_merge_lock_module.py::test_ac4_dead_holder_of_other_project_is_left_intact — tests/test_merge_lock_module.py:787 (то же утверждение)
- mutation-001: WaitTextsByProjectTest::test_ac10_wait_texts_name_holder_of_waiting_task_project — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:633 → test_merge_queue.py::test_ac10_wait_texts_name_holder_of_waiting_task_project — tests/test_merge_queue.py:862 (то же утверждение)
- mutation-001: QueueByProjectTest::test_ac2_other_project_holder_does_not_delay_wait_for_window — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:490 → test_merge_queue.py::test_ac2_other_project_holder_does_not_delay_wait_for_window — tests/test_merge_queue.py:705 (то же утверждение)
- mutation-002: AcquireByProjectTest::test_ac16_artel_holder_excludes_empty_null_and_missing_target — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:281 → test_merge_lock_module.py::test_ac16_artel_holder_excludes_empty_null_and_missing_target — tests/test_merge_lock_module.py:812 (то же утверждение)
- mutation-002: WaitTextsByProjectTest::test_ac10_wait_texts_name_holder_of_waiting_task_project — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:597 → test_merge_queue.py::test_ac10_wait_texts_name_holder_of_waiting_task_project — tests/test_merge_queue.py:675 (только утверждением подготовки — не доказательство)
- mutation-002: AcquireByProjectTest::test_ac4_dead_holder_of_same_project_is_taken_over — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:236 → test_merge_lock_module.py::test_ac4_dead_holder_of_same_project_is_taken_over — tests/test_merge_lock_module.py:753 (то же утверждение)
- mutation-002: AcquireByProjectTest::test_ac3_live_holder_of_same_project_refuses_with_old_text — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:208 → test_merge_lock_module.py::test_ac3_live_holder_of_same_project_refuses_with_old_text — tests/test_merge_lock_module.py:719 (то же утверждение)
- mutation-002: AcquireByProjectTest::test_ac16_empty_or_null_target_holder_excludes_artel_task — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:302 → test_merge_lock_module.py::test_ac16_empty_or_null_target_holder_excludes_artel_task — tests/test_merge_lock_module.py:837 (то же утверждение)
- mutation-002: WaitTextsByProjectTest::test_ac10_single_project_texts_are_unchanged — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:597 → test_merge_queue.py::test_ac10_single_project_texts_are_unchanged — tests/test_merge_queue.py:675 (только утверждением подготовки — не доказательство)
- mutation-003: WaitTextsByProjectTest::test_ac10_wait_texts_name_holder_of_waiting_task_project — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:633 → test_merge_queue.py::test_ac10_wait_texts_name_holder_of_waiting_task_project — tests/test_merge_queue.py:862 (то же утверждение)
- mutation-003: AcquireByProjectTest::test_ac3_live_holder_of_same_project_refuses_with_old_text — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:209 → test_merge_lock_module.py::test_ac3_live_holder_of_same_project_refuses_with_old_text — tests/test_merge_lock_module.py:720 (то же утверждение)
- mutation-003: WaitTextsByProjectTest::test_ac10_single_project_texts_are_unchanged — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:659 → test_merge_queue.py::test_ac10_single_project_texts_are_unchanged — tests/test_merge_queue.py:892 (то же утверждение)
- mutation-004: AcquireByProjectTest::test_ac4_dead_holder_of_same_project_is_taken_over — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:236 → test_merge_lock_module.py::test_ac4_dead_holder_of_same_project_is_taken_over — tests/test_merge_lock_module.py:753 (то же утверждение)
- mutation-005: AcquireByProjectTest::test_ac4_dead_holder_of_other_project_is_left_intact — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:260 → test_merge_lock_module.py::test_ac4_dead_holder_of_other_project_is_left_intact — tests/test_merge_lock_module.py:783 (то же утверждение)
- mutation-005: StoreMergeLockTest::test_ac11_set_merge_lock_keeps_other_project_row — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:458 → test_merge_lock_module.py::test_ac11_set_merge_lock_keeps_other_project_row — tests/test_merge_lock_module.py:1017 (то же утверждение)
- mutation-005: AcquireByProjectTest::test_ac1_other_project_holder_does_not_block_acquire — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:183 → test_merge_lock_module.py::test_ac1_other_project_holder_does_not_block_acquire — tests/test_merge_lock_module.py:690 (то же утверждение)
- mutation-006: AcquireByProjectTest::test_ac4_dead_holder_of_same_project_is_taken_over — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:234 → test_merge_lock_module.py::test_ac4_dead_holder_of_same_project_is_taken_over — tests/test_merge_lock_module.py:750 (то же утверждение)
- mutation-007: AcquireByProjectTest::test_ac16_artel_holder_excludes_empty_null_and_missing_target — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:281 → test_merge_lock_module.py::test_ac16_artel_holder_excludes_empty_null_and_missing_target — tests/test_merge_lock_module.py:812 (то же утверждение)
- mutation-008: QueueByProjectTest::test_ac8_head_is_earliest_entry_of_own_project — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:515 → test_merge_queue.py::test_ac8_head_is_earliest_entry_of_own_project — tests/test_merge_queue.py:735 (то же утверждение)
- mutation-008: QueueByProjectTest::test_ac9_dead_entry_of_project_does_not_hold_its_head — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:584 → test_merge_queue.py::test_ac9_dead_entry_of_project_does_not_hold_its_head — tests/test_merge_queue.py:817 (то же утверждение)
- mutation-008: QueueByProjectTest::test_ac8_same_project_tasks_enter_in_fifo_order — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:553 → test_merge_queue.py::test_ac8_same_project_tasks_enter_in_fifo_order — tests/test_merge_queue.py:781 (то же утверждение)
- mutation-009: QueueByProjectTest::test_ac8_same_project_tasks_enter_in_fifo_order — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:550 → test_merge_queue.py::test_ac8_same_project_tasks_enter_in_fifo_order — tests/test_merge_queue.py:777 (то же утверждение)
- mutation-010: QueueByProjectTest::test_ac9_dead_entry_of_project_does_not_hold_its_head — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:584 → test_merge_queue.py::test_ac9_dead_entry_of_project_does_not_hold_its_head — tests/test_merge_queue.py:817 (то же утверждение)
- mutation-011: AcquireByProjectTest::test_ac16_empty_or_null_target_holder_excludes_artel_task — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:302 → test_merge_lock_module.py::test_ac16_empty_or_null_target_holder_excludes_artel_task — tests/test_merge_lock_module.py:837 (то же утверждение)
- mutation-012: ReleaseAndHeartbeatTest::test_ac5_release_removes_only_own_process_row — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:333 → test_merge_lock_module.py::test_ac5_release_removes_only_own_process_row — tests/test_merge_lock_module.py:873 (то же утверждение)
- mutation-013: StoreMergeLockTest::test_ac11_set_merge_lock_keeps_other_project_row — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:467 → test_merge_lock_module.py::test_ac11_set_merge_lock_keeps_other_project_row — tests/test_merge_lock_module.py:1028 (то же утверждение)
- mutation-013: ReleaseAndHeartbeatTest::test_ac5_release_removes_only_own_process_row — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:333 → test_merge_lock_module.py::test_ac5_release_removes_only_own_process_row — tests/test_merge_lock_module.py:873 (то же утверждение)
- mutation-014: ReleaseAndHeartbeatTest::test_ac6_touch_heartbeat_renews_only_callers_project_row — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:366 → test_merge_lock_module.py::test_ac6_touch_heartbeat_renews_only_callers_project_row — tests/test_merge_lock_module.py:910 (то же утверждение)
- mutation-014: ReleaseAndHeartbeatTest::test_ac7_touch_heartbeat_does_not_renew_intercepted_row — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:399 → test_merge_lock_module.py::test_ac7_touch_heartbeat_does_not_renew_intercepted_row — tests/test_merge_lock_module.py:952 (то же утверждение)
- mutation-015: ReleaseAndHeartbeatTest::test_ac7_touch_heartbeat_does_not_renew_intercepted_row — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:399 → test_merge_lock_module.py::test_ac7_touch_heartbeat_does_not_renew_intercepted_row — tests/test_merge_lock_module.py:952 (то же утверждение)
- mutation-016: ReleaseAndHeartbeatTest::test_ac7_touch_heartbeat_does_not_renew_intercepted_row — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:399 → test_merge_lock_module.py::test_ac7_touch_heartbeat_does_not_renew_intercepted_row — tests/test_merge_lock_module.py:952 (то же утверждение)
- mutation-017: ReleaseAndHeartbeatTest::test_ac17_touch_heartbeat_without_args_keeps_old_behaviour — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:154 → test_merge_lock_module.py::test_ac17_touch_heartbeat_without_args_keeps_old_behaviour — tests/test_merge_lock_module.py:658 (то же утверждение)
- mutation-018: WaitTextsByProjectTest::test_ac10_wait_texts_name_holder_of_waiting_task_project — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:634 → test_merge_queue.py::test_ac10_wait_texts_name_holder_of_waiting_task_project — tests/test_merge_queue.py:865 (то же утверждение)
- mutation-019: WaitTextsByProjectTest::test_ac10_wait_texts_name_holder_of_waiting_task_project — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:634 → test_merge_queue.py::test_ac10_wait_texts_name_holder_of_waiting_task_project — tests/test_merge_queue.py:865 (то же утверждение)
- mutation-019: WaitTextsByProjectTest::test_ac10_single_project_texts_are_unchanged — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:660 → test_merge_queue.py::test_ac10_single_project_texts_are_unchanged — tests/test_merge_queue.py:893 (то же утверждение)
- mutation-020: TaskIdFormTest::test_form_accepts_ids_prefixes_and_legacy_rejects_rest — tests/test_merge_after.py:32 → test_merge_after_module.py::test_form_accepts_ids_prefixes_and_legacy_rejects_rest — tests/test_merge_after_module.py:361 (то же утверждение)
- mutation-021: TaskIdFormTest::test_form_accepts_ids_prefixes_and_legacy_rejects_rest — tests/test_merge_after.py:32 → test_merge_after_module.py::test_form_accepts_ids_prefixes_and_legacy_rejects_rest — tests/test_merge_after_module.py:361 (то же утверждение)
- mutation-022: TaskIdMatchesTest::test_exact_match_wins_over_longer_ids_with_same_prefix — tests/test_merge_after.py:64 → test_merge_after_module.py::test_exact_match_wins_over_longer_ids_with_same_prefix — tests/test_merge_after_module.py:375 (то же утверждение)
- mutation-023: CheckTest::test_prefix_and_full_id_of_same_task_is_a_repeat — tests/test_merge_after.py:83 → test_merge_after_module.py::test_prefix_and_full_id_of_same_task_is_a_repeat — tests/test_merge_after_module.py:394 (то же утверждение)
- mutation-024: CheckTest::test_done_dependency_is_valid — tests/test_merge_after.py:94 → test_merge_after_module.py::test_done_dependency_is_valid — tests/test_merge_after_module.py:406 (то же утверждение)
- mutation-025: MergeGateMissingDependencyTest::test_dependency_missing_from_db_refuses_with_answer_channel — tests/test_merge_after.py:116 → test_merge_after_module.py::test_dependency_missing_from_db_refuses_with_answer_channel — tests/test_merge_after_module.py:430 (то же утверждение)
- mutation-026: MandateLineTest::test_none_word_mixed_with_ids_refused — tests/test_merge_after.py:134 → test_merge_after_module.py::test_none_word_mixed_with_ids_refused — tests/test_merge_after_module.py:449 (то же утверждение)
- mutation-027: MandateLineTest::test_two_mandate_lines_refused — tests/test_merge_after.py:147 → test_merge_after_module.py::test_two_mandate_lines_refused — tests/test_merge_after_module.py:465 (то же утверждение)
- mutation-028: PlanChannelSameValueTest::test_plan_value_equal_to_db_after_resolution_is_silent — tests/test_merge_after.py:167 → test_merge_after_module.py::test_plan_value_equal_to_db_after_resolution_is_silent — tests/test_merge_after_module.py:486 (то же утверждение)
- mutation-029: ReplaceDividedTest::test_task_not_depending_on_parent_is_untouched — tests/test_merge_after.py:189 → test_merge_after_module.py::test_task_not_depending_on_parent_is_untouched — tests/test_merge_after_module.py:515 (то же утверждение)
- mutation-030: MigrationTest::test_migrate_adds_merge_after_to_old_tasks_table — tests/test_merge_after.py:210 → test_merge_after_module.py::test_migrate_adds_merge_after_to_old_tasks_table — tests/test_merge_after_module.py:538 (то же утверждение)
- mutation-031: DeclaredFromTzTest::test_label_must_start_line_and_word_must_be_whole — tests/test_merge_after_declared.py:41 → test_merge_after_module.py::test_label_must_start_line_and_word_must_be_whole — tests/test_merge_after_module.py:553 (то же утверждение)
- mutation-032: DeclaredFromTzTest::test_label_must_start_line_and_word_must_be_whole — tests/test_merge_after_declared.py:41 → test_merge_after_module.py::test_label_must_start_line_and_word_must_be_whole — tests/test_merge_after_module.py:553 (то же утверждение)
- mutation-033: DeclaredFromTzTest::test_empty_list_is_refused — tests/test_merge_after_declared.py:54 → test_merge_after_module.py::test_empty_list_is_refused — tests/test_merge_after_module.py:569 (то же утверждение)
- mutation-034: DeclaredFromTzTest::test_explicit_target_of_new_task_is_used — tests/test_merge_after_declared.py:65 → test_merge_after_module.py::test_explicit_target_of_new_task_is_used — tests/test_merge_after_module.py:581 (то же утверждение)
- mutation-035: SpecGateDeclaredRefusalTest::test_no_check_after_spec_gate_was_passed — tests/test_merge_after_declared.py:93 → test_merge_after_module.py::test_no_check_after_spec_gate_was_passed — tests/test_merge_after_module.py:608 (то же утверждение)
- mutation-036: SpecGateDeclaredRefusalTest::test_short_prefix_inside_other_id_is_not_justification — tests/test_merge_after_declared.py:118 → test_merge_after_module.py::test_short_prefix_inside_other_id_is_not_justification — tests/test_merge_after_module.py:638 (то же утверждение)
- mutation-037: DivisionRewritesDependentsTest::test_ac1_parent_replaced_by_last_subtask_in_every_dependent — tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py:151 → test_merge_after_module.py::test_ac1_parent_replaced_by_last_subtask_in_every_dependent — tests/test_merge_after_module.py:662 (то же утверждение)
- mutation-037: DivisionRewritesDependentsTest::test_ac2_dependent_journal_names_old_and_new_value — tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py:179 → test_merge_after_module.py::test_ac2_dependent_journal_names_old_and_new_value — tests/test_merge_after_module.py:691 (то же утверждение)
- mutation-038: DivisionRewritesDependentsTest::test_ac2_dependent_journal_names_old_and_new_value — tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py:179 → test_merge_after_module.py::test_ac2_dependent_journal_names_old_and_new_value — tests/test_merge_after_module.py:691 (то же утверждение)
- mutation-038: DivisionRewritesDependentsTest::test_ac1_parent_replaced_by_last_subtask_in_every_dependent — tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py:151 → test_merge_after_module.py::test_ac1_parent_replaced_by_last_subtask_in_every_dependent — tests/test_merge_after_module.py:662 (то же утверждение)
- mutation-039: DivisionRewritesDependentsTest::test_ac1_parent_replaced_by_last_subtask_in_every_dependent — tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py:151 → test_merge_after_module.py::test_ac1_parent_replaced_by_last_subtask_in_every_dependent — tests/test_merge_after_module.py:662 (то же утверждение)
- mutation-039: DivisionRewritesDependentsTest::test_ac2_dependent_journal_names_old_and_new_value — tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py:172 → test_merge_after_module.py::test_ac2_dependent_journal_names_old_and_new_value — tests/test_merge_after_module.py:683 (то же утверждение)
- mutation-039: DivisionRewritesDependentsTest::test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent — tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py:209 → test_merge_after_module.py::test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent — tests/test_merge_after_module.py:723 (то же утверждение)
- mutation-040: DivisionRewritesDependentsTest::test_ac2_dependent_journal_names_old_and_new_value — tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py:179 → test_merge_after_module.py::test_ac2_dependent_journal_names_old_and_new_value — tests/test_merge_after_module.py:691 (то же утверждение)
- mutation-040: DivisionRewritesDependentsTest::test_ac1_parent_replaced_by_last_subtask_in_every_dependent — tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py:151 → test_merge_after_module.py::test_ac1_parent_replaced_by_last_subtask_in_every_dependent — tests/test_merge_after_module.py:662 (то же утверждение)
- mutation-041: DivisionRewritesDependentsTest::test_ac2_dependent_journal_names_old_and_new_value — tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py:172 → test_merge_after_module.py::test_ac2_dependent_journal_names_old_and_new_value — tests/test_merge_after_module.py:683 (то же утверждение)
- mutation-042: DivisionRewritesDependentsTest::test_ac2_dependent_journal_names_old_and_new_value — tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py:172 → test_merge_after_module.py::test_ac2_dependent_journal_names_old_and_new_value — tests/test_merge_after_module.py:683 (то же утверждение)
- mutation-043: DivisionRewritesDependentsTest::test_ac2_dependent_journal_names_old_and_new_value — tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py:172 → test_merge_after_module.py::test_ac2_dependent_journal_names_old_and_new_value — tests/test_merge_after_module.py:683 (то же утверждение)
- mutation-043: DivisionRewritesDependentsTest::test_ac1_parent_replaced_by_last_subtask_in_every_dependent — tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py:151 → test_merge_after_module.py::test_ac1_parent_replaced_by_last_subtask_in_every_dependent — tests/test_merge_after_module.py:662 (то же утверждение)
- mutation-043: DivisionRewritesDependentsTest::test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent — tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py:209 → test_merge_after_module.py::test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent — tests/test_merge_after_module.py:723 (то же утверждение)
- mutation-044: DivisionRewritesDependentsTest::test_ac1_parent_replaced_by_last_subtask_in_every_dependent — tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py:151 → test_merge_after_module.py::test_ac1_parent_replaced_by_last_subtask_in_every_dependent — tests/test_merge_after_module.py:662 (то же утверждение)
- mutation-044: DivisionRewritesDependentsTest::test_ac2_dependent_journal_names_old_and_new_value — tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py:172 → test_merge_after_module.py::test_ac2_dependent_journal_names_old_and_new_value — tests/test_merge_after_module.py:683 (то же утверждение)
- mutation-044: DivisionRewritesDependentsTest::test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent — tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py:209 → test_merge_after_module.py::test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent — tests/test_merge_after_module.py:723 (то же утверждение)
- mutation-045: LossRefusalTextTest::test_ac8_loss_refusal_leads_through_reject_and_escalated_answer — tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py:128 → test_merge_after_module.py::test_ac8_loss_refusal_leads_through_reject_and_escalated_answer — tests/test_merge_after_module.py:775 (то же утверждение)
- mutation-046: LossRefusalTextTest::test_ac8_loss_refusal_leads_through_reject_and_escalated_answer — tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py:129 → test_merge_after_module.py::test_ac8_loss_refusal_leads_through_reject_and_escalated_answer — tests/test_merge_after_module.py:776 (то же утверждение)
- mutation-047: LossRefusalTextTest::test_ac8_loss_refusal_leads_through_reject_and_escalated_answer — tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py:125 → test_merge_after_module.py::test_ac8_loss_refusal_leads_through_reject_and_escalated_answer — tests/test_merge_after_module.py:772 (то же утверждение)
- mutation-048: DeclaredPathTest::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged — tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py:239 → test_merge_after_module.py::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged — tests/test_merge_after_module.py:845 (то же утверждение)
- mutation-049: DeclaredPathTest::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged — tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py:271 → test_merge_after_module.py::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged — tests/test_merge_after_module.py:879 (то же утверждение)
- mutation-050: DeclaredPathTest::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged — tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py:225 → test_merge_after_module.py::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged — tests/test_merge_after_module.py:826 (то же утверждение)
- mutation-051: ReleaseAndHeartbeatTest::test_ac6_touch_heartbeat_renews_only_callers_project_row — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:366 → test_merge_lock_module.py::test_ac6_touch_heartbeat_renews_only_callers_project_row — tests/test_merge_lock_module.py:910 (то же утверждение)
- mutation-051: ReleaseAndHeartbeatTest::test_ac7_touch_heartbeat_does_not_renew_intercepted_row — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:399 → test_merge_lock_module.py::test_ac7_touch_heartbeat_does_not_renew_intercepted_row — tests/test_merge_lock_module.py:952 (то же утверждение)
- mutation-052: QueueByProjectTest::test_ac9_dead_entry_of_project_does_not_hold_its_head — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:584 → test_merge_queue.py::test_ac9_dead_entry_of_project_does_not_hold_its_head — tests/test_merge_queue.py:817 (то же утверждение)

## Зерно

- mutation-001: убийство не зависит от зерна — строка другого проекта в таблице есть в каждом подслучае; оба порядка проектов из `project_pairs` перебираются циклом, имена задач и проектов от зерна в исход не входят.
- mutation-002: убийство не зависит от зерна — держатель того же проекта живой (чужой host, свежий heartbeat) в каждом подслучае, его не находит при любом зерне.
- mutation-003: убийство не зависит от зерна — текст отказа не зависит от случайных id, шаблон `refusal_pattern` экранирует их `re.escape`.
- mutation-004: убийство не зависит от зерна — протухший heartbeat задан `_ts_ago(LEASE_STALE_AFTER_SEC + 60)`, перехват идёт в каждом подслучае при любом зерне.
- mutation-005: убийство не зависит от зерна — строка другого проекта есть в таблице до записи в каждом подслучае; оба порядка проектов из `project_pairs` перебираются циклом, имена задач и проектов от зерна в исход не входят.
- mutation-006: убийство не зависит от зерна — мёртвая строка того же проекта есть в каждом подслучае; состав таблицы сверяется целиком.
- mutation-007: убийство не зависит от зерна — вызывающие с пустым, `NULL` и отсутствующим target заданы литералами, не зерном.
- mutation-008: убийство не зависит от зерна — запись другого проекта стоит раньше по `enqueued_ts` (`_ts_ago` с разницей минут) в каждом подслучае; оба порядка проектов из `project_pairs` перебираются циклом, имена задач и проектов от зерна в исход не входят.
- mutation-009: убийство не зависит от зерна — запись P1 стоит в очереди раньше P2 в каждом подслучае; паузы — подменённые, без часов.
- mutation-010: убийство не зависит от зерна — мёртвая запись P0 (протухший heartbeat либо `_dead_pid` на своём host) — в обоих видах подслучая при любом зерне.
- mutation-011: убийство не зависит от зерна — держатель с пустым target — первый подслучай цикла `("", None)`, задан литералом.
- mutation-012: убийство не зависит от зерна — перемешивание `rng.shuffle` меняет только проекты трёх строк; строка той же сессии с чужим pid есть всегда.
- mutation-013: убийство не зависит от зерна — строки других процессов есть в таблице до снятия в каждом сценарии, от зерна зависят только имена.
- mutation-014: убийство не зависит от зерна — строка B со старым heartbeat есть в каждом подслучае; оба порядка проектов из `project_pairs` перебираются циклом, имена задач и проектов от зерна в исход не входят.
- mutation-015: убийство не зависит от зерна — строка нового держателя того же проекта — в каждом подслучае обоих вариантов, литералы вариантов не от зерна.
- mutation-016: убийство не зависит от зерна — вариант «другая сессия» (та же задача, другая сессия) — литерал цикла, есть при любом зерне.
- mutation-017: убийство не зависит от зерна — одна строка с heartbeat `_ts_ago(600)` в каждом подслучае, свежесть меряется часами, не зерном.
- mutation-018: убийство не зависит от зерна — оба порядка вставки (`p_first` True/False) перебираются циклом; в порядке «Q первой» текст называет Q при любом зерне.
- mutation-019: убийство не зависит от зерна — формат текста не зависит от случайных id.
- mutation-020: убийство не зависит от зерна — `full + "0"` — 27 символов алфавита ULID при любом id из `idgen` (случайна только последовательность символов).
- mutation-021: убийство не зависит от зерна — `full.lower()` длиной 26 проходит одну проверку длины при любом id из `idgen`.
- mutation-022: убийство не зависит от зерна — id `T1`/`T10` — литералы, ULID не участвуют.
- mutation-023: убийство не зависит от зерна — `dep[:-1]` (25 символов ULID из `idgen`) — однозначный префикс `dep` при любом зерне, текст элемента всегда иной.
- mutation-024: убийство не зависит от зерна — состояние `done` — литерал, ULID из `idgen` на исход не влияет.
- mutation-025: убийство не зависит от зерна — ULID-призрак из `idgen` в БД нет при любом значении.
- mutation-026: убийство не зависит от зерна — зависимость — живая задача с ULID из `idgen`, проверка `check` проходит при любом id.
- mutation-027: убийство не зависит от зерна — две строки мандата — литерал текста, id из `idgen` на число строк не влияют.
- mutation-028: убийство не зависит от зерна — `dep[:-2]` — однозначный префикс ULID из `idgen`, всегда отличный от `dep` текстом.
- mutation-029: убийство не зависит от зерна — задача песочницы переписывается при любых ULID из `idgen`.
- mutation-030: убийство не зависит от зерна — случайных входов у теста нет; зерно не участвует.
- mutation-031: убийство не зависит от зерна — строка с отступом — первый подслучай, задана литералом; ULID из `idgen` годен при любом значении.
- mutation-032: убийство не зависит от зерна — «послезавтра» — литерал подслучая; исход не зависит от ULID из `idgen`.
- mutation-033: убийство не зависит от зерна — текст ТЗ — литерал; ULID из `idgen` не участвует в исходе.
- mutation-034: убийство не зависит от зерна — target `proekt` — литерал; ULID из `idgen` на сверку target не влияет.
- mutation-035: убийство не зависит от зерна — запись журнала `state -> tests_writing` — литерал; ULID из `idgen` не влияет.
- mutation-036: убийство не зависит от зерна — префикс строится от первого различия двух ULID из `idgen` и стоит в разделе как `X<префикс>Y` при любых значениях.
- mutation-037: убийство не зависит от зерна — частей деления от зерна 2–4 — первая подзадача никогда не последняя.
- mutation-038: убийство не зависит от зерна — родитель стоит в значении каждой зависящей задачи при любой позиции от зерна.
- mutation-039: убийство не зависит от зерна — зависящих задач от зерна 2–3 — хотя бы одна остаётся с родителем.
- mutation-040: убийство не зависит от зерна — у каждой зависящей задачи от зерна 1–2 соседа.
- mutation-041: убийство не зависит от зерна — записи нет в журнале каждой зависящей задачи при любом зерне.
- mutation-042: убийство не зависит от зерна — журнал зависящей задачи пуст по этому действию при любом зерне.
- mutation-043: убийство не зависит от зерна — родитель стоит в `merge_after` каждой зависящей задачи при любом зерне.
- mutation-044: убийство не зависит от зерна — колонка родителя пуста, зависящие задачи не переписываются при любом зерне.
- mutation-045: убийство не зависит от зерна — потерянная зависимость есть в каждой из трёх итераций (`kept` урезается при совпадении), «reject» нет при любом зерне.
- mutation-046: убийство не зависит от зерна — порядок слов в тексте не зависит от id и ветки «поле есть/нет».
- mutation-047: убийство не зависит от зерна — начало текста не зависит от id и ветки поля.
- mutation-048: убийство не зависит от зерна — добавка сверх заявленного есть всегда; ожидаемый текст собран из её id.
- mutation-049: убийство не зависит от зерна — подслучай `killed` — литерал цикла, от зерна не зависит.
- mutation-050: убийство не зависит от зерна — `kept` от зерна всегда короче заявленных (`randint(0, len-1)`), колонка без смены ему не равна.
- mutation-051: убийство не зависит от зерна — порядок «B первой» (`a_first=False`) перебирается циклом при любом зерне.
- mutation-052: убийство не зависит от зерна — мёртвая запись P0 своего проекта — в обоих видах подслучая при любом зерне.

## Находки

- Заявка `ReleaseAndHeartbeatTest::test_ac17_touch_heartbeat_without_args_keeps_old_behaviour`,
  альтернатива «пустая таблица роняет вызов исключением»: тест ловит её
  только исключением без падения утверждения (утверждение `assertEqual(…, {})`
  после вызова не исполнится), по требованию 4 это не доказательство;
  мутации, убиваемой этим путём утверждением, нет. Тест не удалён, зерно не
  фиксировано; первую альтернативу заявки держит патч из раздела выше.

## Удалённые дубли

Нет: все 37 тестов пяти файлов перенесены функциями с прежними именами.

## Мутации до

Команда: `mutation-run 01M5R0AFX9Z1GA1DG5XV73JRTE --ref base --tests
tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py,tests/test_merge_after.py,tests/test_merge_after_declared.py,tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py,tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py
--copy-table --wait-lock 4 --patches <часть>`; вывод частей дословно.

Часть №1:

```
# mutation-run №1 задачи 01M5R0AFX9Z1GA1DG5XV73JRTE
# источник патчей: каталог на диске
# ревизия прогона: base 72d52fd367828949767e234ecbe9b0cc79851084
# тесты: tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py, tests/test_merge_after.py, tests/test_merge_after_declared.py, tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py, tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py
# рабочих процессов: auto
# патч 1 mutation-001.diff sha256 7fa89af27aca7ac24d9c470f508310b1e268ca6f9f3a6ca1367aac85b9ddd58a
# патч 2 mutation-002.diff sha256 648fb594a125ff10a1e48510d3d5d634a3f15808156739a5acb2101a0c9fdad2
# патч 3 mutation-003.diff sha256 1b306c96f6c2565e710d2a25160294e172bda908b0d1b7acf80661c41a4eb38e
# патч 4 mutation-004.diff sha256 7c0915f3b97184c259381004bf0a7a19d29ef2f8b6ea4553f5feac290d1b89a7
# патч 5 mutation-005.diff sha256 61aa8415ed970faf8ba3b75cf048f5434f97ed1bb108f886db22fbcfb1ade011
номер	исход	узлы
1	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::AcquireByProjectTest::test_ac1_other_project_holder_does_not_block_acquire,tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::AcquireByProjectTest::test_ac4_dead_holder_of_other_project_is_left_intact,tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::WaitTextsByProjectTest::test_ac10_wait_texts_name_holder_of_waiting_task_project,tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::QueueByProjectTest::test_ac2_other_project_holder_does_not_delay_wait_for_window
2	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::AcquireByProjectTest::test_ac16_artel_holder_excludes_empty_null_and_missing_target,tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::WaitTextsByProjectTest::test_ac10_wait_texts_name_holder_of_waiting_task_project,tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::AcquireByProjectTest::test_ac4_dead_holder_of_same_project_is_taken_over,tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::AcquireByProjectTest::test_ac3_live_holder_of_same_project_refuses_with_old_text,tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::AcquireByProjectTest::test_ac16_empty_or_null_target_holder_excludes_artel_task,tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::WaitTextsByProjectTest::test_ac10_single_project_texts_are_unchanged
3	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::WaitTextsByProjectTest::test_ac10_wait_texts_name_holder_of_waiting_task_project,tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::AcquireByProjectTest::test_ac3_live_holder_of_same_project_refuses_with_old_text,tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::WaitTextsByProjectTest::test_ac10_single_project_texts_are_unchanged
4	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::AcquireByProjectTest::test_ac4_dead_holder_of_same_project_is_taken_over
5	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::AcquireByProjectTest::test_ac4_dead_holder_of_other_project_is_left_intact,tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::StoreMergeLockTest::test_ac11_set_merge_lock_keeps_other_project_row,tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::AcquireByProjectTest::test_ac1_other_project_holder_does_not_block_acquire
```

Часть №2:

```
# mutation-run №2 задачи 01M5R0AFX9Z1GA1DG5XV73JRTE
# источник патчей: каталог на диске
# ревизия прогона: base 72d52fd367828949767e234ecbe9b0cc79851084
# тесты: tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py, tests/test_merge_after.py, tests/test_merge_after_declared.py, tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py, tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py
# рабочих процессов: auto
# патч 6 mutation-006.diff sha256 d50abc5da6f4bdda7d4fe30e42ba04fcadf132b8e391b256c71eb821f3139962
# патч 7 mutation-007.diff sha256 3e9743aa251a9800fd62350283439eb0c8eb156d1dc76e71179f92392e9fc6e7
# патч 8 mutation-008.diff sha256 c8dfaee251a4de5d737807b1f1f2f6d4805f497144d197747003631f4ce2ac95
# патч 9 mutation-009.diff sha256 a0e61e6c8b7c4990e4d8a30958813f836e1cc6aa325dcd7e7a306c7e9d8c549b
# патч 10 mutation-010.diff sha256 c08cac66cdfa1e715e492800ce6930f40052cdb5d6ea40d9780c1d382767d19e
номер	исход	узлы
6	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::AcquireByProjectTest::test_ac4_dead_holder_of_same_project_is_taken_over
7	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::AcquireByProjectTest::test_ac16_artel_holder_excludes_empty_null_and_missing_target
8	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::QueueByProjectTest::test_ac8_head_is_earliest_entry_of_own_project,tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::QueueByProjectTest::test_ac9_dead_entry_of_project_does_not_hold_its_head,tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::QueueByProjectTest::test_ac8_same_project_tasks_enter_in_fifo_order
9	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::QueueByProjectTest::test_ac8_same_project_tasks_enter_in_fifo_order
10	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::QueueByProjectTest::test_ac9_dead_entry_of_project_does_not_hold_its_head
```

Часть №3:

```
# mutation-run №3 задачи 01M5R0AFX9Z1GA1DG5XV73JRTE
# источник патчей: каталог на диске
# ревизия прогона: base 72d52fd367828949767e234ecbe9b0cc79851084
# тесты: tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py, tests/test_merge_after.py, tests/test_merge_after_declared.py, tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py, tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py
# рабочих процессов: auto
# патч 11 mutation-011.diff sha256 839b89aad00866e9df27444731c1bf8a21fdc8f05aa40cde909300aa910c224d
# патч 12 mutation-012.diff sha256 81bae703be72e3ccb73d28ad49acdf4e3287d4eae648463bcd7a9736a53e05fc
# патч 13 mutation-013.diff sha256 53c08a882b76cc902aa68938877f96c1d725f432902c56d778d4fd8aa97dad05
# патч 14 mutation-014.diff sha256 b85c786ad896080d8a6c1e6bc57cf129882f35b238fbc62f35af067bb8de9f57
# патч 15 mutation-015.diff sha256 abc49e25e285d683400985b745653739366fca8e9aa26c8c31b89c9c7059f1c8
# патч 16 mutation-016.diff sha256 d5157f8f37cd6b043e9f06f406e9dffaedb6808cf2adc2c32eb8d6ed25ff0294
# патч 17 mutation-017.diff sha256 059b0bc8f7b5ee37ff8aa781c05acca3638738f6b7c91ecfd2ecc8d2a5a26865
# патч 18 mutation-018.diff sha256 09937644ceb3a19b25a41bd0c049b36a2910524d4f7818449e7a4581ed84e92b
# патч 19 mutation-019.diff sha256 23cdfa4a71dd217f8270909c0964d235f45a961d7f9c4bf40c0890bc1c47f06a
# патч 20 mutation-020.diff sha256 f888b4e7802d94749ebe0e68e723abb35699efc3964147afa7b0725182e97648
# патч 21 mutation-021.diff sha256 58e1229508beb7f9dac14f776847fcaaa71f59ba6b10130dddda5c34e445cf93
# патч 22 mutation-022.diff sha256 8dacbdbd68bc9e1ca5217a4e5db2ea8a0612c280b599641d331d44c03ae8ac50
# патч 23 mutation-023.diff sha256 0b48bf6a4a52ea2d2e15b0adeb0f41099c5dccf1c45feb763cbdba246531ab7f
# патч 24 mutation-024.diff sha256 21fd7eebc4681126e1f138fca9aed4a8e8f6082d3c5cd9602a5ba20da062268e
# патч 25 mutation-025.diff sha256 afb983b3346cd5166ffccb1c7015cc4c93a283f93f48b256ac5a7d206356437f
# патч 26 mutation-026.diff sha256 43181b4130747c960e8bb65383c59df42fb699ea1521a883cb69d9c103195e3c
# патч 27 mutation-027.diff sha256 fa5abd36803024e399bc2d2b44736bd4515a4c718beb5f4dc626ddae1da1da40
# патч 28 mutation-028.diff sha256 67f174f19f3ab66827efb59e149eab1daa6ac7fccbad8dab2bf55be93e3e6823
# патч 29 mutation-029.diff sha256 cae629840ecfcff996f379f487cfbb46bd0004385c2a881b5ec3ad39450eaf5c
# патч 30 mutation-030.diff sha256 2f833199e615837560ca79c9cfd04861deafa08dcb85d70ecf0022f68920ea9f
номер	исход	узлы
11	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::AcquireByProjectTest::test_ac16_empty_or_null_target_holder_excludes_artel_task
12	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::ReleaseAndHeartbeatTest::test_ac5_release_removes_only_own_process_row
13	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::StoreMergeLockTest::test_ac11_set_merge_lock_keeps_other_project_row,tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::ReleaseAndHeartbeatTest::test_ac5_release_removes_only_own_process_row
14	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::ReleaseAndHeartbeatTest::test_ac6_touch_heartbeat_renews_only_callers_project_row,tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::ReleaseAndHeartbeatTest::test_ac7_touch_heartbeat_does_not_renew_intercepted_row
15	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::ReleaseAndHeartbeatTest::test_ac7_touch_heartbeat_does_not_renew_intercepted_row
16	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::ReleaseAndHeartbeatTest::test_ac7_touch_heartbeat_does_not_renew_intercepted_row
17	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::ReleaseAndHeartbeatTest::test_ac17_touch_heartbeat_without_args_keeps_old_behaviour
18	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::WaitTextsByProjectTest::test_ac10_wait_texts_name_holder_of_waiting_task_project
19	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::WaitTextsByProjectTest::test_ac10_wait_texts_name_holder_of_waiting_task_project,tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::WaitTextsByProjectTest::test_ac10_single_project_texts_are_unchanged
20	убита	tests/test_merge_after.py::TaskIdFormTest::test_form_accepts_ids_prefixes_and_legacy_rejects_rest
21	убита	tests/test_merge_after.py::TaskIdFormTest::test_form_accepts_ids_prefixes_and_legacy_rejects_rest
22	убита	tests/test_merge_after.py::TaskIdMatchesTest::test_exact_match_wins_over_longer_ids_with_same_prefix
23	убита	tests/test_merge_after.py::CheckTest::test_prefix_and_full_id_of_same_task_is_a_repeat
24	убита	tests/test_merge_after.py::CheckTest::test_done_dependency_is_valid
25	убита	tests/test_merge_after.py::MergeGateMissingDependencyTest::test_dependency_missing_from_db_refuses_with_answer_channel
26	убита	tests/test_merge_after.py::MandateLineTest::test_none_word_mixed_with_ids_refused
27	убита	tests/test_merge_after.py::MandateLineTest::test_two_mandate_lines_refused
28	убита	tests/test_merge_after.py::PlanChannelSameValueTest::test_plan_value_equal_to_db_after_resolution_is_silent
29	убита	tests/test_merge_after.py::ReplaceDividedTest::test_task_not_depending_on_parent_is_untouched
30	убита	tests/test_merge_after.py::MigrationTest::test_migrate_adds_merge_after_to_old_tasks_table
```

Часть №4:

```
# mutation-run №4 задачи 01M5R0AFX9Z1GA1DG5XV73JRTE
# источник патчей: каталог на диске
# ревизия прогона: base 72d52fd367828949767e234ecbe9b0cc79851084
# тесты: tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py, tests/test_merge_after.py, tests/test_merge_after_declared.py, tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py, tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py
# рабочих процессов: auto
# патч 31 mutation-031.diff sha256 ce25ea82e915eee5dde41d4c4d10bb3107ef53c87ee5c74951203f704b33685c
# патч 32 mutation-032.diff sha256 75df665fa23dfbaaa291ed878da42694c6d890e961df841cb505124f9fd1ff6e
# патч 33 mutation-033.diff sha256 7dbc52f11967eb4c5dec460bd8f4c19ee4792f1f02fb453b9b1b9e162a47b83d
# патч 34 mutation-034.diff sha256 ec7955764094df855255637c72306777285c33a971d200345def2a623f0a7e75
# патч 35 mutation-035.diff sha256 b121b8cf4e96ceee4b6b585a3bbd16e5238d4292834830511a815d22551a50bb
# патч 36 mutation-036.diff sha256 111dde2bf745f83f9abd90a2d316c8553efdb71b0f9fc492ff0ee074bc4cd9ca
# патч 37 mutation-037.diff sha256 2a093a730d605b314009543a1de144803cb2acedda812bceb8666cdef2a3f720
# патч 38 mutation-038.diff sha256 c6b2d41e2c2ebbcddbefda61b54f89f8cbc46b7ea0fb58b8e8d83f21c8874c66
# патч 39 mutation-039.diff sha256 e89fe75ec12af7aaaf0d522f891df9286dc134166b6d9082579f9dc8c7c79077
# патч 40 mutation-040.diff sha256 64ecbdc8fb03c81d06106c94f039b86ed2a54034198196f076b24f0b9ebfe720
# патч 41 mutation-041.diff sha256 8494b7a94ac4916298041e700ea848096b8fceb860249b23d24349e35a62fcba
# патч 42 mutation-042.diff sha256 3063630fb1d7e32fa304c808335c819f8c497fb682e165e43bbaad937f3c174b
# патч 43 mutation-043.diff sha256 4183702bd53468f5e982385aaf68ccee9d26feee6125a4f901ad2966ca923608
# патч 44 mutation-044.diff sha256 af9729e4dffa8a0c5ea002e01b9451ffc363633a0979204a221eccece73896c0
# патч 45 mutation-045.diff sha256 199e6dca92a847e833c004753ac674648b10817f6bd3746dc169a5955ee23204
# патч 46 mutation-046.diff sha256 790201e394566ef8ffbc1462a86475d49241ec94f616c9176a33770aa276b2b7
# патч 47 mutation-047.diff sha256 72918206748fd3fb7f78e1d8d2042283fc5fdb9702d194aa432504bcc51042e8
# патч 48 mutation-048.diff sha256 7829f5254b0096467a73af6369db5804d736b6a89a170832640ef67cb0a28ad1
# патч 49 mutation-049.diff sha256 07c6fcf1d064889f7a3fa121a38068489a81ac84d9774bf6002cb7f84dbb58a8
# патч 50 mutation-050.diff sha256 a191413d034276304d67c5de15b77bada9d0aa903d339e403d6263faf21f4d12
номер	исход	узлы
31	убита	tests/test_merge_after_declared.py::DeclaredFromTzTest::test_label_must_start_line_and_word_must_be_whole
32	убита	tests/test_merge_after_declared.py::DeclaredFromTzTest::test_label_must_start_line_and_word_must_be_whole
33	убита	tests/test_merge_after_declared.py::DeclaredFromTzTest::test_empty_list_is_refused
34	убита	tests/test_merge_after_declared.py::DeclaredFromTzTest::test_explicit_target_of_new_task_is_used
35	убита	tests/test_merge_after_declared.py::SpecGateDeclaredRefusalTest::test_no_check_after_spec_gate_was_passed
36	убита	tests/test_merge_after_declared.py::SpecGateDeclaredRefusalTest::test_short_prefix_inside_other_id_is_not_justification
37	убита	tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py::DivisionRewritesDependentsTest::test_ac1_parent_replaced_by_last_subtask_in_every_dependent,tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py::DivisionRewritesDependentsTest::test_ac2_dependent_journal_names_old_and_new_value
38	убита	tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py::DivisionRewritesDependentsTest::test_ac2_dependent_journal_names_old_and_new_value,tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py::DivisionRewritesDependentsTest::test_ac1_parent_replaced_by_last_subtask_in_every_dependent
39	убита	tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py::DivisionRewritesDependentsTest::test_ac1_parent_replaced_by_last_subtask_in_every_dependent,tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py::DivisionRewritesDependentsTest::test_ac2_dependent_journal_names_old_and_new_value,tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py::DivisionRewritesDependentsTest::test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent
40	убита	tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py::DivisionRewritesDependentsTest::test_ac2_dependent_journal_names_old_and_new_value,tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py::DivisionRewritesDependentsTest::test_ac1_parent_replaced_by_last_subtask_in_every_dependent
41	убита	tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py::DivisionRewritesDependentsTest::test_ac2_dependent_journal_names_old_and_new_value
42	убита	tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py::DivisionRewritesDependentsTest::test_ac2_dependent_journal_names_old_and_new_value
43	убита	tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py::DivisionRewritesDependentsTest::test_ac2_dependent_journal_names_old_and_new_value,tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py::DivisionRewritesDependentsTest::test_ac1_parent_replaced_by_last_subtask_in_every_dependent,tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py::DivisionRewritesDependentsTest::test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent
44	убита	tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py::DivisionRewritesDependentsTest::test_ac1_parent_replaced_by_last_subtask_in_every_dependent,tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py::DivisionRewritesDependentsTest::test_ac2_dependent_journal_names_old_and_new_value,tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py::DivisionRewritesDependentsTest::test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent
45	убита	tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py::LossRefusalTextTest::test_ac8_loss_refusal_leads_through_reject_and_escalated_answer
46	убита	tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py::LossRefusalTextTest::test_ac8_loss_refusal_leads_through_reject_and_escalated_answer
47	убита	tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py::LossRefusalTextTest::test_ac8_loss_refusal_leads_through_reject_and_escalated_answer
48	убита	tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py::DeclaredPathTest::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged
49	убита	tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py::DeclaredPathTest::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged
50	убита	tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py::DeclaredPathTest::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged
```

Часть №5:

```
# mutation-run №5 задачи 01M5R0AFX9Z1GA1DG5XV73JRTE
# источник патчей: каталог на диске
# ревизия прогона: base 72d52fd367828949767e234ecbe9b0cc79851084
# тесты: tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py, tests/test_merge_after.py, tests/test_merge_after_declared.py, tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py, tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py
# рабочих процессов: auto
# патч 51 mutation-051.diff sha256 8ad1dfbd5b701eebd46ef5dc364ef34863d516b39b9411f5c088f45889652ed9
# патч 52 mutation-052.diff sha256 0e124d5d547bbce9e93a903e9d0f5fe42814494ee2f5e1834ba0ab75bbabdc57
номер	исход	узлы
51	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::ReleaseAndHeartbeatTest::test_ac6_touch_heartbeat_renews_only_callers_project_row,tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::ReleaseAndHeartbeatTest::test_ac7_touch_heartbeat_does_not_renew_intercepted_row
52	убита	tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py::QueueByProjectTest::test_ac9_dead_entry_of_project_does_not_hold_its_head
```


## Мутации после

Команда: `mutation-run 01M5R0AFX9Z1GA1DG5XV73JRTE --ref worktree --tests
tests/test_merge_lock_module.py,tests/test_merge_queue.py,tests/test_merge_after_module.py
--copy-table --wait-lock 4 --patches <часть>` — те же диапазоны и то же
`--workers` (умолчание), что «до»; вывод частей дословно.

Перед частью №6: `git status --porcelain -- orchestrator/` — вывод пуст

```
# mutation-run №6 задачи 01M5R0AFX9Z1GA1DG5XV73JRTE
# источник патчей: каталог на диске
# ревизия прогона: worktree a6eb9bc46a354a0eeaa06db37a2463685d80dd68
# тесты: tests/test_merge_lock_module.py, tests/test_merge_queue.py, tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 1 mutation-001.diff sha256 7fa89af27aca7ac24d9c470f508310b1e268ca6f9f3a6ca1367aac85b9ddd58a
# патч 2 mutation-002.diff sha256 648fb594a125ff10a1e48510d3d5d634a3f15808156739a5acb2101a0c9fdad2
# патч 3 mutation-003.diff sha256 1b306c96f6c2565e710d2a25160294e172bda908b0d1b7acf80661c41a4eb38e
# патч 4 mutation-004.diff sha256 7c0915f3b97184c259381004bf0a7a19d29ef2f8b6ea4553f5feac290d1b89a7
# патч 5 mutation-005.diff sha256 61aa8415ed970faf8ba3b75cf048f5434f97ed1bb108f886db22fbcfb1ade011
номер	исход	узлы
1	убита	tests/test_merge_lock_module.py::test_ac4_dead_holder_of_other_project_is_left_intact,tests/test_merge_lock_module.py::test_ac1_other_project_holder_does_not_block_acquire,tests/test_merge_queue.py::test_texts_name_own_project_holder_in_every_insertion_order,tests/test_merge_queue.py::test_earlier_entry_of_other_project_does_not_delay_entry,tests/test_merge_queue.py::test_ac2_other_project_holder_does_not_delay_wait_for_window,tests/test_merge_queue.py::test_ac10_wait_texts_name_holder_of_waiting_task_project
2	убита	tests/test_merge_lock_module.py::test_ac3_live_holder_of_same_project_refuses_with_old_text,tests/test_merge_lock_module.py::test_dead_process_of_own_session_is_intercepted_and_journalled,tests/test_merge_lock_module.py::test_refusal_text_for_own_session_equals_foreign_session_text,tests/test_merge_lock_module.py::test_foreign_fresh_lock_refuses_and_names_holder_and_task,tests/test_merge_lock_module.py::test_ac16_empty_or_null_target_holder_excludes_artel_task,tests/test_merge_lock_module.py::test_live_other_process_of_same_session_is_refused_with_holder_pid,tests/test_merge_lock_module.py::test_ac16_artel_holder_excludes_empty_null_and_missing_target,tests/test_merge_lock_module.py::test_ac4_dead_holder_of_same_project_is_taken_over,tests/test_merge_lock_module.py::test_concurrent_acquire_on_free_lock_exactly_one_wins,tests/test_merge_lock_module.py::test_refusal_exits_without_running_the_body,tests/test_merge_lock_module.py::test_foreign_dead_pid_on_a_different_host_is_not_taken_over,tests/test_merge_lock_module.py::test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled,tests/test_merge_queue.py::test_queue_entry_journal_names_the_holder_pid,tests/test_merge_queue.py::test_texts_name_own_project_holder_in_every_insertion_order,tests/test_merge_queue.py::test_ceiling_expiry_dequeues_and_exits_without_touching_state,tests/test_merge_queue.py::test_ac10_wait_texts_name_holder_of_waiting_task_project,tests/test_merge_queue.py::test_ac10_single_project_texts_are_unchanged
3	убита	tests/test_merge_lock_module.py::test_ac3_live_holder_of_same_project_refuses_with_old_text,tests/test_merge_queue.py::test_ac10_wait_texts_name_holder_of_waiting_task_project,tests/test_merge_queue.py::test_ac10_single_project_texts_are_unchanged
4	убита	tests/test_merge_lock_module.py::test_dead_process_of_own_session_is_intercepted_and_journalled,tests/test_merge_lock_module.py::test_ac4_dead_holder_of_same_project_is_taken_over,tests/test_merge_lock_module.py::test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled
5	убита	tests/test_merge_lock_module.py::test_ac4_dead_holder_of_other_project_is_left_intact,tests/test_merge_lock_module.py::test_ac1_other_project_holder_does_not_block_acquire,tests/test_merge_lock_module.py::test_ac11_set_merge_lock_keeps_other_project_row
```

Перед частью №7: `git status --porcelain -- orchestrator/` — вывод пуст

```
# mutation-run №7 задачи 01M5R0AFX9Z1GA1DG5XV73JRTE
# источник патчей: каталог на диске
# ревизия прогона: worktree a6eb9bc46a354a0eeaa06db37a2463685d80dd68
# тесты: tests/test_merge_lock_module.py, tests/test_merge_queue.py, tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 6 mutation-006.diff sha256 d50abc5da6f4bdda7d4fe30e42ba04fcadf132b8e391b256c71eb821f3139962
# патч 7 mutation-007.diff sha256 3e9743aa251a9800fd62350283439eb0c8eb156d1dc76e71179f92392e9fc6e7
# патч 8 mutation-008.diff sha256 c8dfaee251a4de5d737807b1f1f2f6d4805f497144d197747003631f4ce2ac95
# патч 9 mutation-009.diff sha256 a0e61e6c8b7c4990e4d8a30958813f836e1cc6aa325dcd7e7a306c7e9d8c549b
# патч 10 mutation-010.diff sha256 c08cac66cdfa1e715e492800ce6930f40052cdb5d6ea40d9780c1d382767d19e
номер	исход	узлы
6	убита	tests/test_merge_lock_module.py::test_dead_process_of_own_session_is_intercepted_and_journalled,tests/test_merge_lock_module.py::test_foreign_dead_pid_on_local_host_is_taken_over_despite_fresh_heartbeat,tests/test_merge_lock_module.py::test_refusal_text_for_own_session_equals_foreign_session_text,tests/test_merge_lock_module.py::test_ac4_dead_holder_of_same_project_is_taken_over,tests/test_merge_lock_module.py::test_own_process_re_enters_and_refreshes_the_row,tests/test_merge_lock_module.py::test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled
7	убита	tests/test_merge_lock_module.py::test_ac16_artel_holder_excludes_empty_null_and_missing_target
8	убита	tests/test_merge_queue.py::test_earlier_entry_of_other_project_does_not_delay_entry,tests/test_merge_queue.py::test_ac8_head_is_earliest_entry_of_own_project,tests/test_merge_queue.py::test_ac9_dead_entry_of_project_does_not_hold_its_head,tests/test_merge_queue.py::test_ac8_same_project_tasks_enter_in_fifo_order
9	убита	tests/test_merge_queue.py::test_non_head_process_of_the_same_session_does_not_take_the_window,tests/test_merge_queue.py::test_ac8_same_project_tasks_enter_in_fifo_order
10	убита	tests/test_merge_queue.py::test_ac9_dead_entry_of_project_does_not_hold_its_head
```

Перед частью №8: `git status --porcelain -- orchestrator/` — вывод пуст

```
# mutation-run №8 задачи 01M5R0AFX9Z1GA1DG5XV73JRTE
# источник патчей: каталог на диске
# ревизия прогона: worktree a6eb9bc46a354a0eeaa06db37a2463685d80dd68
# тесты: tests/test_merge_lock_module.py, tests/test_merge_queue.py, tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 11 mutation-011.diff sha256 839b89aad00866e9df27444731c1bf8a21fdc8f05aa40cde909300aa910c224d
# патч 12 mutation-012.diff sha256 81bae703be72e3ccb73d28ad49acdf4e3287d4eae648463bcd7a9736a53e05fc
# патч 13 mutation-013.diff sha256 53c08a882b76cc902aa68938877f96c1d725f432902c56d778d4fd8aa97dad05
# патч 14 mutation-014.diff sha256 b85c786ad896080d8a6c1e6bc57cf129882f35b238fbc62f35af067bb8de9f57
# патч 15 mutation-015.diff sha256 abc49e25e285d683400985b745653739366fca8e9aa26c8c31b89c9c7059f1c8
# патч 16 mutation-016.diff sha256 d5157f8f37cd6b043e9f06f406e9dffaedb6808cf2adc2c32eb8d6ed25ff0294
# патч 17 mutation-017.diff sha256 059b0bc8f7b5ee37ff8aa781c05acca3638738f6b7c91ecfd2ecc8d2a5a26865
# патч 18 mutation-018.diff sha256 09937644ceb3a19b25a41bd0c049b36a2910524d4f7818449e7a4581ed84e92b
# патч 19 mutation-019.diff sha256 23cdfa4a71dd217f8270909c0964d235f45a961d7f9c4bf40c0890bc1c47f06a
# патч 20 mutation-020.diff sha256 f888b4e7802d94749ebe0e68e723abb35699efc3964147afa7b0725182e97648
# патч 21 mutation-021.diff sha256 58e1229508beb7f9dac14f776847fcaaa71f59ba6b10130dddda5c34e445cf93
# патч 22 mutation-022.diff sha256 8dacbdbd68bc9e1ca5217a4e5db2ea8a0612c280b599641d331d44c03ae8ac50
# патч 23 mutation-023.diff sha256 0b48bf6a4a52ea2d2e15b0adeb0f41099c5dccf1c45feb763cbdba246531ab7f
# патч 24 mutation-024.diff sha256 21fd7eebc4681126e1f138fca9aed4a8e8f6082d3c5cd9602a5ba20da062268e
# патч 25 mutation-025.diff sha256 afb983b3346cd5166ffccb1c7015cc4c93a283f93f48b256ac5a7d206356437f
# патч 26 mutation-026.diff sha256 43181b4130747c960e8bb65383c59df42fb699ea1521a883cb69d9c103195e3c
# патч 27 mutation-027.diff sha256 fa5abd36803024e399bc2d2b44736bd4515a4c718beb5f4dc626ddae1da1da40
# патч 28 mutation-028.diff sha256 67f174f19f3ab66827efb59e149eab1daa6ac7fccbad8dab2bf55be93e3e6823
# патч 29 mutation-029.diff sha256 cae629840ecfcff996f379f487cfbb46bd0004385c2a881b5ec3ad39450eaf5c
# патч 30 mutation-030.diff sha256 2f833199e615837560ca79c9cfd04861deafa08dcb85d70ecf0022f68920ea9f
номер	исход	узлы
11	убита	tests/test_merge_lock_module.py::test_ac16_empty_or_null_target_holder_excludes_artel_task
12	убита	tests/test_merge_lock_module.py::test_ac5_release_removes_only_own_process_row,tests/test_merge_lock_module.py::test_store_release_merge_lock_requires_both_session_and_pid,tests/test_merge_lock_module.py::test_release_from_non_holder_process_keeps_the_mutex
13	убита	tests/test_merge_lock_module.py::test_release_removes_only_the_matching_session,tests/test_merge_lock_module.py::test_ac5_release_removes_only_own_process_row,tests/test_merge_lock_module.py::test_store_release_merge_lock_requires_both_session_and_pid,tests/test_merge_lock_module.py::test_release_from_non_holder_process_keeps_the_mutex,tests/test_merge_lock_module.py::test_ac11_set_merge_lock_keeps_other_project_row
14	убита	tests/test_merge_lock_module.py::test_ac6_touch_heartbeat_renews_only_callers_project_row,tests/test_merge_lock_module.py::test_ac7_touch_heartbeat_does_not_renew_intercepted_row
15	убита	tests/test_merge_lock_module.py::test_ac7_touch_heartbeat_does_not_renew_intercepted_row
16	убита	tests/test_merge_lock_module.py::test_ac7_touch_heartbeat_does_not_renew_intercepted_row
17	убита	tests/test_merge_lock_module.py::test_ac17_touch_heartbeat_without_args_keeps_old_behaviour
18	убита	tests/test_merge_queue.py::test_texts_name_own_project_holder_in_every_insertion_order,tests/test_merge_queue.py::test_ac10_wait_texts_name_holder_of_waiting_task_project
19	убита	tests/test_merge_queue.py::test_label_names_task_and_pid_of_the_holder,tests/test_merge_queue.py::test_queued_reports_minutes_waited_and_the_current_holder,tests/test_merge_queue.py::test_queue_entry_journal_names_the_holder_pid,tests/test_merge_queue.py::test_ac10_wait_texts_name_holder_of_waiting_task_project,tests/test_merge_queue.py::test_ac10_single_project_texts_are_unchanged,tests/test_merge_queue.py::test_texts_name_own_project_holder_in_every_insertion_order
20	убита	tests/test_merge_after_module.py::test_form_accepts_ids_prefixes_and_legacy_rejects_rest
21	убита	tests/test_merge_after_module.py::test_form_accepts_ids_prefixes_and_legacy_rejects_rest
22	убита	tests/test_merge_after_module.py::test_exact_match_wins_over_longer_ids_with_same_prefix
23	убита	tests/test_merge_after_module.py::test_prefix_and_full_id_of_same_task_is_a_repeat
24	убита	tests/test_merge_after_module.py::test_done_dependency_is_valid
25	убита	tests/test_merge_after_module.py::test_dependency_missing_from_db_refuses_with_answer_channel
26	убита	tests/test_merge_after_module.py::test_none_word_mixed_with_ids_refused
27	убита	tests/test_merge_after_module.py::test_two_mandate_lines_refused
28	убита	tests/test_merge_after_module.py::test_plan_value_equal_to_db_after_resolution_is_silent
29	убита	tests/test_merge_after_module.py::test_task_not_depending_on_parent_is_untouched
30	убита	tests/test_merge_after_module.py::test_migrate_adds_merge_after_to_old_tasks_table
```

Перед частью №9: `git status --porcelain -- orchestrator/` — вывод пуст

```
# mutation-run №9 задачи 01M5R0AFX9Z1GA1DG5XV73JRTE
# источник патчей: каталог на диске
# ревизия прогона: worktree a6eb9bc46a354a0eeaa06db37a2463685d80dd68
# тесты: tests/test_merge_lock_module.py, tests/test_merge_queue.py, tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 31 mutation-031.diff sha256 ce25ea82e915eee5dde41d4c4d10bb3107ef53c87ee5c74951203f704b33685c
# патч 32 mutation-032.diff sha256 75df665fa23dfbaaa291ed878da42694c6d890e961df841cb505124f9fd1ff6e
# патч 33 mutation-033.diff sha256 7dbc52f11967eb4c5dec460bd8f4c19ee4792f1f02fb453b9b1b9e162a47b83d
# патч 34 mutation-034.diff sha256 ec7955764094df855255637c72306777285c33a971d200345def2a623f0a7e75
# патч 35 mutation-035.diff sha256 b121b8cf4e96ceee4b6b585a3bbd16e5238d4292834830511a815d22551a50bb
# патч 36 mutation-036.diff sha256 111dde2bf745f83f9abd90a2d316c8553efdb71b0f9fc492ff0ee074bc4cd9ca
# патч 37 mutation-037.diff sha256 2a093a730d605b314009543a1de144803cb2acedda812bceb8666cdef2a3f720
# патч 38 mutation-038.diff sha256 c6b2d41e2c2ebbcddbefda61b54f89f8cbc46b7ea0fb58b8e8d83f21c8874c66
# патч 39 mutation-039.diff sha256 e89fe75ec12af7aaaf0d522f891df9286dc134166b6d9082579f9dc8c7c79077
# патч 40 mutation-040.diff sha256 64ecbdc8fb03c81d06106c94f039b86ed2a54034198196f076b24f0b9ebfe720
# патч 41 mutation-041.diff sha256 8494b7a94ac4916298041e700ea848096b8fceb860249b23d24349e35a62fcba
# патч 42 mutation-042.diff sha256 3063630fb1d7e32fa304c808335c819f8c497fb682e165e43bbaad937f3c174b
# патч 43 mutation-043.diff sha256 4183702bd53468f5e982385aaf68ccee9d26feee6125a4f901ad2966ca923608
# патч 44 mutation-044.diff sha256 af9729e4dffa8a0c5ea002e01b9451ffc363633a0979204a221eccece73896c0
# патч 45 mutation-045.diff sha256 199e6dca92a847e833c004753ac674648b10817f6bd3746dc169a5955ee23204
# патч 46 mutation-046.diff sha256 790201e394566ef8ffbc1462a86475d49241ec94f616c9176a33770aa276b2b7
# патч 47 mutation-047.diff sha256 72918206748fd3fb7f78e1d8d2042283fc5fdb9702d194aa432504bcc51042e8
# патч 48 mutation-048.diff sha256 7829f5254b0096467a73af6369db5804d736b6a89a170832640ef67cb0a28ad1
# патч 49 mutation-049.diff sha256 07c6fcf1d064889f7a3fa121a38068489a81ac84d9774bf6002cb7f84dbb58a8
# патч 50 mutation-050.diff sha256 a191413d034276304d67c5de15b77bada9d0aa903d339e403d6263faf21f4d12
номер	исход	узлы
31	убита	tests/test_merge_after_module.py::test_label_must_start_line_and_word_must_be_whole
32	убита	tests/test_merge_after_module.py::test_label_must_start_line_and_word_must_be_whole
33	убита	tests/test_merge_after_module.py::test_empty_list_is_refused
34	убита	tests/test_merge_after_module.py::test_explicit_target_of_new_task_is_used
35	убита	tests/test_merge_after_module.py::test_no_check_after_spec_gate_was_passed
36	убита	tests/test_merge_after_module.py::test_short_prefix_inside_other_id_is_not_justification
37	убита	tests/test_merge_after_module.py::test_ac1_parent_replaced_by_last_subtask_in_every_dependent,tests/test_merge_after_module.py::test_ac2_dependent_journal_names_old_and_new_value
38	убита	tests/test_merge_after_module.py::test_ac2_dependent_journal_names_old_and_new_value,tests/test_merge_after_module.py::test_ac1_parent_replaced_by_last_subtask_in_every_dependent
39	убита	tests/test_merge_after_module.py::test_ac2_dependent_journal_names_old_and_new_value,tests/test_merge_after_module.py::test_ac1_parent_replaced_by_last_subtask_in_every_dependent,tests/test_merge_after_module.py::test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent
40	убита	tests/test_merge_after_module.py::test_ac1_parent_replaced_by_last_subtask_in_every_dependent,tests/test_merge_after_module.py::test_ac2_dependent_journal_names_old_and_new_value
41	убита	tests/test_merge_after_module.py::test_ac2_dependent_journal_names_old_and_new_value
42	убита	tests/test_merge_after_module.py::test_ac2_dependent_journal_names_old_and_new_value
43	убита	tests/test_merge_after_module.py::test_ac1_parent_replaced_by_last_subtask_in_every_dependent,tests/test_merge_after_module.py::test_ac2_dependent_journal_names_old_and_new_value,tests/test_merge_after_module.py::test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent
44	убита	tests/test_merge_after_module.py::test_ac1_parent_replaced_by_last_subtask_in_every_dependent,tests/test_merge_after_module.py::test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent,tests/test_merge_after_module.py::test_ac2_dependent_journal_names_old_and_new_value
45	убита	tests/test_merge_after_module.py::test_ac8_loss_refusal_leads_through_reject_and_escalated_answer
46	убита	tests/test_merge_after_module.py::test_ac8_loss_refusal_leads_through_reject_and_escalated_answer
47	убита	tests/test_merge_after_module.py::test_ac8_loss_refusal_leads_through_reject_and_escalated_answer
48	убита	tests/test_merge_after_module.py::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged
49	убита	tests/test_merge_after_module.py::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged
50	убита	tests/test_merge_after_module.py::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged
```

Перед частью №10: `git status --porcelain -- orchestrator/` — вывод пуст

```
# mutation-run №10 задачи 01M5R0AFX9Z1GA1DG5XV73JRTE
# источник патчей: каталог на диске
# ревизия прогона: worktree a6eb9bc46a354a0eeaa06db37a2463685d80dd68
# тесты: tests/test_merge_lock_module.py, tests/test_merge_queue.py, tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 51 mutation-051.diff sha256 8ad1dfbd5b701eebd46ef5dc364ef34863d516b39b9411f5c088f45889652ed9
# патч 52 mutation-052.diff sha256 0e124d5d547bbce9e93a903e9d0f5fe42814494ee2f5e1834ba0ab75bbabdc57
номер	исход	узлы
51	убита	tests/test_merge_lock_module.py::test_ac6_touch_heartbeat_renews_only_callers_project_row,tests/test_merge_lock_module.py::test_ac7_touch_heartbeat_does_not_renew_intercepted_row
52	убита	tests/test_merge_queue.py::test_ac9_dead_entry_of_project_does_not_hold_its_head
```


## Замеры

- До свода (база ветки): mutex_by_project — 17 тестов, 669 строк;
  `tests/test_merge_after.py` — 10 тестов, 214 строк;
  `tests/test_merge_after_declared.py` — 5 тестов, 119 строк; division — 3
  теста, 214 строк; spec_gate_hint — 2 теста, 278 строк; всего 37 тестов,
  1494 строки; файлы 3м-1: замок 19 тестов, 546 строк; очередь 21 тест,
  523 строки.
- После свода (HEAD): `tests/test_merge_lock_module.py` — 30 тестов, 1029 строк; `tests/test_merge_queue.py` — 27 тестов, 896 строк; `tests/test_merge_after_module.py` — 20 тестов, 882 строк; всего 77 тестов, 2807 строк.
- Время контрольных прогонов `mutation-run` (без патча): «до» №1: 37 тестов за 3,83 с; «до» №2: 37 тестов за 3,69 с; «до» №3: 37 тестов за 3,69 с; «до» №4: 37 тестов за 3,62 с; «до» №5: 37 тестов за 4,65 с; «после» №6: 77 тестов за 5,69 с; «после» №7: 77 тестов за 4,72 с; «после» №8: 77 тестов за 3,22 с; «после» №9: 77 тестов за 4,32 с; «после» №10: 77 тестов за 5,00 с.
- Дерево `orchestrator/` шапок совпадает: `git rev-parse
  72d52fd367828949767e234ecbe9b0cc79851084:orchestrator` и
  `a6eb9bc46a354a0eeaa06db37a2463685d80dd68:orchestrator` — оба
  `6df36660d6bfd9580a3c6dd3f907b09fb1158a4a`. sha256 каждого патча в шапках
  «до» и «после» совпадает (и с файлом на диске).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (патчи, заявки) | 1 |
| 2 (таблица «до») | 1 |
| 3 (строка падения) | 1, 5 |
| 4 (не доказательство) | 1, 5 |
| 5 (зерно, находки) | 1, 5 |
| 6 (красный контроль) | 1, 5 |
| 7 (временные файлы) | 1–5 |
| 8 (свод mutex_by_project) | 2 |
| 9 (свод merge_after) | 3 |
| 10 (фикстуры) | 2, 3 |
| 11 (помощники) | 2, 3 |
| 12 (утверждения) | 2, 3 |
| 13 (дубли) | 2, 3 |
| 14 (таблица «после») | 5 |
| 15 (соответствие) | 5 |
| 16 (замеры) | 5 |
| 17 (удаление, мандат) | 4 |
| 18 (зоны) | 1–5 |
| 19 (независимая проверка) | сессия при Операторе |

## Влияние на систему

Меняются только `tests/`: добавления в конец двух файлов 3м-1 (их 40
тестов, фикстуры и функции не тронуты), новый файл модуля, удаление пяти
файлов волны под мандатом ANSWER-1, `docs/codebase-map.md` — вывод
генератора. `orchestrator/`, `tests/fixtures.py`, `tests/sandbox.py`,
`tests/test_invariants.py` и прочие файлы требования 18 не меняются.
Гейты неослабления сверят перенос по мандату; ни одно утверждение не
удалено и не ослаблено, `skip`/`xfail` и пределы не добавлены. Откат —
revert одного merge-коммита задачи.

## Риски

- Машинный замок полных прогонов занят чужими `suite-run` — части ждут
  `--wait-lock`; при истечении часть перезапускается тем же вызовом.
- Тесты 3м-1 очереди без подмены паузы на патчах окна «после» могут
  упасть `Timeout` — не повод переписывать патч, если перенесённая функция
  падает утверждением (требование 14).

## Предложения системе

- `mutation-run`: логи прогонов патчей лежат вне каталогов роли — `grep`/`Read`
  по ним роли запрещены, читаются только через `python3`; строка падения
  каждой мутации нужна PLAN — не хватает команды пульта, печатающей
  «патч → тест → файл:строка» (здесь — `fail_lines.py`).
- Планка читает PLAN из ссылки документов, а ссылка обновляется только
  автокоммитом по итогам шага: проверить PLAN своей планкой внутри шага
  developer нечем, кроме самодельного `_pult` (здесь — `selfcheck.py`).
- Вспомогательный файл `.md` в каталоге документов (здесь `plan_static.md`)
  молча не пережил смену шага, а файлы иных расширений пережили: правило
  требования 7 SPEC стоит повторить в миссии шага, иначе работа теряется.
