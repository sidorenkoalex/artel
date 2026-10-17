---
task: 01M55V7WB94C9BZXTXTTH83YWV
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/ci.py, orchestrator/ci_rerun.py, orchestrator/acceptance.py, orchestrator/fsm_merge_gate.py, orchestrator/github_adapter.py, tests/
budget_usd: 35
---

# SPEC: CI ветки внешнего проекта: запросы gh к репозиторию проекта

## Контекст
Первая задача на sled (01M55SKHZ293CCAK0N7T4H7ZMR) стоит в `verifying`:
ветка и коммит 9495860f есть в `origin` sled (PR sledproject/sled#17, CI
sled идёт), а пульт трижды пишет «голова ветки не в origin — GitHub не
нашёл коммит 9495860f (HTTP 422)». Причина — `orchestrator/ci.py`
спрашивает GitHub о коммите проекта у репозитория артели:
`gh api repos/{owner}/{repo}/…` разрешает `{owner}/{repo}` по `cwd` пульта
(`config.ROOT`, `ci.py:73`), а функции на пути `verifying`/`ci-rerun`/гейта
мержа не передают репозиторий проекта до `gh`. Вдобавок `ci.gh(repo=…)`
(`ci.py:39-80`) дописывает `--repo <url>`, которого `gh api` не принимает
(«unknown flag: --repo», проверено Оператором 18.10); для `gh api`
репозиторий задаётся переменной окружения `GH_REPO`. Пробел назван аудитом
D2 (Т-5); D2-2 (01M545EDTHS47HSB59AKC1EZ9C) закрыл токен, но не репозиторий.

## Требования

1. Каждый вызов `gh` из `orchestrator/ci.py` по задаче внешнего проекта
   адресован репозиторию проекта (`url` его записи `targets.yaml`) и несёт
   токен его слота `token_slot` (переменной `GH_TOKEN`, как сейчас у
   `ci.gh(repo=…)`):
   - для `gh api` — через переменную окружения `GH_REPO=<владелец>/<имя>`,
     без `--repo` в argv. Владелец и имя берутся из `url` проекта по
     правилу `gitcmd.url_key` (`gitcmd.py:44-46`): завершающие `/` и `.git`
     сняты, `GH_REPO` — два последних сегмента пути адреса;
   - для `gh run`/`gh pr` — флагом `--repo <url>`, как сейчас.

   `GH_REPO` ставится у задачи внешнего проекта и тогда, когда у его
   записи `targets.yaml` нет `token_slot` (токена нет, `gitcmd.py:133-135`):
   окружение такого вызова `gh api` всё равно несёт `GH_REPO` проекта,
   `GH_TOKEN` в нём не появляется.
2. У артели argv, окружение и `cwd` вызовов `gh` функций перечня
   требования 3 не меняются ни на байт относительно main. Сверх того у
   артели вызовы `ci.gh`, `head_sha`, `check_runs`, `run_list`,
   `find_run_id`, `trigger_rerun` идут прежней формой — без новых
   именованных аргументов (приём `ci._repo_kwargs`, `ci.py:83-95`: для
   клона артели и `None` — вызов без `repo`). Подмены этих функций в
   существующих тестах, написанные под прежнюю форму, не ломаются:
   `tests/test_invariants.py:326-328` (защищённый; `ci.gh` как
   `lambda *a:`, `ci.head_sha` как `lambda branch:`),
   `tests/test_ci_status.py:160` (`fake_gh(*args)`), `:367` (`check_runs`
   как `lambda sha:`), `:372` (`run_list` как `lambda branch:`), `:798`
   (`find_run_id` как `lambda sha:`), `tests/test_main_ci_line.py:62`
   (`gh(self, *args, timeout=None)`), `tests/test_merge_gate_ci_wait.py:82`
   (`trigger_rerun` как `lambda branch:`).
