---
task: T102
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 2
---

# REVIEW: cmd_new отклоняет нераспознанные аргументы

## Соответствие SPEC

Инкрементальный diff (`3880ea9...HEAD`) пуст — HEAD ветки совпадает с
коммитом прошлого вердикта (`3880ea97d5706b187f5b1437700e5a853bb10333`
= HEAD, подтверждено `git rev-parse HEAD`), т.е. с итерации 1 в код и
артефакты ничего не добавлено. Ниже — независимая перепроверка того же
кода (не пересказ прошлого REVIEW.md): код прочитан заново, тесты
прогнаны заново.

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (отказ ДО расхода номера/ветки, называет нераспознанное + форма) | OK | `_parse_new_args` (`orchestrator/artel.py:244-267`) валидирует `rest` целиком ДО первого вызова `catalog.cmd_new` (`_cmd_new`, строки 270-275); `remainder` (лишний позиционный/неизвестный флаг, включая случаи «лишнее после `--tz`» и «лишнее перед `--tz`», строки 261-266) даёт `sys.exit(f"Нераспознанный аргумент: {remainder[0]}\n{_NEW_USAGE}")`. |
| 2 (`--help`/`-h`/без аргументов — форма, без задачи) | OK | `orchestrator/artel.py:254-256`: `print(_NEW_USAGE); return None`; `_cmd_new` на `None` просто возвращается, `catalog.cmd_new` не вызывается — номер задачи не расходуется. |
| 3 (название с `-` не принимается) | OK | `orchestrator/artel.py:257-259`: `title.startswith("-")` → `sys.exit`, ДО обращения к `_tz_arg`/`catalog.cmd_new`; включая случай `--tz` как первый токен (тоже начинается с `-`, тоже отказ). |
| 4 (существующие формы работают без изменений) | OK | `_tz_arg` (строки 229-238) не изменена (сигнатура и поведение те же); `ArtelCliTzFlagTest` зелёный без правок. `catalog.py` не тронут — вне зоны параллельной M1 (T094), как и требует SPEC «Не входит». |
| AC-1..AC-7 | OK | Все 7 критериев покрыты `tasks/T102/acceptance_tests/*.py` (9 тестов, AC-5 двумя примерами) — прогнаны заново, зелёные. Тесты проверяют не только текст отказа, но и отсутствие расхода номера/ветки/worktree (`_assert_no_task_spent`) — мутационно осмысленны, не структурные. |

## Замечания

Замечаний нет.

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest tests.test_new_argv_parsing -v` — 9 тестов, все зелёные.
- `python3 -m unittest discover -s tasks/T102/acceptance_tests -v` — 9 тестов (AC-1..AC-7, AC-5 двумя примерами), все зелёные.
- `python3 -m unittest tests.test_analyst_role.ArtelCliTzFlagTest -v` — 4 теста, все зелёные: контракт `_tz_arg`, на который опирается PLAN, не сломан.
- `python3 -m unittest discover -s tests` — 1185 тестов, 2 упавших:
  `test_agent_log.CmdRunLoggingTest.test_timeout_kills_process_and_journals` и
  `test_step_cost.CmdRunPartialCostTest.test_timeout_with_usage_events_charges_a_partial_token_sum`
  — оба ожидают таймаут шага 1800с, получают 2700с. Перепроверено: `git log
  main -1` показывает, что коммит `20afc92` («AGENT_TIMEOUT_SEC 1800 → 2700
  временно на стройку M1... вернуть после мержа T094») — уже верхушка main,
  а T094 (`git log main --oneline | grep T094`) в main ещё не влит —
  расхождение по-прежнему предсуществующее и вне зоны T102 (diff T102 не
  касается `orchestrator/runner.py`/`config.py`/`test_agent_log.py`/
  `test_step_cost.py`), не блокирует.
- `python3 scripts/guard.py --all` — `GUARD: ок (342 файлов)`.
- `python3 scripts/codebase_map.py` (регенерация) — `git diff
  docs/codebase-map.md` после регенерации пуст целиком, включая строку
  `built_at_sha` — карта уже полностью актуальна. Рабочее дерево возвращено
  в чистое состояние (`git checkout -- docs/codebase-map.md`, `git status
  --short` пуст).
- `git diff main...HEAD --stat` — 9 файлов вне зоны конфликта: `orchestrator/
  artel.py`, `tasks/T102/{PLAN,REVIEW,SPEC,TZ}.md`, три тестовых файла
  (`tests/test_new_argv_parsing.py`, `tasks/T102/acceptance_tests/
  test_new_{rejects_unrecognized_args,regression_existing_forms}.py`) и
  `docs/codebase-map.md`; `orchestrator/catalog.py` и прочая зона
  параллельной M1 (T094) не тронуты — соответствует PLAN «Влияние на
  систему» и SPEC «Не входит».
- Прочитан код `orchestrator/artel.py:229-330` (`_tz_arg`, `_NEW_USAGE`,
  `_parse_new_args`, `_cmd_new`, диспетчер `main()`) и `orchestrator/
  catalog.py:90-140` (`cmd_new`) заново; трассировкой вручную подтверждено:
  глобальная ветка `-h/--help` в `main()` (строка 294) не перехватывает
  `new -h`/`new --help` (`args[0] == "new"`, не `"-h"`/`"--help"`); порядок
  «валидация remainder → расход номера» не даёт `_parse_new_args` дойти до
  `store.peek_task_number`/создания worktree на отказном пути; `--tz`,
  оказавшийся первым токеном (начинается с `-`), тоже отказывает как
  нераспознанный, не падает и не создаёт задачу с именем `"--tz"`.
- Прочитан `tasks/T102/acceptance_tests/test_new_rejects_unrecognized_args.py`
  целиком — стенд (`templates/` + `fake_git` + `cmd_init`) корректно
  воспроизводит инциденты T097/T098/T099, тесты проверяют и текст отказа,
  и отсутствие побочных эффектов (`_assert_no_task_spent`).

## Предложения системе

- Инкрементальный diff пакета этой итерации был пуст (HEAD == sha
  прошлого вердикта) — не признак того, что ветка не менялась «зря», а
  честная ситуация «повторный прогон ревью без нового кода»; отработано
  по совету скила «пустой не значит без изменений»: перепроверено `git
  rev-parse HEAD` против sha прошлого REVIEW.md, совпадение подтверждено,
  тесты и guard прогнаны заново независимо, а не унаследованы из
  REVIEW.md итерации 1.
- Предсуществующий сбой `test_agent_log.py`/`test_step_cost.py` из-за
  временного `AGENT_TIMEOUT_SEC=2700` (коммит `20afc92`, класс «лимит»)
  всё ещё не снят: T094 в main пока не влит. Ревью T102 итерации 1 уже
  зафиксировало эту находку — стоит проверить статус T094 перед
  следующим ревью, которое унаследует ту же ветку main, чтобы не
  разбирать один и тот же «предсуществующий сбой» в третий раз.
