---
task: 01M5PCB66D936FDGG7H09CVGA1
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Сведение тестов, волна 1б — тесты `doc-commit` и сверки по базе в `tests/test_doc_commit_module.py`

## Подход

Порядок волны 1а: патч на каждую строку «Ловит мутацию» шести исходных
файлов → таблица «до» (`mutation-run --ref base`, шесть файлов, частями
`--patches`) → свод в `tests/test_doc_commit_module.py` (pytest-функции,
фикстуры `doc_box`/`held_box`/`unit_box`/`knowledge_box` поверх `real_git`
из `tests/fixtures.py`, помощники с утверждениями — функции модуля) →
таблица «после» (`--ref worktree`, новый файл) → удаление шести файлов.

Ключевые решения:
- 71 строка «Ловит мутацию» → 71 патч `mutation-001.diff` … `mutation-071.diff`
  (все — только `orchestrator/notes.py`, кроме 027/028 — `orchestrator/artel.py`).
  Одинаковые по смыслу строки сведены в одну мутацию: 002 (два теста
  «бэклог не принимается»), 018 (два теста «пиновая сверка немедленной
  отправки снята»), 053 (два теста «запись без базы — без предупреждения»).
- Три заявки исходников описывают упразднённый рабочий репозиторий
  `.artel/notes-work` (теперь — клон артели `workspace.repo`, он в стенде
  всегда есть и всегда чистый): их патчи 015, 041, 042 никто не убил ни
  «до», ни «после» — находки ниже. Тесты при этом не удалены (требование 7):
  их строки «Ловит мутацию» в новом файле переписаны на мутации, которые
  они убивают, со своими патчами 017, 070, 071.
- Дублей не удалено: все 71 тест перенесены функциями под прежними именами.
- Main подтянут в ветку (6c4b867a, база ed38d987) после прогонов «до»
  №1–3 (база 549e997e) — «до» повторён на новой базе (требование 9),
  повтор дописан в раздел «Мутации до» после прежних частей (у мутации в
  силе её последняя строка). Дерево `orchestrator/` у всех ревизий шапок
  одно: `git diff --quiet` для пар 549e997e/ca098937/6c4b867a/ed38d987
  по `orchestrator/` — код 0.
- Текст исключения проверяли три места исходников
  (`DocCommitRefusalTest.assert_refused`,
  `PinBaseCheckTest.test_origin_diverged_from_pin_refuses_naming_pin_update`,
  `SuiteGateSandbox.refuse_config`) — только там `pytest.raises(...,
  match=re.escape(...))`; перебор по константе `notes.DOC_COMMIT_CONFIG_PATHS`
  — `parametrize` по самой константе; литеральные наборы путей
  `PathRefusalTest` — `parametrize` литералами; печать зерна случайных
  стендов (`held_box`, `knowledge_box`) — там же, где в исходнике.

## Шаги

1. Патчи мутаций 001–071 в каталоге документов задачи; таблица «до» №1–3.
2. Свод в `tests/test_doc_commit_module.py`, удаление шести файлов волны,
   регенерация `docs/codebase-map.md` (коммит ca098937).
3. Таблица «после» №4–5 (`--ref worktree`).
4. Повтор «до» после подтяжки main (№6–7), сверка «до»/«после».

## Сопоставление мутаций

Строка: патч — тесты исходных файлов, чью строку «Ловит мутацию» он
воплощает, — что меняет патч.

- mutation-001 — PathRefusalTest::test_docs_paths_and_operator_config_are_allowed — `_doc_commit_path_refusal`: снят допуск путей `DOC_COMMIT_CONFIG_PATHS` (конфиг Оператора отказан).
- mutation-002 — PathRefusalTest::test_backlog_is_refused_naming_note, DocCommitRefusalTest::test_backlog_path_refused_origin_keeps_backlog — снят отказ пути `docs/backlog.md`.
- mutation-003 — PathRefusalTest::test_code_tests_skills_templates_tasks_refused_with_named_text — допуск пути по расширению `.md`/`.yaml`, а не по расположению.
- mutation-004 — PathRefusalTest::test_absolute_dotdot_empty_and_bare_docs_dir_refused — снята проверка `..` в частях пути.
- mutation-005 — CommitMessageTest::test_prefix_by_path_kind_without_truncation — `_commit_message` даёт `doc-commit` общий префикс `NOTE_COMMIT_SUBJECT_PREFIX`.
- mutation-006 — CommitMessageTest::test_target_rel_is_own_path_for_doc_commit_and_backlog_for_note — `_target_rel` всегда `BACKLOG_REL`.
- mutation-007 — DocCommitPushTest::test_content_lands_in_origin_output_names_sha_main_copy_untouched — вывод успеха без sha.
- mutation-008 — DocCommitPushTest::test_bytes_preserved_crlf_not_translated — `--from` читается `read_text` (CRLF → LF).
- mutation-009 — DocCommitPushTest::test_no_journal_row_for_doc_commit — снят ранний `return` перед журналом для `doc-commit`.
- mutation-010 — DocCommitPushTest::test_config_path_gets_config_prefix_docs_path_gets_docs_prefix — `_doc_commit_prefix`: путь `docs/` получает префикс конфигурации.
- mutation-011 — DocCommitRefusalTest::test_foreign_path_refused_without_commit_or_hold — проверка пути перенесена после `_run`.
- mutation-012 — DocCommitRefusalTest::test_missing_message_refused_without_commit_or_hold — пробельный `--message` проходит.
- mutation-013 — DocCommitRefusalTest::test_missing_or_absent_source_file_refused — снята проверка `is_file()` файла `--from`.
- mutation-014 — DocCommitRefusalTest::test_identical_content_refused_instead_of_hanging_in_pending — снят отказ «содержимое уже совпадает».
- mutation-015 — DocCommitRefusalTest::test_role_environment_refused_before_work_repo_exists (заявка исходника) — `_ensure_work_repo()` вызывается до рубежа окружения роли.
- mutation-016 — DocCommitRefusalTest::test_role_environment_markers_from_env_are_honoured — рубеж читает `os.environ[ARTEL_ROLE_ENV]` вместо `runner.in_role_environment()`.
- mutation-017 — DocCommitRefusalTest::test_role_environment_refused_before_work_repo_exists (переписанная заявка, `test_doc_commit_module.py::test_role_environment_refused_before_work_repo_exists`) — рубеж окружения роли снят с `cmd_doc_commit`.
- mutation-018 — PinBaseCheckTest::test_origin_diverged_from_pin_refuses_naming_pin_update, ImmediatePinCheckTest::test_ac5_immediate_send_still_refuses_on_pin — снята пиновая сверка немедленной отправки.
- mutation-019 — PinBaseCheckTest::test_new_path_absent_everywhere_is_committed — «пути нет в origin» читается как расхождение с пином.
- mutation-020 — PinBaseCheckTest::test_path_added_in_origin_after_pin_refuses — «в пине нет» пропускается как новый файл.
- mutation-021 — SilenceWindowAndFlushTest::test_open_window_holds_json_with_kind_and_flush_after_close_pushes — окно тишины не проверяется для `doc-commit`.
- mutation-022 — SilenceWindowAndFlushTest::test_flush_does_not_need_source_file_anymore — запись хранит путь `--from` и перечитывает файл при флаше.
- mutation-023 — SilenceWindowAndFlushTest::test_note_flush_sends_both_kinds — `_fetch_and_build` без ветки `doc-commit`.
- mutation-024 — SilenceWindowAndFlushTest::test_doc_commit_flush_sends_both_kinds — `doc-commit --flush` фильтрует записи по своему виду.
- mutation-025 — SilenceWindowAndFlushTest::test_flush_ignores_open_window_but_new_record_is_still_held — попутный флаш в `cmd_doc_commit` безусловен.
- mutation-026 — SilenceWindowAndFlushTest::test_note_hold_texts_unchanged — текст удержания `note` — «запись удержана».
- mutation-027 — DispatcherTest::test_artel_dispatches_doc_commit_with_rest_argv — строка `doc-commit` удалена из таблицы диспетчера `orchestrator/artel.py`.
- mutation-028 — DispatcherTest::test_help_text_names_doc_commit — справка `orchestrator/artel.py` не называет `doc-commit`.
- mutation-029 — RedSuiteTest::test_red_suite_refuses_naming_the_failed_test — гейт полного набора не заводится ни на одной записи.
- mutation-030 — RedSuiteTest::test_unrunnable_suite_refuses_the_same_way — дерево без `tests/` — «гонять нечего», отказа нет.
- mutation-031 — RedSuiteTest::test_green_suite_lets_the_commit_through — условие исхода прогона перевёрнуто.
- mutation-032 — SuiteTreeTest::test_suite_runs_on_the_tree_with_the_change_already_applied — гейт стоит до записи файла.
- mutation-033 — SuiteTreeTest::test_docs_path_does_not_run_the_suite_at_all — гейт на всех путях `doc-commit`.
- mutation-034 — SuiteTreeTest::test_open_window_holds_the_record_and_the_gate_fires_on_flush — гейт поставлен в построение правки, до удержания.
- mutation-035 — AcceptRedTest::test_accept_red_commits_and_journal_carries_path_and_reason — журнал обхода без основания.
- mutation-036 — AcceptRedTest::test_accept_red_skips_the_run_entirely — флаг учитывается после прогона.
- mutation-037 — AcceptRedTest::test_accept_red_without_reason_refuses_by_substance_not_argparse — `--accept-red` объявлен обычным `add_argument`.
- mutation-038 — AcceptRedTest::test_green_suite_with_accept_red_still_journals_the_bypass — журнал обхода только при красном прогоне.
- mutation-039 — GateRefusalLeavesNoDirtTest::test_repeat_after_fixing_the_suite_commits_the_same_change — сверка «уже совпадает» по файлу дерева и `checkout` без `-f`.
- mutation-040 — GateRefusalLeavesNoDirtTest::test_note_reaches_origin_after_a_gate_refusal_and_a_foreign_change — `checkout -B` без `-f` и без проверки кода возврата.
- mutation-041 — GateRefusalLeavesNoDirtTest::test_dirty_work_tree_is_forced_to_origin_before_the_next_record (заявка исходника) — то же снятие `-f` и проверки кода в `_fetch_and_build`.
- mutation-042 — GateRefusalLeavesNoDirtTest::test_leftover_file_in_the_work_tree_is_not_read_as_origin_content (заявка исходника) — сверка «уже совпадает» по файлу дерева, `clean` пути снят.
- mutation-043 — HeldConfigRecordFlushTest::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks — попутный флаш отправляет любую удержанную запись.
- mutation-044 — HeldConfigRecordFlushTest::test_accept_red_record_is_sent_by_the_opportunistic_flush — пропуск попутного флаша не смотрит на `accept_red`.
- mutation-045 — AcceptRedOnDocsPathTest::test_docs_path_accept_red_writes_no_bypass_journal_row — журнал обхода по одному наличию флага.
- mutation-046 — HeldRecordBaseTest::test_ac1_held_record_stores_pin_blob_or_absent_mark — `_hold_pending` пишет запись без базы.
- mutation-047 — StaleBaseRefusalTest::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others — сверка удержанной записи с базой снята.
- mutation-048 — StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base — флаш из `note` отбрасывает базу записи.
- mutation-049 — StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base — попутный флаш отбрасывает базу записи.
- mutation-050 — MatchingBaseSendTest::test_ac3_base_matching_origin_is_sent — база сравнивается с blob'ом нового содержимого, не origin.
- mutation-051 — NewFileBaseTest::test_ac4_new_file_absent_in_origin_is_sent — отметка «файла не было» пишется пустой строкой.
- mutation-052 — NewFileBaseTest::test_ac4_new_file_appeared_in_origin_is_refused — отметка «файла не было» читается как «базы нет».
- mutation-053 — LegacyRecordTest::test_ac6_legacy_record_pin_matches_is_sent_with_warning, LegacyRecordTest::test_ac6_legacy_record_pin_differs_is_refused_with_warning — предупреждение `NO_BASE_WARNING` снято.
- mutation-054 — PendingListTest::test_ac7_pending_lists_each_record_with_truncated_content — выдержка `note --pending` без обрезки.
- mutation-055 — DropPendingTest::test_ac8_drop_pending_removes_exactly_one_and_journals — запись журнала о снятии убрана.
- mutation-056 — RoleRefusalTest::test_ac9_pending_and_drop_pending_refuse_under_role — рубеж роли `note` перенесён после веток `--pending`/`--drop-pending`.
- mutation-057 — NetworkHoldBaseTest::test_network_hold_stores_head_blob — база добавляется только на ветке окна тишины.
- mutation-058 — PendingLineTest::test_multiline_content_stays_one_line_and_truncated — выдержка без замены переводов строк.
- mutation-059 — PendingLineTest::test_empty_pending_says_so — пустой перечень ничего не печатает.
- mutation-060 — DropPendingRefusalTest::test_unknown_or_traversal_id_refuses_without_removal — id склеивается в путь без сверки с перечнем.
- mutation-061 — KnowledgeCommitTest::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite — `_doc_commit_prefix`: путь `knowledge/` получает префикс конфигурации.
- mutation-062 — KnowledgeCommitTest::test_ac14_knowledge_paths_not_in_config_paths — системный файл карточек внесён в `DOC_COMMIT_CONFIG_PATHS`.
- mutation-063 — KnowledgeCommitTest::test_ac14_invalid_form_refused_without_commit_or_hold — проверка формы карточек перенесена в `_build_doc_commit`.
- mutation-064 — KnowledgeCommitTest::test_ac14_nested_and_non_yaml_paths_refused — допуск `knowledge/` по префиксу без уровня и суффикса.
- mutation-065 — KnowledgeCommitTest::test_ac14_role_environment_refused — рубеж роли пропускает файлы карточек.
- mutation-066 — KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before — проверка формы карточек на всех путях `doc-commit`.
- mutation-067 — ConfigRecordNoBaseWarningTest::test_explicit_flush_warns_about_missing_base_of_config_record — ветка `_suite_gate_applies` в `_flush_pending` уходит в `continue` до проверки базы.
- mutation-068 — ConfigRecordNoBaseWarningTest::test_opportunistic_flush_still_skips_config_record_silently_on_base — предупреждение о базе вынесено до проверки `explicit`.
- mutation-069 — BatchWriteFailureTest::test_half_written_record_does_not_become_batch_head_for_next — в `except OSError` `_flush_batch` снято восстановление дерева.
- mutation-070 — GateRefusalLeavesNoDirtTest::test_dirty_work_tree_is_forced_to_origin_before_the_next_record (переписанная заявка) — проверка кода возврата `checkout` в `_fetch_and_build` перевёрнута.
- mutation-071 — GateRefusalLeavesNoDirtTest::test_leftover_file_in_the_work_tree_is_not_read_as_origin_content (переписанная заявка) — `_write_doc` не заводит каталог нового пути.

