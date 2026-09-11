---
task: 01M1SHJZCE0Y4DXAAWQ2W585A7
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: подзадачи деления заводит пульт из раздела «Деление» SPEC при approve

## Подход
Три тесно связанных куска одной механики (SPEC, «Оценка объёма и
деление» — монолит принят Оператором 06.09.2026), один MR:

1. `scripts/guard.py` — разбор и валидация новой секции `## Деление`
   SPEC (2–4 подраздела `### <название>`, поля `Зоны:`/`Порядок:`,
   необязательное `Рамка:`, непустой текст ТЗ; зоны подраздела —
   подмножество зон родителя ∪ `config.COMMON_ZONES`). Публичная
   функция `parse_division_subsections(text)` отдаёт разобранные
   подразделы БЕЗ валидации (переиспользуется `fsm.py` на `approve` —
   секция там уже гарантированно валидна, см. п.3), `division_section_
   errors(path, text, meta)` — сама проверка, подключена в
   `_content_errors` рядом с `spec_zones_errors`/`spec_budget_field_
   errors`. Без версии-гейтинга: секция необязательна для ЛЮБОГО
   `schema_version` (AC-9), в отличие от `zones`/`budget_usd`.
2. `orchestrator/catalog.py::spawn_subtask` — заведение ОДНОЙ подзадачи
   той же механикой, что `cmd_new` с ТЗ Оператора: переиспользует
   готовые `_tz_document`/`_new_external_artifact_branch` без изменений
   их кода, только собирает `TZ.md` не из файла Оператора, а из
   подраздела секции «Деление» (первая строка — ссылка на родителя,
   дальше — сырой текст подраздела ЦЕЛИКОМ, поля `Зоны:`/`Порядок:`/
   `Рамка:` включительно — требование 2: «эта задача не учит cmd_new
   новым параметрам зон/бюджета», аналитик подзадачи прочитает их из
   TZ.md сам). Не публичный CLI-путь — вызывается только из fsm.py.
3. `orchestrator/fsm.py::_approve_spec_gate` — после применения zones/
   budget (как и раньше) проверяет `guard.parse_division_subsections
   (spec_text)`; непусто — заводит по подзадаче на подраздел
   (`_spawn_division_subtasks`), переводит родителя в `killed` через
   `store.set_state(..., detail="поделена на: <id1>, <id2>, ...")`
   (сама функция уже журналирует detail и печатает его, отдельного
   `print` не нужно — AC-6/AC-7 закрываются штатным поведением
   `set_state`), и возвращает без захода в прежнюю ветку skip_tests/
   tests_writing. Ветка срабатывает СТРОГО из состояния `spec_gate`
   (уже внутри обработчика этого состояния) — повторный `approve`
   родителя приходит из `killed`, попадает в диспетчер `_cmd_approve`
   без обработчика и печатает существующее «нечего подтверждать»
   (AC-8/AC-9/AC-12 — без единой строки нового кода для этого случая).

   Guard уже отказал бы переходу `spec_writing -> spec_gate` на
   невалидной секции (`fsm_advance.spec_writing` зовёт `guard_refuses`
   на SPEC.md ДО перехода) — `_approve_spec_gate` не проверяет формат
   заново, только распознаёт уже провалидированный текст.
4. Юнит-тесты слоя `tests/` (`test_guard_division_section.py`,
   `test_catalog_spawn_subtask.py`) — граничные случаи и сама механика
   `parse_division_subsections`/`spawn_subtask` в изоляции; сквозные
   сценарии approve/guard уже закрывает `tasks/<id>/acceptance_tests/`
   (test_author, `tests_writing`, не трогается этим планом).
5. `docs/codebase-map.md` — регенерация тем же коммитом (правка `.py`
   в `orchestrator/`/`scripts/`).
6. Правки защищённых путей (`templates/SPEC.md`, `skills/
   spec-authoring.md`, `docs/operator-gates.md`) — этой веткой НЕ
   трогаются (conventions-core: «правка templates/skills — только
   Оператор отдельным MR»). Три unified-диффа приложены ниже,
   `git apply --check` пройден на чистом дереве до сдачи (требование
   4, AC-10) — Оператор применяет их сам.

