---
task: 01M1TKNXX5YN5KT4WHG4T44JWV
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: R2 — `fsm_advance.py`: гейты `in_dev` и `review` как предикаты с единым исходом

## Подход

Вводим единый неизменяемый тип исхода гейта `GateRefusal(action, detail,
hint)` (`None` — гейт пройден) и один каркас `_run_gates(conn, task_id,
gates)`, применяющий список гейтов-предикатов по порядку: на первом
отказе — ровно один `store.journal(conn, task_id, "fsm", refusal.action,
refusal.detail)`, печать `[{task_id}] переход отклонён: {detail}` и (если
есть) `  дальше: {hint}`, возврат `True` (переход отклонён). Все гейты
пройдены — `False`, без единой записи.

Область применения каркаса — только те проверки, что УЖЕ буквально
следуют этому шаблону «проверка → один `store.journal` c текстом
"переход отклонён: ..." → печать той же строки → печать подсказки →
`return`», и при этом не нуждаются в данных успешного прохода дальше по
коду (иначе пришлось бы либо протаскивать данные через тип исхода,
которого SPEC не предусматривает, либо пересчитывать их повторно ценой
двойной работы/риска). Проверены все кандидаты `in_dev`/`review`:

- `in_dev`: `_capacity_gate_refuses`, `_zones_gate_refuses`,
  `_review_rework_gate_refuses` — точное совпадение шаблона (см. таблицу
  ниже). Это ровно три гейта, названные в SPEC «Контекст» (ёмкость,
  зоны, рубеж «замечания не отработаны») как предмет дедупликации этой
  задачи.
- `review`: блок «голова не в origin» (push в origin) и блок «Реестр
  замечаний» — тоже точное совпадение шаблона, оба не нуждаются в данных
  после прохода (код после них не использует ничего, что вычислил гейт).
  Выделены в новые гейты `_origin_push_gate`/`_registry_gate`.
- НЕ входят в каркас (сознательно, чтобы не расширять зону гейтов сверх
  дедупликации и не рисковать изменением поведения):
  - Проверка свежести вердикта (`iteration is None`) — журналирует
    action `"переход отклонён"` (без суффикса) и печатает
    `f"[{task_id}] {detail}"` БЕЗ префикса «переход отклонён: » —
    формат печати отличается от остальных гейтов буква-в-букву, значит
    это не копия того же шаблона, а самостоятельный случай. Остаётся
    отдельной функцией `_freshness_refuses` со своим форматом.
  - Проверка «acceptance_tests красные» — печатает три строки (короткое
    сообщение, сырой `tail` отдельной строкой, подсказка), а не
    «сообщение+подсказка» двух гейтов выше; сам расчёт (`acc_tdir`)
    нужен ПОСЛЕ прохода для `acceptance.summary`, то есть гейт не может
    быть чистым предикатом без побочных эффектов дальше по коду без
    двойного пересчёта `acceptance.materialize_from_branch` (реальная
    работа с git, не бесплатная переигровка). Остаётся веткой внутри
    `_review_approved`.
  - `fsm._dirty_refuses`, `fsm.guard_refuses`, `fsm._pull_main_or_escalate`
    — определены в `orchestrator/fsm.py`, вне зоны этой задачи (SPEC «Не
    входит»: `fsm.py` — R3); уже сами журналируют и печатают внутри
    (out-of-zone копии того же класса, R3 их не трогает). Вызываются как
    раньше, до/вокруг списка гейтов.

Существующие `_capacity_gate_refuses`/`_zones_gate_refuses`/
`_review_rework_gate_refuses` сохраняют публичную сигнатуру и поведение
(тесты `tests/test_capacity_gate.py`, `tests/test_zones_gate.py`,
`tests/test_fsm_review_rework_gate.py` зовут их напрямую и читают
журнал/stdout) — внутри они не изменились как логика, только вынесены в
чистые предикаты `_capacity_gate`/`_zones_gate`/`_review_rework_gate`
(без журнала/печати), обёрнутые в `_run_gates` с одним элементом списка.
`in_dev()` вызывает эти же предикаты списком через `_run_gates` напрямую
— это и есть устранение дублирования копий связки.

`review()` длиной 173 строки уменьшается декомпозицией на функции по
ветке вердикта (`_review_approved`, `_review_changes_requested`,
`_review_escalate`) — того же приёма, что уже применён в этом файле для
`in_dev`/`review`/`verifying`/`tests_writing` как отдельных функций
одного состояния (SPEC T091). Внутри `_review_approved` находятся два
новых гейта (`_origin_push_gate`, `_registry_gate`) через `_run_gates`.

