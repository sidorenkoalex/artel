---
task: 01M5H1A4GS19TPR4RJ8XRVVYZQ
type: plan
author_role: developer
status: ready
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

Сценарий: каждый файл зоны — отдельным прогоном `python3 -m pytest <файл> -q
-p no:cacheprovider -p timeout -o timeout=600 --durations=0
--durations-min=0` на этой машине; «до» — файл базы `33547d9a` (на время
прогона на месте файла ветки; версии файлов зоны на main `3aacbd39` с ней
совпадают, `git diff --stat 33547d9a main -- <4 файла>` пуст), «после» —
файл ветки. Прогон стартует только при средней загрузке за минуту ниже 4,
её значение в начале прогона — в строках «До»/«После» каждого файла.
Время теста — сумма setup + call + teardown. Кругов: по два на файл,
у profile_callers — три. Порог (требование 4): методы со старым именем и
методы разбиения — ≤ 10 с (у `test_ac20_…` — ≤ 20 с) по максимуму кругов
«после»; прочие тесты — сравнение минимумов кругов «до» и «после»
(«в разбросе кругов „до“» — минимум «после» не больше максимума «до»).

Итог: все 13 методов со старым именем и все 50 методов разбиения в
пороге (самый длинный — `test_ac20_fail_verdict_needs_flag_in_both_forms`
10,04 с при пороге 20 с; из порога 10 с — `share`/подслучаи не длиннее
6,98 с). Самый длинный тест файла до → после: profile_callers 35,36 →
7,01 с; outcome_gate 26,87 → 13,45 с (неразбиваемый
`test_ac6_red_kinds_rerun…`, 12,71–15,02 → 13,25–13,45); spec_audit_flow
35,20 → 13,35 с (неразбиваемый `test_ac17_reject…`, 14,72–15,61 →
11,60–13,35); pytest_own_places 20,43 → 7,68 с. Прочие тесты: все «не
длиннее» либо в разбросе кругов «до», кроме двух, у которых тело не
менялось (сверка AST тел прочих методов база ↔ ветка — совпадают):
`AutogateTest::test_ac1_autogate_full_suite_by_own_profile` (+0,37 с) и
`Ac1OutOfBoundsTest::test_ac1_decide_skip_refusal_and_canary_no_gate`
(+0,66 с). Их проверка — адресным прогоном одного теста `pytest
<файл>::<тест>`, 5 пар «до/после» чередованием (загрузка 4,1–5,1 —
машину делят другие задачи, условие «ниже 4» здесь не выполнено, поэтому
это довод, а не замер AC-4):
- `AutogateTest::test_ac1_…`: до мин. 3,22 / медиана 3,32 с; после мин.
  3,20 / медиана 3,24 с — не длиннее;
- `Ac1OutOfBoundsTest::test_ac1_decide_…`: до мин. 9,23 / медиана 9,30 с;
  после мин. 9,23 / медиана 9,62 с — минимумы равны.
Расхождение на прогоне файла — шум машины, не правка задачи.

#### `test_01m52eehsrd93wmphwb5vjyrkd_profile_callers`

До: круг 1 — загрузка в начале 3.75, 26 passed, 13 warnings, 44 subtests passed in 99.52s (0:01:39); круг 2 — загрузка в начале 3.97, 26 passed, 13 warnings, 44 subtests passed in 116.24s (0:01:56); круг 3 — загрузка в начале 3.96, 26 passed, 13 warnings, 44 subtests passed in 110.47s (0:01:50).
После: круг 1 — загрузка в начале 3.92, 27 passed, 44 subtests passed in 105.93s (0:01:45); круг 2 — загрузка в начале 3.39, 27 passed, 44 subtests passed in 127.43s (0:02:07); круг 3 — загрузка в начале 3.98, 27 passed, 44 subtests passed in 109.72s (0:01:49).