## Шаги
1. `scripts/guard.py`: `parse_division_subsections`, `division_section_
   errors`, подключение в `_content_errors` (AC-1..AC-4, AC-13, AC-14).
2. `orchestrator/catalog.py`: `spawn_subtask` (требования 1-2).
3. `orchestrator/fsm.py`: `_spawn_division_subtasks` + ветка в
   `_approve_spec_gate` (требования 2-3, AC-5..AC-9, AC-11, AC-12).
4. `tests/test_guard_division_section.py`,
   `tests/test_catalog_spawn_subtask.py` + регенерация
   `docs/codebase-map.md` (требование 5).
5. Диффы `templates/SPEC.md`/`skills/spec-authoring.md`/
   `docs/operator-gates.md` приложением к этому PLAN (требование 4,
   AC-10) — см. секцию «Приложение» ниже.

Один MR — шаги выше независимо ПРОВЕРЯЕМЫ (каждый прогнан отдельно
ниже), но не мержимы по отдельности: формат секции без потребителя на
`approve` бесполезен, потребитель без провалидированного guard'ом
формата не тестируется (та же связка, что зафиксировал монолит SPEC).

## Покрытие требований
| Требование | Шаг |
|---|---|
| 1 (формат секции «Деление», guard) | 1 |
| 2 (approve заводит подзадачи, TZ.md со ссылкой) | 2, 3 |
| 3 (killed + журнал, идемпотентность) | 3 |
| 4 (три unified-диффа приложением) | 5 |
| 5 (тесты) | 1, 2, 3, 4 |

| AC | Шаг |
|---|---|
| AC-1 | 5 (защищённый путь, диф приложением — не код этой ветки) |
| AC-2 | 1 |
| AC-3 | 1 |
| AC-4 | 1 |
| AC-5 | 2, 3 |
| AC-6 | 3 |
| AC-7 | 3 |
| AC-8 | 3 |
| AC-9 | 3 |
| AC-10 | 5 |
| AC-11 | 2, 3 |
| AC-12 | 3 |
| AC-13 | 1 |
| AC-14 | 1 |
| AC-15 | 4 (существующие тесты прогнаны зелёными, см. «Влияние на систему») |

## Влияние на систему
- **`_approve_spec_gate` (fsm.py)** — новая ветка срабатывает ТОЛЬКО
  когда `guard.parse_division_subsections(spec_text)` непусто, то есть
  только для SPEC с заполненной секцией «## Деление». SPEC без неё
  (подавляющее большинство существующих и будущих задач) идёт прежним
  путём байт-в-байт — проверено AC-9 (сквозной приёмочный тест) и
  полным прогоном существующих тестов гейта SPEC ниже.
- **`killed` как терминальное состояние деления** — переиспользует
  существующее состояние, ничего не добавляет в FSM/схему БД. Отличие
  от `kill`-switch (`orchestrator/cleanup.py::cmd_kill`): переход НЕ
  запускает `cleanup_killed_task` (уборка worktree/ветки, снимок
  RETRO-долга, журнал TZ.md перед уборкой) — на `spec_gate` у родителя
  ещё нет ни worktree, ни закоммиченного кода (роль developer не
  запускалась), убирать нечего. Ветка кода родителя (заведённая пустой
  `cmd_new`) остаётся неубранной — тот же остаточный след, что у любой
  SPEC-only задачи, а `cmd_kill` уже умеет безусловно убирать хвосты
  даже у ЗАДАЧИ, УЖЕ находящейся в терминальном состоянии
  (`cleanup.py:236-249`, `test_kill_cleanup.py::
  test_repeated_kill_finds_nothing_and_does_not_fail`) — Оператору
  доступен штатный `artel.py kill <parent_id>` как дочистка, если
  ветку правда нужно убрать; ничего не потеряно молча.
