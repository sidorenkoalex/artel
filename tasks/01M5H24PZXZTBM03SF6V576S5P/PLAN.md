---
task: 01M5H24PZXZTBM03SF6V576S5P
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Механика канарейки, часть Б-1б: параллельный прогон --parallel

## Подход
Развилка одна — в `canary.cmd_canary` сразу после `_set_plan`: при
`parallel=True` управление уходит в новую `_cmd_canary_parallel`, прежняя
ветка (замок профиля, `_resolve_target_sha`, последовательный цикл) не
переписана ни строкой. Новый параметр `parallel` необязательный, по
умолчанию `False`; `_cmd_canary` передаёт его только при флаге (по образцу
`on_run_stamp`).

Родитель параллельного прогона (`orchestrator/canary.py`):
- до origin и до реестра — отказ набора с `codex_roles`, затем сверка
  попарной различности имён шаблонов (повтор `--template` уже отказан
  прежним `_named_pool_templates`);
- `_resolve_target_sha`, `run_stamp`, `_live_run_record` (прежний), приёмник
  `on_run_stamp`, первая строка с « параллельно: не более 2 процессов»;
- очередь `_run_children`: не больше `PARALLEL_CHILD_LIMIT = 2` живых
  дочерних; каждый — `subprocess.Popen` с argv из `_child_argv`
  (интерпретатор `-u`, `artel.py canary run-task` и пять флагов), своей
  группой (`start_new_session`), `cwd=config.ROOT`, вывод в журнал
  `<LOGS>/canary/<run_stamp>-<шаблон>.log`, открытый родителем; запуск — под
  `_SignalDeferral`;
- ожидание — поток на каждого дочернего зовёт `_wait_child(proc)` и кладёт
  исход в очередь; главный поток ждёт очередь (сигнал её прерывает).
  `Exception` из `_wait_child` — остановка группы этого дочернего, красная
  строка «ожидание процесса задачи прервано: …», очередь дальше;
  `BaseException` вне `Exception` — пробрасывается в главный поток = выход;
- остановка `_stop_children`: SIGTERM всем группам, общий срок
  `PARALLEL_STOP_GRACE_SEC = 60`, SIGKILL оставшимся, ожидание всех; под
  `_SignalDeferral`, отложенный сигнал не поднимается заново, а лишь
  определяет код выхода, если родитель выходил не по сигналу;
- завершение дочернего `_finish_child`: блок «[canary] <шаблон>: процесс
  <pid> завершён с кодом <n>, журнал <путь>» + журнал целиком; снятие записи
  реестра мёртвого дочернего (только его `.json`, метка не трогается); при
  отсутствии строки шаблона с `run_stamp` — красная строка по образцу
  `_report_drive_failure` (`task_id`/`expected_escalation` — `None`) и
  причина в выводе;
- сигналы родителя SIGTERM/SIGHUP/SIGINT во время очереди ловит прежний
  `_interrupt_on_signal`, которому добавлен необязательный перечень
  сигналов (по умолчанию прежний — SIGTERM, SIGHUP).

Сверка формы `--sha` в `cmd_canary_run_task` — первой строкой тела, до
`_set_plan` и записи реестра, по `reference_cache.SHA_FORM`.

`artel._cmd_canary`: повтор `--parallel` — отказ до ветки `--detach`; с
`--detach` флаг остаётся в argv отвязанного процесса (прежняя передача
`rest`); справка называет `--parallel`.

Имена (ANSWER-1): `PARALLEL_CHILD_LIMIT`, `PARALLEL_STOP_GRACE_SEC`,
`_wait_child`, `_child_argv`.

## Шаги
1. `orchestrator/canary.py`: константы, `_child_argv`, `_wait_child`,
   `_cmd_canary_parallel` и помощники, параметр `parallel` в `cmd_canary`,
   сверка формы sha в `cmd_canary_run_task`, перечень сигналов в
   `_interrupt_on_signal`.
2. `orchestrator/artel.py`: разбор `--parallel`, справка.
3. Тесты разработчика `tests/test_canary_parallel.py` (требование 9):
   очередь и argv с простым дочерним, красная строка за дочерний без
   строки, остановка по сигналу настоящим `cmd_canary_run_task` в отдельном
   интерпретаторе, сверка sha.
4. Карта `python3 scripts/codebase_map.py`, планка `plank-run`, тесты
   затронутых модулей, `suite-run`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | 1 |
| 7 | 1 |
| 8 | 1 (потребители и чтение реестра не тронуты) |
| 9 | 3 |

