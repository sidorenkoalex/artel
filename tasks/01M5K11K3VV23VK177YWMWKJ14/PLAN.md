---
task: 01M5K11K3VV23VK177YWMWKJ14
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: kill --reason — причина ликвидации задачи в записи перехода и в RETRO

## Подход
- `orchestrator/cleanup.py`: `cmd_kill(..., reason: str | None = None) -> bool`.
  Пустая/пробельная причина — `sys.exit("kill: --reason требует непустую
  причину")` первой строкой, до `store.db()`, `_refuse_live_cycle` и lease.
  `reason` прокидывается в `_cmd_kill`; деталь перехода собирает
  `_kill_detail(reason)`: `None` → `kill switch` побайтно, иначе
  `\r\n`→` `, затем `\r`/`\n`→` `, `strip()` → `kill switch: <текст>`.
  `_cmd_kill` возвращает `won`, `cmd_kill` — `bool(lease.run_locked(...))`
  (`run_locked` возвращает результат тела).
- `orchestrator/artel.py`: диспетчер `kill` → новый `_cmd_kill(rest)`.
  Значение берёт существующий `_reason_arg(rest[1:])`; значение на `--` —
  отказ «kill: --reason требует причину следующим аргументом, а не флаг»
  до вызова `cmd_kill`. `reason=` передаётся только при флаге (образец
  `_approve_during_canary_kwargs`), без флага вызов прежний
  `cmd_kill(<id>, confirmed=…)`. Подсказка «причина не записана — …
  artel.py kill <id как введён> --reason "<текст>"» печатается диспетчером
  только без флага и только при возврате `True`; `canary.py` зовёт
  `cmd_kill` напрямую и подсказки не видит. Строка справки —
  `kill <id> [--yes] [--reason "<текст>"]`.
- `retro.py`/`snapshot.py` не трогаются: «Итог:» берёт деталь перехода.

## Шаги
1. `cleanup.py`: параметр `reason`, отказ пустой причины, `_kill_detail`,
   возврат `won`/`bool`. `artel.py`: `_cmd_kill(rest)`, отказ флага-значения,
   условный kwarg, подсказка, справка. Регенерация `docs/codebase-map.md`.

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
| 8 | 1 |
| 9 | 1 |

Проверка: `tests/test_01m5k11k3vv23vk177ywmwkj14_kill_reason.py` (AC-1..AC-17)
зелёный; `plank-run` — 1 passed; затронутые модули зелёные:
`test_kill_cleanup`, `test_kill_live_cycle_refusal`, `test_retro`,
`test_canary`, `test_task_id_prefix_regression`, `test_division_parent_cleanup`
(185 passed) и ещё 20 файлов `tests/`, упоминающих kill (337 passed).
Своих тестов не добавлял: все свойства SPEC покрыты долгоживущим файлом задачи.

## Влияние на систему
- Без `--reason` поведение побайтно прежнее: деталь `kill switch`, вызов
  `cmd_kill(<id>, confirmed=…)` — `KillDispatchYesFlagTest` зелёный без правок.
  Новая только строка-подсказка в выводе командной строки.
- Отказ живому циклу, `--yes`, уборка, коммит закрытия, CAS-цикл — не
  менялись; изменён только `detail` вызова `set_state` и возврат.
- Причина пишется только в деталь записанного перехода — при отказах и
  терминальной задаче её нет ни в журнале, ни в RETRO.
- Гейты, лимиты, инварианты не затронуты. Откат — revert merge-коммита.

## Риски
- `"--yes" in rest[1:]` по-прежнему ищет флаг везде, включая позицию
  значения причины; единственный такой случай (`--reason --yes`) отказан
  раньше проверкой «значение на `--`».

## Предложения системе
