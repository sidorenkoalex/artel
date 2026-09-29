---
task: 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Долгоживущие приёмочные тесты пишутся в tests/ ветки задачи и фиксируются перечнем сумм (ADR-0020, задача 2)

## Подход

Одно правило — один узел, все потребители зовут его:

- **Правило имени Р1 и формат перечня Р2** — `scripts/guard.py`:
  `long_lived_path_prefix`/`is_long_lived_test_path` (полный id в нижнем
  регистре, `<имя>` из `[a-z0-9_]`), `render_long_lived_manifest`/
  `parse_long_lived_manifest` (`<sha256>␣␣<путь>\n`, строки по пути,
  строгий разбор), `LONG_LIVED_MANIFEST_NAME = long_lived.sha256.txt`,
  `long_lived_plank_errors` (долгоживущий файл в планке — отказ с
  подсказкой `tests/test_<префикс>_<имя>.py`),
  `acceptance_traceability_errors(tdir, extra_sources=())`.
- **Мандат test_author на чекпоинте** — `orchestrator/checkpoint.py`:
  `_test_author_own_paths` (пути `tests/` с префиксом задачи, которых нет
  в дереве `gitcmd.diff_base` ветки; только в `tests_writing`;
  переименование своё только целиком) и `_test_author_checkpoint`
  (сначала откат прочего `_discard_out_of_mandate_changes(..., keep=own)`
  с записью в журнал, затем коммит своих путей тем же
  `_commit_worktree_change`, что у developer). Подключён к трём
  WIP-чекпоинтам (`_wip_checkpoint`) и к пути «шаг завершён»
  (`commit_success_checkpoint`, роль `test_author`; reviewer/analyst на
  этом пути — прежнее «ничего»). Сбой git — чекпоинт не трогает worktree.
- **Выход из `tests_writing`** (`fsm_advance.tests_writing`, target
  `artel`, кодовая ветка существует): `_tests_writing_code_diff`
  (`diff_base` + `diff_name_status`; тексты своих `A`-файлов с головы;
  сбой git — отказ) → трассируемость с долгоживущими источниками
  (`fsm._tests_writing_ac_state(..., long_lived_sources)`) → гейт групп
  планки (+ отказ за долгоживущий файл в планке) →
  `_tests_writing_long_lived_gate` (M/D/R/прочие статусы, путь вне
  `tests/`, без префикса, путь уже в `origin/main`, нет строки
  «долгоживущий», признаки и «Ловит мутацию» задачи 1, рабочая копия
  выписана) → сухой сбор планки и долгоживущих файлов ОДНИМ вызовом
  (`acceptance.collect(..., extra=)`) → `_tests_writing_manifest_gate`
  (суммы байтов с головы кодовой ветки через `gitcmd.carpentry(...,
  text=False)`, коммит перечня в ветку документов, push) → `set_state
  in_dev` → `tests_locked_sha` = голова ветки документов, уже с перечнем.
- **Общий узел сверки** — `advance_gates/acceptance.py::
  _long_lived_manifest_refuses(conn, task_id)`: перечень читается из
  дерева коммита ЛОКА (неизменного), каждый путь сверяется с деревом
  головы кодовой ветки по SHA-256 байтов; изменён/удалён — отказ с путём
  и подсказкой «код чинится под тест; правка теста — `amend-tests` по
  решению Оператора»; сбой git — отказ. Вне области (внешний target, нет
  лока, лок снят до внедрения перечня — файла в дереве лока нет) —
  проход. Рубежи Р4: `in_dev` (после подтяжки), `verifying` (зелёный CI,
  перед переходом), `review` (approved, до учёта `reviewed_iter` — отказ
  не сжигает вердикт), `approve` из `acceptance` (после подтяжки), гейт
  мержа (`fsm_merge_gate._acceptance_locks_refuse` после
  `_sync_main_or_wait`, вместе с `_acceptance_lock_refuses` — требование
  8; только target `artel`).
