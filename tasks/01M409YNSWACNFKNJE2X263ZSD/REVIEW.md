---
task: 01M409YNSWACNFKNJE2X263ZSD
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: ADR-0021, этап 1 (б2) — упразднение репозитория фиксации и ссылка внешнего проекта

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–6 → шаги 1–9; AC-1…AC-11 привязаны.
- Шаги проверяемые, размер MR большой (41 файл), но обоснован ANSWER-1 п.1 (вариант (а) — все читатели на один узел); diff без карты ~206 КБ < потолка 262 144.
- Подход (`artifact_branch.repo_for_target`/`task_repo` + узел чтения) не конфликтует с архитектурой: для артели вызовы `gitcmd` байт-в-байт без `repo=`.
- Перечень изменённых существующих тестов в PLAN есть, с основаниями (ANSWER-1 п.2, ANSWER-2 п.1).
- Приложение к `docs/invariants.md`: `git apply --check` прогнан мной — проходит.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_fix_external`, `_read_external`, `init_artifact_repo`, `artifact_repo_has_no_remote`, `check_remote_empty` удалены; grep по `orchestrator/` и `scripts/` — ни определений, ни вызовов. `fixation.fix/read` — голова ссылки (AC-1/AC-2/AC-3 зелёные). |
| 2 | OK | `artifact_branch._write/_send/_attempt_push` работают на `task_repo`; без клона — `_NO_REPO`, git не спрашивается (нет утечки `git -C` вверх в git пульта). AC-4/AC-5 зелёные. |
| 3 | OK | `origin_sync_refusal`, `send_pending`, `doctor.check_artifact_ref_sync` и `_fix_unsent_closed_refs` — по репозиторию задачи, группами по репозиторию. AC-6/AC-7/AC-8 зелёные, включая «посторонняя ссылка пульта не решает». |
| 4 | OK | Гейт мержа, `kill`, лок планки, мандат ANSWER — та же сверка, меняется только репозиторий. Снятые проверки `doctor` (`remote-empty`, `recovery-clean`, `recovery-fsck`) — по ANSWER-1 п.3. |
| 5 | OK | Приложение к инварианту 25 без «грязной копии»; `git apply --check` — проходит; `tests/test_invariants.py` правки не требует (на него ссылаются неизменённые классы). |
| 6 | OK | Долгоживущий файл задачи покрывает AC-1, AC-2, AC-4–AC-9; узел чтения — `tests/test_artifact_branch_read_node.py`, у каждого метода заявка «Ловит мутацию». Изменённые утверждения — только в методах из мандатов ANSWER-1 п.2 и ANSWER-2 п.1. |

## Замечания

Blocker/major не найдено.

Наблюдение (minor, в реестр не заведено, вердикт не блокирует) — `orchestrator/fixation.py:223` —
`refixate_after_rejected_transition` зовёт `gitcmd.commit_committer_dates(entry_sha, current_sha)`
без `repo=`: для внешней задачи `entry_sha`/`current_sha` — коммиты ссылки в клоне проекта, в
git пульта их нет → `None` → перефиксации нет. Это читатель, который ANSWER-1 п.1 велел перевести,
но его пропустили. Исход fail-closed (инцидент целостности, как при постороннем коммите). Практически путь
почти недостижим: все пишущие места пульта перефиксируют ссылку сами
(`store.record_fixation`). Внешних задач в базе 0. Предложение — при этапе 2 ADR-0021 (клон проекта
заводит пульт) передать `repo=artifact_branch.task_repo(task_id)` (параметр `repo` у
`commit_committer_dates` уже есть).

Проверка утверждений тестов против base (Фаза B, п.6):
- `tests/test_doctor.py` — `recovery-clean` в двух методах снято, метод `test_dirty_working_copy…` удалён — мандат ANSWER-1 п.2/п.3; добавлено `assertTrue(sha)`. `test_sha_mismatch_raises_an_incident_alert` не тронут, `commit_artifact()` в нём зовётся без аргументов — смена сигнатуры (`task_id` первым) его не сужает.
- `tests/test_fsm_merge_gate_done_snapshot.py` — `pult_origin → target_origin`, `is_ancestor` в клоне проекта — мандат ANSWER-2 п.1, прямо требуется AC-5.
- `tests/test_git_fixation.py` — удалены три класса (6 методов) — мандат ANSWER-1 п.2; остальное — только `setUp` (`make_project_repo`).
- Прочие файлы (`test_artifact_materialization`, `test_guard_task_root_subdirectory`, `test_checkpoint_external_step_artifacts`, `test_multitarget_invariants`, `test_branch_freshness_gate`, `test_split_assessment_merge_gate`, `test_artifact_ref_sync`, `test_doctor_artifact_branch_sync`) — подготовка данных и `repo=` в помощниках чтения, утверждения те же. Сужения данных под неизменным утверждением не нашёл. Исключение — `ExternalWorkspaceIsolationTest::test_external_target_cwd_is_its_workspace` (утверждение `is_dir()` теперь выполняется всегда); принято ANSWER-2 п.2 и отражено в PLAN «Риски».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: blocker/major не найдено, прошлых итераций нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p timeout -o timeout=300` по планке задачи (`tasks/01M409YNSWACNFKNJE2X263ZSD/acceptance_tests`, скопирована в рабочий каталог), `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`, `tests/test_artifact_branch_read_node.py` и всем изменённым тестовым модулям (`test_artifact_materialization`, `test_artifact_ref_sync`, `test_branch_freshness_gate`, `test_checkpoint_external_step_artifacts`, `test_doctor`, `test_doctor_artifact_branch_sync`, `test_fsm_merge_gate_done_snapshot`, `test_git_fixation`, `test_guard_task_root_subdirectory`, `test_multitarget_invariants`, `test_split_assessment_merge_gate`) — **246 passed, 3 subtests passed** (148 с).
- Временная мутация 1: `artifact_branch._repo_kw` → всегда `{}` (узел чтения спрашивает git пульта) — красные `test_show_ls_tree_and_sha_come_from_the_project_clone` и `test_pult_copy_of_the_ref_is_not_read`. Код возвращён.
- Временная мутация 2: `review.artifact_text` всегда `gitcmd.git` (игнор `task_id`) — красный `test_review_package_text_reads_the_project_clone`. Код возвращён; `git status` — чисто.
- `git apply --check` приложения PLAN (инвариант 25), вырезанного из PLAN.md, — проходит.
- `python3 scripts/codebase_map.py` → `git diff docs/codebase-map.md` — разница только в `built_at_sha`, карта свежа; изменение откачено.
- `grep -rn "_fix_external|_read_external|init_artifact_repo|artifact_repo_has_no_remote|check_remote_empty" orchestrator scripts` — пусто (AC-3).
- Обход оставшихся прямых `gitcmd.show/ls_tree_files/branch_head_sha/diff_names` в `orchestrator/`: остальные читают кодовую ветку, `main` или пути только для артели (`target == DEFAULT_TARGET`). Единственный пропущенный читатель ссылки — `fixation.py:223` (наблюдение выше).

## Предложения системе
- Класс «чтение ссылки документов мимо узла `artifact_branch`»: кроме `gitcmd.show/ls_tree_files` (предложение в PLAN), сюда же входят диапазонные примитивы по sha фиксации (`gitcmd.commit_committer_dates`, `is_ancestor`) — guard на «sha из `fixed_sha`/`tests_locked_sha` идёт в `gitcmd.*` без `repo=`» поймал бы `fixation.py:223`.
- Гейт `approved` требует реестр, закрытый целиком, — minor-наблюдение без блокировки вердикта завести в реестр нельзя, оно уходит в свободный текст. Стоит дать статус-носитель для неблокирующих наблюдений (например, `deferred` с адресом этапа).