## Находки

- mutation-015 — находка: не убита ни «до», ни «после»; рабочий репозиторий — клон артели, в стенде он есть до вызова, ранний `_ensure_work_repo()` ненаблюдаем. В доказательство не входит.
- mutation-041 — находка: не убита ни «до», ни «после»; клон стенда перед `checkout` чист, `-f` ненаблюдаем. В доказательство не входит.
- mutation-042 — находка: не убита ни «до», ни «после»; после принудительного `checkout` файл дерева равен origin, сверка по нему неотличима. В доказательство не входит.
- Тесты этих заявок не удалены: их строки «Ловит мутацию» в новом файле переписаны на патчи 017, 070, 071 (убиты «до» и «после»).

## Падения подготовки

Узлов, убитых только падением подготовки песочницы (`setUp` классов
исходников, фикстуры нового файла), нет ни «до», ни «после»: в логах
прогонов (`.artel/logs/suite-run/<id>/…-mutation-run-<N>-p<nnn>.log`)
нет ни одной строки с `setUp` или `ERROR at setup`; исхода «ошибка
сбора, импорта или setup» нет ни в одной таблице.

## Удалённые дубли

Нет: все 71 тест шести исходных файлов перенесены функциями нового файла
под прежними именами.

## Числа до и после

- До: 6 файлов, 71 тест, 2271 строка, адресный прогон 48.88 с
  (`python3 -m pytest <шесть файлов> -p no:cacheprovider -p timeout`).
- После: 1 файл, 71 тестовая функция (88 узлов с вариантами
  `parametrize`), 2214 строк, адресный прогон 35.08 с.

## Мутации до

### Часть 1 (патчи 1-24)

```text
--- таблица /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5PCB66D936FDGG7H09CVGA1/01M5PCB66D936FDGG7H09CVGA1-mutation-run-1.mutations.tsv ---
# mutation-run №1 задачи 01M5PCB66D936FDGG7H09CVGA1
# источник патчей: каталог на диске
# ревизия прогона: base 549e997ec89bb9b448980d71066a37922b537b9f
# тесты: tests/test_doc_commit.py, tests/test_doc_commit_suite_gate.py, tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py, tests/test_doc_commit_held_base.py, tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py, tests/test_notes_batch_flush_edges.py
# патч 1 mutation-001.diff sha256 abbbe486f27f16124a6a6979a605111fba274dcbf75a12c933b6865acdafdbd6
# патч 2 mutation-002.diff sha256 85b5742da9e6dbca8a84168feb01a1c6d698c0e8261ea9923a5681d3e53601b4
# патч 3 mutation-003.diff sha256 ad9adebb08323a492ff3e6f388cf5a007e8007b48173478b0171c4328c93efea
# патч 4 mutation-004.diff sha256 70b684187a49387d5ab8510423c8e363e41a55d045b84d60f2a11d8e883093d0
# патч 5 mutation-005.diff sha256 2df277efe9739b66715dff14f109a6a9ab7aa49001e7230d5d7a93485f3028df
# патч 6 mutation-006.diff sha256 39e58a334031bde383abceb8f281793be6dec0171d5fb59b28446b5bbbe86e00
# патч 7 mutation-007.diff sha256 d40e6cba6637a11d1abfdda27832a9f685d91b97125527572198b3296cdbee6e
# патч 8 mutation-008.diff sha256 6886aea803441b034f1e17c91003ed89ec7b092c96f7926b18eff016bea956d8
# патч 9 mutation-009.diff sha256 ec793663aed4e2b1f3ba4e05b96e3e9d0a87a17b744cea7aed488185c7198b70
# патч 10 mutation-010.diff sha256 3c0701caf9a1fcfcfc9888405907f758410bae823465c8516264c91aad37bf5c
# патч 11 mutation-011.diff sha256 c28cae1c51469d563b51a9b55bba9be68c7d222bbf6bd5b8beef787a73820037
# патч 12 mutation-012.diff sha256 68cc8441976d671a4e9727500dfa7bfc9c727dddd5241b760ec440e3729e5cd5
# патч 13 mutation-013.diff sha256 bb2c27da00c6f06e9d614e7b089736f70a80e459ac9c21ceed0f659b1695e860
# патч 14 mutation-014.diff sha256 b001f3d05d683ffe2a6e978a909061ad43d37184ff76b3d4946c5aadada4d65b
# патч 15 mutation-015.diff sha256 f410d38271b14ff63407778fb19c291b27c54315842de40f65f9474b1fc396c0
# патч 16 mutation-016.diff sha256 2be48290941dff00fdbd9f29804e3f6a6818530353a3d57ada4ed59d93f2ab5f
# патч 17 mutation-017.diff sha256 6e7bcd205b47e5de281b214ac6c1b1e0be4c3e4f816f35ccad4ab97890590880
# патч 18 mutation-018.diff sha256 3047760581440cba993f444f3fc001f5c7352eed2a1e18acfd2be3c88c411530
# патч 19 mutation-019.diff sha256 1ee88e0e2da76ad3cfb59449d7fcfc4187df1dd46182da4236e606d1aa267874
# патч 20 mutation-020.diff sha256 a7995556b2933cb5390f18e7701d06dc2f5cc68f0ac913cc713895343e69901c
# патч 21 mutation-021.diff sha256 4c0fdc48e3d494ec9b990d11f4cc33a324e35ed5926c73eec8831bc5f22b4411
# патч 22 mutation-022.diff sha256 b3080cc1d5ec655cadc37313695618ba17783896bf793a58dbcceaba4a2c4a6c
# патч 23 mutation-023.diff sha256 a6a63317465878f2b3a199939b248fb7eb1f44b0bfade13c6be9619d96ddaca2
# патч 24 mutation-024.diff sha256 38d1c5ae5ab42e950ece2e27519edbb182872a2b88fbaa15e608ef46e20bddd9
номер	исход	узлы
1	убита	tests/test_doc_commit.py::PathRefusalTest::test_docs_paths_and_operator_config_are_allowed,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_unrunnable_suite_refuses_the_same_way,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_red_suite_refuses_naming_the_failed_test,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_green_suite_lets_the_commit_through,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_doc_commit.py::DocCommitPushTest::test_config_path_gets_config_prefix_docs_path_gets_docs_prefix,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_commits_and_journal_carries_path_and_reason,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_skips_the_run_entirely,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_green_suite_with_accept_red_still_journals_the_bypass,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_without_reason_refuses_by_substance_not_argparse,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_accept_red_record_is_sent_by_the_opportunistic_flush,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_opportunistic_flush_still_skips_config_record_silently_on_base,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_explicit_flush_warns_about_missing_base_of_config_record
2	убита	tests/test_doc_commit.py::DocCommitRefusalTest::test_backlog_path_refused_origin_keeps_backlog,tests/test_doc_commit.py::PathRefusalTest::test_backlog_is_refused_naming_note
3	убита	tests/test_doc_commit.py::PathRefusalTest::test_code_tests_skills_templates_tasks_refused_with_named_text,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_nested_and_non_yaml_paths_refused
4	убита	tests/test_doc_commit.py::PathRefusalTest::test_absolute_dotdot_empty_and_bare_docs_dir_refused
5	убита	tests/test_doc_commit.py::CommitMessageTest::test_prefix_by_path_kind_without_truncation,tests/test_doc_commit.py::DocCommitPushTest::test_config_path_gets_config_prefix_docs_path_gets_docs_prefix,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite
6	убита	tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit.py::DocCommitPushTest::test_bytes_preserved_crlf_not_translated,tests/test_doc_commit.py::DocCommitPushTest::test_content_lands_in_origin_output_names_sha_main_copy_untouched,tests/test_doc_commit.py::CommitMessageTest::test_target_rel_is_own_path_for_doc_commit_and_backlog_for_note,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_green_suite_lets_the_commit_through,tests/test_doc_commit.py::PinBaseCheckTest::test_new_path_absent_everywhere_is_committed,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_open_window_holds_json_with_kind_and_flush_after_close_pushes,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_skips_the_run_entirely,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_note_flush_sends_both_kinds,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_leftover_file_in_the_work_tree_is_not_read_as_origin_content,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_does_not_need_source_file_anymore,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_commits_and_journal_carries_path_and_reason,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_docs_path_does_not_run_the_suite_at_all,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_accept_red_record_is_sent_by_the_opportunistic_flush,tests/test_doc_commit_suite_gate.py::AcceptRedOnDocsPathTest::test_docs_path_accept_red_writes_no_bypass_journal_row,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::MatchingBaseSendTest::test_ac3_base_matching_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_absent_in_origin_is_sent,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_explicit_flush_warns_about_missing_base_of_config_record,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::LegacyRecordTest::test_ac6_legacy_record_pin_matches_is_sent_with_warning
7	убита	tests/test_doc_commit.py::DocCommitPushTest::test_content_lands_in_origin_output_names_sha_main_copy_untouched
8	убита	tests/test_doc_commit.py::DocCommitPushTest::test_bytes_preserved_crlf_not_translated
9	убита	tests/test_doc_commit.py::DocCommitPushTest::test_no_journal_row_for_doc_commit
10	убита	tests/test_doc_commit.py::CommitMessageTest::test_prefix_by_path_kind_without_truncation,tests/test_doc_commit.py::DocCommitPushTest::test_config_path_gets_config_prefix_docs_path_gets_docs_prefix,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before
11	убита	tests/test_doc_commit.py::DocCommitRefusalTest::test_backlog_path_refused_origin_keeps_backlog,tests/test_doc_commit.py::DocCommitRefusalTest::test_foreign_path_refused_without_commit_or_hold,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_nested_and_non_yaml_paths_refused
12	убита	tests/test_doc_commit.py::DocCommitRefusalTest::test_missing_message_refused_without_commit_or_hold
13	убита	tests/test_doc_commit.py::DocCommitRefusalTest::test_missing_or_absent_source_file_refused
14	убита	tests/test_doc_commit.py::DocCommitRefusalTest::test_identical_content_refused_instead_of_hanging_in_pending
15	не убита	
16	убита	tests/test_doc_commit.py::DocCommitRefusalTest::test_role_environment_refused_before_work_repo_exists,tests/test_doc_commit.py::DocCommitRefusalTest::test_role_environment_markers_from_env_are_honoured
17	убита	tests/test_doc_commit.py::DocCommitRefusalTest::test_role_environment_refused_before_work_repo_exists,tests/test_doc_commit.py::DocCommitRefusalTest::test_role_environment_markers_from_env_are_honoured,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_role_environment_refused
18	убита	tests/test_doc_commit.py::PinBaseCheckTest::test_origin_diverged_from_pin_refuses_naming_pin_update,tests/test_doc_commit.py::PinBaseCheckTest::test_path_added_in_origin_after_pin_refuses,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::ImmediatePinCheckTest::test_ac5_immediate_send_still_refuses_on_pin,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::LegacyRecordTest::test_ac6_legacy_record_pin_differs_is_refused_with_warning
19	убита	tests/test_doc_commit.py::PinBaseCheckTest::test_new_path_absent_everywhere_is_committed,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_leftover_file_in_the_work_tree_is_not_read_as_origin_content,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_absent_in_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_appeared_in_origin_is_refused,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::HeldRecordBaseTest::test_ac1_held_record_stores_pin_blob_or_absent_mark,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite
20	убита	tests/test_doc_commit.py::PinBaseCheckTest::test_path_added_in_origin_after_pin_refuses
21	убита	tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_ignores_open_window_but_new_record_is_still_held,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_open_window_holds_json_with_kind_and_flush_after_close_pushes,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_note_flush_sends_both_kinds,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::HeldRecordBaseTest::test_ac1_held_record_stores_pin_blob_or_absent_mark,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_absent_in_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::MatchingBaseSendTest::test_ac3_base_matching_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_appeared_in_origin_is_refused,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::RoleRefusalTest::test_ac9_pending_and_drop_pending_refuse_under_role,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::DropPendingTest::test_ac8_drop_pending_removes_exactly_one_and_journals,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_opportunistic_flush_still_skips_config_record_silently_on_base,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_explicit_flush_warns_about_missing_base_of_config_record,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::PendingListTest::test_ac7_pending_lists_each_record_with_truncated_content
22	убита	tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_does_not_need_source_file_anymore
23	убита	tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_ignores_open_window_but_new_record_is_still_held,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_open_window_holds_json_with_kind_and_flush_after_close_pushes,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_note_flush_sends_both_kinds,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_does_not_need_source_file_anymore,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_accept_red_record_is_sent_by_the_opportunistic_flush,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_appeared_in_origin_is_refused,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::MatchingBaseSendTest::test_ac3_base_matching_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_absent_in_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::LegacyRecordTest::test_ac6_legacy_record_pin_matches_is_sent_with_warning,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::LegacyRecordTest::test_ac6_legacy_record_pin_differs_is_refused_with_warning
24	убита	tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_ignores_open_window_but_new_record_is_still_held
```

### Часть 2 (патчи 25-48)

