---
task: 01M568XFYM68EYHH0C16Y7D7F0
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: kill задачи внешнего проекта — уборка ветки и PR в его репозитории

## Подход
Одна новая функция `cleanup.cleanup_project_remote(conn, task_id, branch)` в
`orchestrator/cleanup.py`. Её зовёт только `_cmd_kill` и только при `won`
(переход в `killed` выигран из нетерминального состояния), после
`cleanup_killed_task` и независимо от её исхода. `cleanup_killed_task` её не
зовёт, поэтому деление на гейте SPEC (`fsm._cleanup_divided_parent`) и
повторный `kill` задачи в `done`/`killed` в репозиторий проекта не ходят
(AC-9 а, б).

Внутри функции:
- задача артели (`repo_context.is_artel(t)`) или ветка не записана — выход без
  действий и без записи журнала (требование 7);
- контекст проекта не разрешён — обе заметки «оставлено» с причиной
  `repo_context.unresolved_reason`;
- `forge: github` — `_close_project_pr`: `ci.gh("pr", "close", <ветка>,
  "--comment", "задача ликвидирована в пульте: <id>", repo=<url записи>)`
  (токен слота и предел `GH_TIMEOUT_SEC` даёт `ci.gh`); не GitHub — `gh` не
  зовётся;
- затем всегда `_delete_origin_branch`: `gitcmd.in_repo(<клон>, "-c",
  "http.lowSpeedLimit=1", "-c", f"http.lowSpeedTime={config.GH_TIMEOUT_SEC}",
  "push", "origin", "--delete", <ветка>)`. Предел читается из
  `config.GH_TIMEOUT_SEC` в момент вызова; `gitcmd._hosting_project` пропускает
  пары `-c` и узнаёт хостинговый `push`, так что токен слота (или отказ при
  пустом слоте) идёт штатным механизмом, `gitcmd.py` не правится;
- ни одна ветка не бросает исключения: `ci.gh` и `gitcmd.git` превращают
  сбой в ненулевой `CompletedProcess`, `targets.TargetsError` ловит
  `_forge_of`.

Заметки — одна запись `store.journal(conn, id, "orchestrator", "уборка", …)`
через «; »: «PR <ветка>: закрыт» / «PR <ветка>: оставлено — <причина>»,
«ветка origin <ветка>: удалена» / «ветка origin <ветка>: оставлено —
<причина>». Причина «… не ответил за N с (…)» — только при пределе: у `gh`
stderr `ci.gh` начинается с «gh молчал дольше», у пуша stderr несёт «Operation
too slow»/«curl 28» (срабатывание `http.lowSpeedTime`); иначе «отказ: <текст
ошибки>».

Текст «перейди на … и повтори kill» в `cleanup_killed_task` называет
`_base_of(repo)` — базу проекта задачи (у артели это по-прежнему
`config.MAIN_BRANCH`). `drop_task_dir` не тронут.

`refs/artifacts/<id>` не удаляются: пуш адресует только `refs/heads`-ветку
задачи по имени.

## Шаги
1. `orchestrator/cleanup.py`: `cleanup_project_remote` и помощники, вызов из
   `_cmd_kill` при `won`, база проекта в тексте отказа уборки; регенерация
   `docs/codebase-map.md`. Тесты — долгоживущий файл задачи
   `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py`
   (test_author), соседние тесты kill.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (`cleanup_project_remote` из `_cmd_kill` при `won`, после локальной уборки и независимо от неё; AC-1, AC-8) |
| 2 | 1 (`_close_project_pr` через `ci.gh(..., repo=url)` только для `forge: github`; AC-2, AC-9 в) |
| 3 | 1 (`_delete_origin_branch` через `gitcmd.in_repo` с `-c http.lowSpeed*`; AC-1, AC-6) |
| 4 | 1 (PR раньше пуша, сбой PR не отменяет пуш; AC-2, AC-3) |
| 5 | 1 (удаляется только `refs/heads`-ветка; AC-1) |
| 6 | 1 (заметки «оставлено» с причиной «отказ: …»/«… не ответил …», без исключений; AC-3…AC-6) |
| 7 | 1 (выход для артели; AC-7) |
| 8 | 1 (`_base_of(repo)` в тексте; AC-8) |
| 9 | 1 (долгоживущий файл задачи: bare-origin, подставной HTTP-хостинг, подставной `gh`) |

Прогоны: долгоживущий файл задачи — 11 passed; `tests/test_kill_cleanup.py`,
`test_kill_live_cycle_refusal.py`, `test_division_parent_cleanup.py`,
`test_multitarget_invariants.py`, `test_01m545edths47hsb59akc1ez9c_project_token.py`,
`test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`,
`test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`,
`test_task_id_prefix_regression.py`, `test_cas_set_state.py`,
`test_01m42pencs26d0656x8fr7dfa7_project_area.py`,
`test_snapshot_closing_outcome.py` — 144 passed. Планки задачи нет
(acceptance_tests/ пуст, записка test_author). Полный набор —
`artel.py suite-run` №1: зелёный, прошло 5654, упало 0, пропущено 2.

Своих тестов в `tests/` не добавлял: все свойства SPEC покрыты долгоживущим
файлом задачи (AC-1…AC-9).

## Влияние на систему
- Затронут только путь `kill` с выигранным переходом в `killed` задачи
  внешнего проекта: новые сетевые вызовы (`gh pr close`, `git push --delete`)
  к хостингу проекта, каждый с пределом `config.GH_TIMEOUT_SEC` — `kill` в
  худшем случае дольше на 2 × 60 с, но не висит без конца.
- Kill switch не ослаблен: уборка в репозитории проекта идёт после смены
  состояния, коммита закрытия и локальной уборки и не может их отменить
  (любой сбой — заметка «оставлено»).
- Задачи артели, деление на гейте SPEC, повторный kill — прежние вызовы
  (AC-7, AC-9 а, б). Гейты, лимиты, guard'ы, существующие тесты не меняются.
  `ci.py`, `gitcmd.py`, `fsm.py`, `github_adapter.py` не правлены.
- Механизм токена хостинга проекта (`hosting_token`) используется штатно: в
  процессе роли и при пустом слоте — отказ без запуска `gh`/`git`.
- Откат — revert одного merge-коммита задачи.

## Риски
- Признаки молчания пуша («Operation too slow», «curl 28») — текст curl в
  stderr git; другая сборка git/curl может назвать предел иначе — тогда
  заметка будет «отказ: …» вместо «… не ответил …» (kill от этого не
  зависает, меняется только формулировка причины).
- Для origin по ssh `http.lowSpeed*` не действует — предел пуша работает
  только для HTTP(S)-хостинга (SPEC выбрал именно эту форму предела).

## Предложения системе
- `tests/sandbox.py` не несёт подставного HTTP-хостинга git: test_author
  написал его прямо в файле задачи (`GitHttpHosting`) — кандидат на вынос в
  песочницу для будущих тестов сетевых пределов.
- `pytest -n` в шаге разработчика падает «node down» у всех воркеров —
  локальный прогон затронутых модулей идёт только последовательно.
