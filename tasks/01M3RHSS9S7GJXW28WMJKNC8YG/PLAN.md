---
task: 01M3RHSS9S7GJXW28WMJKNC8YG
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Тест таймаута прогона приёмочных тестов не зависит от порядка тестов

## Подход
Выбрана подмена, которая не зависит от кэша, а не сброс кэша в тесте.
Тест по-прежнему подменяет `acceptance.subprocess.run` целиком
(`side_effect=TimeoutExpired`), но `timeout` сверяет не у
`run_mock.call_args` (последнего вызова), а у вызова из
`call_args_list`, чья команда (`args[0]`) содержит `pytest` и не содержит
`--collect-only`. Это и есть вызов прогона из `acceptance.run`
(`_pytest_command`). Тест требует, чтобы такой вызов был ровно один.
Вызовы `git/claude --version` из `environment_fingerprint` (timeout=5) под
этот фильтр не попадают, поэтому состояние кэша на итог не влияет.

Тело теста вынесено в `_assert_timeout_blocks_the_transition(cache)`. Два
теста задают состояние кэша явно: `None` (пустой, как при одиночном
запуске) и заранее заполненная строка (как после соседа в полном
`tests/`). В обоих тестах в имени есть `timeout`, поэтому оба попадают в
выборку планки `-k timeout`. Исходное значение кэша возвращается через
`addCleanup`, и соседние тесты его состояния не видят. Проверки вывода
(`превысил {ACCEPTANCE_TIMEOUT_SEC}с`), журнала (ровно одна запись
«переход отклонён: приёмочные тесты» со словом «превысил») и состояния
`in_dev` сохранены без изменений.

Бюджет SPEC не пересматривается.

## Шаги
1. `tests/test_acceptance_tests_flow.py`: переписать
   `AcceptanceRunTest::test_timeout_blocks_the_transition_and_names_the_limit`
   так, чтобы сверялся вызов pytest, выбранный по команде. Добавить
   `AcceptanceRunTest::test_timeout_blocks_the_transition_with_prefilled_fingerprint_cache`.
   Регенерировать `docs/codebase-map.md`.
2. Поиск того же дефекта по `tests/` (требование 4).

## Перечень по требованию 4 (поиск того же дефекта)
Найден и исправлен один тест — исходный:
- `tests/test_acceptance_tests_flow.py::AcceptanceRunTest::test_timeout_blocks_the_transition_and_names_the_limit`
  (к нему добавлен близнец с заполненным кэшем
  `tests/test_acceptance_tests_flow.py::AcceptanceRunTest::test_timeout_blocks_the_transition_with_prefilled_fingerprint_cache`).

Других тестов с этим дефектом не найдено. Как искал:
- `environment_fingerprint()` вызывается в трёх местах:
  `orchestrator/runner.py:1189`, `:1484` и
  `orchestrator/advance_gates/acceptance.py:264`. Все они внутри шага роли
  или перехода `cmd_advance`.
- `grep -rn "call_args\b" tests`. Сверку последнего вызова подменённого
  `subprocess.run` делают только test_acceptance.py:102/121
  (`acceptance.run_full_suite`), test_acceptance_collect.py:93
  (`acceptance.collect`), test_ci_status.py:607 (`ci.gh`) и
  test_git_hooks.py:267 (`gitcmd.git`). Все они зовут функцию напрямую,
  мимо пути, на котором вызывается `environment_fingerprint`. В остальных
  совпадениях сверяется `subprocess.Popen` (runner: fingerprint его не
  зовёт) или моки функций пульта, а не `subprocess.run`.
- `grep -rn '"subprocess.run"' tests` находит глобальные подмены
  (test_ci_push_class, test_fsm_map_regen, test_brief, test_codebase_map,
  test_acceptance_tests_flow:974/1009). Ни одна из них не сверяет
  `call_args` последнего вызова на пути fingerprint. Два теста
  fingerprint в test_acceptance_tests_flow сами сбрасывают кэш и
  проверяют текст журнала.
- `grep -rn "call_args_list\[-" tests`: сверок «последний из списка» на
  `subprocess.run` нет.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 2 |

## Влияние на систему
Изменён только тест, код пульта не трогал. Проверка не ослаблена: к
прежним ассертам добавлено требование, что вызов pytest ровно один, и
сверяется `timeout` именно этого вызова. Проверил, что мутации ловятся,
прогоном планки `_runner.py`. При удалении `timeout=` из `acceptance.run`
и при замене слова «превысил» тесты красные (код 1) при обоих состояниях
кэша. Без мутаций тесты зелёные при обоих состояниях кэша.

Прогоны в шаге:
- `python3 -m pytest tests/test_acceptance_tests_flow.py -k timeout -p no:cacheprovider -p timeout -o timeout=120`: 2 passed.
- Планка `test_ac1_ac2_ac3_timeout_test_cache_independent.py`: 4 passed, 4 subtests passed.

Откат — revert коммита.

## Риски
Фильтр опознаёт вызов по подстроке `pytest` в команде. Если
`_pytest_command` сменит способ запуска (например, на бинарь `py.test`),
тест упадёт на проверке «вызов pytest ровно один». Упадёт громко, а не
пройдёт вхолостую.

## Предложения системе
- Класс дефекта «сверка `mock.call_args` (последнего вызова) при подмене
  общего `subprocess.run`, когда на пути есть кэшируемые на процесс
  побочные вызовы» стоит внести в skills/test-authoring.md как
  антипаттерн: вызов нужно опознавать по команде.