```text
--- таблица /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5PCB66D936FDGG7H09CVGA1/01M5PCB66D936FDGG7H09CVGA1-mutation-run-2.mutations.tsv ---
# mutation-run №2 задачи 01M5PCB66D936FDGG7H09CVGA1
# источник патчей: каталог на диске
# ревизия прогона: base 549e997ec89bb9b448980d71066a37922b537b9f
# тесты: tests/test_doc_commit.py, tests/test_doc_commit_suite_gate.py, tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py, tests/test_doc_commit_held_base.py, tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py, tests/test_notes_batch_flush_edges.py
# патч 25 mutation-025.diff sha256 0a534e43d38bbfd94623f0267b00e40a0d991d9bc9c14455abcf047ccf9e314c
# патч 26 mutation-026.diff sha256 aa8034217aa5c89b41dec4aff46790d8d237cf08c38cb71fa5af1353ae803616
# патч 27 mutation-027.diff sha256 de115c455130a626834f4ebf0e6380597e821ad55696de6742604596f3aa0413
# патч 28 mutation-028.diff sha256 d4e80cec5c7a60c7309265cce1a32cde820c3a04f5eb41d8b948d7c0481b65f9
# патч 29 mutation-029.diff sha256 9339a00ff6b4403afc177f39f90a211f0a4712d84f3fb7ecadffed948b392900
# патч 30 mutation-030.diff sha256 3bb153defb41a92e5b3f44e2e1e4557ccfb0d0ca40af66fee5010a3c3becc790
# патч 31 mutation-031.diff sha256 87f688317bc18c226e0242beb05e47521da956f1d53d2d2ca7725e470ef1f07d
# патч 32 mutation-032.diff sha256 9418b781a54bd850d2bc4dc619644fa6fe01756271155120c530e147ea2cf6cb
# патч 33 mutation-033.diff sha256 9c38350ce39d527710a1d1f6878417a5ae924224e59a2077ca9645d69070145c
# патч 34 mutation-034.diff sha256 8dc0bf3f424bae633fecf6ee6d9a3c65dd8442051efa6e0f60d285ed17e3ae6b
# патч 35 mutation-035.diff sha256 165040f3e69065e18f44f23db6105e6d8079a7fbced1f9622977e02988a351e7
# патч 36 mutation-036.diff sha256 656c363d2797b086cd1162f35fe5246b6e119f9e911196c1141e1f15b8dc5b26
# патч 37 mutation-037.diff sha256 acfdf5fa3982cbf85d3cdf9af7117e3cd5266aa75b016bb9e4e02fff42103094
# патч 38 mutation-038.diff sha256 4518b97545224f68ab4057ec8dd199252e0b16a39f8a57da0107b753ddd3cfd8
# патч 39 mutation-039.diff sha256 93ba616ac75da1b993d19212ff5941d2fbf28c012d9fe0aaf5d81dc2652b6178
# патч 40 mutation-040.diff sha256 59009a5a7576c8e5c3ba31f7dccbbc72a2d14898b64463e9e26e7d829431df83
# патч 41 mutation-041.diff sha256 cfdb0fb850c4b9ba4934aa3e2feb42b197173d6e007c2547478a351719a76500
# патч 42 mutation-042.diff sha256 eb2ab9e0810a823694d3d1c9b072435e5c95a89ed91b346d369db1e2068d2de9
# патч 43 mutation-043.diff sha256 de67be8a5fb71e5680b83370d1e1b303979d2b060bfcbc321dd96e577738b001
# патч 44 mutation-044.diff sha256 7ddaebf809a0a442db192a2b92342466deba963b5d44aee7e9b7659e386de221
# патч 45 mutation-045.diff sha256 76d9daaca56e3a4163a796ffcc22dd8a3fca2e745b50ec33df82c6f6414a0881
# патч 46 mutation-046.diff sha256 8a39e4eb4afd593d54a1cb6b117497c20886489e67db24de0acf8495e55cc4d0
# патч 47 mutation-047.diff sha256 5414b6868b76cf37c82d649df08f47ae44cfe1bb4a7e80baea1b8d4b7e335c96
# патч 48 mutation-048.diff sha256 cff294497f40484f459137894438d415db31eeb24ff2691aee9f04f93ad8d3bb
номер	исход	узлы
25	убита	tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_ignores_open_window_but_new_record_is_still_held,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_note_flush_sends_both_kinds,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::HeldRecordBaseTest::test_ac1_held_record_stores_pin_blob_or_absent_mark,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::DropPendingTest::test_ac8_drop_pending_removes_exactly_one_and_journals
26	убита	tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_note_hold_texts_unchanged
27	убита	tests/test_doc_commit.py::DispatcherTest::test_artel_dispatches_doc_commit_with_rest_argv
28	убита	tests/test_doc_commit.py::DispatcherTest::test_help_text_names_doc_commit
29	убита	tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_red_suite_refuses_naming_the_failed_test,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_unrunnable_suite_refuses_the_same_way,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_note_reaches_origin_after_a_gate_refusal_and_a_foreign_change,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before
30	убита	tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_unrunnable_suite_refuses_the_same_way,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before
31	убита	tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_red_suite_refuses_naming_the_failed_test,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_unrunnable_suite_refuses_the_same_way,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_green_suite_lets_the_commit_through,tests/test_doc_commit.py::DocCommitPushTest::test_config_path_gets_config_prefix_docs_path_gets_docs_prefix,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_note_reaches_origin_after_a_gate_refusal_and_a_foreign_change,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_explicit_flush_warns_about_missing_base_of_config_record
32	убита	tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_suite_runs_on_the_tree_with_the_change_already_applied
33	убита	tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_docs_path_does_not_run_the_suite_at_all,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_absent_in_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::MatchingBaseSendTest::test_ac3_base_matching_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::LegacyRecordTest::test_ac6_legacy_record_pin_matches_is_sent_with_warning,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before
34	убита	tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_open_window_holds_the_record_and_the_gate_fires_on_flush
35	убита	tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_commits_and_journal_carries_path_and_reason,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_green_suite_with_accept_red_still_journals_the_bypass
36	убита	tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_skips_the_run_entirely,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_accept_red_record_is_sent_by_the_opportunistic_flush
37	убита	tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_without_reason_refuses_by_substance_not_argparse
38	убита	tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_commits_and_journal_carries_path_and_reason,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_green_suite_with_accept_red_still_journals_the_bypass
39	убита	tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_note_reaches_origin_after_a_gate_refusal_and_a_foreign_change
40	убита	tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_note_reaches_origin_after_a_gate_refusal_and_a_foreign_change
41	не убита	
42	не убита	
43	убита	tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_opportunistic_flush_still_skips_config_record_silently_on_base
44	убита	tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_accept_red_record_is_sent_by_the_opportunistic_flush
45	убита	tests/test_doc_commit_suite_gate.py::AcceptRedOnDocsPathTest::test_docs_path_accept_red_writes_no_bypass_journal_row
46	убита	tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::HeldRecordBaseTest::test_ac1_held_record_stores_pin_blob_or_absent_mark,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_appeared_in_origin_is_refused,tests/test_doc_commit_held_base.py::NetworkHoldBaseTest::test_network_hold_stores_head_blob
47	убита	tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_appeared_in_origin_is_refused
48	убита	tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base
```

### Часть 3 (патчи 49-71)

```text
--- таблица /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5PCB66D936FDGG7H09CVGA1/01M5PCB66D936FDGG7H09CVGA1-mutation-run-3.mutations.tsv ---
# mutation-run №3 задачи 01M5PCB66D936FDGG7H09CVGA1
# источник патчей: каталог на диске
# ревизия прогона: base 549e997ec89bb9b448980d71066a37922b537b9f
# тесты: tests/test_doc_commit.py, tests/test_doc_commit_suite_gate.py, tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py, tests/test_doc_commit_held_base.py, tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py, tests/test_notes_batch_flush_edges.py
# патч 49 mutation-049.diff sha256 9ac851234c0eb3151f05ec8055e7bcb1933c6148cc5b036e6755d10a36e34ade
# патч 50 mutation-050.diff sha256 9ee5bc3112bb835bddfb4b2ecabdb8cb55b74134cd2b50d50e73fdc5015dd7f6
# патч 51 mutation-051.diff sha256 c514808ac90f383bcd6a5eb14ff59c57b872e435edbf98af1a0b48039ec2cae8
# патч 52 mutation-052.diff sha256 cd6495c2abfa210b6753ca28e3f450fd435eb6c080d773343594a1b679b2da5a
# патч 53 mutation-053.diff sha256 ee13e4fee1976cc8c2286bb5d8dcea0b9eb35d34ca32814947741f9a2d44bf2d
# патч 54 mutation-054.diff sha256 3dc5a655324e871930e67f4d73f0f3030b98163af9b6bb4c6b73d38f7a64444f
# патч 55 mutation-055.diff sha256 5f5d112ae72b01f5a3fa9c9b5beabc585bb6caaf5ee5fd6e907da9ab230aa44b
# патч 56 mutation-056.diff sha256 6b176d3b038add347751b5be713726c54fc6db4468d2800ba13007894b327200
# патч 57 mutation-057.diff sha256 73ad044690eefa1b3285cbddc2985258c7ff19e3982a0c9618cd8ccf4b518f90
# патч 58 mutation-058.diff sha256 6d4d1c4d314a5ab3dcda89eaf7e61d5075f3935d71134aa0f40fcc6f239a5acd
# патч 59 mutation-059.diff sha256 afc9e0727a6b6e44361a274d389fb4a0725d9f848a481d70ac0d7c2e3ac5cc55
# патч 60 mutation-060.diff sha256 39096edc9118ea98fe02cdfe4f2f54215c88c2bb76567c0b356faa6cdcc957c4
# патч 61 mutation-061.diff sha256 3bd21ead9bd6046c6b003a33b3ee96c17cfabdffe0f5e4c72226061800e26ef3
# патч 62 mutation-062.diff sha256 4855f8e78ae93a8fc4d696445ab73355e6771e819b3e947a6017fb351742dde4
# патч 63 mutation-063.diff sha256 cddc466d6815224ebf74688d636ae5303ce1a1853c22d44143039a0061c77d36
# патч 64 mutation-064.diff sha256 23d714dd7b24b3df5f99ae2bb117464d83eb8935667dcefb4525e0bef4f7cad2
# патч 65 mutation-065.diff sha256 e15b52c0362636fb9185565300285bb4ae14c0e3647e7d10f148fad3d832e844
# патч 66 mutation-066.diff sha256 b3c7d491367b0f50db968dca074584743a866992905f91c43646357a584394da
# патч 67 mutation-067.diff sha256 56c94817d974019145b2f85a1649514e8d6a74b0f82cfd00fd3951ccfcbc5cbf
# патч 68 mutation-068.diff sha256 054fbf117306ea9e64b3872298f92c0364a3f646d5109d241eafd5181bf454c5
# патч 69 mutation-069.diff sha256 ea00b216f1ec8b6d49cdf647e545b1bb48e6f39a1d679c49491a150d93567b78
# патч 70 mutation-070.diff sha256 24f567ea0aae6cff55dc38af2f34e4526888aefc9b16b5308843daec58a46369
# патч 71 mutation-071.diff sha256 d8c297cf4a8620727be4607ace7fb6d4e2beb7f37a6e56d4c939ae1e8c92801e
номер	исход	узлы
49	убита	tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base
50	убита	tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_ignores_open_window_but_new_record_is_still_held,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_open_window_holds_json_with_kind_and_flush_after_close_pushes,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_note_flush_sends_both_kinds,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_does_not_need_source_file_anymore,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_absent_in_origin_is_sent,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::MatchingBaseSendTest::test_ac3_base_matching_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_accept_red_record_is_sent_by_the_opportunistic_flush
51	убита	tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_absent_in_origin_is_sent
52	убита	tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_appeared_in_origin_is_refused
53	убита	tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_explicit_flush_warns_about_missing_base_of_config_record,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::LegacyRecordTest::test_ac6_legacy_record_pin_differs_is_refused_with_warning,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::LegacyRecordTest::test_ac6_legacy_record_pin_matches_is_sent_with_warning
54	убита	tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::PendingListTest::test_ac7_pending_lists_each_record_with_truncated_content,tests/test_doc_commit_held_base.py::PendingLineTest::test_multiline_content_stays_one_line_and_truncated
55	убита	tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::DropPendingTest::test_ac8_drop_pending_removes_exactly_one_and_journals
56	убита	tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::RoleRefusalTest::test_ac9_pending_and_drop_pending_refuse_under_role
57	убита	tests/test_doc_commit_held_base.py::NetworkHoldBaseTest::test_network_hold_stores_head_blob
58	убита	tests/test_doc_commit_held_base.py::PendingLineTest::test_multiline_content_stays_one_line_and_truncated
59	убита	tests/test_doc_commit_held_base.py::PendingLineTest::test_empty_pending_says_so
60	убита	tests/test_doc_commit_held_base.py::DropPendingRefusalTest::test_unknown_or_traversal_id_refuses_without_removal
61	убита	tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite
62	убита	tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_knowledge_paths_not_in_config_paths
63	убита	tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_invalid_form_refused_without_commit_or_hold
64	убита	tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_nested_and_non_yaml_paths_refused
65	убита	tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_role_environment_refused
66	убита	tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_ignores_open_window_but_new_record_is_still_held,tests/test_doc_commit.py::DocCommitPushTest::test_content_lands_in_origin_output_names_sha_main_copy_untouched,tests/test_doc_commit.py::DocCommitRefusalTest::test_identical_content_refused_instead_of_hanging_in_pending,tests/test_doc_commit.py::PinBaseCheckTest::test_origin_diverged_from_pin_refuses_naming_pin_update,tests/test_doc_commit.py::DocCommitPushTest::test_bytes_preserved_crlf_not_translated,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_red_suite_refuses_naming_the_failed_test,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_unrunnable_suite_refuses_the_same_way,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_green_suite_lets_the_commit_through,tests/test_doc_commit.py::PinBaseCheckTest::test_new_path_absent_everywhere_is_committed,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_open_window_holds_json_with_kind_and_flush_after_close_pushes,tests/test_doc_commit.py::DocCommitPushTest::test_config_path_gets_config_prefix_docs_path_gets_docs_prefix,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_docs_path_does_not_run_the_suite_at_all,tests/test_doc_commit.py::DocCommitPushTest::test_no_journal_row_for_doc_commit,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_note_flush_sends_both_kinds,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_does_not_need_source_file_anymore,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_commits_and_journal_carries_path_and_reason,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_skips_the_run_entirely,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_leftover_file_in_the_work_tree_is_not_read_as_origin_content,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_green_suite_with_accept_red_still_journals_the_bypass,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_accept_red_record_is_sent_by_the_opportunistic_flush,tests/test_doc_commit_suite_gate.py::AcceptRedOnDocsPathTest::test_docs_path_accept_red_writes_no_bypass_journal_row,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::HeldRecordBaseTest::test_ac1_held_record_stores_pin_blob_or_absent_mark,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_absent_in_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_appeared_in_origin_is_refused,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::ImmediatePinCheckTest::test_ac5_immediate_send_still_refuses_on_pin,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::RoleRefusalTest::test_ac9_pending_and_drop_pending_refuse_under_role,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::DropPendingTest::test_ac8_drop_pending_removes_exactly_one_and_journals,tests/test_doc_commit_held_base.py::NetworkHoldBaseTest::test_network_hold_stores_head_blob,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::MatchingBaseSendTest::test_ac3_base_matching_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::PendingListTest::test_ac7_pending_lists_each_record_with_truncated_content,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_opportunistic_flush_still_skips_config_record_silently_on_base,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_explicit_flush_warns_about_missing_base_of_config_record,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before
67	убита	tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_explicit_flush_warns_about_missing_base_of_config_record
68	убита	tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_opportunistic_flush_still_skips_config_record_silently_on_base
69	убита	tests/test_notes_batch_flush_edges.py::BatchWriteFailureTest::test_half_written_record_does_not_become_batch_head_for_next
70	убита	tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_ignores_open_window_but_new_record_is_still_held,tests/test_doc_commit.py::DocCommitPushTest::test_bytes_preserved_crlf_not_translated,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_note_hold_texts_unchanged,tests/test_doc_commit.py::PinBaseCheckTest::test_origin_diverged_from_pin_refuses_naming_pin_update,tests/test_doc_commit.py::DocCommitPushTest::test_content_lands_in_origin_output_names_sha_main_copy_untouched,tests/test_doc_commit.py::DocCommitRefusalTest::test_identical_content_refused_instead_of_hanging_in_pending,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_green_suite_lets_the_commit_through,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_unrunnable_suite_refuses_the_same_way,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_red_suite_refuses_naming_the_failed_test,tests/test_doc_commit.py::PinBaseCheckTest::test_new_path_absent_everywhere_is_committed,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_does_not_need_source_file_anymore,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_note_flush_sends_both_kinds,tests/test_doc_commit.py::DocCommitPushTest::test_config_path_gets_config_prefix_docs_path_gets_docs_prefix,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_open_window_holds_json_with_kind_and_flush_after_close_pushes,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_docs_path_does_not_run_the_suite_at_all,tests/test_doc_commit.py::DocCommitPushTest::test_no_journal_row_for_doc_commit,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_commits_and_journal_carries_path_and_reason,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_skips_the_run_entirely,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_green_suite_with_accept_red_still_journals_the_bypass,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_leftover_file_in_the_work_tree_is_not_read_as_origin_content,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_dirty_work_tree_is_forced_to_origin_before_the_next_record,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_note_reaches_origin_after_a_gate_refusal_and_a_foreign_change,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_accept_red_record_is_sent_by_the_opportunistic_flush,tests/test_doc_commit_suite_gate.py::AcceptRedOnDocsPathTest::test_docs_path_accept_red_writes_no_bypass_journal_row,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::ImmediatePinCheckTest::test_ac5_immediate_send_still_refuses_on_pin,tests/test_notes_batch_flush_edges.py::BatchWriteFailureTest::test_half_written_record_does_not_become_batch_head_for_next,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_explicit_flush_warns_about_missing_base_of_config_record,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_opportunistic_flush_still_skips_config_record_silently_on_base,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before
71	убита	tests/test_doc_commit.py::PinBaseCheckTest::test_new_path_absent_everywhere_is_committed,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_leftover_file_in_the_work_tree_is_not_read_as_origin_content,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_absent_in_origin_is_sent,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite
```