- **`catalog.spawn_subtask`** переиспользует `_tz_document`/
  `_new_external_artifact_branch` БЕЗ изменения их кода — поведение
  `cmd_new` не затронуто (проверено `tests.test_catalog_new_race`
  ниже). Push артефактной ветки новой подзадачи — тот же best-effort
  путь, что и у `cmd_new` (отказ сети не прерывает заведение).
- **guard.py** — новая проверка подключена только для `atype == "spec"`
  и только когда заголовок `## Деление` присутствует; на SPEC без него
  `division_section_errors` возвращает `[]` первой же строкой (не
  трогает существующие пути `split_assessment_errors`/`spec_zones_
  errors`/`spec_budget_field_errors` рядом — проверено полным прогоном
  их тестов ниже).
- **Откат**: три файла (`guard.py`, `catalog.py`, `fsm.py`) — правки
  чистые добавления новых функций + одна условная ветка в существующей
  функции; откат — обратный git-коммит, схема БД и существующие
  колонки не менялись.

Прогнано (зелёными, без ослабления, требование 5/AC-15):
`tasks/01M1SHJZCE0Y4DXAAWQ2W585A7/acceptance_tests/` — все 10
исполняемых файлов (AC-2..AC-9, AC-11, AC-12); `tests.
test_advance_guard`, `tests.test_zones_approve`, `tests.
test_guard_split_signals`, `tests.test_catalog_new_race` (SPEC,
требование 5, поимённо); дополнительно (не по AC-15, для своей
уверенности) `tests.test_fsm_advance_gate_framework`,
`test_fsm_advance_gate_smoke`, `test_fsm_autogate`,
`test_fsm_branch_correct_status_reads`, `test_fsm_draft_mr_reentry`,
`test_fsm_map_conflict_autoresolve`, `test_fsm_map_regen`,
`test_fsm_merge_conflict_note`, `test_fsm_merge_gate_done_snapshot`,
`test_fsm_merge_gate_scratch_worktree_cleanup`, `test_fsm_retro`,
`test_catalog_status_log`, `test_catalog_tz_zones_parsing`,
`test_catalog_wave_breaker_status`, `test_guard_artifact_branch_mode`,
`test_guard_extraneous_acceptance_files`, `test_guard_schema`,
`test_guard_task_root_subdirectory`, `test_cmd_approve_dispatch`,
`test_fsm_review_rework_gate`, `test_fsm_review_rework_sha_gate`,
`test_multitarget`, `test_multitarget_invariants`, `test_invariants`,
`tests.test_guard_division_section`, `tests.test_catalog_spawn_subtask`
(новые).

## Риски
- Ветка кода родителя, поделённого на подзадачи, остаётся неубранной
  до явного `artel.py kill <parent_id>` Оператором (см. «Влияние на
  систему») — не автоматизировано этой задачей (requirement 2 SPEC не
  требует уборки хвостов, только переход в `killed` + журнал).
- `parse_division_subsections` ищет поля `Зоны:`/`Порядок:`/`Рамка:`
  построчно по всему телу подраздела (первое найденное значение
  побеждает), не строго сразу за заголовком — формат Оператора чуть
  свободнее буквы требования 1, но ловит все фикстуры приёмочных
  тестов и не расширяет пространство ложно-валидных SPEC (строка,
  НЕ начинающаяся ровно с `Зоны:`/`Порядок:`/`Рамка:`, полем не
  считается).

## Приложение: диффы защищённых путей (требование 4, AC-10)
Три unified-диффа ниже проверены `git apply --check <файл>` на чистом
дереве (текущий `main`/ветка задачи, `templates/SPEC.md`/`skills/
spec-authoring.md`/`docs/operator-gates.md` этой веткой не тронуты) —
все три прошли БЕЗ ошибок непосредственно перед сдачей этого PLAN.
Применяет и коммитит Оператор.

