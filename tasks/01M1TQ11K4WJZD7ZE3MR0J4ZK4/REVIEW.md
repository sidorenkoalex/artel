---
task: 01M1TQ11K4WJZD7ZE3MR0J4ZK4
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: подсказка потолка по калибровке при new и на гейте SPEC

## Замечание к пакету ревью (диагностика перед вердиктом)

Diff в пакете (база `e306e1858cfb369220a4d41c641a87bd2df09ab3` →
HEAD `d6b1efa6`) почти целиком состоит из содержимого ЧУЖОЙ задачи
(01M1TQ0ZCYJ6TESZ2KGJ6AWYNH, артефактная ветка от `origin/main`) —
пришло commit'ом «подтяжка main» (d6b1efa6). Причина: база диффа
(`e306e185`) — это САМ коммит фикса R1-F1
(«01M1TQ11K4WJZD7ZE3MR0J4ZK4: замечания ревью итерации 1 — фикс
разбора «Зоны:» в ТЗ (R1-F1)»), сделанный разработчиком ПОСЛЕ вердикта
итерации 1 (`changes_requested`). Взяв этот коммит границей, пакет
скрыл собственно фикс, ради проверки которого и идёт эта итерация —
пустой diff по зоне задачи создавал бы неверное впечатление «ничего не
изменилось» (класс, описанный в review-checklist: «Инкрементальный
diff пакета — пустой не значит «без изменений»»).

Проверено вручную (не по пакету):
- `git show e306e185 -- orchestrator/catalog.py
  tests/test_catalog_tz_zones_parsing.py` — содержимое фикса R1-F1
  (см. «Реестр замечаний» ниже).
- `git diff e306e1858cfb369220a4d41c641a87bd2df09ab3..HEAD --stat --
  orchestrator/config.py orchestrator/catalog.py orchestrator/budget.py
  orchestrator/fsm.py docs/adr/0014-budget-default-and-role-cap.md
  tasks/01M1TQ11K4WJZD7ZE3MR0J4ZK4/` — пусто: ни один файл зоны этой
  задачи не менялся после фикса R1-F1; commit `d6b1efa6` («подтяжка
  main») принёс только чужой код (01M1TQ0ZCYJ6TESZ2KGJ6AWYNH) и не
  затронул зону этой задачи.
- `docs/adr/0014-budget-default-and-role-cap.md` — правка AC-3
  (`config.BUDGET_CALIBRATION_TABLE`/`config.
  BUDGET_CALIBRATION_FLOOR_USD`) сделана ещё в исходном коммите
  `0490e10b`, до итерации 1, и с тех пор не менялась — без изменений.

## Фаза A: проверка плана

PLAN.md не менялся с итерации 1 в части «Подход»/«Шаги»/«Покрытие
требований»/«Влияние на систему» — только добавлены разделы «Возврат:
замечания ревью итерации 1 (R1-F1, R1-F2)» с описанием обеих правок и
перепрогонов. Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (таблица `config.BUDGET_CALIBRATION_TABLE` + пол $25, ADR-0014 п.7 ссылается на константу) | OK | Без изменений с итерации 1 — `docs/adr/0014-budget-default-and-role-cap.md:68-70` ссылается на имена констант, чисел не дублирует. |
| 2 (`new`: ориентир+рамка, предупреждение при занижении >1/3, не отказывает) | OK | R1-F1 исправлен: `_TZ_ZONES_RE` (`orchestrator/catalog.py:110-121`) заякорен на начало строки (`re.M`) и продолжает захват до пустой строки/следующей метки-раздела. Прогнано на реальном `TZ.md` этой же задачи: `catalog._tz_calibration_inputs(...)` -> `(20.0, 4, 5)` (было `zone_files=1`) — верно отражает 5 путей зоны из ТЗ. |
| 3 (гейт SPEC: ориентир+`budget_usd` рядом с «дальше:», предупреждение при занижении >1/3, не отказывает) | OK | Без изменений с итерации 1. |
| 4 (тесты: границы таблицы, появление/отсутствие предупреждения в обеих точках, отсутствие отказа, регрессия test_catalog*/test_budget*/test_fsm*) | OK | Новый `tests/test_catalog_tz_zones_parsing.py` (2 теста, оба сценария R1-F1) зелёный; 21 приёмочный+юнит тест зоны задачи и 336 тестов смежных модулей (`test_catalog*`, `test_zones_*`, `test_fsm*`, `test_invariants`, `test_cmd_approve_dispatch`, `test_pull`, `test_review_package`, `test_guard_split_signals`, `test_split_assessment_merge_gate`, `test_new_argv_parsing`, `test_spec_budget`) — все зелёные, без правки существующих ассертов. |

## Замечания

