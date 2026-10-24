---
task: 01M5PWM5K5M23RS4RR5KK48FY5
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Сведение тестов, волна 2а-1а — песочница гейта исходов в `tests/outcome_gate_sandbox.py`, тесты `id_mandate` и `test_outcome_integrity` в `tests/test_outcome_gate_module.py`

## Подход

Порядок волн 1а/1б и 2а-1: набор мутаций к коду `orchestrator/` по строкам
«Ловит мутацию» двух исходных файлов (11 заявок, у части — по несколько
альтернатив разного смысла → 23 патча `mutation-001.diff`…`mutation-023.diff`;
по патчу на каждую альтернативу, ANSWER-1 п. 4; заготовка 001–009 — патчи 2а-1
с номерами 10, 13, 23, 28, 29, 31, 32, 33, 34, 010–023 написаны заново; каждый
проверен `git apply --check` на 921869bf), таблица «до» на двух исходных файлах
одной частью (`--ref base`), затем вынос песочницы и свод, таблица «после» на
`tests/test_outcome_gate_module.py` (`--ref worktree`, коммит e74df525).

- Песочница: строки 47–899 исходного
  `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py` перенесены в
  `tests/outcome_gate_sandbox.py` дословно; докстринг — одна строка.
- `outcome_gate`: строки 47–899 заменены одной инструкцией
  `from tests.outcome_gate_sandbox import (…)` с 27 именами; докстринг
  (1–46) и строки 900–2493 не тронуты.
- Импортёры: в трёх файлах сменён только модуль в `from … import (`.
- `IdOutcomeGateSandbox` с константами и функциями (строки 53–516 id-файла)
  — в новом файле дословно, с тремя переименованиями.
- Все 11 тестов перенесены функциями модуля под прежними именами методов;
  удалённых дублей нет.

Итерация 2 (REVIEW итерация 1, R1-F1): код `tests/` не менялся (ревью
подтвердило перенос); переписан 010 (одна мутация вместо двух слитых),
добавлены 011–023 на альтернативы заявок, перепрогнаны «до» (№3) и «после»
(№4) полным набором из 23 патчей.

## Шаги

1. Патчи `mutation-001.diff`…`mutation-023.diff` в каталоге документов,
   таблица «до» (`mutation-run --ref base`, оба исходных файла, одна часть).
2. Перенос песочницы в `tests/outcome_gate_sandbox.py`, замена строк 47–899
   `outcome_gate` импортом 27 имён, смена источника импорта у трёх
   импортёров; `pytest --collect-only` по четырём файлам.
3. Новый `tests/test_outcome_gate_module.py`: `IdOutcomeGateSandbox`
   дословно с переименованиями, фикстура `id_box`, функции модуля
   `gate_refusal`/`id_no_gate_refusal`, 11 тестовых функций; удаление двух
   исходных файлов; карта `python3 scripts/codebase_map.py`.
4. Таблица «после» (`mutation-run --ref worktree --tests
   tests/test_outcome_gate_module.py`), сверки, guard, планка.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1, 4 |
| 4 | 1, 4 |
| 5 | 1–4 |
| 6 | 2 |
| 7 | 2 |
| 8 | 3 |
| 9 | 3 |
| 10 | 3 |
| 11 | 2, 3 |
| 12 | 4 |
| 13 | 4 |
| 14 | 2, 3 |
| 15 | — (сессия при Операторе) |

## Мутации и заявки

Файл B — `tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py`,
C — `tests/test_outcome_integrity.py`; все патчи меняют только
`orchestrator/advance_gates/outcome_integrity.py`. В скобках — номер патча
в 2а-1. Каждая альтернатива заявки (часть строки «Ловит мутацию» через «либо»,
«;» или перечисление) — своя мутация; одна мутация на две заявки — только
003 и 017, где альтернативы двух заявок C совпадают по смыслу.

