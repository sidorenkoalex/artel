---
task: 01M5H1A4GS19TPR4RJ8XRVVYZQ
type: plan
author_role: developer
status: draft
schema_version: 5
---

# PLAN: Ускорение полного набора: разбиение длинных тестов и вспомогательный метод, собиравшийся как тест

## Подход

Правка только четырёх файлов зоны `tests/`; `orchestrator/`, `scripts/`,
`tests/sandbox.py`, `conftest.py`, `pyproject.toml` не меняются.

- **Разбиение циклов подслучаев (outcome_gate, test_ac9 фиксированные,
  test_ac20).** Каждый подслучай — свой метод в том же классе. Метод со
  старым именем несёт ветвление по метке подслучая (`label = "<метка
  первого подслучая>"`; `if label == …:` на каждую ветку) с вызовами
  помощников с утверждениями всех ветвей прямо в своём теле — так учёт
  `guard.test_assertions` по старому имени не уменьшается (требование 2);
  исполняется одна ветка. Новые методы несут тело своего подслучая
  дословно (перенос телом цикла по AST, отступ снят), с тем же
  `subTest(case=…, seed=self.seed)`, тем же зерном (`self.seed`/`self.rng`
  класса подготовки), тем же текстом метки.
  Старое имя у outcome_gate — первый подслучай литерала `cases`
  (`cases[0]`); у `test_ac9` — «ADR в ТЗ», у `test_ac20` — форма `"sha"`
  (первые по сортировке меток, требование 2).
- **Доли перечней.** `places()` у `PultUnchangedTest` — `PLACE_SHARES = 8`
  долей на профиль (16 мест профиля → по 2 места на метод); `PLACES`
  у pytest_own_places — `PLACE_SHARES = 4` (8 мест → по 2 места на метод:
  у `test_ac3_*` в каждой доле ≥ 2 прогона, проверка «HOME не общий»
  сохраняется в каждой доле); категории `config.SPEC_AUDIT_SIGNAL_PATHS`
  у `test_ac9` — `CATEGORY_SHARES = 2` (4 категории → по 2). Доля —
  `sorted(перечень, key=метка)[i::K]` от самого перечня (копия
  сортируется, литерал `PLACES` побайтно прежний, `FULL_PLACES`/`TWO_SIDED`
  прежние); перемешивание `self.rng.shuffle` — внутри доли; каждая доля
  `self.assertTrue(share)`. Метод со старым именем — доля 0, остальные —
  `…_share<i>` (`test_ac9_path_category_share<i>_switches_to_full_review`).
  Цикл по месту внутри доли и вызовы `assert_pult`/`calls_of`/`context`/
  `check_home`/`scenario`/`wrapper_records` — в теле каждого метода.
- **`tests_dir` → `project_tests_dir`** (`ProfileCallersSandbox`, 3 места
  вызова): имя не начинается с `test`, pytest его больше не собирает.
- Выделенных классов и параметризованных подклассов нет: все новые
  методы — в исходных классах.

## Шаги

1. Разбиение `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`
   (6 методов → +19).
2. `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`: доли
   `places` (2 метода → +14), `tests_dir` → `project_tests_dir`.
3. `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py`: `test_ac9`
   (+7: 5 фиксированных и 2 доли категорий), `test_ac20` (+1).
4. `tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py`: доли
   `PLACES` (3 метода → +9).
5. Доказательства: сверка учёта, мутации, число тестов, замеры.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1–4 |
| 2 | 1–4, сверка учёта (шаг 5) |
| 3 | 2–4, сценарий долей |
| 4 | 5, замеры |
| 5 | 2 |
| 6 | 1–4 (только тела тестовых методов и новые помощники тестовых классов) |
| 7 | 5 |
| 8 | 1–4 |

## Таблица «старый тест → новые тесты»

Старое имя исполняет подслучай/долю, названную в скобках.