`in_dev()` длиной 127 строк по той же причине не укладывается в ≤40
строк одним только вынесением трёх гейтов (они и раньше были отдельными
функциями — тело `in_dev` сокращает не их извлечение, а список вместо
трёх последовательных `if`). Оставшийся объём — лок `acceptance_tests/`
(три похожих отказа, не входящих в перечень SPEC «Контекст» — точечная,
специфичная для этой планки проверка, не копия шаблона трёх гейтов) и
ветка `PLAN.md status: escalate` — вынесены НЕ через `_run_gates`
(разные форматы печати/условий), а обычной декомпозицией на функции
`_acceptance_lock_refuses`/`_in_dev_plan_escalate`, тем же приёмом, что
`_review_approved`/`_review_changes_requested`/`_review_escalate` в
`review()`.

## Шаги

1. `GateRefusal` + `_run_gates` в `orchestrator/fsm_advance.py`; юнит-тесты
   каркаса (порядок, остановка на первом отказе, один `journal` на отказ,
   ноль записей при полном проходе) — синтетические гейты, без привязки
   к реальным проверкам.
2. `_capacity_gate`/`_zones_gate`/`_review_rework_gate` — чистые предикаты
   с той же логикой, что старые `_capacity_gate_refuses`/`_zones_gate_refuses`/
   `_review_rework_gate_refuses`, минус журнал/печать. Старые имена — тонкие
   обёртки через `_run_gates([...])`, сигнатуры не изменились.
3. `in_dev()` — список из трёх новых предикатов через один `_run_gates`
   вместо трёх последовательных `if _xxx_gate_refuses(...): return False`.
4. `review()` — извлечение `_origin_push_gate`/`_registry_gate` (через
   `_run_gates`) и декомпозиция тела на `_review_approved`/
   `_review_changes_requested`/`_review_escalate`; `_freshness_refuses` —
   отдельная функция (не через каркас, см. «Подход»).
5. `tests/test_fsm_advance_gate_framework.py` — юнит-тесты каркаса на
   синтетических гейтах (шаг 1). `tests/test_fsm_advance_gate_smoke.py` —
   смоук трёх сценариев (ёмкость/зоны/рубеж), журнал и stdout байт-в-байт;
   фикстура снята прогоном ДО правки кода (см. таблицу ниже, значения
   зафиксированы буквально в тесте).
