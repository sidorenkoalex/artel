---
task: 01M5PHK9K0YQCTPA6CK94BBZ33
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Сведение тестов, волна 2а-1 — песочница гейта исходов в `tests/outcome_gate_sandbox.py`, тесты в `tests/test_outcome_gate_module.py`

## Подход

Порядок волн 1а/1б: сначала набор мутаций к коду `orchestrator/` по строкам
«Ловит мутацию» трёх исходных файлов (53 заявки → 35 патчей
`mutation-001.diff`…`mutation-035.diff`), таблица «до» на трёх исходных
файлах (`--ref base`, части 1-15, 16-30, 31-35), затем вынос песочницы и
свод тестов, таблица «после» на `tests/test_outcome_gate_module.py`
(`--ref worktree`, те же части).

- Песочница: строки 47–899 исходного
  `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py` перенесены в
  `tests/outcome_gate_sandbox.py` дословно, докстринг — одна строка.
- Импортёры: в трёх файлах сменён только модуль в `from … import`.
- `IdOutcomeGateSandbox` с константами и функциями — в новом файле
  дословно, с тремя переименованиями.
- Все 53 теста переносятся функциями модуля под прежними именами; удалённых
  дублей нет.

## Мутации и заявки

Строка = мутация, её заявившие тесты (строки «Ловит мутацию» трёх исходных
файлов; одинаковые по смыслу — одной мутацией) и что меняет патч. Файл A —
`tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`, B —
`tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py`, C —
`tests/test_outcome_integrity.py`; патчи меняют
`orchestrator/advance_gates/outcome_integrity.py` (кроме 3 и 4 —
`orchestrator/fsm_advance.py`).

- mutation-001: `Ac1OutOfBoundsTest::test_ac1_artel_and_test_profile_no_gate` («граница по `reported(profile)` без `from_components` … гейт создаётся у любого профиля»); патч: `_bounds` не сверяет `in_outcome_bounds` — гейт создан у артели и `test_profile`.
- mutation-002: `Ac1OutOfBoundsTest::test_ac1_decide_skip_refusal_and_canary_no_gate` («условие `t["is_canary"]` пропущено»); патч: `_bounds` не возвращает `None` для канарейки.
- mutation-003: `Ac2PlaceTest::test_ac2_text_gate_refusal_first_no_outcome_runs` («гейт исходов поставлен до гейта по тексту»); патч: в `fsm_advance.in_dev` вызов `_outcome_integrity_gate_refuses` поставлен перед `_test_integrity_gate_refuses`.
- mutation-004: `Ac2PlaceTest::test_ac2_outcome_refusal_stops_before_review_rework_gate` («гейт исходов поставлен после гейта переделки ревью»); патч: в `fsm_advance.in_dev` `_review_rework_gate_refuses` перенесён перед гейтом исходов.
- mutation-005: `Ac3RunsTest::test_ac3_full_suite_on_base_and_head_checkouts_fresh` («`fresh` не передан — `False` в вызове»); патч: `_full_run` зовёт `components_full_suite(..., fresh=False)`.
- mutation-006: `Ac4PrepareTest::test_ac4_git_preparation_failures_refuse`, `Ac4PrepareTest::test_ac4_git_head_not_read_refuses` («`None` от `diff_base` или пустая голова — гейт пропущен»); патч: `_gate` при отказе «… не определена»/«… не прочитана» возвращает `None` (гейт пропущен).
- mutation-007: `Ac4PrepareTest::test_ac4_git_base_checkout_failure_refuses`, `Ac4PrepareTest::test_ac4_git_head_checkout_failure_refuses` («сбой выписки проглочен — сравнение по одной стороне»); патч: `_checkouts` при сбое выписки выписывает sha другой стороны.
- mutation-008: `Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side`, `Ac4PrepareTest::test_ac4_side_base_timeout_refuses_naming_base` («"неизвестно"/таймаут базы принят за пустой отчёт — набор `PASS_TO_PASS` пуст, гейт пройден»); патч: `_full_run` на стороне базы при «не начат»/таймауте возвращает пустой список.
- mutation-009: `Ac4PrepareTest::test_ac4_side_head_unknown_refuses_naming_head`, `Ac4PrepareTest::test_ac4_side_head_timeout_refuses_naming_head` («сторона в отказе не названа»); патч: текст отказа `_full_run` без названия стороны.
- mutation-010: `Ac5PassToPassTest::test_ac5_retried_on_base_not_in_pass_to_pass`, `RecordLevelTest::test_retried_pass_on_base_not_in_pass_to_pass` («в набор берётся любой `passed` базы без сверки `retries == 0`»); патч: `in_pass_to_pass` без `retries == 0`.
- mutation-011: `Ac5PassToPassTest::test_ac5_no_tests_on_base_empty_pass_to_pass` («"нет тестов" базы принят за отказ»); патч (переписан после «до» №1, где первая редакция — `_Prepare` только при исходе `FULL_SUITE_NO_TESTS` — не убита: пустая база идёт иным исходом прогона): `_full_run` отказывает при пустом списке записей стороны.
- mutation-012: `Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit` («перепрогон базы пропущен — перепрогонов базы ноль»); патч: `_rerun` по умолчанию только на стороне ветки.
- mutation-013: `RecordLevelTest::test_red_on_branch_kinds` («`passed` с повтором не считается красным»); патч: `red_on_branch` без ветки `passed` с повтором.
- mutation-014: `Ac6RerunTest::test_ac6_skipped_on_branch_not_rerun` («`skipped` на ветке считается красным»); патч: `red_on_branch` считает `skipped` красным.
- mutation-015: `Ac7RerunPrepareTest::test_ac7_rerun_preparation_refusals`, `Ac7RerunPrepareTest::test_ac7_rerun_unknown_outcome_refuses`, `Ac7RerunPrepareTest::test_ac7_rerun_timeout_refuses` («без `select` … "неизвестно"/предел перепрогона принят за красный»); патч: `_rerun` не отказывает при `run.refusal`, таймауте и исходе не «зелёный»/«красный».
- mutation-016: `Ac7RerunPrepareTest::test_ac7_rerun_base_skipped_refuses`, `Ac7RerunPrepareTest::test_ac7_rerun_base_record_missing_refuses` («пропуск или отсутствие записи на базе принят за красный базы»); патч: `_rerun` не отказывает на базе при `skipped`/нет записи.
- mutation-017: `Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red` («`passed` с повтором — зелёный»); патч: зелёный перепрогона — любой `passed`.
- mutation-018: `Ac7RerunPrepareTest::test_ac7_branch_rerun_skipped_is_red`, `Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red` («`skipped` или отсутствие записи на перепрогоне ветки — зелёный»); патч: зелёный перепрогона — и `skipped`, и нет записи.
- mutation-019: `Ac7RerunPrepareTest::test_ac7_branch_rerun_red_kinds`, `Ac7RerunPrepareTest::test_ac7_branch_rerun_error_is_red`, `Ac8VerdictByRecordTest::test_ac8_broken_unstable_and_flaky_on_base` («итог — "нестабилен после правки" вместо "сломан правкой"»; «"нестабилен" не отличается от "сломан"»); патч: `_redness` всегда даёт «нестабилен после правки».
- mutation-020: `Ac8VerdictByRecordTest::test_ac8_unstable_after_change_general_refusal` («"нестабилен" не отличается от "сломан" — действие "… — сломан правкой"»); патч: `_redness` всегда даёт «сломан правкой».
- mutation-021: `Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal` («красная база перепрогона не читается»); патч: `_redness` не смотрит на красноту базы.
- mutation-022: `Ac8VerdictByRecordTest::test_ac8_neighbour_red_in_same_file_does_not_redden_rerun` («итог перепрогона по вердикту прогона»); патч: зелёный перепрогона — `run.state == GREEN`.
- mutation-023: `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings`, `Ac9CompareTest::test_ac9_junit_records_findings`, `RecordLevelTest::test_compare_vitest_findings_and_non_findings`, `RecordLevelTest::test_compare_junit_became_skipped_from_each_outcome` («"стал пропуском" только у `passed` базы»); патч: `compare` — «стал пропуском» только при `passed` базы.
- mutation-024: `Ac9CompareTest::test_ac9_one_finding_per_id_senior_kind` («вторая запись сравнения к "сломан правкой" по тому же идентификатору»); патч: `_judge` не отбрасывает записи `compare` по уже взятым идентификаторам.
- mutation-025: `Ac10OrderTest::test_ac10_findings_order_and_one_line_each` («порядок строк отказа — порядок отчёта или сравнения»); патч: `ordered` возвращает список без сортировки.
- mutation-026: `Ac11MandateTest::test_ac11_file_and_prefix_mandate_cover_findings`, `Ac11MandateTest::test_ac11_class_prefix_mandate_covers`, `Ac11MandateTest::test_ac11_method_prefix_mandate_covers_variants` («мандат сверяется точным равенством с идентификатором»); патч: `_covering_element` — только равенство элемента идентификатору.
- mutation-027: `Ac11MandateTest::test_ac11_other_file_mandate_does_not_cover` («покрытие по имени файла без пути»); патч (переписан после «до» №2, где первая редакция — сравнение имени файла без каталога — не убита: у мандата другого файла и имя файла другое): `_covering_element` считает покрывающим любой элемент без `::` (мандат на файл), не сверяя путь.
- mutation-028: `Ac11MandateTest::test_ac11_prefix_needs_separator_after_it`, `RecordLevelTest::test_mandate_prefix_needs_separator` («покрытие — `startswith` без сверки следующего символа»); патч: хвост после префикса не сверяется.
- mutation-029: `Ac11MandateTest::test_ac11_role_autocommitted_answer_does_not_cover`, `RoleAutocommitTest::test_ac11_role_autocommitted_id_mandate_does_not_cover` («мандат собран без отбраковки автокоммита роли»); патч: `_answer_mandates` не отбрасывает автокоммит шага роли.
- mutation-030: `Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts` («число покрытых мандатом находок не указано»); патч: из строки чисел записи пройденного гейта убрано число покрытых мандатом.
- mutation-031: `ExactIdTest::test_ac12_exact_id_with_n_covers_other_variant_does_not` («элементы нового маркера в гейте не собираются — (а) отказ»); патч: `_covering_pair` не смотрит мандат по идентификатору.
- mutation-032: `HintTest::test_ac13_refusal_hint_names_both_markers` («своя подсказка называет только новый маркер»); патч: `_mandate_hint` без прежнего маркера.
- mutation-033: `RecordLevelTest::test_skip_growth_line` («строка пишется и без роста»); патч: `skip_growth` пишет строку при равенстве чисел.
- mutation-034: `RecordLevelTest::test_covered_ids_round_trip_every_finding_kind` («разбор строки по первому " — "»); патч: `_finding_of` делит строку по первому « — ».
- mutation-035: `RecordLevelTest::test_fingerprint_sorted_unique_or_none` («отпечаток без сортировки или с повтором элемента»); патч: `fingerprint` без `sorted(set(...))`.

