---
task: 01M5RWNJEZT6YA2VP7JK6F3RXS
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Скорость пульта, git 2 — одна отправка ссылки документов на команду пульта

## Фаза A — план
- Таблица покрытия PLAN полна: требования 1–8 → шаги 1–5.
- Шаги — единицы размера MR (механизм+подключение, точки досылки, правка теста по мандату, новый файл тестов, карта и счёт).
- Подход согласован с ADR-0021 п.3 (поправка 25.10) и ANSWER-1: `_ci_ready_or_wait` без досылки (решение 5), наследник `Ac5ProofMismatchTest` — `tests/test_merge_outcome_module.py` (решение 7), долгие прогоны `cmd_advance` вне объёма (решение 8).
- Требование 7 / AC-14: счёт до/после есть (всего 1296→1284, push 43→37, remote 43→37). Сокращение ровно 6 — разбор по точкам не обязателен, но дан (паспорт вне команды, коммиты шага вне команды, отправка на каждую команду `cmd_advance`/`cmd_answer`, `commit_closing`).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1а | OK | `artifact_branch.deferred_sends()`, `send_pending(task_id=None, repo=None)` |
| 1б | OK | `_write`: при `_area_depth` — `_remember_unsent`; пара (задача, repo записи), без повторов, порядок первой записи |
| 1в | OK | вне области `_send` сразу; `test_outside_area_sends_each_commit_right_after_update_ref` сверяет `update-ref` → `remote get-url` → `push` (AC-13) |
| 1г | OK | досылка в `finally` на любом уровне; вложенный `run_locked` досылает весь набор (AC-2) |
| 1д | OK | `lease.run_locked`: `with deferred_sends()` внутри `try`, `release` в `finally` после; при отказе `acquire` — возврат до `try` |
| 2 | OK | `_take_unsent` убирает пары до `_send`; пустой набор — 0 без git/БД (`test_empty_set_exit_no_git_no_db`, `store.db` подменена `AssertionError`) |
| 3а | OK | `origin_sync_refusal`: `send_pending` первым; `and not sent` — не больше одной отправки за вызов |
| 3б | OK | обе функции досылают до `git fetch`; оба вызывающих `fetch_all_from_origin` (`docs_fetch.py:135`, `workspace.py:140`) передают тот же путь клона, что `repo_for_target` → фильтр `repo` совпадает с repo пары |
| 3в | OK | `ensure_draft_mr` перед `push -u`; `ensure_head_in_origin` после сверки «уже в origin»; `_sync_main_or_wait` перед `push -u` |
| 3г | OK | `runner._spawn_and_wait` перед `spawn_agent` — весь набор |
| 3д | OK | `snapshot.commit_closing` после проверки sha |
| 3е | OK | `_wait_for_branch_ci_green`, `_await_main_ci` первым действием; `_full_suite_or_refuse` после `needed`; `_ci_ready_or_wait` без досылки по ANSWER-1 п.5 |
| 4 | OK | `quiet=body_failed`: при летящем исключении — строка в stderr, иначе первое исключение после всех пар |
| 5 | OK | `push`, `_attempt_push`, `_classify_push_failure`, `_journal_push_outcome`, `_origin_configured`, `write_commit`, `commit_files` не тронуты (только докстринг); `snapshot.py:294`, `doctor/artifact_branches.py:137` не тронуты; докстринги модуля и `_send` обновлены |
| 6 | OK | новый pytest-файл, 28 тестов, у каждого «Ловит мутацию:» с наблюдаемым расхождением |
| 7 | OK | счёт в PLAN |
| 8 | OK | `test_review_package.py`: перенос ровно двух элементов в конец списка и фраза комментария — совпадает с мандатом ANSWER-1; число/состав элементов и точное сравнение с порядком сохранены, прочее в файле не тронуто |

Зоны: diff только в файлах из `zones` SPEC; защищённые пути не тронуты. Карта кодовой базы: `python3 scripts/codebase_map.py` даёт расхождение только в `built_at_sha` — не дефект.

## Замечания

Блокирующих и major нет. Наблюдения без замечаний:
- `tests/…_one_push_per_command.py::test_spawn_agent_sees_docs_sent` наблюдает отправку по вызовам FakeGit, а не равенство голов в origin (как просит ANSWER-1 п.4): у песочницы `CmdRunReviewPackageTest` настоящего origin нет, и отправка между коммитом и `spawn_agent` — ближайшее наблюдаемое; чтения закрытого набора нет. Временная мутация (убрана досылка в `runner`) тест краснит.
- `_send_pairs` ловит `BaseException`, т.е. `KeyboardInterrupt` во время досылки откладывается до попытки остальных пар — так требует п.4 SPEC.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py "tests/test_review_package.py::CmdRunReviewPackageTest"` — 38 passed.
- `artel.py plank-run 01M5RWNJEZT6YA2VP7JK6F3RXS` — 26 passed, код выхода pytest 0.
- Временные мутации (код восстановлен `git checkout`, `git status` чист):
  - убрана `send_pending(task_id)` в `snapshot.commit_closing` → `test_commit_closing_sends_before_return` FAILED;
  - убрано `and not sent` в `origin_sync_refusal` → `test_sync_refusal_no_second_push_when_pending_send_failed` FAILED;
  - убрана `send_pending()` в `runner._spawn_and_wait` → `test_spawn_agent_sees_docs_sent` FAILED.
- `python3 scripts/codebase_map.py` → diff карты только в строке `built_at_sha` (откатил).

## Предложения системе
- Для задач «счёт вызовов git до/после» (требование 7) пригодилась бы команда пульта со шпионом процессов — разработчик пишет такой сценарий каждый раз заново (подтверждаю наблюдение PLAN).
