---
task: 01M5RWNJEZT6YA2VP7JK6F3RXS
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Скорость пульта, git 2 — одна отправка ссылки документов на команду пульта

## Подход
ADR-0021 п.3 (поправка 25.10.2026): внутри команды пульта (тело
`lease.run_locked`) коммит документов не отправляется сразу, а запоминается;
ссылка уходит в `origin` один раз при выходе и раньше — в точках досрочной
досылки. Вне команды — прежнее поведение байт в байт.

- `orchestrator/artifact_branch.py`: глобалы процесса `_area_depth` (глубина
  открытых областей) и `_unsent` (список пар (задача, репозиторий записи) в
  порядке первой записи, без повторов). Менеджер контекста
  `deferred_sends()` — `+1` к глубине, в `finally` `-1` и досылка всего
  набора на любом уровне вложенности; при летящем исключении тела сбой
  досылки печатается одной строкой в stderr, при нормальном выходе первое
  исключение досылки поднимается после попытки всех пар. Открытая
  `send_pending(task_id=None, repo=None) -> int` — досылка задачи /
  задач репозитория / всего набора; пары убираются из набора до `_send`;
  пустая выборка — возврат 0 без git и без БД. `_write` после удачного
  `update-ref`: при `_area_depth` — `_remember_unsent`, иначе `_send` как
  раньше. Репозиторий пары — тот, куда легла запись (`target=` до строки
  задачи в БД).
- `origin_sync_refusal`: первым действием `send_pending(task_id)`; если
  досылка была, прежняя ветка «расходится → `_send`» не повторяет отправку —
  отправок за вызов не больше одной, как прежде. Тексты отказов те же.
- `fetch_from_origin` — `send_pending(task_id)`, `fetch_all_from_origin(repo)`
  — `send_pending(repo=repo)`, оба до `git fetch`.
- `lease.run_locked`: `with artifact_branch.deferred_sends(): return body(sid)`
  внутри `try`, `release` в `finally` после досылки; при отказе `acquire`
  область не открывается.
- Досрочные досылки: `github_adapter.ensure_draft_mr` (перед
  `push -u`), `ensure_head_in_origin` (после сверки «голова уже в origin»),
  `fsm_merge_gate._sync_main_or_wait` (перед `push -u`) — задачи;
  `runner._spawn_and_wait` перед `spawn_agent` — весь набор;
  `snapshot.commit_closing` после записанного коммита закрытия — задачи;
  `fsm_merge_gate._wait_for_branch_ci_green`, `_await_main_ci` первым
  действием и `_full_suite_or_refuse` после «прогон нужен» — весь набор.
  `_ci_ready_or_wait` досылки не получает (ANSWER-1, решение 5).
- Импорт: `lease` и `github_adapter` импортируют `artifact_branch` на уровне
  модуля (цикла нет — `artifact_branch` их не тянет); в `runner` — локальный
  импорт по идиоме модуля.
- AC-7: коммит до запуска — подмена `checkpoint.main_copy_watch_start`
  (её `cmd_run` зовёт между подготовкой шага и `_spawn_and_wait`, внутри
  команды); наблюдение — по вызовам git FakeGit, без чтения набора.
- ANSWER-1, решение 6в: пустой набор — подмена `store.db` с
  `side_effect=AssertionError`, утверждение `assert_not_called`.

## Шаги
1. Область и досылка в `artifact_branch.py` + документация модуля, `_send`,
   `commit_files`; подключение в `lease.run_locked`.
2. Точки досрочной досылки (требование 3) в `artifact_branch.py`,
   `github_adapter.py`, `fsm_merge_gate.py`, `runner.py`, `snapshot.py`.
3. Правка `tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package`
   по мандату (ANSWER-1): два элемента (`remote get-url origin`, `push -q
   origin <ref>:<ref>`) перенесены в конец списка, фраза комментария о
   порядке отправки поправлена; прочее не тронуто.
4. Новый файл `tests/test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py`
   (pytest, 28 тестов: AC-1…AC-13 и критерии ANSWER-1 — `send_pending(repo=R)`
   / `send_pending(task_id)`, `fetch_all_from_origin`, порядок в
   `ensure_draft_mr` и `_sync_main_or_wait`, исключения 6а/6б/6в).
   Сторожа проверены временными мутациями — 13 мутаций кода, все красные.
