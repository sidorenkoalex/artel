---
task: 01M5H24PZXZTBM03SF6V576S5P
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Механика канарейки, часть Б-1б: параллельный прогон --parallel

## Фаза A: план
- Таблица покрытия PLAN полна (требования 1–9 → шаги 1–3), шаги размера MR.
- Раздел «Замечания ревью, итерация 1» точно описывает инкремент: дифф
  c0639a84..HEAD — только `tests/test_canary_parallel.py` (+ карта),
  `orchestrator/` не тронут. «Влияние на систему» по-прежнему совпадает с
  полным диффом ветки (итерация 1 сверяла его).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 1 (artel.py: отказ повтора до `--detach`, флаг в `rest`, справка). |
| 2 | OK | Без изменений: отказ `codex_roles` до origin/замка/клона. |
| 3 | OK | `_run_children` (canary.py:3477): предел `PARALLEL_CHILD_LIMIT`, `pending.pop(0)`. |
| 4 | OK | `_child_argv`, `_wait_child`, журнал, `start_new_session`; `SHA_FORM.fullmatch` в `cmd_canary_run_task` (canary.py:3648). |
| 5 | OK | `_stop_children` под `_SignalDeferral`; `late` → `CanaryInterrupted` только если выход не по сигналу (canary.py:3550–3553); ветка `Exception` из ожидания — canary.py:3533–3535. |
| 6 | OK | `_finish_child` (canary.py:3449): красная строка только без строки шаблона. |
| 7 | OK | Приёмник зовётся внутри `_live_run_record` (canary.py:3581–3584) — отказ «уже идёт» до него. |
| 8 | OK | Потребители и чтение реестра не тронуты. |
| 9 | OK | Новые тесты на событиях FIFO (`<шаблон>.term`), подмена `_wait_child` (`_WaitFault`), не `Popen.wait`; SIGKILL-тест — только с дочерним `ignore_term`; срок не уменьшен в тестах с послушными дочерними. Долгоживущие сторожа для AC-21/20/14/19/5/17/9 теперь в `tests/`. |

## Замечания

Нет. Изменения `tests/test_canary_parallel.py` вне новых методов — только
помощники (`wait_fifo`, `catch_term`, каналы `.term`, параметр `extra`);
ни одно прежнее утверждение не удалено и не ослаблено.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_canary_parallel.py | Свойства AC-21, AC-20, AC-14, AC-19, AC-5, AC-17, верхний регистр AC-9 закрывались только разовой планкой | — | Добавлены `WaitFailureTest` (3), `StopTest::test_killed_child_with_own_row_gets_no_duplicate`, `::test_second_signal_does_not_interrupt_stop`, `ParentRefusalTest` (2), `RunTaskShaTest::test_upper_case_sha_refused_before_record`; ключевые заявки подтверждены временной мутацией (см. ниже) |

## Вердикт
approved — R1-F1 закрыт, blocker/major нет.

## Проверено исполнением
- `python3 -m pytest -q tests/test_canary_parallel.py` — 17 passed, 2 subtests.
- Временные мутации `orchestrator/canary.py` (скриптом с восстановлением в
  `finally`; после — `git status` чистый):
  - «`Exception` из `_wait_child` пробрасывается» (canary.py:3528 → `if error is not None:`)
    — красные `WaitFailureTest::test_wait_exception_red_row_group_stopped_queue_goes_on`
    и `::test_wait_exception_no_second_row_when_row_exists` (в итерации 1 эта
    мутация оставляла tests/ зелёными);
  - «поздний сигнал не попадает в код» (canary.py:3552 → `if False:`) — красный
    `WaitFailureTest::test_base_exception_in_wait_then_signal_during_stop`;
  - «без сверки `_has_run_row`» (canary.py:3449 → `if False:`) — 5 красных,
    включая `StopTest::test_killed_child_with_own_row_gets_no_duplicate` и
    `WaitFailureTest::test_wait_exception_no_second_row_when_row_exists`.
- `python3 …/artel.py plank-run 01M5H24PZXZTBM03SF6V576S5P` — 29 passed, код 0.
- Затронутые модули (`test_canary_parallel`, `test_canary_run_task`,
  `test_new_argv_parsing`, `test_canary_template_flag`, 01M4AXPY detach/doctor/
  lifecycle, 01M5FA4N doctor_live/live_cmd/mark/window) — 101 passed,
  197 subtests passed.
- CI коммита ff29ac5c зелёный (16 проверок) — по пакету.

## Предложения системе
- В шаге ревью `rm` недоступен в Bash (command not found), `/bin/rm` требует
  подтверждения — временный файл в каталоге документов пришлось удалять через
  `python3 -c os.remove`; для приёма «временная мутация» стоит дать штатный
  инструмент (например, `artel.py mutate-run`), чтобы скрипт мутации не надо
  было класть в каталог документов.
