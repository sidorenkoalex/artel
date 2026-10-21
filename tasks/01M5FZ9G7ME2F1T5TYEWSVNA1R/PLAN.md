---
task: 01M5FZ9G7ME2F1T5TYEWSVNA1R
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Механика канарейки, часть Б-1а: подкоманда canary run-task и запись дочернего в реестр

## Подход
Новая функция `canary.cmd_canary_run_task(*, run_stamp, template_path,
target_sha, set_name, summary)` в конце `orchestrator/canary.py` и разбор
`run-task` в `orchestrator/artel.py` отдельной функцией
`_cmd_canary_run_task(rest)`, которую зовёт одна вставленная ветка
`_cmd_canary` (после `live`, до `--detach`/`--k`). Прежние функции
(`cmd_canary`, `_run_one_task`, `_live_run_record`, `_report_drive_failure`,
функции реестра Б-2) не меняются: приём записи (`.json.tmp` + `os.replace`)
и строка «оборвана сигналом» повторены в новой функции (требование 7).

Тело подкоманды целиком под `_interrupt_on_signal`; внутри `try/finally`,
снимающего свою запись и её `.json.tmp` (пути запомнены до клона —
`_ephemeral_clone` уводит `config.ROOT`):
(0) `_set_plan(--set)`, отказ набора с `codex_roles`; (а) запись
`<run_stamp>-<pid>.json` (поля `_live_run_record` + `parent_pid`,
`template`, `tasks`=1); (б) метка `<run_stamp>.lock` несёт `os.getppid()`,
иначе отказ; (в) `plan.summary == --summary`, иначе красная строка по
образцу `_report_drive_failure` и отказ «набор изменился во время прогона»;
(г) `_run_one_task(template, run_stamp, config.CANARY_DEVIATION_RATIO,
target_sha, None, plan, None)`, `CanaryInterrupted` в нём — строка
«оборвана сигналом <имя>» и `SystemExit(128+n)`. Сигнал вне (г) —
`SystemExit(128+n)` без строки. Подкоманда не зовёт `_resolve_target_sha`,
`fetch_ref_sha`, `_live_run_record`, не трогает метку и профиль Codex.

Разбор: пары «флаг значение» из пяти флагов; неизвестный элемент, повтор,
флаг последним или со следующим элементом на `--` — отказ; все пять
обязательны; `--stamp` — `RUN_STAMP_RE.fullmatch`. Пустая строка значением
законна. Отказ под ролью — прежний `_refuse_if_role_restricted` (canary не
в белом списке); справка `artel.py` не меняется.

## Шаги
1. `orchestrator/canary.py`: `cmd_canary_run_task` и помощник записи.
2. `orchestrator/artel.py`: `_cmd_canary_run_task` и ветка в `_cmd_canary`.
3. `tests/test_canary_run_task.py`: разбор аргументов в любом порядке и
   передача значений; регенерация `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 (поля записи читает прежний `live_runs`) |
| 5 | 1 (прежний `_run_one_task` с планом) |
| 6 | 1 (прежние потребители реестра) |
| 7 | 1, 2 |
| 8 | 3 + планка |

## Влияние на систему
Без вызова `canary run-task` поведение прежнее: добавлена одна ветка в
`_cmd_canary` до прежних, остальные тела не тронуты (AC-7 сверяет разбором).
Код чтения/уборки реестра и потребители окна не меняются — запись дочернего
читается ими как обычная запись (`pid`, `tasks`, `started_at`,
`process_start`). Белый список ролей не расширяется. Откат — revert
merge-коммита.

## Риски
- Сигнал между записью красной строки и выходом — не обрабатывается особо
  (строка уже записана, код 128+n).

## Предложения системе
- `suite-run` при занятом машинном замке отказывает сразу, без режима
  «встать в очередь»: шагу роли приходится писать свой цикл повтора (в
  окружении роли нет даже `sleep`) — не хватает `suite-run <id> --queue`.