### templates/SPEC.md — секция «## Деление» рядом с «Оценка объёма и деление»
```diff
--- a/templates/SPEC.md
+++ b/templates/SPEC.md
@@ -64,6 +64,38 @@
 
 Решение утверждает Оператор на гейте SPEC (docs/operator-gates.md).>
 
+## Деление
+<Заполняется ТОЛЬКО при решении «нарезка» секции выше — заявка на
+деление, не команда: роль не вправе звать команды пульта из своего
+worktree (T056), заводит подзадачи сам пульт при `approve` на этом же
+гейте (docs/operator-gates.md, гейт SPEC). 2–4 подраздела `### <название
+подзадачи>`, один на каждую часть нарезки. Каждый подраздел несёт:
+
+- `Зоны:` — список путей/масок через запятую; каждая зона обязана
+  входить либо в зоны родителя (frontmatter zones: этого SPEC), либо в
+  общие зоны (orchestrator/config.py::COMMON_ZONES) — guard отказывает
+  подразделу, режущему зону родителя поперёк;
+- `Порядок:` — для первой части буквально «первая, без зависимостей»;
+  для остальных — «после части N»;
+- `Рамка: $N` — необязательно, рамка бюджета будущей подзадачи;
+- текст ТЗ подзадачи — свободный текст после полей, до следующего
+  `###` или конца секции; станет TZ.md подзадачи с добавленной первой
+  строкой-ссылкой на эту задачу.
+
+### <название первой подзадачи>
+
+Зоны: ...
+Порядок: первая, без зависимостей
+
+<текст ТЗ первой подзадачи>
+
+### <название второй подзадачи>
+
+Зоны: ...
+Порядок: после части 1
+
+<текст ТЗ второй подзадачи>>
+
 ## Не входит
 <Явные границы: что НЕ делаем в этой задаче.>
 
```
`git apply --check` на чистом дереве: **прошёл без ошибок**.

### skills/spec-authoring.md — «Нарезка на 2–4 подзадачи»: заявка секцией, не `cmd_new`
```diff
--- a/skills/spec-authoring.md
+++ b/skills/spec-authoring.md
@@ -68,10 +68,17 @@
   часть с механикой, на которую опираются остальные (остальные части
   без неё не имеют смысла мержить). Для каждой части — короткое
   обоснование, почему она самостоятельно мержима с зелёной планкой
-  (не оставляет систему в промежуточном нерабочем состоянии). Заведи
-  подзадачи командой `cmd_new`, указав родительскую задачу текстом в
-  ТЗ каждой подзадачи (общая связка — только текстом, отдельной
-  механики родительства нет).
+  (не оставляет систему в промежуточном нерабочем состоянии). Заявку
+  оформи секцией «## Деление» этого же `SPEC.md` (`templates/SPEC.md`):
+  по одному подразделу `### <название>` на часть, поля `Зоны:`/
+  `Порядок:` (необязательное `Рамка:`) и текст ТЗ подзадачи —
+  `scripts/guard.py` проверяет формат при `advance` на этот же гейт.
+  Ты не зовёшь `cmd_new` сама (T056 запрещает роли команды пульта из
+  своего worktree) — подзадачи заводит пульт САМ при `approve` на
+  `spec_gate` этой заявки (`docs/operator-gates.md`, гейт SPEC, п.6);
+  общая связка с родителем — текстом первой строки `TZ.md` подзадачи,
+  которую впишет пульт, отдельной механики родительства по-прежнему
+  нет.
 - **Обоснование монолита.** Что именно нельзя разрезать (атомарная
   смена механики) и почему промежуточное состояние неработоспособно.
   Решение утверждает Оператор на гейте SPEC (`docs/operator-gates.md`)
```
`git apply --check` на чистом дереве: **прошёл без ошибок**.

### docs/operator-gates.md — гейт SPEC, п.6: заявка на деление утверждается тем же approve
```diff
--- a/docs/operator-gates.md
+++ b/docs/operator-gates.md
@@ -70,7 +70,14 @@
    действуют на живые задачи; история не переписывается — SPEC уже
    закрытых задач (`docs/retro/<id>.md` существует) под новые правила
    задним числом не подпадает и backfill'ом не правится (ANSWER-3
