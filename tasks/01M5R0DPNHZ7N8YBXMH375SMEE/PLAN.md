---
task: 01M5R0DPNHZ7N8YBXMH375SMEE
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Сведение тестов, волна 2а-2а — песочница мержа в `tests/merge_outcome_sandbox.py`, тесты `merge_outcome_gate` в `tests/test_merge_outcome_module.py`, тесты `added_lines` в `tests/test_outcome_gate_module.py`

## Подход

Доказательство неослабления — множество убиваемых патчей набора `mutation-<nnn>.diff`
каталога документов: «до» на исходных файлах базы (`--ref base`), «после» на
приёмниках рабочей копии (`--ref worktree`), теми же диапазонами и тем же числом
рабочих процессов (по умолчанию, `auto`). Патчи строит сценарий `mutgen.py`
каталога документов (правки «было → стало» по номерам), каждый проверен
`git apply --check` на чистом дереве; патчи меняют только `orchestrator/`.

Набор: 55 патчей — 001–049 группы М (19 заявок `merge_outcome_gate`, по патчу на
каждую несовпадающую по смыслу альтернативу заявки), 050–055 группы Д (6 заявок
`added_lines`). Части «до» и «после»: группа М — `1-10`, `11-20`, `21-30`,
`31-40`, `41-49`; группа Д — `50-55`.

Перенос:
- `tests/merge_outcome_sandbox.py` — строки 42–99, 101–365, 955–980 старого
  файла дословно, в том же порядке, новый однострочный докстринг; сверка
  `ast.dump`: 38 операторов верхнего уровня, все равны исходным (сценарий
  `python3 -c` по `git show HEAD:<старый файл>` до удаления).
- `tests/test_merge_outcome_module.py` — 19 функций, фикстуры `box`
  (`_sandbox(MergeOutcomeSandbox)`) и `two_sided_box` (`_sandbox(TwoSidedSandbox)`,
  бывшие `Ac11`, `Ac12`, `Ac14`), функция `no_gate_refusal` — по `ast.dump` равна
  одноимённой функции `tests/test_outcome_gate_module.py` (сверено: `True`).
  Бывшие `subTest` — прежним циклом или прямым кодом; ярлык и зерно — в
  локальном `case = f"<ярлык>, зерно {box.seed}: "` спереди сообщения каждого
  утверждения подслучая (у бывших `Ac11`, `Ac12` — `tag`, так как `case` там —
  переменная цикла исходника).
- `tests/test_outcome_gate_module.py` — дописан в конец раздел `added_lines`:
  `git(box, *args)`, фикстура `added_repo(tmp_dir)`, `commit(box)`,
  `files(tests=())` и 6 тестов; импорт `from orchestrator.advance_gates import
  outcome_integrity` — следующей строкой после `… as gate`; докстринг дополнен
  абзацем о своде.
- Импортёры `outcome_prior` и `outcome_components` — только строка источника
  импорта (`tests.merge_outcome_sandbox`).

## Шаги

1. Патчи мутаций и таблицы «до» (группа М — пять частей, группа Д — одна часть).
2. Песочница, новый модуль, раздел `added_lines`, импортёры, удаление двух
   файлов волны, карта кода (`python3 scripts/codebase_map.py`).
3. Таблицы «после» теми же частями, строки падений «до» и «после», соответствие
   «до → после», числа и время.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 3 |
| 4 | 1, 3 |
| 5 | 1, 3 |
| 6 | 1, 3 |
| 7 | 1, 3 |
| 8 | 1, 3 |
| 9 | 1–3 |
| 10 | 2 |
| 11 | 2 |
| 12 | 2 |
| 13 | 2 |
| 14 | 2 |
| 15 | 2 |
| 16 | 2 |
| 17 | 2 |
| 18 | 2 |
| 19 | 3 |
| 20 | 3 |
| 21 | 3 |
| 22 | 3 |
| 23 | 2 |
| 24 | 2 |
| 25 | вне ролей (сессия при Операторе) |

## Мутации и заявки

### Группа М (`tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`)