3. Репозиторий проекта доходит до всех функций CI на пути `verifying`,
   `ci-rerun`, автогейта приёмки и гейта мержа (проверка CI ветки и CI
   main после мержа) для задачи внешнего проекта. Перечень, сверенный по
   коду main (поиск вызовов `ci.<функция>(` по пакету пульта и скриптам):

   Функции `orchestrator/ci.py`, зовущие `gh` прямо или через другую
   функцию перечня:
   - `gh` (`:39`) — исполнитель; сейчас `--repo` дописывается и к `gh api`;
   - `check_runs_page` (`:118`) — `gh api …/commits/<sha>/check-runs`;
     `repo` принимает, но передаёт его как `--repo`;
   - `check_runs` (`:143`) — репозитория не принимает;
   - `run_list` (`:198`) — `gh run list`; `repo` принимает;
   - `_commit_workflow_runs` (`:371`) — `gh api …/actions/runs?head_sha=`;
     репозитория не принимает;
   - `_no_checks_by_branch` (`:674`) — зовёт `run_list(branch)` без
     репозитория;
   - `_inherited_from_main` (`:474`) — голову main читает в клоне проекта,
     но `failed_check_names(main_sha)` зовёт без репозитория;
   - `failed_check_names` (`:732`) — репозитория не принимает;
   - `verifying_status` (`:600`), `branch_status` (`:767`) — клон проекта
     передают только в `head_sha`;
   - `accepted_full_suite` (`:823`) — для внешнего проекта возвращает
     отказ до обращения к `gh` (`:829`); поведение остаётся;
   - `main_line_status` (`:1029`) и `_main_line_runs` (`:974`) —
     `check_runs`/`_commit_workflow_runs` без репозитория;
   - `find_run_id` (`:1136`) — `gh api …/actions/runs` и `check_runs` без
     репозитория;
   - `check_run_workflow_run` (`:1211`) — `gh api …/actions/jobs/<id>` без
     репозитория;
   - `trigger_rerun` (`:1235`) — `gh run rerun`/`gh run watch` без
     репозитория; голову ветки читает `head_sha(branch)` без клона
     проекта (клон артели).

   Вызывающие вне `ci.py`:
   - `orchestrator/ci_rerun.py`: `:224` `check_run_workflow_run(check_id)`,
     `:232` `trigger_rerun(branch, run_id=…)`, `:267` и `:279`
     `failed_check_names(…)`, `:298` `trigger_rerun(branch)` — без
     репозитория проекта; `:123`, `:158` `verifying_status(…, repo=…)` и
     `:244` `head_sha(…, repo=…)` — клон проекта уже передают;
   - `orchestrator/fsm_merge_gate.py`: `:290` `trigger_rerun(branch)` — без
     репозитория проекта; `:293`, `:341` `branch_status(…, repo=…)` и
     `:579`, `:618` `main_line_status(…, repo=ctx.path)` — клон передают
     (сверка CI main при этом идёт только для артели — ранний выход
     `repo_context.is_artel(ctx)`, `:571`, `:614`);
   - `orchestrator/acceptance.py`: `:2069` `head_sha`, `:2087`
     `accepted_full_suite`, `:2184` `verifying_status` — клон уже передают;
   - `orchestrator/github_adapter.py`: `:168`, `:193`, `:306` `ci.gh("pr",
     …, repo=<url>)` — `gh pr` с `--repo`, уже по требованию 1;
   - `orchestrator/fsm_advance.py:453` и `orchestrator/fsm_autogate.py:287`
     (вне зон) — `verifying_status(…, repo=workspace.task_repo(…))`, клон
     уже передают, правки не требуют;
   - `orchestrator/advance_gates/` функций `ci` не зовёт.

   В вызывающих модулях — только передача репозитория проекта, без
   изменения логики гейтов.
4. До правки кода argv, окружение и `cwd` вызовов `gh` артели для функций
   перечня требования 3 зафиксированы тестами.
5. Тесты детерминированы и без сети: подставной исполняемый `gh`,
   записывающий argv и переменные `GH_REPO`/`GH_TOKEN`; учебный внешний
   проект — запись `targets.yaml` со своим `url` и слотом токена.

## Критерии приёмки

AC-1. У артели argv, окружение (в том числе отсутствие `GH_REPO`) и `cwd`
вызовов `gh` функций перечня требования 3 — `verifying_status`,
`branch_status`, `accepted_full_suite`, `failed_check_names`,
`main_line_status`, `find_run_id`, `check_run_workflow_run`,
`trigger_rerun` — совпадают с main; подмены из требования 2
(`tests/test_invariants.py:326-328`, `tests/test_ci_status.py:160`, `:367`,
`:372`, `:798`, `tests/test_main_ci_line.py:62`,
`tests/test_merge_gate_ci_wait.py:82`) работают без правки.

AC-2. У учебного внешнего проекта, `url` которого оканчивается на `.git`
или `/` (например `https://github.com/<владелец>/<имя>.git`), каждый
вызов `gh api` функций перечня требования 3 получает в окружении
`GH_REPO=<владелец>/<имя>` (без `.git` и `/` в конце) и `GH_TOKEN` —
токен его слота, а в argv нет `--repo`. «Каждый вызов» проверяется в
сценариях, доходящих до всех мест `gh api`:
- красный путь `verifying_status`/`branch_status` со сверкой с main —
  `_inherited_from_main` → `failed_check_names(main_sha)` (`ci.py:660`,
  `:814`);
- проверки коммита с `check_suite.id` (или ссылкой на прогон) — запрос
  `_commit_workflow_runs` (`ci.py:379-383`);
- `find_run_id` при двух и более красных прогонах коммита — `gh api
  …/actions/runs` и `check_runs` (`ci.py:1162`, `:1180-1181`);
- `check_run_workflow_run` (`ci.py:1221`).

AC-3. У учебного внешнего проекта каждый вызов `gh run` (`run list`,
`run rerun`, `run watch`) и `gh pr` функций перечня требования 3 несёт в
argv `--repo <url>` проекта и `GH_TOKEN` — токен его слота. В том числе
в сценарии без проверок коммита — `_no_checks_by_branch` → `run_list`
(`ci.py:627`, `:638`, `:678`).

