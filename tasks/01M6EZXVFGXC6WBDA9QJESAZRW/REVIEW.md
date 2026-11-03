---
task: 01M6EZXVFGXC6WBDA9QJESAZRW
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: GitLab Б2.3-1: отказ при сбое вместо пропуска

## Фаза A — план
- Таблица покрытия PLAN полна (требования 1–13 → шаги 1–4); добавлен раздел «Закрытие
  ревью, итерация 1» с описью «мутация → сторож в `tests/`» — пробел итерации 1 закрыт
  на уровне плана.
- «Влияние на систему» совпадает с инкрементальным diff: тронут только
  `tests/test_fail_closed_on_read_failure.py` (+187/−3), код не менялся.

## Соответствие SPEC

Код с итерации 1 не менялся (инкрементальный diff `13889418..cc4c20bc` — только тесты),
вердикты по требованиям итерации 1 в силе; ниже отмечено, что изменилось.

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | сторож в `tests/`: `test_merge_gate_unread_entry_refuses_external[target-human/operator]` — `("stopped",)`, одна запись `PEOPLE_REFUSED_ACTION` с `ENTRY_UNREAD_DETAIL`, поля задачи прежние, нет push/merge |
| 2 | OK | без изменений с итерации 1 (`test_url_destination_unread_entries_is_not_artel`) |
| 3 | OK | без изменений |
| 4 | OK | без изменений |
| 5 | OK | сторож: `test_push_plan_in_flight_db_error_external_refused` (`IN_FLIGHT_UNCHECKED`, push не зван) |
| 6 | OK | сторож: `test_in_repo_db_error_refuses_external_not_artel` — внешний отказ `DB_UNREAD`, артель отправляет |
| 7 | OK | сторож: `test_in_flight_limit_refusal_carries_code_from_git_and_in_repo` — код `IN_FLIGHT_REFUSAL` и из `in_repo`, и из `git` |
| 8 | OK | без изменений |
| 9 | OK | без изменений |
| 10 | OK | без изменений, долгоживущий файл лока |
| 11 | OK | новых сравнений с литералом нет (diff — только тесты) |
| 12 | OK | новые тесты подменяют сбой в названной точке: `_people_entry_record`, `store.last_task_step_of` (счёт предела), первый вызов `store.project_tasks` (`_fail_first`), не постоянной подменой загрузчика |
| 13 | OK | без изменений |

Изменённые существующие тесты: в diff только сигнатура помощника `_task` (добавлен
необязательный `branch`, умолчание прежнее) — утверждения существующих тестов не тронуты.
Докстринги новых тестов несут сценарий и «Ловит мутацию: …» с наблюдаемым расхождением
(исключение/отсутствие записи отказа; код 1 вместо `IN_FLIGHT_REFUSAL`; шпион видит `git push`).

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_fail_closed_on_read_failure.py; места: orchestrator/fsm_merge_gate.py:1521, orchestrator/gitcmd.py:1023, :1016, :905 | долгоживущие свойства требований 1, 5, 6, 7 сторожила только планка | после мержа регрессия открыла бы обход незаметно для CI | принято: четыре сторожа добавлены; ревьювер повторил мутации A–D — каждая роняет ровно свой тест (A — 2 failed, B/C/D — по 1 failed из 20) |

## Вердикт
approved: R1-F1 закрыта, сторожа проверены временными мутациями; планка зелёная.

## Проверено исполнением
- `python3 -m pytest tests/test_fail_closed_on_read_failure.py -p no:cacheprovider -q` — 20 passed.
- Временные мутации (скрипт в каталоге документов, по одной, с `git checkout` файла после
  каждой; `git status` после — чистый), прогон `tests/test_fail_closed_on_read_failure.py`:
  A `fsm_merge_gate.py:1521` `except targets.TargetsError` → `except ZeroDivisionError` —
  2 failed (`test_merge_gate_unread_entry_refuses_external[target-human]`, `[operator]`);
  B `gitcmd.py:1023` `plan.code = IN_FLIGHT_REFUSAL` → `pass` — 1 failed
  (`test_in_flight_limit_refusal_carries_code_from_git_and_in_repo`);
  C `gitcmd.py:1016` `if project != config.DEFAULT_TARGET:` → `if False:` — 1 failed
  (`test_push_plan_in_flight_db_error_external_refused`);
  D `gitcmd.py:905` `if project == config.DEFAULT_TARGET:` → `if True:` — 1 failed
  (`test_in_repo_db_error_refuses_external_not_artel`).
- `artel.py plank-run 01M6EZXVFGXC6WBDA9QJESAZRW` — 42 passed, код выхода 0.
- `python3 -m pytest tests/test_mr_delivery_units.py tests/test_01m6ezxvfgxc6wbda9qjesazrw_hosting_registry.py tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py -p no:cacheprovider -q` — 50 passed, 8 subtests.
- `python3 scripts/codebase_map.py` — расхождение с закоммиченной картой только в
  `built_at_sha` (не дефект); регенерация откачена.

## Предложения системе
- Опись «мутация → сторож в `tests/`» в PLAN (как в «Закрытие ревью, итерация 1» этой
  задачи) сделала повторную проверку механической — стоит сделать её частью
  templates/PLAN.md для шага «тесты в `tests/`».