Новых замечаний нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/catalog.py:110-121 | `_TZ_ZONES_RE` ловил первое по тексту вхождение «Зоны:» (в т.ч. в прозе) и обрезался по первому `\n` | ориентир калибровки на `new` считался по неверному числу файлов зоны (до 2х занижения) | Проверено: regexp заякорен на начало строки (`re.M`), захват продолжается за перенос до пустой строки/метки-раздела; на реальном `tasks/01M1TQ11K4WJZD7ZE3MR0J4ZK4/TZ.md` даёт верные `(20.0, 4, 5)`. `tests/test_catalog_tz_zones_parsing.py` (2 теста, оба сценария — прозаическое упоминание и перенос строки) зелёный. Класс дефекта закрыт полностью, второго вхождения «Зоны:» или другого варианта переноса в diff не найдено. |
| R1-F2 | accepted | tasks/01M1TQ11K4WJZD7ZE3MR0J4ZK4/PLAN.md, раздел «Приложение» | диф-приложение на `skills/spec-authoring.md` не применялся к актуальной голове ветки (`git apply --check` падал) | Оператор не смог бы применить диф-приложение как есть | Проверено: диф в PLAN.md перегенерирован против текущего содержимого `skills/spec-authoring.md` (учитывает уже влитую правку `979023a8`, задача 01M1THKTJ7). `git apply --check` на диф из PLAN.md против чистого дерева текущей головы ветки — пройден (воспроизведено этим шагом: извлёк блок `diff` из PLAN.md, применил `git apply --check` — успех). |

Реестр закрыт целиком (пуст незакрытых записей).

## Вердикт

approved

## Проверено исполнением

- `python3 -c "..."` — прямой вызов `orchestrator.catalog._tz_calibration_inputs` на реальном `tasks/01M1TQ11K4WJZD7ZE3MR0J4ZK4/TZ.md` → `(20.0, 4, 5)` (было `zone_files=1` до фикса R1-F1).
- Извлёк diff-блок из `PLAN.md` («Приложение: диф `skills/spec-authoring.md`») в отдельный файл и прогнал `git apply --check` на нём против чистого дерева текущей головы ветки — успех (R1-F2 подтверждён).
- `python3 -m unittest tests.test_catalog_tz_zones_parsing tasks.01M1TQ11K4WJZD7ZE3MR0J4ZK4.acceptance_tests.test_ac1_ac2_calibration_table tasks.01M1TQ11K4WJZD7ZE3MR0J4ZK4.acceptance_tests.test_ac5_ac6_ac7_ac8_new_hint tasks.01M1TQ11K4WJZD7ZE3MR0J4ZK4.acceptance_tests.test_ac9_ac10_ac11_gate_hint tasks.01M1TQ11K4WJZD7ZE3MR0J4ZK4.acceptance_tests.test_ac_manual_and_skip_markers` — 21 тест, все зелёные.
- `python3 -m unittest tests.test_catalog_new_race tests.test_catalog_status_log tests.test_zones_approve tests.test_zones_gate tests.test_split_assessment_merge_gate tests.test_new_argv_parsing tests.test_spec_budget tests.test_fsm_autogate tests.test_fsm_branch_correct_status_reads tests.test_fsm_draft_mr_reentry tests.test_fsm_map_conflict_autoresolve tests.test_fsm_map_regen tests.test_fsm_merge_conflict_note tests.test_fsm_merge_gate_done_snapshot tests.test_fsm_retro tests.test_fsm_review_rework_gate tests.test_invariants tests.test_cmd_approve_dispatch tests.test_pull tests.test_review_package tests.test_guard_split_signals tests.test_fsm_advance_gate_framework tests.test_fsm_advance_gate_smoke` — 336 тестов, все зелёные (134.65s).
- `git diff e306e1858cfb369220a4d41c641a87bd2df09ab3..HEAD --stat -- orchestrator/config.py orchestrator/catalog.py orchestrator/budget.py orchestrator/fsm.py docs/adr/0014-budget-default-and-role-cap.md tasks/01M1TQ11K4WJZD7ZE3MR0J4ZK4/` — пусто (подтверждает, что после фикса R1-F1 зона задачи не менялась; «подтяжка main» принесла только чужой код).
- `python3 scripts/codebase_map.py` (регенерация на месте) + `git diff --stat -- docs/codebase-map.md` — расходится только `built_at_sha` (не признак дефекта, review-checklist); `git checkout -- docs/codebase-map.md` вернул дерево в чистое состояние.
- `python3 scripts/guard.py tasks/01M1TQ11K4WJZD7ZE3MR0J4ZK4/SPEC.md tasks/01M1TQ11K4WJZD7ZE3MR0J4ZK4/PLAN.md tasks/01M1TQ11K4WJZD7ZE3MR0J4ZK4/ANSWER-1.md tasks/01M1TQ11K4WJZD7ZE3MR0J4ZK4/ANSWER-2.md tasks/01M1TQ11K4WJZD7ZE3MR0J4ZK4/TZ.md` — «GUARD: ок (5 файлов)».
- `git status --short` — чисто (кроме материализованных untracked `tasks/`).
- Полный набор `tests/` не гонял (решение Оператора 05.09 — гоняет CI на каждый пуш) — прогнаны планка задачи и все модули, пересекающиеся с зоной задачи (`catalog`, `fsm`, `budget`/`config`-потребители, `zones_*`, `invariants`, `guard_split_signals`).

## Предложения системе

- Класс «база инкрементального диффа пакета указывает на коммит-фикс
  ревьюверского замечания, а не на коммит, зафиксировавший ПРЕДЫДУЩИЙ
  вердикт ревью» — здесь диф скрыл собственно то, ради чего идёт
  итерация (сам фикс R1-F1), и одновременно раздул пакет содержимым
  чужой задачи, пришедшим позже подтяжкой main. Тот же класс, что уже
  отмечен в копилке review-checklist («Инкрементальный diff пакета —
  пустой не значит «без изменений»», T082/T087) — здесь дифф не пуст,
  но вводит в заблуждение симметрично: не «пусто, хотя менялось», а
  «полно, но не тем».