| Тест | вид | до, к1/к2/к3, с | после, к1/к2/к3, с | мин. до → мин. после, с | итог |
|---|---|---|---|---|---|
| `PultUnchangedTest::test_ac10_external_pult_pytest_unchanged` | старое имя | 28.36 / 35.36 / 32.53 | 4.95 / 4.91 / 5.31 | 28.36 → 4.91 | ≤ 10 с: да |
| `PultUnchangedTest::test_ac10_artel_unchanged` | старое имя | 29.42 / 33.21 / 32.04 | 5.06 / 6.39 / 5.23 | 29.42 → 5.06 | ≤ 10 с: да |
| `MergeGateTest::test_ac3_merge_gate_full_suite_by_own_profile_both_points` | прочий | 6.36 / 7.05 / 6.90 | 6.79 / 6.91 / 7.01 | 6.36 → 6.79 | +0.43 с, в разбросе кругов «до» |
| `PultUnchangedTest::test_ac10_external_pult_pytest_unchanged_share5` | разбиение | — / — / — | 4.78 / 6.65 / 5.10 | — → 4.78 | ≤ 10 с: да |
| `PultUnchangedTest::test_ac10_external_pult_pytest_unchanged_share7` | разбиение | — / — / — | 4.64 / 6.53 / 5.25 | — → 4.64 | ≤ 10 с: да |
| `PultUnchangedTest::test_ac10_external_pult_pytest_unchanged_share1` | разбиение | — / — / — | 5.75 / 6.30 / 6.05 | — → 5.75 | ≤ 10 с: да |
| `PultUnchangedTest::test_ac10_artel_unchanged_share1` | разбиение | — / — / — | 6.23 / 6.01 / 5.97 | — → 5.97 | ≤ 10 с: да |
| `PultUnchangedTest::test_ac10_external_pult_pytest_unchanged_share4` | разбиение | — / — / — | 4.24 / 5.86 / 4.49 | — → 4.24 | ≤ 10 с: да |
| `PullTest::test_ac7_pull_plank_by_own_profile_both_points` | прочий | 3.43 / 4.18 / 3.92 | 4.12 / 5.65 / 3.91 | 3.43 → 3.91 | +0.48 с, в разбросе кругов «до» |
| `PultUnchangedTest::test_ac10_artel_unchanged_share7` | разбиение | — / — / — | 4.81 / 5.44 / 5.06 | — → 4.81 | ≤ 10 с: да |
| `AmendTestsTest::test_ac6_amend_tests_by_own_profile_both_points` | прочий | 3.86 / 4.55 / 4.31 | 4.22 / 5.38 / 4.30 | 3.86 → 4.22 | +0.36 с, в разбросе кругов «до» |
| `PultUnchangedTest::test_ac10_artel_unchanged_share5` | разбиение | — / — / — | 5.02 / 5.21 / 5.14 | — → 5.02 | ≤ 10 с: да |
| `TestsWritingCollectTest::test_ac9_tests_writing_dry_collect_by_own_profile` | прочий | 3.60 / 4.23 / 4.19 | 4.27 / 5.10 / 4.15 | 3.60 → 4.15 | +0.55 с, в разбросе кругов «до» |
| `PultUnchangedTest::test_ac10_external_pult_pytest_unchanged_share2` | разбиение | — / — / — | 3.56 / 4.91 / 3.73 | — → 3.56 | ≤ 10 с: да |
| `PultUnchangedTest::test_ac10_artel_unchanged_share4` | разбиение | — / — / — | 4.15 / 4.74 / 4.63 | — → 4.15 | ≤ 10 с: да |
| `ApproveAcceptanceTest::test_ac2_approve_acceptance_full_suite_by_own_profile` | прочий | 3.30 / 3.94 / 3.73 | 3.71 / 4.66 / 3.69 | 3.30 → 3.69 | +0.39 с, в разбросе кругов «до» |
| `PultUnchangedTest::test_ac10_external_pult_pytest_unchanged_share6` | разбиение | — / — / — | 3.03 / 4.28 / 3.78 | — → 3.03 | ≤ 10 с: да |
| `InDevPlankTest::test_ac12_in_dev_plank_and_seed_repeats_by_own_profile` | прочий | 2.90 / 3.07 / 3.22 | 3.36 / 4.21 / 3.16 | 2.90 → 3.16 | +0.26 с, в разбросе кругов «до» |
| `PultUnchangedTest::test_ac10_artel_unchanged_share6` | разбиение | — / — / — | 3.12 / 4.19 / 3.31 | — → 3.12 | ≤ 10 с: да |
| `PultUnchangedTest::test_ac10_external_pult_pytest_unchanged_share3` | разбиение | — / — / — | 2.70 / 4.19 / 3.02 | — → 2.70 | ≤ 10 с: да |
| `TwoSidedTest::test_ac8_two_sided_by_own_profile_both_callers` | прочий | 3.36 / 3.61 / 3.51 | 3.92 / 3.72 / 3.48 | 3.36 → 3.48 | +0.12 с, в разбросе кругов «до» |
| `AutogateTest::test_ac1_autogate_full_suite_by_own_profile` | прочий | 2.82 / 3.02 / 3.11 | 3.19 / 3.87 / 3.35 | 2.82 → 3.19 | +0.37 с (13 %), тело то же |
| `PultUnchangedTest::test_ac10_artel_unchanged_share2` | разбиение | — / — / — | 3.57 / 3.82 / 3.69 | — → 3.57 | ≤ 10 с: да |
| `PultUnchangedTest::test_ac10_artel_unchanged_share3` | разбиение | — / — / — | 2.87 / 3.82 / 2.86 | — → 2.86 | ≤ 10 с: да |
| `SuiteRunTest::test_ac4_suite_run_by_own_profile_and_result_key` | прочий | 1.47 / 1.66 / 1.66 | 1.68 / 1.86 / 1.66 | 1.47 → 1.66 | +0.19 с, в разбросе кругов «до» |
| `PlankRunTest::test_ac5_plank_run_by_own_profile` | прочий | 1.44 / 1.43 / 1.45 | 1.41 / 1.45 / 1.44 | 1.43 → 1.41 | не длиннее |
| `NoTaskRunTest::test_ac11_run_without_task_unchanged` | прочий | 0.64 / 0.94 / 0.71 | 0.65 / 1.04 / 0.80 | 0.64 → 0.65 | +0.01 с, в разбросе кругов «до» |

