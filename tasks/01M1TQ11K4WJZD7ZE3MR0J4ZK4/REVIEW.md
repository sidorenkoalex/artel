---
task: 01M1TQ11K4WJZD7ZE3MR0J4ZK4
type: review
author_role: reviewer
status: changes_requested        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 5    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: подсказка потолка по калибровке при new и на гейте SPEC

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (таблица `config.BUDGET_CALIBRATION_TABLE` + пол $25, ADR-0014 п.7 ссылается на константу) | OK | Значения и граничные условия проверены прогоном `test_ac1_ac2_calibration_table.py` (все 9 тестов зелёные) и вручную по логике `budget.recommended_budget_usd`; `docs/adr/0014-budget-default-and-role-cap.md` п.7 ссылается на имя константы, чисел не дублирует (AC-3, manual). |
| 2 (`new`: ориентир+рамка, предупреждение при занижении >1/3, не отказывает) | реализовано не так | Механика (печать, порог 2/3, журнал, отсутствие отказа/изменения потолка) сама по себе верна и покрыта тестами AC-5..AC-8 — но разбор поля «Зоны:» из ТЗ (`_TZ_ZONES_RE`) даёт неверное число файлов на РЕАЛЬНОМ ТЗ этой же задачи (см. R1-F1) — итоговый ориентир, который увидел бы Оператор, был бы просто неверным числом. |
| 3 (гейт SPEC: ориентир+`budget_usd` рядом с «дальше:», предупреждение при занижении >1/3, не отказывает) | OK | Проверено прогоном `test_ac9_ac10_ac11_gate_hint.py` (5/5 зелёные) и чтением `_approve_spec_gate`: вызов подсказки — единой точкой до ветвления `skip_reason`, `budget_usd`/переход не меняются. |
| 4 (тесты: границы таблицы, появление/отсутствие предупреждения в обеих точках, отсутствие отказа, регрессия test_catalog*/test_budget*/test_fsm*) | OK | 19 приёмочных тестов зелёные; `tests/test_catalog*.py`, `tests/test_fsm*.py` (test_budget*.py не существует) и смежные (`test_zones_*`, `test_invariants`, `test_cmd_approve_dispatch`, `test_pull`, `test_review_package`, `test_guard_split_signals`) — 326 тестов, все зелёные, без правки ассертов. |

## Замечания

- major — `orchestrator/catalog.py:110` (`_TZ_ZONES_RE = re.compile(r"Зоны:\s*(.*)")`) и `orchestrator/catalog.py:126` (её использование в `_tz_calibration_inputs`) — регэксп ищет ПЕРВОЕ по тексту буквальное вхождение «Зоны:» через `.search()` без привязки к началу строки, и без `re.S` захватывает только до ближайшего `\n`. Оба свойства ломаются на РЕАЛЬНОМ ТЗ этой же задачи (`tasks/01M1TQ11K4WJZD7ZE3MR0J4ZK4/TZ.md`): требование 2 ТЗ ещё до самой строки `Зоны: ...` упоминает формат в прозе — «...число путей в «Зоны:») и разницу...» — и именно это вхождение регэксп ловит первым; отдельно сама строка `Зоны: orchestrator/config.py, orchestrator/catalog.py,\norchestrator/budget.py, ...` физически перенесена на вторую строку (обычный перенос длинной строки), что тоже обрезало бы счёт файлов даже без первой проблемы. Проверено исполнением напрямую: `catalog._tz_calibration_inputs(open("tasks/01M1TQ11K4WJZD7ZE3MR0J4ZK4/TZ.md").read())` возвращает `zone_files=1` вместо фактических 5 путей зоны, из-за чего `recommended_budget_usd` посчитал бы ориентир `$35` вместо верных `$70` — при Рамке $20 предупреждение в этом конкретном случае всё равно срабатывает (оба ориентира выше порога 2/3), но число `~$M`, которое увидит Оператор, было бы попросту неверным — то есть ИМЕННО тот класс ошибки (двукратное занижение ориентира калибровки), ради устранения которого эта задача заведена. Приёмочные фикстуры (`_sandbox.py::tz_text`) не ловят ни один из двух сценариев: тестовое ТЗ никогда не упоминает слово «Зоны» второй раз в прозе и держит саму строку `Зоны: ...` короткой (не переносится). Предложение: заякорить регэксп на начало строки (`re.compile(r"^Зоны:\s*(.*)", re.M)`), и продлить захват на строки-продолжения переноса тем же приёмом, что уже применяет `_TZ_TREBUETSYA_RE` (до пустой строки/новой метки), плюс приёмочный тест на ТЗ, где «Зоны:» упомянуто в прозе раньше самой строки и/или строка «Зоны:» переносится на вторую физическую строку.
- major — `tasks/01M1TQ11K4WJZD7ZE3MR0J4ZK4/PLAN.md`, раздел «Приложение: диф `skills/spec-authoring.md`» — самопроверка «`git apply --check` на чистом дереве ... — Пройден» не подтверждается на актуальной голове ветки: `git apply --check` на этот диф прямо сейчас отказывает (`error: patch failed: skills/spec-authoring.md:29`, `patch does not apply`). Причина — коммит `979023a8` (задача 01M1THKTJ7, уже влитая в main и подтянутая в эту ветку тем самым мержем main, который PLAN описывает в разделе «Возврат: конфликт подтяжки main») уже переписал те же строки `skills/spec-authoring.md` (базовый уровень `~25` → `~35`, добавлено предложение «Планка не ниже $25 ни для одной задачи») — именно тот класс коллизии, который сам разработчик предсказал в «Предложения системе» этого же PLAN.md, но не перепроверил `git apply --check` заново ПОСЛЕ разрешения конфликта подтяжки main. Применить это диф-приложение Оператору сейчас не удастся ни на PLAN-гейте, ни позже. Предложение: перегенерировать диф против текущего содержимого `skills/spec-authoring.md` (после мержа) и заново прогнать `git apply --check` перед сдачей PLAN.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | orchestrator/catalog.py:110,126 | `_TZ_ZONES_RE` ловит первое по тексту вхождение «Зоны:» (в т.ч. в прозе) и обрезается по первому `\n` | ориентир калибровки на `new` считается по неверному числу файлов зоны — вплоть до 2х занижения (демонстрировано на реальном TZ.md задачи: 1 вместо 5 файлов, $35 вместо $70) | `_TZ_ZONES_RE` заякорен на начало строки (`re.M`) и продолжает захват за перенос строки до пустой строки/следующей метки-раздела (`_TZ_LABEL_LINE`) — тот же приём, что у `_TZ_TREBUETSYA_RE`. Добавлен `tests/test_catalog_tz_zones_parsing.py` (2 теста: прозаическое упоминание «Зоны:» игнорируется, перенос строки не обрезает счёт). Проверено на реальном TZ.md задачи: `zone_files=5` (было 1), ориентир `$70.00` (было бы `$35`) — коммит `e306e185` |
| R1-F2 | fixed | tasks/01M1TQ11K4WJZD7ZE3MR0J4ZK4/PLAN.md (раздел «Приложение») | диф-приложение на `skills/spec-authoring.md` не применяется к текущей голове ветки (`git apply --check` падает) — самопроверка PLAN устарела после мержа main (коммит 979023a8 уже переписал те же строки) | Оператор не сможет применить диф-приложение как есть — требование 1 (AC-3/AC-4 по духу — синхронизация скила с ADR) останется невыполненным для `skills/spec-authoring.md` | Диф-приложение в PLAN.md перегенерирован против текущего содержимого `skills/spec-authoring.md` (голова ветки после мержа 979023a8): та же замена чисел на ссылку на константу, но базой взят актуальный текст строк 29–39 (уже несущий «~35»/«Планка не ниже $25»). `git apply --check` на новый диф против чистого дерева — пройден (см. «Проверено исполнением» PLAN.md) |