- **Единый прогон** — `acceptance.run(..., extra=)` исполняет планку и
  долгоживущие файлы перечня одним pytest; `acceptance.summary(...,
  long_lived=)` добавляет строку «одним прогоном: разовая группа — N,
  долгоживущая группа — M». Полный набор автогейта и так гоняет `tests/`
  рабочей копии задачи — второго прогона нет.
- **Задания ролей** — `role_prompt.py`: пункт 2а test_author (место
  `tests/`, конкретный префикс `guard.long_lived_path_prefix(task_id)`,
  запрет трогать существующие файлы `tests/`), строка developer о
  фиксации долгоживущих файлов перечнем под тем же локом.

Бюджет: объём соответствует оценке SPEC, `budget_usd` не поднимаю.

## Шаги

1. `scripts/guard.py` — правило имени, формат перечня, отказ за
   долгоживущий файл в планке, трассируемость с доп. источниками.
2. `orchestrator/checkpoint.py` — мандат test_author на всех путях шага.
3. `orchestrator/acceptance.py` — `extra` у `run`/`collect`, строка групп
   в `summary`.
4. `orchestrator/advance_gates/acceptance.py` — узел сверки перечня,
   сумма байтов блоба, долгоживущие файлы в прогоне `in_dev`.
5. `orchestrator/advance_gates/tests_writing.py`, `orchestrator/
   fsm_advance.py`, `orchestrator/fsm.py` — гейт выхода из
   `tests_writing`, запись перечня до лока, рубежи Р4.
6. `orchestrator/fsm_merge_gate.py` — лок и перечень после подтяжки.
7. `orchestrator/role_prompt.py` — задания test_author/developer.
8. `tests/test_long_lived_manifest.py` — юнит-тесты узлов; правка
   фикстур трёх существующих тестов (см. «Влияние на систему»);
   регенерация `docs/codebase-map.md`.
9. Приложения к `skills/test-authoring.md`, `skills/coding-standards.md`,
   `skills/review-checklist.md`, `docs/invariants.md` (ниже).
10. Итерация 2, замечания REVIEW итерации 1:
    - R1-F1 — `tests/test_long_lived_transitions.py`: сторожа переходов
      через публичные входы на настоящем git — гейт «только добавление»
      (`M`/`D`/`R`, без префикса, вне `tests/`, без строки
      «долгоживущий», путь в `origin/main`), перечень в дереве лока (и
      пустой), трассируемость по своему долгоживущему файлу и не по чужому,
      отказ на каждом рубеже Р4 при правке после лока (+ контроль с CRLF),
      долгоживущий файл реально исполняется в прогоне `in_dev`, расхождение
      лока каталога на гейте мержа. AC-3 (правка/удаление своего файла
      коммитятся) — `test_long_lived_manifest.TestAuthorCheckpointMandateTest`.
      Приложение к `docs/invariants.md` называет новых сторожей.
    - R1-F2 — `advance_gates/acceptance.py::_acceptance_run_refuses`: target
      `artel`, рабочая копия не на ветке задачи, перечень непуст (или не
      прочитан) — отказ «долгоживущие файлы перечня исполнить негде», а не
      прогон одной планки.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (коммит test_author в `tests/`, откат прочего) | 2 |
| 2 (гейт «только добавление», путь в `origin/main`) | 5 |
| 3 (проверки задачи 1, сухой сбор из `tests/`) | 3, 5 |
| 4 (долгоживущий файл в планке — отказ с подсказкой) | 1, 5 |
| 5 (трассируемость) | 1, 5 |
| 6 (перечень до лока, пустой допустим) | 1, 4, 5 |
| 7 (сверка перечня на Р4, сбой git — отказ) | 4, 5, 6 |
| 8 (лок каталога на гейте мержа) | 6 |
| 9 (один прогон, итог двух групп) | 3, 4 |
| 10 (задания ролей) | 7 |
| 11 (область: `artel`, не внешний, не `skip_tests`) | 2, 4, 5, 6 |
| 12 (приложения) | 9 |
| REVIEW итерации 1: R1-F1, R1-F2 | 10 |

