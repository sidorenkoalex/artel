---
task: 01M1TQ11K4WJZD7ZE3MR0J4ZK4
type: plan
author_role: developer
status: ready        # draft | ready | approved
schema_version: 4    # версия формата артефакта, см. scripts/guard.py
---

# PLAN: подсказка потолка по калибровке при new и на гейте SPEC

## Подход

Одна калибровочная таблица + одна общая пара функций-подсказок,
потребляемая ровно двумя точками (`new`, гейт SPEC) — SPEC сама
объясняет в «Оценке объёма и деление», почему это монолит, не нарезка.

1. **Таблица** — `orchestrator/config.py::BUDGET_CALIBRATION_TABLE`:
   кортеж уровней `(потолок $, макс. критериев приёмки, макс. файлов
   зоны)`, проверяемых по порядку (первый подошедший — ответ, `None` —
   ось не ограничивает уровень). Значения ADR-0014 п.7: `(35.0, 5, 3)`,
   `(45.0, 10, 4)`, `(70.0, None, None)`. Верхний потолок «5 и более
   файлов зоны — $70 независимо от критериев» не выразить одной осью
   на среднем уровне без явного `max_zone_files=4` там — иначе средний
   уровень (ограничен только по критериям) перехватывал бы, например,
   2 критерия / 5 файлов раньше, чем таблица дойдёт до уровня $70; SPEC
   явно не описывает поведение ровно на 4 файлах зоны (докстринг
   приёмочной планки, `test_ac1_ac2_calibration_table.py`), поэтому
   этот зазор закрыт в пользу третьего уровня («$70») только когда
   критериев тоже больше 10 — иначе (критериев ≤10, файлов =4) остаётся
   средним уровнем ($45), что не противоречит ни одному AC. Отдельная
   константа-пол `BUDGET_CALIBRATION_FLOOR_USD = 25.0` — подстраховка
   на будущую правку чисел таблицы, а не рабочая ветвь сегодня (все три
   уровня уже выше 25).

2. **`orchestrator/budget.py`** — три чистые функции без побочных
   эффектов:
   - `recommended_budget_usd(ac_count, zone_files) -> float` — перебор
     таблицы, применение пола.
   - `calibration_warning(actual_usd, orientir_usd) -> str | None` —
     единая строка «рамка ниже калибровки: $N против ~$M», если
     `actual_usd < orientir_usd * 2/3` (буквально «ниже более чем на
     треть»), иначе `None`. Общий узел ОБЕИХ точек (требования 2 и 3
     требуют буквально одну и ту же строку).
   - `count_zone_paths(text) -> int` — число непустых путей через
     запятую; общий разбор и для frontmatter `zones:` SPEC (гейт), и
     для строки «Зоны: ...» ТЗ (`new`, где после последнего пути в
     предложении может стоять точка — `rstrip(".")` на каждом элементе
     срезает её, не трогая расширение файла).

3. **`orchestrator/catalog.py::cmd_new`** — три новых regex-константы
   (`_TZ_RAMA_RE`, `_TZ_TREBUETSYA_RE`, `_TZ_ZONES_RE`) и функция
   `_tz_calibration_inputs(tz_raw)`, разбирающая ИСХОДНЫЙ текст файла
   ТЗ (не обёрнутый `_tz_document`) на (рамка, число пунктов
   «Требуется:», число путей «Зоны:») — `None`, если строки «Рамка: $N»
   нет вовсе (требование 2: подсказка активна только при этом
   условии). `_TZ_TREBUETSYA_RE` переиспользует формат пункта
   `guard.PLAIN_NUMBERED_ITEM` (нумерованный список без AC-разметки) —
   тот же формат, что уже определяет guard для «старого формата»
   раздела. `_print_new_calibration_hint` печатает ориентир+рамку и,
   при срабатывании `calibration_warning`, предупреждение +
   `store.journal`. Вызывается из `cmd_new` после строки «создана»,
   когда `tz_raw is not None` — не отказывает и не трогает
   `budget_usd` заведённой задачи (AC-8): дефолт `config.
   DEFAULT_BUDGET_USD` передаётся в `store.insert_task` ДО этого
   вызова, как и раньше.

