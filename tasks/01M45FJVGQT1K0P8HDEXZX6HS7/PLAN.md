---
task: 01M45FJVGQT1K0P8HDEXZX6HS7
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Этап 3 ADR-0021, часть 1 из 3 — профиль тестов проекта и проверки тестов на repo_context

## Подход

Профиль тестов — необязательное поле `test_profile` записи `targets.yaml`.
Разбор и проверка — `orchestrator/targets.py` (`PROFILE_FIELDS`,
`_check_profile`): неизвестное подполе, отсутствие обязательного, неверный
вид, `report` вне `junit-xml`, шаблон без `<id>`/`<name>` — `TargetsError`
с `test_profile` и подполем в причине. `report` и `install` проверяются, но
пультом не исполняются.

Чтение — `repo_context.profile_of(target)` рядом с `resolve`: три исхода
(`PROFILE_PRESENT` со значениями, `PROFILE_ABSENT`, `PROFILE_UNREAD` с
причиной). Профиль артели читается из её записи, как у любого проекта.

Одно правило на все места проверок — новый модуль
`orchestrator/project_profile.py`, `decide(target)`:
- `repo_context.resolve` вернул `None` — отказ «контекст проекта не
  разрешён» (`unresolved=True`);
- профиль есть — `Profile` (команда, маски `weakening_scope` /
  `mutation_claim_scope`, каталог и шаблон долгоживущего файла);
- профиль не прочитан, либо его нет у артели — отказ с `targets.yaml` и
  `test_profile` в причине (fail-closed, ADR-0002);
- профиля нет у внешнего проекта — `skip`; место проверки пишет запись
  `journal_skip` («проверка тестов не выполняется: <проверка>», причина
  «у проекта `<имя>` нет test_profile в targets.yaml»).

Отказ перехода по профилю пишется действием
`переход отклонён: профиль тестов проекта` класса «чинит Оператор»
(`refusal_classes`). Маски: `*` — внутри сегмента, `**` — любое число
сегментов, включая ноль (`project_profile.mask_matches`). Команда прогона:
гейт передаёт `Profile.command` как есть в
`acceptance._pytest_command(..., command=...)`; там, при сборке команды
прогона, первый элемент `python3` заменяется на
`stack.pytest_python_executable()`, флаги пульта (без кеша,
`pytest-timeout`) добавляются как раньше. Интерпретатор не резолвится в
гейте: гейт, чей прогон не состоится (или подменён в тесте), venv не ищет. Префикс и признак долгоживущего файла —
`guard.long_lived_path_prefix` / `is_long_lived_test_path` с аргументами
каталога и шаблона; умолчания равны значениям артели и остаются для
потребителей вне гейтов тестов (чекпоинт, бриф, миссия роли).

Прогон планки и долгоживущих (требование 6) — одна ветка для любого
проекта: `workspace.ensure` + `workspace.on_task_branch` (без жёсткого
`config.DEFAULT_TARGET`), прогон в рабочей копии задачи; ветка
«прогон в `config.ROOT`» удалена в `advance_gates/acceptance.py` и
`advance_gates/tests_writing.py`. Нет рабочей копии — отказ перехода; у
автогейта — автогейт не проводится, запись в журнал.

Канареечная задача: отбор `is_canary` не тронут (ANSWER-1, вопрос 2).

Бюджет SPEC ($50, потолок $100 задан Оператором) не переоцениваю:
`budget_usd` в PLAN не ставлю.

## Шаги

1. `targets.py` — поле `test_profile` и его проверка; `repo_context.
   profile_of` — три исхода.
2. `project_profile.py` — `Profile`, `mask_matches`, `decide`,
   `journal_skip`, `REFUSAL_ACTION` (+ строка в `refusal_classes.py`).
3. `scripts/guard.py` — префикс/признак долгоживущего файла и
   `long_lived_plank_errors` по каталогу и шаблону профиля;
   `acceptance.py` — команда из профиля в `run`/`collect`.
4. Перевод мест таблицы требования 5 на `decide` (таблица ниже), снятие
   развилок по `config.DEFAULT_TARGET` / `is_artel`, единая ветка прогона
   (требование 6).
5. Тесты: долгоживущие файлы задачи (`tests/test_01m45fjvgqt1k0p8hdexzx6hs7_*`,
   test_author) зелёные; свои — `tests/test_project_profile.py`;
   дополнение фикстур профилем артели (перечень ниже).
