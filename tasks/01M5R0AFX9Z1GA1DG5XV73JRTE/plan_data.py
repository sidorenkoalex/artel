"""Данные PLAN.md задачи 01M5R0AFX9Z1GA1DG5XV73JRTE для make_plan.py:
мутация -> файл правки, что меняет патч, заявившие тесты, довод о зерне."""

A1 = "AcquireByProjectTest::test_ac1_other_project_holder_does_not_block_acquire"
A3 = "AcquireByProjectTest::test_ac3_live_holder_of_same_project_refuses_with_old_text"
A4S = "AcquireByProjectTest::test_ac4_dead_holder_of_same_project_is_taken_over"
A4O = "AcquireByProjectTest::test_ac4_dead_holder_of_other_project_is_left_intact"
A16A = "AcquireByProjectTest::test_ac16_artel_holder_excludes_empty_null_and_missing_target"
A16B = "AcquireByProjectTest::test_ac16_empty_or_null_target_holder_excludes_artel_task"
R5 = "ReleaseAndHeartbeatTest::test_ac5_release_removes_only_own_process_row"
R6 = "ReleaseAndHeartbeatTest::test_ac6_touch_heartbeat_renews_only_callers_project_row"
R7 = "ReleaseAndHeartbeatTest::test_ac7_touch_heartbeat_does_not_renew_intercepted_row"
R17 = "ReleaseAndHeartbeatTest::test_ac17_touch_heartbeat_without_args_keeps_old_behaviour"
S11 = "StoreMergeLockTest::test_ac11_set_merge_lock_keeps_other_project_row"
Q2 = "QueueByProjectTest::test_ac2_other_project_holder_does_not_delay_wait_for_window"
Q8H = "QueueByProjectTest::test_ac8_head_is_earliest_entry_of_own_project"
Q8F = "QueueByProjectTest::test_ac8_same_project_tasks_enter_in_fifo_order"
Q9 = "QueueByProjectTest::test_ac9_dead_entry_of_project_does_not_hold_its_head"
W10 = "WaitTextsByProjectTest::test_ac10_wait_texts_name_holder_of_waiting_task_project"
W10S = "WaitTextsByProjectTest::test_ac10_single_project_texts_are_unchanged"
FORM = "TaskIdFormTest::test_form_accepts_ids_prefixes_and_legacy_rejects_rest"
EXACT = "TaskIdMatchesTest::test_exact_match_wins_over_longer_ids_with_same_prefix"
REPEAT = "CheckTest::test_prefix_and_full_id_of_same_task_is_a_repeat"
DONE = "CheckTest::test_done_dependency_is_valid"
MISSING = "MergeGateMissingDependencyTest::test_dependency_missing_from_db_refuses_with_answer_channel"
NONE = "MandateLineTest::test_none_word_mixed_with_ids_refused"
TWO = "MandateLineTest::test_two_mandate_lines_refused"
PLANV = "PlanChannelSameValueTest::test_plan_value_equal_to_db_after_resolution_is_silent"
REPL = "ReplaceDividedTest::test_task_not_depending_on_parent_is_untouched"
MIG = "MigrationTest::test_migrate_adds_merge_after_to_old_tasks_table"
LABEL = "DeclaredFromTzTest::test_label_must_start_line_and_word_must_be_whole"
EMPTY = "DeclaredFromTzTest::test_empty_list_is_refused"
EXPL = "DeclaredFromTzTest::test_explicit_target_of_new_task_is_used"
PASSED = "SpecGateDeclaredRefusalTest::test_no_check_after_spec_gate_was_passed"
SHORT = "SpecGateDeclaredRefusalTest::test_short_prefix_inside_other_id_is_not_justification"
D1 = "DivisionRewritesDependentsTest::test_ac1_parent_replaced_by_last_subtask_in_every_dependent"
D2 = "DivisionRewritesDependentsTest::test_ac2_dependent_journal_names_old_and_new_value"
D3 = "DivisionRewritesDependentsTest::test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent"
H8 = "LossRefusalTextTest::test_ac8_loss_refusal_leads_through_reject_and_escalated_answer"
H9 = "DeclaredPathTest::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged"

PAIRS = ("оба порядка проектов из `project_pairs` перебираются циклом, "
         "имена задач и проектов от зерна в исход не входят")

