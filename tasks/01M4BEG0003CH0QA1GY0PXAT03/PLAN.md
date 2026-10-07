---
task: 01M4BEG0003CH0QA1GY0PXAT03
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Канарейка пропускает полный набор на приёмке учебной задачи

## Подход

В `config.py` булев признак выключен по умолчанию. Блок эфемерного клона временно включает его и восстанавливает прежнее значение в `finally`. `_drive_in_clone` передаёт маркер через окружение отдельному процессу; `config.py` учитывает этот маркер только при запуске модуля `orchestrator.canary_drive` как `__main__`. Поэтому обычный процесс пульта с тем же внешним окружением сохраняет полный прогон. В автогейте ветка пропуска записывает точную причину в журнал и выполняет остальные проверки.

## Шаги

1. Включить признак внутри эфемерного клона, передать маркер дочернему процессу и восстановить исходное значение на обоих выходах.
2. В автогейте пропустить полный набор только при включённом признаке, записать причину и сохранить обработку остальных условий и отказов.
3. Изолировать чтение маркера входом `canary_drive`, добавить незалоченный тест на границу процессов без правки файла из перечня сумм, проверить мутациями, регенерировать карту и прогнать целевые тесты, планку и guard.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2 |
| 3 | 1, 2, 3 |
| 4 | 2, 3 |
| 5 | 3 |

## Влияние на систему

Затронуты конфигурация процесса канарейки, запуск процесса клона, автоматическая приёмка и новый тест границы процессов. Гейты планки, CI, бюджета и обычной задачи остаются в прежнем порядке; `approve` не читает новый признак. Пропуск пишется отдельным действием журнала и не совпадает с действием отказа автогейта, по которому заполняется `canary_runs.autogate_refusal`. Файл из зафиксированного перечня тестов не менялся. Откат — revert коммита задачи.

## Риски

Процесс клона получает собственный импорт `config.py`: без передачи через окружение пропуск виден лишь внешнему процессу. Новый тест проверяет переданный `Popen(env=…)` и реальный импорт при запуске `python -m orchestrator.canary_drive --help` без запуска роли.

Полный набор `suite-run` повторно не стартовал: команда пульта получила `PermissionError` при создании `/Users/al.sidorenko/projects/artel/.artel/logs/suite-run/lock.json`, путь вне разрешённых для записи каталогов роли. Целевые тесты и планка прошли; полного результата нет.

## Проверки

- `python3 -m pytest tests/test_01m4beg0003ch0qa1gy0pxat03_clone_marker.py tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py tests/test_fsm_autogate.py tests/test_canary_drive.py tests/test_canary.py -p no:cacheprovider -p timeout -o timeout=120` — 141 passed.
- Дополнительные модули канарейки (`test_canary_acceptance_reason.py`, `test_canary_codex_clone_auth.py`, `test_canary_profile_safety.py`, `test_canary_sets.py`, `test_canary_template_flag.py`) — 102 passed.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4BEG0003CH0QA1GY0PXAT03` — 1 passed.
- Новый тест покраснел при трёх временных мутациях: передача `0` в `Popen(env=…)`, принятие внешнего env обычным процессом и непринятие маркера процессом `canary_drive`. Мутации убраны.
- `python3 scripts/codebase_map.py` — карта обновлена.
- `python3 scripts/guard.py /Users/al.sidorenko/projects/artel/.artel/projects/artel/tasks/01M4BEG0003CH0QA1GY0PXAT03/PLAN.md` — `GUARD: ок`; `git diff --check` — без ошибок.

## Предложения системе

- `orchestrator/suite_run.py::_acquire_lock` пишет в `.artel/logs/suite-run/lock.json` вне writable roots роли. Команда `suite-run <id>` падает `PermissionError` до прогона; пульту нужен доступный роли адрес замка либо запуск команды за пределами песочницы роли.