6. Приложения к `targets.yaml` и `tests/test_invariants.py` (требование 7),
   проверка `git apply --check`, прогон инвариантов с приложениями.

Места таблицы требования 5 (развилка по проекту → `project_profile.decide`):

| Проверка | Где теперь |
|---|---|
| Неослабление, переход `in_dev → verifying` | `advance_gates/test_integrity.py::_test_integrity_gate` (`scope=profile.in_weakening_scope`) |
| Раздел изменённых утверждений пакета ревью | `orchestrator/review.py` (~627: раздел/пометка о пропуске/отказ) |
| Неослабление, шаг гейта мержа | `fsm_merge_gate.py` ~127 |
| «Ловит мутацию» | `advance_gates/review.py::_mutation_claim_gate` ~208 (`mutation_claim_scope`) |
| Долгоживущие файлы и строки группы на выходе `tests_writing` | `fsm_advance.py` ~396-460, `advance_gates/tests_writing.py` |
| Сухой сбор планки | `advance_gates/tests_writing.py` (рабочая копия задачи, `command`) |
| Перечень сумм и лок планки | `advance_gates/acceptance.py` ~62, ~100 |
| Прогон приёмки | `advance_gates/acceptance.py::_acceptance_run_body` ~269 |
| Автогейт приёмки | `fsm_advance.py` ~195 |
| Лок планки и перечень на мерже | `fsm_merge_gate.py` ~1112, ~1137 |
| Строки группы в `amend-tests` | `amend.py` ~184-220 |

Сверх таблицы новых мест с развилкой по проекту в проверках тестов этой
части не нашёл. Оставшаяся развилка `advance_gates/review.py:355`
(`store.task_target(...) != config.DEFAULT_TARGET`) — вне проверок тестов,
SPEC относит её к части 3 («Не входит»).

AC-10 — вывод поиска по местам таблицы после перевода
(`grep -n "DEFAULT_TARGET\|is_artel"` по изменённым модулям):

```
orchestrator/advance_gates/review.py:355:    if store.task_target(conn, task_id) != config.DEFAULT_TARGET:   # часть 3, не место таблицы
orchestrator/fsm_merge_gate.py:90/496/528/571/913/989: repo_context.is_artel(ctx)   # шаги мержа только пульта (карта, RETRO, снимок), не проверки тестов
orchestrator/review.py:233, 498: workspace.repo(config.DEFAULT_TARGET)   # не сравнение
orchestrator/advance_gates/acceptance.py:37: workspace.repo(config.DEFAULT_TARGET)   # не сравнение
```

Счёт сравнений с `DEFAULT_TARGET` и вызовов `is_artel` (база main → HEAD,
ожидалось снять): `test_integrity.py` 1→0 (1); `review.py` 1→0 (1);
`fsm_merge_gate.py` 8→6 (2); `advance_gates/review.py` 2→1 (1);
`advance_gates/tests_writing.py` 3→0 (3); `fsm_advance.py` 2→0 (2);
`advance_gates/acceptance.py` 2→0 (2); `amend.py` 1→0 (1). Вызов
`workspace.on_task_branch` в `advance_gates/tests_writing.py` жёсткого
`config.DEFAULT_TARGET` не несёт.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1, 2 |
| 3 | 2, 4 |
| 4 | 2, 4, 6 |
| 5 | 4 |
| 6 | 3, 4 |
| 7 | 6 |
| 8 | 5 |

## Тесты

Свои (заявки «Ловит мутацию», каждая проверена временной мутацией —
тест красный, код возвращён): `tests/test_project_profile.py` — маски
(`*` в сегменте, `**` в середине и в хвосте, буквальная точка), команда не
на Python идёт как есть через `acceptance._pytest_command` (метод
`test_non_python_command_passes_as_is` переведён с удалённого
`Profile.pytest_command` на `_pytest_command`; файл новый в ветке, мутация
«замена первого элемента безусловно» перепроверена — красный), области из
своих подполей, префикс и признак
долгоживущего файла по нестандартному каталогу и шаблону. Требования 1-6
по переходам покрывают долгоживущие файлы задачи
`tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py`,
`tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py` и планка.