## Влияние на систему

- **Инвариант 27 усиливается, не ослабляется**: лок каталога теперь
  сверяется и на гейте мержа (раньше — только `in_dev → verifying`),
  перечень долгоживущих файлов — под тем же локом. Ни один гейт, guard,
  лимит не снят и не ослаблен; `_acceptance_lock_refuses`,
  `_tests_writing_test_groups_gate` и проверки задачи 1 на месте
  (AC-23 планки это сверяет).
- **Мандат test_author расширен узко**: коммит только путей Р1, которых
  нет в базе ветки, и только в `tests_writing`; всё прочее — прежний
  откат `_discard_out_of_mandate_changes`. Второй рубеж — гейт «только
  добавление» на выходе.
- **Правки существующих тестов (не ослабление, смена предпосылки по
  SPEC):**
  - `tests/test_acceptance_tests_flow.py::LockTest` и
    `tests/test_amend.py::AmendThenReviewGateTest` — коммит «кода фичи»
    в кодовую ветку перенесён из `setUp` на момент ПОСЛЕ выхода из
    `tests_writing` (как в конвейере: код пишет developer). Раньше он
    стоял до выхода, и новый гейт (требование 2, путь вне `tests/`)
    законно отказывал. Сценарии и ассерты не менялись.
  - `tests/test_fsm_advance_tests_writing_test_groups.py::
    test_fixed_file_passes_on_retry` — «исправленный» файл планки теперь
    разовый: долгоживущий файл в планке по требованию 4 — отказ (временная
    оговорка задачи 1 снята). Свойство теста — «гейт не помнит прошлый
    отказ» — то же, ассерты те же.
- **Вырожденный случай «кодовой ветки ещё нет в git»** на выходе из
  `tests_writing` — долгоживущих файлов быть не может, правило не
  применяется (перечень не пишется), тот же приём, что у ветко-корректных
  чтений (инвариант 28). Лёгкие песочницы тестов живут в этом случае.
- **Задачи, залоченные до мержа** (перечня в дереве лока нет) — сверка
  перечня их пропускает: иначе каждая задача в полёте встала бы на
  первом рубеже.
- **Откат**: revert одного merge-коммита; колонок БД и миграций нет,
  перечень — обычный файл ветки документов.
- Смоук: планка задачи целиком зелёная (кроме AC-22, которая читает
  PLAN.md из артефактной ветки после автокоммита); модули `tests/`,
  затронутые правкой, прогнаны по отдельности (список — в «Проверено»
  ниже).

## Риски

- `gitcmd.branch_exists` отвечает `False` и на сбой git: при сбое на
  выходе из `tests_writing` правило пропускается целиком. Кодовая ветка
  задачи `artel` в конвейере существует с первого шага роли, и
  test_author без неё ничего закоммитить в `tests/` не мог — утечки
  долгоживущего файла мимо перечня этим путём нет, но различать «нет
  ветки» и «git не ответил» `gitcmd` сегодня не умеет (только чтение по
  ТЗ).
- Возврат в `tests_writing` уже после работы developer (кодовая ветка
  несёт код) гейт «только добавление» отклонит — так требует SPEC
  (требование 2); сегодня такой маршрут в пульте есть только через
  эскалацию из самого `tests_writing`, где кода ещё нет.
- CI ветки красный с момента пуша долгоживущих файлов до кода
  разработчика — вне области (SPEC «Не входит»).

## Проверено

- Планка: `python3 -m pytest tasks/01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ/
  acceptance_tests -p no:cacheprovider -p timeout -o timeout=120` — 30
  passed (AC-22 — после автокоммита PLAN.md в артефактную ветку).
