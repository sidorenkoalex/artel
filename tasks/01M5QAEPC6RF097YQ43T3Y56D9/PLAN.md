---
task: 01M5QAEPC6RF097YQ43T3Y56D9
type: plan
author_role: developer
status: draft
schema_version: 5
---

# PLAN: Сведение тестов, волна 2а-1б — тесты гейта исходов `outcome_gate` в `tests/test_outcome_gate_module.py` в стиле pytest с доказательством мутациями

## Подход

Порядок волн сведения: набор мутаций к коду `orchestrator/` по строкам
«Ловит мутацию» 42 тестов
`tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`, таблица «до» на
исходном файле (`--ref base`), свод тестов функциями модуля и удаление
исходного файла, таблица «после» на `tests/test_outcome_gate_module.py`
(`--ref worktree`) теми же частями.

- Набор: 63 патча `mutation-001.diff`…`mutation-063.diff`. Заготовка
  ликвидированной 2а-1 (`refs/artifacts/01M5PHK9K0YQCTPA6CK94BBZ33`,
  патчи 001–030 в финальных редакциях, 011 и 027 — переписанные там) взята
  как основа и проверена заново: каждый патч применяется к 579a3819
  (`git apply --check`), прогнан «до» в этой задаче. Заготовка соединяла в
  одном патче не одинаковые по смыслу альтернативы и не воплощала часть
  альтернатив заявок; по требованию 1 SPEC патчи 006, 008, 015, 016, 018
  сужены до одной альтернативы (006, 008, 015 перепрогнаны «до» частью 6-15; 016, 018 сужены ещё до прогона части 16-30), а
  недостающие альтернативы — патчи 031–063.
- Свод механический (разбор синтаксического дерева исходника):
  `self.assert*` → `assert` с сообщением вторым операндом, `self.` →
  `box.`, вызовы методов-помощников → функции модуля голым именем со
  стендом первым аргументом; бывший `subTest` — строка
  `case = f"{<ярлык>}, зерно {box.seed}"` и тело на уровень выше в той же
  функции (цикл сохранён), каждое прямое утверждение подслучая несёт
  `case + <сообщение>`, каждый вызов помощника исхода — `case=case`.
- Помощники `refusal`, `no_gate_refusal` (из песочницы), `assert_no_gate`,
  `assert_prepare` — функции модуля с последним параметром
  `case: str = ""`, `case` спереди к каждому тексту сообщения;
  `assert_prepare` пробрасывает `case=case` в `refusal` (ANSWER-1, п. 1);
  `prepared`, `broken_task` — функции модуля без `case`. Методы песочницы
  не тронуты.
- Локальные переменные, совпадающие с функциями модуля, переименованы:
  `vitest` → `is_vitest` (все одиннадцать мест), `refusal` → `decide_refusal`.
- Импорт: из `tests.outcome_gate_sandbox` — только имена, которых в модуле
  нет (`OutcomeGateSandbox`, `GATE_ACTIONS`, `py_source`, `re` и константы
  действий); `OUTCOME_ACTION`, `ulid`, `js_source`, стандартные модули —
  прежние имена модуля.
- Удалённых дублей нет: все 42 теста перенесены под прежними именами.

## Шаги

1. Набор патчей и таблица «до» (`mutation-run --ref base --tests
   tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py --copy-table
   --wait-lock 4`) частями 1-15, 16-30, 31-45, 46-60, 61-63 и
   перепрогон переписанных патчей 006, 008, 015 частью 6-15 и патча 031
   частью 31-31.
2. Свод 42 тестов в `tests/test_outcome_gate_module.py`, удаление исходного
   файла, карта `python3 scripts/codebase_map.py`.
3. Таблица «после» (`mutation-run --ref worktree --tests
   tests/test_outcome_gate_module.py --copy-table --wait-lock 4`) частями
   1-15, 16-30, 31-45, 46-60, 61-63 при том же числе рабочих процессов
   (`auto`), перед каждой частью — `git status --porcelain -- orchestrator/`.
4. Строки падений «до»/«после», соответствие имён, числа, guard.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (раздел «Мутации и заявки») |
| 2 | 1 (раздел «Мутации до») |
| 3 | 4 (раздел «Строки падений») |
| 4 | 1, 3 (убийцы вне методов подготовки; патч 031 переписан; раздел «Находки») |
| 5 | 1, 3 (только `--wait-lock 4`) |
| 6 | 1–4 (временные файлы — только первым уровнем каталога документов, не `.md`) |
| 7 | 2 |
| 8 | 2 (фикстура `box`) |
| 9 | 2 (помощники — функции модуля) |
| 10 | 2 |
| 11 | 2 |
| 12 | 2 (дублей не удалено) |
| 13 | 3 (раздел «Мутации после») |
| 14 | 3, 4 (раздел «Числа и время») |
| 15 | 2 |
| 16 | 2 |
| 17 | вне ролей (сессия при Операторе) |

## Мутации и заявки

Строка = мутация, заявившие её тесты исходного файла (одинаковые по смыслу
заявки — одной мутацией) и что меняет патч. Патчи меняют
`orchestrator/advance_gates/outcome_integrity.py`, кроме 003 и 004
(`orchestrator/fsm_advance.py`).

