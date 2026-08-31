---
task: T088
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: Авто-ack алертов: непокрытые источники doctor

## Подход
Расширить существующий приём `_auto_ack_gone` (T035/T054) на пять
источников `doctor`, ранее его не звавших: `doctor.live_smoke`,
`doctor.recovery.sha`, `doctor.recovery.dirty`, `doctor.recovery.fsck`,
`doctor.task_counter`.

Для сирот/leases/merge_lock (T035/T054) сущность, чью «живость» нужно
проверить, восстанавливается РАЗБОРОМ `message` (путь/ветка/pid) — там
проверяющая функция на момент вызова `_auto_ack_gone` уже не помнит,
что именно она проверяла для конкретного открытого алерта прошлого
прогона. Для пяти источников этой задачи ничего восстанавливать не
нужно: `live_smoke`/`recovery_check`/`check_task_counters` в момент
своего текущего прогона уже вычисляют ровно то булево условие, которое
представляет алерт («sha разошлись», «репо грязное», «fsck упал»,
«счётчик отстаёт», «живой смоук провалился») — `is_live` замыкает это
уже посчитанное значение, не парсит `message`.

`doctor.recovery.*` и `doctor.task_counter` — источники, у которых
одновременно может быть открыт алерт одного и того же `source` для
РАЗНЫХ target (SPEC требование 6/AC-6), в отличие от прежних шести
источников (там сущность в `message` и так уникальна, доп. фильтр не
нужен). `_auto_ack_gone` получает необязательный параметр `target`:
если задан — дополнительно фильтрует открытые алерты по колонке
`target`, не только по `source`. По умолчанию `None` — старое поведение
(не фильтровать), все шесть существующих вызовов (`check_orphans`,
`check_leases`, `check_merge_lock`, `check_backup_age`) остаются
нетронутыми и проходят как раньше.

`doctor.live_smoke` — не per-target источник (`raise_alert` зовётся с
`target=None`, как и раньше), поэтому вызывается без `target`.

Архитектурно незначимо — расширение существующего частного хелпера тем
же приёмом, что уже принят в модуле; ADR не нужен.

## Шаги

1. `orchestrator/doctor.py`:
   - `_auto_ack_gone(conn, source, is_live, target=None)` — добавить
     фильтр по `target`, если он задан.
   - `live_smoke`: после `_live_smoke_run` звать
     `_auto_ack_gone(conn, "doctor.live_smoke", lambda _msg: check.status != "ok")`
     безусловно (тем же приёмом, что `check_leases`/`check_merge_lock` —
     зовётся на каждом прогоне, не только при провале).
   - `recovery_check`: заменить `if clean is False`/`if fsck.returncode
     != 0`/`if latest is not None and current and current != ...` на
     булевы переменные (`sha_mismatch`, `dirty`, `fsck_failed`),
     сохранив ветвление `Check`/`raise_alert` как есть; после каждой
     из трёх под-проверок звать `_auto_ack_gone(conn, "doctor.recovery.
     {sha,dirty,fsck}", lambda _msg: <булева>, target=target)`.
   - `check_task_counters`: внутри цикла по `sorted(checked_targets)`
     завести `is_behind = next_number < observed` и звать
     `_auto_ack_gone(conn, "doctor.task_counter", lambda _msg,
     is_behind=is_behind: is_behind, target=target)` на каждой
     итерации (значение по умолчанию аргумента лямбды — фиксация
     текущего `is_behind` цикла, не поздний биндинг).
   - Регенерировать `docs/codebase-map.md`
     (`python3 scripts/codebase_map.py`) — конвенция обязывает при
     любой правке `.py` в `orchestrator/`, даже если публичный
     интерфейс модуля не изменился.

2. `tests/test_doctor.py`: юнит-тесты, дополняющие уже залоченные
   `tasks/T088/acceptance_tests/test_auto_ack_uncovered_doctor_sources.py`
   (AC-1..AC-7 покрыты приёмочными) — здесь только то, чего там нет:
   - `_auto_ack_gone(target=...)` изолированно (без прогона всего
     `recovery_check`) — регресс на то, что фильтр по `target` действительно
     ограничивает выборку, а `target=None` не фильтрует вовсе (совместимость
     с шестью существующими вызовами).
   - `check_task_counters`: закрытие алерта ОДНОГО target при том, что
     алерт другого target из того же прогона остаётся открытым — тот же
     сценарий, что уже покрывает `test_ac6_task_counter_other_target_
     unaffected`, но точечно на уровне `_auto_ack_gone`, а не сквозного
     прогона с реальным git (для документации приёма внутри самого
     `test_doctor.py`, где уже живут остальные `check_task_counters`-тесты).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | 1 |
| 7 | 1 |
| 8 | 1 (переиспользует `alerts.auto_ack` без изменений) |
| 9 | 1 (условия `raise_alert` не меняются — только оформлены в булевы переменные) |
| 10 | 1, 2 (изменения ограничены `orchestrator/doctor.py`, `tests/test_doctor.py`, картой кодовой базы) |

## Влияние на систему
- `_auto_ack_gone` — приватная функция `doctor.py`, единственный
  модуль, который её зовёт; новый параметр — с дефолтом, все шесть
  существующих вызовов (`check_orphans` ×3, `check_leases`,
  `check_merge_lock`, `check_backup_age`) не меняют поведение
  (проверено юнит-тестами шага 2 и полным прогоном `tests/test_doctor.py`).
- `alerts.py`/`alerts.auto_ack`/`alerts.raise_alert`/`alerts.ack` —
  не трогаются (требования 8, 9; принцип целостности, эти функции — вне
  зоны задачи по SPEC «Не входит»).
- Условия, при которых `live_smoke`/`recovery_check`/
  `check_task_counters` заводят `raise_alert`, не меняются — только
  оформлены как именованные булевы переменные для повторного
  использования в `is_live`, сама логика (`!=`, `is False`,
  `returncode != 0`, `<`) побитово та же, что уже была.
- Ручной `alert-ack`/`cmd_alert_ack`/дедупликация `raise_alert` для
  этих пяти источников не задеты — не изменяем ни `alerts.ack`, ни
  условия вызова `raise_alert`, ни `store.open_alert_exists`.
- Откат: `git revert` коммита задачи — правка локальна для `doctor.py`
  и его тестов, миграций схемы БД нет.

## Риски
Нет рисков за пределами обычных для точечного расширения уже принятого
приёма (T035/T054) на новые источники того же класса.

## Предложения системе
(пусто)
