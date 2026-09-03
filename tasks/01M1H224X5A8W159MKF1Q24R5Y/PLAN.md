---
task: 01M1H224X5A8W159MKF1Q24R5Y
type: plan
author_role: developer
status: draft
schema_version: 3
---

# PLAN: A7 — артель как внешний target: пин версии, шаг обновления, внешний флоу

## Подход

Два независимых, но переплетённых блока:

**Б1 — снятие особого случая догфуда (требования 1-2 SPEC).** Все места,
различающие поведение по `target == config.DEFAULT_TARGET`, переводятся
на generic-путь, УЖЕ существующий и протестированный для любого другого
target (`sled`/`extproj` в существующих тестах): `catalog.cmd_new`
(всегда `_new_external_artifact_branch`, `_new_dogfood` удаляется),
`artifact_source.resolve` (всегда артефактная ветка, `foreign=True`),
`fixation.fix`/`read` (всегда `_fix_external`, `_fix_dogfood`/
`_dogfood_branch` удаляются), `checkpoint.commit_step_artifacts` (всегда
`_commit_external_step_artifacts`), `runner.role_cwd` (всегда
`PROJECTS/<target>/workspace`), `cleanup._publish_snapshot_if_pending`
(снапшот для любого target, кроме canary), `doctor.check_target_layout/
check_target_wrapper/check_remote_empty/check_base_branch/recovery_check`
(общий код без skip-ветки для 'artel'), `doctor.check_orphans` (сканирует
и `tasks/` пульта, и `.artel/projects/<target>/tasks/` для ЛЮБОГО
объявленного target, включая artel).

Явно НЕ генерализуется (структурно неприменимо, ANSWER-1): гейт ёмкости
diff снимка (`fsm_advance._capacity_gate_refuses`) и сверка свежести
ветки (`fsm._pull_main_or_escalate`) — код артели физически живёт в
`config.ROOT` (не в отдельном клоне, как у настоящего внешнего target),
поэтому `git diff main...<ветка>` в ROOT остаётся содержательным именно
для артели и не переносится на "foreign"-признак артефактов. Три WIP-
чекпоинта (`checkpoint.commit_timeout_checkpoint/commit_abnormal_
checkpoint/commit_pause_now_checkpoint`) остаются исключительно
догфуд-путём: они и сегодня не работают ни для одного внешнего target
(явный докстринг «расширение — отдельная задача»), AC-6 их не
перечисляет, а корректная генерализация требует собственного дизайна
(куда чекпоинтить WIP произвольного внешнего клона) — вне рамки A7.

Ключевое следствие генерализации: `cmd_new` для НОВОЙ задачи больше не
создаёт git-worktree/кодовую ветку сама — код задачи (там, где он
физически будет — `config.ROOT` для артели, чужой клон для остальных)
заводит роль-разработчик первым коммитом внутри своего шага, как и для
любого сегодняшнего внешнего target.

**Б2 — Stage0/Stage1: пин версии (требования 3-5).** Мандат ANSWER-1
(вопрос 1, вариант B): `merge_gate -> done` переносится на плотницкую
запись, не трогающую чекаут/HEAD `config.ROOT` вовсе. Реализация:

1. `_cmd_approve_merge_gate` вместо `git checkout main` + `git pull
   --ff-only` + `git merge --no-ff <branch>` на `config.ROOT`:
   - `git fetch origin <MAIN_BRANCH>` + `git rev-parse FETCH_HEAD` —
     текущий sha "main артели" (без прикосновения к локальному
     `refs/heads/main`);
   - `git worktree add --detach <scratch> <fetched_sha>` — временный
     worktree ВНЕ рабочего дерева `config.ROOT` (тот же приём, что уже
     несёт `orchestrator/workspace.py` для задач, просто одноразовый и
     detached);
   - `git -C <scratch> merge --no-ff <branch> -m "..."` — тот же merge,
     что раньше делался в ROOT, теперь в scratch-дереве; конфликт —
     тот же разбор (`_handle_merge_conflict`), адресованный на
     `scratch`, не на ROOT;
   - `fsm_postmerge._regenerate_and_commit_map`/`_generate_and_commit_
     retro` получают необязательный параметр `repo` (по умолчанию
     `config.ROOT` — существующие юниты не меняют поведение) и,
     получив `scratch`, читают/пишут файлы и коммитят там
     (`gitcmd.in_repo`), не в ROOT;
   - `git push origin <sha-головы-scratch>:refs/heads/<MAIN_BRANCH>` —
     из `config.ROOT` (общая объектная база с scratch-worktree), явным
     sha, не текущим чекаутом — единственная операция, реально
     продвигающая "main артели" (`self.origin` в песочнице/GitHub в
     проде);
   - `git worktree remove --force <scratch>` — уборка, в `finally`,
     независимо от исхода.