## Мутации до

Вывод `mutation-run --wait` каждой части дословно (шапка и строки).

Часть 1 (`--patches 1-15`):

# mutation-run №1 задачи 01M5PHK9K0YQCTPA6CK94BBZ33
# источник патчей: каталог на диске
# ревизия прогона: base ed38d9879e02d12dc982d1979077b2c3c445382a
# тесты: tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py, tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py, tests/test_outcome_integrity.py
# патч 1 mutation-001.diff sha256 7e8c5ff9839d64211fe5742a4533275e2b8e4e2b4b10d76879a80c7e57718173
# патч 2 mutation-002.diff sha256 45762ddbf2cac2eedaaf53c9c0e54c2edb6abb34735216bb77b8e8a2d9207fc3
# патч 3 mutation-003.diff sha256 1781b115337f29162e78febd5ab4736f32240d768424d259c78aafc0afa0934c
# патч 4 mutation-004.diff sha256 2a59d597363167fdc681eb55aff45908093d9c587437646c74f609a33499cc14
# патч 5 mutation-005.diff sha256 8dcd99b2aabe2cd5b6bd68e228977608a3eec991461de0e5f6e65ef02b5bd4a4
# патч 6 mutation-006.diff sha256 1a2016f76f53ad627baabd009e9e2ef956850504c5f5c2eddaf528066d0ae90f
# патч 7 mutation-007.diff sha256 cf260f676e9892d12f043184fd79ffd86e4fb786ebc39f3ffe955b72f8276e52
# патч 8 mutation-008.diff sha256 b5d7b4422e655876da66d5a702cd42948f66e482a2a7ed315dbe0f145e498ec2
# патч 9 mutation-009.diff sha256 2cd39c6d46590a94aa7122a105e849d833c2fcda7e2caff54c486483164019a4
# патч 10 mutation-010.diff sha256 a037e744c087fde4046a7a4332ca28a028502150d6d5a9e54dad642e389040ac
# патч 11 mutation-011.diff sha256 ce174133527c97e71a00b28058f6d5ddc4509afe048b9e322cfc347f9626fd0a
# патч 12 mutation-012.diff sha256 cfed6f7cf3f12fede296705dc923db40c524d93179aa672881e6df1d8153da95
# патч 13 mutation-013.diff sha256 e608442ca012377afd586dab356cf456f27c6a1478bae8f2f4fa81d40b2ecfc4
# патч 14 mutation-014.diff sha256 48978860d259c827829b351e91839d513d6b1d7541fa8ea044e3869c23de52be
# патч 15 mutation-015.diff sha256 f8e01af38bee7de6959a66b9e1f5ab5e46bf4b2b82e990f8ee1f1af7a2a6a981
номер	исход	узлы
1	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac1OutOfBoundsTest::test_ac1_artel_and_test_profile_no_gate
2	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac1OutOfBoundsTest::test_ac1_decide_skip_refusal_and_canary_no_gate
3	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac3RunsTest::test_ac3_full_suite_on_base_and_head_checkouts_fresh,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac5PassToPassTest::test_ac5_retried_on_base_not_in_pass_to_pass,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac5PassToPassTest::test_ac5_no_tests_on_base_empty_pass_to_pass,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac2PlaceTest::test_ac2_text_gate_refusal_first_no_outcome_runs,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts
4	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac2PlaceTest::test_ac2_outcome_refusal_stops_before_review_rework_gate
5	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac3RunsTest::test_ac3_full_suite_on_base_and_head_checkouts_fresh
6	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_git_preparation_failures_refuse,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_git_head_not_read_refuses
7	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_git_head_checkout_failure_refuses,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_git_base_checkout_failure_refuses
8	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_base_timeout_refuses_naming_base
9	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_head_timeout_refuses_naming_head,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_base_timeout_refuses_naming_base,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_head_unknown_refuses_naming_head
10	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac5PassToPassTest::test_ac5_retried_on_base_not_in_pass_to_pass,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red,tests/test_outcome_integrity.py::RecordLevelTest::test_retried_pass_on_base_not_in_pass_to_pass
11	не убита	
12	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_base_record_missing_refuses,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_base_skipped_refuses,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts
13	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit,tests/test_outcome_integrity.py::RecordLevelTest::test_red_on_branch_kinds
14	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac6RerunTest::test_ac6_skipped_on_branch_not_rerun,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac10OrderTest::test_ac10_findings_order_and_one_line_each,tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py::RoleAutocommitTest::test_ac11_role_autocommitted_id_mandate_does_not_cover,tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py::ExactIdTest::test_ac12_exact_id_with_n_covers_other_variant_does_not,tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py::HintTest::test_ac13_refusal_hint_names_both_markers,tests/test_outcome_integrity.py::RecordLevelTest::test_red_on_branch_kinds
15	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_unknown_outcome_refuses,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_timeout_refuses
Часть 2 (`--patches 16-30`):