- Итерация 2: `tests/test_long_lived_transitions.py` +
  `tests/test_long_lived_manifest.py` — 24 passed, 20 subtests. Временные
  мутации (каждая краснит своего сторожа, код возвращён): гейт
  `_tests_writing_long_lived_gate` снят из списка гейтов; гейт
  `_tests_writing_manifest_gate` снят; `long_lived_sources=[]`; вызов
  `_long_lived_manifest_refuses` снят по одному на каждом из пяти рубежей
  (fsm_advance.py:277, :314, :546, fsm.py:931, fsm_merge_gate
  `_acceptance_locks_refuse`); `_acceptance_lock_refuses` на гейте мержа
  снят; `acceptance.run` без `extra`; отказ R1-F2 снят; чекпоинт признаёт
  своим только `??` в `git status`. Планка — 33 passed, 51 subtests.
  Модули, задетые правкой `_acceptance_run_refuses` (по отдельности):
  test_acceptance_tests_flow, test_advance_guard, test_amend,
  test_auto_cycle, test_branch_freshness_gate, test_ci_rerun_command,
  test_draft_mr_commits, test_fsm_map_conflict_autoresolve,
  test_git_fixation, test_invariants, test_mutation_claim_gate,
  test_review_freshness, test_stall_alerts, test_test_integrity_gate,
  test_zone_lock, test_multitarget, test_multitarget_invariants,
  test_acceptance, test_fsm_advance_gate_*, test_zones_gate,
  test_capacity_gate — зелёные. Приложения: `git apply --check -` каждого
  блока в рабочей копии (защищённые файлы в ней равны main) — все четыре
  накладываются.
- Итерация 1: `tests/test_long_lived_manifest.py` — 13 passed; каждый сторож проверен
  временной мутацией (9 мутаций: суммы не сверяются, test_author идёт
  веткой отката, снята проверка `tests_writing`, префикс `[:10]`, `run`
  игнорирует `extra`, пустая голова = проход, гейт мержа без области,
  `summary` без групп, разбор перечня пропускает мусор) — все красные.
- Затронутые модули `tests/` (по отдельности, в переднем плане):
  test_acceptance_tests_flow, test_fsm_advance_tests_writing_*,
  test_invariants, test_timeout_checkpoint, test_git_fixation,
  test_approve_acceptance_full_suite, test_merge_gate_ci_wait,
  test_fsm_merge_gate_*, test_fsm_map_*, test_fsm_retro,
  test_protected_paths_gate, test_test_integrity_gate,
  test_ci_status_kind_gate, test_branch_freshness_gate,
  test_split_assessment_merge_gate, test_cmd_approve_dispatch,
  test_plan_appendix, test_agent_prompt, test_role_prompt_*,
  test_step_autocommit, test_checkpoint_*, test_pull*,
  test_fsm_advance_gate_*, test_mutation_claim_gate, test_zones_gate,
  test_capacity_gate*, test_fsm_review_*, test_review_registry_gate,
  test_verifying_ceiling, test_fsm_autogate, test_acceptance*,
  test_dry_run, test_guard_*, test_auto_cycle,
  test_artifact_materialization, test_multitarget*, test_amend,
  test_canary*, test_answer*, test_brief и др. — зелёные.

## Предложения системе

- Планка задачи, целиком помеченная «разовый», проверяла проводку гейтов
  FSM — свойства кода; сторожей в `tests/` пришлось добирать итерацией
  ревью (R1-F1). `skills/coding-standards.md`: пока планка разовая, а
  проверяет код, сторож в `tests/` на каждое её свойство — часть первой
  сдачи разработчика, а не итерации ревью; `skills/test-authoring.md` —
  тот же урок со стороны выбора группы.

- `orchestrator/gitcmd.py`: `branch_exists` не различает «ветки нет» и
  «git не ответил» (обе — `False`); fail-closed узлам нужен трёхзначный
  ответ. Класс «вырожденный случай заглушки = сбой git» натирает каждый
  новый гейт на git (здесь — выход из `tests_writing`).
- `orchestrator/gitcmd.py`: нет примитива чтения БАЙТОВ блоба — сумма
  SHA-256 пошла через `gitcmd.carpentry(..., text=False)`, чей докстринг
  про плотницкую запись; `show` с `text=True` перекодирует концы строк.

## Приложение: skills/test-authoring.md