6. Прогон `python3 -m unittest tests.test_capacity_gate tests.test_zones_gate
   tests.test_fsm_review_rework_gate tests.test_review_registry_gate
   tests.test_advance_guard tests.test_branch_freshness_gate
   tests.test_github_adapter tests.test_fsm_draft_mr_reentry
   tests.test_invariants tests.test_multitarget tests.test_multitarget_invariants
   tests.test_zone_lock tests.test_fsm_map_conflict_autoresolve
   tests.test_fsm_merge_conflict_note tests.test_review_freshness
   tests.test_step_refixation tests.test_advance_refusal_history
   tests.test_review_package tests.test_split_assessment_merge_gate
   tests.test_canary tests.test_acceptance_tests_flow tests.test_acceptance
   tests.test_fsm_advance_gate_framework tests.test_fsm_advance_gate_smoke`
   — все зелёные (392 теста). `scripts/guard.py` на PLAN.md — ок.
   `python3 scripts/codebase_map.py` — карта регенерирована тем же
   коммитом (новые тестовые файлы попали в `docs/codebase-map.md`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (единый тип исхода) | 1 |
| 2 (гейт — чистый предикат) | 2, 4 |
| 3 (общий каркас) | 1 |
| 4 (короткие тела ≤40 строк) | 3, 4 |
| 5 (юнит-тесты каркаса) | 1 |
| 6 (смоук трёх сценариев байт-в-байт) | 5 |
| 7 (поведение не меняется) | 2, 3, 4, 6 |

## Таблица «гейт → прежнее место → текст»

| Гейт | Прежнее место (до правки) | action (store.journal) | Печать |
|---|---|---|---|
| Ёмкость diff | `fsm_advance._capacity_gate_refuses`, строки ~470-504 | `"переход отклонён: гейт ёмкости diff"` | `[{id}] переход отклонён: {detail}` + `  дальше: ...` |
| Зоны | `fsm_advance._zones_gate_refuses`, строки ~634-677 | `"переход отклонён: гейт зон"` | то же |
| Рубеж «замечания не отработаны» (per регрессии №13/№15) | `fsm_advance._review_rework_gate_refuses`, строки ~852-880 | `"переход отклонён: замечания ревью не отработаны"` (`_REWORK_REFUSAL_ACTION`) | то же |
| Голова не в origin | `fsm_advance.review()`, строки ~174-182 (только `status == "approved" and not is_canary`) | `"переход отклонён: голова не в origin"` | то же |
| Реестр замечаний | `fsm_advance.review()`, строки ~194-210 (только `status == "approved"` и `guard.requires_registry(meta)`) | `"переход отклонён: реестр замечаний"` | то же |

Порядок применения не изменился: в `in_dev()` — ёмкость → зоны → рубеж
(после `fsm._pull_main_or_escalate`, как и раньше); в `review()` — голова
в origin (перед `store.update_task(reviewed_iter=...)`) → реестр
замечаний (после, внутри ветки `approved`), как и раньше — оба
по-прежнему условны на `status == "approved"` соответствующей веткой
вызова, не элементом списка (гейт-функция сама возвращает `None`, если
условие неприменимо — эквивалентно старому `if status == "approved":`).

## Влияние на систему

Зона задачи — только `orchestrator/fsm_advance.py` и `tests/`. Публичные
имена и сигнатуры точек входа `in_dev`/`review` и модульных функций,
подменяемых тестами (`_capacity_gate_refuses`, `_zones_gate_refuses`,
`_review_rework_gate_refuses`, `_reviewer_verdict_baseline`,
`_answer_zones_mandate`, `_plan_zones_extension_paths`, `_split_zone_paths`,
`_touches_zone`, `_answer_commit_is_role_step_autocommit`) — не изменены.
Тексты отказов/подсказок/действий журнала — байт-в-байт прежние (см.
таблицу и смоук-тест). `fsm.py` не тронут (R3). Никакой гейт/лимит/тест
не ослаблен — наоборот, добавлены новые юнит-тесты каркаса и смоук.
Откат — `git revert` коммита правки, поведение возвращается к прежнему
файлу целиком (никакая внешняя система не зависит от внутренней
структуры `fsm_advance.py`, только от `in_dev`/`review` как обработчиков
`cmd_advance`, чьё поведение не изменилось).

## Риски

- Декомпозиция `review()` на `_review_approved`/`_review_changes_requested`/
  `_review_escalate` — риск разойтись в порядке побочных эффектов
  (`store.update_task(reviewed_iter=...)` относительно двух новых
  гейтов). Смягчение — смоук/существующие тесты `test_review_registry_gate.py`,
  `test_github_adapter.py`, `test_fsm_draft_mr_reentry.py` гоняются
  явно после правки.
- `_freshness_refuses` и блок «acceptance_tests красные» намеренно не
  унифицированы (иной формат печати/данные нужны после прохода) — риск
  того, что ревью сочтёт это неполным покрытием требования 2/3; довод
  зафиксирован в «Подходе» и таблице выше для ревью.

## Предложения системе
(пусто)

## Разрешение эскалации (ANSWER-2)

Вопрос 1 (конфликт лока AC-9 и требования ANSWER-1 сохранить поведение
`01M1SG9T962WJJ31S282GWM0EN` байт-в-байт) решён Оператором вариантом по
умолчанию: фикстура AC-9 сдвинута штатным каналом `artel.py amend-tests`
— ожидаемые строки отказов гейтов ёмкости/зон теперь несут «база
сравнения deadbeef от origin/main» с тем же мокнутым `gitcmd.diff_base`/
`diff_base_source`, что и `tests/test_fsm_advance_gate_smoke.py`. Код не
менялся этим шагом: планка задачи на коде ветки —
`python3 -m unittest` по всем пяти файлам
`tasks/01M1TKNXX5YN5KT4WHG4T44JWV/acceptance_tests/` — 16/16 OK.
Дополнительно перепрогнан список планок ANSWER-1 (`tests.test_capacity_gate`,
`tests.test_zones_gate`, `tests.test_fsm_review_rework_gate`,
`tests.test_review_registry_gate`, `tests.test_advance_guard`,
`tests.test_fsm_advance_gate_framework`, `tests.test_fsm_advance_gate_smoke`,
`tests.test_advance_refusal_history`) — 65/65 OK. Поведение
`01M1SG9T962WJJ31S282GWM0EN` сохранено, принцип целостности не нарушен.
