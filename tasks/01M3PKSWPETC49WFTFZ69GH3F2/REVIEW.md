---
task: 01M3PKSWPETC49WFTFZ69GH3F2
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Канарейка исполняет код проверяемого коммита, а не код пина (ADR-0021, этап 0)

## Фаза A — план

- Таблица покрытия полна: требования 1–8 привязаны к шагам 1–3, AC-11 закрыт
  перечнем в «Переписанные тесты и сохранённые свойства».
- Шаги — единицы размера MR (вход, переключение фазы 1, тесты), не
  микрооперации.
- Подход согласован с архитектурой: помощники ведения остаются в
  `canary.py` и исполняются копией модуля из клона, форма 9-элементного
  кортежа фазы 1 сохранена ради `PhaseOneCodexAuthArgumentTest` и планки
  01M3GKJFN90ATK2KECNDZXPPP6. Решение «существующие тесты не переписывать»
  обосновано: они проверяют помощники, а не то, какой процесс их вызывает.
- Риск с чужой залоченной планкой 01M1SC3Y20YBTTJVQDJBF2NDQW
  (`test_canary_report_kill_reason.py` против нового устройства не
  пройдёт) назван честно. Её правка — дело Оператора через `amend-tests`,
  этой задаче не вменяется.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `sys.executable -m orchestrator.canary_drive`, `cwd=dest`, файл `--result` (`canary.py::_drive_in_clone`). Порядок ведения — `canary._drive_task` из клона. Сторожа в `tests/` у самого `drive()` нет (R1-F2) |
| 2 | OK | `build_result`: task_id, head, outcome, escalated, metrics, steps |
| 3 | OK | Пульт больше не вызывает `catalog.cmd_new`/`workspace.ensure`/`_drive_task` (из `_run_task_in_ephemeral_clone` убраны) |
| 4 | OK | `_ephemeral_clone`, `_set_plan`, `_codex_clone_auth`, `_baseline_deviation_note`, `_run_verdict` не тронуты |
| 5 | OK | `main_sha = metrics["code_sha"]`, при расхождении `normal_outcome=False`. Сводка называет оба коммита; сторожа в `tests/` у строки сводки нет (R1-F2) |
| 6 | OK | `sys.exit` с «ADR-0021, этап 0» внутри блока клона до запуска процесса; кодом пина задача не ведётся |
| 7 | реализовано не полностью | Код выхода, отсутствующий или битый результат, таймаут → `CanaryDriveFailed` → красная строка. Но прерывание пульта оставляет живую группу процесса клона (R1-F1). При снятии по таймауту буферизованный вывод Python теряется (R1-F3) |
| 8 | OK | Существующие файлы `tests/` не изменены; новый `tests/test_canary_drive.py` |

## Замечания

- **major** — `orchestrator/canary.py::_drive_in_clone` (блок `try: returncode = proc.wait(timeout=…)` / `except subprocess.TimeoutExpired`). Процесс клона запущен в собственной сессии (`start_new_session=True`), а снятие группы есть только в ветке `TimeoutExpired`.
  - **Сценарий.** Любое другое прерывание ожидания — Ctrl-C Оператора (`KeyboardInterrupt`), `SystemExit` от обработчика сигнала, SIGTERM пульту — выходит из `with clone_ctx`, и `finally` `_ephemeral_clone` удаляет клон и origin-заглушку. Группа процесса клона при этом продолжает жить: SIGINT терминала до неё не доходит, потому что у неё своя сессия. Текущий шаг роли (агент до `AGENT_TIMEOUT_SEC` = 45 мин) продолжает тратить бюджет и подписку на удалённом каталоге. Затем `auto` клона падает на исчезнувших путях.
  - **Почему это регрессия.** До задачи ведение шло в процессе пульта и умирало вместе с ним.
  - **Предложение.** Ловить `BaseException` вокруг `proc.wait`: `liveness.terminate_process_group(proc.pid)`, `proc.wait()`, `raise`. Добавить тест в `tests/test_canary_drive.py` — `KeyboardInterrupt`, поднятый из подменённого `proc.wait`/`Popen.wait`, снимает группу, после выхода процесс мёртв.
- **major** — долгоживущие свойства задачи без сторожа в `tests/` (ADR-0018 п.3). Вся планка задачи помечена `Группа: разовый`, после мержа её не гоняет никто. Проверено временной мутацией: прогон `tests/test_canary_drive.py tests/test_canary.py tests/test_canary_budget_ceiling.py tests/test_canary_synthetic_answer.py tests/test_canary_codex_clone_auth.py` — 163 passed при каждой из двух мутаций; код возвращён `git checkout`.
  - **Место 1: `orchestrator/canary_drive.py::drive`.** Удалён вызов `canary._drive_task(conn, task_id)` — зелёный весь набор. В `CanaryDriveMainTest` `drive` подменён целиком, и ведение, порядок `cmd_new → workspace.ensure → _drive_task → build_result` и проверку `wt_error` не держит ни один тест `tests/`. Последствие: будущая правка входа, которая перестанет вести задачу или заводить worktree, пройдёт CI. Канарейка при этом выдаст «штатный» результат по недоведённой задаче либо упадёт только на живом прогоне.
  - **Место 2: `orchestrator/canary.py::_run_one_task`, строка `[РАСХОЖДЕНИЕ КОММИТА: …]`.** Условие заменено на `if False:` — зелёный весь набор. Свойство AC-6 «сводка называет причину и оба коммита» держит только разовая планка.
  - **Предложение.** В `tests/test_canary_drive.py`:
    - тест `drive()` с подменёнными `catalog.cmd_new`/`workspace.ensure`/`canary._drive_task`/`build_result`: порядок вызовов и отказ на `wt_error`;
    - тест `_run_one_task` с подменённой фазой 1, метрики с `code_sha != target_sha`: строка сводки несёт оба sha.