2. Проверка `root_branch != config.MAIN_BRANCH` удаляется целиком
   (AC-10) — плотницкий merge не читает и не требует чекаута ROOT.
3. Doctor-проверка `check_root_pin`: сравнивает `gitcmd.head_sha()`
   (пин ROOT) с `git ls-remote origin refs/heads/<MAIN_BRANCH>` (main
   артели, без единого локального side-effect) — `warn` при
   расхождении с текстом обеих sha и командой `pin-update`, `ok` при
   совпадении; никогда `fail`.
4. Команда `artel.py pin-update <sha>`: `git fetch origin
   <MAIN_BRANCH>` + `git merge --ff-only <sha>` на `config.ROOT` (тут
   уже НАМЕРЕННО чекаут ROOT — единственное разрешённое место); журнал
   — `store.journal` с синтетическим `task_id` (`config.PIN_UPDATE_
   JOURNAL_TASK_ID`, по образцу `PROGRAM_SPEND_RESEED_TASK_ID`),
   `actor="operator"`, оба sha (7-значный префикс+полный) в `detail`.

**Б3 — защищённые пути в Draft-MR (требование 7/AC-16).** `github_
adapter.ensure_draft_mr` перед `pr create` считает diff ветки задачи
относительно её базы (`git diff --name-only <base>...<branch>` в
`config.ROOT`, тем же способом, что уже умеет `review.git_diff_part`,
только список путей, не текст) и, если хотя бы один задет
`config.PROTECTED_PATHS`, добавляет вызов `ci.gh("pr", "comment",
branch, "--body", <текст с путями>)` после `pr create` — независимо от
существующего предупреждения CI-job (не заменяет его).

## Шаги

1. **Generic-путь для 5 подсистем AC-6 + catalog.cmd_new (AC-5) +
   doctor generic-checks (AC-2/AC-3/AC-4)** — один MR: `catalog.py`,
   `artifact_source.py`, `fixation.py`, `checkpoint.py`, `runner.py`,
   `cleanup.py`, `doctor.py`. Юнит-тесты: адаптация `tests/test_doctor.
   py` (три теста, буквально проверявших skip для 'artel', переписаны
   на generic-исход по образцу их же соседних тестов для 'sled'),
   `tests/test_multitarget_invariants.py::test_dogfood_cwd_is_worktree`
   (переписан на generic-исход `role_cwd`).
2. **Плотницкий merge (Stage0) + doctor-проверка пина + pin-update
   (Stage1)** — `fsm_merge_gate.py`, `fsm_postmerge.py`, новый
   `orchestrator/pin.py`, `doctor.py` (`check_root_pin`), `artel.py`
   (диспетчер команды `pin-update`), `config.py`
   (`PIN_UPDATE_JOURNAL_TASK_ID`). Требует адаптации `tests/test_
   invariants.py` (`MergeOnlyFromMergeGateTest`/`MergeNeedsGreenCiTest`
   — часть проверок мокала git целиком и сверялась по имени
   подкоманды/порядку `checkout < merge`; переписаны на сверку исхода
   через реальный git, тем же приёмом, что уже применяет `tasks/
   01M1H224X5A8W159MKF1Q24R5Y/acceptance_tests/
   test_ac15_invariants_12_19_remain_green.py` — мандат на этот перенос
   даёт сам ANSWER-1) и `tests/test_git_fixation.py`/`tests/test_
   invariants.py` фикстур, опиравшихся на однобраншевый флоу `cmd_new`
   (см. «Влияние на систему»).
3. **Защищённые пути в Draft-MR** — `github_adapter.py`. Юнит-тест:
   `tests/test_github_adapter.py` (новый метод сценария с диффом,
   задевающим `config.PROTECTED_PATHS`).
4. **Targets.yaml/targets.py** — без изменений кода (AC-1 «зелёное с
   рождения», зафиксировано локальным приёмочным тестом); шаг явно не
   заводится.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (targets.yaml обычная запись) | 4 (уже выполнено) |
| 2 (generic-логика вместо догфуд-веток) | 1, 2 |
| 3 (новые задачи артели — M1/Б₃) | 1 |
| 4 (Stage0 — пин) | 2 |
| 5 (Stage1 — шаг обновления) | 2 |
| 6 (журнал обновления пина) | 2 |
| 7 (защищённые пути в MR) | 3 |
| 8 (полный внешний флоу без записи в кодовые ветки/main) | 1, 2 |

