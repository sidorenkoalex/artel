---
task: 01M42PENCS26D0656X8FR7DFA7
type: plan
author_role: developer
status: draft
schema_version: 5
budget_usd: 100
---

# PLAN: ADR-0021, этап 2 — клон и рабочие копии задач в области проекта

## Подход
Центральный узел — область проекта в `orchestrator/workspace.py` и
`orchestrator/repo_context.py`:

- `repo_context.clone_path(<имя>)` = `.artel/projects/<имя>/repo` для ЛЮБОГО
  проекта, включая артель; `resolve("artel").path` — клон, `path_or_none` —
  путь клона для любого разрешённого контекста, `repo_context.git` — всегда
  `gitcmd.in_repo(ctx.path, …)`.
- `workspace.ensure_clone(target)` — идемпотентный `git clone <url записи
  targets.yaml>` + `core.hooksPath = <config.ROOT>/scripts/git-hooks`
  (`set_clone_hooks`); существующий каталог клона не трогается; неудача —
  каталог недоделанного клона убирается, причина называет клон и адрес,
  отката на главную копию/`workspace/` нет. Зовут `init`, `doctor --fix`,
  `new` (через `workspace.ensure`).
- `workspace.path(id, target)` = `.artel/projects/<имя>/worktrees/<id>/`;
  `workspace.ensure` — `fetch origin` в клоне, затем `git -C <клон> worktree
  add -b <ветка> <путь> <origin/база>`; `task_repo(id)` — клон проекта задачи.
  `runner.role_cwd`, `plank-run`, уборка чекпоинтов и планки — этот каталог.
  `.artel/worktrees/<id>` и общий `workspace/` пульт больше не заводит.
- Все git-операции задачи получают репозиторий явно (`repo=`/`in_repo`):
  ветка, автокоммиты и чекпоинты (теперь и для внешнего проекта — у него
  своя рабочая копия на ветке задачи), ссылка документов (`artifact_branch.
  repo_for_target` = клон, особого случая `config.ROOT` нет), push, временная
  рабочая копия мержа и проверки приложений PLAN (в клоне), коммит мержа,
  push `main`, уборка (`cleanup.py`, `doctor/orphans.py`).
- Шаги мержа, включавшиеся сравнением пути с `config.ROOT`, переведены на
  признак `target == config.DEFAULT_TARGET` (таблица требования 3).
- `note`/`doc-commit`/`canary pool-seal` коммитят и пушат через клон артели;
  база сверки удержанных записей — `origin/main` клона; `.artel/notes-work`
  упразднён.
- Исторические ссылки артели (AC-13): `docs <id>` при отсутствии ссылки в
  клоне и в `origin` читает её из git главной копии ТОЛЬКО чтением с явным
  репозиторием (`gitcmd.show/ls_tree_files/branch_head_sha(repo=config.ROOT)`,
  `docs_fetch._main_copy_reader`), с предупреждением в stderr; git главной
  копии не меняется. `docs --fetch-all` и `retro_corpus` читают клон.
- Канарейка строит `projects/artel/repo` и `worktrees/<id>` во временном
  каталоге тем же кодом (её `config.ROOT`/`PROJECTS` — временные).

Расхождение с оценкой SPEC ($50): детектор долгоживущего теста нашёл 124
вызова `gitcmd` без репозитория в ~40 модулях, плюс правка существующих
тестов под новое место рабочей копии и явный `-C`. Потолок поднят до $100
(ROLE_BUDGET_CAP).

## Шаги
1. Область проекта: `repo_context`, `workspace` (клон, хуки клона, рабочая
   копия задачи), `artifact_branch` (репозиторий ссылок — клон), `catalog`
   (`init`/`new` заводят клон, отказ `new` с причиной), `runner.role_cwd`.
2. Явный репозиторий во всех вызовах `gitcmd` по задаче/проекту
   (`advance_gates/*`, `fsm*`, `review`, `brief`, `ci`, `coldstart`,
   `cleanup`, `artifact_cleanup`, `checkpoint`, `pull`, `amend`, `doctor/*`,
   `github_adapter`, `fixation`, `dry_run`, …); примитивы `gitcmd` получили
   параметр `repo`.
