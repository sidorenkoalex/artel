---
task: 01M291EPQ2VFGCHZTXXC81616V
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Часть 2: очередь мержа FIFO вместо отказа, мёртвые записи очереди, doctor

## Фаза A: гейт плана

1. Покрытие требований — таблица PLAN.md «Покрытие требований» покрывает
   все 7 требований SPEC шагами 1-9; каждому AC (1-10) соответствует
   приёмочный тест (`tasks/.../acceptance_tests/test_ac*.py`), без
   `manual`/`skip` пометок — автогейт acceptance не выключен.
2. Шаги плана — проверяемые единицы (константа → схема → CRUD → модуль →
   точка встраивания → status → doctor → карта → тесты), ни один не
   «сделать всё».
3. Подход не конфликтует с конвенциями: очередь построена по образцу уже
   принятых `merge_lock.py` (CRUD-приём) и `zone_lock.py` (механика
   ожидания/добавка `status`), явно сослано в PLAN.md и докстрингах кода.
4. Деление на монолит (не резать по границе зон) обосновано и утверждено
   Оператором на гейте SPEC — обоснование («мёртвая схема без потребителя»
   / «блокирующий механизм без doctor-видимости») соответствует
   фактическому диффу: `merge_queue` таблица не остаётся без кода,
   `doctor`-видимость введена тем же MR, что и сама очередь.
5. Расширение зон (`orchestrator/merge_queue.py`,
   `orchestrator/doctor/__init__.py`, `orchestrator/doctor/cli.py`) несёт
   мандат Оператора (ANSWER-2.md, ANSWER-3.md) и совпадающий раздел
   «## Расширение зон» в PLAN.md — путь в мандате и путь в диффе совпадают
   буквально.
6. Разрешение конфликта подтяжки main (ANSWER-1.md) реализовано так, как
   предписано: мьютекс части 1 держится на весь цикл `approve` включая
   ожидание CI, `merge_queue.wait_for_window` встроена ПЕРЕД взятием
   мьютекса (`fsm_merge_gate.py:716-718`), `finally` снимает мьютекс
   безусловно (`fsm_merge_gate.py:732-733`); добавки `status` в
   `catalog.py` идут в порядке «существующие, затем новая»
   (`orchestrator/catalog.py:403-410`: `holder`→`zone`→`wave_breaker`→
   `division`→`merge_wait`); `docs/codebase-map.md` регенерирована на
   слитом дереве (проверено `codebase_map.py --check` — расхождений нет).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (вход в очередь, опрос, журнал, status) | OK | `merge_queue.wait_for_window`/`wait_suffix`; AC-1/AC-2 зелёные |
| 2 (таблица `merge_queue`, FIFO, только голова берёт окно) | OK | `schema.py`/`store.py`; AC-3/AC-4 зелёные |
| 3 (потолок очереди `MERGE_QUEUE_WAIT_CEILING_SEC`=7200, выход без merge) | OK | AC-6 зелёный |
| 4 (потолок CI не считает время очереди) | OK | `start` берётся после `wait_for_window`; AC-7 зелёный |
| 5 (пруна мёртвых записей, тот же признак, что `_holder_is_dead`) | OK | AC-8 зелёный |
| 6 (doctor: видимость очереди + отдельный fail на мёртвые) | OK | AC-9 зелёный, отдельные `Check` подтверждены тестом `test_dead_entry_does_not_mask_the_live_one_behind_it` |
| 7 (поведение части 1 не ослаблено) | OK | `tests/test_merge_lock.py`/`tests/test_merge_gate_ci_wait.py` — 0 изменений в диффе (`git diff` пуст), обе планки зелёные; AC-10 зелёный |

## Замечания

Blocker/major не найдено.

- minor — `orchestrator/doctor/leases.py:227-229` — после `return results`
  осталась лишняя пустая строка (двойной перевод строки в конце файла) —
  стилистическая мелочь, не влияет на поведение.

## Реестр замечаний

Замечаний уровня blocker/major нет — реестр пуст (все найденные пункты —
minor, вне обязательного реестра).

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tasks/01M291EPQ2VFGCHZTXXC81616V/acceptance_tests/ -q`
  — 10 passed (AC-1..AC-10, включая AC-10 прогон существующих планок
  `test_merge_lock.py`/`test_merge_gate_ci_wait.py` внутри самого теста).
- `python3 -m pytest tests/test_merge_queue.py tests/test_merge_lock.py tests/test_merge_gate_ci_wait.py tests/test_doctor.py -q`
  — 162 passed, 3 subtests passed.
- `python3 -m pytest tests/test_catalog_status_log.py -q` — 6 passed
  (регрессия `cmd_status` не задета добавкой `merge_wait`).
- `python3 scripts/codebase_map.py --check` — без вывода/без ошибки:
  карта соответствует дереву (built_at_sha не сравнивался — не признак
  дефекта per skill).
- `git diff cb3d7aa974892120041a5610b530a90bc82a0be7...HEAD -- tests/test_merge_lock.py tests/test_merge_gate_ci_wait.py`
  — пустой вывод: планки части 1 не тронуты ни строкой (требование 7 /
  AC-10 подтверждено по диффу, не только прогоном).
- `git log --oneline cb3d7aa9..HEAD` — цепочка коммитов соответствует
  описанию ANSWER-1 (реализация → слияние main → повторная подтяжка);
  `git show --stat d9615401` проверен на предмет протечки `.github/`
  в диф задачи — изменения `ci.yml` унаследованы от базового `cb3d7aa9`
  (сам являющегося одним из родителей мерж-коммита), в диффе ревью
  (база `cb3d7aa9...HEAD`) не появляются — протечки нет.
- CI коммита `d9615401` — зелёный (14 проверок), см. пакет.
- Прочитаны точечно (сверх пакета, по причине отсутствия SPEC/PLAN.md в
  самом диффе): `tasks/01M291EPQ2VFGCHZTXXC81616V/SPEC.md`, `PLAN.md`,
  все 6 файлов `acceptance_tests/*.py`, `_sandbox.py`,
  `orchestrator/merge_lock.py` (сверка сигнатуры `_holder_is_dead`),
  `orchestrator/zone_lock.py` (сверка образца), `orchestrator/store.py`,
  `tests/test_merge_lock.py` (прецедент докстрингов) — каждое чтение
  требовалось для конкретной проверки выше.

## Предложения системе

- `skills/test-authoring.md` («Ловит мутацию: …» в докстринге каждого
  теста) текстуально не ограничен `acceptance_tests/`, а
  `skills/review-checklist.md` (Фаза B, п.3) цитирует его как общее
  требование к «каждому новому или изменённому тесту» диффа. На практике
  разработческие юнит-тесты (`tests/*.py`) этому не следуют — новые
  `tests/test_merge_queue.py` (13 методов) и добавленный класс
  `MergeQueueCheckTest` в `tests/test_doctor.py` (5 методов) не несут ни
  докстринга-сценария, ни заявки «Ловит мутацию», но это ТОЧНО тот же
  паттерн, что уже несёт смерженный `tests/test_merge_lock.py` (часть 1,
  уже прошедшая ревью) — прецедент кодовой базы говорит, что конвенция
  фактически применяется только к `tasks/<id>/acceptance_tests/`, не к
  `tests/`. Стоит явно сузить формулировку в одном из двух скилов (либо
  распространить практику на `tests/`, либо явно исключить их из
  Фазы B п.3), чтобы ревьюверы не спорили с этим на каждой задаче заново.