#### `test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate`

До: круг 1 — загрузка в начале 3.78, 23 passed, 37 subtests passed in 219.42s (0:03:39); круг 2 — загрузка в начале 3.93, 23 passed, 37 subtests passed in 243.24s (0:04:03).
После: круг 1 — загрузка в начале 3.49, 42 passed, 37 subtests passed in 218.73s (0:03:38); круг 2 — загрузка в начале 3.89, 42 passed, 37 subtests passed in 245.51s (0:04:05).

| Тест | вид | до, к1/к2, с | после, к1/к2, с | мин. до → мин. после, с | итог |
|---|---|---|---|---|---|
| `Ac7RerunPrepareTest::test_ac7_branch_rerun_red_kinds` | старое имя | 21.63 / 26.87 | 4.77 / 4.66 | 21.63 → 4.66 | ≤ 10 с: да |
| `Ac7RerunPrepareTest::test_ac7_rerun_preparation_refusals` | старое имя | 22.31 / 26.64 | 4.52 / 5.82 | 22.31 → 4.52 | ≤ 10 с: да |
| `Ac11MandateTest::test_ac11_file_and_prefix_mandate_cover_findings` | старое имя | 21.60 / 22.57 | 5.13 / 5.58 | 21.60 → 5.13 | ≤ 10 с: да |
| `Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side` | старое имя | 15.65 / 17.53 | 4.04 / 3.98 | 15.65 → 3.98 | ≤ 10 с: да |
| `Ac4PrepareTest::test_ac4_git_preparation_failures_refuse` | старое имя | 13.97 / 15.94 | 3.79 / 4.53 | 13.97 → 3.79 | ≤ 10 с: да |
| `Ac6RerunTest::test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit` | прочий | 12.71 / 15.02 | 13.45 / 13.25 | 12.71 → 13.25 | +0.54 с, в разбросе кругов «до» |
| `Ac8VerdictByRecordTest::test_ac8_broken_unstable_and_flaky_on_base` | старое имя | 14.39 / 14.94 | 4.30 / 6.73 | 14.39 → 4.30 | ≤ 10 с: да |
| `Ac2PlaceTest::test_ac2_outcome_refusal_stops_before_review_rework_gate` | прочий | 11.63 / 11.37 | 11.02 / 11.50 | 11.37 → 11.02 | не длиннее |
| `Ac5PassToPassTest::test_ac5_retried_on_base_not_in_pass_to_pass` | прочий | 9.46 / 10.91 | 9.81 / 10.47 | 9.46 → 9.81 | +0.35 с, в разбросе кругов «до» |
| `Ac1OutOfBoundsTest::test_ac1_decide_skip_refusal_and_canary_no_gate` | прочий | 10.10 / 9.70 | 10.82 / 10.36 | 9.70 → 10.36 | +0.66 с (7 %), тело то же |
| `Ac1OutOfBoundsTest::test_ac1_artel_and_test_profile_no_gate` | прочий | 8.34 / 10.04 | 8.86 / 9.36 | 8.34 → 8.86 | +0.52 с, в разбросе кругов «до» |
| `Ac8VerdictByRecordTest::test_ac8_flaky_on_base_no_refusal` | разбиение | — / — | 4.62 / 6.94 | — → 4.62 | ≤ 10 с: да |
| `Ac13PassedRecordTest::test_ac13_passed_gate_journal_counts` | прочий | 5.83 / 6.00 | 5.24 / 6.25 | 5.83 → 5.24 | не длиннее |
| `Ac8VerdictByRecordTest::test_ac8_neighbour_red_in_same_file_does_not_redden_rerun` | прочий | 4.72 / 5.02 | 4.43 / 6.14 | 4.72 → 4.43 | не длиннее |
| `Ac8VerdictByRecordTest::test_ac8_unstable_after_change_general_refusal` | разбиение | — / — | 4.21 / 6.06 | — → 4.21 | ≤ 10 с: да |
| `Ac7RerunPrepareTest::test_ac7_rerun_unknown_outcome_refuses` | разбиение | — / — | 4.42 / 5.91 | — → 4.42 | ≤ 10 с: да |
| `Ac7RerunPrepareTest::test_ac7_rerun_timeout_refuses` | разбиение | — / — | 4.29 / 5.84 | — → 4.29 | ≤ 10 с: да |
| `Ac10OrderTest::test_ac10_findings_order_and_one_line_each` | прочий | 5.00 / 5.31 | 4.73 / 5.83 | 5.00 → 4.73 | не длиннее |
| `Ac11MandateTest::test_ac11_method_prefix_mandate_covers_variants` | разбиение | — / — | 4.94 / 5.65 | — → 4.94 | ≤ 10 с: да |
| `Ac11MandateTest::test_ac11_class_prefix_mandate_covers` | разбиение | — / — | 5.29 / 5.61 | — → 5.29 | ≤ 10 с: да |
| `Ac9CompareTest::test_ac9_vitest_records_findings_and_non_findings` | прочий | 4.85 / 5.33 | 4.33 / 5.47 | 4.85 → 4.33 | не длиннее |
| `Ac3RunsTest::test_ac3_full_suite_on_base_and_head_checkouts_fresh` | прочий | 4.75 / 5.45 | 5.02 / 5.06 | 4.75 → 5.02 | +0.27 с, в разбросе кругов «до» |
| `Ac5PassToPassTest::test_ac5_no_tests_on_base_empty_pass_to_pass` | прочий | 5.16 / 5.39 | 4.89 / 5.42 | 5.16 → 4.89 | не длиннее |
| `Ac11MandateTest::test_ac11_role_autocommitted_answer_does_not_cover` | прочий | 4.77 / 5.38 | 4.21 / 4.54 | 4.77 → 4.21 | не длиннее |
| `Ac4PrepareTest::test_ac4_side_head_timeout_refuses_naming_head` | разбиение | — / — | 4.37 / 5.32 | — → 4.37 | ≤ 10 с: да |
| `Ac9CompareTest::test_ac9_one_finding_per_id_senior_kind` | прочий | 4.75 / 5.20 | 4.32 / 4.84 | 4.75 → 4.32 | не длиннее |
| `Ac11MandateTest::test_ac11_other_file_mandate_does_not_cover` | разбиение | — / — | 4.49 / 5.15 | — → 4.49 | ≤ 10 с: да |
| `Ac9CompareTest::test_ac9_junit_records_findings` | прочий | 4.69 / 4.87 | 4.12 / 5.08 | 4.69 → 4.12 | не длиннее |
| `Ac11MandateTest::test_ac11_prefix_needs_separator_after_it` | прочий | 5.02 / 4.67 | 4.47 / 4.92 | 4.67 → 4.47 | не длиннее |
| `Ac7RerunPrepareTest::test_ac7_branch_rerun_retried_is_red` | разбиение | — / — | 4.45 / 5.01 | — → 4.45 | ≤ 10 с: да |
| `Ac7RerunPrepareTest::test_ac7_rerun_base_skipped_refuses` | разбиение | — / — | 4.47 / 4.94 | — → 4.47 | ≤ 10 с: да |
| `Ac4PrepareTest::test_ac4_side_base_timeout_refuses_naming_base` | разбиение | — / — | 4.15 / 4.83 | — → 4.15 | ≤ 10 с: да |
| `Ac6RerunTest::test_ac6_skipped_on_branch_not_rerun` | прочий | 4.19 / 4.65 | 4.51 / 4.80 | 4.19 → 4.51 | +0.32 с, в разбросе кругов «до» |
| `Ac7RerunPrepareTest::test_ac7_branch_rerun_missing_is_red` | разбиение | — / — | 4.79 / 4.62 | — → 4.62 | ≤ 10 с: да |
| `Ac7RerunPrepareTest::test_ac7_branch_rerun_skipped_is_red` | разбиение | — / — | 4.69 / 4.41 | — → 4.41 | ≤ 10 с: да |
| `Ac7RerunPrepareTest::test_ac7_branch_rerun_error_is_red` | разбиение | — / — | 4.46 / 4.57 | — → 4.46 | ≤ 10 с: да |
| `Ac4PrepareTest::test_ac4_git_base_checkout_failure_refuses` | разбиение | — / — | 3.90 / 4.50 | — → 3.90 | ≤ 10 с: да |
| `Ac7RerunPrepareTest::test_ac7_rerun_base_record_missing_refuses` | разбиение | — / — | 4.46 / 4.44 | — → 4.44 | ≤ 10 с: да |
| `Ac4PrepareTest::test_ac4_side_head_unknown_refuses_naming_head` | разбиение | — / — | 4.28 / 4.40 | — → 4.28 | ≤ 10 с: да |
| `Ac4PrepareTest::test_ac4_git_head_checkout_failure_refuses` | разбиение | — / — | 3.95 / 4.37 | — → 3.95 | ≤ 10 с: да |
| `Ac4PrepareTest::test_ac4_git_head_not_read_refuses` | разбиение | — / — | 3.73 / 4.22 | — → 3.73 | ≤ 10 с: да |
| `Ac2PlaceTest::test_ac2_text_gate_refusal_first_no_outcome_runs` | прочий | 3.75 / 4.11 | 3.80 / 3.92 | 3.75 → 3.80 | +0.05 с, в разбросе кругов «до» |

