---
task: 01M2ARQD7C472KZACB3SZXGF1N
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 5    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: Канарейка: повтор developer на красной планке (вариант а)

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/config.py`: `CANARY_MAX_DEV_RETRIES = 2`, докстринг-комментарий по образцу `CANARY_MAX_ESCALATION_CYCLES`/`CANARY_MAX_STALL_ITERS` (соседняя строка в файле). |
| 2 | OK | `canary._drive_task` (orchestrator/canary.py:867-889): ветка `state == "in_dev" and _acceptance_refusal_blocks_in_dev(...)` стоит ДО generic-ветки `runner.step_role`, зовёт `runner.cmd_run(task_id)` и продолжает `continue`. Детектор `_acceptance_refusal_blocks_in_dev` (canary.py:733-751) распознаёт оба пути: прямую запись `fsm`/`_ACCEPTANCE_TESTS_REFUSAL_ACTION` и обёртку `_AUTO_STOPPED_ACTION` ("auto остановлен") — сверил буквальный литерал `_ACCEPTANCE_TESTS_REFUSAL_ACTION = "переход отклонён: приёмочные тесты"` с `orchestrator/fsm_advance.py:1302` (`row["action"]`, не `detail` — совпадает байт-в-байт) и формат обёртки `f"{state}: {reason}"` в `orchestrator/auto.py:468-469` (`auto_stop`) — подстрочный поиск `in (last["detail"] or "")` корректно ловит этот формат. |
| 3 | OK | Счётчик `dev_retries` — локальная переменная цикла, обнуляется на первой же итерации, где состояние после `auto.cmd_auto` не `in_dev` (canary.py:832-836); повтор считается прогрессом — `stall_streak = 0`, `prev_signature` не трогается (канарейка.py:884-888), потраченное растёт через реальный `runner.cmd_run`. Превышение `CANARY_MAX_DEV_RETRIES` — `_kill_inconclusive` с точным текстом требования. |
| 4 | OK | Сравнение `==` с точным литералом (не `startswith`/префиксный поиск) — отказ другого класса («переход отклонён: гейт зон» и т.п.) не совпадает и идёт прежним путём стагнации; подтверждено тестом `DriveTaskOtherClassRefusalDoesNotRetryDeveloperTest`/приёмочным `test_canary_other_class_refusal.py`, оба зелёные. |
| 5 | OK | `_dev_retry_count` (canary.py:956-961) считает записи `actor=CANARY_MARK_ACTOR, action=_DEV_RETRY_ACTION`, подключена в `_task_metrics` (`dev_retries`), строка отчёта `_run_one_task` несёт `повторов developer={metrics['dev_retries']}` перед `исход=…` (canary.py:1213). |

## Замечания

Замечаний нет.

## Реестр замечаний

(пусто — замечаний в этой итерации не заведено)

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tasks/01M2ARQD7C472KZACB3SZXGF1N/acceptance_tests/ -q` —
  9 passed (оба приёмочных файла задачи: `test_canary_dev_retry.py`,
  `test_canary_other_class_refusal.py`).
- `python3 -m pytest tests/test_canary.py -q` — 78 passed, 4 subtests
  passed (полный модуль затронутого файла тестов, включая новые классы
  `DriveTaskDevRetryOnAcceptanceRefusalTest`,
  `DriveTaskDevRetryCapExceededTest`,
  `DriveTaskOtherClassRefusalDoesNotRetryDeveloperTest`,
  `DevRetriesConfigConstantTest`, `MetricsFromJournalTest::
  test_task_metrics_includes_dev_retries_count`).
- Сверка литерала `_ACCEPTANCE_TESTS_REFUSAL_ACTION` против
  `orchestrator/fsm_advance.py:1302` (`grep -n "переход отклонён:
  приёмочные тесты"`) — совпадает байт-в-байт с журналируемым `action`
  (не с текстом print).
- Сверка формата обёртки стоп-крана T038: прочитан
  `orchestrator/auto.py:457-476` (`auto_stop`) — `detail` журнала
  `"auto остановлен"` несёт ровно `f"{state}: {reason}"`, где `reason`
  для этого класса — тот же литерал (`_advance_refusal`,
  `orchestrator/auto.py:164-176`, возвращает `row["action"]` без
  изменений). Подстрочный детектор в `canary.py` корректен для этого
  формата.
- `git diff --stat` инкрементального диапазона (после исключения
  `docs/codebase-map.md`) — тронуты ровно `orchestrator/canary.py`,
  `orchestrator/config.py`, `tests/test_canary.py`: зона правки
  совпадает с зоной SPEC (`orchestrator/canary.py, orchestrator/
  config.py, tests/`), scope creep не найден.
- `docs/codebase-map.md`: локальный прогон `python3
  scripts/codebase_map.py` дал diff только по строке `built_at_sha`
  (сверено `git diff`) — карта по содержимому актуальна, изменение
  отброшено (`git checkout -- docs/codebase-map.md`) как не относящееся
  к ревью.
- Прочитан diff и оба приёмочных теста задачи целиком (все case'ы AC-1..
  AC-9); каждый новый/изменённый тест несёт докстринг «Ловит мутацию: …»,
  описывающий конкретный сценарий поломки, не пересказ имени метода.

## Предложения системе

(пусто)