# mutation-run №2 задачи 01M5PHK9K0YQCTPA6CK94BBZ33
# источник патчей: каталог на диске
# ревизия прогона: base ed38d9879e02d12dc982d1979077b2c3c445382a
# тесты: tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py, tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py, tests/test_outcome_integrity.py
# патч 16 mutation-016.diff sha256 c52e5dd7df12c56551d01975704b1a5e46bbd7c18096fbade2538b92fd4419df
# патч 17 mutation-017.diff sha256 4923a6f66ee77928cb0866f798912ccaa91cefb99007d125fa54a87aa0655e0f
# патч 18 mutation-018.diff sha256 d98c11a755b916ea39d2a6abf22df0d77da57586096b970172e85e6d20e907c4
# патч 19 mutation-019.diff sha256 dcf6b1ca472572b02abada0947d4c9bbc870119928310c975c4d4b905d48d460
# патч 20 mutation-020.diff sha256 0d7ee74a5002a8c65043d4ec20e344300852087637da7ebbab806750624d15a4
# патч 21 mutation-021.diff sha256 4e97a93f725b4e0bcfea98363f58225c30e7f101830f355daec52070e43a75eb
# патч 22 mutation-022.diff sha256 8165c30d1bcc9a0c4f612f5441cd5ccf28680a99948d829a92ef7e6b030d4b84
# патч 23 mutation-023.diff sha256 5854ed431ab99394c00842d47daf3fbffc3e689918cb7a178c2d395355149b5b
# патч 24 mutation-024.diff sha256 3ca7731d0352802892aa72cd32dc93e4ee6c3bc9f08433ed4142f560eeab63a5
# патч 25 mutation-025.diff sha256 c5123293bef9265f03a11d1f847d275eaeaaef05f7fc29fe3dbd2ec06c0118fc
# патч 26 mutation-026.diff sha256 364e15fa42d160b8836c32e17a88224fc29164091c4cbb41ecdf25d4c35f2106
# патч 27 mutation-027.diff sha256 a2c6f89a090a2f74a79eff67567ab2030eaa64fe335bf9e4f8520130976e06d6
# патч 28 mutation-028.diff sha256 0afa20a351bbb739b51dd1fa7b840390c7805beca923ea2b2c28b44349642b76
# патч 29 mutation-029.diff sha256 b9ac24756c3f2961ddd662b39962fe1c123871519ce10580a4967c4647dd6cab
# патч 30 mutation-030.diff sha256 0b9de6deebb3e445b78d57391d14f1dae643af9e752116b52f13d21945a01ec0
номер	исход	узлы
16	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_base_record_missing_refuses,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_base_skipped_refuses
17	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red
18	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_skipped_is_red
19	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac5PassToPassTest::test_ac5_retried_on_base_not_in_pass_to_pass,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac2PlaceTest::test_ac2_outcome_refusal_stops_before_review_rework_gate,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_error_is_red,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_broken_unstable_and_flaky_on_base,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_red_kinds,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_skipped_is_red,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_other_file_mandate_does_not_cover,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_one_finding_per_id_senior_kind,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_role_autocommitted_answer_does_not_cover,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_prefix_needs_separator_after_it
20	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_neighbour_red_in_same_file_does_not_redden_rerun,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_unstable_after_change_general_refusal,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac10OrderTest::test_ac10_findings_order_and_one_line_each
21	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts
22	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_skipped_is_red,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_neighbour_red_in_same_file_does_not_redden_rerun,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings
23	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_junit_records_findings,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings,tests/test_outcome_integrity.py::RecordLevelTest::test_compare_vitest_findings_and_non_findings,tests/test_outcome_integrity.py::RecordLevelTest::test_compare_junit_became_skipped_from_each_outcome
24	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_one_finding_per_id_senior_kind
25	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac10OrderTest::test_ac10_findings_order_and_one_line_each
26	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_file_and_prefix_mandate_cover_findings,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_class_prefix_mandate_covers,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_method_prefix_mandate_covers_variants,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_prefix_needs_separator_after_it,tests/test_outcome_integrity.py::RecordLevelTest::test_mandate_prefix_needs_separator
27	не убита	
28	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_prefix_needs_separator_after_it,tests/test_outcome_integrity.py::RecordLevelTest::test_mandate_prefix_needs_separator
29	убита	tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py::RoleAutocommitTest::test_ac11_role_autocommitted_id_mandate_does_not_cover,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_role_autocommitted_answer_does_not_cover
30	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts

Часть 3 (`--patches 31-35`):

# mutation-run №3 задачи 01M5PHK9K0YQCTPA6CK94BBZ33
# источник патчей: каталог на диске
# ревизия прогона: base ed38d9879e02d12dc982d1979077b2c3c445382a
# тесты: tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py, tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py, tests/test_outcome_integrity.py
# патч 31 mutation-031.diff sha256 75606e4fd1d20ae1c398271645e628b3aec69e12785458bf408e77b9e398ae6e
# патч 32 mutation-032.diff sha256 31d28986cd1cfc82d311237c2f535d214f4297e0a7b6cfe86879a2d3155b9dfd
# патч 33 mutation-033.diff sha256 eccd871aab688e2a9ab9e0b722ba73dd8e1858b69a21374571dcb55e13fe08b0
# патч 34 mutation-034.diff sha256 a8d21ebcd326420b9c52ace5528f64fb584a7f22de81e20113fa9a4c49a069b2
# патч 35 mutation-035.diff sha256 27fc5d96ee096cb31284164298964d38fffc5f7bb3681bce446c631ffa2eecbd
номер	исход	узлы
31	убита	tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py::ExactIdTest::test_ac12_exact_id_with_n_covers_other_variant_does_not
32	убита	tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py::HintTest::test_ac13_refusal_hint_names_both_markers
33	убита	tests/test_outcome_integrity.py::RecordLevelTest::test_skip_growth_line
34	убита	tests/test_outcome_integrity.py::RecordLevelTest::test_covered_ids_round_trip_every_finding_kind
35	убита	tests/test_outcome_integrity.py::RecordLevelTest::test_fingerprint_sorted_unique_or_none

