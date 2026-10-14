---
task: 01M4VC31NFCS6JZ0VE8HNJ7FYM
type: spec_audit
author_role: spec_auditor
status: ready
verdict: pass
signals: в) пути-признаки (тесты): tests/, tests/test_model_sets.py; в) пути-признаки (гейты): orchestrator/fsm_advance.py; в) пути-признаки (лимиты): orchestrator/budget.py; в) пути-признаки (песочница ролей): orchestrator/runner.py; г) budget_usd 45 ≥ 45; д) ТЗ ссылается на ADR: ADR-0019, ADR-0022
spec_sha: a75c8812afd8eb2f1f6575cc8f83e32d7a440943
schema_version: 5
---

# SPEC-AUDIT: Чистый прогон канарейки учитывает эскалацию аудитора SPEC по той же ловушке

## ТЗ и SPEC
Требования ТЗ 1–6 отражены в SPEC 1–6 в обе стороны:
- ТЗ 1 → SPEC 1 (SPEC.md:28-104): форма — перечень ролей по порядку
  (выбор, разрешённый ТЗ), колонка `escalation_roles`, `NULL` — данных нет;
  роль — по состоянию-источнику, не по тексту детали (SPEC.md:82-88);
  неустановленная роль — `unknown`.
- ТЗ 2 / 3 / 4 / 5 → SPEC 2 / 3 / 4 / 5 без потерь; подстрока причины
  `эскалаций роли <роль>: <число>` конкретизирует «причина называет роль и
  число».
- ТЗ 6 → SPEC 6 и AC-1…AC-11 (каждый пункт ТЗ 6 имеет критерий: AC-5, AC-6,
  AC-8, AC-9, AC-2/AC-3).
- Решение Оператора на гейте №1: Т-1 (промежуточные записи в AC-1…AC-3) —
  SPEC.md:146-187; Т-2 (нет ключа = `NULL`) — SPEC требование 4 и AC-9
  (SPEC.md:222-231); Ф-1 (адрес `:2232` в `_run_task_in_ephemeral_clone`) —
  «Материалы». Отражено.
- Решение №2: Е-1 (эскалация пульта из `spec_writing`/`spec_audit` —
  `unknown`) — SPEC.md:57-81, AC-11 (SPEC.md:240-264); В-1 (уровень подмены
  не навязывает устройство) — AC-1, SPEC.md:159-165. Отражено.
- Отклонения прошлого визита (Ф-1 «маркер строго следующей записью», В-2,
  Е-1) сняты: маркер ищется до следующего перехода `state -> …`, без
  требования соседства (SPEC.md:61-75), журналы всех AC несут фиксацию
  `sha зафиксирован` между переходом и маркером (SPEC.md:137-144), AC-1 и
  AC-11 прямо называют обе неверные реализации.
- Наблюдение без отклонения: SPEC распространяет признак «эскалация самой
  роли» на все состояния (эскалация пульта из `in_dev` — тоже `unknown`, не
  `developer`), тогда как решение №2 говорит о `spec_writing`/`spec_audit`.
  Исход чистоты от этого не меняется (и `developer`, и `unknown` пачкают
  прогон), отличается только имя в причине — и оно точнее: это не
  эскалация роли. Сверх ТЗ по существу не идёт.

## Факты против кода
Подтвердилось (рабочий каталог на 891b3a48):
- `models.expected_escalation_met` — orchestrator/models.py:1128;
  `unclean_reason` — :1136 (ветка «ожидаемая покрывает только одну» —
  :1149-1151, вердикт/ревью/автогейт — :1140-1143, :1152-1154);
  `pair_admission` — :1174, «не чистый — {reason}» — :1196-1197;
  `BLAME_*` — :996-998.
- `config.STATE_ROLE` — orchestrator/config.py:805 (без `spec_writing`).
- `canary._DRIVE_METRIC_FIELDS` — orchestrator/canary.py:291;
  `_escalation_notes` — :1848 (все `state -> escalated`); `_task_metrics` —
  :1867; `_run_task_in_ephemeral_clone` — def :2146, `steps = result["steps"]`
  — :2232; `_drive_in_clone` — :2255; `_read_drive_result` — :2311;
  `_record_canary_run` — :2361, вызов :2578; `_run_one_task` — :2504;
  `insert_canary_run` — :2416, :2645, :2762; бюджетная развилка — :1734-1747,
  возврат через синтетический ANSWER и `set_state(back, …)` — :1628-1654,
  :1475-1479 (то есть за бюджетной эскалацией всегда идёт переход
  `state -> X` — как в AC-11).
- `canary_drive.build_result` — orchestrator/canary_drive.py:67-87: `steps`
  — весь журнал задачи клона (`store.task_steps`), поля `STEP_FIELDS` — :41;
  записи `sha зафиксирован` и actor `lease` в нём есть.
- `store.set_state` — orchestrator/store.py:775; `_cas_state` пишет
  `state -> escalated` (:852), затем `record_fixation` (:827) пишет
  `sha зафиксирован` (:966) либо `fixation.journal_drift` (:829-830); маркер
  вызывающий пишет после возврата (orchestrator/fsm_advance.py:290-292 и
  др.) — ровно как описывает SPEC.md:61-75.
- `fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER` — orchestrator/fsm.py:71;
  `_mark_artifact_escalation` — orchestrator/fsm_advance.py:67, вызовы :180,
  :207, :292, :382, :556, :650 — все сразу после `set_state(…, "escalated")`.
  Прочие `set_state(…, "escalated")` без маркера: fsm_advance.py:347, :482;
  budget.py:300; fixation.py:248; runner.py:447, :800; pull.py:556, :574,
  :670, :786, :821; fsm_merge_gate.py:112, :270; fsm.py:1626;
  advance_gates/acceptance.py:183; advance_gates/test_integrity.py:1577;
  store.py:867 (инцидент ссылки) — по SPEC все `unknown`, что в
  `spec_writing`/`spec_audit` соответствует решению №2.
