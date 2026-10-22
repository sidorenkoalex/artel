---
task: 01M5H24PZXZTBM03SF6V576S5P
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Механика канарейки, часть Б-1б: параллельный прогон --parallel

## Фаза A: план
- Таблица покрытия PLAN полна (требования 1–9 → шаги 1–3), шаги размера MR,
  подход (одна развилка `if parallel` в `cmd_canary` после `_set_plan`,
  прежняя ветка не тронута) с архитектурой согласован.
- «Влияние на систему» = дифф: `orchestrator/canary.py`, `orchestrator/artel.py`,
  новый `tests/test_canary_parallel.py` (+ карта). Защищённые пути, потребители
  реестра и код чтения реестра не тронуты. Откат — revert.
- Имена по ANSWER-1 соблюдены: `PARALLEL_CHILD_LIMIT = 2`,
  `PARALLEL_STOP_GRACE_SEC = 60`, `_wait_child`, `_child_argv`.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `artel.py:1568` отказ повтора до `--detach`; флаг остаётся в `rest` для `_detach_canary` (artel.py:1686); `parallel=True` передаётся только при флаге; справка в той же строке. |
| 2 | OK | `canary.py` `_cmd_canary_parallel`: отказ по `plan.codex_roles` первым, до `_resolve_target_sha`, замка профиля и клона; текст по SPEC. |
| 3 | OK | `_run_children`: не больше `PARALLEL_CHILD_LIMIT`, `pending.pop(0)` — порядок прогона; ненулевой код/исключение запуска очередь не обрывают. |
| 4 | OK | `_child_argv`: `-u`, пять флагов, полный sha из `_resolve_target_sha`; `start_new_session`, `cwd=config.ROOT`, без оболочки; журнал `<LOGS>/canary/<stamp>-<шаблон>.log` открывает родитель; запуск под `_SignalDeferral`. Сверка `SHA_FORM.fullmatch` — первой строкой `cmd_canary_run_task`, до `_set_plan` и записи. Пустой `--summary` парсер Б-1а принимает (artel.py:1634). |
| 5 | OK | `_stop_children`: SIGTERM всем → общий срок → SIGKILL → ожидание; под `_SignalDeferral` (он откладывает и SIGINT, canary.py:2317); поздний сигнал не поднимается заново (`deferral.pending = None`), при выходе не по сигналу превращается в `CanaryInterrupted(late)`. Запись/метка снимаются `_live_run_record` после `_run_children`. `Exception` из `_wait_child` — остановка группы этого дочернего, красная строка, очередь дальше; `BaseException` вне `Exception` — выход. |
| 6 | OK | `_finish_child`: заголовок + журнал целиком, красная строка только при отсутствии строки шаблона (`_has_run_row`), поля как у `_report_drive_failure` (canary.py:2754), `task_id`/`expected_escalation` = `None`; «завершён» после всех; код 0 только если все запущены и прошли. |
| 7 | OK | Строки и базовые пишет только дочерний; приёмник зовётся после `_live_run_record` — отказ «уже идёт» его не достигает (планка AC-17 зелёная). |
| 8 | OK | Потребители реестра и чтение реестра не тронуты (планка AC-18 зелёная). |
| 9 | частично | Тесты детерминированы, на событиях FIFO, песочница. Но долгоживущих тестов в `tests/` нет для ряда свойств требований 4–6 — см. R1-F1. |

## Замечания

- major — tests/test_canary_parallel.py (файл целиком; планка
  `acceptance_tests/test_*.py` вся помечена `Группа: разовый`) — свойства
  кода, которые обязаны держаться после мержа, закрыты только разовой
  планкой и в `tests/` сторожа не имеют (ADR-0018 п.3): после мержа планку не
  гоняет ни CI, ни автогейт. Нет теста в `tests/` на:
  1. `Exception` из `_wait_child` — красная строка «ожидание процесса задачи
     прервано», группа снята, очередь идёт дальше, второй строки нет при
     уже записанной (AC-21; canary.py `_run_children`, ветка `error is not None`);
  2. `BaseException` вне `Exception` из `_wait_child` + сигнал во время
     остановки → код 128 + номер этого сигнала (AC-20; блок
     `except BaseException` с `late`);
  3. повторный сигнал (SIGHUP после SIGTERM) не прерывает остановку, код —
     по первому сигналу (AC-14);
  4. дочерний со своей строкой, снятый SIGKILL, дубля не получает (AC-19);
  5. отказ повтора имени шаблона до `_resolve_target_sha`/реестра (AC-5) и
     отказ «прогон уже идёт» в параллельном режиме без отдачи `run_stamp`
     приёмнику и без дочерних (AC-17);
  6. (мелочь в том же классе) `RunTaskShaTest` не проверяет sha в верхнем
     регистре (AC-9 его называет).
  Сценарий: временная мутация «`Exception` из `_wait_child` обрывает
  очередь» (`if error is not None: raise error`) — `tests/test_canary_parallel.py`
  9/9 зелёные, краснеют только 2 теста планки AC-21. После мержа такая
  регрессия пройдёт CI молча. Предложение: добавить в `tests/` (через уже
  готовый `_ParallelSandbox` и подмену `canary._wait_child`) тесты пунктов
  1–5 с заявками «Ловит мутацию», плюс подтест верхнего регистра в
  `RunTaskShaTest`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | tests/test_canary_parallel.py (весь файл) | Свойства требований 4–6 (AC-21, AC-20, AC-14, AC-19, AC-5, AC-17, верхний регистр AC-9) закрыты только разовой планкой, долгоживущего теста в `tests/` нет | Регрессия ветки ожидания/остановки после мержа проходит CI незамеченной (подтверждено временной мутацией: tests/ зелёные) | Добавить тесты пунктов 1–5 и подтест верхнего регистра в `tests/test_canary_parallel.py` с заявками «Ловит мутацию» |

## Вердикт
changes_requested — закрыть R1-F1 (долгоживущие тесты в `tests/` для пунктов
1–6). Код по SPEC замечаний не имеет.

## Проверено исполнением
- `python3 …/artel.py plank-run 01M5H24PZXZTBM03SF6V576S5P` — 29 passed, код 0.
- `python3 -m pytest -q tests/test_canary_parallel.py tests/test_canary_run_task.py
  tests/test_new_argv_parsing.py tests/test_canary_template_flag.py
  tests/test_01m4axpy1py4ps1yafamd47vby_canary_{detach,doctor,lifecycle}.py
  tests/test_01m5fa4nr91pcf47szt6v0q9hs_{doctor_live,live_cmd,mark,window}.py`
  — 93 passed, 197 subtests passed.
- Временная мутация `PARALLEL_CHILD_LIMIT = 3` — `QueueTest::test_at_most_two_children…`
  красный (заявка подтверждена); код возвращён.
- Временная мутация «`Exception` из `_wait_child` пробрасывается» —
  `tests/test_canary_parallel.py` 9 passed (сторожа нет), планка
  `test_parallel.py` — 2 failed (AC-21); код возвращён, `git status` чистый.
- CI коммита c0639a84 зелёный (16 проверок) — по пакету.

## Предложения системе
- Планка этой задачи целиком помечена «Группа: разовый», хотя почти все
  её тесты проверяют свойства кода (очередь, остановка, красные строки) —
  класс «код-свойство как разовый» у test_author; стоит ловить на гейте
  планки, а не перекладывать на ревью MR (skills/test-authoring.md, ADR-0020).