## Влияние на систему
Без `--parallel` путь побайтно прежний: развилка — одна строка `if` в
`cmd_canary`, `_interrupt_on_signal` без аргумента ставит те же два
сигнала. Потребители реестра (`_silence_window_reason`,
`_refuse_during_canary`, `refuse_main_move_during_canary`, `live_run_note`)
и функции чтения/уборки реестра не меняются. Запись родителя и метка
держатся прежним `_live_run_record` до конца остановки всех дочерних —
окно тишины части А не ослабляется. Подкоманда `run-task` меняется только
сверкой формы sha (отказ раньше записи). Откат — revert merge-коммита.

## Проверка
- Имена отчёта (требование 4): сборка argv — `canary._child_argv`, ожидание
  дочернего — `canary._wait_child(proc)`; константы
  `PARALLEL_CHILD_LIMIT = 2`, `PARALLEL_STOP_GRACE_SEC = 60`.
- `plank-run`: 29 passed.
- `tests/test_canary_parallel.py`: 9 тестов; временные мутации (предел 3,
  `match` вместо `fullmatch`, без снятия записи снятого SIGKILL, выход по
  сигналу без остановки, красная строка без сверки `canary_runs`, обрыв
  очереди на ненулевом коде) — каждая краснит свой тест.
- Тесты затронутых модулей (`test_canary_run_task`, `test_new_argv_parsing`,
  `test_canary_template_flag`, тесты detach/lifecycle 01M4AXPY, тесты Б-2
  01M5FA4N, `test_invariants`) — зелёные.
- `suite-run` №1: оборван пределом 1500 с (нагрузка машины, load 4–6);
  6417 прошло, 2 упали — `test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow::
  SignalDepthTest::test_ac9_each_signal_alone_switches_to_full_review` и
  `test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate::Ac4PrepareTest::
  test_ac4_side_not_started_or_timeout_refuses_naming_side`; модули вне
  диффа, повтор по именам — оба зелёные (346 с).

## Замечания ревью, итерация 1
- R1-F1 — fixed. В `tests/test_canary_parallel.py` добавлены долгоживущие
  тесты (код `orchestrator/` не менялся); `_CHILD` получил режимы
  `term_exit`/`term_hold` (обработчик SIGTERM дочернего, `term_hold` держит
  его на канале `<шаблон>.term`), `run_parallel` — параметр `extra`:
  1. AC-21: `WaitFailureTest::test_wait_exception_red_row_group_stopped_queue_goes_on`,
     `::test_wait_exception_no_second_row_when_row_exists` (подмена `_wait_child`);
  2. AC-20: `WaitFailureTest::test_base_exception_in_wait_then_signal_during_stop`;
  3. AC-14: `StopTest::test_second_signal_does_not_interrupt_stop`;
  4. AC-19: `StopTest::test_killed_child_with_own_row_gets_no_duplicate`
     (строки `canary_runs` и файл результата);
  5. AC-5, AC-17: `ParentRefusalTest::test_repeated_template_refused_before_sha_and_registry`,
     `::test_live_run_stamp_refused_without_receiver_and_children`;
  6. AC-9 верхний регистр: новый метод
     `RunTaskShaTest::test_upper_case_sha_refused_before_record` (прежний
     метод не тронут).
- Временные мутации `orchestrator/canary.py` (код возвращён, `git status`
  без `canary.py`), каждая краснит названный тест:
  «`Exception` из `_wait_child` пробрасывается» → оба AC-21; «поздний сигнал
  не в коде выхода» → AC-20; «поздний сигнал подменяет первый» и «остановка
  в except-ветке без откладывания» → AC-14; «без сверки `_has_run_row`» →
  AC-19 и AC-21 со строкой; «приёмник до `_live_run_record`» → AC-17;
  «выход без остановки дочерних» → AC-20 и тесты StopTest; «сверка sha по
  `.lower()`» → верхний регистр.
- `tests/test_canary_parallel.py` — 17 passed; затронутые модули — 101
  passed; `plank-run` — 29 passed; `suite-run` №2 (полный набор) — зелёный:
  6432 прошло, 0 упало, 2 пропущено.

## Риски
- Конкурентный `Popen.wait` из потока-ожидателя и из остановки: `Popen`
  держит `_waitpid_lock`, ожидание со сроком при занятом замке только
  опрашивает `returncode`.
- Группа ведения в клоне после SIGKILL дочернего может остаться — по SPEC
  это за `doctor`.

## Предложения системе
- `suite-run` полного набора упёрся в предел 1500 с под нагрузкой машины
  (load 4–6), и два медленных теста легли в итог как «новые на ветке» без
  признака ошибки — отчёт не отличает обрыв по пределу от падения теста.