### Повтор после подтяжки main, часть 1 (патчи 1-36)

```text
--- таблица /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5PCB66D936FDGG7H09CVGA1/01M5PCB66D936FDGG7H09CVGA1-mutation-run-6.mutations.tsv ---
# mutation-run №6 задачи 01M5PCB66D936FDGG7H09CVGA1
# источник патчей: каталог на диске
# ревизия прогона: base ed38d9879e02d12dc982d1979077b2c3c445382a
# тесты: tests/test_doc_commit.py, tests/test_doc_commit_suite_gate.py, tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py, tests/test_doc_commit_held_base.py, tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py, tests/test_notes_batch_flush_edges.py
# патч 1 mutation-001.diff sha256 abbbe486f27f16124a6a6979a605111fba274dcbf75a12c933b6865acdafdbd6
# патч 2 mutation-002.diff sha256 85b5742da9e6dbca8a84168feb01a1c6d698c0e8261ea9923a5681d3e53601b4
# патч 3 mutation-003.diff sha256 ad9adebb08323a492ff3e6f388cf5a007e8007b48173478b0171c4328c93efea
# патч 4 mutation-004.diff sha256 70b684187a49387d5ab8510423c8e363e41a55d045b84d60f2a11d8e883093d0
# патч 5 mutation-005.diff sha256 2df277efe9739b66715dff14f109a6a9ab7aa49001e7230d5d7a93485f3028df
# патч 6 mutation-006.diff sha256 39e58a334031bde383abceb8f281793be6dec0171d5fb59b28446b5bbbe86e00
# патч 7 mutation-007.diff sha256 d40e6cba6637a11d1abfdda27832a9f685d91b97125527572198b3296cdbee6e
# патч 8 mutation-008.diff sha256 6886aea803441b034f1e17c91003ed89ec7b092c96f7926b18eff016bea956d8
# патч 9 mutation-009.diff sha256 ec793663aed4e2b1f3ba4e05b96e3e9d0a87a17b744cea7aed488185c7198b70
# патч 10 mutation-010.diff sha256 3c0701caf9a1fcfcfc9888405907f758410bae823465c8516264c91aad37bf5c
# патч 11 mutation-011.diff sha256 c28cae1c51469d563b51a9b55bba9be68c7d222bbf6bd5b8beef787a73820037
# патч 12 mutation-012.diff sha256 68cc8441976d671a4e9727500dfa7bfc9c727dddd5241b760ec440e3729e5cd5
# патч 13 mutation-013.diff sha256 bb2c27da00c6f06e9d614e7b089736f70a80e459ac9c21ceed0f659b1695e860
# патч 14 mutation-014.diff sha256 b001f3d05d683ffe2a6e978a909061ad43d37184ff76b3d4946c5aadada4d65b
# патч 15 mutation-015.diff sha256 f410d38271b14ff63407778fb19c291b27c54315842de40f65f9474b1fc396c0
# патч 16 mutation-016.diff sha256 2be48290941dff00fdbd9f29804e3f6a6818530353a3d57ada4ed59d93f2ab5f
# патч 17 mutation-017.diff sha256 6e7bcd205b47e5de281b214ac6c1b1e0be4c3e4f816f35ccad4ab97890590880
# патч 18 mutation-018.diff sha256 3047760581440cba993f444f3fc001f5c7352eed2a1e18acfd2be3c88c411530
# патч 19 mutation-019.diff sha256 1ee88e0e2da76ad3cfb59449d7fcfc4187df1dd46182da4236e606d1aa267874
# патч 20 mutation-020.diff sha256 a7995556b2933cb5390f18e7701d06dc2f5cc68f0ac913cc713895343e69901c
# патч 21 mutation-021.diff sha256 4c0fdc48e3d494ec9b990d11f4cc33a324e35ed5926c73eec8831bc5f22b4411
# патч 22 mutation-022.diff sha256 b3080cc1d5ec655cadc37313695618ba17783896bf793a58dbcceaba4a2c4a6c
# патч 23 mutation-023.diff sha256 a6a63317465878f2b3a199939b248fb7eb1f44b0bfade13c6be9619d96ddaca2
# патч 24 mutation-024.diff sha256 38d1c5ae5ab42e950ece2e27519edbb182872a2b88fbaa15e608ef46e20bddd9
# патч 25 mutation-025.diff sha256 0a534e43d38bbfd94623f0267b00e40a0d991d9bc9c14455abcf047ccf9e314c
# патч 26 mutation-026.diff sha256 aa8034217aa5c89b41dec4aff46790d8d237cf08c38cb71fa5af1353ae803616
# патч 27 mutation-027.diff sha256 de115c455130a626834f4ebf0e6380597e821ad55696de6742604596f3aa0413
# патч 28 mutation-028.diff sha256 d4e80cec5c7a60c7309265cce1a32cde820c3a04f5eb41d8b948d7c0481b65f9
# патч 29 mutation-029.diff sha256 9339a00ff6b4403afc177f39f90a211f0a4712d84f3fb7ecadffed948b392900
# патч 30 mutation-030.diff sha256 3bb153defb41a92e5b3f44e2e1e4557ccfb0d0ca40af66fee5010a3c3becc790
# патч 31 mutation-031.diff sha256 87f688317bc18c226e0242beb05e47521da956f1d53d2d2ca7725e470ef1f07d
# патч 32 mutation-032.diff sha256 9418b781a54bd850d2bc4dc619644fa6fe01756271155120c530e147ea2cf6cb
# патч 33 mutation-033.diff sha256 9c38350ce39d527710a1d1f6878417a5ae924224e59a2077ca9645d69070145c
# патч 34 mutation-034.diff sha256 8dc0bf3f424bae633fecf6ee6d9a3c65dd8442051efa6e0f60d285ed17e3ae6b
# патч 35 mutation-035.diff sha256 165040f3e69065e18f44f23db6105e6d8079a7fbced1f9622977e02988a351e7
# патч 36 mutation-036.diff sha256 656c363d2797b086cd1162f35fe5246b6e119f9e911196c1141e1f15b8dc5b26
номер	исход	узлы
1	убита	tests/test_doc_commit.py::PathRefusalTest::test_docs_paths_and_operator_config_are_allowed,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_red_suite_refuses_naming_the_failed_test,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_green_suite_lets_the_commit_through,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_unrunnable_suite_refuses_the_same_way,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit.py::DocCommitPushTest::test_config_path_gets_config_prefix_docs_path_gets_docs_prefix,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_without_reason_refuses_by_substance_not_argparse,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_commits_and_journal_carries_path_and_reason,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_green_suite_with_accept_red_still_journals_the_bypass,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_skips_the_run_entirely,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_accept_red_record_is_sent_by_the_opportunistic_flush,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_explicit_flush_warns_about_missing_base_of_config_record,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_opportunistic_flush_still_skips_config_record_silently_on_base
2	убита	tests/test_doc_commit.py::DocCommitRefusalTest::test_backlog_path_refused_origin_keeps_backlog,tests/test_doc_commit.py::PathRefusalTest::test_backlog_is_refused_naming_note
3	убита	tests/test_doc_commit.py::PathRefusalTest::test_code_tests_skills_templates_tasks_refused_with_named_text,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_nested_and_non_yaml_paths_refused
4	убита	tests/test_doc_commit.py::PathRefusalTest::test_absolute_dotdot_empty_and_bare_docs_dir_refused
5	убита	tests/test_doc_commit.py::CommitMessageTest::test_prefix_by_path_kind_without_truncation,tests/test_doc_commit.py::DocCommitPushTest::test_config_path_gets_config_prefix_docs_path_gets_docs_prefix,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite
6	убита	tests/test_doc_commit.py::DocCommitPushTest::test_bytes_preserved_crlf_not_translated,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit.py::DocCommitPushTest::test_content_lands_in_origin_output_names_sha_main_copy_untouched,tests/test_doc_commit.py::CommitMessageTest::test_target_rel_is_own_path_for_doc_commit_and_backlog_for_note,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_green_suite_lets_the_commit_through,tests/test_doc_commit.py::PinBaseCheckTest::test_new_path_absent_everywhere_is_committed,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_open_window_holds_json_with_kind_and_flush_after_close_pushes,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_commits_and_journal_carries_path_and_reason,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_note_flush_sends_both_kinds,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_does_not_need_source_file_anymore,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_leftover_file_in_the_work_tree_is_not_read_as_origin_content,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_skips_the_run_entirely,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_accept_red_record_is_sent_by_the_opportunistic_flush,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_doc_commit_suite_gate.py::AcceptRedOnDocsPathTest::test_docs_path_accept_red_writes_no_bypass_journal_row,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::MatchingBaseSendTest::test_ac3_base_matching_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_absent_in_origin_is_sent,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_docs_path_does_not_run_the_suite_at_all,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::LegacyRecordTest::test_ac6_legacy_record_pin_matches_is_sent_with_warning,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_explicit_flush_warns_about_missing_base_of_config_record
7	убита	tests/test_doc_commit.py::DocCommitPushTest::test_content_lands_in_origin_output_names_sha_main_copy_untouched
8	убита	tests/test_doc_commit.py::DocCommitPushTest::test_bytes_preserved_crlf_not_translated
9	убита	tests/test_doc_commit.py::DocCommitPushTest::test_no_journal_row_for_doc_commit
10	убита	tests/test_doc_commit.py::CommitMessageTest::test_prefix_by_path_kind_without_truncation,tests/test_doc_commit.py::DocCommitPushTest::test_config_path_gets_config_prefix_docs_path_gets_docs_prefix,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before
11	убита	tests/test_doc_commit.py::DocCommitRefusalTest::test_backlog_path_refused_origin_keeps_backlog,tests/test_doc_commit.py::DocCommitRefusalTest::test_foreign_path_refused_without_commit_or_hold,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_nested_and_non_yaml_paths_refused
12	убита	tests/test_doc_commit.py::DocCommitRefusalTest::test_missing_message_refused_without_commit_or_hold
13	убита	tests/test_doc_commit.py::DocCommitRefusalTest::test_missing_or_absent_source_file_refused
14	убита	tests/test_doc_commit.py::DocCommitRefusalTest::test_identical_content_refused_instead_of_hanging_in_pending
15	не убита	
16	убита	tests/test_doc_commit.py::DocCommitRefusalTest::test_role_environment_refused_before_work_repo_exists,tests/test_doc_commit.py::DocCommitRefusalTest::test_role_environment_markers_from_env_are_honoured
17	убита	tests/test_doc_commit.py::DocCommitRefusalTest::test_role_environment_refused_before_work_repo_exists,tests/test_doc_commit.py::DocCommitRefusalTest::test_role_environment_markers_from_env_are_honoured,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_role_environment_refused
18	убита	tests/test_doc_commit.py::PinBaseCheckTest::test_origin_diverged_from_pin_refuses_naming_pin_update,tests/test_doc_commit.py::PinBaseCheckTest::test_path_added_in_origin_after_pin_refuses,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::LegacyRecordTest::test_ac6_legacy_record_pin_differs_is_refused_with_warning,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::ImmediatePinCheckTest::test_ac5_immediate_send_still_refuses_on_pin
19	убита	tests/test_doc_commit.py::PinBaseCheckTest::test_new_path_absent_everywhere_is_committed,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_leftover_file_in_the_work_tree_is_not_read_as_origin_content,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_absent_in_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::HeldRecordBaseTest::test_ac1_held_record_stores_pin_blob_or_absent_mark,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_appeared_in_origin_is_refused,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite
20	убита	tests/test_doc_commit.py::PinBaseCheckTest::test_path_added_in_origin_after_pin_refuses
21	убита	tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_ignores_open_window_but_new_record_is_still_held,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_open_window_holds_json_with_kind_and_flush_after_close_pushes,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_note_flush_sends_both_kinds,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::HeldRecordBaseTest::test_ac1_held_record_stores_pin_blob_or_absent_mark,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_absent_in_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::MatchingBaseSendTest::test_ac3_base_matching_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_appeared_in_origin_is_refused,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::DropPendingTest::test_ac8_drop_pending_removes_exactly_one_and_journals,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::PendingListTest::test_ac7_pending_lists_each_record_with_truncated_content,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::RoleRefusalTest::test_ac9_pending_and_drop_pending_refuse_under_role,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_opportunistic_flush_still_skips_config_record_silently_on_base,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_explicit_flush_warns_about_missing_base_of_config_record
22	убита	tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_does_not_need_source_file_anymore
23	убита	tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_ignores_open_window_but_new_record_is_still_held,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_open_window_holds_json_with_kind_and_flush_after_close_pushes,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_note_flush_sends_both_kinds,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_does_not_need_source_file_anymore,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_accept_red_record_is_sent_by_the_opportunistic_flush,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::MatchingBaseSendTest::test_ac3_base_matching_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_absent_in_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_appeared_in_origin_is_refused,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::LegacyRecordTest::test_ac6_legacy_record_pin_differs_is_refused_with_warning,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::LegacyRecordTest::test_ac6_legacy_record_pin_matches_is_sent_with_warning
24	убита	tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_ignores_open_window_but_new_record_is_still_held
25	убита	tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_ignores_open_window_but_new_record_is_still_held,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_note_flush_sends_both_kinds,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::HeldRecordBaseTest::test_ac1_held_record_stores_pin_blob_or_absent_mark,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::DropPendingTest::test_ac8_drop_pending_removes_exactly_one_and_journals
26	убита	tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_note_hold_texts_unchanged
27	убита	tests/test_doc_commit.py::DispatcherTest::test_artel_dispatches_doc_commit_with_rest_argv
28	убита	tests/test_doc_commit.py::DispatcherTest::test_help_text_names_doc_commit
29	убита	tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_unrunnable_suite_refuses_the_same_way,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_red_suite_refuses_naming_the_failed_test,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_note_reaches_origin_after_a_gate_refusal_and_a_foreign_change,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before
30	убита	tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_unrunnable_suite_refuses_the_same_way,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before
31	убита	tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_red_suite_refuses_naming_the_failed_test,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_unrunnable_suite_refuses_the_same_way,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_green_suite_lets_the_commit_through,tests/test_doc_commit.py::DocCommitPushTest::test_config_path_gets_config_prefix_docs_path_gets_docs_prefix,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_note_reaches_origin_after_a_gate_refusal_and_a_foreign_change,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_explicit_flush_warns_about_missing_base_of_config_record,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before
32	убита	tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_suite_runs_on_the_tree_with_the_change_already_applied
33	убита	tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_docs_path_does_not_run_the_suite_at_all,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::MatchingBaseSendTest::test_ac3_base_matching_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_absent_in_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::LegacyRecordTest::test_ac6_legacy_record_pin_matches_is_sent_with_warning,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base
34	убита	tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_open_window_holds_the_record_and_the_gate_fires_on_flush
35	убита	tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_commits_and_journal_carries_path_and_reason,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_green_suite_with_accept_red_still_journals_the_bypass
36	убита	tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_skips_the_run_entirely,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_accept_red_record_is_sent_by_the_opportunistic_flush
```