**Меняемое поведение / смена ожиданий существующих тестов.** Раздела
«Меняемое поведение» в SPEC нет, мандата Оператора на смену ожиданий не
требуется: ни одно утверждение существующего теста не изменено. Тесты,
закреплявшие пропуск проверок у внешнего проекта
(`tests/test_mutation_claim_gate.py:71`,
`tests/test_test_integrity_gate.py:364`,
`tests/test_fsm_advance_tests_writing_test_groups.py:136, 229`), сохраняют
утверждения (`assertIsNone` / пустой список ошибок): внешний проект в них
теперь объявлен в `targets.yaml` без профиля (`tests/sandbox.py::
declared_without_profile`), и пропуск идёт по правилу требования 3.

**Дополнение фикстур профилем артели и прочие правки фикстур** (утверждения
не меняются):
- `tests/sandbox.py` — `ARTEL_TEST_PROFILE`, `seed_artel_targets`,
  `declared_without_profile`, `declare_target`; `TmpRootTest`/
  `RealGitSandbox` сеют запись артели с профилем (у `RealGitSandbox` —
  под `.artel/`, не в дереве репозитория песочницы).
- Запись артели с профилем в своей декларации песочницы:
  `tests/test_git_fixation.py`, `tests/test_plan_appendix.py`,
  `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`,
  `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`,
  `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`,
  `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`,
  `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`,
  `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`,
  `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`,
  `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`,
  `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py` (там же
  `config.TARGETS` песочницы возвращён в дерево главной копии — её
  сценарий коммитит правку декларации).
- Запись артели с профилем (`ARTEL_TEST_PROFILE`) в декларации, которую
  песочница пишет сама поверх посеянной (итерация после возврата из
  `verifying`: в CI эти песочницы читали свою запись без профиля):
  `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py` (`MainCiSandbox`,
  `COPY_CODE`), `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`
  (`AppliedAppendixMergeSandbox`).
- Посев `seed_artel_targets()` в собственных песочницах:
  `tests/test_advance_guard.py` (`AdvanceGuardTest.setUp` — патчит
  `config.TARGETS` на несуществующий файл песочницы),
  `tests/test_review_freshness.py`, `tests/test_auto_cycle.py`,
  `tests/test_agent_prompt.py`, `tests/test_fsm_branch_correct_status_reads.py`,
  `tests/test_acceptance_tests_flow.py` (`LockTest`),
  `tests/test_review_package.py` (`CmdRunReviewPackageTest` — раньше читал
  боевой `targets.yaml` пульта, теперь подменяет `config.TARGETS`).
- Временная декларация артели с профилем (`tests/sandbox.py::
  declared_artel_profile`) вместо боевого `targets.yaml`:
  `tests/test_fsm_advance_tests_writing_test_groups.py`
  (`AmendGroupLineTest.errors`).
- Посеянная запись артели убрана там, где предмет — сам файл или его
  отсутствие (`config.TARGETS.unlink()` в `setUp`):
  `tests/test_multitarget.py`, `tests/test_repo_context.py`.
- Внешний проект объявлен в `targets.yaml` без профиля
  (`declared_without_profile` / `declare_target`; необъявленному гейт
  теперь отказывает — контекст не разрешён):
  `tests/test_mutation_claim_gate.py`, `tests/test_test_integrity_gate.py`,
  `tests/test_fsm_advance_tests_writing_test_groups.py`,
  `tests/test_docs_dir_layout.py`, `tests/test_external_code_copy_refusal.py`,
  `tests/test_long_lived_manifest.py`,
  `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py` (`OutOfScopeTest`).
- `origin` у песочницы (рабочая копия задачи артели на выходе
  `tests_writing` заводится от базы в `origin`): `tests/test_amend.py`,
  `tests/test_id_format_guard.py`, `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`.
- SPEC до A4 на диске к выходу из `in_dev` (прогон приёмки в рабочей копии
  без планки читает SPEC — требование 6):
  `tests/test_review_freshness.py` (`ReviewFreshnessScenarioTest.setUp`,
  `PRE_A4_SPEC_MD`),
  `tests/test_auto_cycle.py` (`AutoCycleTest.setUp`),
  `tests/test_branch_freshness_gate.py` (`setup_recording`; там же
  черновик запроса на слияние выключен: посеянная запись несёт
  `forge: github`, а черновик зовёт `commits_behind`, которого сценарий
  не ждёт).