Перепрогон мутации 11 после переписи патча (`--patches 11-11`):

# mutation-run №4 задачи 01M5PHK9K0YQCTPA6CK94BBZ33
# источник патчей: каталог на диске
# ревизия прогона: base ed38d9879e02d12dc982d1979077b2c3c445382a
# тесты: tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py, tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py, tests/test_outcome_integrity.py
# патч 11 mutation-011.diff sha256 7015d4d8dfcf958801c643fe866b1cf608cc6f6cfba90d6db613c772536f37f6
номер	исход	узлы
11	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac5PassToPassTest::test_ac5_no_tests_on_base_empty_pass_to_pass

Перепрогон мутации 27 после переписи патча (`--patches 27-27`):

# mutation-run №5 задачи 01M5PHK9K0YQCTPA6CK94BBZ33
# источник патчей: каталог на диске
# ревизия прогона: base ed38d9879e02d12dc982d1979077b2c3c445382a
# тесты: tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py, tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py, tests/test_outcome_integrity.py
# патч 27 mutation-027.diff sha256 b62a1dba0c2c8854b959fd1f9dedcdd6c87037e1e7f8565678ea192ff92322a8
номер	исход	узлы
27	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_other_file_mandate_does_not_cover,tests/test_outcome_integrity.py::RecordLevelTest::test_mandate_prefix_needs_separator

## Мутации после

Вывод `mutation-run --wait` каждой части дословно (шапка и строки), `--ref worktree`, тесты — `tests/test_outcome_gate_module.py`. Перед каждой частью — вывод `git status --porcelain -- orchestrator/` рабочей копии (ANSWER-1, п. 3).

Часть 1 (`--patches 1-15`). `git status --porcelain -- orchestrator/` перед стартом: пустой вывод.



# mutation-run №6 задачи 01M5PHK9K0YQCTPA6CK94BBZ33
# источник патчей: каталог на диске
# ревизия прогона: worktree 071800d4e679d80648f4b06c21df4542de2e689b
# тесты: tests/test_outcome_gate_module.py
# патч 1 mutation-001.diff sha256 7e8c5ff9839d64211fe5742a4533275e2b8e4e2b4b10d76879a80c7e57718173
# патч 2 mutation-002.diff sha256 45762ddbf2cac2eedaaf53c9c0e54c2edb6abb34735216bb77b8e8a2d9207fc3
# патч 3 mutation-003.diff sha256 1781b115337f29162e78febd5ab4736f32240d768424d259c78aafc0afa0934c
# патч 4 mutation-004.diff sha256 2a59d597363167fdc681eb55aff45908093d9c587437646c74f609a33499cc14
# патч 5 mutation-005.diff sha256 8dcd99b2aabe2cd5b6bd68e228977608a3eec991461de0e5f6e65ef02b5bd4a4
# патч 6 mutation-006.diff sha256 1a2016f76f53ad627baabd009e9e2ef956850504c5f5c2eddaf528066d0ae90f
# патч 7 mutation-007.diff sha256 cf260f676e9892d12f043184fd79ffd86e4fb786ebc39f3ffe955b72f8276e52
# патч 8 mutation-008.diff sha256 b5d7b4422e655876da66d5a702cd42948f66e482a2a7ed315dbe0f145e498ec2
# патч 9 mutation-009.diff sha256 2cd39c6d46590a94aa7122a105e849d833c2fcda7e2caff54c486483164019a4
# патч 10 mutation-010.diff sha256 a037e744c087fde4046a7a4332ca28a028502150d6d5a9e54dad642e389040ac
# патч 11 mutation-011.diff sha256 7015d4d8dfcf958801c643fe866b1cf608cc6f6cfba90d6db613c772536f37f6
# патч 12 mutation-012.diff sha256 cfed6f7cf3f12fede296705dc923db40c524d93179aa672881e6df1d8153da95
# патч 13 mutation-013.diff sha256 e608442ca012377afd586dab356cf456f27c6a1478bae8f2f4fa81d40b2ecfc4
# патч 14 mutation-014.diff sha256 48978860d259c827829b351e91839d513d6b1d7541fa8ea044e3869c23de52be
# патч 15 mutation-015.diff sha256 f8e01af38bee7de6959a66b9e1f5ab5e46bf4b2b82e990f8ee1f1af7a2a6a981
номер	исход	узлы
1	убита	tests/test_outcome_gate_module.py::test_ac1_artel_and_test_profile_no_gate
2	убита	tests/test_outcome_gate_module.py::test_ac1_decide_skip_refusal_and_canary_no_gate
3	убита	tests/test_outcome_gate_module.py::test_ac2_text_gate_refusal_first_no_outcome_runs,tests/test_outcome_gate_module.py::test_ac3_full_suite_on_base_and_head_checkouts_fresh,tests/test_outcome_gate_module.py::test_ac5_no_tests_on_base_empty_pass_to_pass,tests/test_outcome_gate_module.py::test_ac5_retried_on_base_not_in_pass_to_pass,tests/test_outcome_gate_module.py::test_ac13_passed_gate_journal_counts
4	убита	tests/test_outcome_gate_module.py::test_ac2_outcome_refusal_stops_before_review_rework_gate
5	убита	tests/test_outcome_gate_module.py::test_ac3_full_suite_on_base_and_head_checkouts_fresh
6	убита	tests/test_outcome_gate_module.py::test_ac4_git_head_not_read_refuses,tests/test_outcome_gate_module.py::test_ac4_git_preparation_failures_refuse
7	убита	tests/test_outcome_gate_module.py::test_ac4_git_head_checkout_failure_refuses,tests/test_outcome_gate_module.py::test_ac4_git_base_checkout_failure_refuses
8	убита	tests/test_outcome_gate_module.py::test_ac4_side_not_started_or_timeout_refuses_naming_side,tests/test_outcome_gate_module.py::test_ac4_side_base_timeout_refuses_naming_base
9	убита	tests/test_outcome_gate_module.py::test_ac4_side_head_timeout_refuses_naming_head,tests/test_outcome_gate_module.py::test_ac4_side_head_unknown_refuses_naming_head,tests/test_outcome_gate_module.py::test_ac4_side_not_started_or_timeout_refuses_naming_side,tests/test_outcome_gate_module.py::test_ac4_side_base_timeout_refuses_naming_base
10	убита	tests/test_outcome_gate_module.py::test_ac7_branch_rerun_retried_is_red,tests/test_outcome_gate_module.py::test_ac5_retried_on_base_not_in_pass_to_pass,tests/test_outcome_gate_module.py::test_retried_pass_on_base_not_in_pass_to_pass
11	убита	tests/test_outcome_gate_module.py::test_ac5_no_tests_on_base_empty_pass_to_pass
12	убита	tests/test_outcome_gate_module.py::test_ac7_rerun_base_skipped_refuses,tests/test_outcome_gate_module.py::test_ac7_rerun_base_record_missing_refuses,tests/test_outcome_gate_module.py::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit,tests/test_outcome_gate_module.py::test_ac8_flaky_on_base_no_refusal,tests/test_outcome_gate_module.py::test_ac13_passed_gate_journal_counts
13	убита	tests/test_outcome_gate_module.py::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit,tests/test_outcome_gate_module.py::test_red_on_branch_kinds[case2-True]
14	убита	tests/test_outcome_gate_module.py::test_ac6_skipped_on_branch_not_rerun,tests/test_outcome_gate_module.py::test_ac10_findings_order_and_one_line_each,tests/test_outcome_gate_module.py::test_ac11_role_autocommitted_id_mandate_does_not_cover,tests/test_outcome_gate_module.py::test_ac13_refusal_hint_names_both_markers,tests/test_outcome_gate_module.py::test_red_on_branch_kinds[case3-False],tests/test_outcome_gate_module.py::test_red_on_branch_kinds[case4-False],tests/test_outcome_gate_module.py::test_ac12_exact_id_with_n_covers_other_variant_does_not
15	убита	tests/test_outcome_gate_module.py::test_ac7_rerun_unknown_outcome_refuses,tests/test_outcome_gate_module.py::test_ac7_rerun_timeout_refuses