3. Гейт мержа: временная рабочая копия мержа и проверки приложений — в
   клоне; шаги таблицы требования 3 — по признаку «артель».
4. Чекпоинты/`plank-run`/`acceptance.drop_from_code_copy` — `worktrees/<id>/`
   проекта задачи; чекпоинт кода — для любого проекта, при отсутствии
   рабочей копии — пропуск без вызова git (как прежде).
5. `note`/`doc-commit`/`pool-seal` через клон артели, база — `origin/main`
   клона.
6. `doctor`: хуки клона (`check_git_hooks` — главная копия как прежде + клон
   каждого проекта; предупреждение с именем клона; `--fix` ставит
   абсолютный путь), сироты и ветки задач — в клоне.
7. Исторические ссылки (`docs`, `--fetch-all`, `retro_corpus`).
8. Канарейка — область `projects/artel` во временном каталоге.
9. Приложения к `docs/invariants.md` и `tests/test_invariants.py` (ниже).
10. Тесты: долгоживущие файлы задачи (автор тестов) + правка существующих
    тестов в объёме ADR-0021 (перечень ниже); карта кодовой базы.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 4 |
| 2 | 2, 3, 4 |
| 3 | 3, 4 |
| 4 | 2 |
| 5 | 5 |
| 6 | 1, 6 |
| 7 | 8 |
| 8 | 7 |
| 9 | 9 |
| 10 | 10 |

### Вывод поиска вызовов `gitcmd` без репозитория (AC-8)
Поиск — детектором долгоживущего теста
`tests/test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py`
(`calls_without_repo` по всем `orchestrator/**/*.py`, кроме самого
`gitcmd.py`; вывод в формате `grep -n`). Все 31 вызов — из перечня
требования 4 (pin, doctor/root_pin, doctor/git_hooks в части главной копии,
catalog — версия пульта, canary, canary_drive, snapshot, git-идентичность
Оператора); вызовов вне перечня нет:

```
orchestrator/canary.py:1771:if not main_sha or not gitcmd.is_ancestor(main_sha, target_sha):
orchestrator/canary.py:1773:age = gitcmd.merges_between(main_sha, target_sha)
orchestrator/canary.py:2013:res = gitcmd.git("rev-parse", "--verify", f"{revision}^{{commit}}")
orchestrator/canary.py:2056:target_sha, _reason = gitcmd.fetch_ref_sha("origin", config.MAIN_BRANCH)
orchestrator/canary.py:2058:return gitcmd.head_sha(), None
orchestrator/canary.py:2080:if target_sha == gitcmd.head_sha():
orchestrator/canary.py:2136:else gitcmd.head_sha())
orchestrator/canary.py:2339:target_sha = gitcmd.head_sha()
orchestrator/canary_drive.py:52:head = gitcmd.head_sha()
orchestrator/catalog.py:428:root_sha = gitcmd.head_sha()
orchestrator/doctor/git_hooks.py:26:res = doctor.gitcmd.git("rev-parse", "--is-inside-work-tree")
orchestrator/doctor/git_hooks.py:34:res = doctor.gitcmd.git("config", "--get", "core.hooksPath")
orchestrator/doctor/git_hooks.py:100:res = doctor.gitcmd.git("config", "core.hooksPath", HOOKS_PATH)
orchestrator/doctor/root_pin.py:29:root_sha = doctor.gitcmd.head_sha()
orchestrator/doctor/root_pin.py:30:ls = doctor.gitcmd.git("ls-remote", "origin", f"refs/heads/{doctor.config.MAIN_BRANCH}")
orchestrator/doctor/root_pin.py:53:return doctor.gitcmd.fetch_head_sha("origin", doctor.config.MAIN_BRANCH)
orchestrator/doctor/root_pin.py:63:if not root_sha or doctor.gitcmd.is_ancestor(root_sha, origin_sha):
orchestrator/doctor/root_pin.py:65:res = doctor.gitcmd.git("log", f"{origin_sha}..{root_sha}",
orchestrator/doctor/root_pin.py:86:root_sha = doctor.gitcmd.head_sha()
orchestrator/pin.py:93:old_sha = gitcmd.head_sha()
orchestrator/pin.py:95:fetch = gitcmd.git("fetch", "-q", "origin", config.MAIN_BRANCH)
orchestrator/pin.py:110:merge = gitcmd.git("merge", "--ff-only", sha)
orchestrator/pin.py:116:new_sha = gitcmd.head_sha()
orchestrator/pin.py:152:old_sha = gitcmd.head_sha()
orchestrator/pin.py:155:if not gitcmd.is_ancestor(sha, old_sha):
orchestrator/pin.py:174:reset = gitcmd.git("reset", "--hard", target)
orchestrator/pin.py:180:new_sha = gitcmd.head_sha()
orchestrator/runner.py:724:res = gitcmd.git("config", "--get", option)
orchestrator/snapshot.py:21:res = gitcmd.git("config", "--get", "user.name")
orchestrator/snapshot.py:52:conn, task_id, gitcmd.head_sha(),
orchestrator/snapshot.py:58:f"artel_sha: {gitcmd.head_sha()}\n"
```

