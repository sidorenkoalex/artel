---
task: 01M462QACEH29RPRD2RZHGHQFM
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Полный прогон тестов из шага роли — команда `suite-run`

## Фаза A — план

- Таблица покрытия полна: требования 1–19 разнесены по шагам 1–7.
- Шаги размером с MR (константы; узел `acceptance`; новый модуль с проводкой; миссия; тесты; карта; приложение) — не микрооперации.
- Подход не расходится с архитектурой: прогон идёт через узел `acceptance.run_full_suite`, параметры по умолчанию оставляют argv гейта прежним, хозяйство команды лежит в `config.LOGS`. Приложение к `skills/coding-standards.md` применяется: `git apply --check` на дереве ветки даёт код 0 (проверено).
- «Влияние на систему» сходится с diff: тронуты `acceptance.py`, `artel.py`, `config.py`, `role_prompt.py`, новые `suite_run.py` и `tests/test_suite_run.py`, плюс карта. Существующие тесты не менялись.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `run_full_suite(wt, command=профиль, …)`, `-n FULL_SUITE_WORKERS`. Argv гейта прежний (`GateArgvTest`) |
| 2 | OK | `_profile_command`/`_is_pytest` |
| 3 | OK | `env` без `ARTEL_ROLE` при запуске фонового процесса, `_pytest_env` у прогона |
| 4 | OK | `Popen(start_new_session=True)`, номер и лог в выводе, проверка идущего прогона в `_running` |
| 5 | OK | `_wait`, `_wait_minutes` (0…9) |
| 6 | OK | `_run_full_suite_to_log`: убивается группа процессов, итог — префикс таймаута и числа по строкам хода |
| 7 | OK | `saved_failures`/`save_failures` по sha, `_remember_gate_failures` в `full_suite`, прогон базы в `_base_copy` |
| 8 | OK | сохраняется только `finished` (есть итоговая строка pytest). Иначе — «база не посчитана» |
| 9 | реализовано не так | перечень перезаписывается каждым прогоном, но в него попадают строки, которые не являются id тестов (R1-F1) |
| 10 | реализовано не так | после R1-F1 `--failed` передаёт pytest мусорные аргументы: повтор не прогоняет ни одного теста и обнуляет перечень |
| 11 | реализовано не так | число и состав «новых на ветке» искажены мусорными записями (R1-F1) |
| 12 | OK | `_group_lines`, `_clip`, хвост «и ещё N групп, M тестов» |
| 13 | OK, с оговоркой | замок `O_EXCL`, мёртвый pid не держит, снятие в `finally`. Гонка двух одновременных запусков — R1-F2 (minor) |
| 14 | OK | белый список роли, пишет только под `config.LOGS` |
| 15 | OK | `_base_copy`: `finally` с `worktree remove --force`, `rmtree`, `prune` |
| 16 | OK | `suite_run_note` в миссии developer |
| 17 | OK | приложение к PLAN, `git apply --check` = 0 |
| 18 | OK | карта несёт `suite_run`. Регенерация `scripts/codebase_map.py` даёт расхождение только в `built_at_sha` |
| 19 | OK | долгоживущий файл и `tests/test_suite_run.py` несут заявки «Ловит мутацию». Повторов долгоживущего нет |

## Замечания