временная оговорка задачи 1 снята; долгоживущие файлы — в tests/ кодовой ветки с префиксом задачи.

```diff
diff --git a/skills/test-authoring.md b/skills/test-authoring.md
index 636c91d3..250a33be 100644
--- a/skills/test-authoring.md
+++ b/skills/test-authoring.md
@@ -95,9 +95,19 @@ guard разбирает её текстом, без импорта файлов
   докстринге модуля строкой
   `Заменяет: tests/<файл>.py::<Класс>::<метод>` (ADR-0020, пункт 8).
 
-До мержа задачи 2 внедрения ADR-0020 долгоживущие файлы лежат там же,
-где разовые, — в `tasks/<id>/acceptance_tests/`; сам файл обязан
-собираться и из каталога `tests/` без правки.
+Долгоживущий файл пишется не в `tasks/<id>/acceptance_tests/`, а в
+`tests/` кодовой ветки задачи, с префиксом задачи в имени:
+`tests/test_<id задачи в нижнем регистре>_<имя>.py`, `<имя>` — из
+`[a-z0-9_]` (конкретный префикс называет задание роли). Долгоживущий
+файл в `acceptance_tests/` выход из `tests_writing` отклоняет. В
+кодовой ветке test_author только ДОБАВЛЯЕТ такие файлы: правку,
+переименование и удаление существующих файлов `tests/`, файл без
+префикса и любую правку вне `tests/` пульт откатывает на чекпоинте шага,
+а выход из `tests_writing` отклоняет. Свои файлы коммитит пульт; пока
+задача в `tests_writing`, их можно править и удалять. На выходе пульт
+фиксирует их перечнем сумм `acceptance_tests/long_lived.sha256.txt` под
+тем же локом, что планку, и гоняет в одном прогоне с ней; метод
+`test_ac<n>_…` долгоживущего файла своей задачи покрывает критерий.
 
 ## Источник артефактов задачи — только артефактная ветка
 Источник артефактов задачи в планке: только артефактная ветка через
```

## Приложение: skills/coding-standards.md

правило «двойник в tests/» снято; долгоживущие файлы не правятся, тесты — только на непокрытое.

```diff
diff --git a/skills/coding-standards.md b/skills/coding-standards.md
index c07ab778..3416bd47 100644
--- a/skills/coding-standards.md
+++ b/skills/coding-standards.md
@@ -69,11 +69,12 @@ PLAN вправе один раз, при первой сдаче, поднят
   планки (skills/test-authoring.md): без неё выход из `in_dev`
   отказывает гейтом заявки мутации, а ревьювер сверяет тест с этой
   заявкой. Пересказ имени метода заявкой не является.
-- Долгоживущий файл планки (`Группа: долгоживущий`, skills/
-  test-authoring.md) до мержа задачи 2 внедрения ADR-0020 лежит в
-  `tasks/<id>/acceptance_tests/` и после мержа не исполняется. Поэтому
-  для свойства, которое он проверяет, пиши в `tests/` двойника — тест
-  того же свойства по правилам `tests/`.
+- Долгоживущие файлы задачи (`tests/test_<id задачи в нижнем
+  регистре>_*.py`, их пишет test_author, ADR-0020) зафиксированы
+  перечнем сумм так же, как приёмочные тесты: не правь их, расхождение с
+  ними эскалируй (правка — `amend-tests` по решению Оператора). Свои
+  тесты в `tests/` дописывай только на свойства, не покрытые
+  долгоживущими файлами задачи.
 - Сторожа (свой тест в `tests/`) проверяй временной мутацией: временно
   сломай код так, как заявлено в его «Ловит мутацию: …», прогони
   названные файлы `tests/` без приёмочных тестов (`python3 -m pytest