Дополнительных мест «шаг включается сравнением с `config.ROOT`» сверх
таблицы требования 3 не найдено: оставшиеся упоминания `config.ROOT` в
`orchestrator/` — пути файлов пульта (templates/, skills/, scripts/,
docs/ пульта), а не включение шага.

### Изменения существующих тестов (AC-15)
Каждое — в объёме ADR-0021; утверждения меняются только там, где они
называли прежнее место (главная копия/`workspace/`/`.artel/worktrees/`).

- `tests/sandbox.py` — ADR-0021 п. 1: `strip_dash_c` (заглушки видят
  подкоманду сквозь `-C <клон>`), `link_artel_clone_to_root`,
  `seed_artel_clone_stub`, `make_project_repo` кладёт клон в `repo/`,
  фейковый `clone` оставляет каталог клона.
- `tests/test_workspace.py` — ADR-0021 п. 1: путь рабочей копии
  `.artel/projects/artel/worktrees/<id>` (было `config.WORKTREES/<id>` в
  `PathTest::test_path_is_the_standard_location` и `wt_path`);
  `registered_paths(клон)`; заглушки сквозь `strip_dash_c`; заявки мутаций.
- `tests/test_done_branch_cleanup.py` — ADR-0021 п. 1: `drop_merged_task_branch`
  получает репозиторий клона явно; утверждения прежние; заявки мутаций.
- `tests/test_kill_cleanup.py` — ADR-0021 п. 1: песочница патчит
  `PROJECTS`/`TARGETS`, клон артели = корень песочницы; распознавание
  подкоманды сквозь `strip_dash_c`; утверждения прежние.
- `tests/test_git_fixation.py` — ADR-0021 п. 1: клон артели = корень
  песочницы (`link_artel_clone_to_root`); утверждения прежние.
- `tests/test_brief.py` — ADR-0021 п. 1 (требование 4 SPEC):
  `CheckoutAfterReadTest` — утверждение `assertIn(("checkout", "--", MAP_REL),
  calls)` стало `assertIn(…, [strip_dash_c(c) for c in calls])`: вызов идёт с
  явным `-C`.
- `tests/test_multitarget.py` — ADR-0021 п. 1: структура проекта
  `["knowledge", "logs", "tasks", "worktrees"]` (было `… "workspace"`),
  каталог клона `repo` исключён из сверки структуры; заявки мутаций.
- `tests/test_multitarget_invariants.py` — ADR-0021 п. 1, п. 12:
  `PultArtifactIsolationTest` — клон артели = корень песочницы, маркеры
  внешнего проекта в `repo/` и `worktrees/T001/` (было `workspace/`);
  `ExternalWorkspaceIsolationTest::test_dogfood_target_cwd_is_its_worktree`
  ждёт `.artel/projects/artel/worktrees/T001` (было `config.WORKTREES/T001`);
  `test_external_target_cwd_is_its_workspace` ждёт
  `.artel/projects/sled/worktrees/<id>` (было `…/sled/workspace`), рабочую
  копию заводит настоящий `git worktree add` (`git_config_else_real`, мимо
  шпиона `subprocess.run` песочницы); заявки мутаций.
