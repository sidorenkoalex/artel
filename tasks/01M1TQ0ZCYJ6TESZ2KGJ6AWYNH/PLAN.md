---
task: 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: артефактная ветка новой задачи заводится от origin/main, а не от пина

## Подход

Родитель первого коммита артефактной ветки сегодня вычисляется в
`artifact_branch.commit_files` (`gitcmd.branch_head_sha(branch) or
gitcmd.branch_head_sha(config.MAIN_BRANCH) or None`) — второй операнд
`or` читает голову ЛОКАЛЬНОГО пина, никогда не опрашивая `origin`.

Правка вводит один новый git-примитив (`gitcmd.fetch_head_sha`) и один
новый выбор родителя (`artifact_branch._new_branch_parent`), включаемый
в цепочку `or` РОВНО там же, где раньше стоял `branch_head_sha(config.
MAIN_BRANCH)` — короткое замыкание `or` уже гарантирует требование 4
(повторный коммит в существующую ветку эту ветку кода не задевает
вовсе, тест AC-4).

- `gitcmd.fetch_head_sha(remote, ref) -> (sha, reason)` — `git fetch
  <remote> <ref>`, затем `git rev-parse --verify --quiet FETCH_HEAD`.
  `git fetch` не чекаутит и не двигает HEAD ни при каком исходе (AC-1
  «мутация: fetch подменили на pull» ловится именно тем, что pull
  реально сдвинул бы HEAD/индекс главной копии — тест AC-1/AC-6 после
  вызова `commit_files` не проверяет HEAD главной копии впрямую, но
  дерево коммита обязано совпасть с origin, чего `fetch` без `pull`/
  чекаута и добивается). Отказ (нет сети/нет origin/git не ответил) —
  `("", причина)`, не исключение — вызывающий код сам решает деградацию.

- `artifact_branch._new_branch_parent(task_id)` — предпочитает голову
  `origin/main` (`fetch_head_sha("origin", config.MAIN_BRANCH)`); если
  origin недоступен — фолбэк на `gitcmd.branch_head_sha(config.
  MAIN_BRANCH)` (текущее поведение, требование 1/AC-2) с записью в
  журнал задачи (`store.journal`, действие «артефактная ветка: fallback
  на локальный main», detail `"артефактная ветка от локального main:
  <причина>"` — ровно префикс, который ищет тест AC-7). Журнал пишется,
  только если фолбэк реально состоялся (`local_head` непусто) — в
  лёгких песочницах без git-репозитория вовсе (`fake_git`/светлый
  `TmpRootTest`) оба источника пусты, поведение не меняется (parent
  остаётся `None`, как и до этой задачи).

- Требование 2/AC-3 не требует отдельного кода (ANSWER-1, вариант A):
  `commit_files` уже коммитит ЛЮБОЙ target в `config.ROOT` — правка
  автоматически покрывает и внешний target тем же путём.

- `doctor.check_artifact_branch_parent_ancestry(conn)` — новая отдельная
  проверка (SPEC требование 3/AC-5): задача 01M1TQ0X14Y5B3C87WC0Q31PK2 на
  момент начала разработки этой задачи (проверено по её артефактной
  ветке `artifact/01m1tq0x14y5b3c87wc0q31pk2`: только SPEC/TZ/
  acceptance_tests, PLAN.md ещё нет, diff кода с `main` пуст) свою
  проверку «артефактная ветка синхронна» ещё не реализовала — расширять
  нечего, и её проверка (локальный ref `artifact/<id>` == `origin/
  artifact/<id>`, требование 3 ЕЁ SPEC) отвечает на другой вопрос, чем
  моя (родитель первого коммита — предок `origin/main`), даже когда обе
  появятся. Для каждой нетерминальной задачи с существующей артефактной
  веткой: находит родителя первого коммита ветки обходом `git log
  --format=%H %ae --first-parent <branch>` назад от головы, пока автор
  строки — `fixation.FIXATION_AUTHOR_EMAIL` (единственный автор ЛЮБОГО
  коммита `write_commit`, ни один вызывающий код его не переопределяет)
  — последний совпавший коммит и есть граница; родитель ГРАНИЦЫ и есть
  искомый sha. Сверяет его `git merge-base --is-ancestor` с головой
  `origin/main` (тот же `fetch_head_sha`) — `warn` при отказе (`rc==1`),
  тихий `skip` без origin, `continue` (не warn) на неоднозначном ответе
  git (`rc` не 0/1). Вписана в `all_checks` рядом с `check_branch_
  freshness` — та же категория «внимание Оператора, не incident».

## Шаги

1. `gitcmd.fetch_head_sha` — новый примитив (`orchestrator/gitcmd.py`).
2. `artifact_branch._new_branch_parent` + правка `commit_files`
   (`orchestrator/artifact_branch.py`), импорт `store` в модуль.
3. `doctor.check_artifact_branch_parent_ancestry` +
   `_artifact_branch_first_commit_parent` (`orchestrator/doctor.py`),
   вписана в `all_checks`.