- mutation-001: `Ac1OutOfBoundsTest::test_ac1_artel_and_test_profile_no_gate` («гейт создаётся у любого профиля»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_bounds` не сверяет `in_outcome_bounds`.
- mutation-002: `Ac1OutOfBoundsTest::test_ac1_decide_skip_refusal_and_canary_no_gate` («условие `t["is_canary"]` пропущено»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_bounds` не возвращает `None` для канарейки.
- mutation-003: `Ac2PlaceTest::test_ac2_text_gate_refusal_first_no_outcome_runs` («гейт исходов поставлен до гейта по тексту»); патч `orchestrator/fsm_advance.py`: в `in_dev` вызов `_outcome_integrity_gate_refuses` перед `_test_integrity_gate_refuses`.
- mutation-004: `Ac2PlaceTest::test_ac2_outcome_refusal_stops_before_review_rework_gate` («гейт исходов поставлен после гейта переделки ревью»); патч `orchestrator/fsm_advance.py`: `_review_rework_gate_refuses` перед гейтом исходов.
- mutation-005: `Ac3RunsTest::test_ac3_full_suite_on_base_and_head_checkouts_fresh` («`fresh` не передан — `False` в вызове»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_full_run` зовёт `components_full_suite(..., fresh=False)`.
- mutation-006: `Ac4PrepareTest::test_ac4_git_preparation_failures_refuse` («`None` от `diff_base` — гейт пропущен»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_gate` при отказе «… (diff_base) не определена» возвращает `None` (сужен до одной альтернативы).
- mutation-007: `Ac4PrepareTest::test_ac4_git_preparation_failures_refuse`, `Ac4PrepareTest::test_ac4_git_base_checkout_failure_refuses`, `Ac4PrepareTest::test_ac4_git_head_checkout_failure_refuses` («сбой выписки проглочен — сравнение по одной стороне»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_checkouts` при сбое выписки выписывает sha другой стороны.
- mutation-008: `Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side` («"неизвестно" на базе принят за пустой отчёт»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_full_run` на стороне базы при «прогон не начат» возвращает пустой список (сужен до одной альтернативы).
- mutation-009: `Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side`, `Ac4PrepareTest::test_ac4_side_head_unknown_refuses_naming_head`, `Ac4PrepareTest::test_ac4_side_base_timeout_refuses_naming_base`, `Ac4PrepareTest::test_ac4_side_head_timeout_refuses_naming_head` («сторона в отказе не названа»); патч `orchestrator/advance_gates/outcome_integrity.py`: текст отказа `_full_run` без названия стороны.
- mutation-010: `Ac5PassToPassTest::test_ac5_retried_on_base_not_in_pass_to_pass` («в набор берётся любой `passed` базы без сверки `retries == 0`»); патч `orchestrator/advance_gates/outcome_integrity.py`: `in_pass_to_pass` без `retries == 0`.
- mutation-011: `Ac5PassToPassTest::test_ac5_no_tests_on_base_empty_pass_to_pass` («"нет тестов" базы принят за отказ»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_full_run` отказывает при пустом списке записей стороны.
- mutation-012: `Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit` («перепрогон базы пропущен»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_rerun` по умолчанию только на стороне ветки.
- mutation-013: `Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit` («`passed` с повтором не считается красным»); патч `orchestrator/advance_gates/outcome_integrity.py`: `red_on_branch` без ветки `passed` с повтором.
- mutation-014: `Ac6RerunTest::test_ac6_skipped_on_branch_not_rerun` («`skipped` на ветке считается красным»); патч `orchestrator/advance_gates/outcome_integrity.py`: `red_on_branch` считает `skipped` красным.
- mutation-015: `Ac7RerunPrepareTest::test_ac7_rerun_preparation_refusals`, `Ac7RerunPrepareTest::test_ac7_rerun_unknown_outcome_refuses` («"неизвестно" перепрогона принят за красный»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_rerun` не отказывает при исходе перепрогона не «зелёный»/«красный» (сужен до одной альтернативы).
- mutation-016: `Ac7RerunPrepareTest::test_ac7_rerun_preparation_refusals`, `Ac7RerunPrepareTest::test_ac7_rerun_base_skipped_refuses` («пропуск на базе принят за красный базы»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_rerun` на базе отказывает только при отсутствии записи, `skipped` идёт красным (сужен до одной альтернативы).
- mutation-017: `Ac7RerunPrepareTest::test_ac7_branch_rerun_red_kinds`, `Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red` («`passed` с повтором — зелёный»); патч `orchestrator/advance_gates/outcome_integrity.py`: зелёный перепрогона — любой `passed`.
- mutation-018: `Ac7RerunPrepareTest::test_ac7_branch_rerun_red_kinds`, `Ac7RerunPrepareTest::test_ac7_branch_rerun_skipped_is_red` («`skipped` на перепрогоне ветки — зелёный»); патч `orchestrator/advance_gates/outcome_integrity.py`: зелёный перепрогона — и `skipped` (сужен до одной альтернативы).
- mutation-019: `Ac7RerunPrepareTest::test_ac7_branch_rerun_red_kinds`, `Ac7RerunPrepareTest::test_ac7_branch_rerun_error_is_red`, `Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red` («итог — "нестабилен после правки" вместо "сломан правкой"»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_redness` всегда даёт «нестабилен после правки».
- mutation-020: `Ac8VerdictByRecordTest::test_ac8_broken_unstable_and_flaky_on_base`, `Ac8VerdictByRecordTest::test_ac8_unstable_after_change_general_refusal` («"нестабилен" не отличается от "сломан" — действие "… — сломан правкой"»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_redness` всегда даёт «сломан правкой».
- mutation-021: `Ac8VerdictByRecordTest::test_ac8_broken_unstable_and_flaky_on_base`, `Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal` («красная база перепрогона не читается»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_redness` не смотрит на красноту базы.
- mutation-022: `Ac8VerdictByRecordTest::test_ac8_neighbour_red_in_same_file_does_not_redden_rerun` («итог перепрогона по вердикту прогона»); патч `orchestrator/advance_gates/outcome_integrity.py`: зелёный перепрогона — `run.state == GREEN`.
- mutation-023: `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings`, `Ac9CompareTest::test_ac9_junit_records_findings` («"стал пропуском" только у `passed` базы»); патч `orchestrator/advance_gates/outcome_integrity.py`: `compare` — «стал пропуском» только при `passed` базы.
- mutation-024: `Ac9CompareTest::test_ac9_one_finding_per_id_senior_kind` («находка сравнения добавляется к "сломан правкой"»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_judge` не отбрасывает записи `compare` по уже взятым идентификаторам.
- mutation-025: `Ac10OrderTest::test_ac10_findings_order_and_one_line_each` («в порядке отчёта»); патч `orchestrator/advance_gates/outcome_integrity.py`: `ordered` возвращает список без сортировки.
- mutation-026: `Ac11MandateTest::test_ac11_file_and_prefix_mandate_cover_findings`, `Ac11MandateTest::test_ac11_class_prefix_mandate_covers`, `Ac11MandateTest::test_ac11_method_prefix_mandate_covers_variants` («мандат сверяется точным равенством с идентификатором»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_covering_element` — только равенство элемента идентификатору.
- mutation-027: `Ac11MandateTest::test_ac11_file_and_prefix_mandate_cover_findings`, `Ac11MandateTest::test_ac11_other_file_mandate_does_not_cover` («покрытие по имени файла без пути»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_covering_element` считает покрывающим любой элемент без `::`, не сверяя путь.
- mutation-028: `Ac11MandateTest::test_ac11_prefix_needs_separator_after_it` («`startswith` без сверки следующего символа»); патч `orchestrator/advance_gates/outcome_integrity.py`: хвост после префикса не сверяется.
- mutation-029: `Ac11MandateTest::test_ac11_role_autocommitted_answer_does_not_cover` («мандат собран без отбраковки автокоммита роли»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_answer_mandates` не отбрасывает автокоммит шага роли.
- mutation-030: `Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts` («число покрытых мандатом не указано»); патч `orchestrator/advance_gates/outcome_integrity.py`: из строки чисел записи пройденного гейта убрано число покрытых мандатом.
- mutation-031: `Ac1OutOfBoundsTest::test_ac1_artel_and_test_profile_no_gate` («граница по `reported(profile)` без `from_components`»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_bounds` сверяет границу по `project_profile.reported(profile)` вместо `in_outcome_bounds` (без `from_components`). Первая редакция меняла общую `in_outcome_bounds` в `acceptance.py`, и её «убивало» только утверждение `in_dev_task` (выход из `tests_writing` отклонён) — переписана и перепрогнана частью 31-31.
- mutation-032: `Ac1OutOfBoundsTest::test_ac1_decide_skip_refusal_and_canary_no_gate` («отказ решения `decide` у гейта исходов — отказ перехода»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_outcome_integrity_gate` при отказе `decide` возвращает отказ «переход отклонён: гейт неослабления по исходам».
- mutation-033: `Ac1OutOfBoundsTest::test_ac1_decide_skip_refusal_and_canary_no_gate` («прогон по профилю записи в обход решения»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_bounds` при отказе `decide` берёт первый профиль `component_profiles` записи.
- mutation-034: `Ac3RunsTest::test_ac3_full_suite_on_base_and_head_checkouts_fresh` («голова гоняется в рабочей копии задачи»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_full_runs` гоняет голову в `workspace.path(task_id)`.
- mutation-035: `Ac3RunsTest::test_ac3_full_suite_on_base_and_head_checkouts_fresh` («база гоняется на дереве головы»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_full_runs` гоняет обе стороны на выписке головы.
- mutation-036: `Ac4PrepareTest::test_ac4_git_preparation_failures_refuse`, `Ac4PrepareTest::test_ac4_git_head_not_read_refuses` («пустая голова — гейт пропущен»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_gate` при отказе «голова … не прочитана» возвращает `None`.
- mutation-037: `Ac4PrepareTest::test_ac4_side_base_timeout_refuses_naming_base` («таймаут базы принят за пустой отчёт»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_full_run` на стороне базы при таймауте возвращает пустой список.
- mutation-038: `Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side`, `Ac4PrepareTest::test_ac4_side_head_timeout_refuses_naming_head` («таймаут головы принят за красный прогон»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_full_run` на стороне головы при таймауте отдаёт записи прогона, как у красного.
- mutation-039: `Ac4PrepareTest::test_ac4_side_head_unknown_refuses_naming_head` («"неизвестно" на голове принят за красный прогон»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_full_run` на стороне головы при «прогон не начат» отдаёт записи прогона.
- mutation-040: `Ac4PrepareTest::test_ac4_side_head_unknown_refuses_naming_head` («"неизвестно" на голове принят за пустой отчёт»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_full_run` на стороне головы при «прогон не начат» возвращает пустой список.
- mutation-041: `Ac5PassToPassTest::test_ac5_no_tests_on_base_empty_pass_to_pass` («"нет тестов" базы принят за "все тесты исчезли"»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_judge` при пустой базе пишет «исчез» по каждому тесту головы.
- mutation-042: `Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit` («перепрогон по всем файлам набора»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_rerun` передаёт раннеру все файлы отчёта базы.
- mutation-043: `Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit` («предел — `config.FULL_SUITE_TIMEOUT_SEC`»); патч `orchestrator/advance_gates/outcome_integrity.py`: предел `_rerun` — `config.FULL_SUITE_TIMEOUT_SEC`.
- mutation-044: `Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit` («предел приёмки»); патч `orchestrator/advance_gates/outcome_integrity.py`: предел `_rerun` — `config.ACCEPTANCE_TIMEOUT_SEC`.
- mutation-045: `Ac7RerunPrepareTest::test_ac7_rerun_preparation_refusals` («без `select` перепрогон идёт полным набором»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_rerun` при отказе запуска (`run.refusal`) гоняет полный набор (`report_run(..., None, ...)`).
- mutation-046: `Ac7RerunPrepareTest::test_ac7_rerun_preparation_refusals`, `Ac7RerunPrepareTest::test_ac7_rerun_timeout_refuses` («предел перепрогона принят за красный»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_rerun` не отказывает при таймауте перепрогона.
- mutation-047: `Ac7RerunPrepareTest::test_ac7_rerun_preparation_refusals`, `Ac7RerunPrepareTest::test_ac7_rerun_base_record_missing_refuses` («отсутствие записи на базе принято за красный базы»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_rerun` на базе отказывает только при `skipped`, отсутствие записи идёт красным.
- mutation-048: `Ac7RerunPrepareTest::test_ac7_branch_rerun_red_kinds`, `Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red` («отсутствие записи на перепрогоне ветки — зелёный»); патч `orchestrator/advance_gates/outcome_integrity.py`: зелёный перепрогона — и отсутствие записи.
- mutation-049: `Ac7RerunPrepareTest::test_ac7_branch_rerun_red_kinds`, `Ac7RerunPrepareTest::test_ac7_branch_rerun_skipped_is_red` («`skipped` на перепрогоне ветки — отказ»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_rerun` отказывает (`_Prepare`) при `skipped` на перепрогоне ветки.
- mutation-050: `Ac7RerunPrepareTest::test_ac7_branch_rerun_red_kinds`, `Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red` («отсутствие записи на перепрогоне ветки — отказ»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_rerun` отказывает (`_Prepare`) при отсутствии записи на перепрогоне ветки.
- mutation-051: `Ac7RerunPrepareTest::test_ac7_branch_rerun_error_is_red` («`error` перепрогона не считается красным — зелёный»); патч `orchestrator/advance_gates/outcome_integrity.py`: зелёный перепрогона — и `error`.
- mutation-052: `Ac8VerdictByRecordTest::test_ac8_broken_unstable_and_flaky_on_base`, `Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal` («строка о базе не пишется»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_judge` не пишет строк «нестабилен и на базе».
- mutation-053: `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings` («`todo` — без сверки с базой»); патч `orchestrator/advance_gates/outcome_integrity.py`: `compare` — «появилось todo» при `todo` ветки независимо от базы.
- mutation-054: `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings` («`fails` — без сверки с базой»); патч `orchestrator/advance_gates/outcome_integrity.py`: `compare` — «появилось fails» при `fails` ветки независимо от базы.
- mutation-055: `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings` («новый идентификатор не проверяется»); патч `orchestrator/advance_gates/outcome_integrity.py`: `compare` не обходит идентификаторы, которых нет на базе.
- mutation-056: `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings` («у `to_todo` две записи сравнения — пропуск и `todo`»); патч `orchestrator/advance_gates/outcome_integrity.py`: `compare` к «появилось todo» с пропуском добавляет «стал пропуском».
- mutation-057: `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings` («рост пропусков — отдельные строки по тестам без итоговой»); патч `orchestrator/advance_gates/outcome_integrity.py`: при росте пропусков `_judge` пишет строку на каждый пропуск вместо итоговой.
- mutation-058: `Ac9CompareTest::test_ac9_junit_records_findings` («исчезновение ищется не по отчёту»); патч `orchestrator/advance_gates/outcome_integrity.py`: `compare` не пишет «исчез» по отчёту.
- mutation-059: `Ac10OrderTest::test_ac10_findings_order_and_one_line_each` («в порядке сравнения — прочие раньше красных»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_judge` ставит записи `compare` перед «сломан правкой» и не пересортировывает итог.
- mutation-060: `Ac10OrderTest::test_ac10_findings_order_and_one_line_each` («внутри вида без сортировки»); патч `orchestrator/advance_gates/outcome_integrity.py`: `ordered` сортирует только по виду.
- mutation-061: `Ac10OrderTest::test_ac10_findings_order_and_one_line_each` («все одной строкой»); патч `orchestrator/advance_gates/outcome_integrity.py`: строки отказа соединены «; » вместо перевода строки.
- mutation-062: `Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts` («запись пройденного гейта не пишется»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_judge` не зовёт `store.journal` для «гейт неослабления по исходам пройден».
- mutation-063: `Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts` («прогоны файлов не посчитаны»); патч `orchestrator/advance_gates/outcome_integrity.py`: `_rerun` не считает прогоны файлов.

## Мутации до

Вывод `mutation-run --wait` каждой части дословно (шапка и все строки),
`--ref base`, тесты — исходный файл, рабочих процессов — `auto` (умолчание
узла прогона) во всех частях. Части 1-15, 16-30, 31-45, 46-60, 61-63;
перепрогон переписанных патчей 006, 008, 015 — частью 6-15, патча 031 —
частью 31-31 (у мутации действует последняя строка в порядке текста).

Прогон №1 (`--patches 1-15`, рабочих процессов auto):

# mutation-run №1 задачи 01M5QAEPC6RF097YQ43T3Y56D9
# источник патчей: каталог на диске
# ревизия прогона: base 579a38199ce682917b9d5e40f15ac95cde4aaddc
# тесты: tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py
# рабочих процессов: auto
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
1	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac1OutOfBoundsTest::test_ac1_artel_and_test_profile_no_gate
2	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac1OutOfBoundsTest::test_ac1_decide_skip_refusal_and_canary_no_gate
3	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac3RunsTest::test_ac3_full_suite_on_base_and_head_checkouts_fresh,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac5PassToPassTest::test_ac5_retried_on_base_not_in_pass_to_pass,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac5PassToPassTest::test_ac5_no_tests_on_base_empty_pass_to_pass,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac2PlaceTest::test_ac2_text_gate_refusal_first_no_outcome_runs,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts
4	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac2PlaceTest::test_ac2_outcome_refusal_stops_before_review_rework_gate
5	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac3RunsTest::test_ac3_full_suite_on_base_and_head_checkouts_fresh
6	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_git_preparation_failures_refuse,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_git_head_not_read_refuses
7	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_git_head_checkout_failure_refuses,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_git_base_checkout_failure_refuses
8	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_base_timeout_refuses_naming_base
9	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_head_timeout_refuses_naming_head,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_base_timeout_refuses_naming_base,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_head_unknown_refuses_naming_head
10	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac5PassToPassTest::test_ac5_retried_on_base_not_in_pass_to_pass,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red
11	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac5PassToPassTest::test_ac5_no_tests_on_base_empty_pass_to_pass
12	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_base_record_missing_refuses,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_base_skipped_refuses,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts
13	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit
14	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac6RerunTest::test_ac6_skipped_on_branch_not_rerun,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac10OrderTest::test_ac10_findings_order_and_one_line_each
15	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_unknown_outcome_refuses,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_timeout_refuses

Прогон №2 (`--patches 16-30`, рабочих процессов auto):

# mutation-run №2 задачи 01M5QAEPC6RF097YQ43T3Y56D9
# источник патчей: каталог на диске
# ревизия прогона: base 579a38199ce682917b9d5e40f15ac95cde4aaddc
# тесты: tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py
# рабочих процессов: auto
# патч 16 mutation-016.diff sha256 9c0b13eca4aa089ce5fe4d5a1c02b827c04b9eb3b0613e3af65e84ac7ddc9225
# патч 17 mutation-017.diff sha256 4923a6f66ee77928cb0866f798912ccaa91cefb99007d125fa54a87aa0655e0f
# патч 18 mutation-018.diff sha256 f5beb1a2e3ba7c35e1322196f5733355c548061cb707f118aeaf28cf3f846942
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
16	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_base_skipped_refuses
17	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red
18	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_skipped_is_red
19	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac2PlaceTest::test_ac2_outcome_refusal_stops_before_review_rework_gate,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac5PassToPassTest::test_ac5_retried_on_base_not_in_pass_to_pass,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_broken_unstable_and_flaky_on_base,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_error_is_red,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_red_kinds,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_skipped_is_red,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_other_file_mandate_does_not_cover,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_one_finding_per_id_senior_kind,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_role_autocommitted_answer_does_not_cover,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_prefix_needs_separator_after_it
20	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_neighbour_red_in_same_file_does_not_redden_rerun,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_unstable_after_change_general_refusal
21	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts
22	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_skipped_is_red,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_neighbour_red_in_same_file_does_not_redden_rerun,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings
23	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_junit_records_findings,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings
24	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_one_finding_per_id_senior_kind
25	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac10OrderTest::test_ac10_findings_order_and_one_line_each
26	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_file_and_prefix_mandate_cover_findings,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_class_prefix_mandate_covers,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_method_prefix_mandate_covers_variants,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_prefix_needs_separator_after_it,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts
27	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_other_file_mandate_does_not_cover
28	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_prefix_needs_separator_after_it
29	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_role_autocommitted_answer_does_not_cover
30	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts

Прогон №3 (`--patches 31-45`, рабочих процессов auto):

# mutation-run №3 задачи 01M5QAEPC6RF097YQ43T3Y56D9
# источник патчей: каталог на диске
# ревизия прогона: base 579a38199ce682917b9d5e40f15ac95cde4aaddc
# тесты: tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py
# рабочих процессов: auto
# патч 31 mutation-031.diff sha256 4e6ad59f035e93bf21c24ab74aa01c3aed56a30a2cdc8860ec2ff510fa1674dd
# патч 32 mutation-032.diff sha256 074d90d53613956c7216709cdeed22f273faee69899e22af51be9eca7f8a408e
# патч 33 mutation-033.diff sha256 949ec6c774d1203cd2f8619e317c779dc84effbcab774e7873e9a47c1eaed763
# патч 34 mutation-034.diff sha256 a88617df8a8e1e38af797c3e8858d7854045c4a650d97d96d27f9612dcd106b2
# патч 35 mutation-035.diff sha256 aaa2f21a7ee88800f7ca4e9397e2991461203ce2d61e0b29926fcfdc46651dbe
# патч 36 mutation-036.diff sha256 ce30df1d9896a128f04f2e647f08090d3c68516407ba3f24b28c48adceb58757
# патч 37 mutation-037.diff sha256 b49eaebf3b1ec8a43fde70dfb9e733284c2e62ad5028c157c0f8c486460af454
# патч 38 mutation-038.diff sha256 1090bd7ed92e428fca217e400a1269b29860aebde1ce58957067c40a4a2b4e7e
# патч 39 mutation-039.diff sha256 270f3f16ddf3a4fdf91c3c6615a13d6d61c02f519b665e7124270feb40883493
# патч 40 mutation-040.diff sha256 cd3653aa5d498fe5ff93d328c9b2e6c254bca5e52b370a06f3152d691543d4dc
# патч 41 mutation-041.diff sha256 4a3f157ba8f210129dc460995bcc46834a7fdf7ccf9b07346b983d9789d23591
# патч 42 mutation-042.diff sha256 00ccb54acf38b92ee53344e6ba70093fdb7e6d6070657ddbaf3144f067f761fd
# патч 43 mutation-043.diff sha256 4c937d5a592ce65224b7b05f80e9c58a6fd1e204e13290dea889b035daa197ab
# патч 44 mutation-044.diff sha256 d0bacb44043caf5aacfe4e5c3a099d61a234d2e83d8104846eb7789e888b361c
# патч 45 mutation-045.diff sha256 e512c9cfbf0b016cddf335c8132cbc08a8884e784cec27ef1329a2035abf3f9c
номер	исход	узлы
31	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac1OutOfBoundsTest::test_ac1_artel_and_test_profile_no_gate
32	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac1OutOfBoundsTest::test_ac1_decide_skip_refusal_and_canary_no_gate
33	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac1OutOfBoundsTest::test_ac1_decide_skip_refusal_and_canary_no_gate
34	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac3RunsTest::test_ac3_full_suite_on_base_and_head_checkouts_fresh
35	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_head_timeout_refuses_naming_head,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac3RunsTest::test_ac3_full_suite_on_base_and_head_checkouts_fresh,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac5PassToPassTest::test_ac5_retried_on_base_not_in_pass_to_pass,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_unknown_outcome_refuses,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_base_record_missing_refuses,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac2PlaceTest::test_ac2_outcome_refusal_stops_before_review_rework_gate,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_preparation_refusals,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_base_timeout_refuses_naming_base,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_head_unknown_refuses_naming_head,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_red_kinds,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_timeout_refuses,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_error_is_red,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_broken_unstable_and_flaky_on_base,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_skipped_is_red,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_base_skipped_refuses,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_unstable_after_change_general_refusal,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_neighbour_red_in_same_file_does_not_redden_rerun,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_junit_records_findings,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_one_finding_per_id_senior_kind,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac10OrderTest::test_ac10_findings_order_and_one_line_each,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_other_file_mandate_does_not_cover,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_prefix_needs_separator_after_it,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac11MandateTest::test_ac11_role_autocommitted_answer_does_not_cover
36	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_git_head_not_read_refuses
37	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_base_timeout_refuses_naming_base
38	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_head_timeout_refuses_naming_head
39	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_head_unknown_refuses_naming_head
40	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_head_unknown_refuses_naming_head
41	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac5PassToPassTest::test_ac5_no_tests_on_base_empty_pass_to_pass
42	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit
43	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit
44	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit
45	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_preparation_refusals

Прогон №4 (`--patches 46-60`, рабочих процессов auto):

# mutation-run №4 задачи 01M5QAEPC6RF097YQ43T3Y56D9
# источник патчей: каталог на диске
# ревизия прогона: base 579a38199ce682917b9d5e40f15ac95cde4aaddc
# тесты: tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py
# рабочих процессов: auto
# патч 46 mutation-046.diff sha256 ef6a09407aa6eea8606fb04a89ca7af83d054e88f86db131a280b3e5d4252d89
# патч 47 mutation-047.diff sha256 fd3a2349e718d875480aec4617513b582e69034ffffdac02d3ca05dbda5e88d9
# патч 48 mutation-048.diff sha256 970acb7df072ef316195675d6bbae5adb1a0490cf76bc231fcb78da958611879
# патч 49 mutation-049.diff sha256 20713c53bad305498233df209f7099ae14e73bf97d29f5f6d7539cd57e754b02
# патч 50 mutation-050.diff sha256 536cd913c4e92a0bb66319669778bf8ef47f7083633be01bc4a6cf4d6fde6873
# патч 51 mutation-051.diff sha256 ffca80b782b6de317e0552d66479ba7ead26ef85d06b9c10cc055ee2bdc73748
# патч 52 mutation-052.diff sha256 66833e578e68110200ba787be58dca22e3165f99ab4d1679c93fa79e9c99ea87
# патч 53 mutation-053.diff sha256 26c10a3041eb5958359d0b5b705a48c331ea3b92162828d871bf2e351590af0d
# патч 54 mutation-054.diff sha256 09a75ab3f0deb05b064b6e19aba747bcc0178724132a81f951e28097552543ce
# патч 55 mutation-055.diff sha256 0b5ad56645de10b2e1c6e931045d072ce23d2ded064dc408baca88944bea0c1e
# патч 56 mutation-056.diff sha256 4260a992e3cb8978058880199ecfa77cd6a36527f1c4c51018ee7b193efd4562
# патч 57 mutation-057.diff sha256 bb3fbb2fb0d3ab07721ac9d4682c62f2658cb6084779ccd817e8d9492d2ef267
# патч 58 mutation-058.diff sha256 3d0dfaf8334cee31ca17effc62b2c728bff12668d0b43d699ebfa1d716a2665f
# патч 59 mutation-059.diff sha256 2035f613642a4244d7407fb5be4b27a9921341f119156e797111ebb7f1ac3895
# патч 60 mutation-060.diff sha256 fc20fa847878674c7866baf11f0c4b15fceba47f9700a6eb3613d218f4f9e614
номер	исход	узлы
46	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_timeout_refuses
47	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_base_record_missing_refuses
48	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red
49	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_skipped_is_red,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings
50	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red
51	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_error_is_red,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal
52	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal
53	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings
54	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings
55	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_junit_records_findings,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings
56	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings
57	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_junit_records_findings,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac10OrderTest::test_ac10_findings_order_and_one_line_each
58	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_junit_records_findings,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac10OrderTest::test_ac10_findings_order_and_one_line_each,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts
59	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac10OrderTest::test_ac10_findings_order_and_one_line_each
60	не убита	

Прогон №5 (`--patches 61-63`, рабочих процессов auto):

# mutation-run №5 задачи 01M5QAEPC6RF097YQ43T3Y56D9
# источник патчей: каталог на диске
# ревизия прогона: base 579a38199ce682917b9d5e40f15ac95cde4aaddc
# тесты: tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py
# рабочих процессов: auto
# патч 61 mutation-061.diff sha256 bddfcdd66fe43489dbd5a92ae124ae39f60d175eebf5e045b9e5ddc1e525bfa4
# патч 62 mutation-062.diff sha256 f608e8c1f74ebae512dc445b0b31ef5ba79e387a1c4ca2dbb59d9510264f20f7
# патч 63 mutation-063.diff sha256 56ba94d659816cd2c23443d735ff75290093cf43ce724dfde59545bcc27ccbf4
номер	исход	узлы
61	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac10OrderTest::test_ac10_findings_order_and_one_line_each,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings
62	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts
63	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts

Прогон №6 (`--patches 6-15`, рабочих процессов auto):

# mutation-run №6 задачи 01M5QAEPC6RF097YQ43T3Y56D9
# источник патчей: каталог на диске
# ревизия прогона: base 579a38199ce682917b9d5e40f15ac95cde4aaddc
# тесты: tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py
# рабочих процессов: auto
# патч 6 mutation-006.diff sha256 ecddcca1e529f5422c1a3be8e91b5f1b62b1f16943a359fe70d07509f2ec7fd1
# патч 7 mutation-007.diff sha256 cf260f676e9892d12f043184fd79ffd86e4fb786ebc39f3ffe955b72f8276e52
# патч 8 mutation-008.diff sha256 8034c4c11922820ec78b3465631012eeb3bb3ccd3842cff65cecea85794092c5
# патч 9 mutation-009.diff sha256 2cd39c6d46590a94aa7122a105e849d833c2fcda7e2caff54c486483164019a4
# патч 10 mutation-010.diff sha256 a037e744c087fde4046a7a4332ca28a028502150d6d5a9e54dad642e389040ac
# патч 11 mutation-011.diff sha256 7015d4d8dfcf958801c643fe866b1cf608cc6f6cfba90d6db613c772536f37f6
# патч 12 mutation-012.diff sha256 cfed6f7cf3f12fede296705dc923db40c524d93179aa672881e6df1d8153da95
# патч 13 mutation-013.diff sha256 e608442ca012377afd586dab356cf456f27c6a1478bae8f2f4fa81d40b2ecfc4
# патч 14 mutation-014.diff sha256 48978860d259c827829b351e91839d513d6b1d7541fa8ea044e3869c23de52be
# патч 15 mutation-015.diff sha256 ba5684145e17c7f0aa540c39fb344cd7a464c5d38811e9178a1559f9e5474d06
номер	исход	узлы
6	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_git_preparation_failures_refuse
7	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_git_head_checkout_failure_refuses,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_git_base_checkout_failure_refuses
8	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side
9	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_head_timeout_refuses_naming_head,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_base_timeout_refuses_naming_base,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac4PrepareTest::test_ac4_side_head_unknown_refuses_naming_head
10	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac5PassToPassTest::test_ac5_retried_on_base_not_in_pass_to_pass,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red
11	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac5PassToPassTest::test_ac5_no_tests_on_base_empty_pass_to_pass
12	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_base_record_missing_refuses,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_base_skipped_refuses,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts
13	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit
14	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac6RerunTest::test_ac6_skipped_on_branch_not_rerun,tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac10OrderTest::test_ac10_findings_order_and_one_line_each
15	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac7RerunPrepareTest::test_ac7_rerun_unknown_outcome_refuses

Прогон №7 (`--patches 31-31`, рабочих процессов auto):

# mutation-run №7 задачи 01M5QAEPC6RF097YQ43T3Y56D9
# источник патчей: каталог на диске
# ревизия прогона: base 579a38199ce682917b9d5e40f15ac95cde4aaddc
# тесты: tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py
# рабочих процессов: auto
# патч 31 mutation-031.diff sha256 e5b643ac1e5d0a4d8f9767da17847ff5433f9bc153b3407d585e98e5afd5b9ae
номер	исход	узлы
31	убита	tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::Ac1OutOfBoundsTest::test_ac1_artel_and_test_profile_no_gate

## Мутации после

Вывод `mutation-run --wait` каждой части дословно (шапка и все строки),
`--ref worktree`, тесты — `tests/test_outcome_gate_module.py`, рабочих
процессов — `auto`, те же части 1-15, 16-30, 31-45, 46-60, 61-63.

Прогон №8 (`--patches 1-15`, рабочих процессов auto). Перед стартом части `git status --porcelain -- orchestrator/` рабочей копии — пустой вывод.

# mutation-run №8 задачи 01M5QAEPC6RF097YQ43T3Y56D9
# источник патчей: каталог на диске
# ревизия прогона: worktree 9b29a735590fcc4ab2799ae3a0678dca7831ef2c
# тесты: tests/test_outcome_gate_module.py
# рабочих процессов: auto
# патч 1 mutation-001.diff sha256 7e8c5ff9839d64211fe5742a4533275e2b8e4e2b4b10d76879a80c7e57718173
# патч 2 mutation-002.diff sha256 45762ddbf2cac2eedaaf53c9c0e54c2edb6abb34735216bb77b8e8a2d9207fc3
# патч 3 mutation-003.diff sha256 1781b115337f29162e78febd5ab4736f32240d768424d259c78aafc0afa0934c
# патч 4 mutation-004.diff sha256 2a59d597363167fdc681eb55aff45908093d9c587437646c74f609a33499cc14
# патч 5 mutation-005.diff sha256 8dcd99b2aabe2cd5b6bd68e228977608a3eec991461de0e5f6e65ef02b5bd4a4
# патч 6 mutation-006.diff sha256 ecddcca1e529f5422c1a3be8e91b5f1b62b1f16943a359fe70d07509f2ec7fd1
# патч 7 mutation-007.diff sha256 cf260f676e9892d12f043184fd79ffd86e4fb786ebc39f3ffe955b72f8276e52
# патч 8 mutation-008.diff sha256 8034c4c11922820ec78b3465631012eeb3bb3ccd3842cff65cecea85794092c5
# патч 9 mutation-009.diff sha256 2cd39c6d46590a94aa7122a105e849d833c2fcda7e2caff54c486483164019a4
# патч 10 mutation-010.diff sha256 a037e744c087fde4046a7a4332ca28a028502150d6d5a9e54dad642e389040ac
# патч 11 mutation-011.diff sha256 7015d4d8dfcf958801c643fe866b1cf608cc6f6cfba90d6db613c772536f37f6
# патч 12 mutation-012.diff sha256 cfed6f7cf3f12fede296705dc923db40c524d93179aa672881e6df1d8153da95
# патч 13 mutation-013.diff sha256 e608442ca012377afd586dab356cf456f27c6a1478bae8f2f4fa81d40b2ecfc4
# патч 14 mutation-014.diff sha256 48978860d259c827829b351e91839d513d6b1d7541fa8ea044e3869c23de52be
# патч 15 mutation-015.diff sha256 ba5684145e17c7f0aa540c39fb344cd7a464c5d38811e9178a1559f9e5474d06
номер	исход	узлы
1	убита	tests/test_outcome_gate_module.py::test_ac1_artel_and_test_profile_no_gate
2	убита	tests/test_outcome_gate_module.py::test_ac1_decide_skip_refusal_and_canary_no_gate
3	убита	tests/test_outcome_gate_module.py::test_ac5_retried_on_base_not_in_pass_to_pass,tests/test_outcome_gate_module.py::test_ac5_no_tests_on_base_empty_pass_to_pass,tests/test_outcome_gate_module.py::test_ac2_text_gate_refusal_first_no_outcome_runs,tests/test_outcome_gate_module.py::test_ac3_full_suite_on_base_and_head_checkouts_fresh,tests/test_outcome_gate_module.py::test_ac13_passed_gate_journal_counts
4	убита	tests/test_outcome_gate_module.py::test_ac2_outcome_refusal_stops_before_review_rework_gate
5	убита	tests/test_outcome_gate_module.py::test_ac3_full_suite_on_base_and_head_checkouts_fresh
6	убита	tests/test_outcome_gate_module.py::test_ac4_git_preparation_failures_refuse
7	убита	tests/test_outcome_gate_module.py::test_ac4_git_base_checkout_failure_refuses,tests/test_outcome_gate_module.py::test_ac4_git_head_checkout_failure_refuses
8	убита	tests/test_outcome_gate_module.py::test_ac4_side_not_started_or_timeout_refuses_naming_side
9	убита	tests/test_outcome_gate_module.py::test_ac4_side_base_timeout_refuses_naming_base,tests/test_outcome_gate_module.py::test_ac4_side_not_started_or_timeout_refuses_naming_side,tests/test_outcome_gate_module.py::test_ac4_side_head_timeout_refuses_naming_head,tests/test_outcome_gate_module.py::test_ac4_side_head_unknown_refuses_naming_head
10	убита	tests/test_outcome_gate_module.py::test_ac5_retried_on_base_not_in_pass_to_pass,tests/test_outcome_gate_module.py::test_retried_pass_on_base_not_in_pass_to_pass,tests/test_outcome_gate_module.py::test_ac7_branch_rerun_retried_is_red
11	убита	tests/test_outcome_gate_module.py::test_ac5_no_tests_on_base_empty_pass_to_pass
12	убита	tests/test_outcome_gate_module.py::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit,tests/test_outcome_gate_module.py::test_ac7_rerun_base_skipped_refuses,tests/test_outcome_gate_module.py::test_ac7_rerun_base_record_missing_refuses,tests/test_outcome_gate_module.py::test_ac8_flaky_on_base_no_refusal,tests/test_outcome_gate_module.py::test_ac13_passed_gate_journal_counts
13	убита	tests/test_outcome_gate_module.py::test_red_on_branch_kinds,tests/test_outcome_gate_module.py::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit
14	убита	tests/test_outcome_gate_module.py::test_red_on_branch_kinds,tests/test_outcome_gate_module.py::test_ac11_role_autocommitted_id_mandate_does_not_cover,tests/test_outcome_gate_module.py::test_ac13_refusal_hint_names_both_markers,tests/test_outcome_gate_module.py::test_ac12_exact_id_with_n_covers_other_variant_does_not,tests/test_outcome_gate_module.py::test_ac10_findings_order_and_one_line_each,tests/test_outcome_gate_module.py::test_ac6_skipped_on_branch_not_rerun
15	убита	tests/test_outcome_gate_module.py::test_ac7_rerun_unknown_outcome_refuses

## Строки падений

Строка падения — файл:строка упавшего утверждения из лога прогона патча
(`<id>-mutation-run-<n>-p<nnn>.log`, раздел FAILURES, нижний кадр
`tests/…`). «До» — по исходному файлу и песочнице на базе, «после» — по
`tests/test_outcome_gate_module.py`: утверждение функции, в которую
перенесён убивший «до» тест, или помощника исхода.

- mutation-001 «до»: `Ac1OutOfBoundsTest::test_ac1_artel_and_test_profile_no_gate` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:60`
- mutation-001 «после»: `test_outcome_gate_module.py::test_ac1_artel_and_test_profile_no_gate` — `tests/test_outcome_gate_module.py:833`
- mutation-002 «до»: `Ac1OutOfBoundsTest::test_ac1_decide_skip_refusal_and_canary_no_gate` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:60`
- mutation-002 «после»: `test_outcome_gate_module.py::test_ac1_decide_skip_refusal_and_canary_no_gate` — `tests/test_outcome_gate_module.py:833`
- mutation-003 «до»: `Ac3RunsTest::test_ac3_full_suite_on_base_and_head_checkouts_fresh` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:256`
- mutation-003 «до»: `Ac5PassToPassTest::test_ac5_retried_on_base_not_in_pass_to_pass` — `tests/outcome_gate_sandbox.py:837`
- mutation-003 «до»: `Ac5PassToPassTest::test_ac5_no_tests_on_base_empty_pass_to_pass` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:665`
- mutation-003 «до»: `Ac2PlaceTest::test_ac2_text_gate_refusal_first_no_outcome_runs` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:178`
- mutation-003 «до»: `Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts` — `tests/outcome_gate_sandbox.py:837`
- mutation-003 «после»: `test_outcome_gate_module.py::test_ac5_retried_on_base_not_in_pass_to_pass` — `tests/test_outcome_gate_module.py:828`
- mutation-003 «после»: `test_outcome_gate_module.py::test_ac5_no_tests_on_base_empty_pass_to_pass` — `tests/test_outcome_gate_module.py:1455`
- mutation-003 «после»: `test_outcome_gate_module.py::test_ac2_text_gate_refusal_first_no_outcome_runs` — `tests/test_outcome_gate_module.py:991`
- mutation-003 «после»: `test_outcome_gate_module.py::test_ac3_full_suite_on_base_and_head_checkouts_fresh` — `tests/test_outcome_gate_module.py:1067`
- mutation-003 «после»: `test_outcome_gate_module.py::test_ac13_passed_gate_journal_counts` — `tests/test_outcome_gate_module.py:828`
- mutation-004 «до»: `Ac2PlaceTest::test_ac2_outcome_refusal_stops_before_review_rework_gate` — `tests/outcome_gate_sandbox.py:824`
- mutation-004 «после»: `test_outcome_gate_module.py::test_ac2_outcome_refusal_stops_before_review_rework_gate` — `tests/test_outcome_gate_module.py:818`
- mutation-005 «до»: `Ac3RunsTest::test_ac3_full_suite_on_base_and_head_checkouts_fresh` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:257`
- mutation-005 «после»: `test_outcome_gate_module.py::test_ac3_full_suite_on_base_and_head_checkouts_fresh` — `tests/test_outcome_gate_module.py:1068`
- mutation-006 «до»: `Ac4PrepareTest::test_ac4_git_preparation_failures_refuse` — `tests/outcome_gate_sandbox.py:824`
- mutation-006 «после»: `test_outcome_gate_module.py::test_ac4_git_preparation_failures_refuse` — `tests/test_outcome_gate_module.py:818`
- mutation-007 «до»: `Ac4PrepareTest::test_ac4_git_head_checkout_failure_refuses` — `tests/outcome_gate_sandbox.py:824`
- mutation-007 «до»: `Ac4PrepareTest::test_ac4_git_base_checkout_failure_refuses` — `tests/outcome_gate_sandbox.py:824`
- mutation-007 «после»: `test_outcome_gate_module.py::test_ac4_git_base_checkout_failure_refuses` — `tests/test_outcome_gate_module.py:818`
- mutation-007 «после»: `test_outcome_gate_module.py::test_ac4_git_head_checkout_failure_refuses` — `tests/test_outcome_gate_module.py:818`
- mutation-008 «до»: `Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side` — `tests/outcome_gate_sandbox.py:824`
- mutation-008 «после»: `test_outcome_gate_module.py::test_ac4_side_not_started_or_timeout_refuses_naming_side` — `tests/test_outcome_gate_module.py:818`
- mutation-009 «до»: `Ac4PrepareTest::test_ac4_side_head_timeout_refuses_naming_head` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:294`
- mutation-009 «до»: `Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:294`
- mutation-009 «до»: `Ac4PrepareTest::test_ac4_side_base_timeout_refuses_naming_base` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:294`
- mutation-009 «до»: `Ac4PrepareTest::test_ac4_side_head_unknown_refuses_naming_head` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:294`
- mutation-009 «после»: `test_outcome_gate_module.py::test_ac4_side_base_timeout_refuses_naming_base` — `tests/test_outcome_gate_module.py:859`
- mutation-009 «после»: `test_outcome_gate_module.py::test_ac4_side_not_started_or_timeout_refuses_naming_side` — `tests/test_outcome_gate_module.py:859`
- mutation-009 «после»: `test_outcome_gate_module.py::test_ac4_side_head_timeout_refuses_naming_head` — `tests/test_outcome_gate_module.py:859`
- mutation-009 «после»: `test_outcome_gate_module.py::test_ac4_side_head_unknown_refuses_naming_head` — `tests/test_outcome_gate_module.py:859`
- mutation-010 «до»: `Ac5PassToPassTest::test_ac5_retried_on_base_not_in_pass_to_pass` — `tests/outcome_gate_sandbox.py:837`
- mutation-010 «до»: `Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red` — `tests/outcome_gate_sandbox.py:824`
- mutation-010 «после»: `test_outcome_gate_module.py::test_ac5_retried_on_base_not_in_pass_to_pass` — `tests/test_outcome_gate_module.py:828`
- mutation-010 «после»: `test_outcome_gate_module.py::test_retried_pass_on_base_not_in_pass_to_pass` — `tests/test_outcome_gate_module.py:672`
- mutation-010 «после»: `test_outcome_gate_module.py::test_ac7_branch_rerun_retried_is_red` — `tests/test_outcome_gate_module.py:818`
- mutation-011 «до»: `Ac5PassToPassTest::test_ac5_no_tests_on_base_empty_pass_to_pass` — `tests/outcome_gate_sandbox.py:837`
- mutation-011 «после»: `test_outcome_gate_module.py::test_ac5_no_tests_on_base_empty_pass_to_pass` — `tests/test_outcome_gate_module.py:828`
- mutation-012 «до»: `Ac7RerunPrepareTest::test_ac7_rerun_base_record_missing_refuses` — `tests/outcome_gate_sandbox.py:824`
- mutation-012 «до»: `Ac7RerunPrepareTest::test_ac7_rerun_base_skipped_refuses` — `tests/outcome_gate_sandbox.py:824`
- mutation-012 «до»: `Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal` — `tests/outcome_gate_sandbox.py:837`
- mutation-012 «до»: `Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:706`
- mutation-012 «до»: `Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts` — `tests/outcome_gate_sandbox.py:837`
- mutation-012 «после»: `test_outcome_gate_module.py::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit` — `tests/test_outcome_gate_module.py:1495`
- mutation-012 «после»: `test_outcome_gate_module.py::test_ac7_rerun_base_skipped_refuses` — `tests/test_outcome_gate_module.py:818`
- mutation-012 «после»: `test_outcome_gate_module.py::test_ac7_rerun_base_record_missing_refuses` — `tests/test_outcome_gate_module.py:818`
- mutation-012 «после»: `test_outcome_gate_module.py::test_ac8_flaky_on_base_no_refusal` — `tests/test_outcome_gate_module.py:828`
- mutation-012 «после»: `test_outcome_gate_module.py::test_ac13_passed_gate_journal_counts` — `tests/test_outcome_gate_module.py:828`
- mutation-013 «до»: `Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:706`
- mutation-013 «после»: `test_outcome_gate_module.py::test_red_on_branch_kinds` — `tests/test_outcome_gate_module.py:692`
- mutation-013 «после»: `test_outcome_gate_module.py::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit` — `tests/test_outcome_gate_module.py:1495`
- mutation-014 «до»: `Ac6RerunTest::test_ac6_skipped_on_branch_not_rerun` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:726`
- mutation-014 «до»: `Ac10OrderTest::test_ac10_findings_order_and_one_line_each` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1409`
- mutation-014 «после»: `test_outcome_gate_module.py::test_red_on_branch_kinds` — `tests/test_outcome_gate_module.py:692`
- mutation-014 «после»: `test_outcome_gate_module.py::test_ac11_role_autocommitted_id_mandate_does_not_cover` — `tests/test_outcome_gate_module.py:560`
- mutation-014 «после»: `test_outcome_gate_module.py::test_ac13_refusal_hint_names_both_markers` — `tests/test_outcome_gate_module.py:560`
- mutation-014 «после»: `test_outcome_gate_module.py::test_ac12_exact_id_with_n_covers_other_variant_does_not` — `tests/test_outcome_gate_module.py:560`
- mutation-014 «после»: `test_outcome_gate_module.py::test_ac10_findings_order_and_one_line_each` — `tests/test_outcome_gate_module.py:2189`
- mutation-014 «после»: `test_outcome_gate_module.py::test_ac6_skipped_on_branch_not_rerun` — `tests/test_outcome_gate_module.py:1516`
- mutation-015 «до»: `Ac7RerunPrepareTest::test_ac7_rerun_unknown_outcome_refuses` — `tests/outcome_gate_sandbox.py:824`
- mutation-015 «после»: `test_outcome_gate_module.py::test_ac7_rerun_unknown_outcome_refuses` — `tests/test_outcome_gate_module.py:818`
- mutation-016 «до»: `Ac7RerunPrepareTest::test_ac7_rerun_base_skipped_refuses` — `tests/outcome_gate_sandbox.py:824`
- mutation-017 «до»: `Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red` — `tests/outcome_gate_sandbox.py:824`
- mutation-018 «до»: `Ac7RerunPrepareTest::test_ac7_branch_rerun_skipped_is_red` — `tests/outcome_gate_sandbox.py:824`
- mutation-019 «до»: `Ac2PlaceTest::test_ac2_outcome_refusal_stops_before_review_rework_gate` — `tests/outcome_gate_sandbox.py:824`
- mutation-019 «до»: `Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red` — `tests/outcome_gate_sandbox.py:824`
- mutation-019 «до»: `Ac5PassToPassTest::test_ac5_retried_on_base_not_in_pass_to_pass` — `tests/outcome_gate_sandbox.py:824`
- mutation-019 «до»: `Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red` — `tests/outcome_gate_sandbox.py:824`
- mutation-019 «до»: `Ac8VerdictByRecordTest::test_ac8_broken_unstable_and_flaky_on_base` — `tests/outcome_gate_sandbox.py:824`
- mutation-019 «до»: `Ac7RerunPrepareTest::test_ac7_branch_rerun_error_is_red` — `tests/outcome_gate_sandbox.py:824`
- mutation-019 «до»: `Ac7RerunPrepareTest::test_ac7_branch_rerun_red_kinds` — `tests/outcome_gate_sandbox.py:824`
- mutation-019 «до»: `Ac7RerunPrepareTest::test_ac7_branch_rerun_skipped_is_red` — `tests/outcome_gate_sandbox.py:824`
- mutation-019 «до»: `Ac11MandateTest::test_ac11_other_file_mandate_does_not_cover` — `tests/outcome_gate_sandbox.py:824`
- mutation-019 «до»: `Ac9CompareTest::test_ac9_one_finding_per_id_senior_kind` — `tests/outcome_gate_sandbox.py:824`
- mutation-019 «до»: `Ac11MandateTest::test_ac11_role_autocommitted_answer_does_not_cover` — `tests/outcome_gate_sandbox.py:824`
- mutation-019 «до»: `Ac11MandateTest::test_ac11_prefix_needs_separator_after_it` — `tests/outcome_gate_sandbox.py:824`
- mutation-020 «до»: `Ac8VerdictByRecordTest::test_ac8_neighbour_red_in_same_file_does_not_redden_rerun` — `tests/outcome_gate_sandbox.py:824`
- mutation-020 «до»: `Ac8VerdictByRecordTest::test_ac8_unstable_after_change_general_refusal` — `tests/outcome_gate_sandbox.py:824`
- mutation-021 «до»: `Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal` — `tests/outcome_gate_sandbox.py:837`
- mutation-021 «до»: `Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts` — `tests/outcome_gate_sandbox.py:837`
- mutation-022 «до»: `Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red` — `tests/outcome_gate_sandbox.py:824`
- mutation-022 «до»: `Ac7RerunPrepareTest::test_ac7_branch_rerun_skipped_is_red` — `tests/outcome_gate_sandbox.py:824`
- mutation-022 «до»: `Ac8VerdictByRecordTest::test_ac8_neighbour_red_in_same_file_does_not_redden_rerun` — `tests/outcome_gate_sandbox.py:824`
- mutation-022 «до»: `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1286`
- mutation-023 «до»: `Ac9CompareTest::test_ac9_junit_records_findings` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1328`
- mutation-023 «до»: `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1286`
- mutation-024 «до»: `Ac9CompareTest::test_ac9_one_finding_per_id_senior_kind` — `tests/outcome_gate_sandbox.py:824`
- mutation-025 «до»: `Ac10OrderTest::test_ac10_findings_order_and_one_line_each` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1409`
- mutation-026 «до»: `Ac11MandateTest::test_ac11_file_and_prefix_mandate_cover_findings` — `tests/outcome_gate_sandbox.py:837`
- mutation-026 «до»: `Ac11MandateTest::test_ac11_class_prefix_mandate_covers` — `tests/outcome_gate_sandbox.py:837`
- mutation-026 «до»: `Ac11MandateTest::test_ac11_method_prefix_mandate_covers_variants` — `tests/outcome_gate_sandbox.py:837`
- mutation-026 «до»: `Ac11MandateTest::test_ac11_prefix_needs_separator_after_it` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1576`
- mutation-026 «до»: `Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts` — `tests/outcome_gate_sandbox.py:837`
- mutation-027 «до»: `Ac11MandateTest::test_ac11_other_file_mandate_does_not_cover` — `tests/outcome_gate_sandbox.py:824`
- mutation-028 «до»: `Ac11MandateTest::test_ac11_prefix_needs_separator_after_it` — `tests/outcome_gate_sandbox.py:824`
- mutation-029 «до»: `Ac11MandateTest::test_ac11_role_autocommitted_answer_does_not_cover` — `tests/outcome_gate_sandbox.py:824`
- mutation-030 «до»: `Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1641`
- mutation-031 «до»: `Ac1OutOfBoundsTest::test_ac1_artel_and_test_profile_no_gate` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:60`
- mutation-032 «до»: `Ac1OutOfBoundsTest::test_ac1_decide_skip_refusal_and_canary_no_gate` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:61`
- mutation-033 «до»: `Ac1OutOfBoundsTest::test_ac1_decide_skip_refusal_and_canary_no_gate` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:60`
- mutation-034 «до»: `Ac3RunsTest::test_ac3_full_suite_on_base_and_head_checkouts_fresh` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:262`
- mutation-035 «до»: `Ac4PrepareTest::test_ac4_side_head_timeout_refuses_naming_head` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:294`
- mutation-035 «до»: `Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac3RunsTest::test_ac3_full_suite_on_base_and_head_checkouts_fresh` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:258`
- mutation-035 «до»: `Ac5PassToPassTest::test_ac5_retried_on_base_not_in_pass_to_pass` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac7RerunPrepareTest::test_ac7_rerun_unknown_outcome_refuses` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac7RerunPrepareTest::test_ac7_rerun_base_record_missing_refuses` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac2PlaceTest::test_ac2_outcome_refusal_stops_before_review_rework_gate` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac7RerunPrepareTest::test_ac7_rerun_preparation_refusals` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac4PrepareTest::test_ac4_side_base_timeout_refuses_naming_base` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac4PrepareTest::test_ac4_side_head_unknown_refuses_naming_head` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:294`
- mutation-035 «до»: `Ac7RerunPrepareTest::test_ac7_branch_rerun_red_kinds` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac7RerunPrepareTest::test_ac7_rerun_timeout_refuses` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac7RerunPrepareTest::test_ac7_branch_rerun_error_is_red` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac8VerdictByRecordTest::test_ac8_broken_unstable_and_flaky_on_base` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac7RerunPrepareTest::test_ac7_branch_rerun_skipped_is_red` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac7RerunPrepareTest::test_ac7_rerun_base_skipped_refuses` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1206`
- mutation-035 «до»: `Ac8VerdictByRecordTest::test_ac8_unstable_after_change_general_refusal` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac8VerdictByRecordTest::test_ac8_neighbour_red_in_same_file_does_not_redden_rerun` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac9CompareTest::test_ac9_junit_records_findings` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac9CompareTest::test_ac9_one_finding_per_id_senior_kind` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:706`
- mutation-035 «до»: `Ac10OrderTest::test_ac10_findings_order_and_one_line_each` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac11MandateTest::test_ac11_other_file_mandate_does_not_cover` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac11MandateTest::test_ac11_prefix_needs_separator_after_it` — `tests/outcome_gate_sandbox.py:824`
- mutation-035 «до»: `Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1641`
- mutation-035 «до»: `Ac11MandateTest::test_ac11_role_autocommitted_answer_does_not_cover` — `tests/outcome_gate_sandbox.py:824`
- mutation-036 «до»: `Ac4PrepareTest::test_ac4_git_head_not_read_refuses` — `tests/outcome_gate_sandbox.py:824`
- mutation-037 «до»: `Ac4PrepareTest::test_ac4_side_base_timeout_refuses_naming_base` — `tests/outcome_gate_sandbox.py:824`
- mutation-038 «до»: `Ac4PrepareTest::test_ac4_side_head_timeout_refuses_naming_head` — `tests/outcome_gate_sandbox.py:824`
- mutation-039 «до»: `Ac4PrepareTest::test_ac4_side_head_unknown_refuses_naming_head` — `tests/outcome_gate_sandbox.py:824`
- mutation-040 «до»: `Ac4PrepareTest::test_ac4_side_head_unknown_refuses_naming_head` — `tests/outcome_gate_sandbox.py:824`
- mutation-041 «до»: `Ac5PassToPassTest::test_ac5_no_tests_on_base_empty_pass_to_pass` — `tests/outcome_gate_sandbox.py:837`
- mutation-042 «до»: `Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:708`
- mutation-043 «до»: `Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:709`
- mutation-044 «до»: `Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:709`
- mutation-045 «до»: `Ac7RerunPrepareTest::test_ac7_rerun_preparation_refusals` — `tests/outcome_gate_sandbox.py:824`
- mutation-046 «до»: `Ac7RerunPrepareTest::test_ac7_rerun_timeout_refuses` — `tests/outcome_gate_sandbox.py:824`
- mutation-047 «до»: `Ac7RerunPrepareTest::test_ac7_rerun_base_record_missing_refuses` — `tests/outcome_gate_sandbox.py:824`
- mutation-048 «до»: `Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red` — `tests/outcome_gate_sandbox.py:824`
- mutation-049 «до»: `Ac7RerunPrepareTest::test_ac7_branch_rerun_skipped_is_red` — `tests/outcome_gate_sandbox.py:824`
- mutation-049 «до»: `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings` — `tests/outcome_gate_sandbox.py:824`
- mutation-050 «до»: `Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red` — `tests/outcome_gate_sandbox.py:824`
- mutation-051 «до»: `Ac7RerunPrepareTest::test_ac7_branch_rerun_error_is_red` — `tests/outcome_gate_sandbox.py:824`
- mutation-051 «до»: `Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal` — `tests/outcome_gate_sandbox.py:837`
- mutation-052 «до»: `Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1206`
- mutation-053 «до»: `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1291`
- mutation-054 «до»: `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1291`
- mutation-055 «до»: `Ac9CompareTest::test_ac9_junit_records_findings` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1330`
- mutation-055 «до»: `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1286`
- mutation-056 «до»: `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1286`
- mutation-057 «до»: `Ac9CompareTest::test_ac9_junit_records_findings` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1328`
- mutation-057 «до»: `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1286`
- mutation-057 «до»: `Ac10OrderTest::test_ac10_findings_order_and_one_line_each` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1405`
- mutation-058 «до»: `Ac9CompareTest::test_ac9_junit_records_findings` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1328`
- mutation-058 «до»: `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1289`
- mutation-058 «до»: `Ac10OrderTest::test_ac10_findings_order_and_one_line_each` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1405`
- mutation-058 «до»: `Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1641`
- mutation-059 «до»: `Ac10OrderTest::test_ac10_findings_order_and_one_line_each` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1409`
- mutation-061 «до»: `Ac10OrderTest::test_ac10_findings_order_and_one_line_each` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1407`
- mutation-061 «до»: `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1296`
- mutation-062 «до»: `Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1206`
- mutation-062 «до»: `Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1641`
- mutation-063 «до»: `Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts` — `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1641`

## Соответствие имён «до → после»

Каждый тест исходного файла перенесён в функцию модуля с тем же именем.

- `Ac1OutOfBoundsTest::test_ac1_artel_and_test_profile_no_gate` → `test_outcome_gate_module.py::test_ac1_artel_and_test_profile_no_gate`
- `Ac1OutOfBoundsTest::test_ac1_decide_skip_refusal_and_canary_no_gate` → `test_outcome_gate_module.py::test_ac1_decide_skip_refusal_and_canary_no_gate`
- `Ac2PlaceTest::test_ac2_text_gate_refusal_first_no_outcome_runs` → `test_outcome_gate_module.py::test_ac2_text_gate_refusal_first_no_outcome_runs`
- `Ac2PlaceTest::test_ac2_outcome_refusal_stops_before_review_rework_gate` → `test_outcome_gate_module.py::test_ac2_outcome_refusal_stops_before_review_rework_gate`
- `Ac3RunsTest::test_ac3_full_suite_on_base_and_head_checkouts_fresh` → `test_outcome_gate_module.py::test_ac3_full_suite_on_base_and_head_checkouts_fresh`
- `Ac4PrepareTest::test_ac4_git_preparation_failures_refuse` → `test_outcome_gate_module.py::test_ac4_git_preparation_failures_refuse`
- `Ac4PrepareTest::test_ac4_git_head_not_read_refuses` → `test_outcome_gate_module.py::test_ac4_git_head_not_read_refuses`
- `Ac4PrepareTest::test_ac4_git_base_checkout_failure_refuses` → `test_outcome_gate_module.py::test_ac4_git_base_checkout_failure_refuses`
- `Ac4PrepareTest::test_ac4_git_head_checkout_failure_refuses` → `test_outcome_gate_module.py::test_ac4_git_head_checkout_failure_refuses`
- `Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side` → `test_outcome_gate_module.py::test_ac4_side_not_started_or_timeout_refuses_naming_side`
- `Ac4PrepareTest::test_ac4_side_head_unknown_refuses_naming_head` → `test_outcome_gate_module.py::test_ac4_side_head_unknown_refuses_naming_head`
- `Ac4PrepareTest::test_ac4_side_base_timeout_refuses_naming_base` → `test_outcome_gate_module.py::test_ac4_side_base_timeout_refuses_naming_base`
- `Ac4PrepareTest::test_ac4_side_head_timeout_refuses_naming_head` → `test_outcome_gate_module.py::test_ac4_side_head_timeout_refuses_naming_head`
- `Ac5PassToPassTest::test_ac5_retried_on_base_not_in_pass_to_pass` → `test_outcome_gate_module.py::test_ac5_retried_on_base_not_in_pass_to_pass`
- `Ac5PassToPassTest::test_ac5_no_tests_on_base_empty_pass_to_pass` → `test_outcome_gate_module.py::test_ac5_no_tests_on_base_empty_pass_to_pass`
- `Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit` → `test_outcome_gate_module.py::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit`
- `Ac6RerunTest::test_ac6_skipped_on_branch_not_rerun` → `test_outcome_gate_module.py::test_ac6_skipped_on_branch_not_rerun`
- `Ac7RerunPrepareTest::test_ac7_rerun_preparation_refusals` → `test_outcome_gate_module.py::test_ac7_rerun_preparation_refusals`
- `Ac7RerunPrepareTest::test_ac7_rerun_unknown_outcome_refuses` → `test_outcome_gate_module.py::test_ac7_rerun_unknown_outcome_refuses`
- `Ac7RerunPrepareTest::test_ac7_rerun_timeout_refuses` → `test_outcome_gate_module.py::test_ac7_rerun_timeout_refuses`
- `Ac7RerunPrepareTest::test_ac7_rerun_base_skipped_refuses` → `test_outcome_gate_module.py::test_ac7_rerun_base_skipped_refuses`
- `Ac7RerunPrepareTest::test_ac7_rerun_base_record_missing_refuses` → `test_outcome_gate_module.py::test_ac7_rerun_base_record_missing_refuses`
- `Ac7RerunPrepareTest::test_ac7_branch_rerun_red_kinds` → `test_outcome_gate_module.py::test_ac7_branch_rerun_red_kinds`
- `Ac7RerunPrepareTest::test_ac7_branch_rerun_error_is_red` → `test_outcome_gate_module.py::test_ac7_branch_rerun_error_is_red`
- `Ac7RerunPrepareTest::test_ac7_branch_rerun_skipped_is_red` → `test_outcome_gate_module.py::test_ac7_branch_rerun_skipped_is_red`
- `Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red` → `test_outcome_gate_module.py::test_ac7_branch_rerun_missing_is_red`
- `Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red` → `test_outcome_gate_module.py::test_ac7_branch_rerun_retried_is_red`
- `Ac8VerdictByRecordTest::test_ac8_broken_unstable_and_flaky_on_base` → `test_outcome_gate_module.py::test_ac8_broken_unstable_and_flaky_on_base`
- `Ac8VerdictByRecordTest::test_ac8_unstable_after_change_general_refusal` → `test_outcome_gate_module.py::test_ac8_unstable_after_change_general_refusal`
- `Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal` → `test_outcome_gate_module.py::test_ac8_flaky_on_base_no_refusal`
- `Ac8VerdictByRecordTest::test_ac8_neighbour_red_in_same_file_does_not_redden_rerun` → `test_outcome_gate_module.py::test_ac8_neighbour_red_in_same_file_does_not_redden_rerun`
- `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings` → `test_outcome_gate_module.py::test_ac9_vitest_records_findings_and_non_findings`
- `Ac9CompareTest::test_ac9_junit_records_findings` → `test_outcome_gate_module.py::test_ac9_junit_records_findings`
- `Ac9CompareTest::test_ac9_one_finding_per_id_senior_kind` → `test_outcome_gate_module.py::test_ac9_one_finding_per_id_senior_kind`
- `Ac10OrderTest::test_ac10_findings_order_and_one_line_each` → `test_outcome_gate_module.py::test_ac10_findings_order_and_one_line_each`
- `Ac11MandateTest::test_ac11_file_and_prefix_mandate_cover_findings` → `test_outcome_gate_module.py::test_ac11_file_and_prefix_mandate_cover_findings`
- `Ac11MandateTest::test_ac11_class_prefix_mandate_covers` → `test_outcome_gate_module.py::test_ac11_class_prefix_mandate_covers`
- `Ac11MandateTest::test_ac11_method_prefix_mandate_covers_variants` → `test_outcome_gate_module.py::test_ac11_method_prefix_mandate_covers_variants`
- `Ac11MandateTest::test_ac11_other_file_mandate_does_not_cover` → `test_outcome_gate_module.py::test_ac11_other_file_mandate_does_not_cover`
- `Ac11MandateTest::test_ac11_prefix_needs_separator_after_it` → `test_outcome_gate_module.py::test_ac11_prefix_needs_separator_after_it`
- `Ac11MandateTest::test_ac11_role_autocommitted_answer_does_not_cover` → `test_outcome_gate_module.py::test_ac11_role_autocommitted_answer_does_not_cover`
- `Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts` → `test_outcome_gate_module.py::test_ac13_passed_gate_journal_counts`

## Находки

- Находка mutation-060 (заявка `Ac10OrderTest::test_ac10_findings_order_and_one_line_each`, «внутри вида без сортировки — пары идут в порядке файлов»): «до» не убита никем. Патч убирает сортировку по идентификатору из `ordered` (`outcome_integrity.py:221`), но вход `ordered` уже упорядочен по идентификатору внутри вида: красные идут из `red = sorted(...)` (`outcome_integrity.py:943`), а записи `compare` — в порядке отчёта базы, где идентификатор начинается с пути файла, так что «порядок файлов» совпадает с порядком идентификаторов. Тест эту альтернативу не различает; тест не удалён, перенесён в `test_ac10_findings_order_and_one_line_each`.
- Иных мутаций, не убитых «до», нет; исходов «ошибка сбора, импорта или setup» и предела в последних строках нет.

## Удалённые дубли

Нет: все 42 теста перенесены.

## Числа и время

- Тестов «до»: 42 в исходном файле (строк 1646) и 11 в модуле на базе (строк 781).
- Тестов «после»: 53 в `tests/test_outcome_gate_module.py` (строк 2412).
- Время контрольных прогонов `mutation-run` (без патча, `auto` рабочих процессов): «до» — 24.86 с (прогон №1), 41.02 с (прогон №2), 34.36 с (прогон №3), 37.94 с (прогон №4), 24.43 с (прогон №5), 25.05 с (прогон №6), 22.55 с (прогон №7); «после» — 31.77 с (прогон №8).

## Влияние на систему

- Код пульта не меняется: `orchestrator/` не тронут, мутации живут только
  во временной копии `mutation-run`. Ветка меняет
  `tests/test_outcome_gate_module.py` (добавлены фикстура `box`, шесть
  функций-помощников, 42 теста, импорт из песочницы, абзац докстринга),
  удаляет `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py` (мандат —
  ANSWER-1) и обновляет `docs/codebase-map.md` выводом генератора.
- Неослабление: ожидания перенесены дословно (литерал — литералом,
  константа — константой), сравнения не ослаблены, `skip`/`xfail` и
  пределов нет; доказательство — таблицы «до»/«после»: каждую мутацию,
  убитую «до» тестом T, «после» убивает функция T.
- Песочница, три импортёра, `tests/fixtures.py`, `tests/sandbox.py`,
  файлы волны 2б-3 не тронуты; 11 тестов волны 2а-1а и имена `id_`/`ID_`
  не изменены.
- Откат — revert одного merge-коммита: исходный файл вернётся, функции
  модуля уйдут.

## Риски

- Сообщения подслучаев склеены как `case + <текст>` без разделителя (так
  требует правило сверки помощников по AST): текст провала читается как
  «<ярлык>, зерно <n>зерно: <n>; …» — неудобно, но ярлык и зерно на месте.
- Планка читает PLAN и таблицы из ссылки документов: локальный
  `plank-run` видит их только после автокоммита шага.

## Предложения системе

- `orchestrator/mutation_run.py`: нет флага прогона одного патча по номеру
  вне диапазона «до» — перепрогон переписанных патчей частью 6-15
  гоняет и неизменённые соседние; заготовка 2а-1 при этом соединяла
  альтернативы заявок в одном патче — правило «по патчу на альтернативу»
  стоит проверять при переносе заготовки, а не только при написании.
