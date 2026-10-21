---
task: 01M5FGHNB29QA254FM07QR55AB
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Очередь зон: запись «ждёт зоны» закрывается при любом выходе из ожидания; подсказка merge_after на гейте SPEC согласована с отказом `answer`

## Подход
Три точечные правки в зонах SPEC, монолит (решение Оператора 21.10).

- `orchestrator/zone_lock.py`: маркер `_WAIT_INTERRUPTED_PREFIX = "ожидание зоны прервано:"`,
  функция `wait_interrupted_action(reason, minutes, holder)` →
  «ожидание зоны прервано: <причина>; <N> мин, держал <id>»; константы
  `AUTO_START_ACTION`/`AUTO_STOPPED_ACTION`/`CYCLE_ABORTED_ACTION`.
  `wait_minutes` пропускает `RELEASE_ACTION` (точное совпадение) и
  считает закрытием «зона свободна через»/прерванный выход (по началу) и три
  записи цикла (точно). Подпись прежняя.
- `orchestrator/auto.py`: в `_wait_for_zone` локальный помощник
  `interrupted(stop)` журналирует (актор `operator`, без печати) запись
  выхода с `stop.reason`, `int(elapsed_sec // 60)` и текущим `occupier_id`
  (обновляется на каждом опросе) и возвращает тот же `Stop` — им обёрнуты
  все четыре точки: stop до сна, stop во время сна, потолок, потеря lease.
  Сами `Stop`, печать, ветка освобождения зоны — без изменений. Три литерала
  записей цикла заменены на `zone_lock.<константа>` (чтение атрибута в
  момент вызова — подмена константы в модуле меняет запись, AC-5).
- `orchestrator/merge_after.py`: хвост отказа о потере заявленной
  зависимости заменён: `artel.py reject <id> "аналитик, эскалируй вопрос о
  зависимости <id…>"` → после эскалации аналитика ответ в escalated —
  `artel.py answer <id> <файл>` со строкой «Зависимости мержа: …» → `artel.py
  approve <id>`. Начало отказа и прочие отказы не тронуты.

Оценка бюджета SPEC ($25) не меняется.

## Шаги
1. Правки трёх модулей выше + регенерация `docs/codebase-map.md`
   (`python3 scripts/codebase_map.py`). Тесты: долгоживущие файлы задачи
   (`tests/test_01m5fghnb29qa254fm07qr55ab_{zone_wait_exit,wait_minutes,spec_gate_hint}.py`,
   написаны test_author, покрывают AC-1..AC-9) — свои тесты сверх них не
   нужны: незакрытых свойств не осталось.

Прогон (передний план): долгоживущие файлы задачи + `tests/test_auto_cycle.py`,
`tests/test_catalog_status_log.py`, `tests/test_zone_lock.py`,
`tests/test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py` — 131 passed;
`tests/test_merge_after_declared.py`, `tests/test_merge_queue.py`,
`tests/test_suite_run.py` — 41 passed. Полный набор — `suite-run` пульта.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (`auto._wait_for_zone`, `zone_lock.wait_interrupted_action`) |
| 2 | 1 (`zone_lock.wait_minutes`, три константы, замена литералов в `auto.py`) |
| 3 | 1 (механика зон не тронута: правки только маркеров ожидания и констант) |
| 4 | 1 (`merge_after.spec_gate_declared_refusal`, текст отказа о потере) |
| 5 | 1 (долгоживущие тесты задачи; существующие тесты и `tests/sandbox.py` не правятся) |

## Влияние на систему
- Захват/освобождение зоны, `blocking_conflict`, `refusal`, `queue_*`,
  `cmd_zone_release`, тексты `REFUSAL_ACTION`/`RELEASE_ACTION`/`CLAIM_ACTION`
  не тронуты: старт кода в занятой зоне по-прежнему запрещён (AC-7).
- Новая запись журнала — только запись; печать цикла побайтно прежняя. Её
  текст не начинается с «ждёт зоны», поэтому прочие читатели журнала,
  ищущие вход по префиксу (`watch.py`, `doctor/hung_test_watchdog.py`),
  её за вход не примут.
- `wait_minutes` стал строже (больше закрытий) — `status` перестаёт
  показывать «ждёт N мин» от оконченного ожидания; держатель/очередь
  выводятся прежним кодом `catalog`.
- Тексты записей «auto старт/остановлен», «цикл оборван» в журнале прежние
  (константы равны литералам) — копии литералов в `watch.py`/`canary.py`
  продолжают совпадать.
- Гейты, лимиты, тесты не ослабляются. Откат — revert коммита задачи.
- merge_after не меняется.

## Риски
- Процесс `auto`, убитый без записи выхода и без последующего `auto` той же
  задачи, оставит ожидание открытым — вне зоны (SPEC «Не входит», liveness).

## Предложения системе
- Литералы «auto старт»/«auto остановлен»/«цикл оборван» остаются копиями в
  `orchestrator/watch.py` и `orchestrator/canary.py` — их стоит перевести на
  `zone_lock.*` отдельной задачей (SPEC её исключил).
