---
task: 01M1R5B33CC7E6BZK085XV3ZCX
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: B2 ТЗ-1: репозиторный контекст target для git/gh-слоя

## Фаза A — гейт плана

PLAN.md прирос двумя разделами со времени итерации 1: «Возврат — DNS-имя
в тестах» (правка литералов `example.invalid`/`https://x` на `localhost`
в `tests/test_repo_context.py`/`tests/test_fsm_merge_gate_done_snapshot.py`
— чинит защищённый инвариант `NoNetworkAddressesInTestsTest`, код
`orchestrator/` не тронут) и «Возврат — REVIEW.md итерация 1: R1-F1
(major) и R1-F2 (minor)» — точечный фикс `_drop_scratch_worktree` и
докстринги `test_repo_context.py`, ровно по тексту замечаний. Оба
раздела заявляют конкретные правки, конкретные файлы/строки и конкретные
прогоны — подход не пересмотрен, доводка не выходит за рамки того, что
просило REVIEW.md итерации 1. Зоны не расширены сверх SPEC ∪ ANSWER-2:
`orchestrator/fsm_merge_gate.py` — в зоне SPEC, `tests/` — тестовая зона
без ограничения `zones:` (то же обоснование, что уже приняла итерация 1).
Фаза A пройдена без новых замечаний.

## Инкрементальный diff пакета — сверено вручную

Пакет отдал пустой инкрементальный diff (sha «предыдущего вердикта»
caec7a9c совпал с HEAD ветки) — по правилу скила («пустой не значит без
изменений») проверил руками: `caec7a9c` — это САМ коммит с фиксами
R1-F1/R1-F2 (сообщение «замечания ревью итерации 1 закрыты —
R1-F1/R1-F2»), HEAD ветки. Разобрал его `git show --stat`/`git show --
<файл>` вместо пакетного diff — см. «Соответствие SPEC» и «Проверено
исполнением» ниже.

## Соответствие SPEC

Все 6 требований и 17 AC оценены полностью в REVIEW.md итерации 1
(таблица со всеми пятью «OK» и одним «реализовано не полностью» —
именно тот пункт, который закрывает эта итерация). Для итерации 2 важен
только пункт 4 (изменённый код):

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (единый узел контекста) | OK | без изменений с итерации 1. |
| 2 (`ci.gh` с контекстом) | OK | без изменений с итерации 1. |
| 3 (сверка/подтяжка по контексту) | OK | без изменений с итерации 1. |
| 4 (merge/карта/RETRO по контексту) | OK | R1-F1 закрыт: `_drop_scratch_worktree(ctx, repo)` (`orchestrator/fsm_merge_gate.py:79-90`) зовёт `repo_context.git(ctx, "worktree", "remove", "--force", str(repo))` — дерегистрация идёт в репозитории-владельце worktree (self — байт-в-байт `gitcmd.git`, внешний target — `-C ctx.path`), `ctx` протащен через все 5 вызовов (`_handle_merge_conflict` x2, `_guard_task_root_or_refuse`, `_publish_merge_artifacts`, `_cmd_approve_merge_gate`). |
| 5 (гейт ёмкости + diff ревью-пакета) | OK | без изменений с итерации 1. |
| 6 (сквозной тест на двух репозиториях) | OK | без изменений с итерации 1 (39/39 приёмочных методов зелёные, включая AC-12/AC-13, которые эта правка не тронула поведенчески для self). |

## Замечания

(нет новых — правка закрывает ровно то, что просила итерация 1)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/fsm_merge_gate.py:79-90 (+ вызовы 125,140,324,493,610) | `_drop_scratch_worktree` теперь принимает `ctx: repo_context.RepoContext` и дерегистрирует scratch-worktree через `repo_context.git(ctx, "worktree", "remove", "--force", str(repo))` в репозитории-владельце. Верифицировано лично: (1) прочитан `git show caec7a9c -- orchestrator/fsm_merge_gate.py` — правка byte-точно совпадает с описанной в реестре; (2) прогнан новый тест `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py` (3 метода, реальный git, два репозитория) — зелёный; (3) мутационно: временно вернул голую `gitcmd.git(...)` вместо `repo_context.git(ctx, ...)` — `test_cleanup_deregisters_worktree_in_the_target_clone` покраснел с ровно тем же `AssertionError` (worktree осталась в `target_repo`), два других метода теста остались зелёными как и ожидает докстринг; откатил мутацию, `git status` чист. Регресс реально закрыт. | — (закрыто) | принято |
| R1-F2 | accepted | tests/test_repo_context.py (все 9 методов) | всем 9 методам добавлен докстринг `Ловит мутацию: …` с конкретным сценарием (перепутанные поля `RepoContext`, порядок чтения targets.yaml, исключение вместо `None`-деградации, self/external ветвление `path_or_none`/`repo_context.git`). Прочитал diff (`git show caec7a9c -- tests/test_repo_context.py`) — каждый докстринг называет конкретную мутацию и наблюдаемое свойство, не пересказывает имя метода; прогнан весь модуль — 9/9 зелёные. Конвенция test-authoring выполнена. | — (закрыто) | принято |

