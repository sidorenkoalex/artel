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

- `artifact_branch._new_branch_parent(task_id)` — СНАЧАЛА
  `gitcmd.has_no_remote(config.ROOT)`: ни одного `remote` вовсе (нет
  сети/`origin` никогда не настраивался/лёгкая тестовая песочница) —
  сразу голова локального `config.MAIN_BRANCH`, БЕЗ `git fetch` и БЕЗ
  записи в журнал (Решение Оператора по возврату 06.09, «Причина
  возврата»: «репозиторий без origin — молча локальный main»). Иначе
  (remote есть, хотя бы один) — предпочитает голову `origin/main`
  (`fetch_head_sha("origin", config.MAIN_BRANCH)`); если САМ `fetch` не
  удался (remote настроен, но недостижим/сеть недоступна) — фолбэк на
  `gitcmd.branch_head_sha(config.MAIN_BRANCH)` (текущее поведение,
  требование 1/AC-2) с записью в журнал задачи (`store.journal`,
  действие «артефактная ветка: fallback на локальный main», detail
  `"артефактная ветка от локального main: <причина>"` — ровно префикс,
  который ищет тест AC-7).

  Правка этого возврата: до неё `_new_branch_parent` всегда пыталась
  `git fetch origin main`, даже без единого `remote` в репозитории.
  `tests/test_branch_freshness_gate.py::TargetSourcedRemoteTest::
  test_pull_freshness_fetches_target_url_not_pult_origin` создаёт
  задачу с внешним target'ом в лёгкой песочнице (`gitcmd.git`
  подменена на `fake_git`, ни одного настоящего `remote`) и проверяет,
  что ПЕРВЫЙ записанный `fetch`-вызов — это фетч источника target'а на
  гейте свежести (`("fetch", url, base)`), а не пульта; безусловный
  `fetch_head_sha("origin", config.MAIN_BRANCH)` при заведении задачи
  (`cmd_new` → `commit_files` → `_new_branch_parent`, первый коммит)
  оказывался ПЕРВЫМ вызовом `fetch` в этой песочнице и красил
  `assertNotIn("origin", remote_args)` — CI-красный, зафиксированный
  возвратом. `has_no_remote` для этой песочницы (и для АНАЛОГИЧНЫХ
  лёгких `fake_git`-песочниц, и для настоящих git-репозиториев без
  `origin`) возвращает True (`git remote` пуст) — фетч и журнал
  пропускаются целиком, стороннего `fetch`-вызова больше не возникает.
  Тест AC-7 этой же задачи опирался на СТАРОЕ поведение (журнал пишется
  даже вовсе без `origin`) — переписан на сценарий «`origin` заведён
  (`add_origin`), но недостижим» (bare-репозиторий уничтожен ДО
  коммита), что и есть теперь настоящий критерий записи в журнал; см.
  «Риски» ниже.

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
- Возврат 06.09 (бюджет исчерпан в предыдущем шаге, $15.96 из $15.00)
  прервал шаг ПОСЛЕ того, как код и PLAN.md уже были зафиксированы
  (коммит `bc17bb20`) — предыдущий advance `in_dev -> review` был
  отклонён с «нет шага developer после возврата». В этом шаге код не
  менялся (он уже реализует требования 1-4 и AC-1..AC-8 без замечаний):
  повторно прогнаны приёмочные тесты задачи (7/7, зелёные), затронутые
  юнит-планки — `tests/test_gitcmd_branch_reads.py`,
  `tests/test_gitcmd_carpentry.py`, `tests/test_gitcmd_check_ignore.py`,
  `tests/test_git_fixation.py` (79 тестов), `tests/test_doctor.py`
  (120 тестов), `tests/test_catalog_new_race.py`,
  `tests/test_catalog_status_log.py`, `tests/test_artifact_materialization.py`,
  `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py`
  (72 теста) — все зелёные, и `scripts/guard.py` на артефактах задачи
  (`GUARD: ок`). Правка этого шага — фиксация факта повторной проверки
  здесь, закрывающая причину возврата.