- `tests/test_repo_context.py` — ADR-0021 п. 1 (AC-6 SPEC): путь артели —
  клон (`assertEqual(ctx.path, config.ROOT)` →
  `assertEqual(ctx.path, PROJECTS/artel/repo)`), путь внешнего — `…/sled/repo`
  (было `…/sled/workspace`); `path_or_none` для артели — путь клона (было
  `assertIsNone`); `repo_context.git` для артели — `in_repo` клона.
- `tests/test_artifact_ref_sync.py` — ADR-0021 п. 1:
  `CompareAndSwapRaceTest` распознаёт `update-ref` сквозь `strip_dash_c`
  (ссылка документов пишется в клоне с `-C`); утверждения прежние.

## Приложение 1: docs/invariants.md — инварианты 20, 21, новый 40
Инварианты 20 и 21 — в редакции таблицы п.12 ADR-0021 (любой проект, включая артель; каталог роли — `worktrees/<id>/`), новая строка 40 — «git главной копии пульта не меняется в ходе задачи».

Применимость подтверждена: `git apply --check` каждого приложения по порядку (1 → 2 → 3) на чистой копии дерева ветки задачи — код 0 у всех трёх; после наложения `tests/test_invariants.py` целиком зелёный (72 passed), новый тест красен под обеими мутациями планки (ветка задачи и временная рабочая копия мержа в git главной копии).