- Черновик запроса на слияние выключен (`github_adapter._is_github_target`
  → `False`) в `tests/test_fsm_map_conflict_autoresolve.py`
  (`MapConflictAutoResolveTest.setUp`): посеянная запись артели несёт
  `forge: github`, черновик зовёт `gh` тем же `subprocess.run`, что
  сценарий подменил под регенератор карты и считает
  (`regen.assert_called_once`); без записи черновика не было.
- Строка группы в фикстуре планки (гейт строк группы теперь видит планку
  ветки задачи, а не копию пина): `tests/test_id_format_guard.py`
  (`TEST_CLEAN`), `tests/test_step_refixation.py`.
- Рабочая копия задачи артели: `tests/test_acceptance_tests_flow.py::
  LockTest.commit_feature_code` коммитит код в рабочей копии задачи (ветку
  держит она). На ревью: в методе
  `tests/test_acceptance_tests_flow.py::AcceptanceRunTest::test_no_acceptance_tests_directory_does_not_block_legacy_tasks`
  добавлена строка сценария — SPEC с `skip_tests` (случай, названный
  докстрингом метода); утверждения метода не тронуты. Без неё задача
  артели с SPEC v2 без `skip_tests` и без планки теперь отклоняется
  «планка не найдена в источнике», как внешний проект (требование 6).
  Изменённый метод несёт в докстринге заявку «Ловит мутацию» (гейт
  заявки мутации); проверена временной мутацией — `skip_tests` не
  учитывается в `advance_gates/acceptance.py::_missing_plank_refuses`,
  тест красный, код возвращён. Прочие изменённые методы `tests/test_*.py`
  ветки сверены `guard.test_functions_without_mutation_claim` против
  merge-base — без заявки нет ни одного.

## Проверено исполнением

Итерация после возврата из `verifying` (CI 87fdc026 красный с наложенными
приложениями). Причина: локально рабочая копия несла незакоммиченный
`targets.yaml` с профилем, а часть песочниц не несла своей записи артели с
профилем (или писала свою без него). Прогоны ниже — с наложенными обоими
приложениями (`git apply` блоков PLAN), без иных незакоммиченных правок
`targets.yaml`; после прогонов приложения сняты (`git checkout`), рабочая
копия их не несёт. Временных файлов `.chunk*`, `.runchunk.py`,
`.dbgrun.py` в корне рабочей копии нет (`find -maxdepth 1 -name '.*'`).

- Файлы из причины возврата, каждый `python3 -m pytest <файл>
  -p no:cacheprovider -p timeout -o timeout=120`: `tests/test_invariants.py`
  — 74 passed; `tests/test_review_freshness.py`,
  `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`,
  `tests/test_ci_status_kind_gate.py`,
  `tests/test_fsm_map_conflict_autoresolve.py`,
  `tests/test_advance_guard.py` — зелёные (вместе с `test_doctor`,
  `test_review_registry_gate`, `test_verifying_ceiling`,
  `test_branch_freshness_gate` — 165 passed).
- `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`: 9 тестов гейта мержа
  из причины возврата краснели на «нет test_profile» — их песочница пишет
  свою запись артели, теперь с профилем. Локально все 16 сценариев этого
  файла, зовущие `approve`/`pin --to`, отказывают «команда недоступна
  процессу роли developer» (признак шага роли, на базе так же) — обходить
  признак не стал, итог этих 9 покажет CI.
- Класс «песочница подменяет `config.TARGETS` без записи артели с
  профилем»: перебраны все файлы `tests/`, где есть `config.TARGETS`, без
  `seed_artel_targets`/`ARTEL_TEST_PROFILE`; все прогнаны — зелёные
  (75 passed и 174 passed двумя пачками).
- Модули прогона команды: `test_project_profile`, `test_acceptance*`,
  `test_fsm_advance_tests_writing_*`, `test_long_lived_*`,
  `test_pull_long_lived_plank`, `test_fsm_autogate*`, `test_amend*`,
  `test_acceptance_tests_flow`, `test_mutation_claim_gate`,
  `test_test_integrity_gate`, долгоживущие файлы задачи — зелёные.
- Планка: `artel.py plank-run 01M45FJVGQT1K0P8HDEXZX6HS7` — 31 passed.
- `git apply --check` обоих приложений на чистом дереве HEAD —
  применяются (блоки приложений не менялись).