Часть 2 (`--patches 16-30`). `git status --porcelain -- orchestrator/` перед стартом: пустой вывод.



# mutation-run №7 задачи 01M5PHK9K0YQCTPA6CK94BBZ33
# источник патчей: каталог на диске
# ревизия прогона: worktree 071800d4e679d80648f4b06c21df4542de2e689b
# тесты: tests/test_outcome_gate_module.py
# патч 16 mutation-016.diff sha256 c52e5dd7df12c56551d01975704b1a5e46bbd7c18096fbade2538b92fd4419df
# патч 17 mutation-017.diff sha256 4923a6f66ee77928cb0866f798912ccaa91cefb99007d125fa54a87aa0655e0f
# патч 18 mutation-018.diff sha256 d98c11a755b916ea39d2a6abf22df0d77da57586096b970172e85e6d20e907c4
# патч 19 mutation-019.diff sha256 dcf6b1ca472572b02abada0947d4c9bbc870119928310c975c4d4b905d48d460
# патч 20 mutation-020.diff sha256 0d7ee74a5002a8c65043d4ec20e344300852087637da7ebbab806750624d15a4
# патч 21 mutation-021.diff sha256 4e97a93f725b4e0bcfea98363f58225c30e7f101830f355daec52070e43a75eb
# патч 22 mutation-022.diff sha256 8165c30d1bcc9a0c4f612f5441cd5ccf28680a99948d829a92ef7e6b030d4b84
# патч 23 mutation-023.diff sha256 5854ed431ab99394c00842d47daf3fbffc3e689918cb7a178c2d395355149b5b
# патч 24 mutation-024.diff sha256 3ca7731d0352802892aa72cd32dc93e4ee6c3bc9f08433ed4142f560eeab63a5
# патч 25 mutation-025.diff sha256 c5123293bef9265f03a11d1f847d275eaeaaef05f7fc29fe3dbd2ec06c0118fc
# патч 26 mutation-026.diff sha256 364e15fa42d160b8836c32e17a88224fc29164091c4cbb41ecdf25d4c35f2106
# патч 27 mutation-027.diff sha256 b62a1dba0c2c8854b959fd1f9dedcdd6c87037e1e7f8565678ea192ff92322a8
# патч 28 mutation-028.diff sha256 0afa20a351bbb739b51dd1fa7b840390c7805beca923ea2b2c28b44349642b76
# патч 29 mutation-029.diff sha256 b9ac24756c3f2961ddd662b39962fe1c123871519ce10580a4967c4647dd6cab
# патч 30 mutation-030.diff sha256 0b9de6deebb3e445b78d57391d14f1dae643af9e752116b52f13d21945a01ec0
номер	исход	узлы
16	убита	tests/test_outcome_gate_module.py::test_ac7_rerun_base_skipped_refuses,tests/test_outcome_gate_module.py::test_ac7_rerun_base_record_missing_refuses
17	убита	tests/test_outcome_gate_module.py::test_ac7_branch_rerun_retried_is_red
18	убита	tests/test_outcome_gate_module.py::test_ac7_branch_rerun_skipped_is_red,tests/test_outcome_gate_module.py::test_ac7_branch_rerun_missing_is_red
19	убита	tests/test_outcome_gate_module.py::test_ac7_branch_rerun_skipped_is_red,tests/test_outcome_gate_module.py::test_ac7_branch_rerun_retried_is_red,tests/test_outcome_gate_module.py::test_ac7_branch_rerun_red_kinds,tests/test_outcome_gate_module.py::test_ac2_outcome_refusal_stops_before_review_rework_gate,tests/test_outcome_gate_module.py::test_ac5_retried_on_base_not_in_pass_to_pass,tests/test_outcome_gate_module.py::test_ac7_branch_rerun_missing_is_red,tests/test_outcome_gate_module.py::test_ac7_branch_rerun_error_is_red,tests/test_outcome_gate_module.py::test_ac8_broken_unstable_and_flaky_on_base,tests/test_outcome_gate_module.py::test_ac11_role_autocommitted_answer_does_not_cover,tests/test_outcome_gate_module.py::test_ac9_one_finding_per_id_senior_kind,tests/test_outcome_gate_module.py::test_ac11_other_file_mandate_does_not_cover,tests/test_outcome_gate_module.py::test_ac10_findings_order_and_one_line_each,tests/test_outcome_gate_module.py::test_ac11_prefix_needs_separator_after_it
20	убита	tests/test_outcome_gate_module.py::test_ac8_unstable_after_change_general_refusal,tests/test_outcome_gate_module.py::test_ac10_findings_order_and_one_line_each,tests/test_outcome_gate_module.py::test_ac8_neighbour_red_in_same_file_does_not_redden_rerun
21	убита	tests/test_outcome_gate_module.py::test_ac8_flaky_on_base_no_refusal,tests/test_outcome_gate_module.py::test_ac13_passed_gate_journal_counts
22	убита	tests/test_outcome_gate_module.py::test_ac7_branch_rerun_skipped_is_red,tests/test_outcome_gate_module.py::test_ac7_branch_rerun_missing_is_red,tests/test_outcome_gate_module.py::test_ac8_neighbour_red_in_same_file_does_not_redden_rerun,tests/test_outcome_gate_module.py::test_ac9_vitest_records_findings_and_non_findings
23	убита	tests/test_outcome_gate_module.py::test_ac9_vitest_records_findings_and_non_findings,tests/test_outcome_gate_module.py::test_ac9_junit_records_findings,tests/test_outcome_gate_module.py::test_compare_junit_became_skipped_from_each_outcome,tests/test_outcome_gate_module.py::test_compare_vitest_findings_and_non_findings
24	убита	tests/test_outcome_gate_module.py::test_ac9_one_finding_per_id_senior_kind
25	убита	tests/test_outcome_gate_module.py::test_ac10_findings_order_and_one_line_each
26	убита	tests/test_outcome_gate_module.py::test_ac11_class_prefix_mandate_covers,tests/test_outcome_gate_module.py::test_ac11_file_and_prefix_mandate_cover_findings,tests/test_outcome_gate_module.py::test_ac11_method_prefix_mandate_covers_variants,tests/test_outcome_gate_module.py::test_ac13_passed_gate_journal_counts,tests/test_outcome_gate_module.py::test_mandate_prefix_needs_separator,tests/test_outcome_gate_module.py::test_ac11_prefix_needs_separator_after_it
27	убита	tests/test_outcome_gate_module.py::test_ac11_other_file_mandate_does_not_cover,tests/test_outcome_gate_module.py::test_mandate_prefix_needs_separator
28	убита	tests/test_outcome_gate_module.py::test_mandate_prefix_needs_separator,tests/test_outcome_gate_module.py::test_ac11_prefix_needs_separator_after_it
29	убита	tests/test_outcome_gate_module.py::test_ac11_role_autocommitted_answer_does_not_cover,tests/test_outcome_gate_module.py::test_ac11_role_autocommitted_id_mandate_does_not_cover
30	убита	tests/test_outcome_gate_module.py::test_ac13_passed_gate_journal_counts