#### `test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow`

До: круг 1 — загрузка в начале 3.33, 23 passed, 14 subtests passed in 203.83s (0:03:23); круг 2 — загрузка в начале 3.87, 23 passed, 14 subtests passed in 160.08s (0:02:40).
После: круг 1 — загрузка в начале 3.79, 31 passed, 14 subtests passed in 156.19s (0:02:36); круг 2 — загрузка в начале 3.81, 31 passed, 14 subtests passed in 156.38s (0:02:36).

| Тест | вид | до, к1/к2, с | после, к1/к2, с | мин. до → мин. после, с | итог |
|---|---|---|---|---|---|
| `SignalDepthTest::test_ac9_each_signal_alone_switches_to_full_review` | старое имя | 35.20 / 29.00 | 3.23 / 3.25 | 29.00 → 3.23 | ≤ 10 с: да |
| `AcceptAuditFailTest::test_ac20_fail_verdict_needs_flag_in_both_forms` | старое имя | 31.26 / 20.51 | 10.04 / 8.81 | 20.51 → 8.81 | ≤ 20 с: да |
| `ReturnCounterTest::test_ac17_reject_does_not_reset_return_counter` | прочий | 15.61 / 14.72 | 11.60 / 13.35 | 14.72 → 11.60 | не длиннее |
| `ReturnCounterTest::test_ac17_spec_audit_command_does_not_reset_return_counter` | прочий | 14.92 / 11.91 | 10.34 / 11.81 | 11.91 → 10.34 | не длиннее |
| `FailReturnTest::test_ac14_two_fails_return_third_goes_to_gate_with_return_reason` | прочий | 11.53 / 8.76 | 9.75 / 9.58 | 8.76 → 9.58 | +0.82 с, в разбросе кругов «до» |
| `AuditExitTest::test_ac13_pass_and_concerns_lead_to_gate_draft_stays` | прочий | 10.68 / 8.56 | 8.95 / 9.23 | 8.56 → 8.95 | +0.39 с, в разбросе кругов «до» |
| `FreshnessTest::test_ac15_previous_visit_pass_does_not_advance` | прочий | 10.50 / 7.11 | 8.17 / 8.05 | 7.11 → 8.05 | +0.94 с, в разбросе кругов «до» |
| `AcceptAuditFailTest::test_ac20_fail_verdict_short_form_needs_flag` | разбиение | — / — | 9.51 / 8.00 | — → 8.00 | ≤ 20 с: да |
| `GateVerdictTest::test_ac19_show_status_auto_name_journal_verdict` | прочий | 8.31 / 7.32 | 6.46 / 6.30 | 7.32 → 6.30 | не длиннее |
| `SignalDepthTest::test_ac8_behavior_section_full_review_and_no_signal_short_review` | прочий | 7.74 / 6.39 | 6.09 / 5.95 | 6.39 → 5.95 | не длиннее |
| `AuditEscalationTest::test_ac18_escalate_status_escalates_and_returns_to_audit` | прочий | 6.71 / 4.55 | 3.92 / 4.44 | 4.55 → 3.92 | не длиннее |
| `SignalDepthTest::test_ac9_path_category_share0_switches_to_full_review` | разбиение | — / — | 6.21 / 5.92 | — → 5.92 | ≤ 10 с: да |
| `SignalDepthTest::test_ac9_path_category_share1_switches_to_full_review` | разбиение | — / — | 5.75 / 5.98 | — → 5.75 | ≤ 10 с: да |
| `ShaBindingTest::test_ac16_spec_sha_mismatch_refuses_and_match_passes` | прочий | 5.36 / 4.97 | 4.31 / 4.82 | 4.97 → 4.31 | не длиннее |
| `EntryChecksKeptTest::test_ac4_questions_escalate_from_spec_writing_and_bad_spec_refused` | прочий | 5.28 / 3.44 | 3.64 / 3.61 | 3.44 → 3.61 | +0.17 с, в разбросе кругов «до» |
| `AuditorBriefTest::test_ac7_brief_carries_inputs_and_entry_sha_not_questions_or_logs` | прочий | 5.13 / 4.98 | 4.48 / 4.43 | 4.98 → 4.43 | не длиннее |
| `AcceptAuditFailTest::test_ac20_flag_outside_spec_gate_refused_and_no_verdict_passes` | прочий | 4.77 / 2.56 | 2.17 / 1.83 | 2.56 → 1.83 | не длиннее |
| `SpecBudgetTest::test_ac5_spec_budget_applies_on_entry_to_audit_and_on_approve` | прочий | 4.70 / 3.64 | 4.06 / 3.89 | 3.64 → 3.89 | +0.25 с, в разбросе кругов «до» |
| `AuditArtifactCommitTest::test_ac11_auditor_step_commits_spec_audit_but_not_other_names` | прочий | 4.32 / 2.91 | 3.29 / 3.13 | 2.91 → 3.13 | +0.22 с, в разбросе кругов «до» |
| `ShaBindingTest::test_ac16_entry_journal_carries_spec_content_sha_not_ref_head` | прочий | 3.74 / 3.74 | 3.37 / 3.56 | 3.74 → 3.37 | не длиннее |
| `SignalDepthTest::test_ac9_answer_mandate_switches_to_full_review` | разбиение | — / — | 3.64 / 3.71 | — → 3.64 | ≤ 10 с: да |
| `EntryRouteTest::test_ac2_task_with_tz_goes_to_spec_audit_not_spec_gate` | прочий | 3.59 / 2.34 | 2.45 / 2.30 | 2.34 → 2.30 | не длиннее |
| `ShaBindingTest::test_ac16_spec_changed_in_audit_step_refuses_with_both_sha` | прочий | 3.55 / 3.52 | 2.96 / 3.24 | 3.52 → 2.96 | не длиннее |
| `RequiredArtifactTest::test_ac12_auditor_step_without_spec_audit_is_not_success` | прочий | 3.54 / 2.49 | 2.89 / 2.69 | 2.49 → 2.69 | +0.20 с, в разбросе кругов «до» |
| `SignalDepthTest::test_ac9_budget_44_keeps_short_review` | разбиение | — / — | 3.53 / 3.19 | — → 3.19 | ≤ 10 с: да |
| `SignalDepthTest::test_ac9_plan_appendix_switches_to_full_review` | разбиение | — / — | 3.07 / 3.26 | — → 3.07 | ≤ 10 с: да |
| `SignalDepthTest::test_ac9_protected_path_switches_to_full_review` | разбиение | — / — | 3.24 / 3.11 | — → 3.11 | ≤ 10 с: да |
| `SignalDepthTest::test_ac9_budget_45_switches_to_full_review` | разбиение | — / — | 3.18 / 3.17 | — → 3.17 | ≤ 10 с: да |
| `SpecAuditCommandTest::test_ac21_spec_audit_command_from_gate_and_refusal_elsewhere` | прочий | 2.66 / 2.90 | 2.18 / 1.87 | 2.66 → 1.87 | не длиннее |
| `FreshnessTest::test_ac15_spec_audit_written_by_analyst_does_not_advance` | прочий | 2.51 / 2.04 | 2.06 / 2.30 | 2.04 → 2.06 | +0.02 с, в разбросе кругов «до» |
| `EntryRouteTest::test_ac3_task_without_tz_goes_to_spec_gate_as_before` | прочий | 1.80 / 1.54 | 1.51 / 1.44 | 1.54 → 1.44 | не длиннее |

