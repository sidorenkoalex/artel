---
task: 01M5FGJW4RBN9C9P48Q8MDHJX1
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Ветка задачи task/… удаляется из origin после мержа

## Подход
Новая функция `cleanup.cleanup_merged_remote(conn, task_id, branch,
merged_sha)` (`orchestrator/cleanup.py`) рядом с уборкой kill. Тело —
закрытый помощник, возвращающий (исход, подсказки); обёртка перехватывает
любое исключение (приём `_rebuild_core_reference`), пишет одну запись
журнала «уборка» и печатает исход строкой с отступом, затем подсказки
(в журнал подсказки не идут). Пустое имя ветки — немедленный выход до
любых вызовов git.

Чтение головы — `gitcmd.in_repo(<клон>, "-c", "http.lowSpeedLimit=1",
"-c", "http.lowSpeedTime=<GH_TIMEOUT_SEC>", "ls-remote", "origin",
"refs/heads/<branch>")` с тремя исходами `remote_ref_state` (`gitcmd.py`
не меняется). Входимость головы — `gitcmd.is_ancestor(head, merged_sha,
repo=<клон>)`. Удаление — общий примитив `_delete_origin_branch`,
расширенный необязательным `lease`: при нём аргументы `push
--force-with-lease=refs/heads/<b>:<sha> origin --delete refs/heads/<b>`,
без него — прежние аргументы kill побайтно. Ответ `None` примитив
разбирает как «оставлено — git не ответил» (единственная смена исхода
kill). Клон — `workspace.task_repo(task_id)`, как у kill (у внешнего
проекта его `origin` и токен — тем же путём `in_repo`).

`fsm_merge_gate._cleanup_merged_task` получает `merged_sha` и зовёт новую
уборку последней — после worktree и локальной ветки; `_cmd_approve_merge_gate`
передаёт ей `final_sha`. Вызов стоит там же, где и был — после `"ok"`
push и `done`, поэтому отказы гейта и `"moved"` до уборки не доходят.

## Шаги
1. `orchestrator/cleanup.py`: `_delete_origin_branch(repo, branch, lease=None)`
   с разбором `None`; `cleanup_merged_remote` + помощники чтения головы и
   подсказок.
2. `orchestrator/fsm_merge_gate.py`: параметр `merged_sha` у
   `_cleanup_merged_task`, передача `final_sha`.
3. `docs/retention.md`: абзац в разделе «Ветки `task/*` пульта».
4. Карта `scripts/codebase_map.py`; прогон долгоживущего файла, планки,
   тестов затронутых модулей, `suite-run`.
5. (Ревью, итерация 1, R1-F1) Сторож проводки в `tests/`:
   `tests/test_fsm_merge_gate_remote_branch_cleanup.py` — тело гейта
   `_cmd_approve_merge_gate` у внешнего проекта и у артели (приём
   `tests/test_fsm_merge_gate_done_snapshot.py`): ветка задачи
   опубликована в bare-`origin`; `("done",)` → ветки нет, одна запись
   «уборка» «удалена»; `_push_merged_main` → `"moved"` → ветка на месте,
   записи нет. Проверено временными мутациями: вызов уборки удалён из
   `_cleanup_merged_task` → 2 теста `done` красные; уборка перенесена до
   проверки исхода push → все 4 красные; код возвращён.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1 |
| 3 | 1 |
| 4 | 2 |
| 5 | 1 |
| 6 | 3 |
| 7 | 2 |
| 8 | 4 (долгоживущий файл test_author — свойства уборки), 5 (сторож проводки гейта мержа в `tests/`) |

## Влияние на систему
Kill: аргументы пуша прежние; меняется только исход на `None` от
`in_repo` (было `AttributeError`) — требование SPEC. Гейт мержа: новая
запись журнала «уборка» после `done`; порядок шагов и условия не
меняются, исключения уборки перехвачены — мерж, `_await_main_ci`,
`_rebuild_core_reference` идут как раньше. Существующие тесты, доводящие
гейт до `done`, получат лишнюю запись/строки вывода; сверено полным
прогоном. Откат — revert merge-коммита задачи.

## Риски
- Шаг мержа удлиняется на два сетевых вызова под мьютексом мержа —
  ограничены `http.lowSpeedTime`.
- Удаление head-ветки на GitHub может перевести открытый PR в
  «closed», а не «merged» — сверка на первом мерже (оговорено в
  `docs/retention.md`).

## Предложения системе