- mutation-001 (2а-1: 010): заявка RecordLevelTest::test_retried_pass_on_base_not_in_pass_to_pass (C) «`in_pass_to_pass` без сверки `retries == 0`»; патч в orchestrator/advance_gates/outcome_integrity.py: `in_pass_to_pass` возвращает `case.outcome == outcome.PASSED` без `retries == 0`.
- mutation-002 (2а-1: 013): заявка RecordLevelTest::test_red_on_branch_kinds (C), альтернатива 1 «`passed` с повтором не считается красным»; патч в orchestrator/advance_gates/outcome_integrity.py: `red_on_branch` без ветки «`passed` с повтором».
- mutation-003 (2а-1: 023): заявки RecordLevelTest::test_compare_vitest_findings_and_non_findings, альтернатива 2 «"стал пропуском" только у `passed`», и RecordLevelTest::test_compare_junit_became_skipped_from_each_outcome, альтернатива 1 «"стал пропуском" только у `passed` базы» (C) — одна по смыслу; патч в orchestrator/advance_gates/outcome_integrity.py: в `compare` условие «стал пропуском» — `b.outcome == outcome.PASSED` вместо `!= SKIPPED`.
- mutation-004 (2а-1: 028): заявка RecordLevelTest::test_mandate_prefix_needs_separator (C) «покрытие `startswith` без сверки следующего символа»; патч в orchestrator/advance_gates/outcome_integrity.py: `_covering_element` не сверяет хвост после префикса (`if True`).
- mutation-005 (2а-1: 029): заявка RoleAutocommitTest::test_ac11_role_autocommitted_id_mandate_does_not_cover (B) «сбор мандата без отбраковки автокоммита роли»; патч в orchestrator/advance_gates/outcome_integrity.py: `_answer_mandates` не отбрасывает ANSWER автокоммита шага роли.
- mutation-006 (2а-1: 031): заявка ExactIdTest::test_ac12_exact_id_with_n_covers_other_variant_does_not (B), альтернатива (а) «элементы нового маркера в гейте не собираются — (а) отказ»; патч в orchestrator/advance_gates/outcome_integrity.py: `_covering_pair` не смотрит мандат по идентификатору.
- mutation-007 (2а-1: 032): заявка HintTest::test_ac13_refusal_hint_names_both_markers (B), альтернатива 2 «своя подсказка называет только новый маркер»; патч в orchestrator/advance_gates/outcome_integrity.py: `_mandate_hint` без прежнего маркера.
- mutation-008 (2а-1: 033): заявка RecordLevelTest::test_skip_growth_line (C), альтернатива 1 «строка пишется и без роста»; патч в orchestrator/advance_gates/outcome_integrity.py: `skip_growth` пишет строку при равенстве чисел (`after < before`).
- mutation-009 (2а-1: 034): заявка RecordLevelTest::test_covered_ids_round_trip_every_finding_kind (C), альтернатива 1 «разбор строки по первому « — »»; патч в orchestrator/advance_gates/outcome_integrity.py: `_finding_of` делит строку по первому « — ».
- mutation-010 (2а-1: 035, переписан): заявка RecordLevelTest::test_fingerprint_sorted_unique_or_none (C), альтернатива 1 «отпечаток без сортировки»; патч в orchestrator/advance_gates/outcome_integrity.py: `fingerprint` — `list(dict.fromkeys(elements_used))` (уникальные, порядок входа) вместо `sorted(set(...))`.
- mutation-011: та же заявка RecordLevelTest::test_fingerprint_sorted_unique_or_none (C), альтернатива 2 «с повтором элемента»; патч в orchestrator/advance_gates/outcome_integrity.py: `fingerprint` — `sorted(elements_used)` (сортировка без устранения повторов).
- mutation-012: заявка RecordLevelTest::test_red_on_branch_kinds (C), альтернатива 2 «`skipped` считается красным»; патч в orchestrator/advance_gates/outcome_integrity.py: `red_on_branch` — `outcome.SKIPPED` добавлен к `(FAILED, ERROR)`.
- mutation-013: заявка RecordLevelTest::test_compare_vitest_findings_and_non_findings (C), альтернатива 1а «`todo` — находка без сверки с базой»; патч в orchestrator/advance_gates/outcome_integrity.py: в `compare` ветка «появилось todo» — `h.mode == _TODO_MODE` без `b.mode != _TODO_MODE`.
- mutation-014: та же заявка RecordLevelTest::test_compare_vitest_findings_and_non_findings, альтернатива 1б «`fails` — находка без сверки с базой»; патч в orchestrator/advance_gates/outcome_integrity.py: ветка «появилось fails» — `h.fails` без `not b.fails`.
- mutation-015: та же заявка RecordLevelTest::test_compare_vitest_findings_and_non_findings, альтернатива 3 «новый идентификатор не проверяется»; патч в orchestrator/advance_gates/outcome_integrity.py: во втором цикле `compare` — `if True: continue` вместо `if cid in base_map: continue`.
- mutation-016: та же заявка RecordLevelTest::test_compare_vitest_findings_and_non_findings, альтернатива 4 «у `to_todo` две находки»; патч в orchestrator/advance_gates/outcome_integrity.py: ветка «появилось todo» дописывает вторую находку `BECAME_SKIPPED`.
- mutation-017: заявка RecordLevelTest::test_compare_junit_became_skipped_from_each_outcome (C), альтернатива 2 «пропуск, бывший пропуском и на базе, даёт находку»; патч в orchestrator/advance_gates/outcome_integrity.py: условие «стал пропуском» — `h.outcome == outcome.SKIPPED` без сверки базы. (Ту же мутацию в заявке vitest не называет; её убивает и vitest-тест — `keep_todo`.)
- mutation-018: заявка RecordLevelTest::test_skip_growth_line (C), альтернатива 2 «несёт идентификатор теста»; патч в orchestrator/advance_gates/outcome_integrity.py: строка `skip_growth` дописывает через «, » идентификаторы пропусков ветки.
- mutation-019: заявка RecordLevelTest::test_covered_ids_round_trip_every_finding_kind (C), альтернатива 2 «маркер исходов «база: » у «сломан правкой»»; патч в orchestrator/advance_gates/outcome_integrity.py: `_runs_marker` — « — ветка: » только у `UNSTABLE`, `BROKEN` получает « — база: ».
- mutation-020: та же заявка RecordLevelTest::test_covered_ids_round_trip_every_finding_kind, альтернатива 3 «строки без пометки мандата дают идентификаторы»; патч в orchestrator/advance_gates/outcome_integrity.py: `_covered_findings` без фильтра `if COVERED_MARK in line`.
- mutation-021: заявка ExactIdTest::test_ac12_exact_id_with_n_covers_other_variant_does_not (B), альтернатива (в) «к ним применено префиксное правило прежнего мандата (`путь::имя`, за которым `#`)»; патч в orchestrator/advance_gates/outcome_integrity.py: `_covering_pair` после точного равенства покрывает `cid` элементом нового маркера-префиксом, за которым `::`, `[` или `#`.
- mutation-022: та же заявка ExactIdTest::test_ac12_exact_id_with_n_covers_other_variant_does_not, альтернатива (б) «сверка по идентификатору без номера (`parse_test_id` без `#n`)»; патч в orchestrator/advance_gates/outcome_integrity.py: `_covering_pair` покрывает `cid` элементом нового маркера с равными `parse_test_id(...)[:3]` (компонент, путь, имя без `#n`).
- mutation-023: заявка HintTest::test_ac13_refusal_hint_names_both_markers (B), альтернатива 1 «гейт исходов по-прежнему зовёт подсказку гейта по тексту (`test_integrity._mandate_hint`)»; патч в orchestrator/advance_gates/outcome_integrity.py: отказ гейта исходов несёт `test_integrity._mandate_hint(task_id)` вместо своей `_mandate_hint`.

