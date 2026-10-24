---
task: 01M5R0AFX9Z1GA1DG5XV73JRTE
type: plan
author_role: developer
status: draft
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

- mutation-001: AcquireByProjectTest::test_ac1_other_project_holder_does_not_block_acquire — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:181 → test_merge_lock_module.py::test_ac1_other_project_holder_does_not_block_acquire (строка формы не найдена)
- mutation-001: AcquireByProjectTest::test_ac4_dead_holder_of_other_project_is_left_intact — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:262 → test_merge_lock_module.py::test_ac4_dead_holder_of_other_project_is_left_intact (строка формы не найдена)
- mutation-001: WaitTextsByProjectTest::test_ac10_wait_texts_name_holder_of_waiting_task_project — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:633 → test_merge_queue.py::test_ac10_wait_texts_name_holder_of_waiting_task_project (строка формы не найдена)
- mutation-001: QueueByProjectTest::test_ac2_other_project_holder_does_not_delay_wait_for_window — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:490 → test_merge_queue.py::test_ac2_other_project_holder_does_not_delay_wait_for_window (строка формы не найдена)
- mutation-002: AcquireByProjectTest::test_ac16_artel_holder_excludes_empty_null_and_missing_target — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:281 → test_merge_lock_module.py::test_ac16_artel_holder_excludes_empty_null_and_missing_target (строка формы не найдена)
- mutation-002: WaitTextsByProjectTest::test_ac10_wait_texts_name_holder_of_waiting_task_project → test_merge_queue.py::test_ac10_wait_texts_name_holder_of_waiting_task_project (только утверждением подготовки — не доказательство)
- mutation-002: AcquireByProjectTest::test_ac4_dead_holder_of_same_project_is_taken_over — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:236 → test_merge_lock_module.py::test_ac4_dead_holder_of_same_project_is_taken_over (строка формы не найдена)
- mutation-002: AcquireByProjectTest::test_ac3_live_holder_of_same_project_refuses_with_old_text — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:208 → test_merge_lock_module.py::test_ac3_live_holder_of_same_project_refuses_with_old_text (строка формы не найдена)
- mutation-002: AcquireByProjectTest::test_ac16_empty_or_null_target_holder_excludes_artel_task — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:302 → test_merge_lock_module.py::test_ac16_empty_or_null_target_holder_excludes_artel_task (строка формы не найдена)
- mutation-002: WaitTextsByProjectTest::test_ac10_single_project_texts_are_unchanged → test_merge_queue.py::test_ac10_single_project_texts_are_unchanged (только утверждением подготовки — не доказательство)
- mutation-003: WaitTextsByProjectTest::test_ac10_wait_texts_name_holder_of_waiting_task_project — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:633 → test_merge_queue.py::test_ac10_wait_texts_name_holder_of_waiting_task_project (строка формы не найдена)
- mutation-003: AcquireByProjectTest::test_ac3_live_holder_of_same_project_refuses_with_old_text — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:209 → test_merge_lock_module.py::test_ac3_live_holder_of_same_project_refuses_with_old_text (строка формы не найдена)
- mutation-003: WaitTextsByProjectTest::test_ac10_single_project_texts_are_unchanged — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:659 → test_merge_queue.py::test_ac10_single_project_texts_are_unchanged (строка формы не найдена)
- mutation-004: AcquireByProjectTest::test_ac4_dead_holder_of_same_project_is_taken_over — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:236 → test_merge_lock_module.py::test_ac4_dead_holder_of_same_project_is_taken_over (строка формы не найдена)
- mutation-005: AcquireByProjectTest::test_ac4_dead_holder_of_other_project_is_left_intact — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:260 → test_merge_lock_module.py::test_ac4_dead_holder_of_other_project_is_left_intact (строка формы не найдена)
- mutation-005: StoreMergeLockTest::test_ac11_set_merge_lock_keeps_other_project_row — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:458 → test_merge_lock_module.py::test_ac11_set_merge_lock_keeps_other_project_row (строка формы не найдена)
- mutation-005: AcquireByProjectTest::test_ac1_other_project_holder_does_not_block_acquire — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:183 → test_merge_lock_module.py::test_ac1_other_project_holder_does_not_block_acquire (строка формы не найдена)
- mutation-006: AcquireByProjectTest::test_ac4_dead_holder_of_same_project_is_taken_over — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:234 → test_merge_lock_module.py::test_ac4_dead_holder_of_same_project_is_taken_over (строка формы не найдена)
- mutation-007: AcquireByProjectTest::test_ac16_artel_holder_excludes_empty_null_and_missing_target — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:281 → test_merge_lock_module.py::test_ac16_artel_holder_excludes_empty_null_and_missing_target (строка формы не найдена)
- mutation-008: QueueByProjectTest::test_ac8_head_is_earliest_entry_of_own_project — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:515 → test_merge_queue.py::test_ac8_head_is_earliest_entry_of_own_project (строка формы не найдена)
- mutation-008: QueueByProjectTest::test_ac9_dead_entry_of_project_does_not_hold_its_head — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:584 → test_merge_queue.py::test_ac9_dead_entry_of_project_does_not_hold_its_head (строка формы не найдена)
- mutation-008: QueueByProjectTest::test_ac8_same_project_tasks_enter_in_fifo_order — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:553 → test_merge_queue.py::test_ac8_same_project_tasks_enter_in_fifo_order (строка формы не найдена)
- mutation-009: QueueByProjectTest::test_ac8_same_project_tasks_enter_in_fifo_order — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:550 → test_merge_queue.py::test_ac8_same_project_tasks_enter_in_fifo_order (строка формы не найдена)
- mutation-010: QueueByProjectTest::test_ac9_dead_entry_of_project_does_not_hold_its_head — tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py:584 → test_merge_queue.py::test_ac9_dead_entry_of_project_does_not_hold_its_head (строка формы не найдена)

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


## Мутации после

Команда: `mutation-run 01M5R0AFX9Z1GA1DG5XV73JRTE --ref worktree --tests
tests/test_merge_lock_module.py,tests/test_merge_queue.py,tests/test_merge_after_module.py
--copy-table --wait-lock 4 --patches <часть>` — те же диапазоны и то же
`--workers` (умолчание), что «до»; вывод частей дословно.

(частей ещё нет)

## Замеры

- До свода (база ветки): mutex_by_project — 17 тестов, 669 строк;
  `tests/test_merge_after.py` — 10 тестов, 214 строк;
  `tests/test_merge_after_declared.py` — 5 тестов, 119 строк; division — 3
  теста, 214 строк; spec_gate_hint — 2 теста, 278 строк; всего 37 тестов,
  1494 строки; файлы 3м-1: замок 19 тестов, 546 строк; очередь 21 тест,
  523 строки.
- После свода (HEAD): `tests/test_merge_lock_module.py` — 30 тестов, 1032 строк; `tests/test_merge_queue.py` — 27 тестов, 898 строк; `tests/test_merge_after_module.py` — 20 тестов, 882 строк; всего 77 тестов, 2812 строк.
- Время контрольных прогонов `mutation-run` (без патча): «до» №1: 37 тестов за 3,83 с; «до» №2: 37 тестов за 3,69 с.

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