```

## Приложение: skills/review-checklist.md

повтор долгоживущего теста — замечание; временное правило «Долгоживущие свойства — в tests/» не тронуто.

```diff
diff --git a/skills/review-checklist.md b/skills/review-checklist.md
index c235e9c8..c841294a 100644
--- a/skills/review-checklist.md
+++ b/skills/review-checklist.md
@@ -49,6 +49,10 @@ MVP): проверяй PLAN.md первым блоком того же прог
    чтение `tasks/<id>/`), помеченный долгоживущим, и свойство кода,
    помеченное разовым, — замечание: первый станет ложным сторожем после
    мержа, второе останется без сторожа.
+   **Повтор долгоживущего теста — замечание** (ADR-0020, п. 4). Свойство,
+   которое уже держит долгоживущий файл задачи (`tests/test_<id задачи в
+   нижнем регистре>_*.py`), разработчик в `tests/` не повторяет; тест
+   разработчика, повторяющий долгоживущий, — замечание.
    **Сторож — проверен временной мутацией.** Сомневаешься, ловит ли тест
    `tests/` свою заявку, — проверь приёмом «временная мутация»: временно
    сломай код так, как заявлено в «Ловит мутацию: …», прогони названные
```

## Приложение: docs/invariants.md

инвариант 27: лок на перечень долгоживущих файлов, сверка на переходах и на мерже.

```diff
diff --git a/docs/invariants.md b/docs/invariants.md
index a7106191..418d4e2b 100644
--- a/docs/invariants.md
+++ b/docs/invariants.md
@@ -54,7 +54,7 @@ docs/adr/0002-integrity-principle.md, CLAUDE.md.
 | 24 | Счётчик номеров задач target не переиспользует номер архивированной (не удалённой) строки при пересеве после reconnect | `test_multitarget_invariants.CounterSurvivesArchivalOnReconnectTest` | ADR-0003 3ж («архивация строк, никогда DELETE»); tasks/T020/SPEC.md, требование 5 |
 | 25 | FSM принимает решения только по артефактам, чьи хэши зафиксированы его журналом: расхождение живого sha (или грязная копия) с зафиксированным на последнем переходе — инцидент целостности, агент не запускается; `approve` без явного sha сам сверяет живой sha и чистоту копии/артефактной ветки с зафиксированными на последнем переходе тем же источником, которым печатается подсказка — совпало, гейт проходит без ручного набора и журналирует согласованный sha, расхождение/грязная копия отклоняют его именованным отказом с обоими sha так же, как и явный неверный sha | `test_git_fixation.FsmDecidesOnlyOnFixedHashesTest`; `test_git_fixation.IntegrityIncidentBlocksRunTest`; `test_git_fixation.ApproveByShaTest`; `tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/acceptance_tests/test_ac1_*.py`, `test_ac2_matching_fixation_auto_confirms.py`, `test_ac3_diverged_or_dirty_refuses_named.py` | ADR-0003 п.15, п.17; tasks/T021/SPEC.md, требования 4–6; tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/SPEC.md, требования 1–2 |
 | 26 | Выход из `tests_writing`: критерий приёмки (AC-n) без теста и без пометки manual/skip/escalate — невалидный выход, переход отказывает с именем критерия | `test_acceptance_tests_flow.TraceabilityTest` | tasks/T023/SPEC.md, требование 4 |