Сводка заявка → мутации: C `in_pass_to_pass` — 001; C `red_on_branch` — 002,
012; C vitest `compare` — 013, 003, 015, 016 (альтернатива «todo/fails» — две
мутации 013, 014); C junit `compare` — 003, 017; C `skip_growth` — 008, 018;
C `covering` — 004; C `_covered_ids` — 009, 019, 020; C `fingerprint` — 010,
011; B ac11 — 005; B ac12 — 006, 021, 022; B ac13 — 023, 007.

## Мутации до

# mutation-run №3 задачи 01M5PWM5K5M23RS4RR5KK48FY5
# источник патчей: каталог на диске
# ревизия прогона: base 921869bf4752b43c7ab52033fc0de9a32611d9ae
# тесты: tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py, tests/test_outcome_integrity.py
# патч 1 mutation-001.diff sha256 a037e744c087fde4046a7a4332ca28a028502150d6d5a9e54dad642e389040ac
# патч 2 mutation-002.diff sha256 e608442ca012377afd586dab356cf456f27c6a1478bae8f2f4fa81d40b2ecfc4
# патч 3 mutation-003.diff sha256 5854ed431ab99394c00842d47daf3fbffc3e689918cb7a178c2d395355149b5b
# патч 4 mutation-004.diff sha256 0afa20a351bbb739b51dd1fa7b840390c7805beca923ea2b2c28b44349642b76
# патч 5 mutation-005.diff sha256 b9ac24756c3f2961ddd662b39962fe1c123871519ce10580a4967c4647dd6cab
# патч 6 mutation-006.diff sha256 75606e4fd1d20ae1c398271645e628b3aec69e12785458bf408e77b9e398ae6e
# патч 7 mutation-007.diff sha256 31d28986cd1cfc82d311237c2f535d214f4297e0a7b6cfe86879a2d3155b9dfd
# патч 8 mutation-008.diff sha256 eccd871aab688e2a9ab9e0b722ba73dd8e1858b69a21374571dcb55e13fe08b0
# патч 9 mutation-009.diff sha256 a8d21ebcd326420b9c52ace5528f64fb584a7f22de81e20113fa9a4c49a069b2
# патч 10 mutation-010.diff sha256 03447e9e68b5b29b199266c7fe8d96614467231fb0f5f450c3fd5ee897bdfbca
# патч 11 mutation-011.diff sha256 16c057c76d21278fe8bc1b34b652882f2e5bcb12749fb3dccb5ddb6d3763dab3
# патч 12 mutation-012.diff sha256 6194f9518bab4c72c770dc421d0af71a9d792535660c7f61281e974039fc831b
# патч 13 mutation-013.diff sha256 302744a914972c551733c9e822c7025fffc84e9daced3a70c6c02af294a95a85
# патч 14 mutation-014.diff sha256 b926d5340da9ad3b67b8078f446853ac0c88aeb9ee4c95c1677f1fb5acefdbdc
# патч 15 mutation-015.diff sha256 be794c9068e132f4163c5b4e3dd0c786c7c265fe9350b98e84a618c4e1cc2acb
# патч 16 mutation-016.diff sha256 86680791c86092bb20ec48862362da637d35f6ac6c9728ca6819af9b985814a6
# патч 17 mutation-017.diff sha256 cf2554728eb3f28bc26c6646def9a5b8c8c1c7002f85690d12eb38cde0e85d0b
# патч 18 mutation-018.diff sha256 63c42d1be0d27096359543456a9c747f40ed13445f00bc8186621edac190d4fe
# патч 19 mutation-019.diff sha256 2291c21dddd4dd6ee4416c8500461a458fe0e26b88496a7f29d8013b81e61d77
# патч 20 mutation-020.diff sha256 bed71c7b85b807ede138ecaf5ef2308c067be63f7fd7a375867920df403061df
# патч 21 mutation-021.diff sha256 a3ee74498aa2f9ecf78341c361ce048eb1ba0ce351bb9a3df5323b4f5c396749
# патч 22 mutation-022.diff sha256 9e231520a4caefb0e59d4ec73342f95523f3c7aba8623e45ba9696e46fb34abe
# патч 23 mutation-023.diff sha256 3d6254252b020aee2bf2d9fce3e3c8308021191c0596c87f02d109095b7ea72d
номер	исход	узлы
1	убита	tests/test_outcome_integrity.py::RecordLevelTest::test_retried_pass_on_base_not_in_pass_to_pass
2	убита	tests/test_outcome_integrity.py::RecordLevelTest::test_red_on_branch_kinds
3	убита	tests/test_outcome_integrity.py::RecordLevelTest::test_compare_vitest_findings_and_non_findings,tests/test_outcome_integrity.py::RecordLevelTest::test_compare_junit_became_skipped_from_each_outcome
4	убита	tests/test_outcome_integrity.py::RecordLevelTest::test_mandate_prefix_needs_separator
5	убита	tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py::RoleAutocommitTest::test_ac11_role_autocommitted_id_mandate_does_not_cover
6	убита	tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py::ExactIdTest::test_ac12_exact_id_with_n_covers_other_variant_does_not
7	убита	tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py::HintTest::test_ac13_refusal_hint_names_both_markers
8	убита	tests/test_outcome_integrity.py::RecordLevelTest::test_skip_growth_line
9	убита	tests/test_outcome_integrity.py::RecordLevelTest::test_covered_ids_round_trip_every_finding_kind
10	убита	tests/test_outcome_integrity.py::RecordLevelTest::test_fingerprint_sorted_unique_or_none
11	убита	tests/test_outcome_integrity.py::RecordLevelTest::test_fingerprint_sorted_unique_or_none
12	убита	tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py::HintTest::test_ac13_refusal_hint_names_both_markers,tests/test_outcome_integrity.py::RecordLevelTest::test_red_on_branch_kinds,tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py::ExactIdTest::test_ac12_exact_id_with_n_covers_other_variant_does_not,tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py::RoleAutocommitTest::test_ac11_role_autocommitted_id_mandate_does_not_cover
13	убита	tests/test_outcome_integrity.py::RecordLevelTest::test_compare_vitest_findings_and_non_findings
14	убита	tests/test_outcome_integrity.py::RecordLevelTest::test_compare_vitest_findings_and_non_findings
15	убита	tests/test_outcome_integrity.py::RecordLevelTest::test_compare_vitest_findings_and_non_findings
16	убита	tests/test_outcome_integrity.py::RecordLevelTest::test_compare_vitest_findings_and_non_findings
17	убита	tests/test_outcome_integrity.py::RecordLevelTest::test_compare_vitest_findings_and_non_findings,tests/test_outcome_integrity.py::RecordLevelTest::test_compare_junit_became_skipped_from_each_outcome
18	убита	tests/test_outcome_integrity.py::RecordLevelTest::test_skip_growth_line
19	убита	tests/test_outcome_integrity.py::RecordLevelTest::test_covered_ids_round_trip_every_finding_kind
20	убита	tests/test_outcome_integrity.py::RecordLevelTest::test_covered_ids_round_trip_every_finding_kind
21	убита	tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py::ExactIdTest::test_ac12_exact_id_with_n_covers_other_variant_does_not
22	убита	tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py::ExactIdTest::test_ac12_exact_id_with_n_covers_other_variant_does_not
23	убита	tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py::HintTest::test_ac13_refusal_hint_names_both_markers