- major — `orchestrator/acceptance.py:776` (`_FAILED_ENTRY`/`failed_entries`), `orchestrator/suite_run.py:262` (`parse`: `failures.update(acceptance.failed_entries(output))`), `orchestrator/suite_run.py:416` (`_run`: запись `failed.json`), `orchestrator/acceptance.py:851` (`_remember_gate_failures`) — сам дефект: регулярка `^(?:FAILED|ERROR) (.+?)(?: - (.*))?$` ищет совпадения по ВСЕМУ выводу, а не только в блоке «short test summary info». Захваченный лог упавшего теста печатается форматом pytest по умолчанию (`ERROR    m:test_x.py:3 boom here`), и эта строка становится «упавшим тестом» `m:test_x.py:3 boom here`. Так же сработает любой захваченный stdout, начинающийся с `FAILED `/`ERROR `. Сценарий проверен исполнением: тест пишет `logging.error(...)` и падает, прогон `-vv -n 1`. `parse` даёт `failed=1` (по сводке), а в `failures` три записи: `fake/line`, `m:test_x.py:3 boom here` и настоящий `tests/test_x.py::test_a`. Последствия: (1) отчёт называет 3 «новых на ветке» при одном упавшем, группы выдуманы (требование 11); (2) `failed.json` несёт мусор, и `suite-run --failed` передаёт его pytest аргументами. Проверено: pytest с аргументами `tests/test_x.py::test_a` и `m:test_x.py:3 boom here` выходит кодом 5, «no tests ran», 0 items — настоящий упавший тоже не прогоняется. Затем `failed.json` перезаписан пустым перечнем, и следующий `--failed` отказывает «упавших нет». Повтор упавших ломается ровно у тех падений, которые пишут ERROR-лог, а для набора пульта это частый случай (требования 9–10); (3) итог базы, который сохраняет гейт или прогон базы, несёт те же мусорные id. Это безвредно для деления, но засоряет итог. Предложение: разбирать `FAILED`/`ERROR` только внутри блока между заголовком `short test summary info` и итоговой строкой pytest. Добавить в `tests/test_suite_run.py` тест: вывод с захваченной строкой лога `ERROR    …` и строкой stdout `FAILED …` вне сводки даёт ровно упавшие из сводки, с заявкой «Ловит мутацию: разбор по всему выводу — в перечне появляется id `m:…`».
- minor — `orchestrator/suite_run.py:592-610` (`cmd_suite_run`) и `:430-438` (`background`) — сам дефект: замок проверяется в CLI неатомарно (`_live_lock_holder`), а берётся уже в фоновом процессе. Два одновременных запуска (например, роли двух задач) оба проходят проверку и оба печатают «запущен фоном», код 0. Затем второй фоновый процесс не получает замок и пишет в `result.json` отказ. Последствие: требование 13 ждёт немедленного отказа с держателем, а здесь отказ виден только при `--wait`. Отказ при этом не теряется и не тихий, поэтому minor. Предложение: брать замок в CLI до `Popen` и передавать его дочернему процессу (переписать pid в замке), либо явно оговорить это окно в PLAN/риски.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | orchestrator/acceptance.py:776; orchestrator/suite_run.py:262, 416; orchestrator/acceptance.py:851 | `failed_entries` ищет `FAILED`/`ERROR` по всему выводу; захваченный лог `ERROR    …` и stdout становятся «упавшими тестами» | отчёт завышает «новые на ветке»; `--failed` передаёт pytest мусор: 0 тестов, перечень обнулён; итог базы засорён | разбирать только блок «short test summary info» до итоговой строки; тест в `tests/test_suite_run.py` с захваченным логом и stdout. Разработчик: новый `acceptance.short_summary_block` — текст от последнего заголовка «short test summary info» до следующего разделителя `=== … ===`; `failed_entries` читает только его (один разборщик на `parse`, `_run`/`failed.json` и `_remember_gate_failures`). Тот же класс в строках хода: `suite_run._progress` читает только текст до первой секции отчёта (`FAILURES` и далее), иначе захваченное `x::y PASSED` считалось выполненным тестом. Тест `ParseTest::test_captured_output_outside_summary_is_not_a_failure`, обе мутации проверены — красный |
| R1-F2 | fixed | orchestrator/suite_run.py:592-610, 430-438 | замок проверяется в CLI неатомарно, а берётся в фоновом процессе | при одновременном запуске двух задач второй вызов печатает «запущен» вместо немедленного отказа (требование 13) | брать замок до `Popen` и передавать его дочернему процессу, либо оговорить окно в PLAN. Разработчик: `cmd_suite_run` берёт замок `O_EXCL` (`_acquire_lock`) до заведения лога и `Popen`, занятый — немедленный отказ с id и pid держателя; после `Popen` замок переписан на pid фонового процесса (`_hand_lock`), сбой запуска снимает замок. Фоновый процесс принимает замок своей задачи и номера (`_adopt_lock`), иначе берёт сам. Тесты `LockTest::test_command_takes_lock_before_background_start`, `::test_background_adopts_handed_lock`, мутации проверены — красные |

## Вердикт

changes_requested — исправить R1-F1 (major): разбор упавших ограничить блоком «short test summary info» и добавить юнит-тест на захваченный ERROR-лог и stdout. R1-F2 (minor) — исправить или обоснованно отклонить.

## Проверено исполнением

- Опыт R1-F1: временный проект, тест с `logging.getLogger("m").error(...)`, `print("FAILED fake/line - …")` и `assert False`; `python3 -m pytest tests -p no:cacheprovider -n 1 -p xdist -vv`. `acceptance.failed_entries` вернул `[('fake/line', …), ('m:test_x.py:3 boom here', ''), ('tests/test_x.py::test_a', 'assert False')]`, а `suite_run.parse` — `failed=1` и три записи в `failures`.
- Опыт последствия для `--failed`: pytest с аргументами `tests/test_x.py::test_a` и `m:test_x.py:3 boom here` — код 5, «no tests ran», `parse` → `красный прогон 0 0 [] finished=False`.
- `python3 -m pytest tests/test_suite_run.py -p no:cacheprovider -p timeout -o timeout=120` — 11 passed.
- `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py` двумя прогонами по классам: 16 passed (99 с) + 10 passed, 6 subtests (84 с) — все 26 зелёные.
- `tests/test_acceptance.py tests/test_approve_acceptance_full_suite.py tests/test_artel_role_restricted_commands.py tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py` — 41 passed.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без `built_at_sha` — расхождений нет (карта свежая, изменение откачено).
- `git apply --check` приложения из PLAN.md — код 0.
- `plank-run` не запускался: планки `acceptance_tests/` у задачи нет (PLAN).

## Предложения системе

- Класс «разбор вывода pytest регуляркой по всему тексту»: строки `FAILED`/`ERROR` в захваченном логе и stdout неотличимы от сводки. Стоит один общий разборщик блока «short test summary info» в `acceptance.py`, без новых регулярок в каждом потребителе.