### Повтор после подтяжки main, часть 2 (патчи 37-71)

```text
--- таблица /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5PCB66D936FDGG7H09CVGA1/01M5PCB66D936FDGG7H09CVGA1-mutation-run-7.mutations.tsv ---
# mutation-run №7 задачи 01M5PCB66D936FDGG7H09CVGA1
# источник патчей: каталог на диске
# ревизия прогона: base ed38d9879e02d12dc982d1979077b2c3c445382a
# тесты: tests/test_doc_commit.py, tests/test_doc_commit_suite_gate.py, tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py, tests/test_doc_commit_held_base.py, tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py, tests/test_notes_batch_flush_edges.py
# патч 37 mutation-037.diff sha256 acfdf5fa3982cbf85d3cdf9af7117e3cd5266aa75b016bb9e4e02fff42103094
# патч 38 mutation-038.diff sha256 4518b97545224f68ab4057ec8dd199252e0b16a39f8a57da0107b753ddd3cfd8
# патч 39 mutation-039.diff sha256 93ba616ac75da1b993d19212ff5941d2fbf28c012d9fe0aaf5d81dc2652b6178
# патч 40 mutation-040.diff sha256 59009a5a7576c8e5c3ba31f7dccbbc72a2d14898b64463e9e26e7d829431df83
# патч 41 mutation-041.diff sha256 cfdb0fb850c4b9ba4934aa3e2feb42b197173d6e007c2547478a351719a76500
# патч 42 mutation-042.diff sha256 eb2ab9e0810a823694d3d1c9b072435e5c95a89ed91b346d369db1e2068d2de9
# патч 43 mutation-043.diff sha256 de67be8a5fb71e5680b83370d1e1b303979d2b060bfcbc321dd96e577738b001
# патч 44 mutation-044.diff sha256 7ddaebf809a0a442db192a2b92342466deba963b5d44aee7e9b7659e386de221
# патч 45 mutation-045.diff sha256 76d9daaca56e3a4163a796ffcc22dd8a3fca2e745b50ec33df82c6f6414a0881
# патч 46 mutation-046.diff sha256 8a39e4eb4afd593d54a1cb6b117497c20886489e67db24de0acf8495e55cc4d0
# патч 47 mutation-047.diff sha256 5414b6868b76cf37c82d649df08f47ae44cfe1bb4a7e80baea1b8d4b7e335c96
# патч 48 mutation-048.diff sha256 cff294497f40484f459137894438d415db31eeb24ff2691aee9f04f93ad8d3bb
# патч 49 mutation-049.diff sha256 9ac851234c0eb3151f05ec8055e7bcb1933c6148cc5b036e6755d10a36e34ade
# патч 50 mutation-050.diff sha256 9ee5bc3112bb835bddfb4b2ecabdb8cb55b74134cd2b50d50e73fdc5015dd7f6
# патч 51 mutation-051.diff sha256 c514808ac90f383bcd6a5eb14ff59c57b872e435edbf98af1a0b48039ec2cae8
# патч 52 mutation-052.diff sha256 cd6495c2abfa210b6753ca28e3f450fd435eb6c080d773343594a1b679b2da5a
# патч 53 mutation-053.diff sha256 ee13e4fee1976cc8c2286bb5d8dcea0b9eb35d34ca32814947741f9a2d44bf2d
# патч 54 mutation-054.diff sha256 3dc5a655324e871930e67f4d73f0f3030b98163af9b6bb4c6b73d38f7a64444f
# патч 55 mutation-055.diff sha256 5f5d112ae72b01f5a3fa9c9b5beabc585bb6caaf5ee5fd6e907da9ab230aa44b
# патч 56 mutation-056.diff sha256 6b176d3b038add347751b5be713726c54fc6db4468d2800ba13007894b327200
# патч 57 mutation-057.diff sha256 73ad044690eefa1b3285cbddc2985258c7ff19e3982a0c9618cd8ccf4b518f90
# патч 58 mutation-058.diff sha256 6d4d1c4d314a5ab3dcda89eaf7e61d5075f3935d71134aa0f40fcc6f239a5acd
# патч 59 mutation-059.diff sha256 afc9e0727a6b6e44361a274d389fb4a0725d9f848a481d70ac0d7c2e3ac5cc55
# патч 60 mutation-060.diff sha256 39096edc9118ea98fe02cdfe4f2f54215c88c2bb76567c0b356faa6cdcc957c4
# патч 61 mutation-061.diff sha256 3bd21ead9bd6046c6b003a33b3ee96c17cfabdffe0f5e4c72226061800e26ef3
# патч 62 mutation-062.diff sha256 4855f8e78ae93a8fc4d696445ab73355e6771e819b3e947a6017fb351742dde4
# патч 63 mutation-063.diff sha256 cddc466d6815224ebf74688d636ae5303ce1a1853c22d44143039a0061c77d36
# патч 64 mutation-064.diff sha256 23d714dd7b24b3df5f99ae2bb117464d83eb8935667dcefb4525e0bef4f7cad2
# патч 65 mutation-065.diff sha256 e15b52c0362636fb9185565300285bb4ae14c0e3647e7d10f148fad3d832e844
# патч 66 mutation-066.diff sha256 b3c7d491367b0f50db968dca074584743a866992905f91c43646357a584394da
# патч 67 mutation-067.diff sha256 56c94817d974019145b2f85a1649514e8d6a74b0f82cfd00fd3951ccfcbc5cbf
# патч 68 mutation-068.diff sha256 054fbf117306ea9e64b3872298f92c0364a3f646d5109d241eafd5181bf454c5
# патч 69 mutation-069.diff sha256 ea00b216f1ec8b6d49cdf647e545b1bb48e6f39a1d679c49491a150d93567b78
# патч 70 mutation-070.diff sha256 24f567ea0aae6cff55dc38af2f34e4526888aefc9b16b5308843daec58a46369
# патч 71 mutation-071.diff sha256 d8c297cf4a8620727be4607ace7fb6d4e2beb7f37a6e56d4c939ae1e8c92801e
номер	исход	узлы
37	убита	tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_without_reason_refuses_by_substance_not_argparse
38	убита	tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_green_suite_with_accept_red_still_journals_the_bypass,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_commits_and_journal_carries_path_and_reason
39	убита	tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_note_reaches_origin_after_a_gate_refusal_and_a_foreign_change,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_repeat_after_fixing_the_suite_commits_the_same_change
40	убита	tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_note_reaches_origin_after_a_gate_refusal_and_a_foreign_change
41	не убита	
42	не убита	
43	убита	tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_opportunistic_flush_still_skips_config_record_silently_on_base
44	убита	tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_accept_red_record_is_sent_by_the_opportunistic_flush
45	убита	tests/test_doc_commit_suite_gate.py::AcceptRedOnDocsPathTest::test_docs_path_accept_red_writes_no_bypass_journal_row
46	убита	tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::HeldRecordBaseTest::test_ac1_held_record_stores_pin_blob_or_absent_mark,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_appeared_in_origin_is_refused,tests/test_doc_commit_held_base.py::NetworkHoldBaseTest::test_network_hold_stores_head_blob
47	убита	tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_appeared_in_origin_is_refused
48	убита	tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base
49	убита	tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base
50	убита	tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_ignores_open_window_but_new_record_is_still_held,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_open_window_holds_json_with_kind_and_flush_after_close_pushes,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_note_flush_sends_both_kinds,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_does_not_need_source_file_anymore,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_accept_red_record_is_sent_by_the_opportunistic_flush,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_absent_in_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::MatchingBaseSendTest::test_ac3_base_matching_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others
51	убита	tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_absent_in_origin_is_sent
52	убита	tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_appeared_in_origin_is_refused
53	убита	tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::LegacyRecordTest::test_ac6_legacy_record_pin_matches_is_sent_with_warning,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::LegacyRecordTest::test_ac6_legacy_record_pin_differs_is_refused_with_warning,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_explicit_flush_warns_about_missing_base_of_config_record
54	убита	tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::PendingListTest::test_ac7_pending_lists_each_record_with_truncated_content,tests/test_doc_commit_held_base.py::PendingLineTest::test_multiline_content_stays_one_line_and_truncated
55	убита	tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::DropPendingTest::test_ac8_drop_pending_removes_exactly_one_and_journals
56	убита	tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::RoleRefusalTest::test_ac9_pending_and_drop_pending_refuse_under_role
57	убита	tests/test_doc_commit_held_base.py::NetworkHoldBaseTest::test_network_hold_stores_head_blob
58	убита	tests/test_doc_commit_held_base.py::PendingLineTest::test_multiline_content_stays_one_line_and_truncated
59	убита	tests/test_doc_commit_held_base.py::PendingLineTest::test_empty_pending_says_so
60	убита	tests/test_doc_commit_held_base.py::DropPendingRefusalTest::test_unknown_or_traversal_id_refuses_without_removal
61	убита	tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite
62	убита	tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_knowledge_paths_not_in_config_paths
63	убита	tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_invalid_form_refused_without_commit_or_hold
64	убита	tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_nested_and_non_yaml_paths_refused
65	убита	tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_role_environment_refused
66	убита	tests/test_doc_commit.py::DocCommitPushTest::test_bytes_preserved_crlf_not_translated,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_ignores_open_window_but_new_record_is_still_held,tests/test_doc_commit.py::DocCommitPushTest::test_content_lands_in_origin_output_names_sha_main_copy_untouched,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit.py::PinBaseCheckTest::test_origin_diverged_from_pin_refuses_naming_pin_update,tests/test_doc_commit.py::DocCommitRefusalTest::test_identical_content_refused_instead_of_hanging_in_pending,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_unrunnable_suite_refuses_the_same_way,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_red_suite_refuses_naming_the_failed_test,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_green_suite_lets_the_commit_through,tests/test_doc_commit.py::PinBaseCheckTest::test_new_path_absent_everywhere_is_committed,tests/test_doc_commit.py::DocCommitPushTest::test_config_path_gets_config_prefix_docs_path_gets_docs_prefix,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_note_flush_sends_both_kinds,tests/test_doc_commit.py::DocCommitPushTest::test_no_journal_row_for_doc_commit,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_open_window_holds_json_with_kind_and_flush_after_close_pushes,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_does_not_need_source_file_anymore,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_docs_path_does_not_run_the_suite_at_all,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_commits_and_journal_carries_path_and_reason,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_green_suite_with_accept_red_still_journals_the_bypass,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_skips_the_run_entirely,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_leftover_file_in_the_work_tree_is_not_read_as_origin_content,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_accept_red_record_is_sent_by_the_opportunistic_flush,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_doc_commit_suite_gate.py::AcceptRedOnDocsPathTest::test_docs_path_accept_red_writes_no_bypass_journal_row,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_note_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::HeldRecordBaseTest::test_ac1_held_record_stores_pin_blob_or_absent_mark,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::MatchingBaseSendTest::test_ac3_base_matching_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_absent_in_origin_is_sent,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::ImmediatePinCheckTest::test_ac5_immediate_send_still_refuses_on_pin,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::DropPendingTest::test_ac8_drop_pending_removes_exactly_one_and_journals,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::StaleBaseRefusalTest::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::RoleRefusalTest::test_ac9_pending_and_drop_pending_refuse_under_role,tests/test_doc_commit_held_base.py::NetworkHoldBaseTest::test_network_hold_stores_head_blob,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_appeared_in_origin_is_refused,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::PendingListTest::test_ac7_pending_lists_each_record_with_truncated_content,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_explicit_flush_warns_about_missing_base_of_config_record,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_opportunistic_flush_still_skips_config_record_silently_on_base
67	убита	tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_explicit_flush_warns_about_missing_base_of_config_record
68	убита	tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_opportunistic_flush_still_skips_config_record_silently_on_base
69	убита	tests/test_notes_batch_flush_edges.py::BatchWriteFailureTest::test_half_written_record_does_not_become_batch_head_for_next
70	убита	tests/test_doc_commit.py::DocCommitPushTest::test_content_lands_in_origin_output_names_sha_main_copy_untouched,tests/test_doc_commit.py::DocCommitRefusalTest::test_identical_content_refused_instead_of_hanging_in_pending,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_ignores_open_window_but_new_record_is_still_held,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_note_hold_texts_unchanged,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit.py::PinBaseCheckTest::test_origin_diverged_from_pin_refuses_naming_pin_update,tests/test_doc_commit.py::DocCommitPushTest::test_bytes_preserved_crlf_not_translated,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_unrunnable_suite_refuses_the_same_way,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_green_suite_lets_the_commit_through,tests/test_doc_commit_suite_gate.py::RedSuiteTest::test_red_suite_refuses_naming_the_failed_test,tests/test_doc_commit.py::PinBaseCheckTest::test_new_path_absent_everywhere_is_committed,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_open_window_holds_json_with_kind_and_flush_after_close_pushes,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_flush_does_not_need_source_file_anymore,tests/test_doc_commit.py::DocCommitPushTest::test_no_journal_row_for_doc_commit,tests/test_doc_commit.py::DocCommitPushTest::test_config_path_gets_config_prefix_docs_path_gets_docs_prefix,tests/test_doc_commit.py::SilenceWindowAndFlushTest::test_note_flush_sends_both_kinds,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_docs_path_does_not_run_the_suite_at_all,tests/test_doc_commit_suite_gate.py::SuiteTreeTest::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_commits_and_journal_carries_path_and_reason,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_accept_red_skips_the_run_entirely,tests/test_doc_commit_suite_gate.py::AcceptRedTest::test_green_suite_with_accept_red_still_journals_the_bypass,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_dirty_work_tree_is_forced_to_origin_before_the_next_record,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_note_reaches_origin_after_a_gate_refusal_and_a_foreign_change,tests/test_doc_commit_suite_gate.py::AcceptRedOnDocsPathTest::test_docs_path_accept_red_writes_no_bypass_journal_row,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_doc_commit_suite_gate.py::HeldConfigRecordFlushTest::test_accept_red_record_is_sent_by_the_opportunistic_flush,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_leftover_file_in_the_work_tree_is_not_read_as_origin_content,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::ImmediatePinCheckTest::test_ac5_immediate_send_still_refuses_on_pin,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite,tests/test_notes_batch_flush_edges.py::BatchWriteFailureTest::test_half_written_record_does_not_become_batch_head_for_next,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_explicit_flush_warns_about_missing_base_of_config_record,tests/test_notes_batch_flush_edges.py::ConfigRecordNoBaseWarningTest::test_opportunistic_flush_still_skips_config_record_silently_on_base,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_previous_paths_behave_as_before
71	убита	tests/test_doc_commit.py::PinBaseCheckTest::test_new_path_absent_everywhere_is_committed,tests/test_doc_commit_suite_gate.py::GateRefusalLeavesNoDirtTest::test_leftover_file_in_the_work_tree_is_not_read_as_origin_content,tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py::NewFileBaseTest::test_ac4_new_file_absent_in_origin_is_sent,tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py::KnowledgeCommitTest::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite
```