- **minor** — `orchestrator/canary.py::_drive_in_clone`, argv `[sys.executable, "-m", CANARY_DRIVE_MODULE, …]`.
  - **Проблема.** stdout процесса клона направлен в файл, поэтому у Python он блочно буферизован (~8 КБ). По таймауту группа снимается SIGTERM/SIGKILL, буфер не сбрасывается. Строки ведения (`store.set_state`, `cleanup.cmd_kill`, `print` помощников) последних минут, а при коротком выводе — весь вывод процесса теряются. Каталог диагностики AC-9 окажется без того, что нужно для разбора зависания. Тест `test_hanging_process_is_killed_after_the_limit` этого не видит: сценарный вход печатает с `flush=True`.
  - **Предложение.** Запускать с `-u` (прецедент — `orchestrator/artel.py:647`, `[sys.executable, "-u", …]`) или `PYTHONUNBUFFERED=1` в окружении процесса.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/canary.py::_drive_in_clone (`proc.wait` / `except subprocess.TimeoutExpired`) | Прерывание пульта, кроме таймаута (Ctrl-C, SystemExit, SIGTERM), не снимает группу процесса клона из собственной сессии | Агент роли продолжает работать и тратить бюджет на удалённом клоне после выхода пульта | `except BaseException`: `terminate_process_group(proc.pid)`, `proc.wait()`, `raise`, плюс тест в `tests/` |
| R1-F2 | open | orchestrator/canary_drive.py::drive; orchestrator/canary.py::_run_one_task (`[РАСХОЖДЕНИЕ КОММИТА…]`) | Долгоживущие свойства (ведение в `drive()` и сводка с обоими коммитами, AC-6) держит только разовая планка; временная мутация каждого — `tests/` зелёные | После мержа поломку входа или строки сводки CI не поймает | Тесты в `tests/test_canary_drive.py`: порядок и отказ `drive()`; строка сводки `_run_one_task` при `code_sha != target_sha` |
| R1-F3 | open | orchestrator/canary.py::_drive_in_clone (argv) | Вывод процесса клона блочно буферизован; при снятии по таймауту буфер теряется | Диагностика зависания (AC-9) без строк ведения | Запуск с `-u` / `PYTHONUNBUFFERED=1` |

## Вердикт

`changes_requested`. Нужно исправить R1-F1 и R1-F2 (major), желательно заодно R1-F3. Основная механика (ведение кодом клона, отказ без входа, сбой и таймаут → красная строка, `main_sha` из HEAD клона) реализована верно и проверена исполнением.

## Проверено исполнением

- `python3 -m pytest -q tasks/01M3PKSWPETC49WFTFZ69GH3F2/acceptance_tests` — 20 passed (79.5 с).
- `python3 -m pytest -q tests/test_canary_drive.py tests/test_canary.py tests/test_canary_budget_ceiling.py tests/test_canary_codex_clone_auth.py tests/test_canary_synthetic_answer.py tests/test_canary_template_flag.py tests/test_canary_sets.py tests/test_pin.py` — 239 passed, 18 subtests passed.
- Временная мутация (обе сразу): удалён `canary._drive_task(conn, task_id)` в `canary_drive.drive` и условие строки `[РАСХОЖДЕНИЕ КОММИТА]` заменено на `if False:`. Прогон `tests/test_canary_drive.py tests/test_canary.py tests/test_canary_budget_ceiling.py tests/test_canary_synthetic_answer.py tests/test_canary_codex_clone_auth.py` — 163 passed, то есть сторожа нет (R1-F2). Код возвращён `git checkout -- orchestrator/canary.py orchestrator/canary_drive.py`, `git status` чист, кроме `tasks/`.
- Сверка `tests/` по диффу: изменён только новый файл `tests/test_canary_drive.py`, существующие ассерты не тронуты. Каждый метод нового файла несёт «Ловит мутацию: …».
- `grep "Группа:"` по планке: все 9 файлов `разовый`, основание для R1-F2.

## Предложения системе

- `skills/review-checklist.md` / роль test_author: планка, где свойства кода (AC-1/3/5/6) целиком помечены `разовый`, перекладывает на разработчика обязанность сторожа в `tests/`, но PLAN такого перечня «свойство → тест `tests/`» не требует. Стоит добавить в шаблон PLAN таблицу «долгоживущее свойство → сторож в `tests/`».
- Вечная чужая планка 01M1SC3Y20YBTTJVQDJBF2NDQW, которую не гоняет CI, после этого мержа станет заведомо красной. Нужна отметка Оператора (`amend-tests` или вывод из обращения), иначе следующий, кто её запустит, примет это за регрессию.
