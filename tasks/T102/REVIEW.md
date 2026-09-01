---
task: T102
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: cmd_new отклоняет нераспознанные аргументы

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (отказ ДО расхода номера/ветки, называет нераспознанное + форма) | OK | `_parse_new_args` (`orchestrator/artel.py:244-267`) валидирует `rest` целиком ДО первого вызова `catalog.cmd_new`; `remainder` (лишний позиционный/неизвестный флаг) даёт `sys.exit(f"Нераспознанный аргумент: {remainder[0]}\n{_NEW_USAGE}")`. |
| 2 (`--help`/`-h`/без аргументов — форма, без задачи) | OK | `orchestrator/artel.py:254-256`: `print(_NEW_USAGE); return None`; `_cmd_new` (270-275) на `None` просто возвращается, `catalog.cmd_new` не вызывается. |
| 3 (название с `-` не принимается) | OK | `orchestrator/artel.py:257-259`: `title.startswith("-")` → `sys.exit`, ДО обращения к `_tz_arg`/`catalog.cmd_new`. |
| 4 (существующие формы работают без изменений) | OK | `_tz_arg` не изменена (сигнатура и поведение те же); `ArtelCliTzFlagTest` (`tests/test_analyst_role.py`) зелёный без правок. |
| AC-1..AC-7 | OK | Все 7 критериев покрыты `tasks/T102/acceptance_tests/*.py`, прогнаны — зелёные (см. «Проверено исполнением»). |

## Замечания

Замечаний нет.

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest tests.test_new_argv_parsing -v` — 9 тестов, все зелёные (юнит-тесты `_parse_new_args`: валидные формы, `-h`/`--help`/пустой rest, лишний позиционный, неизвестный флаг, название с `-`, висящий `--tz`).
- `python3 -m unittest discover -s tasks/T102/acceptance_tests -v` — 9 тестов (AC-1..AC-7, AC-5 двумя примерами), все зелёные.
- `python3 -m unittest tests.test_analyst_role.ArtelCliTzFlagTest -v` — 4 теста, все зелёные: регресс контракта `_tz_arg`, на который явно опирается PLAN, не сломан.
- `python3 -m unittest discover -s tests` — 1185 тестов, 2 упавших:
  `test_agent_log.CmdRunLoggingTest.test_timeout_kills_process_and_journals` и
  `test_step_cost.CmdRunPartialCostTest.test_timeout_with_usage_events_charges_a_partial_token_sum`
  — оба ожидают «таймаут шага (30 мин)», получают «(45 мин)». Diff T102 не
  касается `orchestrator/runner.py`/`config.py`/`test_agent_log.py`/
  `test_step_cost.py` ни строкой; расхождение объясняется коммитом
  `20afc92` (уже в истории ветки, «AGENT_TIMEOUT_SEC 1800 → 2700 временно
  на стройку M1... вернуть после мержа T094»), который меняет именно этот
  таймаут и явно называет себя временным. Предсуществующий сбой вне зоны
  T102, не блокирует — но см. «Предложения системе».
- `python3 scripts/guard.py --all` — `GUARD: ок (341 файлов)`.
- `python3 scripts/codebase_map.py` (регенерация) — diff после регенерации
  ограничен строкой `built_at_sha` (сверено по содержимому без неё,
  `git diff docs/codebase-map.md` до и после); карта в MR уже актуальна,
  включая новую запись `tests/test_new_argv_parsing.py` и обновлённый
  список «Импортируется» для `orchestrator/artel.py`. Рабочее дерево
  возвращено в чистое состояние (`git checkout -- docs/codebase-map.md`)
  после проверки.
- Прочитан код `orchestrator/artel.py:229-301` (`_tz_arg`, `_parse_new_args`,
  `_cmd_new`, диспетчер `main()`) и `orchestrator/catalog.py:90-130`
  (`cmd_new`) — подтверждено ручной трассировкой, что глобальная ветка
  `-h/--help` в `main()` (строка 294) не перехватывает `new -h`
  (`args[0] == "new"`, не `"-h"`), и что порядок «валидация → расход
  номера» действительно не даёт `_parse_new_args` дойти до
  `store.peek_task_number`/создания worktree на отказном пути.

## Предложения системе

- Полный прогон `tests/` на этой ветке содержит 2 предсуществующих сбоя
  (`test_agent_log.py`, `test_step_cost.py`), вызванных временным
  изменением `AGENT_TIMEOUT_SEC` под M1 (коммит `20afc92`, класс
  «лимит», должен быть возвращён после мержа T094) — не дефект T102, но
  до возврата конфига полный прогон `tests/` будет краснеть на КАЖДОЙ
  ветке, подтянувшей этот коммит main; стоит проверить, снят ли он
  вовремя после мержа T094, иначе следующие ревью будут повторно тратить
  время на то же самое разбирательство «пред-существующий сбой или нет».
