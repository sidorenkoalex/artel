---
task: 01M4JC5B3TYFCVY51RKZ1AM1VF
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Очередь зоны решает старт

## Фаза A — план
- Таблица покрытия полна, требования 1–8 сопоставлены шагам. Добавлен
  шаг 4 под R1-F1/R1-F2, на него ссылаются строки требований 4 и 7.
- Шаг 4 размером с MR: одна строка кода в `_holds_queue` и два теста
  в `tests/test_zone_lock.py`.
- Подход не меняется. `_holds_queue` использует готовое правило
  `lease.foreign_live_lease` (lease.py:258–282), нового понятия
  живости не вводит. Импорт `lease` по-прежнему отложенный (цикл
  `lease -> runner -> zone_lock`).
- «Влияние на систему» сходится с инкрементальным diff: меняются
  только `orchestrator/zone_lock.py` (+8/−2, `_holds_queue`) и
  `tests/test_zone_lock.py` (два новых метода, остальное не тронуто).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 1. |
| 2 | OK | Без изменений с итерации 1. |
| 3 | OK | Без изменений с итерации 1. |
| 4 | OK | Живость цикла теперь проверяет `lease.foreign_live_lease(conn, id, None)`: heartbeat свежий И pid адресуем на своём host (zone_lock.py:524). Задача с мёртвым процессом цикла очередь не держит (R1-F1 закрыто). |
| 5 | OK | `queue_wait` берёт ту же `_holds_queue`, поэтому при мёртвом pid показ ставит пометку «не держит очередь». Сторож проверяет `holds=False`. |
| 6 | OK | Без изменений с итерации 1. |
| 7 | OK | Отказы очереди и зависимости доходят до `blocking_conflict`. В `tests/` появился сторож (R1-F2 закрыто). |
| 8 | OK | Существующие методы `tests/` не изменены, в diff только добавления. |

## Замечания

Новых замечаний нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/zone_lock.py:524 | `_holds_queue` проверял живость цикла через `lease.is_live` (только heartbeat) | Задача с мёртвым процессом держала бы очередь до 2 ч | Принято: правило `foreign_live_lease` (heartbeat + pid на своём host). Тест `test_lease_with_dead_pid_does_not_hold_queue` проверен временной мутацией: красный при правиле «только heartbeat», зелёный без мутации |
| R1-F2 | accepted | tests/test_zone_lock.py | Отказы очереди и зависимости через `blocking_conflict` проверяла только разовая планка | Регресс к одной занятости не ловился в CI | Принято: тест `test_blocking_conflict_names_queue_head_and_waiting_dependency` проверяет тройку для задачи впереди и для ждущей зависимости. Временная мутация «только `_OCCUPIED`» → красный, без мутации зелёный |

## Вердикт
approved — R1-F1 и R1-F2 исправлены по сути. Заявки обоих новых тестов
называют наблюдаемое расхождение, и тесты его действительно ловят:
проверено исполнением. Других дефектов в инкрементальном diff нет.

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py tests/test_zone_lock.py tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py tests/test_auto_cycle.py`
  — 113 passed, 49 subtests passed.
- Временные мутации через `mock` в `python3 -c` (код на диске не менялся),
  каждый тест прогнан чистым и мутированным:
  - `lease.foreign_live_lease` заменён правилом «только heartbeat»
    (`lease_row`, если `lease.is_live`): чистый
    `test_lease_with_dead_pid_does_not_hold_queue` — ok, мутированный — 1 failure;
  - `zone_lock.blocking_conflict` возвращает только конфликт `_OCCUPIED`:
    чистый `test_blocking_conflict_names_queue_head_and_waiting_dependency` — ok,
    мутированный — 1 failure.
- `artel.py plank-run 01M4JC5B3TYFCVY51RKZ1AM1VF` — 1 passed, код 0.
- `python3 scripts/codebase_map.py` — в diff карты меняется только
  `built_at_sha`, карта свежая. Изменение откатил `git checkout`,
  `git status` чистый.
- CI коммита 1cf6fcf1 зелёный (16 проверок, по данным пакета).

## Предложения системе
- Песочница роли отклоняет `cp`/`sed -i` и heredoc в Bash. Поэтому
  проверку «временной мутацией» на диске (как её описывает
  review-checklist) ревьювер делает только через `mock` в `python3 -c`.
  Стоит описать этот приём в `skills/review-checklist.md` как штатный.