Прежняя итерация:

- Долгоживущие файлы задачи: `python3 -m pytest
  tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py
  tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py` — 13 passed.
- Планка: `artel.py plank-run 01M45FJVGQT1K0P8HDEXZX6HS7
  test_profile_gates_git.py` — 23 passed.
- Модули с правленными фикстурами (по файлу, передний план): зелёные
  `test_review_freshness`, `test_id_format_guard`, `test_plan_appendix`,
  `test_auto_cycle`, `test_artifact_escalation_marker`,
  `test_branch_freshness_gate`, `test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after`,
  `test_01m42pencs26d0656x8fr7dfa7_project_area` (30 passed),
  `test_project_profile` (7 passed), `test_step_refixation`.
- Красные и на базе ветки (0b3257c7) одинаково, к задаче не относятся
  (окружение): `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py` (16),
  `tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`,
  `tests/test_main_ci_line.py::FixesMainArgTest::test_flag_without_reason_is_refused`.
- `tests/test_invariants.py`: без приложений — 18 failed (артель без
  профиля получает отказ — требование 4, ожидаемо); с обоими приложениями —
  74 passed.
- `git apply --check` обоих приложений на чистом дереве HEAD — применяются.

## Влияние на систему

- Гейты целостности тестов не ослаблены: у артели все проверки таблицы
  выполняются с прежними значениями (AC-3 планки), без профиля артели —
  отказ, не пропуск; неразрешённый контекст — отказ. Прогон планки артели
  перестал идти в главной копии пульта (проверял код пина) — теперь
  проверяется код задачи; это ужесточение: строки группы и отсутствие
  планки у SPEC v2 без `skip_tests` теперь видны и у артели.
- Инвариант 38 (`docs/invariants.md`): область `tests/**/*.py` та же,
  только читается из профиля. Формулировка не менялась.
- Внимание к мержу: после мержа кода и до наложения приложения к
  `targets.yaml` у артели нет профиля — проверки тестов отказывают.
  Приложение накладывается пультом в том же мерже (гейт приложений PLAN),
  отдельного окна нет. Если приложение не легло — задача остаётся на гейте
  мержа.
- Откат — revert merge-коммита задачи (приложения в нём же).
- `merge_after` не меняю.

## Риски

- `targets.yaml` пульта без профиля (холодный старт со старым файлом) —
  все переходы задач артели с проверками тестов отказывают с причиной
  «нет поля test_profile в targets.yaml»; лечится одной правкой файла.
- Тесты без песочницы `config.TARGETS` читают боевой `targets.yaml`
  пульта; до наложения приложения у артели там нет профиля, и такие
  тесты на ветке без приложения краснеют (два найденных класса переведены
  на свою декларацию — см. «Тесты»). CI ветки и прогон на мерже идут с
  наложенными приложениями (`scripts/plan_appendix_ci.py`), полный набор
  в шаге не гонялся (правило шага) — остаток такого класса покажет CI.
- `RealGitSandbox` хранит `targets.yaml` под `.artel/` — сценарий, который
  коммитит декларацию в дерево песочницы, должен вернуть путь сам (как
  `ProjectAreaSandbox`).

## Приложение: targets.yaml

Профиль тестов артели (требование 7): только блок `test_profile` записи
`artel`, `no_paths` и комментарий записи не меняются.

```diff
diff --git a/targets.yaml b/targets.yaml
index a830a80f..9de23282 100644
--- a/targets.yaml
+++ b/targets.yaml
@@ -29,3 +29,11 @@ targets:
     no_paths: [gates.yaml, roles.yaml, targets.yaml, CLAUDE.md, .github/, templates/, skills/, docs/invariants.md, tests/test_invariants.py]
     project_skills: []
     merge_gate: operator
+    test_profile:
+      command: [python3, -m, pytest]
+      long_lived_dir: tests
+      long_lived_name: test_<id>_<name>.py
+      weakening_scope: [tests/**/*.py]
+      mutation_claim_scope: [tests/test_*.py]
+      report: junit-xml
+      install: []
```

## Приложение: tests/test_invariants.py