Часть 3 (`--patches 31-35`). `git status --porcelain -- orchestrator/` перед стартом: пустой вывод.

# mutation-run №8 задачи 01M5PHK9K0YQCTPA6CK94BBZ33
# источник патчей: каталог на диске
# ревизия прогона: worktree 071800d4e679d80648f4b06c21df4542de2e689b
# тесты: tests/test_outcome_gate_module.py
# патч 31 mutation-031.diff sha256 75606e4fd1d20ae1c398271645e628b3aec69e12785458bf408e77b9e398ae6e
# патч 32 mutation-032.diff sha256 31d28986cd1cfc82d311237c2f535d214f4297e0a7b6cfe86879a2d3155b9dfd
# патч 33 mutation-033.diff sha256 eccd871aab688e2a9ab9e0b722ba73dd8e1858b69a21374571dcb55e13fe08b0
# патч 34 mutation-034.diff sha256 a8d21ebcd326420b9c52ace5528f64fb584a7f22de81e20113fa9a4c49a069b2
# патч 35 mutation-035.diff sha256 27fc5d96ee096cb31284164298964d38fffc5f7bb3681bce446c631ffa2eecbd
номер	исход	узлы
31	убита	tests/test_outcome_gate_module.py::test_ac12_exact_id_with_n_covers_other_variant_does_not
32	убита	tests/test_outcome_gate_module.py::test_ac13_refusal_hint_names_both_markers
33	убита	tests/test_outcome_gate_module.py::test_skip_growth_line
34	убита	tests/test_outcome_gate_module.py::test_covered_ids_round_trip_every_finding_kind
35	убита	tests/test_outcome_gate_module.py::test_fingerprint_sorted_unique_or_none

Шапки «до» и «после» согласованы: `git diff --quiet ed38d9879e02d12dc982d1979077b2c3c445382a 071800d4e679d80648f4b06c21df4542de2e689b -- orchestrator/` — код 0 (дерево `orchestrator/` не менялось и после подтяжки main dd9adb48); sha256 каждого из 35 патчей в шапках «после» №6–8 равен sha256 в шапках «до» (для 11 и 27 — шапкам перепрогонов №4 и №5).

## Доказательство: убившие узлы и упавшие утверждения

По логам прогонов патчей `mutation-run` (`.artel/logs/suite-run/01M5PHK9K0YQCTPA6CK94BBZ33/…-mutation-run-<n>-p<nnn>.log`): для каждой мутации доказательства — убивший узел и самая глубокая строка его трассы в тестовом файле, лежащая в утверждении вне `setUp` и методов песочницы, готовящих задачу. Узлов, убитых только падением этих методов, нет ни в одном прогоне — ни «до» (№1–5), ни «после» (№6–8): у каждого упавшего узла всех 72 логов прогонов патчей есть строка трассы в утверждении вне них; строк `ERROR at setup` и `ERROR collecting` в логах нет.

- mutation-001 до: убивший узел `Ac1OutOfBoundsTest::test_ac1_artel_and_test_profile_no_gate`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:907`.
- mutation-002 до: убивший узел `Ac1OutOfBoundsTest::test_ac1_decide_skip_refusal_and_canary_no_gate`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:907`.
- mutation-003 до: убивший узел `Ac5PassToPassTest::test_ac5_retried_on_base_not_in_pass_to_pass`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:882`.
- mutation-004 до: убивший узел `Ac2PlaceTest::test_ac2_outcome_refusal_stops_before_review_rework_gate`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:869`.
- mutation-005 до: убивший узел `Ac3RunsTest::test_ac3_full_suite_on_base_and_head_checkouts_fresh`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1104`.
- mutation-006 до: убивший узел `Ac4PrepareTest::test_ac4_git_preparation_failures_refuse`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:869`.
- mutation-007 до: убивший узел `Ac4PrepareTest::test_ac4_git_head_checkout_failure_refuses`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:869`.
- mutation-008 до: убивший узел `Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:869`.
- mutation-009 до: убивший узел `Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1141`.
- mutation-010 до: убивший узел `Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:869`.
- mutation-012 до: убивший узел `Ac7RerunPrepareTest::test_ac7_rerun_base_record_missing_refuses`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:869`.
- mutation-013 до: убивший узел `RecordLevelTest::test_red_on_branch_kinds`, упавшее утверждение `tests/test_outcome_integrity.py:53`.
- mutation-014 до: убивший узел `Ac6RerunTest::test_ac6_skipped_on_branch_not_rerun`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1573`.
- mutation-015 до: убивший узел `Ac7RerunPrepareTest::test_ac7_rerun_unknown_outcome_refuses`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:869`.
- mutation-016 до: убивший узел `Ac7RerunPrepareTest::test_ac7_rerun_base_record_missing_refuses`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:869`.
- mutation-017 до: убивший узел `Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:869`.
- mutation-018 до: убивший узел `Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:869`.
- mutation-019 до: убивший узел `Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:869`.
- mutation-020 до: убивший узел `Ac8VerdictByRecordTest::test_ac8_neighbour_red_in_same_file_does_not_redden_rerun`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:869`.
- mutation-021 до: убивший узел `Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:882`.
- mutation-022 до: убивший узел `Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:869`.
- mutation-023 до: убивший узел `Ac9CompareTest::test_ac9_junit_records_findings`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:2175`.
- mutation-024 до: убивший узел `Ac9CompareTest::test_ac9_one_finding_per_id_senior_kind`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:869`.
- mutation-025 до: убивший узел `Ac10OrderTest::test_ac10_findings_order_and_one_line_each`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:2256`.
- mutation-026 до: убивший узел `Ac11MandateTest::test_ac11_file_and_prefix_mandate_cover_findings`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:882`.
- mutation-028 до: убивший узел `RecordLevelTest::test_mandate_prefix_needs_separator`, упавшее утверждение `tests/test_outcome_integrity.py:121`.
- mutation-029 до: убивший узел `RoleAutocommitTest::test_ac11_role_autocommitted_id_mandate_does_not_cover`, упавшее утверждение `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py:507`.
- mutation-030 до: убивший узел `Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:2488`.