- Возврат из `verifying` (CI красный, 4 теста): корневая причина —
  `_new_branch_parent` безусловно звала `git fetch origin main` даже в
  репозитории вовсе БЕЗ `remote` (нет сети/`origin` не настроен/лёгкая
  тестовая песочница), тем самым (а) полируя список git-вызовов
  первым посторонним `fetch` в `tests/test_branch_freshness_gate.py::
  TargetSourcedRemoteTest` (внешний target, `cmd_new` → первый коммит
  артефактной ветки пульта → наш `fetch` раньше собственного фетча
  гейта свежести на target) и (б) писала бы в журнал задачи запись
  «fallback на локальный main» при КАЖДОМ заведении задачи без origin,
  включая любые лёгкие песочницы. Решение Оператора по возврату (текст
  «Причина возврата»): запись в журнал — только когда `remote origin`
  СУЩЕСТВУЕТ, а сам `fetch` не удался; репозиторий вовсе без `origin` —
  молча локальный `main`, без сетевого вызова и без записи. Правка:
  `_new_branch_parent` (`orchestrator/artifact_branch.py`) — новая
  первая проверка `gitcmd.has_no_remote(config.ROOT)`, при True —
  сразу `branch_head_sha(config.MAIN_BRANCH)`, минуя `fetch_head_sha`
  и `store.journal` целиком.
- Правка задела тест AC-7 этой же задачи (не «существующий» тест вне
  зоны — собственный приёмочный тест, залоченный для code-фиксов, но
  редактируемый под явное решение Оператора о переинтерпретации AC-2,
  см. выше): его прежний сценарий («вовсе без origin») по новому
  правилу больше не пишет в журнал — переписан на «`origin` заведён
  (`add_origin()`), но bare-репозиторий уничтожен ДО коммита» (`fetch`
  падает, remote при этом существует) — ровно тот случай, для которого
  запись в журнал теперь и предназначена. Прогнаны все 7 приёмочных
  тестов задачи (зелёные) и widely-затронутая батарея (`tests/
  test_branch_freshness_gate.py`, `test_doctor.py`, `test_gitcmd_
  branch_reads.py`, `test_gitcmd_carpentry.py`, `test_gitcmd_check_
  ignore.py`, `test_git_fixation.py`, `test_catalog_new_race.py`,
  `test_catalog_status_log.py`, `test_artifact_materialization.py`,
  `test_multitarget.py`, `test_multitarget_invariants.py`,
  `test_zones_gate.py`, `test_review_package.py`, `test_answer_
  branch_reads.py`, `test_amend.py`, `test_doctor_fix_ignored_
  artifacts.py`, `test_fsm_merge_gate_done_snapshot.py`, `test_zones_
  approve.py`, `test_dry_run.py`, `test_checkpoint_external_step_
  artifacts.py`, `test_acceptance_tests_flow.py`, `test_answer_gate.py`,
  `test_analyst_role.py` — 557 тестов + 17 subtests, все зелёные,
  включая ранее красный `test_pull_freshness_fetches_target_url_not_
  pult_origin`).

## Предложения системе

- Возврат по исчерпанию бюджета ($15.96 из $15.00) остановил шаг УЖЕ
  ПОСЛЕ фиксации кода и PLAN.md — но advance следующим шагом всё равно
  был отклонён формулировкой «замечания ревью не отработаны: возврат не
  отработан: нет шага developer после возврата», хотя реального
  REVIEW.md с `changes_requested` в задаче никогда не было (проверено
  `git log --all -- tasks/.../REVIEW.md` — пусто). Гейт «нет шага
  developer после возврата», видимо, срабатывает одинаково и на
  возврат по вердикту ревью, и на прерывание шага по бюджету — для
  второго случая формулировка отказа вводит в заблуждение (адресует
  разработчика к несуществующему REVIEW.md вместо факта прерывания по
  бюджету).
- Класс дефекта, повторившийся здесь: новый код на горячем пути
  `cmd_new`/`commit_files` (любой первый коммит артефактной ветки)
  проверен точечно списком заведомо релевантных тестовых файлов
  (`test_gitcmd_*`, `test_catalog_*`, `test_multitarget*`,
  `test_doctor.py` и т.п.), но `tests/test_branch_freshness_gate.py`
  в этот список не попал ни разу, хотя тоже заводит задачу через
  `catalog.cmd_new` в лёгкой `fake_git`-песочнице и чувствителен к
  ЛЮБОМУ новому git-вызову на этом пути. Точечный список «тестов
  затронутых модулей» составлялся по ИМЕНИ модуля (`gitcmd`/
  `artifact_branch`/`doctor`), не по факту прохождения кода через
  `cmd_new` — для правок хот-пути заведения задачи стоит явно искать
  `grep -l "cmd_new\|capture_new_task_id" tests/*.py` вместо интуиции
  по названию файла, иначе тесты вроде этого систематически выпадают
  из точечного прогона и красят только CI.