## Вердикт

changes_requested — почини оба замечания реестра (R1-F1: разбор «Зоны:» в `catalog.py`, с приёмочным тестом на реалистичный ТЗ; R1-F2: перегенерируй диф-приложение на `skills/spec-authoring.md` против текущей головы ветки и заново подтверди `git apply --check`), остальная реализация (требования 1, 3, 4) замечаний не вызывает.

## Проверено исполнением

- `python3 -m unittest tasks.01M1TQ11K4WJZD7ZE3MR0J4ZK4.acceptance_tests.test_ac1_ac2_calibration_table tasks.01M1TQ11K4WJZD7ZE3MR0J4ZK4.acceptance_tests.test_ac5_ac6_ac7_ac8_new_hint tasks.01M1TQ11K4WJZD7ZE3MR0J4ZK4.acceptance_tests.test_ac9_ac10_ac11_gate_hint` — 19 тестов, все зелёные.
- `python3 -m unittest tests.test_catalog_new_race tests.test_catalog_status_log tests.test_zones_approve tests.test_zones_gate tests.test_split_assessment_merge_gate tests.test_new_argv_parsing tests.test_spec_budget tests.test_fsm_autogate tests.test_fsm_branch_correct_status_reads tests.test_fsm_draft_mr_reentry tests.test_fsm_map_conflict_autoresolve tests.test_fsm_map_regen tests.test_fsm_merge_conflict_note tests.test_fsm_merge_gate_done_snapshot tests.test_fsm_retro tests.test_fsm_review_rework_gate tests.test_invariants tests.test_cmd_approve_dispatch tests.test_pull tests.test_review_package tests.test_guard_split_signals` — 326 тестов, все зелёные (в т.ч. `StdlibOnlyImportsInvariantTest` — новые импорты `budget` в `fsm.py` и `scripts.guard` в `catalog.py` циклов не заводят).
- `python3 scripts/codebase_map.py --check` — карта актуальна (без учёта `built_at_sha`).
- `python3 -c "..."` — ручной прогон `orchestrator.catalog._tz_calibration_inputs` и `orchestrator.budget.recommended_budget_usd`/`calibration_warning` на реальном `tasks/01M1TQ11K4WJZD7ZE3MR0J4ZK4/TZ.md` — воспроизвёл R1-F1 (`zone_files=1` вместо 5, ориентир $35 вместо $70).
- `git apply --check` на диф-приложение из «Приложение» PLAN.md против текущей головы ветки — отказ (`patch does not apply`), воспроизвёл R1-F2; `git merge-base --is-ancestor 979023a8 HEAD` подтвердил, что конфликтующий коммит уже в ветке.

## Предложения системе

- Класс «диф-приложение на защищённый путь подготовлен ДО мержа main, `git apply --check` подтверждён, но не перепроверен ПОСЛЕ последующего разрешения конфликта подтяжки main» — конвенция требует проверки «на чистом дереве», но не уточняет, что дерево обязано быть АКТУАЛЬНЫМ на момент сдачи шага, а не на момент написания диффа; в этой задаче разработчик даже предсказал коллизию в «Предложения системе», но не связал это с необходимостью перепроверки уже подготовленного приложения после своего же `git merge main`.
