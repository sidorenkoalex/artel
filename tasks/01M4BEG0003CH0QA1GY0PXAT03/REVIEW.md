---
task: 01M4BEG0003CH0QA1GY0PXAT03
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Канарейка не гоняет полный набор tests/ на приёмке своей задачи

## Гейт плана

Таблица покрытия полна: требования 1–5 покрыты шагами 1–3. Шаги проверяемы
и соразмерны MR. Подход изолирует маркер входом `canary_drive`: обычный
процесс не наследует обход даже при внешнем `ARTEL_CANARY_SKIP_FULL_SUITE=1`.
Изменения соответствуют заявленному влиянию на систему; откат возможен
revert коммита задачи.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Эфемерный клон включает признак и восстанавливает его в `finally`; дочернему процессу передаётся отдельный env-маркер. |
| 2 | OK | При включённом признаке `full_suite` обходится, причина записывается в журнал, последующие проверки продолжаются. |
| 3 | OK | `config` читает env-маркер только при входе `python -m orchestrator.canary_drive`; обычный процесс сохраняет полный прогон и `approve`. |
| 4 | OK | Пропуск не становится `autogate_refusal`; прежняя обработка иных отказов и вердикт канарейки сохранены. |
| 5 | OK | Долгоживущие тесты имеют содержательные заявки «Ловит мутацию», не запускают реальные роли или канарейку и проверяют изоляцию, проводку env, восстановление и вердикт. |

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/config.py:411; orchestrator/fsm_autogate.py:299 | Обычный процесс принимал канареечный обход из общего окружения. | Внешняя переменная окружения могла отключить полный набор `tests/` у обычной задачи. | `config.py` учитывает маркер только во входе `canary_drive`; новый тест подтверждает выключенный признак у обычного процесса с тем же env. |
| R1-F2 | accepted | tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py:51-83,190-205 | Тест не наблюдал `env` дочернего процесса. | Поломка передачи признака в клон осталась бы незамеченной, и клон снова запустил бы полный набор. | `tests/test_01m4beg0003ch0qa1gy0pxat03_clone_marker.py` проверяет `Popen(env=…)` и импорт маркера настоящим входом `canary_drive`; залоченный файл не менялся. |

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tests/test_01m4beg0003ch0qa1gy0pxat03_clone_marker.py tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py tests/test_fsm_autogate.py tests/test_canary_drive.py tests/test_canary.py -p no:cacheprovider -p timeout -o timeout=120` — 141 passed.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4BEG0003CH0QA1GY0PXAT03` — 1 passed.
- `git diff --check 26c709222110572893ecb0372bb2520f1005431f...HEAD` — ошибок пробелов нет.