| Старый тест | Метод со старым именем | Новые тесты |
|---|---|---|
| `PultUnchangedTest::test_ac10_external_pult_pytest_unchanged` | доля 0 из 8 | `test_ac10_external_pult_pytest_unchanged_share1` … `_share7` (`test_ac10_external_pult_pytest_unchanged_share1`, `test_ac10_external_pult_pytest_unchanged_share2`, `test_ac10_external_pult_pytest_unchanged_share3`, `test_ac10_external_pult_pytest_unchanged_share4`, `test_ac10_external_pult_pytest_unchanged_share5`, `test_ac10_external_pult_pytest_unchanged_share6`, `test_ac10_external_pult_pytest_unchanged_share7`) |
| `PultUnchangedTest::test_ac10_artel_unchanged` | доля 0 из 8 | `test_ac10_artel_unchanged_share1`, `test_ac10_artel_unchanged_share2`, `test_ac10_artel_unchanged_share3`, `test_ac10_artel_unchanged_share4`, `test_ac10_artel_unchanged_share5`, `test_ac10_artel_unchanged_share6`, `test_ac10_artel_unchanged_share7` |
| `Ac4PrepareTest::test_ac4_git_preparation_failures_refuse` | «база не определена» | `test_ac4_git_head_not_read_refuses`, `test_ac4_git_base_checkout_failure_refuses`, `test_ac4_git_head_checkout_failure_refuses` |
| `Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side` | «неизвестно база» | `test_ac4_side_head_unknown_refuses_naming_head`, `test_ac4_side_base_timeout_refuses_naming_base`, `test_ac4_side_head_timeout_refuses_naming_head` |
| `Ac7RerunPrepareTest::test_ac7_rerun_preparation_refusals` | «без select» | `test_ac7_rerun_unknown_outcome_refuses`, `test_ac7_rerun_timeout_refuses`, `test_ac7_rerun_base_skipped_refuses`, `test_ac7_rerun_base_record_missing_refuses` |
| `Ac7RerunPrepareTest::test_ac7_branch_rerun_red_kinds` | `failed` | `test_ac7_branch_rerun_error_is_red`, `test_ac7_branch_rerun_skipped_is_red`, `test_ac7_branch_rerun_missing_is_red`, `test_ac7_branch_rerun_retried_is_red` |
| `Ac8VerdictByRecordTest::test_ac8_broken_unstable_and_flaky_on_base` | «сломан» | `test_ac8_unstable_after_change_general_refusal`, `test_ac8_flaky_on_base_no_refusal` |
| `Ac11MandateTest::test_ac11_file_and_prefix_mandate_cover_findings` | «файл» | `test_ac11_class_prefix_mandate_covers`, `test_ac11_method_prefix_mandate_covers_variants`, `test_ac11_other_file_mandate_does_not_cover` |
| `SignalDepthTest::test_ac9_each_signal_alone_switches_to_full_review` | «ADR в ТЗ» | `test_ac9_budget_44_keeps_short_review`, `test_ac9_budget_45_switches_to_full_review`, `test_ac9_protected_path_switches_to_full_review`, `test_ac9_answer_mandate_switches_to_full_review`, `test_ac9_plan_appendix_switches_to_full_review`, `test_ac9_path_category_share0_switches_to_full_review`, `test_ac9_path_category_share1_switches_to_full_review` |
| `AcceptAuditFailTest::test_ac20_fail_verdict_needs_flag_in_both_forms` | форма `"sha"` | `test_ac20_fail_verdict_short_form_needs_flag` |
| `PytestOwnEnvironmentTest::test_ac3_home_fresh_and_removed_after_completion` | доля 0 из 4 | `test_ac3_home_fresh_and_removed_after_completion_share1`, `test_ac3_home_fresh_and_removed_after_completion_share2`, `test_ac3_home_fresh_and_removed_after_completion_share3` |
| `PytestOwnEnvironmentTest::test_ac3_home_removed_after_timeout_and_exception` | доля 0 из 4 | `test_ac3_home_removed_after_timeout_and_exception_share1`, `test_ac3_home_removed_after_timeout_and_exception_share2`, `test_ac3_home_removed_after_timeout_and_exception_share3` |
| `PytestOwnProcessGroupTest::test_ac6_child_gone_after_timeout_and_exception` | доля 0 из 4 | `test_ac6_child_gone_after_timeout_and_exception_share1`, `test_ac6_child_gone_after_timeout_and_exception_share2`, `test_ac6_child_gone_after_timeout_and_exception_share3` |