```diff
diff --git a/docs/invariants.md b/docs/invariants.md
index 830412af..99c1b836 100644
--- a/docs/invariants.md
+++ b/docs/invariants.md
@@ -47,8 +47,8 @@ docs/adr/0002-integrity-principle.md, CLAUDE.md.
 | 17 | Оценка влияния на систему — артефакт: PLAN без секции «Влияние на систему» не проходит guard | `test_invariants.GuardKeepsTheIntegritySectionTest` | ADR-0002, правило 1 |
 | 18 | Автоматизация механических команд не проходит гейты: `auto` не вызывает `approve`/`reject` и пути мимо гейта не имеет | `test_auto_cycle.AutoNeverPassesAGateTest` | design §4; tasks/T014/SPEC.md, требование 3 |
 | 19 | Merge требует зелёного CI головного коммита ветки задачи; не-зелёный, **неизвестный** и **неполный** (проверок меньше, чем обещает `total_count`) статус merge не выполняют | `test_invariants.MergeNeedsGreenCiTest`; разбор статуса — `test_ci_status.BranchStatusTest`, полнота ответа — `test_ci_status.PaginationTest` | design §4 (guards неотключаемы); tasks/T017/SPEC.md, требование 6; tasks/T018/SPEC.md, требования 1–3 |
-| 20 | Артефакты и логи внешнего target не появляются в рабочем дереве пульта ни на одном переходе FSM (`.artel/` — `.gitignore` пульта целиком) | `test_multitarget_invariants.PultArtifactIsolationTest` | ADR-0003 3д; tasks/T020/SPEC.md, требование 1 |
-| 21 | Рабочий каталог роли внешнего target — только `.artel/projects/<target>/workspace/`; на запись роли дополнительно открыт только каталог документов задачи `.artel/projects/<target>/tasks/<id>/` (`--add-dir` у claude и у `codex exec`, ADR-0021 этап 1), документы задачи в рабочей копии кода вне прогона приёмки не лежат; окружение процесса не содержит путей и конфигов пульта сверх явно переданного (HOME/CLAUDE_CONFIG_DIR) | `test_multitarget_invariants.ExternalWorkspaceIsolationTest` | ADR-0003 §4, п.14; tasks/T020/SPEC.md, требование 2 |
+| 20 | Артефакты и логи любого проекта, включая артель (область проекта `.artel/projects/<имя>/`: клон `repo/`, рабочие копии задач `worktrees/<id>/`, `tasks/`, `logs/`), не появляются в рабочем дереве пульта ни на одном переходе FSM (`.artel/` — `.gitignore` пульта целиком) | `test_multitarget_invariants.PultArtifactIsolationTest` | ADR-0003 3д; ADR-0021 пп. 1, 12; tasks/T020/SPEC.md, требование 1; tasks/01M42PENCS26D0656X8FR7DFA7/SPEC.md, требование 9 |
+| 21 | Рабочий каталог роли задачи любого проекта, включая артель, — только её рабочая копия `.artel/projects/<имя>/worktrees/<id>/` (не главная копия пульта, не общий `workspace/`); на запись роли дополнительно открыт только каталог документов задачи `.artel/projects/<имя>/tasks/<id>/` (`--add-dir` у claude и у `codex exec`, ADR-0021 этап 1), документы задачи в рабочей копии кода вне прогона приёмки не лежат; окружение процесса не содержит путей и конфигов пульта сверх явно переданного (HOME/CLAUDE_CONFIG_DIR) | `test_multitarget_invariants.ExternalWorkspaceIsolationTest` | ADR-0003 §4, п.14; ADR-0021 пп. 1, 12; tasks/T020/SPEC.md, требование 2; tasks/01M42PENCS26D0656X8FR7DFA7/SPEC.md, требование 9 |
 | 22 | Нумерация задач независима per-target; операции по `task_id` (журнал, spend, kill) одного target не читают и не меняют строки другого | `test_multitarget_invariants.CrossTargetDbIsolationTest` | ADR-0003 3ж; tasks/T020/SPEC.md, требование 3 |
 | 23 | Пороги суммарного расхода программы (70%/90%) считаются суммой `spent_usd` по всем задачам ВСЕХ target, не одного | `test_multitarget_invariants.ProgramSpendAcrossTargetsTest` | roadmap §5; ADR-0003 3ж; tasks/T020/SPEC.md, требование 4 |
 | 24 | Счётчик номеров задач target не переиспользует номер архивированной (не удалённой) строки при пересеве после reconnect | `test_multitarget_invariants.CounterSurvivesArchivalOnReconnectTest` | ADR-0003 3ж («архивация строк, никогда DELETE»); tasks/T020/SPEC.md, требование 5 |
@@ -67,6 +67,7 @@ docs/adr/0002-integrity-principle.md, CLAUDE.md.
 | 37 | Класс `tests/*.py` с собственным `PATCHED_ATTRS` для `tests.sandbox.TmpRootTest` патчит `config.WORKTREES`, либо явно значится в `ALLOWLIST` скана с обоснованием, почему запись по этому пути для него недостижима (read-only сценарий или подмена самого `workspace.ensure`, не пути) — непропатченный `WORKTREES` не двигается вместе с `config.ROOT` (вычислен один раз при импорте) и уводит настоящий `git worktree add` в `.artel/worktrees` реального корня пульта, а не песочницы теста | `test_invariants.SandboxPatchedAttrsCoverWorktreesInvariantTest` | tasks/01M2CN465WEDCF6D77V37FJ82E/SPEC.md; docs/audits/code-revision-2026-09-12.md (CR-2026-09-12-1 ★), docs/audits/code-revision-2026-09-13.md (повтор) |
 | 38 | Удаление, переименование и ослабление тестов `tests/**/*.py` без мандата Оператора не проходят: переход `in_dev → verifying` отказывает именованным действием «переход отклонён: гейт неослабления тестов», гейт мержа тем же узлом сравнения переводит задачу в `escalated` до попытки merge. Находка — удалённый файл, пара переименования (`git diff -M`), исчезнувший из head тестовый метод изменённого файла и появившийся в head пропуск (`@skip`/`@skipIf`/`@skipUnless`/`@expectedFailure`/`@pytest.mark.skip`/`skipif`/`xfail`, вызов `self.skipTest(`/`pytest.skip(`), которого не было в base на том же имени; файл с нулём тестовых методов в base находкой не считается. Утверждение тестового метода, сохранившего имя, которого в head нет в той же нормальной форме (оператор `assert`, вызов `assert*`/`fail`, `pytest.raises`/`pytest.warns`; сообщение, локальные имена и корень импортированного модуля не различаются), — находка наблюдения: запись журнала «изменены утверждения тестов (наблюдение)» на обоих рубежах и раздел ревью-пакета, переход и мерж от неё не зависят (SPEC 01M3Y753QNG6TS5C7MTJS1MEV6). Мандат — строка `Ослабление тестов разрешено: <пути и имена>` в `tasks/<id>/ANSWER-n.md`, ЧЕЙ ПОСЛЕДНИЙ КОММИТ в истории ссылки документов `refs/artifacts/<id>` доказанно не автокоммит артефактов шага роли (тот же рубеж, что у мандата зон в инварианте 34): роль не выписывает разрешение себе сама. Молчание git на переходе — отказ (fail-closed, ADR-0002), на мерже — fail-open, как у соседнего рубежа защищённых путей | `test_invariants.TestWeakeningNeedsTheOperatorTest`; `tests/test_test_integrity_gate.py` (в том числе `AssertionObservationTest`); `tests/test_guard_test_ast.py` (в том числе `ChangedAssertionsTest`); `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`; `tasks/01M3FQ2V77QNK95Z599DM124QN/acceptance_tests/` | tasks/01M3FQ2V77QNK95Z599DM124QN/SPEC.md, требования 1-7; ADR-0002 (принцип целостности); строка бэклога П2 от 26.09.2026 «Гейт неослабления тестов в пульте» |
 | 39 | Порядок состояний FSM — `in_dev → verifying → review → acceptance → merge_gate`: CI подтянутой головы кодовой ветки проверяется ДО ревьювера, не после. Девять рубежей перехода `in_dev → review` (подтяжка main, прогон приёмочной планки, гейт зон, гейт заявки мутации — новые и изменённые тесты `tests/` без строки «Ловит мутацию:» в докстринге, 01M29A0F88P9GKSXFW90F99H2N, гейт неослабления тестов — удаление, переименование и ослабление тестов `tests/` без мандата Оператора, 01M3FQ2V77QNK95Z599DM124QN, гейт ёмкости, лок планки, гейт «замечания ревью не отработаны», сверка головы на origin) стоят на `in_dev → verifying` целиком, без повтора на `verifying → review`; в `review` из `verifying` ведёт только зелёный CI головы. Возврат `changes_requested` — в `in_dev`, повторный вход в `review` — снова через `verifying` | `tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/test_ac01_ac09_state_order.py`; `tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/test_ac02_ac08_gates_moved_to_verifying.py`; `test_auto_cycle.py::FSM_STATES` | ADR-0015 (docs/adr/0015-ci-before-review.md); tasks/01M1TQ0TRCZPRZX22C4084NCPB/SPEC.md, требования 1-3 |
+| 40 | Git главной копии пульта не меняется в ходе задачи: от `new` до `done` (автокоммит шага, подтяжка `main`, мерж) ветки `refs/heads/*`, ссылки `refs/artifacts/*`, HEAD и `git worktree list` главной копии остаются прежними — ветка задачи, её рабочая копия, ссылка документов, временная рабочая копия мержа, коммит мержа и push живут в клоне проекта `.artel/projects/<имя>/repo`; git главной копии меняют только `pin-update`/`pin --to` и ремонт хуков самого пульта (`doctor --fix`) | `test_invariants.MainCopyGitUnchangedDuringTaskTest` | ADR-0021 пп. 1, 2, 12; tasks/01M42PENCS26D0656X8FR7DFA7/SPEC.md, требования 2, 9 |
 
 ## На ревью — тестом не выражаются
 
```

## Приложение 2: tests/test_invariants.py — совместимость существующих тестов
ADR-0021 п. 1: `KillKeepsMainIntactTest` патчит `PROJECTS`/`TARGETS` и связывает клон артели с корнем песочницы; заглушка `_show` `TestWeakeningNeedsTheOperatorTest` принимает `repo=`. Утверждения не меняются.

Применимость подтверждена: `git apply --check` каждого приложения по порядку (1 → 2 → 3) на чистой копии дерева ветки задачи — код 0 у всех трёх; после наложения `tests/test_invariants.py` целиком зелёный (72 passed), новый тест красен под обеими мутациями планки (ветка задачи и временная рабочая копия мержа в git главной копии).

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index 109f1734..ed2ff696 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -1593,8 +1593,18 @@ class KillKeepsMainIntactTest(unittest.TestCase):
                             # Worktree задачи (SPEC T045): kill убирает его —
                             # без патча ушёл бы в .artel/worktrees/ РЕАЛЬНОГО
                             # репозитория пульта, не песочницы.
-                            ("WORKTREES", self.root / ".artel" / "worktrees")):
+                            ("WORKTREES", self.root / ".artel" / "worktrees"),
+                            # Область проектов (ADR-0021 п.1, этап 2): клон
+                            # артели и рабочие копии задач — в песочнице.
+                            ("PROJECTS", self.root / ".artel" / "projects"),
+                            ("TARGETS", self.root / "targets.yaml")):
             self.repo.enter_context(mock.patch.object(config, attr, value))
+        # Клон артели — сам этот репозиторий (ADR-0021 п.1, этап 2): ветка
+        # задачи живёт в клоне, сценарии сверяют её и main git'ом
+        # `self.root`. До этапа 2 ссылка безвредна: клон не читается.
+        clone = self.root / ".artel" / "projects" / config.DEFAULT_TARGET / "repo"
+        clone.parent.mkdir(parents=True, exist_ok=True)
+        clone.symlink_to(self.root, target_is_directory=True)
 
         self.capture(catalog.cmd_init)
         # SPEC T094: id — ULID, не предсказуемый "T001" — берём то, что
@@ -2374,7 +2384,9 @@ class TestWeakeningNeedsTheOperatorTest(TmpRootTest):
         self.answer_text = None
         self.answer_subject = f"{self.TASK}: ANSWER-1 — ответ Оператора"
 
-    def _show(self, ref, rel):
+    def _show(self, ref, rel, repo=None):
+        # `repo` — клон проекта задачи (ADR-0021 п.1, этап 2): git задачи
+        # получает репозиторий явно; ответ от него здесь не зависит.
         if (ref, rel) == (self.BASE, self.DELETED):
             return self.SOURCE, ""
         if (ref, rel) == (self.ARTIFACT, self.ANSWER) and self.answer_text:
```

## Приложение 3: tests/test_invariants.py — тест инварианта 40
Сквозной прогон FSM задачи артели в песочнице долгоживущего файла задачи; снимок git главной копии сверяется после `new`, после шага, внутри мержа и после `done`.

Применимость подтверждена: `git apply --check` каждого приложения по порядку (1 → 2 → 3) на чистой копии дерева ветки задачи — код 0 у всех трёх; после наложения `tests/test_invariants.py` целиком зелёный (72 passed), новый тест красен под обеими мутациями планки (ветка задачи и временная рабочая копия мержа в git главной копии).

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -2467,3 +2467,68 @@ class TestWeakeningNeedsTheOperatorTest(TmpRootTest):
         self.assertTrue(escalated)
         self.assertEqual("escalated",
                          store.get_task(self.conn, self.TASK)["state"])
+
+
+class MainCopyGitUnchangedDuringTaskTest(unittest.TestCase):
+    """Инвариант 40: git главной копии пульта не меняется в ходе задачи
+    (ADR-0021 п.1, этап 2; tasks/01M42PENCS26D0656X8FR7DFA7/SPEC.md,
+    требования 2, 9).
+
+    Сквозной прогон FSM задачи артели в песочнице долгоживущего файла задачи
+    (`TaskFlowSandbox`: главная копия на настоящем git, bare `origin`, клон
+    артели заводит `init`): `new` → шаг developer штатным `runner.cmd_run`
+    (агент подменён, коммит — автокоммитом шага) → чужой коммит в
+    origin/main → `approve` на `merge_gate` → `done`. Ветки, ссылки
+    документов, HEAD и `git worktree list` главной копии сверяются с
+    исходными после `new`, после шага, ВНУТРИ мержа (пока временная рабочая
+    копия мержа существует) и после `done`.
+    """
+
+    def test_main_copy_git_is_unchanged_from_new_to_done(self):
+        """Ловит мутацию: ветка задачи заводится в git главной копии (её
+        `refs/heads` меняются уже после `new`) либо временная рабочая копия
+        мержа заводится в git главной копии (её `git worktree list` меняется
+        внутри мержа, хотя к `done` она уже снята).
+        """
+        from orchestrator import fsm_merge_gate
+        from tests.test_01m42pencs26d0656x8fr7dfa7_project_area import (
+            TaskFlowSandbox)
+
+        class Flow(TaskFlowSandbox):
+            def runTest(self):
+                pass
+
+        flow = Flow()
+        flow.setUp()
+        self.addCleanup(flow.doCleanups)
+
+        before = flow.main_snapshot()
+        observed = []
+
+        task = flow.new_task()
+        observed.append(("после new", flow.main_snapshot()))
+        step_out = flow.developer_step(
+            task, {f"kod/inv_{flow.rng.randrange(10 ** 6)}.py": "VALUE = 1\n"},
+            flow.task_docs(task, f"m{flow.rng.randrange(10 ** 9)}"))
+        observed.append(("после шага", flow.main_snapshot()))
+        flow.push_foreign(flow.gh["default"])
+        flow.set_state(task, "merge_gate")
+
+        publish = fsm_merge_gate._publish_merge_artifacts
+
+        def publish_observed(*args, **kwargs):
+            observed.append(("внутри мержа", flow.main_snapshot()))
+            return publish(*args, **kwargs)
+
+        with mock.patch.object(fsm_merge_gate, "_publish_merge_artifacts",
+                               publish_observed):
+            out = flow.approve_until_settled(task)
+        observed.append(("после done", flow.main_snapshot()))
+
+        self.assertEqual(flow.state_of(task), "done",
+                         flow.msg(f"{step_out}\n{out}\n{flow.journal(task)}"))
+        self.assertIn("внутри мержа", [name for name, _ in observed],
+                      flow.msg("мерж не дошёл до публикации"))
+        for name, snapshot in observed:
+            self.assertEqual(snapshot, before,
+                             flow.msg(f"git главной копии изменился {name}"))
```

## Влияние на систему
- Гейты не ослабляются: шаги мержа требования 3 исполняются для артели на
  клоне (наблюдаемо — долгоживущие тесты `MergeGateStepsOnCloneTest`), для
  внешнего проекта — как прежде не исполняются.
- Инварианты 20, 21 расширены на любой проект (приложение), новый инвариант
  40 «git главной копии не меняется в ходе задачи» держит сквозной тест
  `MainCopyGitUnchangedDuringTaskTest` (приложение).
- Хуки защиты `main` в клоне — из пина (абсолютный путь), т.е. код
  проверяемой ветки не может их подменить.
- Откат — revert одного merge-коммита; каталоги `.artel/projects/<имя>/repo`
  и `worktrees/` при откате остаются на диске и безвредны (`.artel/` вне git).

## Риски
- **CI ветки без приложения.** Шесть существующих тестов
  `tests/test_invariants.py` (`KillKeepsMainIntactTest` ×3 — нет клона артели
  в песочнице; `TestWeakeningNeedsTheOperatorTest` ×3 — заглушка `_show(ref,
  rel)` не принимает `repo=`) на ветке красны до наложения приложения 1:
  файл защищён, а вызов `gitcmd.show` без репозитория запрещён требованием 4.
  В дереве с приложениями весь `tests/test_invariants.py` зелёный (72 passed,
  проверено копией дерева). Приложение 1 безвредно и до этапа 2 — Оператор
  может провести его в `main` заранее отдельным MR, тогда CI ветки после
  подтяжки `main` зелёный.
- Внешний проект теперь получает чекпоинт кода пультом (раньше общий
  `workspace/` ветки задачи не нёс) — по требованию 2 и долгоживущему
  `test_ac5_external_project_skips_the_artel_steps`.

## Предложения системе
- Оболочка шага роли не знает `ls`/`cat`/`rm`, heredoc с `{"…"}` отклоняется
  как «expansion obfuscation» — отладка идёт через временные файлы-скрипты в
  рабочем каталоге (бэклог П2 от 05.10 уже фиксирует класс).
- Защищённый тестовый файл, чьи СУЩЕСТВУЮЩИЕ тесты ломаются от правки кода,
  красит CI ветки до мержа: нет механики «приложение к защищённому пути
  накладывается и в CI ветки» — стоит решить на уровне `ci.yml`.