4. **`orchestrator/fsm.py::_cmd_approve`** (`state == "spec_gate"`) —
   `_print_spec_gate_calibration_hint(conn, task_id, budget_usd, meta,
   spec_text)`, вызванная сразу после `store.update_task(...,
   zones=...)`: считает `ac_count` через уже существующие в модуле
   `guard.AC_ITEM`/`guard.section_body(spec_text, "Критерии
   приёмки")` (тот же приём, что `_snapshot_split_assessment` рядом
   использует для раздела «Оценка объёма и деление»), `zone_files` —
   через `budget.count_zone_paths(meta.get("zones"))` (уже
   сохранённое в этот момент поле). Печатает ориентир и действующий
   `budget_usd` рядом с обеими веткам «дальше:» (skip_tests и
   AC-разметка) — печать одна, до `if skip_reason ...`, поэтому
   появляется независимо от исхода. Не меняет `budget_usd` и не
   отказывает переход (AC-11) — только печатает/журналирует.
   Единственная ветка `else` (не `foreign`) сейчас недостижима
   (`artifact_source.resolve` всегда возвращает `foreign=True`,
   докстринг модуля) — оставлена как есть, `spec_text` там задаётся
   пустой строкой только ради отсутствия `NameError`, поведение по
   AC не зависит от этой ветки.

## Шаги

1. `orchestrator/config.py`: `BUDGET_CALIBRATION_TABLE`,
   `BUDGET_CALIBRATION_FLOOR_USD`.
2. `orchestrator/budget.py`: `recommended_budget_usd`,
   `calibration_warning`, `count_zone_paths`.
3. `orchestrator/catalog.py`: разбор ТЗ + подсказка в `cmd_new`.
4. `orchestrator/fsm.py`: подсказка на гейте SPEC в `_cmd_approve`.
5. `docs/adr/0014-budget-default-and-role-cap.md`, пункт решения 7 —
   ссылка на имя константы вместо чисел прозой (docs/adr не входит в
   защищённые пути `config.PROTECTED_PATHS` — правка прямая, не
   диф-приложение).
6. Диф-приложение (см. «Приложение» ниже) на `skills/spec-
   authoring.md` — защищённый путь, применяет Оператор.