#### `test_01m52eefna1wh31962hvnt0yz9_pytest_own_places`

До: круг 1 — загрузка в начале 3.47, 12 passed, 120 subtests passed in 62.70s (0:01:02); круг 2 — загрузка в начале 3.70, 12 passed, 120 subtests passed in 60.16s (0:01:00).
После: круг 1 — загрузка в начале 3.98, 21 passed, 120 subtests passed in 61.68s (0:01:01); круг 2 — загрузка в начале 3.97, 21 passed, 120 subtests passed in 61.15s (0:01:01).

| Тест | вид | до, к1/к2, с | после, к1/к2, с | мин. до → мин. после, с | итог |
|---|---|---|---|---|---|
| `PytestOwnEnvironmentTest::test_ac3_home_removed_after_timeout_and_exception` | старое имя | 19.69 / 20.43 | 4.47 / 4.48 | 19.69 → 4.47 | ≤ 10 с: да |
| `PytestOwnProcessGroupTest::test_ac6_child_gone_after_timeout_and_exception` | старое имя | 19.79 / 19.57 | 4.56 / 4.53 | 19.57 → 4.53 | ≤ 10 с: да |
| `PytestOwnEnvironmentTest::test_ac2_env_only_allowed_profile_env_and_pycache` | прочий | 7.88 / 6.42 | 7.32 / 7.68 | 6.42 → 7.32 | +0.90 с, в разбросе кругов «до» |
| `PytestOwnEnvironmentTest::test_ac3_home_fresh_and_removed_after_completion` | старое имя | 7.04 / 6.17 | 1.60 / 1.68 | 6.17 → 1.60 | ≤ 10 с: да |
| `PytestOwnProcessGroupTest::test_ac6_child_gone_after_timeout_and_exception_share3` | разбиение | — / — | 6.98 / 6.65 | — → 6.65 | ≤ 10 с: да |
| `PytestOwnEnvironmentTest::test_ac3_home_removed_after_timeout_and_exception_share3` | разбиение | — / — | 6.78 / 6.72 | — → 6.72 | ≤ 10 с: да |
| `PytestOwnFullSuiteTest::test_ac8_saved_gate_result_not_reused_for_other_workdir_or_env` | прочий | 5.64 / 5.04 | 3.78 / 3.48 | 5.04 → 3.48 | не длиннее |
| `PytestOwnEnvironmentTest::test_ac3_home_removed_after_timeout_and_exception_share1` | разбиение | — / — | 4.51 / 4.55 | — → 4.51 | ≤ 10 с: да |
| `PytestOwnEnvironmentTest::test_ac3_home_removed_after_timeout_and_exception_share2` | разбиение | — / — | 4.47 / 4.55 | — → 4.47 | ≤ 10 с: да |
| `PytestOwnProcessGroupTest::test_ac6_child_gone_after_timeout_and_exception_share2` | разбиение | — / — | 4.40 / 4.47 | — → 4.40 | ≤ 10 с: да |
| `PytestOwnProcessGroupTest::test_ac6_child_gone_after_timeout_and_exception_share1` | разбиение | — / — | 4.46 / 4.46 | — → 4.46 | ≤ 10 с: да |
| `PytestOwnEnvironmentTest::test_ac3_home_fresh_and_removed_after_completion_share3` | разбиение | — / — | 2.55 / 2.57 | — → 2.55 | ≤ 10 с: да |
| `PytestOwnEnvironmentTest::test_ac3_home_fresh_and_removed_after_completion_share2` | разбиение | — / — | 1.95 / 1.72 | — → 1.72 | ≤ 10 с: да |
| `PytestOwnEnvironmentTest::test_ac3_home_fresh_and_removed_after_completion_share1` | разбиение | — / — | 1.83 / 1.73 | — → 1.73 | ≤ 10 с: да |
| `PytestOwnFullSuiteTest::test_ac5_missing_long_lived_dir_means_no_tests` | прочий | 1.00 / 1.04 | 0.61 / 0.63 | 1.00 → 0.61 | не длиннее |
| `PytestOwnWorkdirOutsideTest::test_ac7_workdir_link_outside_refused_without_run` | прочий | 0.53 / 0.51 | 0.52 / 0.43 | 0.51 → 0.43 | не длиннее |
| `PytestOwnArgvTest::test_ac4_argv_profile_command_gate_args_cwd_workdir` | прочий | 0.34 / 0.29 | 0.29 / 0.24 | 0.29 → 0.24 | не длиннее |
| `SuiteResultKeyTest::test_ac8_pult_pytest_profile_key_equals_command_key` | прочий | 0.18 / 0.20 | 0.11 / 0.12 | 0.18 → 0.11 | не длиннее |
| `SuiteResultKeyTest::test_ac8_key_differs_by_runner_workdir_env` | прочий | 0.18 / 0.16 | 0.15 / 0.16 | 0.16 → 0.15 | не длиннее |
| `PytestOwnArgvTest::test_ac5_full_suite_targets_translated_to_workdir` | прочий | 0.17 / 0.16 | 0.15 / 0.13 | 0.16 → 0.13 | не длиннее |
| `SuiteResultKeyTest::test_ac5_base_key_drops_long_lived_dir` | прочий | 0.04 / 0.03 | 0.03 / 0.03 | 0.03 → 0.03 | не длиннее |


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
- Замер «до» требует временно положить файл базы на место файла ветки;
  дважды (3419c85d, 0a75956f) шаг кончился посреди такого замера, и
  WIP-коммит пульта (`checkpoint.py`) унёс в ветку задачи версию базы —
  разбиение пропало молча, восстановлено коммитами 6e22f4a0, 4ee6d73c.
  Не хватает команды пульта «замер файла на базе» в отдельной копии
  (как `plank-run`), не трогающей рабочую копию задачи.