-   tasks/01M1KS8K9RXWHX2PW3ZKB0P903).
+   tasks/01M1KS8K9RXWHX2PW3ZKB0P903). Решение «нарезка» аналитик
+   оформляет заявкой в самом SPEC — секцией «## Деление»
+   (`templates/SPEC.md`, 01M1SHJZCE0Y4DXAAWQ2W585A7): по подразделу
+   `### <название>` на подзадачу, формат проверяет `scripts/guard.py`
+   на этом же переходе. Утверждаешь заявку ТЕМ ЖЕ `approve` на
+   `spec_gate` — отдельной команды на заведение подзадач нет: пульт сам
+   заводит их по секции, переводит эту задачу в `killed` и печатает id
+   заведённых подзадач.
 
 Отказ (`reject`) или редактура Оператором: расхождение с ТЗ,
 непроверяемый критерий, пропуск в нумерации AC. Редактура на гейте —
```
`git apply --check` на чистом дереве: **прошёл без ошибок**.

## Предложения системе
- `orchestrator/fsm.py::_approve_spec_gate` растёт веткой за веткой
  (zones/budget/calibration/skip_tests/tests_writing/деление) — при
  следующей похожей вставке стоит присмотреться к вынесению в таблицу
  условий по образцу `_cmd_approve`/`_cmd_advance` (SPEC T091), пока
  функция не превратилась в код, который проще переписать, чем читать.

## Возврат — REVIEW.md итерация 1: R1-F1 (major), R1-F2/R1-F3/R1-F4 (minor)

Закрыты все четыре записи реестра REVIEW.md итерации 1.

**R1-F1** (`scripts/guard.py::division_section_errors`, major) — сверка
зоны подраздела с зонами родителя/`config.COMMON_ZONES` заменена с
плоского членства в множестве (`zone not in parent_zones and zone not
in common_zones`) на покрытие с учётом вложенности каталог/файл — тем
же приёмом, что уже применяет `orchestrator/zone_lock.py` для точно той
же задачи (общие зоны вида `"tests/"`): `zone_lock._is_common_zone(zone)`
(покрытие общими зонами) и `any(zone_lock._covered_by(zone, pz) for pz
in parent_zones)` (покрытие зоной родителя), обе функции переиспользованы
без изменений их кода — приём тот же, что уже применяет остальной
кодовая база к приватным именам соседних модулей (`fsm_advance.py` зовёт
`fsm._dirty_refuses`, `catalog.py` — `zone_lock._own_paths` и т.п.).
Импорт `orchestrator/zone_lock.py` добавлен в `scripts/guard.py` —
цикла импорта нет (`zone_lock.py` импортирует только `config`/`store`,
ни один из которых не импортирует `guard`), карта перегенерирована
(новое ребро `scripts/guard.py -> orchestrator/zone_lock.py`).

Регресс закрыт тремя новыми тестами `tests/test_guard_division_section.py`
(`test_zone_nested_under_a_common_directory_zone_does_not_error`,
`test_zone_nested_under_a_parent_directory_zone_does_not_error`,
`test_zone_wider_than_parent_directory_still_errors` — последний ловит
обратную лазейку: вложенность не должна разрешать подразделу называть
зоной каталог ШИРЕ узкой зоны родителя). Мутационная проверка: вернул
временно старую плоскую проверку — `test_zone_nested_under_a_common_
directory_zone_does_not_error`/`test_zone_nested_under_a_parent_
directory_zone_does_not_error` покраснели (`AssertionError`, зона
`tests/test_something_new.py`/`orchestrator/catalog.py` отказана, как
и описал ревьювер), `test_zone_wider_than_parent_directory_still_errors`
остался зелёным (плоская проверка тоже её ловит); вернул фикс — все три
снова зелёные.

**R1-F3** (`scripts/guard.py::division_section_errors`, minor) —
заголовок «## Деление» присутствует и тело секции непустое, но
`parse_division_subsections` не находит ни одного `### <название>` —
раньше это отдавалось молча (`if not subsections: return []`,
неотличимо от полного отсутствия секции); теперь функция явно
проверяет непустоту тела (`section_body(...).strip()`) ДО разбора и, при
пустых `subsections` на непустом теле, возвращает явную ошибку «секция
не несёт ни одного подраздела '### <название>'», а не тихий проход.
Тест: `test_header_present_with_prose_but_no_subsections_errors`.

