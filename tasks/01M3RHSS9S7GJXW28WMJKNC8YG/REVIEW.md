---
task: 01M3RHSS9S7GJXW28WMJKNC8YG
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Тест таймаута прогона приёмочных тестов не зависит от порядка тестов

## Фаза A: план
- Покрытие: все требования 1–4 привязаны к шагам плана, таблица полная.
- Шаги размером с MR: правка одного теста плюс поиск по требованию 4.
- Подход (подмена, не зависящая от кэша, плюс явная установка кэша с
  возвратом через `addCleanup`) не противоречит конвенциям. Код пульта не
  тронут, зона — `tests/`, как в SPEC.
- Перечень по требованию 4 есть, поиск описан тремя grep'ами и тремя
  точками вызова `environment_fingerprint`. Точки вызова я сверил с
  описанием: вызов в `advance_gates/acceptance.py` идёт после
  `acceptance.run`, остальные — в `runner.py`, где подменяют `Popen`.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `tests/test_acceptance_tests_flow.py:1064-1069`: вызов pytest опознаётся по элементу `"pytest"` в списке команды (`_pytest_command` → `[py, "-m", "pytest", …]`, `orchestrator/acceptance.py:38`) без `--collect-only`. Требуется ровно один такой вызов и `timeout=ACCEPTANCE_TIMEOUT_SEC`. Проверки `in_dev`, вывода «превысил Nс» и единственной записи журнала сохранены. |
| 2 | OK | Проверено временной мутацией: без `timeout=` в `acceptance.run` оба теста красные. |
| 3 | OK | Два теста: кэш `None` и заполненный кэш. Исходное значение кэша возвращается через `addCleanup`. Оба зелёные в одиночном прогоне `-k timeout`. Полный `tests/` зелёный в CI c7100ed8. |
| 4 | OK | Перечень в PLAN. Кроме исходного теста, других таких тестов не найдено, поиск описан. |

## Замечания
- minor — tests/test_acceptance_tests_flow.py:1047-1048 — после правки нет пробела в `exc =subprocess.TimeoutExpired(`, и строка продолжения `timeout=…` съехала на один столбец относительно скобки. Это только оформление, на поведение не влияет. Поправить при случае, в реестр не заношу.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved — замечаний уровня blocker или major нет.

## Проверено исполнением
- `python3 -m pytest tests/test_acceptance_tests_flow.py -k timeout -p no:cacheprovider -q` — 2 passed.
- `python3 -m pytest tasks/01M3RHSS9S7GJXW28WMJKNC8YG/acceptance_tests -p no:cacheprovider -q` — 5 passed, 8 subtests passed.
- Временная мутация: убрал `timeout=config.ACCEPTANCE_TIMEOUT_SEC` из вызова в `orchestrator/acceptance.py:186-189` (`run`). Тот же прогон `-k timeout` дал 2 failed: оба теста, и с пустым, и с заполненным кэшем. Файл вернул через `git checkout orchestrator/acceptance.py`, `git status` чистый (кроме `tasks/`).
- CI коммита c7100ed8 зелёный (14 проверок, из пакета). Это покрывает прогон теста в составе полного `tests/`.

## Предложения системе
- Поддерживаю предложение из PLAN: в skills/test-authoring.md стоит добавить антипаттерн «сверка `mock.call_args` при подмене общего `subprocess.run`, когда на пути есть побочные вызовы с кэшем на процесс». Вызов нужно опознавать по команде.