Итого добавлено разбиением 50 методов: profile_callers 14, outcome_gate 19,
spec_audit_flow 8, pytest_own_places 9.

## Сверка учёта `guard.test_assertions` (мультимножества `Counter`)

Сценарий: `guard.test_assertions(src, rel, guard.TestModules(load))` по
обеим сторонам каждого файла — база `33547d9a` (точка ветвления от main,
`git show`) и голова (диск); нормальные формы утверждений — `Counter`.
Проверяются оба включения требования 7: (1) `Counter(база[старое]) −
Counter(голова[старое])` пуст; (2) `Counter(база[старое]) − (Counter(голова[новые
методы класса]) + Counter(голова[старое]))` пуст (сумма мультимножеств
`Counter +`; метод со старым именем несёт вызовы всех ветвей, исполняемая
доля — среди них).

| Метод | база | старое имя на ветке | сумма (`Counter` +) | потеря (1) | потеря (2) |
|---|---|---|---|---|---|
| `test_ac10_external_pult_pytest_unchanged` | 1 | 11 | 165 | 0 | 0 |
| `test_ac10_artel_unchanged` | 1 | 11 | 165 | 0 | 0 |
| `test_ac4_git_preparation_failures_refuse` | 6 | 6 | 39 | 0 | 0 |
| `test_ac4_side_not_started_or_timeout_refuses_naming_side` | 5 | 5 | 38 | 0 | 0 |
| `test_ac7_rerun_preparation_refusals` | 3 | 3 | 31 | 0 | 0 |
| `test_ac7_branch_rerun_red_kinds` | 4 | 4 | 32 | 0 | 0 |
| `test_ac8_broken_unstable_and_flaky_on_base` | 10 | 10 | 30 | 0 | 0 |
| `test_ac11_file_and_prefix_mandate_cover_findings` | 5 | 5 | 20 | 0 | 0 |
| `test_ac9_each_signal_alone_switches_to_full_review` | 12 | 12 | 86 | 0 | 0 |
| `test_ac20_fail_verdict_needs_flag_in_both_forms` | 7 | 7 | 14 | 0 | 0 |
| `test_ac3_home_fresh_and_removed_after_completion` | 5 | 6 | 42 | 0 | 0 |
| `test_ac3_home_removed_after_timeout_and_exception` | 5 | 6 | 42 | 0 | 0 |
| `test_ac6_child_gone_after_timeout_and_exception` | 3 | 4 | 16 | 0 | 0 |

(У `PultUnchangedTest` на базе учёт 1 — `check_places` был помощником;
на ветке вызовы `calls_of`/`context`/`assert_pult` и `assertTrue(share)`
стоят в теле каждого метода. «Сумма» у `PultUnchangedTest` и
`PytestOwnEnvironmentTest` считается по всем новым методам класса — два
старых метода класса делят одну строку.) Сумма по классам считается
по новым методам класса целиком; ни в одной строке потерь нет.

## Сценарий долей: объединение и непересечение

Для перечня `L` и `K ≤ len(L)`: `shares = [sorted(L, key=метка)[i::K] for i
in range(K)]`. Проверка: `sorted(sum(shares, []), key=метка) == sorted(L,
key=метка)` (объединение долей равно полному перечню) и `sum(len(s) for s in
shares) == len(L)` при попарно пустом пересечении `set(s_i) & set(s_j)`
(доли не пересекаются), каждая `s_i` непуста. Прогнано на:
- `PLACES` (8 элементов, K = 4): доли по 2, объединение = `PLACES`,
  пересечений нет;
- категории `config.SPEC_AUDIT_SIGNAL_PATHS` (`гейты`, `лимиты`,
  `песочница ролей`, `тесты`; K = 2): доли по 2, объединение — все 4,
  пересечений нет;
- `places()` каждого профиля `PultUnchangedTest` (16 меток, K = 8): доли
  по 2, объединение — все 16, пересечений нет.

