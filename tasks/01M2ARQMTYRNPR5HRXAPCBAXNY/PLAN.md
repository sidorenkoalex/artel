---
task: 01M2ARQMTYRNPR5HRXAPCBAXNY
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Гейт свежести — документные коммиты main без подтяжки

## Подход
`pull.evaluate` уже вычисляет `behind` (SPEC 01M2ARQMTYRNPR5HRXAPCBAXNY,
контекст) через `gitcmd.commits_behind(branch, base=base, repo=repo_path)`
ДО того, как заводится worktree (`workspace.ensure`). Между этой точкой и
началом `git merge` добавляется новая проверка: если ВСЕ файлы диффа main
от точки расхождения (`merge-base(branch, base)`) до `base` документные
(`scripts.ci_push_class.is_doc_path`) и не пересекаются с диффом ветки от
той же точки расхождения до `branch` — переход коротко замыкает на
`Fresh()` с журналом, минуя worktree/merge/приёмку целиком (требование 1,
AC-1/AC-4).

Правка (итерация 2, после отказа гейта зон): первая попытка сдачи несла
`merge_base(a, b, repo=None)` и `repo=` у `diff_names` в
`orchestrator/gitcmd.py` — гейт зон отклонил переход байт-в-байт («дифф
трогает файлы вне заявленных zones и COMMON_ZONES: orchestrator/
gitcmd.py»), т.к. `zones` SPEC несёт только `orchestrator/pull.py,
scripts/ci_push_class.py, tests/`, а `gitcmd.py` не входит и не покрыт
`config.COMMON_ZONES`. `orchestrator/gitcmd.py` возвращён к виду на базе
сверки (`git checkout <база> -- orchestrator/gitcmd.py`); вместо новых
публичных примитивов там `pull.py` несёт две свои функции (`_git_in`,
`_diff_names_in`), собранные из уже ПУБЛИЧНЫХ `gitcmd.git`/`gitcmd.
in_repo` (существовали и раньше, правки не требуют) — тот же выбор «`git`
в `config.ROOT` при `repo_path is None`, иначе `in_repo(repo_path, ...)`»,
что нёс бы `repo=` в `gitcmd.py`, просто без изменения самого модуля вне
зоны задачи.

Для этого:
- `scripts/ci_push_class.py`: `_is_doc_path` переименован в `is_doc_path`
  (публичное имя, требование 4/AC-6) — единственный вызывающий код внутри
  файла (`classify`) переключён на новое имя, `_DOC_PATTERN` не менялся.
- `orchestrator/pull.py`: `_git_in(repo_path, *args)` — `gitcmd.git(*args)`
  при `repo_path is None`, иначе `gitcmd.in_repo(repo_path, *args)`;
  `_diff_names_in(repo_path, a, b)` — тот же разбор вывода, что несёт
  существующий `gitcmd.diff_names`, поверх `_git_in`. Новая чистая функция
  `_doc_only_main_advance` считает `merge-base` через `_git_in`, дифф main
  и дифф ветки через `_diff_names_in`; `None` на любом из трёх запросов
  (git не ответил) или недокументный/пересекающийся файл — `None`
  (прежнее поведение, AC-2); иначе — список файлов main для журнала.
  `evaluate()` зовёт её сразу после `if not behind: return Fresh()`, до
  создания worktree — самой функции безразлично, какая из трёх точек
  сверки её вызвала (`fsm._pull_main_or_escalate` не меняется, AC-4
  закрывается тем, что все три точки уже идут через одну `evaluate`).

Оба недокументированных случая (git не ответил на `merge-base`/`diff`) —
fail-closed на ПРЕЖНЕЕ поведение (подтяжка), не на новое «пропустить»:
расхождение с ADR-0002 было бы обратным — молчаливый пропуск подтяжки на
сбое git скрывал бы реальное расхождение веток.

Bare origin в тестах не заводится: `pull.evaluate` получает `base` уже
готовым sha параметром (`origin_main_sha`), сам не читает `origin/*` —
существующий стенд `tests/test_pull.py::PullEvaluateTest` тоже обходится
без него (fictional sha + мок `commits_behind`). Для сценариев (а)-(в),
которым нужны настоящие `merge-base`/`diff --name-only`, новый класс
использует `tests/sandbox.py::RealGitSandbox` (реальный git, локальные
ветки main/task, без origin) — тот же уровень стенда, каким уже пользуются
другие тесты этого файла для реального git (`RealGitSandbox`), только
`origin_main_sha` подставляется sha реального коммита на локальном main,
а не фиктивной строкой.

## Шаги
1. `scripts/ci_push_class.py`: публичное имя `is_doc_path`.
2. `orchestrator/pull.py`: `_git_in`/`_diff_names_in` (свои, без правки
   `gitcmd.py` — вне зоны задачи) + `_doc_only_main_advance` + подключение
   в `evaluate`, журнал «свежесть: N документных коммитов main без
   подтяжки».
3. `tests/test_pull.py`: новый класс на `RealGitSandbox` со сценариями
   (а)-(в) (AC-7..AC-9) + юнит на `ci_push_class.is_doc_path` (сценарий
   (г), AC-10); прогон существующих тестов файла и `tests/
   test_ci_push_class.py`/`test_merge_gate_ci_wait.py` без ослабления.
4. `python3 scripts/codebase_map.py` тем же коммитом (правка `*.py` в
   `orchestrator/`/`scripts/`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 2 |
| 3 | 2 (общая `evaluate`, без правок `fsm.py`/`fsm_merge_gate.py`) |
| 4 | 1 |
| 5 | 3 |

## Влияние на систему
Новая ветка кода трогает только `orchestrator/pull.py` — единственную
точку, которую зовут все три сверки свежести (`fsm._pull_main_or_
escalate`); `fsm.py`/`fsm_merge_gate.py`/`orchestrator/gitcmd.py` не
меняются (последний — вне зоны задачи, требование итерации 2 после
отказа гейта зон, см. «Подход»), поведение `merge_gate -> done` по
зелёному CI (AC-5) не затронуто — сверка CI идёт отдельным путём
(`ci.py`), эта задача её не касается. `_git_in`/`_diff_names_in` в
`pull.py` — новые ПРИВАТНЫЕ функции этого модуля поверх уже публичных
`gitcmd.git`/`gitcmd.in_repo`, ничьё внешнее поведение не меняют.
`is_doc_path` — переименование единственного приватного имени внутри
одного файла без внешних потребителей (grep подтвердил: `_is_doc_path` не
упоминается ни в одном другом файле репозитория) — не incompatible
изменение. Откат — два файла (`pull.py`, `ci_push_class.py`) возвращаются
к прежнему виду одним `git revert`, тесты `tests/test_pull.py`/`tests/
test_ci_push_class.py` откатываются тем же коммитом.

## Риски
Fail-closed на неответивший git (`merge-base`/`diff --name-only` вернули
`None`) — минус в том, что временный сбой git на этой конкретной проверке
не пропускает документные коммиты main (обычная подтяжка всё равно
проходит, просто не короче), что безопаснее ложного пропуска.

## Предложения системе
(пусто)
