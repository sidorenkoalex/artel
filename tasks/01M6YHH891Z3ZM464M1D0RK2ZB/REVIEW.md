---
task: 01M6YHH891Z3ZM464M1D0RK2ZB
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Ускорение тестов suite_run без ослабления — уборка без ожидания своего процесса, меньшие пределы, шаг опроса из config, проверка процессов вместо пауз

## Фаза A: план
- Таблица покрытия полна (требования 1–9 → шаги 1–2). Два шага — проверяемые единицы
  (код + карта; тестовый файл), деление обосновано в SPEC («Оценка объёма»).
- «Влияние на систему» совпадает с диффом: `config.py`, `suite_run.py`, `mutation_run.py`,
  один тестовый файл, карта. Откат — revert merge-коммита. Конфликта с архитектурой нет.
- AC-10 (таблица мутаций `mutation-run`) в шаге не гонялась — PLAN это честно называет;
  по SPEC это свидетельство приёмки, не шаг разработчика.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `config.py:296` `SUITE_RUN_POLL_SEC = 1.0`; `_POLL_SEC` из `suite_run.py` удалена, `wait_request`/`_wait` (`:952`, `:1100`) и `mutation_run._wait` (`:861`) читают `config.SUITE_RUN_POLL_SEC` в момент паузы. grep: ссылок на `_POLL_SEC` модуля suite_run больше нет. Держит долгоживущий `tests/test_01m6yhh891z3zm464m1d0rk2zb_poll_step.py`. |
| 2 | OK | Копия `config.py` песочницы дописывает `SUITE_RUN_POLL_SEC = 0.1`. |
| 3 | OK | `pids.discard(os.getpid())` после цикла сбора; потомки остаются. |
| 4 | OK | `TIMEOUT_SEC = 8` у `TimeoutTest`, `BaseTimeoutTest`, `FootprintTest`; ac16 гейт — `FULL_SUITE_TIMEOUT_SEC` 3. |
| 5 | OK | `assertEqual(result.outcome, acceptance.FULL_SUITE_TIMEOUT)` добавлено к `assertFalse(result.green)`. |
| 6 | OK | ac24: кроме «предел» — `self.report(...)` без «не уложился»; «зелёная»/«красная» — лог `…-base.log` несёт `PYTEST_SUMMARY`; у «исключения» — нет. Отсутствие лога базы — красный (`assertTrue(base_log.is_file())`), не молчаливый пропуск. |
| 7 | OK | `assert_no_run` (ac3, ac4), ac9, ac20, ac21: `time.sleep` нет; сначала `process_snapshot()` (`/bin/ps -axww -o pid=,ppid=,command=`, провал «снимок процессов не получен» без строки `os.getpid()`), затем журналы. Иглы: id задачи, проба, корень (как есть и после realpath), граница пути `(?![\w.-])` ловит и подпути. ac21: id и рабочая копия B — у всех процессов; проба и корень — у всех, кроме `holder` и потомков по `ppid` в том же снимке. ac9 дополнительно получил проверку пустого журнала `conftest.py` (по SPEC: «журналы обёртки и conftest.py пусты»). |
| 8 | OK | Сверено с base по диффу: прежние утверждения не сняты и не ослаблены, изменён только вызов `assert_no_run(out)` → `assert_no_run(out, task_id)` (гейт: покрыто мандатом ANSWER-1); паузы ac6/ac8 не тронуты; 26 тестов, skip нет (планка AC-9 зелёная). Сужения данных под неизменными утверждениями не нашёл: `setUp`, фикстуры и `outcomes` ac24 прежние. |
| 9 | OK | `tests/test_01m5pwfgjqnv8ysan5mf0ckhvw_mutation_run_flags.py` и долгоживущий тест задачи зелёные; CI коммита 55aef548 зелёный (16 проверок). |

## Замечания
Нет замечаний уровня blocker/major/minor.

Наблюдения для Оператора (к указанию на гейте SPEC, не замечания разработчику):
- Указание 3: ac24 строит путь лога базы из пути лога ветки, названного в выводе запуска
  `suite-run` (`launched`), с суффиксом `-base` — по правилу `suite_run._log_path`, но
  источник — вывод запуска, а не запись `run.json`. Вывод отчёта `--wait` не используется,
  промах пути даёт красный тест, а не ложный зелёный — по существу указание соблюдено.
- Указание 1: `process_snapshot` не сверяет код выхода `ps` отдельно — провал держится только
  на наличии строки `os.getpid()` в снимке. Пустой или сорванный снимок этим ловится;
  ненулевой код при частичном выводе, содержащем pid теста, — теоретический случай.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `artel.py plank-run 01M6YHH891Z3ZM464M1D0RK2ZB` — 8 passed in 1.59s, код выхода 0.
- `python3 -m pytest -p no:cacheprovider -q tests/test_01m6yhh891z3zm464m1d0rk2zb_poll_step.py tests/test_01m5pwfgjqnv8ysan5mf0ckhvw_mutation_run_flags.py` — 43 passed за 150 с.
- `python3 -m pytest -p no:cacheprovider -q --durations=8 tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py` — 26 passed, 6 subtests passed за 176,7 с серийно (самый долгий — ac24, 25 с; ac13 в верхних восьми больше нет).
- Временная мутация (сторож ac21): в `orchestrator/suite_run.py` перед `sys.exit` отказа по замку
  добавлен `subprocess.Popen` фонового процесса задачи B. `pytest …::LockTest` — 1 failed:
  «живой процесс 82571 (ppid 1) несёт «01MJM80JJ716RMXPYGF84XD339»: … suite_run.background(…) 01MJM80JJ716RMXPYGF84XD339 1 full». Код возвращён, `git status` чистый.
- `python3 scripts/codebase_map.py` → `git diff -- docs/codebase-map.md` без строки `built_at_sha`: пусто, карта свежая (регенерация откачена).
- grep `_POLL_SEC` по `orchestrator/` и `tests/`: ссылок на `suite_run._POLL_SEC` нет.

## Предложения системе
- `scripts/codebase_map.py --help` не печатает справку, а молча перегенерирует карту — у
  ревьювера рабочая копия меняется без явного намерения; стоит завести `--check`-режим
  (как сравнение в CI-джобе) для проверки свежести без записи.