# номер: (файл правки, что меняет патч, [(тест, альтернатива заявки)], довод о зерне)
MUTATIONS = {
    1: ("orchestrator/merge_lock.py",
        "`acquire` берёт строку мьютекса всего пульта `store.merge_lock_row(conn)` вместо строки проекта задачи",
        [(A1, "«acquire читает одну строку на пульт»"), (A4O, "«перехватывает любую мёртвую строку таблицы»"),
         (A4S, "«перехват ищет мёртвую строку не своего проекта» — тот же смысл; этот тест её не убивает: в его таблице одна строка"),
         (Q2, "«acquire ждёт освобождения мьютекса всего пульта»")],
        "строка другого проекта в таблице есть в каждом подслучае; " + PAIRS),
    2: ("orchestrator/merge_lock.py",
        "`acquire` ищет держателя по проекту `task_id` (никогда не совпадает) — держатель того же проекта считается чужим",
        [(A3, "«проект сверяется не по target задачи держателя»")],
        "держатель того же проекта живой (чужой host, свежий heartbeat) в каждом подслучае, его не находит при любом зерне"),
    3: ("orchestrator/merge_lock.py",
        "текст отказа `acquire`: «дождись освобождения» → «жди освобождения»",
        [(A3, "«текст отказа собран иначе»")],
        "текст отказа не зависит от случайных id, шаблон `refusal_pattern` экранирует их `re.escape`"),
    4: ("orchestrator/merge_lock.py",
        "перехват мёртвого держателя в `acquire` без записи журнала «мьютекс merge перехвачен»",
        [(A4S, "«перехват идёт без записи журнала»")],
        "протухший heartbeat задан `_ts_ago(LEASE_STALE_AFTER_SEC + 60)`, перехват идёт в каждом подслучае при любом зерне"),
    5: ("orchestrator/store.py",
        "`set_merge_lock` стирает всю таблицу `merge_locks` (`DELETE` без `WHERE`)",
        [(A1, "«set_merge_lock делает DELETE без WHERE»"), (A4O, "«set_merge_lock стирает строки других проектов»"),
         (S11, "«set_merge_lock оставлен с DELETE без WHERE»")],
        "строка другого проекта есть в таблице до записи в каждом подслучае; " + PAIRS),
    6: ("orchestrator/store.py",
        "`set_merge_lock` добавляет строку, не снося прежнюю строку проекта",
        [(A4S, "«set_merge_lock добавляет строку, не снося прежнюю строку проекта»")],
        "мёртвая строка того же проекта есть в каждом подслучае; состав таблицы сверяется целиком"),
    7: ("orchestrator/store.py",
        "`task_target` отдаёт сырую колонку `target` (пустую, `NULL`, `None` для задачи без строки) без нормализации",
        [(A16A, "«проект задачи берётся сырой колонкой target»")],
        "вызывающие с пустым, `NULL` и отсутствующим target заданы литералами, не зерном"),
    8: ("orchestrator/merge_queue.py",
        "`wait_for_window`: голова — первая запись всей очереди `_head_task_id(conn)` без проекта",
        [(Q8H, "«голова очереди — первая запись всего пульта»"), (Q8F, "«голова считается по всей очереди»"),
         (Q9, "«голова по всей очереди»")],
        "запись другого проекта стоит раньше по `enqueued_ts` (`_ts_ago` с разницей минут) в каждом подслучае; " + PAIRS),
    9: ("orchestrator/merge_queue.py",
        "`wait_for_window`: условие «голова очереди своего проекта» заменено на `True` — FIFO внутри проекта снят",
        [(Q8F, "«FIFO внутри проекта снят (голова — любая запись своего проекта либо своя)»")],
        "запись P1 стоит в очереди раньше P2 в каждом подслучае; паузы — подменённые, без часов"),
    10: ("orchestrator/merge_queue.py",
         "`wait_for_window` не зовёт `_prune_dead_entries` до определения головы",
         [(Q9, "«пруна мёртвых записей не идёт до определения головы проекта»")],
         "мёртвая запись P0 (протухший heartbeat либо `_dead_pid` на своём host) — в обоих видах подслучая при любом зерне"),
    11: ("orchestrator/store.py",
         "`_ROW_TARGET_SQL` (проект строки мьютекса для `merge_lock_rows`): `COALESCE(t.target, ?)` — пустой target не нормализуется",
         [(A16B, "«проект держателя берётся сырой колонкой target»")],
         "держатель с пустым target — первый подслучай цикла `(\"\", None)`, задан литералом"),
    12: ("orchestrator/store.py",
         "`release_merge_lock` снимает строки по одному `session_id`",
         [(R5, "«release сносит строки по одному session_id»")],
         "перемешивание `rng.shuffle` меняет только проекты трёх строк; строка той же сессии с чужим pid есть всегда"),
    13: ("orchestrator/store.py",
         "`release_merge_lock` снимает всю таблицу `merge_locks`",
         [(R5, "«release сносит всю таблицу»"), (S11, "«release_merge_lock снимает строки по проекту/всю таблицу»")],
         "строки других процессов есть в таблице до снятия в каждом сценарии, от зерна зависят только имена"),
    14: ("orchestrator/merge_lock.py",
         "`_own_rows` с `task_id`: продлеваются все строки таблицы",
         [(R6, "«продлевает все строки»")],
         "строка B со старым heartbeat есть в каждом подслучае; " + PAIRS),
    15: ("orchestrator/merge_lock.py",
         "`_own_rows` с `task_id`: «своя» строка сверяется только по проекту",
         [(R7, "«продление сверяет только проект строки»")],
         "строка нового держателя того же проекта — в каждом подслучае обоих вариантов, литералы вариантов не от зерна"),
    16: ("orchestrator/merge_lock.py",
         "`_own_rows` с `task_id`: «своя» строка сверяется по проекту и задаче, без сессии",
         [(R7, "«или только задачу»")],
         "вариант «другая сессия» (та же задача, другая сессия) — литерал цикла, есть при любом зерне"),
    17: ("orchestrator/merge_lock.py",
         "`_own_rows` без `task_id` при одной строке: «своя» строка сверяется по `task_id is None` — ничего не продлевается",
         [(R17, "«прежняя форма без task_id превращена в ничего не делающую»")],
         "одна строка с heartbeat `_ts_ago(600)` в каждом подслучае, свежесть меряется часами, не зерном"),
    18: ("orchestrator/merge_queue.py",
         "`_holder_row`: держатель для текстов ожидания — первая строка таблицы `merge_lock_row`",
         [(W10, "«тексты собираются по первой строке таблицы»")],
         "оба порядка вставки (`p_first` True/False) перебираются циклом; в порядке «Q первой» текст называет Q при любом зерне"),
    19: ("orchestrator/merge_queue.py",
         "`_current_holder_label`: метка «(pid <pid>, проект <target>)»",
         [(W10S, "«тексты получили метку проекта или иной формат»")],
         "формат текста не зависит от случайных id"),
    20: ("orchestrator/idgen.py",
         "`is_task_id_form`: проверка длины снята",
         [(FORM, "«проверка длины снята»")],
         "`full + \"0\"` — 27 символов алфавита ULID при любом id из `idgen` (случайна только последовательность символов)"),
    21: ("orchestrator/idgen.py",
         "`is_task_id_form`: алфавит не сверяется, только длина",
         [(FORM, "«алфавит не сверяется»")],
         "`full.lower()` длиной 26 проходит одну проверку длины при любом id из `idgen`"),
    22: ("orchestrator/store.py",
         "`task_id_matches`: точное совпадение не проверяется первым",
         [(EXACT, "«точное совпадение не проверяется первым»")],
         "id `T1`/`T10` — литералы, ULID не участвуют"),
    23: ("orchestrator/merge_after.py",
         "`check`: повтор сверяется по буквальному тексту элемента, не по разрешённому id",
         [(REPEAT, "«повтор сверяется только по буквальному тексту элемента»")],
         "`dep[:-1]` (25 символов ULID из `idgen`) — однозначный префикс `dep` при любом зерне, текст элемента всегда иной"),
    24: ("orchestrator/merge_after.py",
         "`check`: зависимость в `done` отказывается как `killed`",
         [(DONE, "«done спутан с killed»")],
         "состояние `done` — литерал, ULID из `idgen` на исход не влияет"),
    25: ("orchestrator/merge_after.py",
         "`merge_gate_refuses`: пропавшая из БД зависимость — в ветке незавершённых (подсказка повтора `approve`)",
         [(MISSING, "«пропавшая зависимость обрабатывается как незавершённая»")],
         "ULID-призрак из `idgen` в БД нет при любом значении"),
    26: ("orchestrator/merge_after.py",
         "`value_refusals`: «нет» молча отбрасывается из элементов строки мандата до проверки",
         [(NONE, "«нет молча отбрасывается из перечня до проверки»")],
         "зависимость — живая задача с ULID из `idgen`, проверка `check` проходит при любом id"),
    27: ("orchestrator/merge_after.py",
         "`lines_refusal`: считается только первая строка мандата — повтор не замечается",
         [(TWO, "«берётся первая строка, вторая молча теряется»")],
         "две строки мандата — литерал текста, id из `idgen` на число строк не влияют"),
    28: ("orchestrator/merge_after.py",
         "`apply_plan`: совпадение с БД сверяется по сырому тексту PLAN, не по разрешённым id",
         [(PLANV, "«сравнение идёт по сырому тексту PLAN»")],
         "`dep[:-2]` — однозначный префикс ULID из `idgen`, всегда отличный от `dep` текстом"),
    29: ("orchestrator/merge_after.py",
         "`replace_divided`: фильтр «родитель в значении» снят — переписывается каждая задача",
         [(REPL, "«фильтр «родитель в значении» снят»")],
         "задача песочницы переписывается при любых ULID из `idgen`"),
    30: ("orchestrator/schema.py",
         "`migrate` не добавляет колонку `merge_after`",
         [(MIG, "«колонка добавлена только в DDL»")],
         "случайных входов у теста нет; зерно не участвует"),
    31: ("orchestrator/merge_after.py",
         "`_ORDER_LINE_RE` без `^` — метка ищется в любом месте строки",
         [(LABEL, "«метка ищется в любом месте строки (без ^)»")],
         "строка с отступом — первый подслучай, задана литералом; ULID из `idgen` годен при любом значении"),
    32: ("orchestrator/merge_after.py",
         "`_ORDER_LINE_RE` без `(?!\\w)` — слово «после» сверяется префиксом",
         [(LABEL, "«слово «после» сверяется префиксом»")],
         "«послезавтра» — литерал подслучая; исход не зависит от ULID из `idgen`"),
    33: ("orchestrator/merge_after.py",
         "`declared_from_tz`: пустой перечень возвращается как `([], [])`",
         [(EMPTY, "«пустой перечень возвращается как ([], [])»")],
         "текст ТЗ — литерал; ULID из `idgen` не участвует в исходе"),
    34: ("orchestrator/merge_after.py",
         "`check`: target заводимой задачи берётся из БД (`store.task_target(conn, None)`), не явный",
         [(EXPL, "«check берёт target из строки БД несуществующей задачи»")],
         "target `proekt` — литерал; ULID из `idgen` на сверку target не влияет"),
    35: ("orchestrator/merge_after.py",
         "`spec_gate_declared_refusal`: признак «гейт SPEC уже пройден» (`_declared_in_force`) снят",
         [(PASSED, "«признак «гейт SPEC уже пройден» снят»")],
         "запись журнала `state -> tests_writing` — литерал; ULID из `idgen` не влияет"),
    36: ("orchestrator/merge_after.py",
         "`_justified`: обоснование ищется подстрокой, не словом целиком",
         [(SHORT, "«обоснование ищется подстрокой»")],
         "префикс строится от первого различия двух ULID из `idgen` и стоит в разделе как `X<префикс>Y` при любых значениях"),
    37: ("orchestrator/fsm.py",
         "деление на гейте SPEC подставляет первую подзадачу `new_ids[0]` вместо последней",
         [(D1, "«вместо последней подзадачи подставлена первая»")],
         "частей деления от зерна 2–4 — первая подзадача никогда не последняя"),
    38: ("orchestrator/merge_after.py",
         "`replace_divided`: элемент-родитель удаляется вместо замены",
         [(D1, "«элемент P удалён вместо замены»")],
         "родитель стоит в значении каждой зависящей задачи при любой позиции от зерна"),
    39: ("orchestrator/merge_after.py",
         "`replace_divided`: переписывается только первая найденная зависящая задача",
         [(D1, "«переписана только первая найденная зависящая задача»")],
         "зависящих задач от зерна 2–3 — хотя бы одна остаётся с родителем"),
    40: ("orchestrator/merge_after.py",
         "`replace_divided`: значение — один Sn, соседи X отброшены",
         [(D1, "«соседи X отброшены»")],
         "у каждой зависящей задачи от зерна 1–2 соседа"),
    41: ("orchestrator/merge_after.py",
         "`replace_divided`: колонка переписывается прямым `store.update_task` мимо `rewrite` (без журнала)",
         [(D2, "«колонка D переписана прямым store.update_task мимо merge_after.rewrite»")],
         "записи нет в журнале каждой зависящей задачи при любом зерне"),
    42: ("orchestrator/merge_after.py",
         "`replace_divided`: запись «merge_after изменён» идёт в журнал родителя, не зависящей задачи",
         [(D2, "«запись сделана в журнал родителя P вместо журнала D»")],
         "журнал зависящей задачи пуст по этому действию при любом зерне"),
    43: ("orchestrator/fsm.py",
         "деление на гейте SPEC не зовёт `replace_divided`",
         [(D3, "«деление не переписывает merge_after зависящих задач»")],
         "родитель стоит в `merge_after` каждой зависящей задачи при любом зерне"),
    44: ("orchestrator/merge_after.py",
         "`replace_divided`: переписывается только строка самого родителя",
         [(D3, "«переписывает только колонку родителя»")],
         "колонка родителя пуста, зависящие задачи не переписываются при любом зерне"),
    45: ("orchestrator/merge_after.py",
         "отказ о потере заявленной зависимости — с прежним хвостом «снять заявленную может только Оператор …»",
         [(H8, "«хвост отказа не заменён»")],
         "потерянная зависимость есть в каждой из трёх итераций (`kept` урезается при совпадении), «reject» нет при любом зерне"),
    46: ("orchestrator/merge_after.py",
         "отказ о потере: «answer» стоит раньше «reject»",
         [(H8, "«новый текст называет answer раньше reject»")],
         "порядок слов в тексте не зависит от id и ветки «поле есть/нет»"),
    47: ("orchestrator/merge_after.py",
         "начало отказа о потере: «merge_after в SPEC теряет …»",
         [(H8, "«правка задела начало отказа»")],
         "начало текста не зависит от id и ветки поля"),
    48: ("orchestrator/merge_after.py",
         "отказ о добавке: «без обоснования» → «без причины»",
         [(H9, "«отказ о добавке без обоснования сменил текст»")],
         "добавка сверх заявленного есть всегда; ожидаемый текст собран из её id"),
    49: ("orchestrator/merge_after.py",
         "отказ гейта мержа по убитой зависимости: «сними или замени её» → «замени её»",
         [(H9, "«отказы гейта мержа сменили текст»")],
         "подслучай `killed` — литерал цикла, от зерна не зависит"),
    50: ("orchestrator/merge_after.py",
         "`mandate_value`: строка мандата в ответе не находится — `answer` в escalated колонку не меняет",
         [(H9, "«answer в escalated перестал менять колонку»")],
         "`kept` от зерна всегда короче заявленных (`randint(0, len-1)`), колонка без смены ему не равна"),
    51: ("orchestrator/merge_lock.py",
         "`_own_rows` с `task_id`: продлевается первая строка таблицы",
         [(R6, "«продление берёт первую строку таблицы»")],
         "порядок «B первой» (`a_first=False`) перебирается циклом при любом зерне"),
    52: ("orchestrator/merge_queue.py",
         "`wait_for_window`: пруна убирает только мёртвые записи других проектов",
         [(Q9, "«или убирает только записи другого проекта»")],
         "мёртвая запись P0 своего проекта — в обоих видах подслучая при любом зерне"),
}

STATUS_BEFORE = {}


def patch_lines():
    out = []
    for n, (path, what, claims, _seed) in sorted(MUTATIONS.items()):
        tests = "; ".join(f"{key} — {alt}" for key, alt in claims)
        out.append(f"- mutation-{n:03d} — `{path}`: {what}. Заявки: {tests}.")
    return out


def seed_lines():
    return [f"- mutation-{n:03d}: убийство не зависит от зерна — {seed}."
            for n, (_p, _w, _c, seed) in sorted(MUTATIONS.items())]
