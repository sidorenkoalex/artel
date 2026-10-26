---
task: 01M5W27CY7K7NR9347NKD8F0NX
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: GitLab А0 — неподдержанный хостинг или гейт людей проекта: именованный отказ до первой задачи

## Фаза A — план
Таблица покрытия PLAN полна (требования 1–7 → шаги 1–3). PLAN дополнен
итерацией 3 (возврат с merge_gate: решение гейта SPEC «проверка в
`catalog.cmd_new`, чтобы её не обходил `epic draft promote`» не было
закреплено тестом). Код `orchestrator/` с итерации 1 не менялся; добавлен
только `tests/test_epic_draft_promote_unsupported_project.py`. Почему он
отдельным файлом, а не в долгоживущем файле задачи, обосновано: тот файл
под локом сумм, правка — только через `amend-tests`. «Влияние на систему»
соответствует diff: 6 файлов `orchestrator/` из зон SPEC + новый тест + карта;
защищённые пути не тронуты, существующие тесты не изменены (планка AC-8
зелёная).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `targets.py` — `SUPPORTED_FORGES`/`SUPPORTED_MERGE_GATES`, `unsupported_reason`; тексты причин дословно как в SPEC. |
| 2 | OK | `target`/`check` не тронуты; тесты, заводящие записи `gitlab`/`target-human`, не правлены. |
| 3 | OK | `catalog.py:759-761` — сразу за `_checked_target`, до `_new_refs`/клона/id. Новый тест подтверждает: путь `epic draft promote` (зовёт `cmd_new` в обход CLI-обёртки) тоже получает отказ. |
| 4 | OK | `runner._cmd_run` и `auto._cmd_auto` вызывают проверку первым действием под lease-обвязкой (обвязка git не зовёт). |
| 5 | OK | `fsm._cmd_approve` вызывает проверку первым действием, до таблицы состояний, — значит в любом состоянии. |
| 6 | OK | `doctor/cli.py` — `project_support_check` первой в цикле записей `all_checks`, артель в цикл входит. |
| 7 | OK | Для поддержанного проекта — `None`, путь прежний; AC-8 зелёный. |

## Замечания
Блокирующих и major нет. Новый тест: в докстринге есть сценарий и заявка
«Ловит мутацию: …» с наблюдаемыми расхождениями (git у шпиона, строки
`tasks`, состояние черновика, текст причины). Заявка проверена временной
мутацией (см. ниже). Долгоживущий тест он не повторяет: файл задачи
путь `epic draft promote` не проверяет.

Не влияет на вердикт (как и в итерации 1, в реестр не заведено):
- `orchestrator/runner.py:180` — в докстринге `refuse_unsupported_project`
  написано «до lease», но вызов стоит под lease. Неточен только текст.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: ни в итерации 1, ни в итерации 2 замечаний уровня minor и
выше не заведено.

## Вердикт
approved.

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_epic_draft_promote_unsupported_project.py tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_drafts.py tests/test_lease_run_task_command.py` — 37 passed, 14 subtests passed.
- `artel.py plank-run 01M5W27CY7K7NR9347NKD8F0NX` — 1 passed, код выхода pytest 0.
- Временная мутация: в `catalog.py:760` условие `unsupported is not None` заменено на `False` (проверка снята) → `tests/test_epic_draft_promote_unsupported_project.py`: 2 failed (оба параметра). Код возвращён, `git status --porcelain` пуст.
- `git grep -c test_epic_draft_promote_unsupported_project -- docs/codebase-map.md` → 8: новый файл в карте есть.

## Предложения системе
- Пакет ревью итерации 2 не смог определить базу инкрементального diff
  («sha предыдущего вердикта не распознан») и показал полный diff от main.
  Изменение итерации пришлось выделять сличением с PLAN. Стоит,
  чтобы журнал фиксации надёжно нёс sha вердикта.