- Читатель маркера `auto._role_step_since_state_entry` —
  orchestrator/auto.py:348-394, «гасится» следующим переходом; докстринг
  про незаписанный первый вход `spec_writing` — auto.py:398-401.
- Задача заводится в `spec_writing` без `state -> spec_writing` —
  orchestrator/catalog.py:667, :670.
- tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py:168-170 —
  фильтр фиксации и `lease` перед проверкой маркера.
- DDL `canary_runs` — orchestrator/store.py:1442; `insert_canary_run` — :1516.
- Прецедент подмены процесса клона в тестах есть:
  tests/test_canary_drive.py, tests/test_01m4beg0003ch0qa1gy0pxat03_clone_marker.py.

Не подтвердилось: нет.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | маркер — строго соседняя запись (даёт `unknown, unknown`); роль по непосредственно предыдущей записи; перечень не пишется в строку / пишется не из `steps`; `escalations` ≠ длине |
| AC-2 | да | роль из текста детали («analyst: …» при `spec_audit`); роль по предыдущей записи; неверное сопоставление `STATE_ROLE` |
| AC-3 | да | источник без перехода → `unknown`; `verifying` → роль; без эскалаций — не пустой список |
| AC-4 | да | новое обязательное поле в `_DRIVE_METRIC_FIELDS`; роли из `metrics`, а не из `steps` |
| AC-5 | да | новое правило не допускает `analyst,spec_auditor`; одиночные роли отвергнуты |
| AC-6 | да | вторая эскалация роли допущена; developer/test_author/reviewer/unknown допущены; причина без роли/числа |
| AC-7 | да | новая ветка возвращает `None` до проверок вердикта/ревью/автогейта |
| AC-8 | да | новое правило применяется без `expected_escalation_met` |
| AC-9 | да | `NULL`/нет ключа читается как пустой перечень или `KeyError`; миграция пишет не `NULL` |
| AC-10 | да | сводка печатает старую причину; правка порогов допуска |
| AC-11 | да | эскалация пульта засчитана ролью состояния; маркер ищется без границы следующего перехода (даёт `analyst, spec_auditor` в (б)) |

Отклонений нет.

## Зоны
Зоны `orchestrator/models.py`, `orchestrator/canary.py`,
`orchestrator/store.py`, `tests/` покрывают всё: вычисление перечня
(canary.py), колонка, миграция и параметр (store.py, DDL лениво в
store.py:1442 — `schema.py` не нужен), критерий (models.py). Чтение
`fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER` и `config.STATE_ROLE` — импорт без
правки (SPEC «Не входит», SPEC.md:280-311). Защищённые пути не задеты,
песочница ролей (`runner.py`) не трогается. На ревью: новая колонка — и в
`CREATE TABLE`, и через `add_column` (паритет схемы —
tests/test_store_schema_migration_parity.py).

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `unclean_reason` для строк с ролями на шаблоне с ловушкой | «ожидаемая покрывает ровно одну» — orchestrator/models.py:1149-1151 | Расширяется ровно на одну эскалацию spec_auditor (матрица ТЗ); прочие роли, `unknown` и повторы ловятся | AC-5, AC-6, AC-11 | принять — заказано ТЗ |
| Эскалация пульта из `spec_writing`/`spec_audit` | на main ловушка + бюджет = 2 → не чистый (models.py:1149-1151) | да: `unknown` → не чистый | AC-11 | принять (решение №2) |
| Шаблон без ловушки | любая эскалация → не чистый — models.py:1144-1145 | да | AC-8 | принять |
| Старые строки `canary_runs` | правило по `escalations` — models.py:1149-1151; tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py | да (`NULL`/нет ключа → старое правило) | AC-9; долгоживущий тест без правки | принять |
| Прочие условия чистоты и числа допуска | models.py:1140-1143, :1152-1154; `ADMIT_MIN_*` | да | AC-7, AC-10 | принять |
| Набор полей результата клона | `_DRIVE_METRIC_FIELDS` — canary.py:291 | да, не меняется | AC-4 | принять |

Раздела «Меняемое поведение» в SPEC нет; смен ожиданий существующих тестов
SPEC не объявляет и не требует (`canary_row` в tests/test_model_sets.py и
долгоживущий тест 01M3YCHV… остаются на старой ветке, SPEC.md:302-311).

## Пути обхода гейтов
- «Маркер строго соседней записью» — ловит AC-1 (фиксация между переходом и
  маркером, ожидание `["analyst","spec_auditor"]`).
- «Маркер где угодно после `escalated`» — ловит AC-11 (б).
- Роль по тексту детали — ловит AC-2 (деталь «analyst: …» при `spec_audit`).
- Роль по предыдущей записи — ловят AC-1…AC-3 (записи шага роли между).
- Перечень из `metrics` вместо `steps` либо обязательное новое поле —
  ловит AC-4.
- Старые строки, перекрашенные пустым перечнем — ловит AC-9.
Других путей не нашёл.

## Вердикт
**pass** — отклонений нет. Решения Оператора на гейте №1 и №2 и отклонения
прошлого визита (Ф-1, В-2, Е-1) отражены; адреса кода подтверждены
(раздел «Факты против кода»); каждый AC ловит правдоподобную мутацию.
Наблюдение без отклонения (раздел «ТЗ и SPEC»): эскалация пульта вне
`spec_writing`/`spec_audit` тоже получает роль `unknown` (SPEC.md:57-81) —
исход чистоты тот же, отличается только имя роли в причине.