Строки падения «до» (лог `…-mutation-run-3-p<nnn>.log`):

- mutation-001: RecordLevelTest::test_retried_pass_on_base_not_in_pass_to_pass — tests/test_outcome_integrity.py:35
- mutation-002: RecordLevelTest::test_red_on_branch_kinds — tests/test_outcome_integrity.py:53
- mutation-003: RecordLevelTest::test_compare_vitest_findings_and_non_findings — tests/test_outcome_integrity.py:75; RecordLevelTest::test_compare_junit_became_skipped_from_each_outcome — tests/test_outcome_integrity.py:92
- mutation-004: RecordLevelTest::test_mandate_prefix_needs_separator — tests/test_outcome_integrity.py:121
- mutation-005: RoleAutocommitTest::test_ac11_role_autocommitted_id_mandate_does_not_cover — tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py:507 (`gate_refusal`, `assertTrue` записи отказа)
- mutation-006: ExactIdTest::test_ac12_exact_id_with_n_covers_other_variant_does_not — tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py:515 (`no_gate_refusal`)
- mutation-007: HintTest::test_ac13_refusal_hint_names_both_markers — tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py:604
- mutation-008: RecordLevelTest::test_skip_growth_line — tests/test_outcome_integrity.py:101
- mutation-009: RecordLevelTest::test_covered_ids_round_trip_every_finding_kind — tests/test_outcome_integrity.py:143
- mutation-010: RecordLevelTest::test_fingerprint_sorted_unique_or_none — tests/test_outcome_integrity.py:155
- mutation-011: RecordLevelTest::test_fingerprint_sorted_unique_or_none — tests/test_outcome_integrity.py:155
- mutation-012: RecordLevelTest::test_red_on_branch_kinds — tests/test_outcome_integrity.py:53 (подслучаи `skipped`); попутно ac11/ac12/ac13 — tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py:507 (`gate_refusal`: отказ записан действием «— сломан правкой», не «по исходам»)
- mutation-013: RecordLevelTest::test_compare_vitest_findings_and_non_findings — tests/test_outcome_integrity.py:75
- mutation-014: RecordLevelTest::test_compare_vitest_findings_and_non_findings — tests/test_outcome_integrity.py:75
- mutation-015: RecordLevelTest::test_compare_vitest_findings_and_non_findings — tests/test_outcome_integrity.py:75
- mutation-016: RecordLevelTest::test_compare_vitest_findings_and_non_findings — tests/test_outcome_integrity.py:75
- mutation-017: RecordLevelTest::test_compare_junit_became_skipped_from_each_outcome — tests/test_outcome_integrity.py:92; RecordLevelTest::test_compare_vitest_findings_and_non_findings — tests/test_outcome_integrity.py:75
- mutation-018: RecordLevelTest::test_skip_growth_line — tests/test_outcome_integrity.py:105 (`assertNotIn("::", line)`)
- mutation-019: RecordLevelTest::test_covered_ids_round_trip_every_finding_kind — tests/test_outcome_integrity.py:143
- mutation-020: RecordLevelTest::test_covered_ids_round_trip_every_finding_kind — tests/test_outcome_integrity.py:143
- mutation-021: ExactIdTest::test_ac12_exact_id_with_n_covers_other_variant_does_not — tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py:507 (`gate_refusal`, подслучай «без #n»)
- mutation-022: ExactIdTest::test_ac12_exact_id_with_n_covers_other_variant_does_not — tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py:507 (`gate_refusal`, подслучаи «другой #3» и «без #n»)
- mutation-023: HintTest::test_ac13_refusal_hint_names_both_markers — tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py:604

Узлы, убитые ошибкой сбора, импорта, setup или утверждением методов
`in_dev_task` (:373, :398) / `operator_mandate` (:462): нет ни «до», ни
«после» — каждая строка падения выше и ниже лежит в утверждении теста или
помощника исхода (`gate_refusal`/`no_gate_refusal`, после — функции модуля).
Исходов «оборвана по пределу» нет. Контрольный прогон «до» (№3): 11 passed,
9 subtests passed за 13.47 с.

### Находки

Нет: все 23 мутации убиты и «до», и «после».

## Мутации после

Перед прогоном — `git status --porcelain -- orchestrator/` рабочей копии
(вывод пуст):

```
git status --porcelain -- orchestrator/
```

# mutation-run №4 задачи 01M5PWM5K5M23RS4RR5KK48FY5
# источник патчей: каталог на диске
# ревизия прогона: worktree e74df52504538b108f1aec1bb0f365d4eb2d45ee
# тесты: tests/test_outcome_gate_module.py
# патч 1 mutation-001.diff sha256 a037e744c087fde4046a7a4332ca28a028502150d6d5a9e54dad642e389040ac
# патч 2 mutation-002.diff sha256 e608442ca012377afd586dab356cf456f27c6a1478bae8f2f4fa81d40b2ecfc4
# патч 3 mutation-003.diff sha256 5854ed431ab99394c00842d47daf3fbffc3e689918cb7a178c2d395355149b5b
# патч 4 mutation-004.diff sha256 0afa20a351bbb739b51dd1fa7b840390c7805beca923ea2b2c28b44349642b76
# патч 5 mutation-005.diff sha256 b9ac24756c3f2961ddd662b39962fe1c123871519ce10580a4967c4647dd6cab
# патч 6 mutation-006.diff sha256 75606e4fd1d20ae1c398271645e628b3aec69e12785458bf408e77b9e398ae6e
# патч 7 mutation-007.diff sha256 31d28986cd1cfc82d311237c2f535d214f4297e0a7b6cfe86879a2d3155b9dfd
# патч 8 mutation-008.diff sha256 eccd871aab688e2a9ab9e0b722ba73dd8e1858b69a21374571dcb55e13fe08b0
# патч 9 mutation-009.diff sha256 a8d21ebcd326420b9c52ace5528f64fb584a7f22de81e20113fa9a4c49a069b2
# патч 10 mutation-010.diff sha256 03447e9e68b5b29b199266c7fe8d96614467231fb0f5f450c3fd5ee897bdfbca
# патч 11 mutation-011.diff sha256 16c057c76d21278fe8bc1b34b652882f2e5bcb12749fb3dccb5ddb6d3763dab3
# патч 12 mutation-012.diff sha256 6194f9518bab4c72c770dc421d0af71a9d792535660c7f61281e974039fc831b
# патч 13 mutation-013.diff sha256 302744a914972c551733c9e822c7025fffc84e9daced3a70c6c02af294a95a85
# патч 14 mutation-014.diff sha256 b926d5340da9ad3b67b8078f446853ac0c88aeb9ee4c95c1677f1fb5acefdbdc
# патч 15 mutation-015.diff sha256 be794c9068e132f4163c5b4e3dd0c786c7c265fe9350b98e84a618c4e1cc2acb
# патч 16 mutation-016.diff sha256 86680791c86092bb20ec48862362da637d35f6ac6c9728ca6819af9b985814a6
# патч 17 mutation-017.diff sha256 cf2554728eb3f28bc26c6646def9a5b8c8c1c7002f85690d12eb38cde0e85d0b
# патч 18 mutation-018.diff sha256 63c42d1be0d27096359543456a9c747f40ed13445f00bc8186621edac190d4fe
# патч 19 mutation-019.diff sha256 2291c21dddd4dd6ee4416c8500461a458fe0e26b88496a7f29d8013b81e61d77
# патч 20 mutation-020.diff sha256 bed71c7b85b807ede138ecaf5ef2308c067be63f7fd7a375867920df403061df
# патч 21 mutation-021.diff sha256 a3ee74498aa2f9ecf78341c361ce048eb1ba0ce351bb9a3df5323b4f5c396749
# патч 22 mutation-022.diff sha256 9e231520a4caefb0e59d4ec73342f95523f3c7aba8623e45ba9696e46fb34abe
# патч 23 mutation-023.diff sha256 3d6254252b020aee2bf2d9fce3e3c8308021191c0596c87f02d109095b7ea72d
номер	исход	узлы
1	убита	tests/test_outcome_gate_module.py::test_retried_pass_on_base_not_in_pass_to_pass
2	убита	tests/test_outcome_gate_module.py::test_red_on_branch_kinds
3	убита	tests/test_outcome_gate_module.py::test_compare_vitest_findings_and_non_findings,tests/test_outcome_gate_module.py::test_compare_junit_became_skipped_from_each_outcome
4	убита	tests/test_outcome_gate_module.py::test_mandate_prefix_needs_separator
5	убита	tests/test_outcome_gate_module.py::test_ac11_role_autocommitted_id_mandate_does_not_cover
6	убита	tests/test_outcome_gate_module.py::test_ac12_exact_id_with_n_covers_other_variant_does_not
7	убита	tests/test_outcome_gate_module.py::test_ac13_refusal_hint_names_both_markers
8	убита	tests/test_outcome_gate_module.py::test_skip_growth_line
9	убита	tests/test_outcome_gate_module.py::test_covered_ids_round_trip_every_finding_kind
10	убита	tests/test_outcome_gate_module.py::test_fingerprint_sorted_unique_or_none
11	убита	tests/test_outcome_gate_module.py::test_fingerprint_sorted_unique_or_none
12	убита	tests/test_outcome_gate_module.py::test_red_on_branch_kinds,tests/test_outcome_gate_module.py::test_ac12_exact_id_with_n_covers_other_variant_does_not,tests/test_outcome_gate_module.py::test_ac11_role_autocommitted_id_mandate_does_not_cover,tests/test_outcome_gate_module.py::test_ac13_refusal_hint_names_both_markers
13	убита	tests/test_outcome_gate_module.py::test_compare_vitest_findings_and_non_findings
14	убита	tests/test_outcome_gate_module.py::test_compare_vitest_findings_and_non_findings
15	убита	tests/test_outcome_gate_module.py::test_compare_vitest_findings_and_non_findings
16	убита	tests/test_outcome_gate_module.py::test_compare_vitest_findings_and_non_findings
17	убита	tests/test_outcome_gate_module.py::test_compare_vitest_findings_and_non_findings,tests/test_outcome_gate_module.py::test_compare_junit_became_skipped_from_each_outcome
18	убита	tests/test_outcome_gate_module.py::test_skip_growth_line
19	убита	tests/test_outcome_gate_module.py::test_covered_ids_round_trip_every_finding_kind
20	убита	tests/test_outcome_gate_module.py::test_covered_ids_round_trip_every_finding_kind
21	убита	tests/test_outcome_gate_module.py::test_ac12_exact_id_with_n_covers_other_variant_does_not
22	убита	tests/test_outcome_gate_module.py::test_ac12_exact_id_with_n_covers_other_variant_does_not
23	убита	tests/test_outcome_gate_module.py::test_ac13_refusal_hint_names_both_markers

Строки падения «после» (лог `…-mutation-run-4-p<nnn>.log`):

- mutation-001: tests/test_outcome_gate_module.py::test_retried_pass_on_base_not_in_pass_to_pass — tests/test_outcome_gate_module.py:653
- mutation-002: tests/test_outcome_gate_module.py::test_red_on_branch_kinds — tests/test_outcome_gate_module.py:673
- mutation-003: tests/test_outcome_gate_module.py::test_compare_vitest_findings_and_non_findings — tests/test_outcome_gate_module.py:696; tests/test_outcome_gate_module.py::test_compare_junit_became_skipped_from_each_outcome — tests/test_outcome_gate_module.py:714
- mutation-004: tests/test_outcome_gate_module.py::test_mandate_prefix_needs_separator — tests/test_outcome_gate_module.py:745
- mutation-005: tests/test_outcome_gate_module.py::test_ac11_role_autocommitted_id_mandate_does_not_cover — tests/test_outcome_gate_module.py:541 (функция модуля `gate_refusal`)
- mutation-006: tests/test_outcome_gate_module.py::test_ac12_exact_id_with_n_covers_other_variant_does_not — tests/test_outcome_gate_module.py:550 (функция модуля `id_no_gate_refusal`)
- mutation-007: tests/test_outcome_gate_module.py::test_ac13_refusal_hint_names_both_markers — tests/test_outcome_gate_module.py:641
- mutation-008: tests/test_outcome_gate_module.py::test_skip_growth_line — tests/test_outcome_gate_module.py:724
- mutation-009: tests/test_outcome_gate_module.py::test_covered_ids_round_trip_every_finding_kind — tests/test_outcome_gate_module.py:768
- mutation-010: tests/test_outcome_gate_module.py::test_fingerprint_sorted_unique_or_none — tests/test_outcome_gate_module.py:780
- mutation-011: tests/test_outcome_gate_module.py::test_fingerprint_sorted_unique_or_none — tests/test_outcome_gate_module.py:780
- mutation-012: tests/test_outcome_gate_module.py::test_red_on_branch_kinds — tests/test_outcome_gate_module.py:673; попутно ac11/ac12/ac13 — tests/test_outcome_gate_module.py:541 (`gate_refusal`)
- mutation-013: tests/test_outcome_gate_module.py::test_compare_vitest_findings_and_non_findings — tests/test_outcome_gate_module.py:696
- mutation-014: tests/test_outcome_gate_module.py::test_compare_vitest_findings_and_non_findings — tests/test_outcome_gate_module.py:696
- mutation-015: tests/test_outcome_gate_module.py::test_compare_vitest_findings_and_non_findings — tests/test_outcome_gate_module.py:696
- mutation-016: tests/test_outcome_gate_module.py::test_compare_vitest_findings_and_non_findings — tests/test_outcome_gate_module.py:696
- mutation-017: tests/test_outcome_gate_module.py::test_compare_junit_became_skipped_from_each_outcome — tests/test_outcome_gate_module.py:714; tests/test_outcome_gate_module.py::test_compare_vitest_findings_and_non_findings — tests/test_outcome_gate_module.py:696
- mutation-018: tests/test_outcome_gate_module.py::test_skip_growth_line — tests/test_outcome_gate_module.py:728 (`assert "::" not in line`)
- mutation-019: tests/test_outcome_gate_module.py::test_covered_ids_round_trip_every_finding_kind — tests/test_outcome_gate_module.py:768
- mutation-020: tests/test_outcome_gate_module.py::test_covered_ids_round_trip_every_finding_kind — tests/test_outcome_gate_module.py:768
- mutation-021: tests/test_outcome_gate_module.py::test_ac12_exact_id_with_n_covers_other_variant_does_not — tests/test_outcome_gate_module.py:541 (`gate_refusal`)
- mutation-022: tests/test_outcome_gate_module.py::test_ac12_exact_id_with_n_covers_other_variant_does_not — tests/test_outcome_gate_module.py:541 (`gate_refusal`)
- mutation-023: tests/test_outcome_gate_module.py::test_ac13_refusal_hint_names_both_markers — tests/test_outcome_gate_module.py:641

Множество убивающих тестов каждой мутации «после» равно множеству «до» по
соответствию имён ниже (в том числе 012 — четыре теста, 003 и 017 — по два).
Ревизии шапок: «до» — base 921869bf, «после» — worktree e74df525;
`git rev-parse <sha>:orchestrator` у обеих — 105c1bb95bca0d84bea9c8966df023b92e9f713d
(дерево `orchestrator/` одно). sha256 каждого из 23 патчей в шапках «до» и
«после» совпадает. Контрольный прогон «после» (№4): 11 passed за 12.53 с.

## Соответствие «до → после»

- RoleAutocommitTest::test_ac11_role_autocommitted_id_mandate_does_not_cover → test_outcome_gate_module.py::test_ac11_role_autocommitted_id_mandate_does_not_cover
- ExactIdTest::test_ac12_exact_id_with_n_covers_other_variant_does_not → test_outcome_gate_module.py::test_ac12_exact_id_with_n_covers_other_variant_does_not
- HintTest::test_ac13_refusal_hint_names_both_markers → test_outcome_gate_module.py::test_ac13_refusal_hint_names_both_markers
- RecordLevelTest::test_retried_pass_on_base_not_in_pass_to_pass → test_outcome_gate_module.py::test_retried_pass_on_base_not_in_pass_to_pass
- RecordLevelTest::test_red_on_branch_kinds → test_outcome_gate_module.py::test_red_on_branch_kinds
- RecordLevelTest::test_compare_vitest_findings_and_non_findings → test_outcome_gate_module.py::test_compare_vitest_findings_and_non_findings
- RecordLevelTest::test_compare_junit_became_skipped_from_each_outcome → test_outcome_gate_module.py::test_compare_junit_became_skipped_from_each_outcome
- RecordLevelTest::test_skip_growth_line → test_outcome_gate_module.py::test_skip_growth_line
- RecordLevelTest::test_mandate_prefix_needs_separator → test_outcome_gate_module.py::test_mandate_prefix_needs_separator
- RecordLevelTest::test_covered_ids_round_trip_every_finding_kind → test_outcome_gate_module.py::test_covered_ids_round_trip_every_finding_kind
- RecordLevelTest::test_fingerprint_sorted_unique_or_none → test_outcome_gate_module.py::test_fingerprint_sorted_unique_or_none

## Удалённые дубли

Нет: перенесены все 11 тестов.

## Перенос песочницы и импорт `outcome_gate`

Сверка `ast.dump` переноса в outcome_gate_sandbox: 60 операторов верхнего уровня строк 47–899 базы `outcome_gate` и 60 операторов `tests/outcome_gate_sandbox.py` после докстринга совпадают по набору, порядку и `ast.dump` каждого; строки 2–854 нового модуля побайтово равны строкам 47–899 исходника (ANSWER-1 п. 6).

27 имён импорта в `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`
(строка 47): `Path`, `SimpleNamespace`, `checkpoint`, `config`, `mock`,
`os`, `project_profile`, `re`, `store`, `unittest`, `workspace`,
`OutcomeGateSandbox`, `js_source`, `py_source`, `ulid`, `BROKEN_ACTION`,
`FLAKY_ON_BASE`, `OUTCOME_ACTION`, `PASSED_NOTE`, `PREPARE_ACTION`,
`REVIEW_CHANGES`, `REWORK_ACTION`, `SEP`, `TASKS_DIR`, `TEXT_GATE_ACTION`,
`TEXT_GATE_SKIP`, `VITEST_KIND`. Проверено обходом AST: каждое имя
употребляется в оставшемся файле, неопределённых имён нет.

Импортёры: `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:60`,
`tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:56`,
`tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:40` — источник
`tests.test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate` → `tests.outcome_gate_sandbox`,
список имён прежний.

`python3 -m pytest --collect-only -q` по `outcome_gate` и трём импортёрам: 122 tests collected.
Их зелень — по CI кодовой ветки (ANSWER-1 п. 1: итог
записывает ревьювер в REVIEW; в итерации 1 ревьювер записал CI e74df525
зелёным, 16 проверок).

## Переименования в `tests/test_outcome_gate_module.py`

- `GATE_ACTIONS` → `ID_GATE_ACTIONS` (определение и употребление в `no_gate_refusal`);
- `VITEST_KIND` → `ID_VITEST_KIND` (определение и употребление в `vitest_run`);
- `spec_text` → `id_spec_text` (определение и вызов в `in_dev_task`).

Прочие совпадающие имена (`ulid`, `flow`, `arg_value`, `js_source`,
`OUTCOME_ACTION` и др.) не импортируются из песочницы: в новом файле —
дословные копии id-файла под прежними именами, песочницы не объединены.
Фикстура `id_box` — только `yield from _sandbox(IdOutcomeGateSandbox)`.
Помощники исхода — функции модуля `gate_refusal(box, rows, output)` и
`id_no_gate_refusal(box, rows, output)` (тело дословно, `self.` → `box.`,
читает `ID_GATE_ACTIONS`); методы `gate_refusal`/`no_gate_refusal` в
`IdOutcomeGateSandbox` не изменены.

Перевод утверждений: `assertIn(a, b, msg)` → `assert a in b, msg`;
`assertTrue`/`assertFalse` → `assert`/`assert not`; `assertEqual` →
`==`; `assertIsNone` → `is None`; `assertNotIn` → `not in`. Оба цикла
`subTest` (`ExactIdTest`, `test_red_on_branch_kinds`) — прежним циклом в
одной функции (ANSWER-1 п. 5), ярлык `subTest` — во втором операнде
`assert`.

## Объём и время

- До: 11 тестов (3 в id-файле, 8 в `test_outcome_integrity.py`), 609 + 160 = 769 строк; контрольный прогон `mutation-run` «до» — 13.47 с (№3; в №1 итерации 1 — 8.64 с).
- После: 11 тестов в `tests/test_outcome_gate_module.py`, 781 строк; контрольный прогон «после» — 12.53 с (№4; в №2 — 8.83 с).
- `tests/outcome_gate_sandbox.py` — 854 строк; `outcome_gate` — 2493 → 1646 строк.

## Влияние на систему

Код `orchestrator/` не меняется (дерево одно у обеих ревизий шапок; мутации
живут только во временной копии `mutation-run`). Удаляются два файла по
мандату ANSWER-1 (`Ослабление тестов разрешено` на оба пути); `outcome_gate`
и три импортёра проходят гейт неослабления без мандата — их тесты и
утверждения не тронуты, сменён только источник импорта. Каждое свойство двух
удаляемых файлов перенесено дословно; доказательство — 23/23 убитых мутаций
«до» и «после», по мутации на каждую альтернативу заявок. `tests/fixtures.py`,
`tests/sandbox.py`, файлы волны 2б-3 не тронуты; `docs/codebase-map.md` —
только вывод генератора. Откат — revert одного merge-коммита.

## Риски

- Тесты `outcome_gate` и трёх импортёров под ролью не прогонялись (только
  сбор, требование 11) — их зелень подтверждает CI кодовой ветки.
- Цикл `ExactIdTest` без `subTest` останавливается на первом упавшем
  подслучае (раньше прогонялись все три) — свойство то же, диагностика
  беднее; подслучаи (б)/(в) по отдельности доказывают 021 и 022.

## Реестр замечаний ревью

- R1-F1 — fixed: 010 переписан на одну мутацию («без сортировки»), добавлены
  011–023 — по патчу на каждую альтернативу из перечня REVIEW (ac12 (в)/(б) —
  021/022; ac13 `test_integrity._mandate_hint` — 023; `red_on_branch` `skipped` —
  012; vitest `compare`: `todo`/`fails` без базы — 013/014, новый id — 015,
  две находки `to_todo` — 016; junit пропуск на обеих сторонах — 017;
  `skip_growth` с идентификатором — 018; `_covered_ids` «база: » у «сломан
  правкой» — 019, строки без пометки — 020; `fingerprint` с повтором — 011).
  Перепрогнаны «до» (№3) и «после» (№4): 23/23 убиты, находок нет;
  сопоставление и строки падения обновлены.

## Предложения системе

- В окружении роли нет `ls`/`cat`, а длинный heredoc Bash отклоняется
  парсером инструмента — генерацию крупных файлов приходится делать
  через Write с меткой и вставкой `python3`; стоит упомянуть в скиле
  разработчика.
- `mutation-run --wait` показывает только последний прогон; дословный вывод
  прежнего прогона берётся из `.artel/logs/suite-run/<id>/…-mutation-run-<n>.mutations.tsv`
  — команды показа таблицы по номеру прогона не хватает.
- `plank-run` читает PLAN.md из закоммиченной ссылки документов
  (`plank_helper.artifact_text`, ревизия выкладки), а не с диска: правку PLAN
  в шаге им не проверить — отказ гейта приёмки 2-й итерации (нет пути
  `orchestrator/…` в строках мутаций и ссылок `test_outcome_gate_module.py::`
  в строках падения «после») пришёл только после сдачи. Нужен режим
  `plank-run` по каталогу документов на диске.
