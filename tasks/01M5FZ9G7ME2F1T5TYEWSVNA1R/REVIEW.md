---
task: 01M5FZ9G7ME2F1T5TYEWSVNA1R
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Механика канарейки, часть Б-1а: подкоманда canary run-task и запись дочернего в реестр

## Фаза A: план
- Таблица покрытия полна (требования 1–8 → шаги 1–4); новый шаг 4 закрывает
  R1-F1/R1-F2 и называет проверенные мутации.
- «Влияние на систему» совпадает с diff итерации: с вердикта b139ab8e
  изменены только `tests/test_canary_run_task.py` и карта; код
  `orchestrator/` не менялся (`git diff b139ab8e --stat`).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 1; теперь сторожится `RunTaskParseRefusalTest` (все отказы разбора с пустым реестром, `--summary ""`, роль, справка) и `test_codex_set_refused_before_record`. |
| 2 | OK | Порядок (0)→(г) сторожится тестами (б), (в), пустой сводки, аргументов `_run_one_task`, сигналов до/во время задачи, отказа `_set_plan`. |
| 3 | OK | Поля записи, снятие записи и `.tmp` по всем исходам, сбой `os.replace` — `RunTaskBodyTest`. |
| 4 | OK | Прежний код реестра Б-2; планка AC-4 зелёная. |
| 5 | OK | Прежний `_run_one_task`; планка AC-5 зелёная. |
| 6 | OK | Потребители не менялись; планка AC-6 зелёная. |
| 7 | OK | Тела прежних функций не тронуты; планка AC-7 зелёная. |
| 8 | OK | Входы фиксированы (`random` убран); без часов и сети; `send_signal` проверяет `signal.getsignal` перед `os.kill`; реестр и БД — в `InitializedTmpRootTest`; обработчики сигналов восстанавливаются в `addCleanup`. |

## Замечания

Новых замечаний нет. Заявки «Ловит мутацию» новых тестов проверены
временными мутациями (см. «Проверено исполнением») — каждая ловится.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_canary_run_task.py:60-399; orchestrator/canary.py::cmd_canary_run_task | Тело подкоманды не сторожилось тестами `tests/` | После мержа регрессия прошла бы зелёный CI | Закрыто: 13 тестов тела в `tests/`; девять временных мутаций тела (снятие записи, снятие `.tmp`, сверка метки, сводка красной строки, ловля `CanaryInterrupted`, проверка Codex, `main_sha` строки сигнала, `_interrupt_on_signal`, запись реестра) — каждая даёт красные тесты |
| R1-F2 | accepted | tests/test_canary_run_task.py:28-32 | Случайное зерно на каждый прогон | Невоспроизводимые входы | Закрыто: константы модуля `STAMP`, `SHA`, `SET_NAME`, `SUMMARY`, `TEMPLATE_NAME`; `import random` удалён |

## Вердикт
approved: R1-F1 и R1-F2 закрыты, новых blocker/major нет.

## Проверено исполнением
- `python3 -m pytest -q tests/test_canary_run_task.py` — 14 passed, 138
  subtests passed.
- Временные мутации `orchestrator/canary.py::cmd_canary_run_task`, после
  каждой прогон `tests/test_canary_run_task.py`, файл затем восстановлен
  (`git status --short` пуст):
  - `record.unlink` в `finally` убран → 8 failed;
  - уборка `.tmp` в `finally` убрана → 2 failed;
  - сверка метки (`_mark_owned_by_parent`) отключена → 2 failed;
  - красная строка (в) пишет `plan.summary` вместо переданной → 2 failed;
  - `except CanaryInterrupted` в (г) заменён на `except KeyError` → 2 failed;
  - проверка `plan.codex_roles` отключена → 1 failed;
  - `main_sha=None` в строке «оборвана сигналом» → 2 failed;
  - `_interrupt_on_signal` заменён на `nullcontext` → 3 failed;
  - запись дочернего не пишется → 3 failed.
- `python3 …/artel.py plank-run 01M5FZ9G7ME2F1T5TYEWSVNA1R` — 32 passed,
  код выхода pytest 0.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`
  без `built_at_sha` — расхождений нет; файл возвращён.

## Предложения системе
- В окружении шага ревьювера нет `rm`/`cat`, а Bash отклоняет функции shell
  и `"${…}"`-конструкции: временные мутации пришлось гонять отдельным
  python-скриптом в каталоге документов — стоит дать штатную команду пульта
  «временная мутация + прогон файлов tests/ + возврат».