**R1-F2** (`tests/test_catalog_spawn_subtask.py` — 4 метода,
`tests/test_guard_division_section.py` — 3 метода, конвенция
test-authoring) — всем семи методам добавлен докстринг «Ловит
мутацию: …» с конкретным сценарием (шаблон/id, спутанные с телом
подраздела ссылка на родителя, состояние заведённой строки,
дефолт `target`, разбор заголовка без секции, необязательность
`Рамка:`, ветвление по `type`).

**R1-F4** (`orchestrator/catalog.py`, minor) — общий скелет `cmd_new`/
`spawn_subtask` (генерация ветки, шаблон SPEC, `_new_external_artifact_
branch`, `store.insert_task`, `store.journal`) вынесен в приватный
хелпер `_new_task_row(conn, task_id, title, target, tz_doc, *,
is_canary=False, journal_detail)` — `cmd_new` передаёт `journal_
detail=title` (прежнее поведение байт-в-байт), `spawn_subtask` —
`journal_detail=f"деление {parent_id}: {title}"`; печать подсказок и
генерация `task_id`/`tz_doc` остаются в вызывающих функциях (они
отличаются по существу, не только текстом). Регресс: существующий
`tests.test_catalog_new_race` и весь `tests.test_catalog_spawn_subtask`
зелёные без изменений тестового кода под этот рефакторинг.

Реестр замечаний REVIEW.md переведён в `fixed` по всем четырём записям
(R1-F1..R1-F4) — закрытие (`accepted`) остаётся решением ревьювера
следующей итерации.

Прогон:
- `python3 -m unittest tests.test_guard_division_section
  tests.test_catalog_spawn_subtask -v` — 15/15 OK (11 прежних + 4 новых:
  3 на R1-F1, 1 на R1-F3).
- `python3 -m unittest tests.test_advance_guard tests.test_zones_approve
  tests.test_guard_split_signals tests.test_catalog_new_race
  tests.test_cmd_approve_dispatch -v` — 40/40 OK (SPEC требование 5,
  поимённо).
- Все 10 исполняемых файлов `tasks/01M1SHJZCE0Y4DXAAWQ2W585A7/
  acceptance_tests/` (AC-2..AC-9, AC-11, AC-12) — зелёные без изменений
  (планка залочена, не трогалась).
- `python3 -m unittest tests.test_fsm_advance_gate_framework
  tests.test_fsm_advance_gate_smoke tests.test_fsm_autogate
  tests.test_fsm_branch_correct_status_reads tests.test_fsm_draft_mr_reentry
  tests.test_fsm_map_conflict_autoresolve tests.test_fsm_map_regen
  tests.test_fsm_merge_conflict_note tests.test_fsm_merge_gate_done_snapshot
  tests.test_fsm_merge_gate_scratch_worktree_cleanup tests.test_fsm_retro
  tests.test_catalog_status_log tests.test_catalog_tz_zones_parsing
  tests.test_catalog_wave_breaker_status tests.test_guard_artifact_branch_mode
  tests.test_guard_extraneous_acceptance_files tests.test_guard_schema
  tests.test_guard_task_root_subdirectory tests.test_fsm_review_rework_gate
  tests.test_fsm_review_rework_sha_gate tests.test_multitarget
  tests.test_multitarget_invariants tests.test_invariants` — 231/231 OK.
- `python3 scripts/guard.py --all` — без новых нарушений (два
  предсуществующих предупреждения `_sandbox.py`, не по зоне этой
  задачи).
- Три unified-диффа приложения (требование 4, AC-10) перепроверены
  `git apply --check` на текущем дереве ПОСЛЕ этой правки (код MR не
  затрагивает `templates/`/`skills/`/`docs/`) — все три прошли без
  ошибок.
- `python3 scripts/codebase_map.py` — перегенерирована (новое ребро
  `scripts/guard.py -> orchestrator/zone_lock.py`), закоммичена этим же
  коммитом (conventions-core: правка `.py` в `orchestrator/`/`scripts/`).