5. `python3 scripts/codebase_map.py`, счёт вызовов git (ниже).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (а–д) | 1 |
| 2 | 1 |
| 3 (а–е) | 2 |
| 4 | 1 |
| 5 | 1 (неизменные части не тронуты, документация поправлена) |
| 6 | 4 |
| 7 | 5 |
| 8 | 3 |

## Счёт вызовов git

Тест `tests/test_merge_outcome_module.py` раздел `Ac5ProofMismatchTest`
(наследник `merge_outcome_gate::Ac5ProofMismatchTest` после сведения,
ANSWER-1 решение 7) — `test_ac5_other_base_key_or_mandate_runs_gate`.
Снято шпионом `subprocess.Popen.__init__` во временных копиях дерева (до —
`git archive 5f25936d`, после — рабочая копия ветки), `random.seed` 1 и 2 —
числа совпали; файл тестов не менялся.

| Счёт | до | после |
|---|---|---|
| всего | 1296 | 1284 |
| push | 43 | 37 |
| remote | 43 | 37 |

Сокращение отправок — 6 (ожидание исследования ~12). Разбор отправок
`refs/artifacts/*` (33 → 27) по месту вызова:
- `_append_passport_line` вне команды: 15 → 6 — песочница двигает задачу
  `store.set_state` вне `run_locked` (подготовка случая), эти 6 остаются
  немедленными по требованию 1в.
- `_commit_step_artifacts_to_branch`: 9 → 9 — коммиты шага, которые
  песочница делает вне команды.
- `_tests_writing_manifest_gate` 3 + `_commit_answer` 3 → выход из команды
  `cmd_advance` 6 и `cmd_answer` 3 — внутри команды коммиты собраны, но
  каждая команда даёт свою отправку.
- `commit_closing`: 3 → 3 — точка досылки 3д: коммит закрытия и строка
  паспорта `done` одной отправкой, одна на `approve` (до задачи строки
  паспорта `approve` отправлялись отдельно и входили в 15 выше).
Отправки кодовой ветки и `main` (10) не меняются.

## Влияние на систему
- Окно, когда документы локально впереди `origin`, теперь длится до конца
  команды. Читатели `origin` в команде получают досылку раньше: сверка
  (`origin_sync_refusal` — гейт мержа, `kill`), подтягивание, CI ветки
  (PLAN.md из `origin`, `scripts/plan_appendix_ci.py`) — до отправки кода,
  шаг роли — до запуска агента, долгие этапы гейта мержа, коммит закрытия.
- Процесс, умерший внутри команды, оставляет ссылку недосланной — как и
  прежде при сбое отправки: досылает следующая отправка вне/внутри команды,
  `origin_sync_refusal` и `doctor --fix` (`_fix_unsent_closed_refs`) — AC-12.
- Тесты, подменяющие `lease.run_locked` простой функцией, видят прежнюю
  немедленную отправку. Гейты, лимиты, guard не тронуты; существующие
  тесты не ослаблены, кроме правки по мандату ANSWER-1 (перестановка двух
  элементов, точное сравнение с порядком сохранено).
- Затронутые модули: 47 файлов `tests/` (artifact_branch, lease,
  github_adapter, snapshot, merge_gate, runner, review_package,
  merge_outcome, kill, docs_fetch, merge_reference…) — 538 passed;
  планка `plank-run` — см. записку.
- Откат — revert одного merge-коммита.

## Риски
- Долгие прогоны внутри `cmd_advance` (планка, полный набор, автогейт
  приёмки) досрочной досылки не получают — вне объёма (ANSWER-1, решение 8).
- Набор — в памяти процесса: в многопоточном коде без блокировки; пульт
  однопоточен.

## Предложения системе
- Шпион git для счёта вызовов в чужом дереве упирается в сторожа
  `conftest.py` (смотрит `sys.argv` процесса): `pytest.main` из сценария
  отказывает, пока `sys.argv` не подменён. Команды пульта «счёт вызовов git
  на тесте до/после» нет — требования 7 подобных задач каждый раз пишут
  такой сценарий заново.