## Вердикт

approved — оба замечания итерации 1 (R1-F1 major, R1-F2 minor) закрыты
по существу и подтверждены проверкой исполнением (не пересказом diff):
регресс-тест на двух настоящих git-репозиториях воспроизводит и ловит
именно тот дефект, который был найден эмпирически в прошлой итерации, и
мутационный откат фикса красит ровно этот тест. Новых замечаний нет.
Реестр закрыт целиком (обе записи `accepted`).

## Проверено исполнением

- `git show --stat caec7a9c` и `git show caec7a9c -- orchestrator/fsm_merge_gate.py tests/test_repo_context.py tests/test_fsm_merge_gate_scratch_worktree_cleanup.py tests/test_guard_task_root_subdirectory.py` — сверил фикс R1-F1/R1-F2 построчно с текстом реестра REVIEW.md итерации 1 (инкрементальный diff пакета был пуст — sha предыдущего вердикта совпал с HEAD, разобрал коммит вручную по правилу скила).
- `python3 -m unittest tests.test_fsm_merge_gate_scratch_worktree_cleanup tests.test_repo_context tests.test_guard_task_root_subdirectory -v` — 19/19 OK.
- Мутационная проверка R1-F1 лично: временно заменил `repo_context.git(ctx, "worktree", "remove", "--force", str(repo))` на `gitcmd.git("worktree", "remove", "--force", str(repo))` в `orchestrator/fsm_merge_gate.py`, прогнал `python3 -m unittest tests.test_fsm_merge_gate_scratch_worktree_cleanup -v` — `test_cleanup_deregisters_worktree_in_the_target_clone` упал (`AssertionError`, worktree осталась в `target_repo`), остальные 2 метода зелёные; откатил (`git checkout -- orchestrator/fsm_merge_gate.py`), `git status --short orchestrator/fsm_merge_gate.py` — пусто.
- `python3 -m pytest tasks/01M1R5B33CC7E6BZK085XV3ZCX/acceptance_tests -o timeout=90 -q` — 39 passed (все 17 AC).
- `python3 -m unittest` по полному списку 28 модулей из «Проверено исполнением» REVIEW.md итерации 1 (+ новый `tests.test_fsm_merge_gate_scratch_worktree_cleanup`, обновлённый `tests.test_guard_task_root_subdirectory`) — Ran 743 tests, OK.
- `python3 scripts/codebase_map.py` на голове ветки, `git diff docs/codebase-map.md` без строки `built_at_sha` — пусто (карта содержательно свежая); локальный регенерированный diff отброшен (`git checkout -- docs/codebase-map.md`), рабочее дерево чистое.
- Зоны: `git show --stat caec7a9c` — изменены только `orchestrator/fsm_merge_gate.py` (зона SPEC), `tests/*` (тестовая зона), `docs/codebase-map.md` (автогенерируемый) — расхождений с SPEC ∪ ANSWER-2 нет.
- CI коммита caec7a9c (HEAD ветки) — зелёный, 14 проверок (данные пакета).

## Предложения системе

- Инкрементальный diff ревью-пакета второй раз подряд (после T082/T087,
  уже отмеченных в скиле) пришёл пустым при sha предыдущего вердикта,
  совпавшем с HEAD — в этот раз причина третья: коммит-фикс R1-F1/R1-F2
  сам стал новым HEAD И одновременно попал в поле «sha предыдущего
  вердикта» (видимо, вычислено от коммита, где REVIEW.md итерации 1
  получил статус, который случайно совпал с этим же коммитом в этой
  ветке). Стоит рассмотреть более надёжный якорь (например, sha из
  `git log --diff-filter=M -- tasks/<id>/REVIEW.md`, а не эвристику
  «последний коммит с этим статусом»).