-| 27 | Каталог `acceptance_tests/` залочен фиксацией T021 после выхода из `tests_writing`: расхождение с зафиксированным на выходе sha — отказ перехода `in_dev → verifying`, код чинится под тест, не наоборот | `test_acceptance_tests_flow.LockTest` | tasks/T023/SPEC.md, требование 5; ADR-0015 (переезд рубежа с `in_dev → review`) |
+| 27 | Каталог `acceptance_tests/` залочен фиксацией T021 после выхода из `tests_writing`: расхождение с зафиксированным на выходе sha — отказ перехода `in_dev → verifying` и гейта мержа после подтяжки main, код чинится под тест, не наоборот. Лок распространяется на перечень долгоживущих файлов задачи `acceptance_tests/long_lived.sha256.txt` (суммы `tests/test_<id задачи в нижнем регистре>_*.py` кодовой ветки): сверка сумм с головой кодовой ветки — на переходах `in_dev → verifying`, `verifying → review`, `review → acceptance`, `approve` из `acceptance` и на гейте мержа после подтяжки main; изменённый или удалённый файл, сбой git — отказ | `test_acceptance_tests_flow.LockTest`; `test_long_lived_manifest.ManifestCheckNodeTest`; `test_long_lived_transitions.ManifestBoundariesTest`, `test_long_lived_transitions.MergeGatePlankLockTest`, `test_long_lived_transitions.TestsWritingManifestTest` | tasks/T023/SPEC.md, требование 5; ADR-0015 (переезд рубежа с `in_dev → review`); ADR-0020, п. 3; SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требования 6-8 |
 | 28 | Чтение артефактов задачи оркестратором (маршрутизация `spec_gate`, бриф роли developer, трассируемость AC, лок `acceptance_tests/`, sha догфуд-фиксации, статус SPEC.md и батч QUESTIONS.md на переходе `spec_writing → spec_gate`, вердикт REVIEW.md — status и iteration — на переходе `review → acceptance/in_dev`) не зависит от того, какая ветка сейчас выписана в рабочем дереве пульта: источник истины — ВЕТКА задачи (`git show`/`git ls-tree`), чужой чекаут её не подменяет; ветка ещё не создана ролью — прежнее поведение (рабочая копия), не именованный отказ | `test_gitcmd_branch_reads.OnForeignBranchTest`; end-to-end по каждому месту чтения — `tasks/T031/acceptance_tests/test_branch_correct_reads.py` (`SpecGateBranchRoutingTest`, `BriefBuildBranchTest`, `TraceabilityBranchTest`, `LockBranchTest`, `FixationBranchTest`, `NoUnhandledExceptionOnMissingBranchTest`); `tasks/T047/acceptance_tests/test_branch_correct_status_reads.py` (`SpecWritingBranchRoutingTest`, `ReviewBranchRoutingTest`, `NoTaskBranchDegradationTest`, `NoGitDegradationTest`) | tasks/T031/SPEC.md, требования 1–2; tasks/T030 (класс-дефект «артефакто-чтения ветко-зависимы», журнал ~17:35 25.08.2026); tasks/T047/SPEC.md, требования 1–4 (инциденты T046 27.08.2026, T045 27.08.2026) |
 | 29 | Стоимость шага не остаётся неучтённой молча: если финальное событие потока (`type: result`) не пришло из-за таймаута шага или обрыва stdout-пайпа, в журнал попадает либо частичная сумма из промежуточных usage-событий с пометкой «частичная», либо событие «стоимость шага неизвестна» с открытым алертом `alerts` (`kind=incident`, `source=spend.unknown_cost`); `spent_usd` при этом не дописывается фиктивной суммой | `tasks/T040/acceptance_tests/test_step_cost_on_missing_final_event.py::MissingFinalEventCostTest`; `test_step_cost.ChargeMissingResultTest`; `test_step_cost.CmdRunPartialCostTest` | tasks/T040/SPEC.md, требования 1–3 |
 | 30 | Таймаут шага с незакоммиченным WIP в рабочем дереве ветки задачи коммитится оркестратором чекпоинтом (`<id>: WIP-чекпоинт после таймаута шага <role>`, журнал actor=`orchestrator`) без участия Оператора; провал шага по коду возврата (не таймаут) и таймаут при уже чистом дереве чекпоинт не коммитят | `tasks/T041/acceptance_tests/test_checkpoint_after_timeout.py::CheckpointAfterTimeoutTest`; `test_timeout_checkpoint.CommitTimeoutCheckpointTest` | tasks/T041/SPEC.md, требования 1–4; прецеденты tasks/T022, tasks/T037 (ручной чекпоинт Оператора) |
```

Каждое приложение проверено `git apply --check` на чистом дереве (индекс базы диффа задачи `gitcmd.diff_base`, временный `GIT_INDEX_FILE`, `git apply --check --cached -`) — все четыре накладываются; сами файлы в кодовой ветке не менялись.
