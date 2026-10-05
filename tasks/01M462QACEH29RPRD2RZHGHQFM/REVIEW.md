---
task: 01M462QACEH29RPRD2RZHGHQFM
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Полный прогон тестов из шага роли — команда `suite-run`

## Фаза A — план

- Таблица покрытия по-прежнему полна: требования 1–19 разнесены по шагам 1–7. Итерация 2 дописала в «Подход» передачу замка (`_acquire_lock` → `_hand_lock` → `_adopt_lock`) и разбор только блока сводки. Это сходится с diff.
- «Влияние на систему» сходится с инкрементальным diff: `acceptance.py` (`short_summary_block`, `failed_entries`), `suite_run.py` (замок, `_progress`), `tests/test_suite_run.py`. Существующие тесты не ослаблены. В `GateSaveTest.SUMMARY` своего же нового файла задачи фикстура приведена к настоящему выводу pytest: это файл этой ветки, не тест базы, и ожидание не ослаблено.
- Приложение к `skills/coding-standards.md` не менялось. На прошлой итерации `git apply --check` дал код 0.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | без изменений с итерации 1. Argv гейта прежний |
| 2 | OK | |
| 3 | OK | |
| 4 | OK | |
| 5 | OK | |
| 6 | OK | |
| 7 | OK | `_remember_gate_failures` берёт перечень из того же `failed_entries` и теперь читает только блок сводки |
| 8 | OK | |
| 9 | OK | R1-F1 закрыт: в `failed.json` попадают только id из блока «short test summary info» и строки хода до секций отчёта |
| 10 | OK | после R1-F1 `--failed` получает только настоящие id (опыт ниже) |
| 11 | OK | после R1-F1 «новые на ветке» не завышаются захваченным выводом |
| 12 | OK | |
| 13 | OK | R1-F2 закрыт. Замок берёт команда (`O_EXCL`) до лога и `Popen` и передаёт фоновому процессу. Второй запуск отказывает сразу. Гонку parent/child проверил: `_hand_lock(run_no, pid CLI)` идёт до `Popen`, поэтому `_adopt_lock` дочернего процесса всегда видит свою задачу и номер. Поздний `_hand_lock(proc.pid)` родителя пишет то же значение. Если дочерний процесс уже успел завершиться, остаётся замок мёртвого pid, а он прогон не держит |
| 14 | OK | |
| 15 | OK | |
| 16 | OK | |
| 17 | OK | |
| 18 | OK | карта свежая: после регенерации расхождений вне `built_at_sha` нет |
| 19 | OK | у трёх новых тестов есть заявки «Ловит мутацию», мутации проверены (ниже). Повторов долгоживущего файла нет |

## Замечания

Нет blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/acceptance.py:784-805; orchestrator/suite_run.py:78, 256-262 | `failed_entries` искал `FAILED`/`ERROR` по всему выводу | мусорные «упавшие», сломанный `--failed` | Исправлено. `short_summary_block` берёт текст от последнего заголовка сводки до следующего разделителя, `_progress` читает только строки до первой секции отчёта. Опыт итерации 1 повторён в режимах `-vv -n 1` и `-q`: перечень равен ровно упавшим из сводки. Тест `ParseTest::test_captured_output_outside_summary_is_not_a_failure` краснеет на обеих мутациях |
| R1-F2 | accepted | orchestrator/suite_run.py:155-204, 636-664 | замок брался только фоновым процессом | второй одновременный запуск печатал «запущен» | Исправлено. Замок атомарно берёт команда, передаёт его через `_hand_lock` и `_adopt_lock`, сбой запуска снимает замок (`except BaseException`). Тесты `LockTest::test_command_takes_lock_before_background_start` и `::test_background_adopts_handed_lock` зелёные, мутация «фоновый процесс берёт замок заново» даёт красный. Долгоживущий `LockTest::test_ac21` зелёный |

## Вердикт

approved — R1-F1 и R1-F2 исправлены и подтверждены исполнением, новых замечаний нет.

## Проверено исполнением

- Опыт R1-F1 повторён на коде ветки. Временный проект: тест с `logging.error`, `print("FAILED fake/line - x")`, `print("tests/fake.py::test_q PASSED")` и `assert False`, плюс тест с двухстрочным `ValueError` и зелёный тест.
  - `-vv -n 1 -p xdist`: `failed_entries` вернул ровно `[test_a 'assert False', test_b 'ValueError: first']`, `parse` → `passed=1 failed=2 finished=True` без мусорных id.
  - `-q` (вывод гейта, итоговая строка без `=`): результат тот же.
- `python3 -m pytest tests/test_suite_run.py tests/test_acceptance.py tests/test_approve_acceptance_full_suite.py tests/test_artel_role_restricted_commands.py tests/test_fsm_autogate.py -p no:cacheprovider -p timeout -o timeout=120` — 75 passed, 4 subtests.
- Временные мутации через `mock.patch` без правки кода:
  - `short_summary_block = lambda o: o` → `ParseTest::test_captured_output_outside_summary_is_not_a_failure` RED;
  - `_REPORT_SECTION`, который ничего не находит → тот же тест RED;
  - `_adopt_lock = _acquire_lock` → `LockTest::test_background_adopts_handed_lock` RED.
- Долгоживущий файл задачи, классы `LockTest`, `FailedRerunTest`, `BaseComparisonTest` и `BackgroundTest::test_ac7` — 8 passed (49 с).
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без `built_at_sha` — расхождений нет, изменение откачено, дерево чистое.
- `artel.py plank-run 01M462QACEH29RPRD2RZHGHQFM` — «планки нет», pytest не запускался (ожидаемо по PLAN).

## Предложения системе

- Поддерживаю предложение PLAN: `acceptance.failed_test_lines` (выжимка журнала гейтов) остаётся в классе R1-F1. Его стоит перевести на `short_summary_block` отдельной задачей.