## Мутации после

### Часть 1 (патчи 1-36)

```text
--- таблица /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5PCB66D936FDGG7H09CVGA1/01M5PCB66D936FDGG7H09CVGA1-mutation-run-4.mutations.tsv ---
# mutation-run №4 задачи 01M5PCB66D936FDGG7H09CVGA1
# источник патчей: каталог на диске
# ревизия прогона: worktree ca098937dfb44f24403aca81dba10a0a01acdf07
# тесты: tests/test_doc_commit_module.py
# патч 1 mutation-001.diff sha256 abbbe486f27f16124a6a6979a605111fba274dcbf75a12c933b6865acdafdbd6
# патч 2 mutation-002.diff sha256 85b5742da9e6dbca8a84168feb01a1c6d698c0e8261ea9923a5681d3e53601b4
# патч 3 mutation-003.diff sha256 ad9adebb08323a492ff3e6f388cf5a007e8007b48173478b0171c4328c93efea
# патч 4 mutation-004.diff sha256 70b684187a49387d5ab8510423c8e363e41a55d045b84d60f2a11d8e883093d0
# патч 5 mutation-005.diff sha256 2df277efe9739b66715dff14f109a6a9ab7aa49001e7230d5d7a93485f3028df
# патч 6 mutation-006.diff sha256 39e58a334031bde383abceb8f281793be6dec0171d5fb59b28446b5bbbe86e00
# патч 7 mutation-007.diff sha256 d40e6cba6637a11d1abfdda27832a9f685d91b97125527572198b3296cdbee6e
# патч 8 mutation-008.diff sha256 6886aea803441b034f1e17c91003ed89ec7b092c96f7926b18eff016bea956d8
# патч 9 mutation-009.diff sha256 ec793663aed4e2b1f3ba4e05b96e3e9d0a87a17b744cea7aed488185c7198b70
# патч 10 mutation-010.diff sha256 3c0701caf9a1fcfcfc9888405907f758410bae823465c8516264c91aad37bf5c
# патч 11 mutation-011.diff sha256 c28cae1c51469d563b51a9b55bba9be68c7d222bbf6bd5b8beef787a73820037
# патч 12 mutation-012.diff sha256 68cc8441976d671a4e9727500dfa7bfc9c727dddd5241b760ec440e3729e5cd5
# патч 13 mutation-013.diff sha256 bb2c27da00c6f06e9d614e7b089736f70a80e459ac9c21ceed0f659b1695e860
# патч 14 mutation-014.diff sha256 b001f3d05d683ffe2a6e978a909061ad43d37184ff76b3d4946c5aadada4d65b
# патч 15 mutation-015.diff sha256 f410d38271b14ff63407778fb19c291b27c54315842de40f65f9474b1fc396c0
# патч 16 mutation-016.diff sha256 2be48290941dff00fdbd9f29804e3f6a6818530353a3d57ada4ed59d93f2ab5f
# патч 17 mutation-017.diff sha256 6e7bcd205b47e5de281b214ac6c1b1e0be4c3e4f816f35ccad4ab97890590880
# патч 18 mutation-018.diff sha256 3047760581440cba993f444f3fc001f5c7352eed2a1e18acfd2be3c88c411530
# патч 19 mutation-019.diff sha256 1ee88e0e2da76ad3cfb59449d7fcfc4187df1dd46182da4236e606d1aa267874
# патч 20 mutation-020.diff sha256 a7995556b2933cb5390f18e7701d06dc2f5cc68f0ac913cc713895343e69901c
# патч 21 mutation-021.diff sha256 4c0fdc48e3d494ec9b990d11f4cc33a324e35ed5926c73eec8831bc5f22b4411
# патч 22 mutation-022.diff sha256 b3080cc1d5ec655cadc37313695618ba17783896bf793a58dbcceaba4a2c4a6c
# патч 23 mutation-023.diff sha256 a6a63317465878f2b3a199939b248fb7eb1f44b0bfade13c6be9619d96ddaca2
# патч 24 mutation-024.diff sha256 38d1c5ae5ab42e950ece2e27519edbb182872a2b88fbaa15e608ef46e20bddd9
# патч 25 mutation-025.diff sha256 0a534e43d38bbfd94623f0267b00e40a0d991d9bc9c14455abcf047ccf9e314c
# патч 26 mutation-026.diff sha256 aa8034217aa5c89b41dec4aff46790d8d237cf08c38cb71fa5af1353ae803616
# патч 27 mutation-027.diff sha256 de115c455130a626834f4ebf0e6380597e821ad55696de6742604596f3aa0413
# патч 28 mutation-028.diff sha256 d4e80cec5c7a60c7309265cce1a32cde820c3a04f5eb41d8b948d7c0481b65f9
# патч 29 mutation-029.diff sha256 9339a00ff6b4403afc177f39f90a211f0a4712d84f3fb7ecadffed948b392900
# патч 30 mutation-030.diff sha256 3bb153defb41a92e5b3f44e2e1e4557ccfb0d0ca40af66fee5010a3c3becc790
# патч 31 mutation-031.diff sha256 87f688317bc18c226e0242beb05e47521da956f1d53d2d2ca7725e470ef1f07d
# патч 32 mutation-032.diff sha256 9418b781a54bd850d2bc4dc619644fa6fe01756271155120c530e147ea2cf6cb
# патч 33 mutation-033.diff sha256 9c38350ce39d527710a1d1f6878417a5ae924224e59a2077ca9645d69070145c
# патч 34 mutation-034.diff sha256 8dc0bf3f424bae633fecf6ee6d9a3c65dd8442051efa6e0f60d285ed17e3ae6b
# патч 35 mutation-035.diff sha256 165040f3e69065e18f44f23db6105e6d8079a7fbced1f9622977e02988a351e7
# патч 36 mutation-036.diff sha256 656c363d2797b086cd1162f35fe5246b6e119f9e911196c1141e1f15b8dc5b26
номер	исход	узлы
1	убита	tests/test_doc_commit_module.py::test_docs_paths_and_operator_config_are_allowed[models.yaml],tests/test_doc_commit_module.py::test_docs_paths_and_operator_config_are_allowed[gates.yaml],tests/test_doc_commit_module.py::test_docs_paths_and_operator_config_are_allowed[roles.yaml],tests/test_doc_commit_module.py::test_docs_paths_and_operator_config_are_allowed[targets.yaml],tests/test_doc_commit_module.py::test_config_path_gets_config_prefix_docs_path_gets_docs_prefix,tests/test_doc_commit_module.py::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit_module.py::test_unrunnable_suite_refuses_the_same_way,tests/test_doc_commit_module.py::test_green_suite_lets_the_commit_through,tests/test_doc_commit_module.py::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_doc_commit_module.py::test_red_suite_refuses_naming_the_failed_test,tests/test_doc_commit_module.py::test_green_suite_with_accept_red_still_journals_the_bypass,tests/test_doc_commit_module.py::test_accept_red_without_reason_refuses_by_substance_not_argparse,tests/test_doc_commit_module.py::test_opportunistic_flush_still_skips_config_record_silently_on_base,tests/test_doc_commit_module.py::test_accept_red_record_is_sent_by_the_opportunistic_flush,tests/test_doc_commit_module.py::test_accept_red_skips_the_run_entirely,tests/test_doc_commit_module.py::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_doc_commit_module.py::test_accept_red_commits_and_journal_carries_path_and_reason,tests/test_doc_commit_module.py::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_doc_commit_module.py::test_explicit_flush_warns_about_missing_base_of_config_record,tests/test_doc_commit_module.py::test_ac14_previous_paths_behave_as_before
2	убита	tests/test_doc_commit_module.py::test_backlog_is_refused_naming_note,tests/test_doc_commit_module.py::test_backlog_path_refused_origin_keeps_backlog
3	убита	tests/test_doc_commit_module.py::test_code_tests_skills_templates_tasks_refused_with_named_text[tasks/01M2XMCG167615YS9EZD9TYJWV/SPEC.md],tests/test_doc_commit_module.py::test_code_tests_skills_templates_tasks_refused_with_named_text[README.md],tests/test_doc_commit_module.py::test_code_tests_skills_templates_tasks_refused_with_named_text[skills/x.md],tests/test_doc_commit_module.py::test_code_tests_skills_templates_tasks_refused_with_named_text[templates/SPEC.md],tests/test_doc_commit_module.py::test_code_tests_skills_templates_tasks_refused_with_named_text[other.yaml],tests/test_doc_commit_module.py::test_ac14_nested_and_non_yaml_paths_refused
4	убита	tests/test_doc_commit_module.py::test_absolute_dotdot_empty_and_bare_docs_dir_refused[docs/../orchestrator/notes.py]
5	убита	tests/test_doc_commit_module.py::test_prefix_by_path_kind_without_truncation,tests/test_doc_commit_module.py::test_config_path_gets_config_prefix_docs_path_gets_docs_prefix,tests/test_doc_commit_module.py::test_ac14_previous_paths_behave_as_before,tests/test_doc_commit_module.py::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite
6	убита	tests/test_doc_commit_module.py::test_target_rel_is_own_path_for_doc_commit_and_backlog_for_note,tests/test_doc_commit_module.py::test_bytes_preserved_crlf_not_translated,tests/test_doc_commit_module.py::test_new_path_absent_everywhere_is_committed,tests/test_doc_commit_module.py::test_content_lands_in_origin_output_names_sha_main_copy_untouched,tests/test_doc_commit_module.py::test_open_window_holds_json_with_kind_and_flush_after_close_pushes,tests/test_doc_commit_module.py::test_flush_does_not_need_source_file_anymore,tests/test_doc_commit_module.py::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit_module.py::test_note_flush_sends_both_kinds,tests/test_doc_commit_module.py::test_green_suite_lets_the_commit_through,tests/test_doc_commit_module.py::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit_module.py::test_docs_path_does_not_run_the_suite_at_all,tests/test_doc_commit_module.py::test_accept_red_commits_and_journal_carries_path_and_reason,tests/test_doc_commit_module.py::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_doc_commit_module.py::test_accept_red_skips_the_run_entirely,tests/test_doc_commit_module.py::test_explicit_flush_warns_about_missing_base_of_config_record,tests/test_doc_commit_module.py::test_accept_red_record_is_sent_by_the_opportunistic_flush,tests/test_doc_commit_module.py::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_doc_commit_module.py::test_ac2_note_flush_refuses_stale_base,tests/test_doc_commit_module.py::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_doc_commit_module.py::test_ac4_new_file_absent_in_origin_is_sent,tests/test_doc_commit_module.py::test_ac6_legacy_record_pin_matches_is_sent_with_warning,tests/test_doc_commit_module.py::test_leftover_file_in_the_work_tree_is_not_read_as_origin_content,tests/test_doc_commit_module.py::test_docs_path_accept_red_writes_no_bypass_journal_row,tests/test_doc_commit_module.py::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite,tests/test_doc_commit_module.py::test_ac14_previous_paths_behave_as_before,tests/test_doc_commit_module.py::test_ac3_base_matching_origin_is_sent
7	убита	tests/test_doc_commit_module.py::test_content_lands_in_origin_output_names_sha_main_copy_untouched
8	убита	tests/test_doc_commit_module.py::test_bytes_preserved_crlf_not_translated
9	убита	tests/test_doc_commit_module.py::test_no_journal_row_for_doc_commit
10	убита	tests/test_doc_commit_module.py::test_prefix_by_path_kind_without_truncation,tests/test_doc_commit_module.py::test_config_path_gets_config_prefix_docs_path_gets_docs_prefix,tests/test_doc_commit_module.py::test_ac14_previous_paths_behave_as_before
11	убита	tests/test_doc_commit_module.py::test_backlog_path_refused_origin_keeps_backlog,tests/test_doc_commit_module.py::test_foreign_path_refused_without_commit_or_hold,tests/test_doc_commit_module.py::test_ac14_nested_and_non_yaml_paths_refused
12	убита	tests/test_doc_commit_module.py::test_missing_message_refused_without_commit_or_hold
13	убита	tests/test_doc_commit_module.py::test_missing_or_absent_source_file_refused
14	убита	tests/test_doc_commit_module.py::test_identical_content_refused_instead_of_hanging_in_pending
15	не убита	
16	убита	tests/test_doc_commit_module.py::test_role_environment_refused_before_work_repo_exists,tests/test_doc_commit_module.py::test_role_environment_markers_from_env_are_honoured
17	убита	tests/test_doc_commit_module.py::test_role_environment_refused_before_work_repo_exists,tests/test_doc_commit_module.py::test_role_environment_markers_from_env_are_honoured,tests/test_doc_commit_module.py::test_ac14_role_environment_refused
18	убита	tests/test_doc_commit_module.py::test_origin_diverged_from_pin_refuses_naming_pin_update,tests/test_doc_commit_module.py::test_path_added_in_origin_after_pin_refuses,tests/test_doc_commit_module.py::test_ac5_immediate_send_still_refuses_on_pin,tests/test_doc_commit_module.py::test_ac6_legacy_record_pin_differs_is_refused_with_warning
19	убита	tests/test_doc_commit_module.py::test_new_path_absent_everywhere_is_committed,tests/test_doc_commit_module.py::test_leftover_file_in_the_work_tree_is_not_read_as_origin_content,tests/test_doc_commit_module.py::test_ac1_held_record_stores_pin_blob_or_absent_mark,tests/test_doc_commit_module.py::test_ac4_new_file_appeared_in_origin_is_refused,tests/test_doc_commit_module.py::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite,tests/test_doc_commit_module.py::test_ac4_new_file_absent_in_origin_is_sent
20	убита	tests/test_doc_commit_module.py::test_path_added_in_origin_after_pin_refuses
21	убита	tests/test_doc_commit_module.py::test_open_window_holds_json_with_kind_and_flush_after_close_pushes,tests/test_doc_commit_module.py::test_note_flush_sends_both_kinds,tests/test_doc_commit_module.py::test_flush_ignores_open_window_but_new_record_is_still_held,tests/test_doc_commit_module.py::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit_module.py::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_doc_commit_module.py::test_explicit_flush_warns_about_missing_base_of_config_record,tests/test_doc_commit_module.py::test_opportunistic_flush_still_skips_config_record_silently_on_base,tests/test_doc_commit_module.py::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_doc_commit_module.py::test_ac2_note_flush_refuses_stale_base,tests/test_doc_commit_module.py::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_doc_commit_module.py::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_doc_commit_module.py::test_ac3_base_matching_origin_is_sent,tests/test_doc_commit_module.py::test_ac4_new_file_appeared_in_origin_is_refused,tests/test_doc_commit_module.py::test_ac7_pending_lists_each_record_with_truncated_content,tests/test_doc_commit_module.py::test_ac8_drop_pending_removes_exactly_one_and_journals,tests/test_doc_commit_module.py::test_ac9_pending_and_drop_pending_refuse_under_role,tests/test_doc_commit_module.py::test_ac4_new_file_absent_in_origin_is_sent,tests/test_doc_commit_module.py::test_ac1_held_record_stores_pin_blob_or_absent_mark
22	убита	tests/test_doc_commit_module.py::test_flush_does_not_need_source_file_anymore
23	убита	tests/test_doc_commit_module.py::test_flush_does_not_need_source_file_anymore,tests/test_doc_commit_module.py::test_open_window_holds_json_with_kind_and_flush_after_close_pushes,tests/test_doc_commit_module.py::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit_module.py::test_flush_ignores_open_window_but_new_record_is_still_held,tests/test_doc_commit_module.py::test_note_flush_sends_both_kinds,tests/test_doc_commit_module.py::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_doc_commit_module.py::test_ac3_base_matching_origin_is_sent,tests/test_doc_commit_module.py::test_ac2_note_flush_refuses_stale_base,tests/test_doc_commit_module.py::test_ac4_new_file_appeared_in_origin_is_refused,tests/test_doc_commit_module.py::test_ac4_new_file_absent_in_origin_is_sent,tests/test_doc_commit_module.py::test_ac6_legacy_record_pin_differs_is_refused_with_warning,tests/test_doc_commit_module.py::test_accept_red_record_is_sent_by_the_opportunistic_flush,tests/test_doc_commit_module.py::test_ac6_legacy_record_pin_matches_is_sent_with_warning,tests/test_doc_commit_module.py::test_ac2_opportunistic_flush_refuses_stale_base
24	убита	tests/test_doc_commit_module.py::test_flush_ignores_open_window_but_new_record_is_still_held,tests/test_doc_commit_module.py::test_doc_commit_flush_sends_both_kinds
25	убита	tests/test_doc_commit_module.py::test_note_flush_sends_both_kinds,tests/test_doc_commit_module.py::test_flush_ignores_open_window_but_new_record_is_still_held,tests/test_doc_commit_module.py::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit_module.py::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_doc_commit_module.py::test_ac2_note_flush_refuses_stale_base,tests/test_doc_commit_module.py::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_doc_commit_module.py::test_ac8_drop_pending_removes_exactly_one_and_journals,tests/test_doc_commit_module.py::test_ac1_held_record_stores_pin_blob_or_absent_mark
26	убита	tests/test_doc_commit_module.py::test_note_hold_texts_unchanged
27	убита	tests/test_doc_commit_module.py::test_artel_dispatches_doc_commit_with_rest_argv
28	убита	tests/test_doc_commit_module.py::test_help_text_names_doc_commit
29	убита	tests/test_doc_commit_module.py::test_red_suite_refuses_naming_the_failed_test,tests/test_doc_commit_module.py::test_unrunnable_suite_refuses_the_same_way,tests/test_doc_commit_module.py::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit_module.py::test_note_reaches_origin_after_a_gate_refusal_and_a_foreign_change,tests/test_doc_commit_module.py::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_doc_commit_module.py::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_doc_commit_module.py::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_doc_commit_module.py::test_ac14_previous_paths_behave_as_before
30	убита	tests/test_doc_commit_module.py::test_unrunnable_suite_refuses_the_same_way,tests/test_doc_commit_module.py::test_ac14_previous_paths_behave_as_before
31	убита	tests/test_doc_commit_module.py::test_config_path_gets_config_prefix_docs_path_gets_docs_prefix,tests/test_doc_commit_module.py::test_red_suite_refuses_naming_the_failed_test,tests/test_doc_commit_module.py::test_unrunnable_suite_refuses_the_same_way,tests/test_doc_commit_module.py::test_green_suite_lets_the_commit_through,tests/test_doc_commit_module.py::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit_module.py::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_doc_commit_module.py::test_note_reaches_origin_after_a_gate_refusal_and_a_foreign_change,tests/test_doc_commit_module.py::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_doc_commit_module.py::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_doc_commit_module.py::test_explicit_flush_warns_about_missing_base_of_config_record,tests/test_doc_commit_module.py::test_ac14_previous_paths_behave_as_before
32	убита	tests/test_doc_commit_module.py::test_suite_runs_on_the_tree_with_the_change_already_applied
33	убита	tests/test_doc_commit_module.py::test_docs_path_does_not_run_the_suite_at_all,tests/test_doc_commit_module.py::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_doc_commit_module.py::test_ac2_note_flush_refuses_stale_base,tests/test_doc_commit_module.py::test_ac6_legacy_record_pin_matches_is_sent_with_warning,tests/test_doc_commit_module.py::test_ac3_base_matching_origin_is_sent,tests/test_doc_commit_module.py::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_doc_commit_module.py::test_ac4_new_file_absent_in_origin_is_sent,tests/test_doc_commit_module.py::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite,tests/test_doc_commit_module.py::test_ac14_previous_paths_behave_as_before
34	убита	tests/test_doc_commit_module.py::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit_module.py::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_doc_commit_module.py::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks
35	убита	tests/test_doc_commit_module.py::test_green_suite_with_accept_red_still_journals_the_bypass,tests/test_doc_commit_module.py::test_accept_red_commits_and_journal_carries_path_and_reason
36	убита	tests/test_doc_commit_module.py::test_accept_red_skips_the_run_entirely,tests/test_doc_commit_module.py::test_accept_red_record_is_sent_by_the_opportunistic_flush
```

