---
task: 01M568XFYM68EYHH0C16Y7D7F0
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: kill задачи внешнего проекта — уборка ветки и PR в его репозитории

## Фаза A: план
- Таблица покрытия PLAN.md охватывает требования 1–9; у каждого есть ссылка на шаг и AC.
- Шаг один, размером с MR: одна функция в одном модуле плюс уже зафиксированный долгоживущий файл тестов. Обоснование монолита из SPEC подходит.
- Подход совпадает с решениями Оператора в SPEC: новая функция `cleanup_project_remote` вызывается только из `_cmd_kill` при `won`, `cleanup_killed_task` её не зовёт. Предел — `-c http.lowSpeed*` без правки `gitcmd.py`, журнал — тот же `store.journal(..., "уборка", ...)`. Конфликта с архитектурой нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/cleanup.py:534-535` — `cleanup_project_remote` вызывается после `cleanup_killed_task` только при `won`, независимо от её исхода. В `cleanup_killed_task` и в `fsm._cleanup_divided_parent` вызова нет (AC-1, AC-8, AC-9 а/б) |
| 2 | OK | `_close_project_pr`: `ci.gh("pr","close",branch,"--comment","задача ликвидирована в пульте: <id>", repo=ctx.remote)`. `ctx.remote` — это `url` записи (`repo_context.py:94`). `gh` вызывается только при `_forge_of(target) == "github"`, признак `draft_mr_created` не читается |
| 3 | OK | `_delete_origin_branch`: `gitcmd.in_repo(repo, "-c","http.lowSpeedLimit=1","-c",f"http.lowSpeedTime={config.GH_TIMEOUT_SEC}","push","origin","--delete",branch)`. Предел читается в момент вызова, `gitcmd.py` не тронут |
| 4 | OK | Сначала PR, затем всегда удаление ветки. Сбой PR даёт только заметку и пуш не отменяет (AC-3) |
| 5 | OK | Пуш адресует только ветку по имени, `refs/artifacts` не трогаются (AC-1) |
| 6 | OK | `ci.gh` и `gitcmd.git` никогда не возвращают `None` и не бросают исключений (`ci.py` ловит TimeoutExpired/OSError, `gitcmd.py:181,188`). «не ответил» пишется только по префиксу «gh молчал дольше» или по curl 28 / «Operation too slow», иначе «отказ: …». Одна запись журнала через «; », заметки начинаются с «PR …» и «ветка origin …» |
| 7 | OK | `repo_context.is_artel(t)` → ранний выход без вызовов и без записи журнала (AC-7) |
| 8 | OK | `cleanup.py:211` — `_base_of(repo)` вместо `config.MAIN_BRANCH`. `drop_task_dir` не тронут |
| 9 | OK | Долгоживущий файл задачи: bare-`origin`, подставной HTTP-хостинг на `git http-backend`, подставной `gh` в `PATH`. Сеть не нужна |

Целостность: diff трогает только `orchestrator/cleanup.py` и сгенерированную `docs/codebase-map.md`. Других `tests/`, гейтов и guard'ов в diff нет, существующие утверждения не меняются. Секция «Влияние на систему» соответствует diff. Откат — revert merge-коммита.

Тесты: у всех методов долгоживущего файла есть заявки «Ловит мутацию», и каждая называет наблюдаемое расхождение: ветку в `origin`, порядок строк журнала событий, слова в причине, время `kill`. Свойства долгоживущие и закрыты в `tests/`. Своих повторов тестов разработчик не добавлял. Планки нет (`acceptance_tests/` пуст), так что пометок manual/skip тоже нет.

## Замечания

- minor — orchestrator/cleanup.py:287-289 — `repo_context.unresolved_reason(target)` вычисляется дважды для двух заметок. Можно вычислить один раз в переменную. На поведение не влияет, это вопрос вкуса.
- minor — orchestrator/cleanup.py:224 — `_PUSH_SILENT_MARKS` опираются на текст curl в stderr git. Риск того, что другая сборка git/curl назовёт предел иначе, честно записан в «Рисках» PLAN. Если это случится, изменится только формулировка причины («отказ» вместо «не ответил»), `kill` от этого не зависнет. Править не нужно.

## Реестр замечаний

Записей нет: замечаний уровня blocker или major нет, а минорные выше вписаны для сведения и исправления не ждут.

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py tests/test_kill_cleanup.py tests/test_division_parent_cleanup.py tests/test_kill_live_cycle_refusal.py` — 45 passed, 2 subtests passed за 67 с. Это все 11 методов AC-1…AC-9 долгоживущего файла, включая AC-6 с подставным HTTP-хостингом и пределом 2 с.
- `artel.py plank-run 01M568XFYM68EYHH0C16Y7D7F0` — отказ «планки нет: … нет файлов test_*.py». Совпадает с PLAN: зафиксированная планка пуста.
- `git diff --stat 96972e61...HEAD -- docs/codebase-map.md` — карта обновлена тем же коммитом кода, 10d95cc9. Перегенерировать её для сверки не удалось: составную команду отклонил предел прав.
- Точечное чтение кода, чтобы проверить требование 6 (нет ли `None` или исключения на пути уборки): `gitcmd.git` (`:162-188`) всегда возвращает `CompletedProcess`; `ci.gh` (`ci.py:39-83`) ловит TimeoutExpired/OSError и отказ токена; `repo_context.resolve` даёт `remote=entry["url"]` (`:94`) — это `--repo` записи для AC-2.
- CI коммита 10d95cc9 зелёный (16 проверок, данные пакета).

## Предложения системе
- `plank-run` при пустой планке отвечает «отказ». Для задачи, у которой все AC закрыты долгоживущим файлом, это штатная ситуация, и слово «отказ» в «Проверено исполнением» читается как сбой. Стоит отличать «планки нет по замыслу» от отказа.