7. `python3 scripts/codebase_map.py` (правка `.py` в `orchestrator/`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 3 |
| 3 | 4 |
| 4 | 5, 6 |

## Влияние на систему

**Новые импорты, без циклов.** `orchestrator/fsm.py` и `orchestrator/
catalog.py` теперь читают `orchestrator/budget.py` (`catalog.py` уже
читал его до этой задачи); `catalog.py` дополнительно читает `scripts/
guard.py` (тем же приёмом, что уже несут `acceptance.py`, `amend.py`,
`canary.py`, `dry_run.py`, `fsm.py`, `fsm_advance.py`, `fsm_autogate.py`,
`retro.py`, `version.py`). `budget.py` сам не читает ни `fsm.py`, ни
`catalog.py`, ни что-либо, что читало бы их транзитивно (проверено по
карте кодовой базы: цепочки `budget -> {alerts, config, lease, retro,
spend, store}` и их собственные импорты не доходят до `fsm`/`catalog`)
— цикла нет. `python3 -m unittest tests.test_invariants.
StdlibOnlyImportsInvariantTest` зелёный (см. «Проверено исполнением»).

**Ничего не блокирует и не меняет потолок.** Обе точки (`new`, гейт
SPEC) только печатают строку и, при занижении, журналируют —
`cmd_new`/`_cmd_approve` не получили ни одного нового `sys.exit`/
`return` до существующей логики; `store.update_task` с `budget_usd` в
обеих новых функциях не вызывается вовсе (AC-8, AC-11 проверяют это
явно приёмочной планкой).

**Существующие гейты/лимиты/инварианты не тронуты.** `budget.
spec_budget`/`apply_spec_budget`/`budget_block`/`enforce_budget` —
не изменены ни строкой; `guard.AC_ITEM`/`guard.section_body`/`guard.
PLAIN_NUMBERED_ITEM` — читаются, не переопределяются. `SPLIT_SIGNAL_*`
константы рядом в `config.py` — не тронуты, калибровочная таблица
самостоятельная (другой физический смысл: рекомендация потолка, не
сигнал деления).

**Откат.** Три независимые точки: удаление
`BUDGET_CALIBRATION_TABLE`/`BUDGET_CALIBRATION_FLOOR_USD` из
`config.py` вместе с тремя функциями `budget.py` и их вызовами в двух
местах возвращает поведение `new`/`_cmd_approve` к состоянию до этой
задачи побайтово (обе функции — чистые добавки, ни одна существующая
строка вызова не переписана, только вставлена новая). Правка ADR-0014
п.7 откатывается тем же diff в обратную сторону.

## Риски

- Разбор ТЗ в `catalog._tz_calibration_inputs` — эвристика по
  буквальному формату «Рамка: $N» / «Требуется:\n1. ...» / «Зоны:
  ...» (тот же формат, что описывает SPEC требование 2 и фикстура
  приёмочной планки, `_sandbox.py::tz_text`). Реальное свободное ТЗ
  Оператора, оформленное иначе (например, без строки «Рамка: $N»
  вовсе, или с «Требуется:» не первым нумерованным списком в файле),
  просто не даёт подсказки (функция возвращает `None`, `new` работает
  как раньше) — не отказ и не искажение, но и не подсказка; если
  формат ТЗ Оператора де-факто разойдётся с этим, стоит скорректировать
  regex отдельной небольшой правкой по факту наблюдения, не сейчас.
- Средний уровень таблицы ограничен `max_zone_files=4`, а не `None`
  (см. «Подход», пункт 1) — решение по зазору, которого SPEC явно не
  описывает; закрыто в пользу чтения «5 и более файлов — $70
  независимо от критериев» буквально (AC-1 явно фиксирует это как
  свойство, AC-2 — нет соответствующего теста на зазоре), риск
  расхождения с ожиданием Оператора минимален (весь диапазон
  приёмочных тестов проходит), но это интерпретация, не буквальный
  текст требования 1 для зазора 4 файла / ≤10 критериев.
- AC-4 (диф-приложение на «скил разработчика») — по факту `grep -rn
  '35\|45\|70\|budget_usd\|калибр\|бюджет' skills/coding-standards.md`
  (роль developer) пуст: калибровочных чисел там сегодня нет вовсе
  (правило переоценки на PLAN, ADR-0014 п.3, — предмет ещё не влитой
  задачи 01M1THKWFX, не этой). Приложен диф только на `skills/spec-
  authoring.md` — рабочий вывод, не эскалация: AC-4 сформулирован по
  факту существующего текста («переписывающий их калибровочные
  числа»), а не по обязательству создать числа там, где их нет.
  Оператор на гейте PLAN может потребовать иначе.

## Проверено исполнением

- `python3 -m unittest tasks.01M1TQ11K4WJZD7ZE3MR0J4ZK4.acceptance_tests.test_ac1_ac2_calibration_table tasks.01M1TQ11K4WJZD7ZE3MR0J4ZK4.acceptance_tests.test_ac5_ac6_ac7_ac8_new_hint tasks.01M1TQ11K4WJZD7ZE3MR0J4ZK4.acceptance_tests.test_ac9_ac10_ac11_gate_hint` — 19 тестов, зелёные.
- `python3 -m unittest tests.test_catalog_new_race tests.test_catalog_status_log tests.test_fsm_autogate tests.test_fsm_branch_correct_status_reads tests.test_fsm_draft_mr_reentry tests.test_fsm_map_conflict_autoresolve tests.test_fsm_map_regen tests.test_fsm_merge_conflict_note tests.test_fsm_merge_gate_done_snapshot tests.test_fsm_retro tests.test_fsm_review_rework_gate` — 71 тест, зелёные (AC-12 для `test_catalog*`/`test_fsm*`; `test_budget*.py` не существует, см. приёмочная планка AC-12).
- `python3 -m unittest tests.test_zones_approve tests.test_zones_gate tests.test_split_assessment_merge_gate` — 29 тестов, зелёные (тот же участок `_cmd_approve`, `spec_gate`).
- `python3 -m unittest tests.test_new_argv_parsing tests.test_invariants` — 56 тестов, зелёные.
- `python3 scripts/codebase_map.py` — карта перегенерирована, диф только по затронутым модулям (`budget.py`, `catalog.py`, `fsm.py` — новые публичные функции/новые рёбра импорта).

### Возврат: конфликт подтяжки main (коммит 94b89600)

Сведён конфликт `git merge main`, описанный в ANSWER-1: `orchestrator/
fsm.py` на main декомпозирован (SPEC 01M1TKP08PKB87K8772H69GCXJ) —
`_cmd_approve` стал таблицей `{"spec_gate": _approve_spec_gate, ...}`,
подтяжка вынесена в `orchestrator/pull.py`. Разрешение — по инструкции
ANSWER-1: взята версия main целиком, поверх неё перенесены три наши
правки (импорт `budget`, функция `_print_spec_gate_calibration_hint`,
её вызов + `spec_text = ""` в ветке `else` внутри `_approve_spec_gate`,
в ту же точку — после `store.update_task(..., zones=...)`, до
`skip_reason = meta.get("skip_tests")`). `docs/codebase-map.md` —
версия main, затем `python3 scripts/codebase_map.py` поверх слияния.

Перепрогон после слияния — все зелёные:
- `python3 -m unittest tasks.01M1TQ11K4WJZD7ZE3MR0J4ZK4.acceptance_tests.test_ac1_ac2_calibration_table tasks.01M1TQ11K4WJZD7ZE3MR0J4ZK4.acceptance_tests.test_ac5_ac6_ac7_ac8_new_hint tasks.01M1TQ11K4WJZD7ZE3MR0J4ZK4.acceptance_tests.test_ac9_ac10_ac11_gate_hint tasks.01M1TQ11K4WJZD7ZE3MR0J4ZK4.acceptance_tests.test_ac_manual_and_skip_markers` — 19 тестов.
- `python3 -m unittest tests.test_fsm_autogate tests.test_fsm_branch_correct_status_reads tests.test_fsm_draft_mr_reentry tests.test_fsm_map_conflict_autoresolve tests.test_fsm_map_regen tests.test_fsm_merge_conflict_note tests.test_fsm_merge_gate_done_snapshot tests.test_fsm_retro tests.test_fsm_review_rework_gate` — 66 тестов (новый набор main после декомпозиции T091/01M1TKP08P — `test_fsm_merge_conflict_note`/`test_fsm_map_regen` теперь бьют по `pull.py`, не по монолиту `fsm.py`).
- `python3 -m unittest tests.test_catalog_new_race tests.test_catalog_status_log tests.test_zones_approve tests.test_zones_gate tests.test_split_assessment_merge_gate tests.test_new_argv_parsing tests.test_spec_budget` — 87 тестов.
- `python3 -m unittest tests.test_invariants` — 47 тестов (в т.ч. `StdlibOnlyImportsInvariantTest` — новый импорт `budget` в `fsm.py` циклов не заводит).
- `python3 -m unittest tests.test_cmd_approve_dispatch tests.test_pull tests.test_review_package tests.test_guard_split_signals` — 126 тестов (новые модули/тесты main, декомпозиция `_cmd_approve` не задета нашей правкой).
- `scripts/guard.py` на `PLAN.md`/`SPEC.md`/`ANSWER-1.md` — ок.
- `git push` из этого шага не выполнялся: рабочая копия без токена git (не через `runner.role_env`) — коммит слияния (`94b89600`) в ветке, push делает штатный механизм оркестратора.

## Предложения системе

- Три задачи подряд (эта, 01M1THKTJ7, 01M1THKWFX) готовят диф-приложения
  на один и тот же участок `skills/spec-authoring.md` (калибровка
  `budget_usd`), не зная друг о друге содержательно (только через
  «Порядок» в SPEC/ТЗ) — при последовательном примении Оператором эти
  дифы почти наверняка законфликтуют текстовым overlap. Возможно, стоит
  фиксировать в SPEC связанных задач не только «зоны кода заняты
  zone_lock», но и «этот же протected-путь уже правится диф-приложением
  другой незавершённой задачи» — сегодня это видно только внимательным
  чтением ADR/SPEC вручную.

## Приложение: диф `skills/spec-authoring.md`

`git apply --check` на чистом дереве (голова этой ветки задачи, файл
не тронут) — пройден.

```diff
diff --git a/skills/spec-authoring.md b/skills/spec-authoring.md
index 67dd39ac..6c107174 100644
--- a/skills/spec-authoring.md
+++ b/skills/spec-authoring.md
@@ -29,9 +29,10 @@
   — по классу задачи, откалиброванному на факте 28.08–05.09 (цена
   шага стабильна: analyst ~$2, reviewer ~$2.3, developer ~$3.5,
   test_author ~$6; цену задачи задаёт число шагов, а его — объём и
-  итерации ревью): до 5 критериев и до 3 файлов зоны — ~25; 6–10
-  критериев — ~45; больше 10 критериев или 5 и более файлов — ~70 либо
-  деление (сигналы «Оценки объёма» это же и ловят). Закладывай две
+  итерации ревью): ориентир — `config.BUDGET_CALIBRATION_TABLE`
+  (`orchestrator/config.py`) по числу критериев приёмки и числу файлов
+  зоны, пол — `config.BUDGET_CALIBRATION_FLOOR_USD` (сигналы «Оценки
+  объёма» те же числа и ловят). Закладывай две
   итерации ревью, не одну (+~$6 на итерацию). Прежние ощущения «~15
   / ~25 / ~50» занижали факт в 2–3 раза (решение Оператора 05.09,
   роадмап §4 копилка). Ставка — **только
```