### Часть 2 (патчи 37-71)

```text
--- таблица /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5PCB66D936FDGG7H09CVGA1/01M5PCB66D936FDGG7H09CVGA1-mutation-run-5.mutations.tsv ---
# mutation-run №5 задачи 01M5PCB66D936FDGG7H09CVGA1
# источник патчей: каталог на диске
# ревизия прогона: worktree 6c4b867a314fc9819ba6d3a589977e924dccbe03
# тесты: tests/test_doc_commit_module.py
# патч 37 mutation-037.diff sha256 acfdf5fa3982cbf85d3cdf9af7117e3cd5266aa75b016bb9e4e02fff42103094
# патч 38 mutation-038.diff sha256 4518b97545224f68ab4057ec8dd199252e0b16a39f8a57da0107b753ddd3cfd8
# патч 39 mutation-039.diff sha256 93ba616ac75da1b993d19212ff5941d2fbf28c012d9fe0aaf5d81dc2652b6178
# патч 40 mutation-040.diff sha256 59009a5a7576c8e5c3ba31f7dccbbc72a2d14898b64463e9e26e7d829431df83
# патч 41 mutation-041.diff sha256 cfdb0fb850c4b9ba4934aa3e2feb42b197173d6e007c2547478a351719a76500
# патч 42 mutation-042.diff sha256 eb2ab9e0810a823694d3d1c9b072435e5c95a89ed91b346d369db1e2068d2de9
# патч 43 mutation-043.diff sha256 de67be8a5fb71e5680b83370d1e1b303979d2b060bfcbc321dd96e577738b001
# патч 44 mutation-044.diff sha256 7ddaebf809a0a442db192a2b92342466deba963b5d44aee7e9b7659e386de221
# патч 45 mutation-045.diff sha256 76d9daaca56e3a4163a796ffcc22dd8a3fca2e745b50ec33df82c6f6414a0881
# патч 46 mutation-046.diff sha256 8a39e4eb4afd593d54a1cb6b117497c20886489e67db24de0acf8495e55cc4d0
# патч 47 mutation-047.diff sha256 5414b6868b76cf37c82d649df08f47ae44cfe1bb4a7e80baea1b8d4b7e335c96
# патч 48 mutation-048.diff sha256 cff294497f40484f459137894438d415db31eeb24ff2691aee9f04f93ad8d3bb
# патч 49 mutation-049.diff sha256 9ac851234c0eb3151f05ec8055e7bcb1933c6148cc5b036e6755d10a36e34ade
# патч 50 mutation-050.diff sha256 9ee5bc3112bb835bddfb4b2ecabdb8cb55b74134cd2b50d50e73fdc5015dd7f6
# патч 51 mutation-051.diff sha256 c514808ac90f383bcd6a5eb14ff59c57b872e435edbf98af1a0b48039ec2cae8
# патч 52 mutation-052.diff sha256 cd6495c2abfa210b6753ca28e3f450fd435eb6c080d773343594a1b679b2da5a
# патч 53 mutation-053.diff sha256 ee13e4fee1976cc8c2286bb5d8dcea0b9eb35d34ca32814947741f9a2d44bf2d
# патч 54 mutation-054.diff sha256 3dc5a655324e871930e67f4d73f0f3030b98163af9b6bb4c6b73d38f7a64444f
# патч 55 mutation-055.diff sha256 5f5d112ae72b01f5a3fa9c9b5beabc585bb6caaf5ee5fd6e907da9ab230aa44b
# патч 56 mutation-056.diff sha256 6b176d3b038add347751b5be713726c54fc6db4468d2800ba13007894b327200
# патч 57 mutation-057.diff sha256 73ad044690eefa1b3285cbddc2985258c7ff19e3982a0c9618cd8ccf4b518f90
# патч 58 mutation-058.diff sha256 6d4d1c4d314a5ab3dcda89eaf7e61d5075f3935d71134aa0f40fcc6f239a5acd
# патч 59 mutation-059.diff sha256 afc9e0727a6b6e44361a274d389fb4a0725d9f848a481d70ac0d7c2e3ac5cc55
# патч 60 mutation-060.diff sha256 39096edc9118ea98fe02cdfe4f2f54215c88c2bb76567c0b356faa6cdcc957c4
# патч 61 mutation-061.diff sha256 3bd21ead9bd6046c6b003a33b3ee96c17cfabdffe0f5e4c72226061800e26ef3
# патч 62 mutation-062.diff sha256 4855f8e78ae93a8fc4d696445ab73355e6771e819b3e947a6017fb351742dde4
# патч 63 mutation-063.diff sha256 cddc466d6815224ebf74688d636ae5303ce1a1853c22d44143039a0061c77d36
# патч 64 mutation-064.diff sha256 23d714dd7b24b3df5f99ae2bb117464d83eb8935667dcefb4525e0bef4f7cad2
# патч 65 mutation-065.diff sha256 e15b52c0362636fb9185565300285bb4ae14c0e3647e7d10f148fad3d832e844
# патч 66 mutation-066.diff sha256 b3c7d491367b0f50db968dca074584743a866992905f91c43646357a584394da
# патч 67 mutation-067.diff sha256 56c94817d974019145b2f85a1649514e8d6a74b0f82cfd00fd3951ccfcbc5cbf
# патч 68 mutation-068.diff sha256 054fbf117306ea9e64b3872298f92c0364a3f646d5109d241eafd5181bf454c5
# патч 69 mutation-069.diff sha256 ea00b216f1ec8b6d49cdf647e545b1bb48e6f39a1d679c49491a150d93567b78
# патч 70 mutation-070.diff sha256 24f567ea0aae6cff55dc38af2f34e4526888aefc9b16b5308843daec58a46369
# патч 71 mutation-071.diff sha256 d8c297cf4a8620727be4607ace7fb6d4e2beb7f37a6e56d4c939ae1e8c92801e
номер	исход	узлы
37	убита	tests/test_doc_commit_module.py::test_accept_red_without_reason_refuses_by_substance_not_argparse
38	убита	tests/test_doc_commit_module.py::test_accept_red_commits_and_journal_carries_path_and_reason,tests/test_doc_commit_module.py::test_green_suite_with_accept_red_still_journals_the_bypass
39	убита	tests/test_doc_commit_module.py::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_doc_commit_module.py::test_note_reaches_origin_after_a_gate_refusal_and_a_foreign_change
40	убита	tests/test_doc_commit_module.py::test_note_reaches_origin_after_a_gate_refusal_and_a_foreign_change
41	не убита	
42	не убита	
43	убита	tests/test_doc_commit_module.py::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_doc_commit_module.py::test_opportunistic_flush_still_skips_config_record_silently_on_base
44	убита	tests/test_doc_commit_module.py::test_accept_red_record_is_sent_by_the_opportunistic_flush
45	убита	tests/test_doc_commit_module.py::test_docs_path_accept_red_writes_no_bypass_journal_row
46	убита	tests/test_doc_commit_module.py::test_ac1_held_record_stores_pin_blob_or_absent_mark,tests/test_doc_commit_module.py::test_ac2_note_flush_refuses_stale_base,tests/test_doc_commit_module.py::test_ac4_new_file_appeared_in_origin_is_refused,tests/test_doc_commit_module.py::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_doc_commit_module.py::test_network_hold_stores_head_blob,tests/test_doc_commit_module.py::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others
47	убита	tests/test_doc_commit_module.py::test_ac2_note_flush_refuses_stale_base,tests/test_doc_commit_module.py::test_ac4_new_file_appeared_in_origin_is_refused,tests/test_doc_commit_module.py::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_doc_commit_module.py::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others
48	убита	tests/test_doc_commit_module.py::test_ac2_note_flush_refuses_stale_base,tests/test_doc_commit_module.py::test_ac2_opportunistic_flush_refuses_stale_base
49	убита	tests/test_doc_commit_module.py::test_ac2_opportunistic_flush_refuses_stale_base
50	убита	tests/test_doc_commit_module.py::test_note_flush_sends_both_kinds,tests/test_doc_commit_module.py::test_flush_does_not_need_source_file_anymore,tests/test_doc_commit_module.py::test_open_window_holds_json_with_kind_and_flush_after_close_pushes,tests/test_doc_commit_module.py::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit_module.py::test_flush_ignores_open_window_but_new_record_is_still_held,tests/test_doc_commit_module.py::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_doc_commit_module.py::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_doc_commit_module.py::test_accept_red_record_is_sent_by_the_opportunistic_flush,tests/test_doc_commit_module.py::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_doc_commit_module.py::test_ac3_base_matching_origin_is_sent,tests/test_doc_commit_module.py::test_ac2_note_flush_refuses_stale_base,tests/test_doc_commit_module.py::test_ac4_new_file_absent_in_origin_is_sent,tests/test_doc_commit_module.py::test_ac2_opportunistic_flush_refuses_stale_base
51	убита	tests/test_doc_commit_module.py::test_ac4_new_file_absent_in_origin_is_sent
52	убита	tests/test_doc_commit_module.py::test_ac4_new_file_appeared_in_origin_is_refused
53	убита	tests/test_doc_commit_module.py::test_explicit_flush_warns_about_missing_base_of_config_record,tests/test_doc_commit_module.py::test_ac6_legacy_record_pin_matches_is_sent_with_warning,tests/test_doc_commit_module.py::test_ac6_legacy_record_pin_differs_is_refused_with_warning
54	убита	tests/test_doc_commit_module.py::test_multiline_content_stays_one_line_and_truncated,tests/test_doc_commit_module.py::test_ac7_pending_lists_each_record_with_truncated_content
55	убита	tests/test_doc_commit_module.py::test_ac8_drop_pending_removes_exactly_one_and_journals
56	убита	tests/test_doc_commit_module.py::test_ac9_pending_and_drop_pending_refuse_under_role
57	убита	tests/test_doc_commit_module.py::test_network_hold_stores_head_blob
58	убита	tests/test_doc_commit_module.py::test_multiline_content_stays_one_line_and_truncated
59	убита	tests/test_doc_commit_module.py::test_empty_pending_says_so
60	убита	tests/test_doc_commit_module.py::test_unknown_or_traversal_id_refuses_without_removal
61	убита	tests/test_doc_commit_module.py::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite
62	убита	tests/test_doc_commit_module.py::test_ac14_knowledge_paths_not_in_config_paths
63	убита	tests/test_doc_commit_module.py::test_ac14_invalid_form_refused_without_commit_or_hold
64	убита	tests/test_doc_commit_module.py::test_ac14_nested_and_non_yaml_paths_refused
65	убита	tests/test_doc_commit_module.py::test_ac14_role_environment_refused
66	убита	tests/test_doc_commit_module.py::test_bytes_preserved_crlf_not_translated,tests/test_doc_commit_module.py::test_config_path_gets_config_prefix_docs_path_gets_docs_prefix,tests/test_doc_commit_module.py::test_content_lands_in_origin_output_names_sha_main_copy_untouched,tests/test_doc_commit_module.py::test_origin_diverged_from_pin_refuses_naming_pin_update,tests/test_doc_commit_module.py::test_note_flush_sends_both_kinds,tests/test_doc_commit_module.py::test_flush_does_not_need_source_file_anymore,tests/test_doc_commit_module.py::test_open_window_holds_json_with_kind_and_flush_after_close_pushes,tests/test_doc_commit_module.py::test_new_path_absent_everywhere_is_committed,tests/test_doc_commit_module.py::test_identical_content_refused_instead_of_hanging_in_pending,tests/test_doc_commit_module.py::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit_module.py::test_no_journal_row_for_doc_commit,tests/test_doc_commit_module.py::test_flush_ignores_open_window_but_new_record_is_still_held,tests/test_doc_commit_module.py::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit_module.py::test_red_suite_refuses_naming_the_failed_test,tests/test_doc_commit_module.py::test_docs_path_does_not_run_the_suite_at_all,tests/test_doc_commit_module.py::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_doc_commit_module.py::test_unrunnable_suite_refuses_the_same_way,tests/test_doc_commit_module.py::test_green_suite_lets_the_commit_through,tests/test_doc_commit_module.py::test_accept_red_skips_the_run_entirely,tests/test_doc_commit_module.py::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_doc_commit_module.py::test_green_suite_with_accept_red_still_journals_the_bypass,tests/test_doc_commit_module.py::test_accept_red_commits_and_journal_carries_path_and_reason,tests/test_doc_commit_module.py::test_accept_red_record_is_sent_by_the_opportunistic_flush,tests/test_doc_commit_module.py::test_explicit_flush_warns_about_missing_base_of_config_record,tests/test_doc_commit_module.py::test_leftover_file_in_the_work_tree_is_not_read_as_origin_content,tests/test_doc_commit_module.py::test_opportunistic_flush_still_skips_config_record_silently_on_base,tests/test_doc_commit_module.py::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_doc_commit_module.py::test_docs_path_accept_red_writes_no_bypass_journal_row,tests/test_doc_commit_module.py::test_ac1_held_record_stores_pin_blob_or_absent_mark,tests/test_doc_commit_module.py::test_network_hold_stores_head_blob,tests/test_doc_commit_module.py::test_ac2_opportunistic_flush_refuses_stale_base,tests/test_doc_commit_module.py::test_ac4_new_file_appeared_in_origin_is_refused,tests/test_doc_commit_module.py::test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others,tests/test_doc_commit_module.py::test_ac3_base_matching_origin_is_sent,tests/test_doc_commit_module.py::test_ac4_new_file_absent_in_origin_is_sent,tests/test_doc_commit_module.py::test_ac7_pending_lists_each_record_with_truncated_content,tests/test_doc_commit_module.py::test_ac8_drop_pending_removes_exactly_one_and_journals,tests/test_doc_commit_module.py::test_ac5_immediate_send_still_refuses_on_pin,tests/test_doc_commit_module.py::test_ac2_note_flush_refuses_stale_base,tests/test_doc_commit_module.py::test_ac9_pending_and_drop_pending_refuse_under_role,tests/test_doc_commit_module.py::test_ac14_previous_paths_behave_as_before
67	убита	tests/test_doc_commit_module.py::test_explicit_flush_warns_about_missing_base_of_config_record
68	убита	tests/test_doc_commit_module.py::test_opportunistic_flush_still_skips_config_record_silently_on_base
69	убита	tests/test_doc_commit_module.py::test_half_written_record_does_not_become_batch_head_for_next
70	убита	tests/test_doc_commit_module.py::test_bytes_preserved_crlf_not_translated,tests/test_doc_commit_module.py::test_config_path_gets_config_prefix_docs_path_gets_docs_prefix,tests/test_doc_commit_module.py::test_origin_diverged_from_pin_refuses_naming_pin_update,tests/test_doc_commit_module.py::test_content_lands_in_origin_output_names_sha_main_copy_untouched,tests/test_doc_commit_module.py::test_flush_does_not_need_source_file_anymore,tests/test_doc_commit_module.py::test_identical_content_refused_instead_of_hanging_in_pending,tests/test_doc_commit_module.py::test_new_path_absent_everywhere_is_committed,tests/test_doc_commit_module.py::test_note_flush_sends_both_kinds,tests/test_doc_commit_module.py::test_open_window_holds_json_with_kind_and_flush_after_close_pushes,tests/test_doc_commit_module.py::test_doc_commit_flush_sends_both_kinds,tests/test_doc_commit_module.py::test_flush_ignores_open_window_but_new_record_is_still_held,tests/test_doc_commit_module.py::test_note_hold_texts_unchanged,tests/test_doc_commit_module.py::test_no_journal_row_for_doc_commit,tests/test_doc_commit_module.py::test_suite_runs_on_the_tree_with_the_change_already_applied,tests/test_doc_commit_module.py::test_docs_path_does_not_run_the_suite_at_all,tests/test_doc_commit_module.py::test_open_window_holds_the_record_and_the_gate_fires_on_flush,tests/test_doc_commit_module.py::test_unrunnable_suite_refuses_the_same_way,tests/test_doc_commit_module.py::test_red_suite_refuses_naming_the_failed_test,tests/test_doc_commit_module.py::test_green_suite_lets_the_commit_through,tests/test_doc_commit_module.py::test_accept_red_skips_the_run_entirely,tests/test_doc_commit_module.py::test_note_reaches_origin_after_a_gate_refusal_and_a_foreign_change,tests/test_doc_commit_module.py::test_dirty_work_tree_is_forced_to_origin_before_the_next_record,tests/test_doc_commit_module.py::test_leftover_file_in_the_work_tree_is_not_read_as_origin_content,tests/test_doc_commit_module.py::test_accept_red_commits_and_journal_carries_path_and_reason,tests/test_doc_commit_module.py::test_green_suite_with_accept_red_still_journals_the_bypass,tests/test_doc_commit_module.py::test_repeat_after_fixing_the_suite_commits_the_same_change,tests/test_doc_commit_module.py::test_explicit_flush_warns_about_missing_base_of_config_record,tests/test_doc_commit_module.py::test_half_written_record_does_not_become_batch_head_for_next,tests/test_doc_commit_module.py::test_docs_path_accept_red_writes_no_bypass_journal_row,tests/test_doc_commit_module.py::test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks,tests/test_doc_commit_module.py::test_opportunistic_flush_still_skips_config_record_silently_on_base,tests/test_doc_commit_module.py::test_accept_red_record_is_sent_by_the_opportunistic_flush,tests/test_doc_commit_module.py::test_ac5_immediate_send_still_refuses_on_pin,tests/test_doc_commit_module.py::test_ac14_previous_paths_behave_as_before,tests/test_doc_commit_module.py::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite
71	убита	tests/test_doc_commit_module.py::test_new_path_absent_everywhere_is_committed,tests/test_doc_commit_module.py::test_ac4_new_file_absent_in_origin_is_sent,tests/test_doc_commit_module.py::test_leftover_file_in_the_work_tree_is_not_read_as_origin_content,tests/test_doc_commit_module.py::test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite
```

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (патчи, сопоставление) | 1; раздел «Сопоставление мутаций» |
| 2 (таблица «до») | 1, 4; раздел «Мутации до» |
| 3 (падения подготовки) | 1, 3, 4; раздел «Падения подготовки» |
| 4 (неубитые — находки) | раздел «Находки» |
| 5, 6, 8 (свод, дословные ожидания, «Ловит мутацию») | 2 |
| 7 (дубли) | 2; раздел «Удалённые дубли» |
| 9 (таблица «после», сверка шапок) | 3, 4; разделы «Мутации до»/«Мутации после», «Подход» |
| 10 (числа) | раздел «Числа до и после» |
| 11, 12 (удаление по мандату ANSWER-1, зоны) | 2 |
| 13 (независимая проверка) | сессия при Операторе, не шаг роли |