## Влияние на систему

- **Инварианты 12/19** (docs/invariants.md) не ослабляются: merge
  по-прежнему делает только `approve` из `merge_gate`, и только при
  зелёном CI — меняется МЕХАНИЗМ записи (плотницки, не чекаутом), не
  ЭТИ два условия. `tests/test_invariants.py` содержит тесты,
  ЛИТЕРАЛЬНО проверяющие старый чекаут-механизм (`test_merge_gate_
  approve_is_that_path` — порядок `checkout < merge`/`pull < merge`;
  весь `MergeNeedsGreenCiTest` — мокает git и сверяется по имени
  подкоманды) — они адаптированы на сверку ИСХОДА через настоящий git
  (продвинулся/не продвинулся `refs/heads/main` origin в зависимости от
  CI), а не механизма; сам мандат на этот перенос даёт ANSWER-1
  (вопрос 1) и явно описывает нелокированный `tasks/
  01M1H224X5A8W159MKF1Q24R5Y/acceptance_tests/
  test_ac15_invariants_12_19_remain_green.py` как образец. Метод
  `test_no_other_state_and_no_other_command_merges` того же файла не
  тронут вовсе (не зависит от механики approve, «зелёный с рождения»).
- **Инвариант T056** (`_refuse_if_worktree`) не тронут — подтверждено
  локальным приёмочным AC-11.
- **Каскад по generic-пути cmd_new**: после того как `cmd_new`
  перестаёт заводить worktree/кодовую ветку для ЛЮБОГО target (включая
  артель), фикстуры юнит-тестов, построенные на однобраншевом флоу
  (`tests/test_git_fixation.py::RealPultGitTest` и её ~15
  зависимых классов; `tests/test_invariants.py::FsmTest` и её
  зависимые классы) перестают воспроизводить достижимый после этой
  задачи сценарий — они адаптированы на артефактную ветку (`artifact_
  branch.commit_files`/`checkpoint.commit_step_artifacts` вместо
  прямой записи на диск `config.TASKS`/worktree), с сохранением
  ПРОВЕРЯЕМОГО УТВЕРЖДЕНИЯ каждого теста (approve-по-sha, sha-фиксация,
  инцидент целостности, счётчики — сам предмет теста не меняется,
  меняется только то, КАК фикстура кладёт артефакт на диск/в git).
  Дубли покрытия, полностью совпадающие по существу с уже
  существующими generic-тестами для другого target (`sled`) —
  устранены (не задвоены), не ослаблены: то же утверждение остаётся
  проверенным ровно тем же классом теста, что уже проверяет его для
  любого внешнего target.
- **Откат**: любой шаг обратим ревертом коммита — новый код не меняет
  формат БД (кроме уже существующих колонок) и не трогает
  `targets.yaml`/защищённые пути. Обновление пина (`pin-update`) —
  ручная операторская команда вне цикла FSM, откатывается повторным
  вызовом со старым sha.

## Риски

- Плотницкий merge через `git worktree add --detach` + `git -C
  <scratch> merge` — новый для этого кодового пути приём (уже
  используется `workspace.py` для задач, но не для служебного
  scratch-merge); при отказе `git merge --abort` внутри scratch
  worktree main НЕ рискует остаться грязным (scratch — не ROOT), но
  сам scratch-worktree может остаться неубранным при инфраструктурном
  сбое — обёрнуто `try/finally` на `git worktree remove`.
- Разошедшийся объём переработки существующих тестов (см. «Влияние на
  систему») — риск пропустить регресс в тесте, который сам не будет
  запущен из-за ошибки импорта/фикстуры; закрывается финальным полным
  прогоном `python3 -m unittest discover -s tests` перед сдачей.

## Предложения системе

- Класс «два параллельных механизма для одного понятия» (артефактная
  ветка пульта `artifact/<id>` для ЖИВЫХ артефактов M1, и отдельный
  git-репозиторий `.artel/projects/<target>/` для их же hash-фиксации
  `fixation._fix_external`) — не связаны между собой: `fixation.fix()`
  коммитит `.artel/projects/<target>/tasks/<id>/`, куда M1-механика
  ничего не пишет. A7 эту нестыковку не создаёт (она уже была для
  любого внешнего target до этой задачи) и не решает — она вне рамки
  ANSWER-1/AC-6, но заслуживает отдельной задачи по сведению фиксации
  на артефактную ветку M1.