4. Приёмочные тесты задачи (`tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/
   acceptance_tests/`) — уже написаны test_author, планка не менялась;
   прогнаны против кода шагов 1-3.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 2 (констатация — код общий) |
| 3 | 3 |
| 4 | 4 |

## Влияние на систему

- Каждый ПЕРВЫЙ коммит артефактной ветки (только `cmd_new`, поскольку
  все прочие вызыватели `commit_files` — `answer`/`amend`/`checkpoint`/
  `doctor --fix` — коммитят в уже существующую ветку и попадают в
  короткое замыкание `branch_head_sha(branch)` до нового кода) теперь
  делает один `git fetch origin main` в `config.ROOT`. Прогнан полный
  список тестов, трогающих `cmd_new`/`commit_files`/`gitcmd`/`doctor`
  (см. «Риски» — конкретные файлы и время); ни один не свалился в
  реальную сеть — тестовые песочницы либо подменяют `gitcmd.git`
  целиком (`fake_git` — любой неизвестный git-вызов отвечает пустым
  успехом), либо гоняют настоящий git с `network_guarded_real_run`
  (`tests/sandbox.py`), который уже распознаёт `fetch`/`push`/
  `ls-remote`/`clone` как сетевые и не даёт им уйти за пределы
  локального пути/удалённого-по-имени.
- `doctor.all_checks` получил ещё один сетевой `git fetch` на весь
  прогон (не на задачу) — тот же порядок цены, что уже несёт
  `check_target_wrapper`/`recovery_check` (по одному git-вызову на
  target/задачу), не новый класс стоимости.
- Гейты/лимиты/инварианты не ослаблены: новая проверка doctor —
  `warn`/`skip`, не блокирует ни один переход FSM; `commit_files`
  сохраняет сигнатуру и контракт возврата (пустая строка — git не
  ответил) для всех вызывающих мест.
- Откат: правка полностью локальна в трёх функциях (`gitcmd.
  fetch_head_sha`, `artifact_branch._new_branch_parent`, `doctor.
  check_artifact_branch_parent_ancestry` + `_artifact_branch_first_
  commit_parent`) — `git revert` коммита этой задачи возвращает прежнее
  поведение без побочных миграций (новых таблиц/колонок нет).

## Риски

- Обход `_artifact_branch_first_commit_parent` опирается на то, что
  ВСЕ коммиты артефактной ветки — авторства `fixation.
  FIXATION_AUTHOR_EMAIL` (сегодня так — ни один вызыватель `commit_
  files` не переопределяет `author_name`/`author_email`). Прямой
  `git commit` в эту ветку в обход `commit_files` (например, ручная
  правка Оператора, упомянутая в контексте параллельной задачи
  01M1TQ0X14) сломает эвристику для затронутой задачи — вне зоны этой
  SPEC (её решает проверка синхронности ref параллельной задачи, не
  эта).
- Прогон полного `tests/` в шаге не делался (конвенция: полный набор
  идёт в CI). Прогнаны точечно (везде `--timeout=60`, зелёные):
  `tests/test_catalog_new_race.py`, `tests/test_catalog_status_log.py`,
  `tests/test_doctor.py` (120 тестов), `tests/test_gitcmd_branch_reads.py`,
  `tests/test_gitcmd_carpentry.py`, `tests/test_gitcmd_check_ignore.py`,
  `tests/test_git_fixation.py`, `tests/test_amend.py`, `tests/
  test_answer.py`, `tests/test_answer_branch_reads.py`, `tests/
  test_checkpoint_external_step_artifacts.py`, `tests/
  test_multitarget.py`, `tests/test_multitarget_invariants.py`, `tests/
  test_step_autocommit.py`, `tests/test_artifact_materialization.py`,
  `tests/test_workspace.py`, `tests/test_new_argv_parsing.py`, `tests/
  test_step_cost.py`, `tests/test_review_freshness.py`, `tests/
  test_review_package.py`, `tests/test_spec_budget.py`, `tests/
  test_task_id_prefix_regression.py`, `tests/
  test_store_schema_migration_parity.py`, `tests/test_invariants.py`,
  `tests/test_advance_guard.py`, `tests/test_agent_failure.py`, `tests/
  test_agent_log.py`, `tests/test_agent_prompt.py`, `tests/
  test_fsm_branch_correct_status_reads.py`, `tests/
  test_fsm_map_conflict_autoresolve.py`, `tests/
  test_fsm_merge_gate_done_snapshot.py`, `tests/test_kill_cleanup.py` —
  суммарно 731 тест + subtests, все зелёные. `tests/
  test_artifact_branch*.py` (AC-8) не существует на момент планки
  (подтверждено `find`), глобу нечего ловить.
- `orchestrator/*.py` правились (`gitcmd.py`, `artifact_branch.py`,
  `doctor.py`) — карта кодовой базы регенерирована тем же коммитом
  (`python3 scripts/codebase_map.py`).

## Предложения системе

- Нет.