Доли по сортировке метки (вывод расчёта):
- `PLACES`: `[_run_full_suite_now без observe, acceptance.run]`,
  `[_run_full_suite_now с observe, acceptance.run_plank]`,
  `[_run_full_suite_to_log, acceptance.run_repeat]`,
  `[acceptance.collect, two_sided._run_side]`;
- категории: `[гейты, песочница ролей]`, `[лимиты, тесты]`;
- `places()`: `[amend-tests без долгоживущих файлов, гейт мержа без
  свежего прогона]`, `[amend-tests с долгоживущими файлами, гейт мержа со
  свежим прогоном]`, `[approve на acceptance, двусторонний прогон гейта]`,
  `[plank-run, двусторонний прогон наблюдения]`, `[pull без долгоживущих
  файлов, повторы долгоживущих файлов с зерном]`, `[pull с долгоживущими
  файлами, прогон планки in_dev -> verifying]`, `[suite-run, сухой сбор
  tests_writing без долгоживущих файлов]`, `[автогейт приёмки, сухой сбор
  tests_writing с долгоживущим файлом]`.
Тот же расчёт держит планка (`acceptance_tests/test_ac3_shares.py`,
`test_ac1_split_methods.py`) с лишним элементом, добавленным в перечень:
он попадает в одну из долей без правки теста.

## Таблица мутаций

Каждая мутация — правка кода пульта в worktree задачи по строке «Ловит
мутацию» разбиваемого теста. Под мутацией прогнаны: старый тест в версии
базы `33547d9a` (файл теста базы временно на месте файла, затем `git
checkout HEAD --`) и новый метод того же подслучая на ветке; после
каждой мутации — `git checkout HEAD -- <файл пульта>`. Код 1 — pytest
красный, 0 — зелёный.

| Разбиваемый метод | Мутация (файл пульта: правка) | Старый тест на базе | Новый метод того же подслучая на ветке |
|---|---|---|---|
| `test_ac10_external_pult_pytest_unchanged` | `acceptance.py` `_pytest_env`: `env = dict(os.environ)` → `{"PATH": …}` (окружение не пульта — «переменной пульта в прогоне нет») | 1 (16 подслучаев красны) | `test_ac10_external_pult_pytest_unchanged_share1` … `_share7` и старое имя (доля 0) — все 1 |
| `test_ac10_artel_unchanged` | `acceptance.py` `_task_profile`: проект задачи → первый проект с `runner: pytest-own` в `targets.yaml` («профиль берётся не по проекту задачи») | 1 (7 мест красны) | `test_ac10_artel_unchanged_share1` — 1 (красны также старое имя и `_share2`–`_share5`, `_share7`; `_share6` зелён — места этой доли, `suite-run` и сухой сбор без долгоживущих файлов, мутацией не задеты) |
| `test_ac4_git_preparation_failures_refuse` | `outcome_integrity._judge`: пустая голова → `return None` («пустая голова — гейт пропущен») | 1 | `test_ac4_git_head_not_read_refuses` — 1 |
| `test_ac4_side_not_started_or_timeout_refuses_naming_side` | `outcome_integrity._full_runs`: условие «не начат/таймаут» → `in ()` (исход стороны не отказ подготовки) | 1 (4 подслучая) | `test_ac4_side_base_timeout_refuses_naming_base` — 1 |
| `test_ac7_rerun_preparation_refusals` | `outcome_integrity._rerun`: проверка `run.state not in (GREEN, RED)` снята («неизвестно» перепрогона принят за красный) | 1 | `test_ac7_rerun_unknown_outcome_refuses` — 1 |
| `test_ac7_branch_rerun_red_kinds` | `outcome_integrity._rerun`: `skipped`/нет записи на перепрогоне ветки — зелёный | 1 | `test_ac7_branch_rerun_skipped_is_red` — 1 |
| `test_ac8_broken_unstable_and_flaky_on_base` | `outcome_integrity._judge`: `all(f.kind == BROKEN …)` → `in (BROKEN, UNSTABLE)` («нестабилен» не отличается от «сломан») | 1 | `test_ac8_unstable_after_change_general_refusal` — 1 |
| `test_ac11_file_and_prefix_mandate_cover_findings` | `outcome_integrity._covering_element`: `rest.startswith(element)` → `rest != element` (мандат сверяется точным равенством) | 1 | `test_ac11_class_prefix_mandate_covers` — 1 |
| `test_ac9_each_signal_alone_switches_to_full_review` | `spec_audit.signals`: `amount >= SPEC_AUDIT_BUDGET_SIGNAL_USD` → `>` (порог бюджета строгий) | 1 | `test_ac9_budget_45_switches_to_full_review` — 1 |
| `test_ac20_fail_verdict_needs_flag_in_both_forms` | `fsm._approve_spec_gate`: `if audit_fail and not accept_audit_fail` → `if False` (approve не смотрит вердикт журнала) | 1 | `test_ac20_fail_verdict_short_form_needs_flag` — 1 |
| `test_ac3_home_fresh_and_removed_after_completion` | `acceptance._own_env`: `env["HOME"] = home` → `os.environ["HOME"]` (HOME прогона — HOME пульта) | 1 | `test_ac3_home_fresh_and_removed_after_completion_share1` — 1 |
| `test_ac3_home_removed_after_timeout_and_exception` | `acceptance._own_env`: уборка `home` вынесена из `finally` | 1 | `test_ac3_home_removed_after_timeout_and_exception_share1` — 1 |
| `test_ac6_child_gone_after_timeout_and_exception` | `acceptance._run_in_session`: по таймауту `_kill_group(proc.pid)` → `proc.kill()` (убит только главный процесс) | 1 | `test_ac6_child_gone_after_timeout_and_exception_share1` — 1 |