AC-4. `verifying_status` ветки задачи учебного внешнего проекта, у
головного коммита которой в репозитории проекта все проверки зелёные,
запрашивает проверки коммита у репозитория проекта и возвращает исход
`ci.VERIFYING_GREEN`; `note` не начинается с «голова ветки не в origin».

AC-5. `branch_status` ветки задачи учебного внешнего проекта с зелёными
проверками головного коммита в репозитории проекта запрашивает проверки у
репозитория проекта и возвращает зелёный исход (`True`).

AC-6. `trigger_rerun` ветки задачи учебного внешнего проекта — и с
заданным `run_id`, и с поиском прогона по головному коммиту — адресует
каждый вызов `gh` репозиторию проекта (поиск прогона — `gh api` с
`GH_REPO` проекта; `gh run rerun`/`gh run watch` — с `--repo <url>`
проекта), головной коммит читает в клоне проекта.

AC-7. Вызовы `check_run_workflow_run` и `failed_check_names` из
`ci-rerun` (`orchestrator/ci_rerun.py`) и `trigger_rerun` из
`ci-rerun` и гейта мержа (`orchestrator/fsm_merge_gate.py`) для задачи
учебного внешнего проекта адресуют `gh` репозиторию проекта.

AC-8. У учебного внешнего проекта без `token_slot` в записи
`targets.yaml` вызов `gh api` функций перечня требования 3 (например
`check_runs` из `verifying_status`) получает в окружении `GH_REPO` проекта,
`GH_TOKEN` в нём не выставлен пультом, в argv нет `--repo`.

## Оценка объёма и деление
Сработавшие сигналы: число файлов зоны ≥ 5 (шесть элементов зоны из ТЗ);
зона задевает механизм инварианта 19 `docs/invariants.md` (неизвестный
статус CI не зелёный — `ci.py`).

Обоснование монолита (решение — за Оператором на гейте SPEC): правка
одна по смыслу — адресация `gh` репозиторием проекта внутри `ci.py` и
передача этого репозитория из двух вызывающих (`ci_rerun.py`,
`fsm_merge_gate.py`, по одному–пяти местам вызова). Часть «только
`ci.py`» без передачи из вызывающих оставляет `ci-rerun` и ре-ран гейта
мержа бьющими в репозиторий артели — дефект ТЗ не закрыт; часть «только
вызывающие» без `ci.py` не имеет куда передать репозиторий. Тесты
фиксации поведения артели (требование 4) — сторож требования 2 этой же
правки: отдельной задачей они мержились бы без изменения, которое
сторожат. Логика гейтов не меняется, правки в `acceptance.py` и
`github_adapter.py` по перечню требования 3 могут не понадобиться вовсе.

## Не входит
- Мерж через `gh pr merge` для внешних проектов.
- Защита ветки sled.
- Задача sled 01M55SKHZ293CCAK0N7T4H7ZMR — продолжится после мержа этой.
- Изменение логики гейтов в вызывающих модулях, в том числе включение
  сверки CI main после мержа (`fsm_merge_gate._check_main_ci`/
  `_await_main_ci`) для внешнего проекта: она остаётся только для артели;
  здесь — лишь передача репозитория проекта.
- Правка `orchestrator/advance_gates/`, `orchestrator/gitcmd.py`,
  `orchestrator/repo_context.py`, `orchestrator/targets.py`,
  `targets.yaml`, `docs/backlog.md` — только чтение; потребность в правке
  вне зон — эскалация.
- Правка `orchestrator/fsm_advance.py` и `orchestrator/fsm_autogate.py`
  (вне зон): клон проекта в `verifying_status` они уже передают.
- Вызовы `ci.main_line_status` из `orchestrator/pin.py:86` и
  `orchestrator/doctor/main_ci.py:33` (артель, вне зон).

## Материалы
- ТЗ: `tasks/01M55V7WB94C9BZXTXTTH83YWV/TZ.md`.
- Ручная проверка Оператора 18.10: `GH_REPO=sledproject/sled gh api
  'repos/{owner}/{repo}'` → `sledproject/sled`; `gh api … --repo …` →
  «unknown flag: --repo».
- `url` учебного проекта в `targets.yaml` — вида
  `https://github.com/<владелец>/<имя>` (так записан sled, `targets.yaml:70`).
- Подмены, написанные под прежнюю форму вызова у артели (приём
  `ci._repo_kwargs`, `ci.py:83-95`), — перечень требования 2:
  `tests/test_invariants.py:326-328` (защищённый, `ci.gh` и `ci.head_sha`),
  `tests/test_ci_status.py:160`, `:367`, `:372`, `:798`,
  `tests/test_main_ci_line.py:62`, `tests/test_merge_gate_ci_wait.py:82`.
- Правило разбора адреса — `gitcmd.url_key` (`gitcmd.py:44-46`, только
  чтение): снимает завершающие `/` и `.git`.
- Тестов, утверждающих `--repo` у `gh api`, в `tests/` main нет (grep
  `--repo` по `tests/`): раздел «Меняемое поведение» не нужен.