Песочница инвариантов (требование 7, ANSWER-1 вопрос 1): `FsmTest`
подменяет `config.TARGETS` на `<tmp>/targets.yaml` и сеет в него запись
артели с профилем тестов; помощник песочницы `write_plan` кладёт SPEC до
A4, если сценарий своего не положил (прогон приёмки в рабочей копии без
планки читает SPEC — требование 6). Тестовые методы — сценарии и
утверждения — не меняются.

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index 0e403649..160eee73 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -43,7 +43,7 @@ from tests.sandbox import (FakeProc, SpyRun, TmpRootTest, _stub_check_stack,  #
                            capture, capture_new_task_id,
                            disk_backed_ls_tree_files, disk_backed_show,
                            patch_pult_sleep, patch_sleep,
-                           resilient_tmp_cleanup)
+                           resilient_tmp_cleanup, seed_artel_targets)
 
 REPO_ROOT = Path(__file__).resolve().parent.parent
 
@@ -172,10 +172,19 @@ class FsmTest(unittest.TestCase):
                             # 01M41M6KGWA9PJ6G1KPDC6XY70, требование 6):
                             # прерванный прогон не оставляет `tasks/<id>/`
                             # в рабочей копии, `addCleanup` до него не доходит.
-                            ("TASKS", root / "tasks")):
+                            ("TASKS", root / "tasks"),
+                            # Декларация проектов — своя (SPEC
+                            # 01M45FJVGQT1K0P8HDEXZX6HS7, требование 7):
+                            # проверки тестов задачи артели читают её профиль
+                            # тестов из targets.yaml, а песочница не зависит
+                            # от боевого файла.
+                            ("TARGETS", root / "targets.yaml")):
             patcher = mock.patch.object(config, attr, value)
             patcher.start()
             self.addCleanup(patcher.stop)
+        # Запись артели с полем test_profile: без профиля проверки тестов
+        # задачи артели отказывают (требование 4).
+        seed_artel_targets()
 
         # `runner.role_env` сверяет `.artel/venv` через `stack.check_stack()`
         # (SPEC 01M1REVEZ1HESMJ7AFD5A9MEJ8, требование 4) — `ROOT` этого
@@ -338,6 +347,13 @@ class FsmTest(unittest.TestCase):
     def write_plan(self, status: str) -> None:
         (self.tdir / "PLAN.md").write_text(
             PLAN_MD.format(task=self.TASK, status=status), encoding="utf-8")
+        # SPEC на диске к выходу из `in_dev`: прогон приёмки идёт в рабочей
+        # копии задачи и для артели и без планки читает SPEC (SPEC
+        # 01M45FJVGQT1K0P8HDEXZX6HS7, требование 6); SPEC фикстуры — до A4
+        # (`schema_version: 1`) и планки не требует. Свой SPEC сценария не
+        # перетирается.
+        if not (self.tdir / "SPEC.md").exists():
+            self.write_spec("approved")
 
     def seed_worktree_plan(self) -> None:
         """Обязательный артефакт роли developer (SPEC 01M1RQ12JVHE3PQYDFV1XPSTQ3,
```

Применимость: оба блока выше прогнаны `git apply --check` на чистом дереве
HEAD ветки задачи — применяются; после наложения обоих
`python3 -m pytest tests/test_invariants.py` — 74 passed.

## Предложения системе

- Мутационная проверка сторожа правкой файла и откатом в ту же секунду
  оставляет устаревший `.pyc` (размер файла совпал, mtime в пределах
  секунды) — следующий прогон молча исполняет мутанта. В
  `skills/coding-standards.md` («Сторожа проверяй временной мутацией»)
  стоит назвать прогоны с `-B`/`PYTHONDONTWRITEBYTECODE=1`.
- `RealGitSandbox` (`tests/sandbox.py`) теперь сеет `targets.yaml` под
  `.artel/`; песочницы, коммитящие декларацию в дерево, обязаны
  возвращать путь сами — кандидат на явный флаг класса в части 3.
- Нет команды пульта «прогнать файлы `tests/` с наложенными приложениями
  PLAN» (как `plank-run` для планки): локальный прогон шёл с рабочей
  копией, где правка защищённого пути лежала незакоммиченной, и разошёлся
  с CI (возврат из `verifying` этой задачи). Приходится накладывать
  приложения `git apply` руками и снимать `git checkout` — кандидат на
  команду пульта (`orchestrator/plank_run.py` по образцу
  `scripts/plan_appendix_ci.py`).