- mutation-001: `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` («строка доказательства не пишется»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_judge` не пишет строку `proof` в запись пройденного гейта.
- mutation-002: `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` («стоит не после строки чисел»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_judge` пишет `proof` перед строкой чисел.
- mutation-003: `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` («голова и база перепутаны»); патч `orchestrator/advance_gates/outcome_integrity.py`: в строке `proof` голова и база местами.
- mutation-004: `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` («ключ по коммиту, а не по дереву»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_component_key` считает ключ по sha головы вместо дерева.
- mutation-005: `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` («ключ с `base=True`»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_component_key` зовёт `report_suite_result_key(tree, profile, True, …)`.
- mutation-006: `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` («отпечаток без сортировки»); патч `orchestrator/advance_gates/outcome_integrity.py`: `fingerprint` сортирует по убыванию (вход `_judge` уже упорядочен по возрастанию, поэтому «без сортировки» воплощено обратным порядком).
- mutation-007: `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` («по всем элементам мандата, включая непокрывший»); патч `orchestrator/advance_gates/outcome_integrity.py`: в `_judge` к покрывшим элементам добавлены все элементы мандата.
- mutation-008: `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` («через запятую»); патч `orchestrator/advance_gates/outcome_integrity.py`: `fingerprint` соединяет элементы запятой.
- mutation-009: `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` («пустой отпечаток вместо «нет»»); патч `orchestrator/advance_gates/outcome_integrity.py`: `fingerprint` без элементов отдаёт пустую строку.
- mutation-010: `Ac1ProofLineTest::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record` («ключ `None` пишется в строку записи и гейт пройден»), `Ac3MergePrepareTest::test_ac3_prepare_failures_keep_merge_gate_without_push` («ключ `None` сравнивается как значение — прогон и проход») — одинаковы по смыслу; патч `orchestrator/advance_gates/outcome_integrity.py`: `_component_key` не отказывает при ключе `None`.
- mutation-011: `Ac1ProofLineTest::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record` («сбой ключа проглочен — запись без строки доказательства»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_component_key` не отказывает при `None`, `_judge` при ключе `None` не пишет строку `proof`.
- mutation-012: `Ac2MergeFindingTest::test_ac2_finding_without_mandate_escalates_merge` («гейт исходов не включён в окно мержа»); патч `orchestrator/fsm_merge_gate.py`: вызов `_outcome_integrity_merge_gate` выключен (`False and …`).
- mutation-013: `Ac2MergeFindingTest::test_ac2_finding_without_mandate_escalates_merge` («сломан правкой» пишется своим действием); патч `orchestrator/advance_gates/outcome_integrity.py`: `merge_gate_escalates` пишет действие `refusal.action` с заменой префикса на «merge отклонён: …» («… — сломан правкой»).
- mutation-014: `Ac2MergeFindingTest::test_ac2_finding_without_mandate_escalates_merge` («возвращает задачу в `in_dev`»); патч `orchestrator/advance_gates/outcome_integrity.py`: `merge_gate_escalates` ставит `in_dev` вместо `escalated`.
- mutation-015: `Ac2MergeFindingTest::test_ac2_finding_without_mandate_escalates_merge` («исчезновение теста не эскалирует»); патч `orchestrator/advance_gates/outcome_integrity.py`: `merge_gate_escalates` возвращает `False` при действии `OUTCOME_REFUSAL_ACTION` (не только «сломан правкой»).
- mutation-016: `Ac2MergeFindingTest::test_ac2_merge_refusal_action_is_operator_class_key` («ключ не добавлен в словарь»); патч `orchestrator/advance_gates/refusal_classes.py`: строка `OUTCOME_MERGE_REFUSAL_ACTION` убрана из `REFUSAL_CLASSES`.
- mutation-017: `Ac2MergeFindingTest::test_ac2_merge_refusal_action_is_operator_class_key` («действие отнесено к «чинит роль»»); патч `orchestrator/advance_gates/refusal_classes.py`: значение ключа — `ROLE_FIXES`.
- mutation-018: `Ac3MergePrepareTest::test_ac3_prepare_failures_keep_merge_gate_without_push` («сбой подготовки пропускает гейт — мерж идёт к CI»); патч `orchestrator/advance_gates/outcome_integrity.py`: `merge_gate_escalates` при отказе подготовки возвращает `False`.
- mutation-019: `Ac3MergePrepareTest::test_ac3_prepare_failures_keep_merge_gate_without_push` («сбой проглочен — гейт пройден, задача в `done`»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_gate` при `_Prepare` возвращает `None`.
- mutation-020: `Ac3MergePrepareTest::test_ac3_prepare_failures_keep_merge_gate_without_push` («fresh» без sha main берёт базой `diff_base`); патч `orchestrator/advance_gates/outcome_integrity.py`: `_merge_base_of` без sha main подставляет `gitcmd.diff_base`.
- mutation-021: `Ac4ProofTest::test_ac4_same_quadruple_proves_without_run` («доказательство не ищется»); патч `orchestrator/advance_gates/outcome_integrity.py`: в `_judge` проверка `_proven` выключена.
- mutation-022: `Ac4ProofTest::test_ac4_same_quadruple_proves_without_run` («при покрытии мандатом отпечаток текущего мандата сверяется неверно»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_proven` считает отпечаток по именам ANSWER вместо элементов.
- mutation-023: `Ac4ProofTest::test_ac4_same_quadruple_proves_without_run` («текст записи с полным sha»); патч `orchestrator/advance_gates/outcome_integrity.py`: запись «доказан» несёт полный sha головы.
- mutation-024: `Ac4ProofTest::test_ac4_same_quadruple_proves_without_run` («текст записи без базы»); патч `orchestrator/advance_gates/outcome_integrity.py`: запись «доказан» без базы.
- mutation-025: `Ac5ProofMismatchTest::test_ac5_other_base_key_or_mandate_runs_gate` («сверяет только голову»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_proven` сравнивает `fields[:1]`.
- mutation-026: `Ac5ProofMismatchTest::test_ac5_other_base_key_or_mandate_runs_gate` («не сверяет ключ»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_proven` сравнивает `fields[:2]`.
- mutation-027: `Ac5ProofMismatchTest::test_ac5_other_base_key_or_mandate_runs_gate` («отпечаток записи не сравнивается с текущим»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_proven` не сверяет отпечаток.
- mutation-028: `Ac6LegacyRecordTest::test_ac6_record_without_proof_line_runs_gate` («запись без строки доказательства принимается»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_proven` возвращает `True` на записи без строки доказательства.
- mutation-029: `Ac7MergeBaseTest::test_ac7_base_is_merge_base_with_fetched_main_not_diff_base` («база на мерже — повторный `diff_base`»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_merge_base_of` берёт базой `gitcmd.diff_base`.
- mutation-030: `Ac7MergeBaseTest::test_ac7_doc_only_lag_runs_gate_with_merge_base` («базой служит сам зафетченный sha main»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_merge_base_of` отдаёт sha main.
- mutation-031: `Ac7MergeBaseTest::test_ac7_doc_only_lag_runs_gate_with_merge_base` («документное отставание — сбой подготовки»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_merge_base_of` отказывает, если merge-base не равен sha main.
- mutation-032: `Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks` («гейт после `_acceptance_locks_refuse`»); патч `orchestrator/fsm_merge_gate.py`: сверка лока перед гейтом исходов.
- mutation-033: `Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks` («гейт до `_sync_main_or_wait`»); патч `orchestrator/fsm_merge_gate.py`: гейт исходов перед сверкой свежести.
- mutation-034: `Ac7MergeBaseTest::test_ac7_canary_from_db_and_in_dev_base_is_diff_base` («признак канарейки не читается на мерже»); патч `orchestrator/advance_gates/outcome_integrity.py`: `merge_gate_escalates` (одна запись профиля) без проверки `is_canary`.
- mutation-035: `Ac7MergeBaseTest::test_ac7_canary_from_db_and_in_dev_base_is_diff_base` («база выхода из `in_dev` — голова»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_diff_base` отдаёт sha головы.
- mutation-036: `Ac7MergeBaseTest::test_ac7_canary_from_db_and_in_dev_base_is_diff_base` («база выхода из `in_dev` — sha зафетченного main»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_diff_base` отдаёт sha `refs/remotes/origin/main`.
- mutation-037: `Ac8ReviewLinesTest::test_ac8_review_section_carries_outcome_gate_lines_for_head` («раздел строится только по гейту по тексту»); патч `orchestrator/review.py`: `_outcome_gate_lines` всегда `None`.
- mutation-038: `Ac8ReviewLinesTest::test_ac8_review_section_carries_outcome_gate_lines_for_head` («запись ищется не по текущей голове»); патч `orchestrator/advance_gates/outcome_integrity.py`: `review_lines` сверяет с головой поле базы записи.
- mutation-039: `Ac8ReviewLinesTest::test_ac8_review_section_carries_outcome_gate_lines_for_head` («покрытые без имени ANSWER»); патч `orchestrator/advance_gates/outcome_integrity.py`: `review_lines` отрезает « — покрыто мандатом ANSWER-n».
- mutation-040: `Ac9ReviewNotRunTest::test_ac9_no_record_for_current_head_says_not_run` («запись берётся последняя без сверки головы»); патч `orchestrator/advance_gates/outcome_integrity.py`: `review_lines` не сверяет голову.
- mutation-041: `Ac9ReviewNotRunTest::test_ac9_no_record_for_current_head_says_not_run` («при отсутствии записи нет строки»); патч `orchestrator/advance_gates/outcome_integrity.py`: `review_lines` без записи отдаёт пустой список.
- mutation-042: `Ac9ReviewNotRunTest::test_ac9_no_record_for_current_head_says_not_run` («при отсутствии записи раздела нет»); патч `orchestrator/review.py`: `_outcome_gate_lines` отдаёт `None` при строке «не исполнялся».
- mutation-043: `Ac10NoPythonSectionTest::test_ac10_component_without_python_has_section_except_canary` («раздел только при строках гейта по тексту»); патч `orchestrator/review.py`: условие раздела без `outcome_lines`.
- mutation-044: `Ac10NoPythonSectionTest::test_ac10_component_without_python_has_section_except_canary` («канареечная задача получает раздел»); патч `orchestrator/review.py`: `_changed_assertions_part` без проверки `is_canary`.
- mutation-045: `Ac11TwoSidedErrorNameTest::test_ac11_only_check_failure_is_failure_on_check` («признак проверки — любой `failed`, как до задачи»); патч `orchestrator/advance_gates/two_sided.py`: `_run_side_report` не входит в ветку профиля в границе.
- mutation-046: `Ac11TwoSidedErrorNameTest::test_ac11_only_check_failure_is_failure_on_check` («классификатор не зовётся вовсе»); патч `orchestrator/advance_gates/two_sided.py`: вид записи — постоянная строка вместо `_check_failure_kind`.
- mutation-047: `Ac12TwoSidedRetryTest::test_ac12_passed_with_retry_is_side_failure_retry` («`passed` с повтором — зелёный»); патч `orchestrator/advance_gates/two_sided.py`: ветка профиля в границе без `passed` с повтором.
- mutation-048: `Ac13RetriedBaseRerunTest::test_ac13_retried_on_base_rerun_is_red_base` («на перепрогоне базы зелёный — любой `passed`»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_rerun` на стороне базы считает зелёным любой `passed`.
- mutation-049: `Ac14OutOfBoundsTest::test_ac14_test_profile_and_multi_component_keep_prior_results` («граница по `reported(profile)` без `from_components`»); патч `orchestrator/advance_gates/acceptance.py`: `in_outcome_bounds` без `from_components`.

### Группа Д (`tests/test_outcome_integrity_added_lines.py`)

- mutation-050: `AddedLinesTest::test_quoted_path_latin1_text_and_no_final_newline` («строка «\ No newline» считается добавленной»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_added_lines` добавляет строку `\…` вне ханка в добавленные. Альтернативы «путь не снимается с кавычек» и «строгое декодирование» отдельными патчами не воплощены: их следствие — исключение (`KeyError` по ключу `added[odd]`, `UnicodeDecodeError`), не падение утверждения (требование 4).
- mutation-051: `AddedLinesTest::test_noprefix_config_does_not_hide_added_lines` («префиксы убраны из argv — разбор молча теряет строки»); патч `orchestrator/advance_gates/outcome_integrity.py`: из argv `_added_lines` убраны `--src-prefix=a/ --dst-prefix=b/`, заголовок без `b/` ставит путь `None`. Альтернатива «отказывает подготовкой» — исключение `_Prepare`, не падение утверждения (требование 4).
- mutation-052: `AddedLinesTest::test_unexpected_header_is_prepare_refusal` («заголовок неожиданной формы ставит путь `None`»); патч `orchestrator/advance_gates/outcome_integrity.py`: в `_added_lines` вместо `_Prepare` — `path = None`.
- mutation-053: `AddedLinesTest::test_deleted_file_header_dev_null_is_not_refusal` («`/dev/null` попадает под разбор пути»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_added_lines` заводит запись `/dev/null`. Патч переписан под падение утверждения: дословная альтернатива заявки («под проверку префикса `b/`») даёт исключение `_Prepare`.
- mutation-054: `CodeExceptionRenameTest::test_rename_from_test_path_to_code_path_is_checked` («вид файла и по старому пути переименования»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_code_exception_findings` пропускает путь, если тестовый и прежний путь переименования.
- mutation-055: `CodeExceptionRenameTest::test_rename_between_test_paths_is_not_checked` («правило файла `A` не распространено на `R`»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_code_exception_findings` освобождает только `A`/`C`.

## Мутации до

```text
# mutation-run №1 задачи 01M5R0DPNHZ7N8YBXMH375SMEE
# источник патчей: каталог на диске
# ревизия прогона: base 72d52fd367828949767e234ecbe9b0cc79851084
# тесты: tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py
# рабочих процессов: auto
# патч 1 mutation-001.diff sha256 e15e3e312c82c7f68c88d7ae0be49865fe59776addd9e0f857e900b8935cadae
# патч 2 mutation-002.diff sha256 9a6c4d2dd3f80d13809d9f2600aca7083ee905730ef459918ae43f3a124a5d59
# патч 3 mutation-003.diff sha256 d648d0515889a04fb06feba9aac3f418bfe9524e6b8cecf5d8963a5393049ded
# патч 4 mutation-004.diff sha256 ae1a106756db6a4d06f94ccdcde7e6fdfcb6a8fb460e56a3a89c04e8ae1ea7d2
# патч 5 mutation-005.diff sha256 0bf230c1aa301d02cc0591e153a4a2084bd7d9957d235f3d0fb4b8b7da1bcab0
# патч 6 mutation-006.diff sha256 d8a1f7e259f3edf6c5a825790f0db17e3341aaf2d9f584dfcf023cb954957198
# патч 7 mutation-007.diff sha256 c8bfcb669b1fcf7f2e1fc03340c6509cc9496e6957d04b79a26f3fbd1a27251a
# патч 8 mutation-008.diff sha256 af1f01ba4d92f145f496c90ba41688384b2c03bf630bbdf3ff3073f9d28da460
# патч 9 mutation-009.diff sha256 b17128a55697c6006b0d3cafec4388cf59b614211a45438e8ff88addc88ea5ee
# патч 10 mutation-010.diff sha256 911b1c3f08d2d708714db000d3c48712b522ecff7259ffcc9338f59f07ea6d62
номер	исход	узлы
1	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac8ReviewLinesTest::test_ac8_review_section_carries_outcome_gate_lines_for_head,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac6LegacyRecordTest::test_ac6_record_without_proof_line_runs_gate,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac5ProofMismatchTest::test_ac5_other_base_key_or_mandate_runs_gate,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac4ProofTest::test_ac4_same_quadruple_proves_without_run,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_canary_from_db_and_in_dev_base_is_diff_base,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks
2	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate
3	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac8ReviewLinesTest::test_ac8_review_section_carries_outcome_gate_lines_for_head,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_canary_from_db_and_in_dev_base_is_diff_base,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac4ProofTest::test_ac4_same_quadruple_proves_without_run
4	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate
5	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac3MergePrepareTest::test_ac3_prepare_failures_keep_merge_gate_without_push,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac1ProofLineTest::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record
6	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate
7	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate
8	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate
9	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac4ProofTest::test_ac4_same_quadruple_proves_without_run,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac6LegacyRecordTest::test_ac6_record_without_proof_line_runs_gate,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_canary_from_db_and_in_dev_base_is_diff_base
10	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac3MergePrepareTest::test_ac3_prepare_failures_keep_merge_gate_without_push,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac1ProofLineTest::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record
```

```text
# mutation-run №2 задачи 01M5R0DPNHZ7N8YBXMH375SMEE
# источник патчей: каталог на диске
# ревизия прогона: base 72d52fd367828949767e234ecbe9b0cc79851084
# тесты: tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py
# рабочих процессов: auto
# патч 11 mutation-011.diff sha256 f0844eaa333ae6dcdfbda7b023f1009c3c25682bc6fb01c769160f1b28e135c8
# патч 12 mutation-012.diff sha256 7df050f0f5036fe4057280df666c22c3017bf4c179369b4e0a131d4c24238025
# патч 13 mutation-013.diff sha256 68c4795c7d9bf79b5db3753ee8fb6c09f4692c228841897462d2a9c4c33da28a
# патч 14 mutation-014.diff sha256 c7767ffd6cf90acce75d62404ed17daf5c19943f7912c0ddcba301eeace739af
# патч 15 mutation-015.diff sha256 f2c8b942bf1fdd1f77f333f57fbc7b640323d2ec76b228fd6aa2f770944ca481
# патч 16 mutation-016.diff sha256 c02267aa1aec88f9a386b33f700354a6d8f5d2ceca50e9f436832cb736429e6f
# патч 17 mutation-017.diff sha256 8080181d0e748b3645368a2267dc19fdac6d3524ed18ebd9fa5410710f399800
# патч 18 mutation-018.diff sha256 0c03108a3dec016ed0c7df84f0e87ae87d86266f71d42f70a1e14f54e83a75d4
# патч 19 mutation-019.diff sha256 e38090114613554d5ff1309f2ef0f1e1f91b075094f2c43c2e231774279a185b
# патч 20 mutation-020.diff sha256 8bccd7f2304d3c6b0fb49c5bc0df0823b406456b03e9c560ffb2adbb70edebdd
номер	исход	узлы
11	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac1ProofLineTest::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac3MergePrepareTest::test_ac3_prepare_failures_keep_merge_gate_without_push
12	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac3MergePrepareTest::test_ac3_prepare_failures_keep_merge_gate_without_push,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac6LegacyRecordTest::test_ac6_record_without_proof_line_runs_gate,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac5ProofMismatchTest::test_ac5_other_base_key_or_mandate_runs_gate,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac2MergeFindingTest::test_ac2_finding_without_mandate_escalates_merge,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_base_is_merge_base_with_fetched_main_not_diff_base,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac4ProofTest::test_ac4_same_quadruple_proves_without_run,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_doc_only_lag_runs_gate_with_merge_base
13	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac2MergeFindingTest::test_ac2_finding_without_mandate_escalates_merge
14	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac2MergeFindingTest::test_ac2_finding_without_mandate_escalates_merge
15	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac2MergeFindingTest::test_ac2_finding_without_mandate_escalates_merge
16	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac2MergeFindingTest::test_ac2_merge_refusal_action_is_operator_class_key
17	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac2MergeFindingTest::test_ac2_merge_refusal_action_is_operator_class_key
18	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac3MergePrepareTest::test_ac3_prepare_failures_keep_merge_gate_without_push
19	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac1ProofLineTest::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac3MergePrepareTest::test_ac3_prepare_failures_keep_merge_gate_without_push
20	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac3MergePrepareTest::test_ac3_prepare_failures_keep_merge_gate_without_push
```

```text
# mutation-run №3 задачи 01M5R0DPNHZ7N8YBXMH375SMEE
# источник патчей: каталог на диске
# ревизия прогона: base 72d52fd367828949767e234ecbe9b0cc79851084
# тесты: tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py
# рабочих процессов: auto
# патч 21 mutation-021.diff sha256 7880f06f8fe97ac72adf35a34145741ed664ba577998036dc817b5252cb3b930
# патч 22 mutation-022.diff sha256 a04460424dc3e72bd63d536f1694587d686c35ac974e0f5ff532ce5604e1e0d7
# патч 23 mutation-023.diff sha256 40c384680bac5d1f130870d0f9229d66f790cd2723bdddccbbb3b06672af192b
# патч 24 mutation-024.diff sha256 a7401a896d9df6b9d234332f7cea98ab9f4a6e7d7ebdd243b12b432c0bee50c0
# патч 25 mutation-025.diff sha256 626db19b5e094df829cd02c08d0dbb42c2f92ac82afdd349a20fe9f686f8e57b
# патч 26 mutation-026.diff sha256 804fd02518fa634d33bd35291cfd1543fa8e7090668fba969efe159309727481
# патч 27 mutation-027.diff sha256 e95d52fef406fb249c204c12b9d5e6c6b0e768068aabdd6c93b2aa7912848a44
# патч 28 mutation-028.diff sha256 d89171aa69548abd829d201749b1c64b470f98b875742a2eb060a9dfd5487909
# патч 29 mutation-029.diff sha256 fb5be695a2a2fd558e1f49fb13ae1e292cf51f116c0739c52cadded2942949ad
# патч 30 mutation-030.diff sha256 23edc0593e98baf2ba0843b6cec6520173991761705976f013807485dabc5fb4
номер	исход	узлы
21	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac4ProofTest::test_ac4_same_quadruple_proves_without_run
22	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac4ProofTest::test_ac4_same_quadruple_proves_without_run
23	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac4ProofTest::test_ac4_same_quadruple_proves_without_run,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks
24	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac4ProofTest::test_ac4_same_quadruple_proves_without_run,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks
25	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac5ProofMismatchTest::test_ac5_other_base_key_or_mandate_runs_gate
26	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac5ProofMismatchTest::test_ac5_other_base_key_or_mandate_runs_gate
27	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac5ProofMismatchTest::test_ac5_other_base_key_or_mandate_runs_gate
28	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac6LegacyRecordTest::test_ac6_record_without_proof_line_runs_gate
29	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_base_is_merge_base_with_fetched_main_not_diff_base
30	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_doc_only_lag_runs_gate_with_merge_base
```

```text
# mutation-run №4 задачи 01M5R0DPNHZ7N8YBXMH375SMEE
# источник патчей: каталог на диске
# ревизия прогона: base 72d52fd367828949767e234ecbe9b0cc79851084
# тесты: tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py
# рабочих процессов: auto
# патч 31 mutation-031.diff sha256 6adbfb6fd6caed34c4624ce4bf4311203a769866ccbc722b6f2187748a90ef61
# патч 32 mutation-032.diff sha256 299378cb62a52aa816dea4f42dd9ea33a28e95d1a89ef86f7c57b54a3c5691fe
# патч 33 mutation-033.diff sha256 4eb64fec5193c3299b301f5418d01993994312dd411005d8463f6adaf58b0322
# патч 34 mutation-034.diff sha256 5d7ae52332efa15d97d59840f729a9d653b61a568a3ada347955e5373f20537c
# патч 35 mutation-035.diff sha256 7e7a0c6b25560f00b24b7c96280a88706fd0b66e73d8054b964a902a49821295
# патч 36 mutation-036.diff sha256 3f7a7b3e5e05afad183651a9e75df7e2effba03c1068648fac81d7d24a92f5b1
# патч 37 mutation-037.diff sha256 c9e7e3edfa5cf4fba679f038c276f53b43e0da54df84285ef9cd3034c060251c
# патч 38 mutation-038.diff sha256 ba4f68f5342bb2b145611eae1213afd08aceea5a5d0a21da0b5aee6d5ab86da6
# патч 39 mutation-039.diff sha256 8bf41e531ef69c8d55d9925d89c59ae7cc97b62e344d8f70eeadcb2ce413e82c
# патч 40 mutation-040.diff sha256 2a7c97e8047f2e1a81f8d75279c1d37873fb4829ff95c7bf1b8359fda544352a
номер	исход	узлы
31	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_doc_only_lag_runs_gate_with_merge_base
32	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks
33	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks
34	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_canary_from_db_and_in_dev_base_is_diff_base
35	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac4ProofTest::test_ac4_same_quadruple_proves_without_run,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac8ReviewLinesTest::test_ac8_review_section_carries_outcome_gate_lines_for_head,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac7MergeBaseTest::test_ac7_canary_from_db_and_in_dev_base_is_diff_base,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac13RetriedBaseRerunTest::test_ac13_retried_on_base_rerun_is_red_base
36	не убита	
37	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac9ReviewNotRunTest::test_ac9_no_record_for_current_head_says_not_run,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac8ReviewLinesTest::test_ac8_review_section_carries_outcome_gate_lines_for_head,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac10NoPythonSectionTest::test_ac10_component_without_python_has_section_except_canary
38	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac8ReviewLinesTest::test_ac8_review_section_carries_outcome_gate_lines_for_head
39	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac8ReviewLinesTest::test_ac8_review_section_carries_outcome_gate_lines_for_head
40	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac9ReviewNotRunTest::test_ac9_no_record_for_current_head_says_not_run
```

```text
# mutation-run №5 задачи 01M5R0DPNHZ7N8YBXMH375SMEE
# источник патчей: каталог на диске
# ревизия прогона: base 72d52fd367828949767e234ecbe9b0cc79851084
# тесты: tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py
# рабочих процессов: auto
# патч 41 mutation-041.diff sha256 fe0646b7d1f1ddc8e900913bbb30bac6aae561406e3b0b30fb3e75002bfebfda
# патч 42 mutation-042.diff sha256 0e484c451290ab529001f9adbad4c0eee561c878274a32a35973e6bf3bb5c5b5
# патч 43 mutation-043.diff sha256 3cd99e40a521dc5420d9310658f4c25caf36998c94556f24752be71e98cd88b4
# патч 44 mutation-044.diff sha256 c9c9affa634660d267217800a5e2f0a8e9640e21308c7329f7fac63da4715916
# патч 45 mutation-045.diff sha256 4839d5f32a38e3c6439c2b2a2ccdf5e727eca30e182224c6e1f247818c92bef0
# патч 46 mutation-046.diff sha256 c1e3e5a528af3b3b9a656db978a36824ec9999372638c6736bcbfbd83e69e0a3
# патч 47 mutation-047.diff sha256 da3d1daf83a1c223ec9ec755798e986b82322a5b39be9f13d1958e594659b05a
# патч 48 mutation-048.diff sha256 dcb70bb90b70c0e763d5e270b2afdf464387a6f531976bf92d2c508b345094a8
# патч 49 mutation-049.diff sha256 4154be3964ce66674b838b860c9d4be37e39b2686eb2e2f10000e5cf5dc643d1
номер	исход	узлы
41	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac9ReviewNotRunTest::test_ac9_no_record_for_current_head_says_not_run
42	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac9ReviewNotRunTest::test_ac9_no_record_for_current_head_says_not_run,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac10NoPythonSectionTest::test_ac10_component_without_python_has_section_except_canary
43	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac9ReviewNotRunTest::test_ac9_no_record_for_current_head_says_not_run,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac8ReviewLinesTest::test_ac8_review_section_carries_outcome_gate_lines_for_head,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac10NoPythonSectionTest::test_ac10_component_without_python_has_section_except_canary
44	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac10NoPythonSectionTest::test_ac10_component_without_python_has_section_except_canary
45	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac12TwoSidedRetryTest::test_ac12_passed_with_retry_is_side_failure_retry,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac11TwoSidedErrorNameTest::test_ac11_only_check_failure_is_failure_on_check
46	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac12TwoSidedRetryTest::test_ac12_passed_with_retry_is_side_failure_retry,tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac11TwoSidedErrorNameTest::test_ac11_only_check_failure_is_failure_on_check
47	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac12TwoSidedRetryTest::test_ac12_passed_with_retry_is_side_failure_retry
48	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac13RetriedBaseRerunTest::test_ac13_retried_on_base_rerun_is_red_base
49	убита	tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac14OutOfBoundsTest::test_ac14_test_profile_and_multi_component_keep_prior_results
```

```text
# mutation-run №6 задачи 01M5R0DPNHZ7N8YBXMH375SMEE
# источник патчей: каталог на диске
# ревизия прогона: base 72d52fd367828949767e234ecbe9b0cc79851084
# тесты: tests/test_outcome_integrity_added_lines.py
# рабочих процессов: auto
# патч 50 mutation-050.diff sha256 b4f6188bb56c5c53b5c28ecf9e9dd5c84aa7488ac881f8fcfa5cae7b1534f142
# патч 51 mutation-051.diff sha256 3bd2dde791b39d0854b299421737f33caa83cd8ea9b0f4805f514b09c20eea56
# патч 52 mutation-052.diff sha256 3f3a001819fa348892a9c53aa82303d65025cb26fb5a31e18481cf5b02f7fdcf
# патч 53 mutation-053.diff sha256 14aead6465413b84598e4fa0078591fd7545a289b65bb0637e2afdb5088c2951
# патч 54 mutation-054.diff sha256 d64e0505413fec96187ac64468d113a6ae61f6cc829fdf3cb67ded54f88c9a8a
# патч 55 mutation-055.diff sha256 d2f1267eadea0bc5ce1edb468910194471b40a1bc0c2a4b778ce76b241983671
номер	исход	узлы
50	убита	tests/test_outcome_integrity_added_lines.py::AddedLinesTest::test_quoted_path_latin1_text_and_no_final_newline
51	убита	tests/test_outcome_integrity_added_lines.py::AddedLinesTest::test_unexpected_header_is_prepare_refusal,tests/test_outcome_integrity_added_lines.py::AddedLinesTest::test_noprefix_config_does_not_hide_added_lines
52	убита	tests/test_outcome_integrity_added_lines.py::AddedLinesTest::test_unexpected_header_is_prepare_refusal
53	убита	tests/test_outcome_integrity_added_lines.py::AddedLinesTest::test_deleted_file_header_dev_null_is_not_refusal
54	убита	tests/test_outcome_integrity_added_lines.py::CodeExceptionRenameTest::test_rename_from_test_path_to_code_path_is_checked
55	убита	tests/test_outcome_integrity_added_lines.py::CodeExceptionRenameTest::test_rename_between_test_paths_is_not_checked
```

## Мутации после

Перед прогоном №7: `git status --porcelain -- orchestrator/` — вывод пуст.

```text
# mutation-run №7 задачи 01M5R0DPNHZ7N8YBXMH375SMEE
# источник патчей: каталог на диске
# ревизия прогона: worktree 98398b908b51c83a667dff18ba2bea4babab4416
# тесты: tests/test_merge_outcome_module.py
# рабочих процессов: auto
# патч 1 mutation-001.diff sha256 e15e3e312c82c7f68c88d7ae0be49865fe59776addd9e0f857e900b8935cadae
# патч 2 mutation-002.diff sha256 9a6c4d2dd3f80d13809d9f2600aca7083ee905730ef459918ae43f3a124a5d59
# патч 3 mutation-003.diff sha256 d648d0515889a04fb06feba9aac3f418bfe9524e6b8cecf5d8963a5393049ded
# патч 4 mutation-004.diff sha256 ae1a106756db6a4d06f94ccdcde7e6fdfcb6a8fb460e56a3a89c04e8ae1ea7d2
# патч 5 mutation-005.diff sha256 0bf230c1aa301d02cc0591e153a4a2084bd7d9957d235f3d0fb4b8b7da1bcab0
# патч 6 mutation-006.diff sha256 d8a1f7e259f3edf6c5a825790f0db17e3341aaf2d9f584dfcf023cb954957198
# патч 7 mutation-007.diff sha256 c8bfcb669b1fcf7f2e1fc03340c6509cc9496e6957d04b79a26f3fbd1a27251a
# патч 8 mutation-008.diff sha256 af1f01ba4d92f145f496c90ba41688384b2c03bf630bbdf3ff3073f9d28da460
# патч 9 mutation-009.diff sha256 b17128a55697c6006b0d3cafec4388cf59b614211a45438e8ff88addc88ea5ee
# патч 10 mutation-010.diff sha256 911b1c3f08d2d708714db000d3c48712b522ecff7259ffcc9338f59f07ea6d62
номер	исход	узлы
1	убита	tests/test_merge_outcome_module.py::test_ac7_canary_from_db_and_in_dev_base_is_diff_base,tests/test_merge_outcome_module.py::test_ac4_same_quadruple_proves_without_run,tests/test_merge_outcome_module.py::test_ac6_record_without_proof_line_runs_gate,tests/test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate,tests/test_merge_outcome_module.py::test_ac5_other_base_key_or_mandate_runs_gate,tests/test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks,tests/test_merge_outcome_module.py::test_ac8_review_section_carries_outcome_gate_lines_for_head
2	убита	tests/test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate
3	убита	tests/test_merge_outcome_module.py::test_ac4_same_quadruple_proves_without_run,tests/test_merge_outcome_module.py::test_ac7_canary_from_db_and_in_dev_base_is_diff_base,tests/test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks,tests/test_merge_outcome_module.py::test_ac8_review_section_carries_outcome_gate_lines_for_head,tests/test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate
4	убита	tests/test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate
5	убита	tests/test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate,tests/test_merge_outcome_module.py::test_ac3_prepare_failures_keep_merge_gate_without_push,tests/test_merge_outcome_module.py::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record
6	убита	tests/test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate
7	убита	tests/test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate
8	убита	tests/test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate
9	убита	tests/test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks,tests/test_merge_outcome_module.py::test_ac7_canary_from_db_and_in_dev_base_is_diff_base,tests/test_merge_outcome_module.py::test_ac6_record_without_proof_line_runs_gate,tests/test_merge_outcome_module.py::test_ac4_same_quadruple_proves_without_run,tests/test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate
10	убита	tests/test_merge_outcome_module.py::test_ac3_prepare_failures_keep_merge_gate_without_push,tests/test_merge_outcome_module.py::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record
```

Перед прогоном №8: `git status --porcelain -- orchestrator/` — вывод пуст.

```text
# mutation-run №8 задачи 01M5R0DPNHZ7N8YBXMH375SMEE
# источник патчей: каталог на диске
# ревизия прогона: worktree 98398b908b51c83a667dff18ba2bea4babab4416
# тесты: tests/test_merge_outcome_module.py
# рабочих процессов: auto
# патч 11 mutation-011.diff sha256 f0844eaa333ae6dcdfbda7b023f1009c3c25682bc6fb01c769160f1b28e135c8
# патч 12 mutation-012.diff sha256 7df050f0f5036fe4057280df666c22c3017bf4c179369b4e0a131d4c24238025
# патч 13 mutation-013.diff sha256 68c4795c7d9bf79b5db3753ee8fb6c09f4692c228841897462d2a9c4c33da28a
# патч 14 mutation-014.diff sha256 c7767ffd6cf90acce75d62404ed17daf5c19943f7912c0ddcba301eeace739af
# патч 15 mutation-015.diff sha256 f2c8b942bf1fdd1f77f333f57fbc7b640323d2ec76b228fd6aa2f770944ca481
# патч 16 mutation-016.diff sha256 c02267aa1aec88f9a386b33f700354a6d8f5d2ceca50e9f436832cb736429e6f
# патч 17 mutation-017.diff sha256 8080181d0e748b3645368a2267dc19fdac6d3524ed18ebd9fa5410710f399800
# патч 18 mutation-018.diff sha256 0c03108a3dec016ed0c7df84f0e87ae87d86266f71d42f70a1e14f54e83a75d4
# патч 19 mutation-019.diff sha256 e38090114613554d5ff1309f2ef0f1e1f91b075094f2c43c2e231774279a185b
# патч 20 mutation-020.diff sha256 8bccd7f2304d3c6b0fb49c5bc0df0823b406456b03e9c560ffb2adbb70edebdd
номер	исход	узлы
11	убита	tests/test_merge_outcome_module.py::test_ac3_prepare_failures_keep_merge_gate_without_push,tests/test_merge_outcome_module.py::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record
12	убита	tests/test_merge_outcome_module.py::test_ac7_base_is_merge_base_with_fetched_main_not_diff_base,tests/test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks,tests/test_merge_outcome_module.py::test_ac3_prepare_failures_keep_merge_gate_without_push,tests/test_merge_outcome_module.py::test_ac2_finding_without_mandate_escalates_merge,tests/test_merge_outcome_module.py::test_ac5_other_base_key_or_mandate_runs_gate,tests/test_merge_outcome_module.py::test_ac7_doc_only_lag_runs_gate_with_merge_base,tests/test_merge_outcome_module.py::test_ac4_same_quadruple_proves_without_run,tests/test_merge_outcome_module.py::test_ac6_record_without_proof_line_runs_gate
13	убита	tests/test_merge_outcome_module.py::test_ac2_finding_without_mandate_escalates_merge
14	убита	tests/test_merge_outcome_module.py::test_ac2_finding_without_mandate_escalates_merge
15	убита	tests/test_merge_outcome_module.py::test_ac2_finding_without_mandate_escalates_merge
16	убита	tests/test_merge_outcome_module.py::test_ac2_merge_refusal_action_is_operator_class_key
17	убита	tests/test_merge_outcome_module.py::test_ac2_merge_refusal_action_is_operator_class_key
18	убита	tests/test_merge_outcome_module.py::test_ac3_prepare_failures_keep_merge_gate_without_push
19	убита	tests/test_merge_outcome_module.py::test_ac3_prepare_failures_keep_merge_gate_without_push,tests/test_merge_outcome_module.py::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record
20	убита	tests/test_merge_outcome_module.py::test_ac3_prepare_failures_keep_merge_gate_without_push
```

Перед прогоном №9: `git status --porcelain -- orchestrator/` — вывод пуст.

```text
# mutation-run №9 задачи 01M5R0DPNHZ7N8YBXMH375SMEE
# источник патчей: каталог на диске
# ревизия прогона: worktree 98398b908b51c83a667dff18ba2bea4babab4416
# тесты: tests/test_merge_outcome_module.py
# рабочих процессов: auto
# патч 21 mutation-021.diff sha256 7880f06f8fe97ac72adf35a34145741ed664ba577998036dc817b5252cb3b930
# патч 22 mutation-022.diff sha256 a04460424dc3e72bd63d536f1694587d686c35ac974e0f5ff532ce5604e1e0d7
# патч 23 mutation-023.diff sha256 40c384680bac5d1f130870d0f9229d66f790cd2723bdddccbbb3b06672af192b
# патч 24 mutation-024.diff sha256 a7401a896d9df6b9d234332f7cea98ab9f4a6e7d7ebdd243b12b432c0bee50c0
# патч 25 mutation-025.diff sha256 626db19b5e094df829cd02c08d0dbb42c2f92ac82afdd349a20fe9f686f8e57b
# патч 26 mutation-026.diff sha256 804fd02518fa634d33bd35291cfd1543fa8e7090668fba969efe159309727481
# патч 27 mutation-027.diff sha256 e95d52fef406fb249c204c12b9d5e6c6b0e768068aabdd6c93b2aa7912848a44
# патч 28 mutation-028.diff sha256 d89171aa69548abd829d201749b1c64b470f98b875742a2eb060a9dfd5487909
# патч 29 mutation-029.diff sha256 fb5be695a2a2fd558e1f49fb13ae1e292cf51f116c0739c52cadded2942949ad
# патч 30 mutation-030.diff sha256 23edc0593e98baf2ba0843b6cec6520173991761705976f013807485dabc5fb4
номер	исход	узлы
21	убита	tests/test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks,tests/test_merge_outcome_module.py::test_ac4_same_quadruple_proves_without_run
22	убита	tests/test_merge_outcome_module.py::test_ac4_same_quadruple_proves_without_run
23	убита	tests/test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks,tests/test_merge_outcome_module.py::test_ac4_same_quadruple_proves_without_run
24	убита	tests/test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks,tests/test_merge_outcome_module.py::test_ac4_same_quadruple_proves_without_run
25	убита	tests/test_merge_outcome_module.py::test_ac5_other_base_key_or_mandate_runs_gate
26	убита	tests/test_merge_outcome_module.py::test_ac5_other_base_key_or_mandate_runs_gate
27	убита	tests/test_merge_outcome_module.py::test_ac5_other_base_key_or_mandate_runs_gate
28	убита	tests/test_merge_outcome_module.py::test_ac6_record_without_proof_line_runs_gate
29	убита	tests/test_merge_outcome_module.py::test_ac7_base_is_merge_base_with_fetched_main_not_diff_base
30	убита	tests/test_merge_outcome_module.py::test_ac7_doc_only_lag_runs_gate_with_merge_base
```

Перед прогоном №10: `git status --porcelain -- orchestrator/` — вывод пуст.

```text
# mutation-run №10 задачи 01M5R0DPNHZ7N8YBXMH375SMEE
# источник патчей: каталог на диске
# ревизия прогона: worktree 98398b908b51c83a667dff18ba2bea4babab4416
# тесты: tests/test_merge_outcome_module.py
# рабочих процессов: auto
# патч 31 mutation-031.diff sha256 6adbfb6fd6caed34c4624ce4bf4311203a769866ccbc722b6f2187748a90ef61
# патч 32 mutation-032.diff sha256 299378cb62a52aa816dea4f42dd9ea33a28e95d1a89ef86f7c57b54a3c5691fe
# патч 33 mutation-033.diff sha256 4eb64fec5193c3299b301f5418d01993994312dd411005d8463f6adaf58b0322
# патч 34 mutation-034.diff sha256 5d7ae52332efa15d97d59840f729a9d653b61a568a3ada347955e5373f20537c
# патч 35 mutation-035.diff sha256 7e7a0c6b25560f00b24b7c96280a88706fd0b66e73d8054b964a902a49821295
# патч 36 mutation-036.diff sha256 3f7a7b3e5e05afad183651a9e75df7e2effba03c1068648fac81d7d24a92f5b1
# патч 37 mutation-037.diff sha256 c9e7e3edfa5cf4fba679f038c276f53b43e0da54df84285ef9cd3034c060251c
# патч 38 mutation-038.diff sha256 ba4f68f5342bb2b145611eae1213afd08aceea5a5d0a21da0b5aee6d5ab86da6
# патч 39 mutation-039.diff sha256 8bf41e531ef69c8d55d9925d89c59ae7cc97b62e344d8f70eeadcb2ce413e82c
# патч 40 mutation-040.diff sha256 2a7c97e8047f2e1a81f8d75279c1d37873fb4829ff95c7bf1b8359fda544352a
номер	исход	узлы
31	убита	tests/test_merge_outcome_module.py::test_ac7_doc_only_lag_runs_gate_with_merge_base
32	убита	tests/test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks
33	убита	tests/test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks
34	убита	tests/test_merge_outcome_module.py::test_ac7_canary_from_db_and_in_dev_base_is_diff_base
35	убита	tests/test_merge_outcome_module.py::test_ac8_review_section_carries_outcome_gate_lines_for_head,tests/test_merge_outcome_module.py::test_ac4_same_quadruple_proves_without_run,tests/test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate,tests/test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks,tests/test_merge_outcome_module.py::test_ac7_canary_from_db_and_in_dev_base_is_diff_base,tests/test_merge_outcome_module.py::test_ac13_retried_on_base_rerun_is_red_base
36	не убита	
37	убита	tests/test_merge_outcome_module.py::test_ac8_review_section_carries_outcome_gate_lines_for_head,tests/test_merge_outcome_module.py::test_ac9_no_record_for_current_head_says_not_run,tests/test_merge_outcome_module.py::test_ac10_component_without_python_has_section_except_canary
38	убита	tests/test_merge_outcome_module.py::test_ac8_review_section_carries_outcome_gate_lines_for_head
39	убита	tests/test_merge_outcome_module.py::test_ac8_review_section_carries_outcome_gate_lines_for_head
40	убита	tests/test_merge_outcome_module.py::test_ac9_no_record_for_current_head_says_not_run
```

Перед прогоном №11: `git status --porcelain -- orchestrator/` — вывод пуст.

```text
# mutation-run №11 задачи 01M5R0DPNHZ7N8YBXMH375SMEE
# источник патчей: каталог на диске
# ревизия прогона: worktree b06b18d2c79ba467a0961a22ea3187804023424e
# тесты: tests/test_merge_outcome_module.py
# рабочих процессов: auto
# патч 41 mutation-041.diff sha256 fe0646b7d1f1ddc8e900913bbb30bac6aae561406e3b0b30fb3e75002bfebfda
# патч 42 mutation-042.diff sha256 0e484c451290ab529001f9adbad4c0eee561c878274a32a35973e6bf3bb5c5b5
# патч 43 mutation-043.diff sha256 3cd99e40a521dc5420d9310658f4c25caf36998c94556f24752be71e98cd88b4
# патч 44 mutation-044.diff sha256 c9c9affa634660d267217800a5e2f0a8e9640e21308c7329f7fac63da4715916
# патч 45 mutation-045.diff sha256 4839d5f32a38e3c6439c2b2a2ccdf5e727eca30e182224c6e1f247818c92bef0
# патч 46 mutation-046.diff sha256 c1e3e5a528af3b3b9a656db978a36824ec9999372638c6736bcbfbd83e69e0a3
# патч 47 mutation-047.diff sha256 da3d1daf83a1c223ec9ec755798e986b82322a5b39be9f13d1958e594659b05a
# патч 48 mutation-048.diff sha256 dcb70bb90b70c0e763d5e270b2afdf464387a6f531976bf92d2c508b345094a8
# патч 49 mutation-049.diff sha256 4154be3964ce66674b838b860c9d4be37e39b2686eb2e2f10000e5cf5dc643d1
номер	исход	узлы
41	убита	tests/test_merge_outcome_module.py::test_ac9_no_record_for_current_head_says_not_run
42	убита	tests/test_merge_outcome_module.py::test_ac9_no_record_for_current_head_says_not_run,tests/test_merge_outcome_module.py::test_ac10_component_without_python_has_section_except_canary
43	убита	tests/test_merge_outcome_module.py::test_ac8_review_section_carries_outcome_gate_lines_for_head,tests/test_merge_outcome_module.py::test_ac9_no_record_for_current_head_says_not_run,tests/test_merge_outcome_module.py::test_ac10_component_without_python_has_section_except_canary
44	убита	tests/test_merge_outcome_module.py::test_ac10_component_without_python_has_section_except_canary
45	убита	tests/test_merge_outcome_module.py::test_ac11_only_check_failure_is_failure_on_check,tests/test_merge_outcome_module.py::test_ac12_passed_with_retry_is_side_failure_retry
46	убита	tests/test_merge_outcome_module.py::test_ac11_only_check_failure_is_failure_on_check,tests/test_merge_outcome_module.py::test_ac12_passed_with_retry_is_side_failure_retry
47	убита	tests/test_merge_outcome_module.py::test_ac12_passed_with_retry_is_side_failure_retry
48	убита	tests/test_merge_outcome_module.py::test_ac13_retried_on_base_rerun_is_red_base
49	убита	tests/test_merge_outcome_module.py::test_ac14_test_profile_and_multi_component_keep_prior_results
```

Перед прогоном №12: `git status --porcelain -- orchestrator/` — вывод пуст.

```text
# mutation-run №12 задачи 01M5R0DPNHZ7N8YBXMH375SMEE
# источник патчей: каталог на диске
# ревизия прогона: worktree b06b18d2c79ba467a0961a22ea3187804023424e
# тесты: tests/test_outcome_gate_module.py
# рабочих процессов: auto
# патч 50 mutation-050.diff sha256 b4f6188bb56c5c53b5c28ecf9e9dd5c84aa7488ac881f8fcfa5cae7b1534f142
# патч 51 mutation-051.diff sha256 3bd2dde791b39d0854b299421737f33caa83cd8ea9b0f4805f514b09c20eea56
# патч 52 mutation-052.diff sha256 3f3a001819fa348892a9c53aa82303d65025cb26fb5a31e18481cf5b02f7fdcf
# патч 53 mutation-053.diff sha256 14aead6465413b84598e4fa0078591fd7545a289b65bb0637e2afdb5088c2951
# патч 54 mutation-054.diff sha256 d64e0505413fec96187ac64468d113a6ae61f6cc829fdf3cb67ded54f88c9a8a
# патч 55 mutation-055.diff sha256 d2f1267eadea0bc5ce1edb468910194471b40a1bc0c2a4b778ce76b241983671
номер	исход	узлы
50	убита	tests/test_outcome_gate_module.py::test_quoted_path_latin1_text_and_no_final_newline
51	убита	tests/test_outcome_gate_module.py::test_unexpected_header_is_prepare_refusal,tests/test_outcome_gate_module.py::test_noprefix_config_does_not_hide_added_lines
52	убита	tests/test_outcome_gate_module.py::test_unexpected_header_is_prepare_refusal
53	убита	tests/test_outcome_gate_module.py::test_deleted_file_header_dev_null_is_not_refusal
54	убита	tests/test_outcome_gate_module.py::test_rename_from_test_path_to_code_path_is_checked
55	убита	tests/test_outcome_gate_module.py::test_rename_between_test_paths_is_not_checked
```

## Строки падений «до → после»

Строка падения — нижний кадр `tests/…` секции FAILURES лога прогона патча (`<id>-mutation-run-<n>-p<nnn>.log`): «до» — прогоны №1–№6, «после» — №7–№12; соответствие «файл:строка до → файл:строка после» — перенесённое утверждение той же функции. Пометка «подготовка» — падение в методе подготовки `rewrite_passed` песочницы: доказательством не засчитано, мутацию доказывают другие строки той же мутации.

Мутация 048 падает в помощнике исхода `no_gate_refusal` (вызов `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:1078` → `tests/test_merge_outcome_module.py:754`) — утверждение исхода, не подготовки.

Мутации 051 и 052 «после» падают на `pytest.raises(outcome_integrity._Prepare)` («DID NOT RAISE», вид `Failed`) — перенос `assertRaises` той же строки.

- mutation-001: «до» `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:407` → «после» `test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_merge_outcome_module.py:124`
- mutation-001: «до» `Ac6LegacyRecordTest::test_ac6_record_without_proof_line_runs_gate` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:320` (подготовка `rewrite_passed` — не доказательство) → «после» `test_merge_outcome_module.py::test_ac6_record_without_proof_line_runs_gate` — `tests/merge_outcome_sandbox.py:280` (подготовка `rewrite_passed` — не доказательство)
- mutation-001: «до» `Ac5ProofMismatchTest::test_ac5_other_base_key_or_mandate_runs_gate` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:320` (подготовка `rewrite_passed` — не доказательство) → «после» `test_merge_outcome_module.py::test_ac5_other_base_key_or_mandate_runs_gate` — `tests/merge_outcome_sandbox.py:280` (подготовка `rewrite_passed` — не доказательство)
- mutation-001: «до» `Ac8ReviewLinesTest::test_ac8_review_section_carries_outcome_gate_lines_for_head` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:884` → «после» `test_merge_outcome_module.py::test_ac8_review_section_carries_outcome_gate_lines_for_head` — `tests/test_merge_outcome_module.py:591`
- mutation-001: «до» `Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:788` → «после» `test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_merge_outcome_module.py:496`
- mutation-001: «до» `Ac7MergeBaseTest::test_ac7_canary_from_db_and_in_dev_base_is_diff_base` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:834` → «после» `test_merge_outcome_module.py::test_ac7_canary_from_db_and_in_dev_base_is_diff_base` — `tests/test_merge_outcome_module.py:542`
- mutation-001: «до» `Ac4ProofTest::test_ac4_same_quadruple_proves_without_run` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:601` → «после» `test_merge_outcome_module.py::test_ac4_same_quadruple_proves_without_run` — `tests/test_merge_outcome_module.py:312`
- mutation-002: «до» `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:411` → «после» `test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_merge_outcome_module.py:128`
- mutation-003: «до» `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:413` → «после» `test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_merge_outcome_module.py:130`
- mutation-003: «до» `Ac8ReviewLinesTest::test_ac8_review_section_carries_outcome_gate_lines_for_head` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:884` → «после» `test_merge_outcome_module.py::test_ac8_review_section_carries_outcome_gate_lines_for_head` — `tests/test_merge_outcome_module.py:591`
- mutation-003: «до» `Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:788` → «после» `test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_merge_outcome_module.py:496`
- mutation-003: «до» `Ac7MergeBaseTest::test_ac7_canary_from_db_and_in_dev_base_is_diff_base` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:835` → «после» `test_merge_outcome_module.py::test_ac7_canary_from_db_and_in_dev_base_is_diff_base` — `tests/test_merge_outcome_module.py:543`
- mutation-003: «до» `Ac4ProofTest::test_ac4_same_quadruple_proves_without_run` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:601` → «после» `test_merge_outcome_module.py::test_ac4_same_quadruple_proves_without_run` — `tests/test_merge_outcome_module.py:312`
- mutation-004: «до» `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:416` → «после» `test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_merge_outcome_module.py:133`
- mutation-005: «до» `Ac1ProofLineTest::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:444` → «после» `test_merge_outcome_module.py::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record` — `tests/test_merge_outcome_module.py:162`
- mutation-005: «до» `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:416` → «после» `test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_merge_outcome_module.py:133`
- mutation-005: «до» `Ac3MergePrepareTest::test_ac3_prepare_failures_keep_merge_gate_without_push` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:555` → «после» `test_merge_outcome_module.py::test_ac3_prepare_failures_keep_merge_gate_without_push` — `tests/test_merge_outcome_module.py:268`
- mutation-006: «до» `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:422` → «после» `test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_merge_outcome_module.py:139`
- mutation-007: «до» `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:422` → «после» `test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_merge_outcome_module.py:139`
- mutation-008: «до» `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:422` → «после» `test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_merge_outcome_module.py:139`
- mutation-009: «до» `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:407` → «после» `test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_merge_outcome_module.py:124`
- mutation-009: «до» `Ac6LegacyRecordTest::test_ac6_record_without_proof_line_runs_gate` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:320` (подготовка `rewrite_passed` — не доказательство) → «после» `test_merge_outcome_module.py::test_ac6_record_without_proof_line_runs_gate` — `tests/merge_outcome_sandbox.py:280` (подготовка `rewrite_passed` — не доказательство)
- mutation-009: «до» `Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:788` → «после» `test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_merge_outcome_module.py:496`
- mutation-009: «до» `Ac7MergeBaseTest::test_ac7_canary_from_db_and_in_dev_base_is_diff_base` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:834` → «после» `test_merge_outcome_module.py::test_ac7_canary_from_db_and_in_dev_base_is_diff_base` — `tests/test_merge_outcome_module.py:542`
- mutation-009: «до» `Ac4ProofTest::test_ac4_same_quadruple_proves_without_run` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:601` → «после» `test_merge_outcome_module.py::test_ac4_same_quadruple_proves_without_run` — `tests/test_merge_outcome_module.py:312`
- mutation-010: «до» `Ac1ProofLineTest::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:444` → «после» `test_merge_outcome_module.py::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record` — `tests/test_merge_outcome_module.py:162`
- mutation-010: «до» `Ac3MergePrepareTest::test_ac3_prepare_failures_keep_merge_gate_without_push` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:555` → «после» `test_merge_outcome_module.py::test_ac3_prepare_failures_keep_merge_gate_without_push` — `tests/test_merge_outcome_module.py:268`
- mutation-011: «до» `Ac1ProofLineTest::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:444` → «после» `test_merge_outcome_module.py::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record` — `tests/test_merge_outcome_module.py:162`
- mutation-011: «до» `Ac3MergePrepareTest::test_ac3_prepare_failures_keep_merge_gate_without_push` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:555` → «после» `test_merge_outcome_module.py::test_ac3_prepare_failures_keep_merge_gate_without_push` — `tests/test_merge_outcome_module.py:268`
- mutation-012: «до» `Ac2MergeFindingTest::test_ac2_finding_without_mandate_escalates_merge` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:479` → «после» `test_merge_outcome_module.py::test_ac2_finding_without_mandate_escalates_merge` — `tests/test_merge_outcome_module.py:196`
- mutation-012: «до» `Ac3MergePrepareTest::test_ac3_prepare_failures_keep_merge_gate_without_push` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:555` → «после» `test_merge_outcome_module.py::test_ac3_prepare_failures_keep_merge_gate_without_push` — `tests/test_merge_outcome_module.py:268`
- mutation-012: «до» `Ac7MergeBaseTest::test_ac7_doc_only_lag_runs_gate_with_merge_base` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:751` → «после» `test_merge_outcome_module.py::test_ac7_doc_only_lag_runs_gate_with_merge_base` — `tests/test_merge_outcome_module.py:458`
- mutation-012: «до» `Ac7MergeBaseTest::test_ac7_base_is_merge_base_with_fetched_main_not_diff_base` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:724` → «после» `test_merge_outcome_module.py::test_ac7_base_is_merge_base_with_fetched_main_not_diff_base` — `tests/test_merge_outcome_module.py:431`
- mutation-012: «до» `Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:788` → «после» `test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_merge_outcome_module.py:496`
- mutation-012: «до» `Ac6LegacyRecordTest::test_ac6_record_without_proof_line_runs_gate` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:683` → «после» `test_merge_outcome_module.py::test_ac6_record_without_proof_line_runs_gate` — `tests/test_merge_outcome_module.py:391`
- mutation-012: «до» `Ac4ProofTest::test_ac4_same_quadruple_proves_without_run` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:604` → «после» `test_merge_outcome_module.py::test_ac4_same_quadruple_proves_without_run` — `tests/test_merge_outcome_module.py:315`
- mutation-012: «до» `Ac5ProofMismatchTest::test_ac5_other_base_key_or_mandate_runs_gate` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:656` → «после» `test_merge_outcome_module.py::test_ac5_other_base_key_or_mandate_runs_gate` — `tests/test_merge_outcome_module.py:366`
- mutation-013: «до» `Ac2MergeFindingTest::test_ac2_finding_without_mandate_escalates_merge` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:480` → «после» `test_merge_outcome_module.py::test_ac2_finding_without_mandate_escalates_merge` — `tests/test_merge_outcome_module.py:197`
- mutation-014: «до» `Ac2MergeFindingTest::test_ac2_finding_without_mandate_escalates_merge` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:479` → «после» `test_merge_outcome_module.py::test_ac2_finding_without_mandate_escalates_merge` — `tests/test_merge_outcome_module.py:196`
- mutation-015: «до» `Ac2MergeFindingTest::test_ac2_finding_without_mandate_escalates_merge` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:479` → «после» `test_merge_outcome_module.py::test_ac2_finding_without_mandate_escalates_merge` — `tests/test_merge_outcome_module.py:196`
- mutation-016: «до» `Ac2MergeFindingTest::test_ac2_merge_refusal_action_is_operator_class_key` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:493` → «после» `test_merge_outcome_module.py::test_ac2_merge_refusal_action_is_operator_class_key` — `tests/test_merge_outcome_module.py:209`
- mutation-017: «до» `Ac2MergeFindingTest::test_ac2_merge_refusal_action_is_operator_class_key` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:494` → «после» `test_merge_outcome_module.py::test_ac2_merge_refusal_action_is_operator_class_key` — `tests/test_merge_outcome_module.py:210`
- mutation-018: «до» `Ac3MergePrepareTest::test_ac3_prepare_failures_keep_merge_gate_without_push` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:555` → «после» `test_merge_outcome_module.py::test_ac3_prepare_failures_keep_merge_gate_without_push` — `tests/test_merge_outcome_module.py:268`
- mutation-019: «до» `Ac3MergePrepareTest::test_ac3_prepare_failures_keep_merge_gate_without_push` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:555` → «после» `test_merge_outcome_module.py::test_ac3_prepare_failures_keep_merge_gate_without_push` — `tests/test_merge_outcome_module.py:268`
- mutation-019: «до» `Ac1ProofLineTest::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:444` → «после» `test_merge_outcome_module.py::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record` — `tests/test_merge_outcome_module.py:162`
- mutation-020: «до» `Ac3MergePrepareTest::test_ac3_prepare_failures_keep_merge_gate_without_push` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:555` → «после» `test_merge_outcome_module.py::test_ac3_prepare_failures_keep_merge_gate_without_push` — `tests/test_merge_outcome_module.py:268`
- mutation-021: «до» `Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:788` → «после» `test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_merge_outcome_module.py:496`
- mutation-021: «до» `Ac4ProofTest::test_ac4_same_quadruple_proves_without_run` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:601` → «после» `test_merge_outcome_module.py::test_ac4_same_quadruple_proves_without_run` — `tests/test_merge_outcome_module.py:312`
- mutation-022: «до» `Ac4ProofTest::test_ac4_same_quadruple_proves_without_run` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:601` → «после» `test_merge_outcome_module.py::test_ac4_same_quadruple_proves_without_run` — `tests/test_merge_outcome_module.py:312`
- mutation-023: «до» `Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:788` → «после» `test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_merge_outcome_module.py:496`
- mutation-023: «до» `Ac4ProofTest::test_ac4_same_quadruple_proves_without_run` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:604` → «после» `test_merge_outcome_module.py::test_ac4_same_quadruple_proves_without_run` — `tests/test_merge_outcome_module.py:315`
- mutation-024: «до» `Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:788` → «после» `test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_merge_outcome_module.py:496`
- mutation-024: «до» `Ac4ProofTest::test_ac4_same_quadruple_proves_without_run` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:604` → «после» `test_merge_outcome_module.py::test_ac4_same_quadruple_proves_without_run` — `tests/test_merge_outcome_module.py:315`
- mutation-025: «до» `Ac5ProofMismatchTest::test_ac5_other_base_key_or_mandate_runs_gate` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:656` → «после» `test_merge_outcome_module.py::test_ac5_other_base_key_or_mandate_runs_gate` — `tests/test_merge_outcome_module.py:366`
- mutation-026: «до» `Ac5ProofMismatchTest::test_ac5_other_base_key_or_mandate_runs_gate` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:656` → «после» `test_merge_outcome_module.py::test_ac5_other_base_key_or_mandate_runs_gate` — `tests/test_merge_outcome_module.py:366`
- mutation-027: «до» `Ac5ProofMismatchTest::test_ac5_other_base_key_or_mandate_runs_gate` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:656` → «после» `test_merge_outcome_module.py::test_ac5_other_base_key_or_mandate_runs_gate` — `tests/test_merge_outcome_module.py:366`
- mutation-028: «до» `Ac6LegacyRecordTest::test_ac6_record_without_proof_line_runs_gate` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:683` → «после» `test_merge_outcome_module.py::test_ac6_record_without_proof_line_runs_gate` — `tests/test_merge_outcome_module.py:391`
- mutation-029: «до» `Ac7MergeBaseTest::test_ac7_base_is_merge_base_with_fetched_main_not_diff_base` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:725` → «после» `test_merge_outcome_module.py::test_ac7_base_is_merge_base_with_fetched_main_not_diff_base` — `tests/test_merge_outcome_module.py:432`
- mutation-030: «до» `Ac7MergeBaseTest::test_ac7_doc_only_lag_runs_gate_with_merge_base` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:753` → «после» `test_merge_outcome_module.py::test_ac7_doc_only_lag_runs_gate_with_merge_base` — `tests/test_merge_outcome_module.py:460`
- mutation-031: «до» `Ac7MergeBaseTest::test_ac7_doc_only_lag_runs_gate_with_merge_base` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:751` → «после» `test_merge_outcome_module.py::test_ac7_doc_only_lag_runs_gate_with_merge_base` — `tests/test_merge_outcome_module.py:458`
- mutation-032: «до» `Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:788` → «после» `test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_merge_outcome_module.py:496`
- mutation-033: «до» `Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:802` → «после» `test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_merge_outcome_module.py:509`
- mutation-034: «до» `Ac7MergeBaseTest::test_ac7_canary_from_db_and_in_dev_base_is_diff_base` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:827` → «после» `test_merge_outcome_module.py::test_ac7_canary_from_db_and_in_dev_base_is_diff_base` — `tests/test_merge_outcome_module.py:535`
- mutation-035: «до» `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:414` → «после» `test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate` — `tests/test_merge_outcome_module.py:131`
- mutation-035: «до» `Ac13RetriedBaseRerunTest::test_ac13_retried_on_base_rerun_is_red_base` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:1080` → «после» `test_merge_outcome_module.py::test_ac13_retried_on_base_rerun_is_red_base` — `tests/test_merge_outcome_module.py:756`
- mutation-035: «до» `Ac8ReviewLinesTest::test_ac8_review_section_carries_outcome_gate_lines_for_head` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:878` → «после» `test_merge_outcome_module.py::test_ac8_review_section_carries_outcome_gate_lines_for_head` — `tests/test_merge_outcome_module.py:585`
- mutation-035: «до» `Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:788` → «после» `test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks` — `tests/test_merge_outcome_module.py:496`
- mutation-035: «до» `Ac7MergeBaseTest::test_ac7_canary_from_db_and_in_dev_base_is_diff_base` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:835` → «после» `test_merge_outcome_module.py::test_ac7_canary_from_db_and_in_dev_base_is_diff_base` — `tests/test_merge_outcome_module.py:543`
- mutation-035: «до» `Ac4ProofTest::test_ac4_same_quadruple_proves_without_run` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:601` → «после» `test_merge_outcome_module.py::test_ac4_same_quadruple_proves_without_run` — `tests/test_merge_outcome_module.py:312`
- mutation-037: «до» `Ac9ReviewNotRunTest::test_ac9_no_record_for_current_head_says_not_run` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:916` → «после» `test_merge_outcome_module.py::test_ac9_no_record_for_current_head_says_not_run` — `tests/test_merge_outcome_module.py:622`
- mutation-037: «до» `Ac10NoPythonSectionTest::test_ac10_component_without_python_has_section_except_canary` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:950` → «после» `test_merge_outcome_module.py::test_ac10_component_without_python_has_section_except_canary` — `tests/test_merge_outcome_module.py:655`
- mutation-037: «до» `Ac8ReviewLinesTest::test_ac8_review_section_carries_outcome_gate_lines_for_head` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:881` → «после» `test_merge_outcome_module.py::test_ac8_review_section_carries_outcome_gate_lines_for_head` — `tests/test_merge_outcome_module.py:588`
- mutation-038: «до» `Ac8ReviewLinesTest::test_ac8_review_section_carries_outcome_gate_lines_for_head` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:884` → «после» `test_merge_outcome_module.py::test_ac8_review_section_carries_outcome_gate_lines_for_head` — `tests/test_merge_outcome_module.py:591`
- mutation-039: «до» `Ac8ReviewLinesTest::test_ac8_review_section_carries_outcome_gate_lines_for_head` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:888` → «после» `test_merge_outcome_module.py::test_ac8_review_section_carries_outcome_gate_lines_for_head` — `tests/test_merge_outcome_module.py:595`
- mutation-040: «до» `Ac9ReviewNotRunTest::test_ac9_no_record_for_current_head_says_not_run` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:923` → «после» `test_merge_outcome_module.py::test_ac9_no_record_for_current_head_says_not_run` — `tests/test_merge_outcome_module.py:629`
- mutation-041: «до» `Ac9ReviewNotRunTest::test_ac9_no_record_for_current_head_says_not_run` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:916` → «после» `test_merge_outcome_module.py::test_ac9_no_record_for_current_head_says_not_run` — `tests/test_merge_outcome_module.py:622`
- mutation-042: «до» `Ac9ReviewNotRunTest::test_ac9_no_record_for_current_head_says_not_run` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:916` → «после» `test_merge_outcome_module.py::test_ac9_no_record_for_current_head_says_not_run` — `tests/test_merge_outcome_module.py:622`
- mutation-042: «до» `Ac10NoPythonSectionTest::test_ac10_component_without_python_has_section_except_canary` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:950` → «после» `test_merge_outcome_module.py::test_ac10_component_without_python_has_section_except_canary` — `tests/test_merge_outcome_module.py:655`
- mutation-043: «до» `Ac9ReviewNotRunTest::test_ac9_no_record_for_current_head_says_not_run` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:916` → «после» `test_merge_outcome_module.py::test_ac9_no_record_for_current_head_says_not_run` — `tests/test_merge_outcome_module.py:622`
- mutation-043: «до» `Ac10NoPythonSectionTest::test_ac10_component_without_python_has_section_except_canary` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:950` → «после» `test_merge_outcome_module.py::test_ac10_component_without_python_has_section_except_canary` — `tests/test_merge_outcome_module.py:655`
- mutation-043: «до» `Ac8ReviewLinesTest::test_ac8_review_section_carries_outcome_gate_lines_for_head` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:881` → «после» `test_merge_outcome_module.py::test_ac8_review_section_carries_outcome_gate_lines_for_head` — `tests/test_merge_outcome_module.py:588`
- mutation-044: «до» `Ac10NoPythonSectionTest::test_ac10_component_without_python_has_section_except_canary` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:948` → «после» `test_merge_outcome_module.py::test_ac10_component_without_python_has_section_except_canary` — `tests/test_merge_outcome_module.py:653`
- mutation-045: «до» `Ac12TwoSidedRetryTest::test_ac12_passed_with_retry_is_side_failure_retry` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:1051` → «после» `test_merge_outcome_module.py::test_ac12_passed_with_retry_is_side_failure_retry` — `tests/test_merge_outcome_module.py:728`
- mutation-045: «до» `Ac11TwoSidedErrorNameTest::test_ac11_only_check_failure_is_failure_on_check` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:1019` → «после» `test_merge_outcome_module.py::test_ac11_only_check_failure_is_failure_on_check` — `tests/test_merge_outcome_module.py:695`
- mutation-046: «до» `Ac12TwoSidedRetryTest::test_ac12_passed_with_retry_is_side_failure_retry` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:1051` → «после» `test_merge_outcome_module.py::test_ac12_passed_with_retry_is_side_failure_retry` — `tests/test_merge_outcome_module.py:728`
- mutation-046: «до» `Ac11TwoSidedErrorNameTest::test_ac11_only_check_failure_is_failure_on_check` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:1022` → «после» `test_merge_outcome_module.py::test_ac11_only_check_failure_is_failure_on_check` — `tests/test_merge_outcome_module.py:698`
- mutation-047: «до» `Ac12TwoSidedRetryTest::test_ac12_passed_with_retry_is_side_failure_retry` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:1051` → «после» `test_merge_outcome_module.py::test_ac12_passed_with_retry_is_side_failure_retry` — `tests/test_merge_outcome_module.py:728`
- mutation-048: «до» `Ac13RetriedBaseRerunTest::test_ac13_retried_on_base_rerun_is_red_base` — `tests/outcome_gate_sandbox.py:837` → «после» `test_merge_outcome_module.py::test_ac13_retried_on_base_rerun_is_red_base` — `tests/test_merge_outcome_module.py:82`
- mutation-049: «до» `Ac14OutOfBoundsTest::test_ac14_test_profile_and_multi_component_keep_prior_results` — `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:1113` → «после» `test_merge_outcome_module.py::test_ac14_test_profile_and_multi_component_keep_prior_results` — `tests/test_merge_outcome_module.py:787`
- mutation-050: «до» `AddedLinesTest::test_quoted_path_latin1_text_and_no_final_newline` — `tests/test_outcome_integrity_added_lines.py:60` → «после» `test_outcome_gate_module.py::test_quoted_path_latin1_text_and_no_final_newline` — `tests/test_outcome_gate_module.py:2486`
- mutation-051: «до» `AddedLinesTest::test_unexpected_header_is_prepare_refusal` — `tests/test_outcome_integrity_added_lines.py:99` → «после» `test_outcome_gate_module.py::test_unexpected_header_is_prepare_refusal` — `tests/test_outcome_gate_module.py:2527`
- mutation-051: «до» `AddedLinesTest::test_noprefix_config_does_not_hide_added_lines` — `tests/test_outcome_integrity_added_lines.py:85` → «после» `test_outcome_gate_module.py::test_noprefix_config_does_not_hide_added_lines` — `tests/test_outcome_gate_module.py:2512`
- mutation-052: «до» `AddedLinesTest::test_unexpected_header_is_prepare_refusal` — `tests/test_outcome_integrity_added_lines.py:99` → «после» `test_outcome_gate_module.py::test_unexpected_header_is_prepare_refusal` — `tests/test_outcome_gate_module.py:2527`
- mutation-053: «до» `AddedLinesTest::test_deleted_file_header_dev_null_is_not_refusal` — `tests/test_outcome_integrity_added_lines.py:110` → «после» `test_outcome_gate_module.py::test_deleted_file_header_dev_null_is_not_refusal` — `tests/test_outcome_gate_module.py:2539`
- mutation-054: «до» `CodeExceptionRenameTest::test_rename_from_test_path_to_code_path_is_checked` — `tests/test_outcome_integrity_added_lines.py:138` → «после» `test_outcome_gate_module.py::test_rename_from_test_path_to_code_path_is_checked` — `tests/test_outcome_gate_module.py:2553`
- mutation-055: «до» `CodeExceptionRenameTest::test_rename_between_test_paths_is_not_checked` — `tests/test_outcome_integrity_added_lines.py:156` → «после» `test_outcome_gate_module.py::test_rename_between_test_paths_is_not_checked` — `tests/test_outcome_gate_module.py:2571`

## Соответствие имён «до → после»

Каждый тест исходного файла перенесён в функцию приёмника с тем же именем.

- `Ac1ProofLineTest::test_ac1_passed_record_carries_head_base_key_and_mandate` → `test_merge_outcome_module.py::test_ac1_passed_record_carries_head_base_key_and_mandate`
- `Ac1ProofLineTest::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record` → `test_merge_outcome_module.py::test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record`
- `Ac2MergeFindingTest::test_ac2_finding_without_mandate_escalates_merge` → `test_merge_outcome_module.py::test_ac2_finding_without_mandate_escalates_merge`
- `Ac2MergeFindingTest::test_ac2_merge_refusal_action_is_operator_class_key` → `test_merge_outcome_module.py::test_ac2_merge_refusal_action_is_operator_class_key`
- `Ac3MergePrepareTest::test_ac3_prepare_failures_keep_merge_gate_without_push` → `test_merge_outcome_module.py::test_ac3_prepare_failures_keep_merge_gate_without_push`
- `Ac4ProofTest::test_ac4_same_quadruple_proves_without_run` → `test_merge_outcome_module.py::test_ac4_same_quadruple_proves_without_run`
- `Ac5ProofMismatchTest::test_ac5_other_base_key_or_mandate_runs_gate` → `test_merge_outcome_module.py::test_ac5_other_base_key_or_mandate_runs_gate`
- `Ac6LegacyRecordTest::test_ac6_record_without_proof_line_runs_gate` → `test_merge_outcome_module.py::test_ac6_record_without_proof_line_runs_gate`
- `Ac7MergeBaseTest::test_ac7_base_is_merge_base_with_fetched_main_not_diff_base` → `test_merge_outcome_module.py::test_ac7_base_is_merge_base_with_fetched_main_not_diff_base`
- `Ac7MergeBaseTest::test_ac7_doc_only_lag_runs_gate_with_merge_base` → `test_merge_outcome_module.py::test_ac7_doc_only_lag_runs_gate_with_merge_base`
- `Ac7MergeBaseTest::test_ac7_gate_after_fresh_and_before_acceptance_locks` → `test_merge_outcome_module.py::test_ac7_gate_after_fresh_and_before_acceptance_locks`
- `Ac7MergeBaseTest::test_ac7_canary_from_db_and_in_dev_base_is_diff_base` → `test_merge_outcome_module.py::test_ac7_canary_from_db_and_in_dev_base_is_diff_base`
- `Ac8ReviewLinesTest::test_ac8_review_section_carries_outcome_gate_lines_for_head` → `test_merge_outcome_module.py::test_ac8_review_section_carries_outcome_gate_lines_for_head`
- `Ac9ReviewNotRunTest::test_ac9_no_record_for_current_head_says_not_run` → `test_merge_outcome_module.py::test_ac9_no_record_for_current_head_says_not_run`
- `Ac10NoPythonSectionTest::test_ac10_component_without_python_has_section_except_canary` → `test_merge_outcome_module.py::test_ac10_component_without_python_has_section_except_canary`
- `Ac11TwoSidedErrorNameTest::test_ac11_only_check_failure_is_failure_on_check` → `test_merge_outcome_module.py::test_ac11_only_check_failure_is_failure_on_check`
- `Ac12TwoSidedRetryTest::test_ac12_passed_with_retry_is_side_failure_retry` → `test_merge_outcome_module.py::test_ac12_passed_with_retry_is_side_failure_retry`
- `Ac13RetriedBaseRerunTest::test_ac13_retried_on_base_rerun_is_red_base` → `test_merge_outcome_module.py::test_ac13_retried_on_base_rerun_is_red_base`
- `Ac14OutOfBoundsTest::test_ac14_test_profile_and_multi_component_keep_prior_results` → `test_merge_outcome_module.py::test_ac14_test_profile_and_multi_component_keep_prior_results`
- `AddedLinesTest::test_quoted_path_latin1_text_and_no_final_newline` → `test_outcome_gate_module.py::test_quoted_path_latin1_text_and_no_final_newline`
- `AddedLinesTest::test_noprefix_config_does_not_hide_added_lines` → `test_outcome_gate_module.py::test_noprefix_config_does_not_hide_added_lines`
- `AddedLinesTest::test_unexpected_header_is_prepare_refusal` → `test_outcome_gate_module.py::test_unexpected_header_is_prepare_refusal`
- `AddedLinesTest::test_deleted_file_header_dev_null_is_not_refusal` → `test_outcome_gate_module.py::test_deleted_file_header_dev_null_is_not_refusal`
- `CodeExceptionRenameTest::test_rename_from_test_path_to_code_path_is_checked` → `test_outcome_gate_module.py::test_rename_from_test_path_to_code_path_is_checked`
- `CodeExceptionRenameTest::test_rename_between_test_paths_is_not_checked` → `test_outcome_gate_module.py::test_rename_between_test_paths_is_not_checked`

## Находки

- Находка mutation-036 (заявка `Ac7MergeBaseTest::test_ac7_canary_from_db_and_in_dev_base_is_diff_base`, альтернатива «база выхода из `in_dev` — sha зафетченного main»): «до» не убита никем. Патч `orchestrator/advance_gates/outcome_integrity.py` отдаёт базой `_diff_base` sha `refs/remotes/origin/main`, но ветка задачи в стенде заведена от текущего main без новых коммитов main, поэтому merge-base ветки с `origin/main` и сам sha `origin/main` совпадают — подслучай (б) эту альтернативу не различает. Тест не удалён, перенесён в `test_ac7_canary_from_db_and_in_dev_base_is_diff_base`; две другие альтернативы заявки доказаны патчами 034 и 035.
- Иных выживших «до» нет; исходов «ошибка сбора, импорта или setup», «итог неизвестен» и предела в последних строках нет.

## Детерминизм при случайной стороне и числах (ANSWER-1 п. 2)

- `Ac11TwoSidedErrorNameTest::test_ac11_only_check_failure_is_failure_on_check` (сторона из `random`) — убийца патчей 045 и 046: оба меняют `_run_side_report` в `orchestrator/advance_gates/two_sided.py`, общий для стороны базы и стороны головы, поэтому подслучай (а) `failed_other` падает на любой выпавшей стороне (патч 045 — исход стороны «утверждение», отказа нет; патч 046 — вид стороны постоянный, имени `ValueError` в нём нет). Обе мутации убивает и `Ac12TwoSidedRetryTest::test_ac12_passed_with_retry_is_side_failure_retry`, который перебирает обе стороны циклом.
- `Ac14OutOfBoundsTest::test_ac14_test_profile_and_multi_component_keep_prior_results` (сторона из `random` в подслучае (в)) — единственный убийца патча 049; падает подслучай (а) «мерж test_profile», где случайной стороны нет: `in_outcome_bounds` без `from_components` включает гейт исходов у `test_profile` на мерже.
- `Ac8ReviewLinesTest::test_ac8_review_section_carries_outcome_gate_lines_for_head` (числа `nb`, `m`, `k` из `random`) — единственный убийца патчей 038 и 039: патч 038 сверяет голову с полем базы записи — запись не находится при любых числах; патч 039 отрезает имя ANSWER у каждой покрытой находки, а покрытых находок `m ≥ 2` при любом зерне.

## Числа и время

- Тестов «до»: 19 в `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py` (строк 1144), 6 в `tests/test_outcome_integrity_added_lines.py` (строк 156), 53 в `tests/test_outcome_gate_module.py` на базе (строк 2412).
- Тестов «после»: 19 в `tests/test_merge_outcome_module.py` (строк 814), 59 в `tests/test_outcome_gate_module.py` (строк 2571); `tests/merge_outcome_sandbox.py` — строк 353, тестов нет.
- Время контрольных прогонов `mutation-run` (без патча, рабочих процессов `auto`): «до» — 19.12 с (№1), 20.09 с (№2), 21.46 с (№3), 28.87 с (№4), 27.07 с (№5), 1.13 с (№6, группа Д, 6 тестов).
- Время контрольных прогонов `mutation-run` «после»: 20.85 с (№7), 19.26 с (№8), 18.97 с (№9), 20.82 с (№10), 19.31 с (№11) — группа М, 19 тестов; 25.88 с (№12, группа Д — весь `tests/test_outcome_gate_module.py`, 59 тестов).
- Ревизии шапок: «до» — base `72d52fd3`, «после» — worktree `98398b90` (№7–№10, код ещё не закоммичен) и `b06b18d2` (№11–№12, после WIP-чекпоинта пульта); `git diff --quiet` по `orchestrator/` между ними — код 0.

## Предусловия тела теста

- `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:715` → `tests/test_merge_outcome_module.py:422`
- `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:718` → `tests/test_merge_outcome_module.py:425`
- `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:749` → `tests/test_merge_outcome_module.py:457`
- `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:786` → `tests/test_merge_outcome_module.py:494`
- `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:801` → `tests/test_merge_outcome_module.py:508`

## Переименованные локальные имена

- `files` (бывшие :150–152 `CodeExceptionRenameTest::test_rename_between_test_paths_is_not_checked`) → `rename_files`: совпадало с функцией модуля `files`.
- Иных совпадений локальных имён исходных тестов с функциями и фикстурами приёмников нет; локальные `files` методов `IdOutcomeGateSandbox` не тронуты.

## Удалённые дубли

Нет: все 25 тестов перенесены.

## Импортёры

- `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py` и `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py`: изменена только строка источника импорта (`tests.merge_outcome_sandbox`), разбивка строк та же.
- Под ролью: `python3 -m pytest --collect-only -q -p no:cacheprovider <оба импортёра>` — «61 tests collected in 0.16s».
- Итог CI кодовой ветки по `outcome_prior` и `outcome_components`: на конце шага разработчика ветки задачи в origin нет (`git ls-remote origin refs/heads/task/01m5r0dpnhz7n8ybxmh375smee-…` — пусто), прогона CI ещё не было; итог дописывается после первого пуша ветки пультом.

## Влияние на систему

Код `orchestrator/` не меняется; мутации живут только во временной копии
`mutation-run`. Свойства двух удаляемых файлов переносятся с дословными
ожиданиями; утверждения подготовки песочницы мержа переехали дословно
(`ast.dump`). Импортёры меняют только источник импорта. Откат — revert
merge-коммита задачи.

## Риски

- Мутации подслучаев со случайной стороной (`Ac11`, `Ac14`) и числами (`Ac8`) —
  патчи меняют путь кода одинаково для обеих сторон и любых чисел (обоснование
  по ANSWER-1 п. 2 — в разделе «Детерминизм при случайной стороне и числах»).
- Итог CI кодовой ветки по импортёрам (требование 11, AC-8) в шаге разработчика
  недоступен: ветка задачи до конца шага не в origin. Сбор импортёров под ролью —
  61 тест; приёмочный тест `test_ac8_plan_names_ci_result_for_importers` до
  дописки итога CI красный. Остальные тесты планки на PLAN с диска (сценарий
  `plancheck.py` каталога документов: `_pult` с `artifact_text` по диску) —
  81 из 82 зелёные; `plank-run` по закоммиченной ревизии документов — 99 passed,
  10 failed (до автокоммита этого PLAN).

## Предложения системе

- SPEC волн сведения (требование 11 «итог CI кодовой ветки в PLAN») требует от
  разработчика итога CI, которого в его шаге ещё нет: ветка пушится пультом после
  шага. Класс — требование SPEC к артефакту роли на событие после её шага;
  `templates/SPEC` / skill аналитика: такой итог относить к ревьюверу или гейту.
- `plank-run` читает PLAN из закоммиченной ревизии ссылки документов — правку PLAN
  текущего шага планка не видит до автокоммита; не хватает режима `plank-run
  --docs-disk` (обход — `plancheck.py` каталога документов).