## Влияние на систему

- Код `orchestrator/` не меняется; мутации живут только во временной
  копии `mutation-run`. В `tests/` — шесть удалений и один новый файл;
  `tests/fixtures.py`, `tests/sandbox.py`, файлы волны 1а не тронуты.
- Свойства шести файлов переносятся с дословными ожиданиями; таблица
  «после» убивает каждую мутацию, убитую «до» (68 из 71; три неубитые —
  находки и «до», и «после»). Удаление двух долгоживущих файлов задач в
  `done` — по ADR-0020 п. 8 и мандату ANSWER-1; гейты неослабления
  (`test_integrity`, `outcome_integrity`) читают этот мандат.
- Откат — revert merge-коммита задачи: возвращает шесть файлов и убирает
  новый.

## Риски

- Подтяжка main между прогонами: «до» повторён на новой базе ed38d987;
  при следующей подтяжке с правкой `orchestrator/` сверка шапок (AC-11)
  покраснеет — тогда повторять обе таблицы.

## Предложения системе

- `mutation-run`: нет способа перенести таблицу в PLAN командой пульта —
  перенос «дословно, до следующей части» каждый раз делается разовым
  сценарием роли (временный файл в рабочей копии отказал переход
  «посторонние файлы»). Нужна опция вида `mutation-run <id> --append-plan
  <раздел>`.