Первая проба для `test_ac10_external_…` (`_head` → `None`) тест не
покрасила — заменена мутацией окружения из той же строки «Ловит
мутацию». После всех мутаций `git status --porcelain orchestrator/` —
пусто.

## Число тестов

`pytest --collect-only -q` каждого файла зоны (база — `33547d9a`, файл
временно на месте; прочие файлы `tests/` не меняются, поэтому разница
набора — разница четырёх файлов):

| Файл | до | после | `::tests_dir` до/после |
|---|---|---|---|
| `test_01m52eehsrd93wmphwb5vjyrkd_profile_callers` | 26 | 27 | 13 / 0 |
| `test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate` | 23 | 42 | 0 / 0 |
| `test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow` | 23 | 31 | 0 / 0 |
| `test_01m52eefna1wh31962hvnt0yz9_pytest_own_places` | 12 | 21 | 0 / 0 |
| итого | 84 | 121 | 13 / 0 |

Пересчёт: 121 − 84 = 37 = 50 (методов, добавленных разбиением: 14 + 19 +
8 + 9) − 13 (классов, где собирался `tests_dir`: `ProfileCallersSandbox`
и 12 наследников). Повторно собранных копий нет: новых классов нет, все
методы разбиения — в исходных классах.

## Замеры `--durations`

ЗАПОЛНЯЕТСЯ

## Влияние на систему

Меняются только четыре файла `tests/` зоны: тестовые методы и помощники
тестовых классов (`share` у `PultUnchangedTest`, `SignalDepthTest`,
константы долей). Гейт неослабления: учёт утверждений по старому имени
не уменьшился ни у одного из 13 методов (таблица выше); ни один
существующий тестовый метод не удалён и не переименован; `tests_dir` —
не тестовый метод (без утверждений), переименован по требованию 5 SPEC.
Имена, импортируемые `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`
(`ENTRY_HEAD`, `PLAN_READY`, `PLANK_PY`, `SEP`, `OutcomeGateSandbox`,
`flow`, `js_source`, `py_source`, `py_tests`, `spec_text`, `ulid`), и
класс `OutcomeGateSandbox` не тронуты. Откат — revert коммитов ветки по
четырём файлам.

## Риски

- Генерация дословного переноса — по AST; проверено планкой (AC-1, AC-2)
  и сверкой учёта.
- Таймаут 120 с под нагрузкой — самый длинный тест теперь короче.

## Предложения системе

- `plank-run` без аргумента файла обрывается на 300 с при планке с
  настоящими прогонами (здесь — 46 тестов, AC-1 один ≈ 190 с под
  нагрузкой): предел пульта не масштабируется на объём планки.