- mutation-011 до: убивший узел `Ac5PassToPassTest::test_ac5_no_tests_on_base_empty_pass_to_pass`, упавшее утверждение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:882`.
- mutation-027 до: убивший узел `RecordLevelTest::test_mandate_prefix_needs_separator`, упавшее утверждение `tests/test_outcome_integrity.py:122`.
- mutation-031 до: убивший узел `ExactIdTest::test_ac12_exact_id_with_n_covers_other_variant_does_not`, упавшее утверждение `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py:515`.
- mutation-032 до: убивший узел `HintTest::test_ac13_refusal_hint_names_both_markers`, упавшее утверждение `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py:604`.
- mutation-033 до: убивший узел `RecordLevelTest::test_skip_growth_line`, упавшее утверждение `tests/test_outcome_integrity.py:101`.
- mutation-034 до: убивший узел `RecordLevelTest::test_covered_ids_round_trip_every_finding_kind`, упавшее утверждение `tests/test_outcome_integrity.py:143`.
- mutation-035 до: убивший узел `RecordLevelTest::test_fingerprint_sorted_unique_or_none`, упавшее утверждение `tests/test_outcome_integrity.py:155`.

- mutation-001 после: убивший узел `tests/test_outcome_gate_module.py::test_ac1_artel_and_test_profile_no_gate`, упавшее утверждение `tests/test_outcome_gate_module.py:474`.
- mutation-002 после: убивший узел `tests/test_outcome_gate_module.py::test_ac1_decide_skip_refusal_and_canary_no_gate`, упавшее утверждение `tests/test_outcome_gate_module.py:474`.
- mutation-003 после: убивший узел `tests/test_outcome_gate_module.py::test_ac2_text_gate_refusal_first_no_outcome_runs`, упавшее утверждение `tests/test_outcome_gate_module.py:662`.
- mutation-004 после: убивший узел `tests/test_outcome_gate_module.py::test_ac2_outcome_refusal_stops_before_review_rework_gate`, упавшее утверждение `tests/test_outcome_gate_module.py:459`.
- mutation-005 после: убивший узел `tests/test_outcome_gate_module.py::test_ac3_full_suite_on_base_and_head_checkouts_fresh`, упавшее утверждение `tests/test_outcome_gate_module.py:738`.
- mutation-006 после: убивший узел `tests/test_outcome_gate_module.py::test_ac4_git_head_not_read_refuses`, упавшее утверждение `tests/test_outcome_gate_module.py:459`.
- mutation-007 после: убивший узел `tests/test_outcome_gate_module.py::test_ac4_git_head_checkout_failure_refuses`, упавшее утверждение `tests/test_outcome_gate_module.py:459`.
- mutation-008 после: убивший узел `tests/test_outcome_gate_module.py::test_ac4_side_not_started_or_timeout_refuses_naming_side`, упавшее утверждение `tests/test_outcome_gate_module.py:459`.
- mutation-009 после: убивший узел `tests/test_outcome_gate_module.py::test_ac4_side_head_timeout_refuses_naming_head`, упавшее утверждение `tests/test_outcome_gate_module.py:500`.
- mutation-010 после: убивший узел `tests/test_outcome_gate_module.py::test_ac7_branch_rerun_retried_is_red`, упавшее утверждение `tests/test_outcome_gate_module.py:459`.
- mutation-011 после: убивший узел `tests/test_outcome_gate_module.py::test_ac5_no_tests_on_base_empty_pass_to_pass`, упавшее утверждение `tests/test_outcome_gate_module.py:469`.
- mutation-012 после: убивший узел `tests/test_outcome_gate_module.py::test_ac7_rerun_base_skipped_refuses`, упавшее утверждение `tests/test_outcome_gate_module.py:459`.
- mutation-013 после: убивший узел `tests/test_outcome_gate_module.py::test_red_on_branch_kinds[case2-True]`, упавшее утверждение `tests/test_outcome_gate_module.py:2179`.
- mutation-014 после: убивший узел `tests/test_outcome_gate_module.py::test_ac6_skipped_on_branch_not_rerun`, упавшее утверждение `tests/test_outcome_gate_module.py:1176`.
- mutation-015 после: убивший узел `tests/test_outcome_gate_module.py::test_ac7_rerun_unknown_outcome_refuses`, упавшее утверждение `tests/test_outcome_gate_module.py:459`.
- mutation-016 после: убивший узел `tests/test_outcome_gate_module.py::test_ac7_rerun_base_skipped_refuses`, упавшее утверждение `tests/test_outcome_gate_module.py:459`.
- mutation-017 после: убивший узел `tests/test_outcome_gate_module.py::test_ac7_branch_rerun_retried_is_red`, упавшее утверждение `tests/test_outcome_gate_module.py:459`.
- mutation-018 после: убивший узел `tests/test_outcome_gate_module.py::test_ac7_branch_rerun_skipped_is_red`, упавшее утверждение `tests/test_outcome_gate_module.py:459`.
- mutation-019 после: убивший узел `tests/test_outcome_gate_module.py::test_ac7_branch_rerun_skipped_is_red`, упавшее утверждение `tests/test_outcome_gate_module.py:459`.
- mutation-020 после: убивший узел `tests/test_outcome_gate_module.py::test_ac8_unstable_after_change_general_refusal`, упавшее утверждение `tests/test_outcome_gate_module.py:459`.
- mutation-021 после: убивший узел `tests/test_outcome_gate_module.py::test_ac8_flaky_on_base_no_refusal`, упавшее утверждение `tests/test_outcome_gate_module.py:469`.
- mutation-022 после: убивший узел `tests/test_outcome_gate_module.py::test_ac7_branch_rerun_skipped_is_red`, упавшее утверждение `tests/test_outcome_gate_module.py:459`.
- mutation-023 после: убивший узел `tests/test_outcome_gate_module.py::test_ac9_vitest_records_findings_and_non_findings`, упавшее утверждение `tests/test_outcome_gate_module.py:1718`.
- mutation-024 после: убивший узел `tests/test_outcome_gate_module.py::test_ac9_one_finding_per_id_senior_kind`, упавшее утверждение `tests/test_outcome_gate_module.py:459`.
- mutation-025 после: убивший узел `tests/test_outcome_gate_module.py::test_ac10_findings_order_and_one_line_each`, упавшее утверждение `tests/test_outcome_gate_module.py:1839`.
- mutation-026 после: убивший узел `tests/test_outcome_gate_module.py::test_mandate_prefix_needs_separator`, упавшее утверждение `tests/test_outcome_gate_module.py:2247`.
- mutation-027 после: убивший узел `tests/test_outcome_gate_module.py::test_mandate_prefix_needs_separator`, упавшее утверждение `tests/test_outcome_gate_module.py:2252`.
- mutation-028 после: убивший узел `tests/test_outcome_gate_module.py::test_mandate_prefix_needs_separator`, упавшее утверждение `tests/test_outcome_gate_module.py:2251`.
- mutation-029 после: убивший узел `tests/test_outcome_gate_module.py::test_ac11_role_autocommitted_answer_does_not_cover`, упавшее утверждение `tests/test_outcome_gate_module.py:459`.
- mutation-030 после: убивший узел `tests/test_outcome_gate_module.py::test_ac13_passed_gate_journal_counts`, упавшее утверждение `tests/test_outcome_gate_module.py:2059`.
- mutation-031 после: убивший узел `tests/test_outcome_gate_module.py::test_ac12_exact_id_with_n_covers_other_variant_does_not`, упавшее утверждение `tests/test_outcome_gate_module.py:529`.
- mutation-032 после: убивший узел `tests/test_outcome_gate_module.py::test_ac13_refusal_hint_names_both_markers`, упавшее утверждение `tests/test_outcome_gate_module.py:2146`.
- mutation-033 после: убивший узел `tests/test_outcome_gate_module.py::test_skip_growth_line`, упавшее утверждение `tests/test_outcome_gate_module.py:2230`.
- mutation-034 после: убивший узел `tests/test_outcome_gate_module.py::test_covered_ids_round_trip_every_finding_kind`, упавшее утверждение `tests/test_outcome_gate_module.py:2274`.
- mutation-035 после: убивший узел `tests/test_outcome_gate_module.py::test_fingerprint_sorted_unique_or_none`, упавшее утверждение `tests/test_outcome_gate_module.py:2286`.

Находок нет: каждую из 35 мутаций убил хотя бы один узел и «до», и «после»; исходов «оборвана по пределу»/«не прогнана (предел)» нет. Удалённых дублей нет: все 53 теста перенесены функциями модуля.

## Перенос песочниц

- Сверка `ast.dump` переноса `tests/outcome_gate_sandbox.py`: 60 утверждений верхнего уровня строк 47–899 исходного файла A против 60 утверждений модуля после докстринга — набор, порядок и `ast.dump` каждого совпадают (скрипт `ast.parse` + попарное `ast.dump`, итог `60 60 True`); докстринг модуля — одна строка назначения.
- Переименования в id-песочнице (имя совпадает с `tests/outcome_gate_sandbox.py` при другом содержимом): `GATE_ACTIONS` → `ID_GATE_ACTIONS`, `VITEST_KIND` → `ID_VITEST_KIND`, `spec_text` → `id_spec_text`, с употреблениями (в том числе в `IdOutcomeGateSandbox` и в функции `id_no_gate_refusal`). Других переименований нет.
- Выбор по 17 именам, совпадающим дословно: все 17 — импортом из `tests.outcome_gate_sandbox` (одно связывание на имя): `REAL_POPEN`, `CROCKFORD`, `LETTERS`, `PLANK_DIR`, `VITEST_BIN`, `VITEST_REPORT_ARGS`, `LONG_TEMPLATE`, `OUTCOME_ACTION`, `APPROVED_DETAIL`, `CLAIM`, `ENTRY_HEAD`, `PLAN_READY`, `MATRIX_HEADERS`, `ulid`, `flow`, `arg_value`, `js_source`.
- Помощники — функции модуля `tests/test_outcome_gate_module.py` (первый параметр — стенд `box`): `refusal`, `no_gate_refusal`, `assert_no_gate`, `assert_prepare` (внутри — `refusal(box, …)`), `prepared`, `broken_task`, `gate_refusal`, `id_no_gate_refusal`; фикстуры `box`/`id_box` только создают стенд (`_sandbox(OutcomeGateSandbox)`, `_sandbox(IdOutcomeGateSandbox)`).
- Отступления от дословности тестов: `RecordLevelTest::test_red_on_branch_kinds` — литеральный `subTest` без общего состояния стал `parametrize` (6 вариантов; сравнивалось с переменной, не литералом); обёртки `subTest` в тестах со стендом сняты, циклы сохранены; блок `if __name__ == "__main__"` файла C не перенесён.

## Числа свода

- До: 53 теста в трёх файлах, 3262 строки (2493 + 609 + 160); адресный прогон по SPEC — около 671 с (657 с + 14 с + 0,3 с).
- После: 53 тестовые функции (58 узлов сбора), 2287 строк `tests/test_outcome_gate_module.py` и 854 строки `tests/outcome_gate_sandbox.py`; адресный прогон `python3 -m pytest tests/test_outcome_gate_module.py -p no:cacheprovider -p timeout -o timeout=120` под ролью (коммит 071800d4) — `58 passed in 230.43s`, то есть 230 с.
- Зелень трёх импортёров по CI кодовой ветки (`tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`, `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py`, `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py`): на момент сдачи шага ветка задачи в origin не выложена (`git ls-remote origin "refs/heads/task/01m5phk9k0yqctpa6ck94bbz33*"` — пусто), CI кодовой ветки ещё не запускался; итог даст CI после выкладки ветки пультом на `verifying`. Под ролью импортёры адресно не гонялись (требование 14 — один файл за шаг, им был `tests/test_outcome_gate_module.py`); смоделированный в SPEC перенос с заменой строки импорта — 80 тестов без потерь.

## Шаги

1. Набор мутаций (35 патчей) и таблица «до».
2. `tests/outcome_gate_sandbox.py` и импортёры.
3. `tests/test_outcome_gate_module.py`: id-песочница, помощники, фикстуры, 53 теста.
4. Удаление трёх исходных файлов, карта кода генератором.
5. Таблица «после», сверка шапок, адресный прогон.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1, 5 |
| 4 | 1, 5 |
| 5 | 2 |
| 6 | 2 |
| 7 | 3 |
| 8 | 3 |
| 9 | 3 |
| 10 | 3 |
| 11 | 3 |
| 12 | 3 |
| 13 | 5 |
| 14 | 5 |
| 15 | 4 |
| 16 | 2, 3, 4 |
| 17 | — (сессия при Операторе) |

## Влияние на систему

Меняется только `tests/`: три файла удалены, два новых, три строки импорта;
`orchestrator/`, `tests/fixtures.py`, `tests/sandbox.py` не меняются.
Откат — revert merge-коммита. Мандат на удаление трёх файлов — ANSWER-1.

## Предложения системе

- `orchestrator/mutation_run.py`: при занятом замке `suite_lock` команда отказывает сразу, ожидания в очереди нет — шагу роли пришлось крутить цикл повторного запуска раз в 30 с (обход вместо команды пульта); не хватает `mutation-run … --queue` (встать в очередь замка и стартовать по его освобождении).
- Шаг роли (`AGENT_TIMEOUT_SEC` 2700 с) короче одной части `mutation-run` из 15 патчей (около 900 с) при занятом замке: волна сведения заведомо занимает несколько шагов разработчика.

## Риски

- Шаг роли короче прогонов мутаций — таблицы «до»/«после» собираются за
  несколько шагов.
