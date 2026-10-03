---
task: 01M409YKM3QE5KVRGV0G94F5ZC
type: plan
author_role: developer
status: escalate
schema_version: 5
---

# PLAN: ADR-0021, этап 1 (б1) — документы вне рабочей копии кода и доступ ролей

## Подход
Код реализован (первая итерация — WIP-чекпоинт `cb433801` после таймаута
шага, вторая — доводка этого шага: `docs/stack.md`, приложения, PLAN).

- **Каталог документов** — `artifact_branch.docs_root(target)` =
  `.artel/projects/<проект>/`, `docs_dir(id, target)` = `…/tasks/<id>/`
  (для артели тоже). `runner.role_cwd` выкладывает туда документы из
  головы `refs/artifacts/<id>` (`materialize_task_dir`, с уборкой лишнего)
  и убирает `tasks/<id>/` из рабочей копии кода (`acceptance.drop_from_code_copy`).
- **Автокоммит шага** (`checkpoint._commit_external_step_artifacts`)
  читает каталог документов; `tasks/<id>/` рабочей копии кода убирается с
  записью журнала «документы задачи убраны из рабочей копии кода»; коммит
  только при реальном расхождении с головой (`_same_as_ref`) — нетронутая
  выкладка не заводит пустой коммит и не перефиксирует ссылку.
- **Сверка фиксации (AC-10, ANSWER-1 вариант а)**: если к концу шага голова
  ссылки ≠ `fixed_sha` (роль сдвинула ссылку мимо пульта),
  автокоммит не выполняется и чекпоинты не перефиксируют
  (`_record_step_fixation`, `_docs_ref_moved_past_pult`) — следующий
  старт шага останавливается штатным инцидентом целостности.
- **Доступ роли**: `provider.command(model, docs_dir=…)`: claude —
  `--add-dir <каталог>` (до `--model`); codex — `--add-dir <каталог>`
  флагом подкоманды после `exec`, глобальные `--disable`/`-c` до неё. Cwd
  шага не меняется — рабочая копия кода. Миссия роли называет каталог
  документов буквальным путём (`role_prompt.docs_dir_note`); проверка
  обязательного артефакта смотрит в каталог документов.
- **`acceptance_tests/` только на время прогона**: контекст-менеджер
  `acceptance.plank_in_code_copy` (выкладка + уборка в `finally`) в
  `advance_gates/acceptance._acceptance_run_refuses` (через `ExitStack`
  — все ранние возвраты и исключения), `fsm_advance._review_approved`
  (автогейт), `amend._check_code_head_long_lived`; в
  `fsm_advance.tests_writing` — уборка в `finally` вокруг гейтов сухого
  сбора. Главная копия пульта (`config.ROOT`) уборкой не трогается.
- **Защищённые пути** (инвариант 21, `tests/test_invariants.py`,
  `skills/`) — только приложениями ниже; в ветке они не правлены.

Сверка `codex exec --add-dir` для 0.155.1: запустить `codex exec --help`
в шаге нельзя (CLI роли не разрешён), журнал изменений вендора тоже
недоступен (сеть закрыта). Флаг подтверждён Оператором для 0.157.1
(«Материалы» SPEC); по моим сведениям `--add-dir` у `codex exec`
появился задолго до линии 0.15x, но для 0.155.1 это не проверено — вопрос
2 эскалации.

## Шаги
1. Каталог документов и выкладка в него на старте шага; уборка
   `tasks/<id>/` из рабочей копии кода (`artifact_branch.py`,
   `runner.py`, `acceptance.py`).
2. Автокоммит из каталога документов, коммит только при изменении,
   отказ перефиксации при ссылке, сдвинутой мимо пульта (`checkpoint.py`).
3. `--add-dir` у обоих провайдеров, миссия с путём каталога,
   обязательный артефакт из каталога (`providers/base.py`, `claude.py`,
   `codex.py`, `role_prompt.py`, `runner.py`).
4. `acceptance_tests/` в рабочей копии только на время прогона
   (`acceptance.py`, `advance_gates/acceptance.py`, `fsm_advance.py`,
   `amend.py`).
5. `docs/stack.md`: абзац «Каталог документов задачи» в разделе
   провайдера, `command(model, docs_dir)`, пункт песочницы codex с
   `codex exec --add-dir`, строка «Файлы вне рабочего каталога» таблицы
   паритета — `--add-dir` в обеих ячейках.
6. Тесты: свои сторожа `tests/test_docs_dir_layout.py`; перенос путей
   фикстур существующих тестов (перечень в «Влиянии на систему»).
7. Приложения: инвариант 21, `tests/test_invariants.py`, два абзаца
   `skills/`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 3 |
| 3 | 4 |
| 4 | 2 (сверка фиксации), гейты лока и перечня — без изменений |
| 5 | 5 |
| 6 | 7 |
| 7 | 6 |

## Влияние на систему
- Гейты не ослаблены: лок `acceptance_tests/` и перечень сумм читаются из
  ссылки/коммита лока, как раньше (планка AC-10 зелёная); сверка
  фиксации усилена — роль, сдвинувшая ссылку, больше не «узаконивается»
  перефиксацией чекпоинта.
- Прогоны тестов этого шага (все зелёные, `python3 -m pytest … -p
  no:cacheprovider -p timeout -o timeout=120`):
  планка `test_docs_dir_step.py`, `test_plank_only_during_run.py`,
  `test_docs_dir_lock.py`, `test_docs_dir_integrity.py`,
  `test_stack_doc_docs_dir.py` + долгоживущий
  `tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py` — 13 passed;
  `test_docs_dir_layout`, `test_01m3vfyp…_pult_commit`,
  `test_01m3y857…_required_artifact`, `test_01m3ychs…_task_model_set`,
  `test_agent_failure`, `test_agent_log`, `test_agent_prompt`,
  `test_artifact_materialization`, `test_checkpoint_external_step_artifacts`,
  `test_guard_task_root_subdirectory` — 148 passed;
  `test_doctor`, `test_long_lived_step_end_to_end`, `test_multitarget`,
  `test_review_package`, `test_runner_model_preflight`,
  `test_runner_role_model`, `test_step_cost`, `test_timeout_checkpoint`,
  `test_providers`, `test_providers_codex`, `test_step_autocommit` — 534
  passed; `test_amend*`, `test_acceptance_tests_flow`,
  `test_long_lived_transitions`, `test_pull_long_lived_plank`,
  `test_fsm_advance_tests_writing_*`, `test_role_prompt_test_author_mission`,
  `test_01m3vfyp…_role_missions`, `test_artifact_ref_sync`,
  `test_git_fixation`, `test_fsm_autogate*`, `test_pull` — 261 passed;
  `test_stack*`, `test_stack_parity_table` — 51 passed;
  `test_invariants.py` + `test_multitarget_invariants.py` С ПРИЛОЖЕНИЯМИ
  ниже — 78 passed.
- Приложения проверены `git apply --check` на чистом дереве ветки (все
  четыре подряд) — применяются.
- Существующие тесты, изменённые по ADR-0021 (документы роли теперь в
  каталоге документов, не в `.artel/worktrees/<id>/tasks/<id>/`). Ни один
  метод не удалён и не переименован; гейт неослабления находок не даёт
  (`test_integrity.findings` -> пусто). Только пути фикстур/сидов (без
  правки утверждений): `test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py`
  (`write_plan_escalate`), `test_01m3y8570h9y57ytp3m7e1amhg_required_artifact.py`
  (`run_step`), `test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`,
  `test_agent_failure.py`, `test_agent_log.py`, `test_agent_prompt.py`,
  `test_artifact_materialization.py`, `test_checkpoint_external_step_artifacts.py`,
  `test_doctor.py`, `test_guard_task_root_subdirectory.py`,
  `test_long_lived_step_end_to_end.py`, `test_multitarget.py`,
  `test_runner_model_preflight.py`, `test_runner_role_model.py`,
  `test_step_cost.py`. `test_step_autocommit.py::CommitStepArtifactsTest::
  test_dirty_tree_commits_to_artifact_branch_and_journals` — прежнее
  утверждение сохранено, добавлено новое (каталог документов тоже убран),
  метод получил докстринг с заявкой мутации (временной мутацией в этом
  шаге не проверялся; сторожа `tests/test_docs_dir_layout.py` написаны
  на шаге 1, их мутационная проверка в этом шаге тоже не повторялась).
  Заменённые утверждения (нужен мандат — вопрос 1):
  - `tests/test_timeout_checkpoint.py::CommitAbnormalCheckpointTest::test_materialized_spec_is_absent_from_the_code_branch_after_abnormal_end`,
    `tests/test_timeout_checkpoint.py::CommitPauseNowCheckpointTest::test_materialized_spec_is_absent_from_the_code_branch_after_pause_now`,
    `tests/test_timeout_checkpoint.py::RoleCwdMaterializationSurvivesTimeoutCheckpointTest::test_materialized_spec_is_absent_from_the_code_branch_after_timeout`
    — было `assertTrue((wt/"tasks"/id/"SPEC.md").exists())`, стало
    `assertTrue((docs_dir(id)/"SPEC.md").exists())`: SPEC требование 1/3
    (документы выкладываются в каталог документов, в рабочей копии их
    нет). Главное утверждение методов (SPEC не попадает в кодовую ветку)
    не тронуто.
  - `tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package`
    — ожидаемый список вызовов git дополнен хвостом автокоммита PLAN.md
    из каталога документов (прежние элементы сохранены, порядок тот же):
    SPEC требование 1 (правка роли в каталоге документов забирается
    автокоммитом шага; раньше маркер, положенный тестом в
    `self.tdir`, автокоммит не видел).
- Откат: revert merge-коммита задачи; приложения — тем же merge.

## Риски
- Курируемый HOME роли (`.artel/home/.claude/CLAUDE.md`, референс
  `docs/reference/role-home/claude/CLAUDE.md`, правило Оператора 05.09)
  велит писать артефакты ОТНОСИТЕЛЬНЫМИ путями `tasks/<id>/…` от
  рабочего каталога и запрещает абсолютные. После мержа такой путь ляжет
  в рабочую копию кода и будет убран пультом — артефакт шага потерян.
  Миссия шага называет каталог документов явно, но правило HOME ему
  противоречит. Путь вне зон задачи — вопрос 3.
- `--add-dir` codex 0.155.1 не проверен исполнением — вопрос 2.
- Роли на старой выкладке после мержа: шаг, начавшийся на старом коде,
  оставит `tasks/<id>/` в рабочей копии — следующий старт его уберёт;
  сам `tasks/<id>/` старого шага автокоммит больше не читает (переход
  при пустом конвейере, ADR-0021 п.13).

## Предложения системе
- Шаг developer этой задачи упал по таймауту, не написав PLAN.md: при
  крупной задаче PLAN стоит писать первым действием (хотя бы черновик) —
  `skills/coding-standards.md` об этом молчит.
- Сторож роли (`conftest.py`) отказывает `pytest -n` по списку модулей
  как «полному прогону» — ускорение по модулям в шаге недоступно.

## Приложение 1: инвариант 21 (docs/invariants.md)

```diff
diff --git a/docs/invariants.md b/docs/invariants.md
index b674ca24..fbaf7fbd 100644
--- a/docs/invariants.md
+++ b/docs/invariants.md
@@ -48,7 +48,7 @@ docs/adr/0002-integrity-principle.md, CLAUDE.md.
 | 18 | Автоматизация механических команд не проходит гейты: `auto` не вызывает `approve`/`reject` и пути мимо гейта не имеет | `test_auto_cycle.AutoNeverPassesAGateTest` | design §4; tasks/T014/SPEC.md, требование 3 |
 | 19 | Merge требует зелёного CI головного коммита ветки задачи; не-зелёный, **неизвестный** и **неполный** (проверок меньше, чем обещает `total_count`) статус merge не выполняют | `test_invariants.MergeNeedsGreenCiTest`; разбор статуса — `test_ci_status.BranchStatusTest`, полнота ответа — `test_ci_status.PaginationTest` | design §4 (guards неотключаемы); tasks/T017/SPEC.md, требование 6; tasks/T018/SPEC.md, требования 1–3 |
 | 20 | Артефакты и логи внешнего target не появляются в рабочем дереве пульта ни на одном переходе FSM (`.artel/` — `.gitignore` пульта целиком) | `test_multitarget_invariants.PultArtifactIsolationTest` | ADR-0003 3д; tasks/T020/SPEC.md, требование 1 |
-| 21 | Рабочий каталог роли внешнего target — только `.artel/projects/<target>/workspace/`; окружение процесса не содержит путей и конфигов пульта сверх явно переданного (HOME/CLAUDE_CONFIG_DIR) | `test_multitarget_invariants.ExternalWorkspaceIsolationTest` | ADR-0003 §4, п.14; tasks/T020/SPEC.md, требование 2 |
+| 21 | Рабочий каталог роли внешнего target — только `.artel/projects/<target>/workspace/`; на запись роли дополнительно открыт только каталог документов задачи `.artel/projects/<target>/tasks/<id>/` (`--add-dir` у claude и у `codex exec`, ADR-0021 этап 1), документы задачи в рабочей копии кода вне прогона приёмки не лежат; окружение процесса не содержит путей и конфигов пульта сверх явно переданного (HOME/CLAUDE_CONFIG_DIR) | `test_multitarget_invariants.ExternalWorkspaceIsolationTest` | ADR-0003 §4, п.14; tasks/T020/SPEC.md, требование 2 |
 | 22 | Нумерация задач независима per-target; операции по `task_id` (журнал, spend, kill) одного target не читают и не меняют строки другого | `test_multitarget_invariants.CrossTargetDbIsolationTest` | ADR-0003 3ж; tasks/T020/SPEC.md, требование 3 |
 | 23 | Пороги суммарного расхода программы (70%/90%) считаются суммой `spent_usd` по всем задачам ВСЕХ target, не одного | `test_multitarget_invariants.ProgramSpendAcrossTargetsTest` | roadmap §5; ADR-0003 3ж; tasks/T020/SPEC.md, требование 4 |
 | 24 | Счётчик номеров задач target не переиспользует номер архивированной (не удалённой) строки при пересеве после reconnect | `test_multitarget_invariants.CounterSurvivesArchivalOnReconnectTest` | ADR-0003 3ж («архивация строк, никогда DELETE»); tasks/T020/SPEC.md, требование 5 |
```

## Приложение 2: tests/test_invariants.py — каталог документов в песочнице FsmTest

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index dbd44a59..46434fe8 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -34,9 +34,9 @@ from unittest import mock
 
 sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
 
-from orchestrator import (artel, budget, catalog, ci, cleanup,  # noqa: E402
-                          config, fsm, fsm_advance, gitcmd, runner, stack,
-                          store)
+from orchestrator import (artel, artifact_branch, budget, catalog,  # noqa: E402
+                          ci, cleanup, config, fsm, fsm_advance, gitcmd,
+                          runner, stack, store)
 from orchestrator.advance_gates import test_integrity  # noqa: E402
 from scripts import guard  # noqa: E402
 from tests.sandbox import (FakeProc, SpyRun, TmpRootTest, _stub_check_stack,  # noqa: E402
@@ -163,7 +163,10 @@ class FsmTest(unittest.TestCase):
                             # worktree — та же логика, что и у ROLE_HOME
                             # выше: в песочницу, не в `.artel/worktrees/`
                             # репозитория (ROOT ниже намеренно реальный).
-                            ("WORKTREES", root / ".artel" / "worktrees")):
+                            ("WORKTREES", root / ".artel" / "worktrees"),
+                            # Каталог документов задачи (ADR-0021, этап 1)
+                            # выкладывает шаг роли — тоже в песочницу.
+                            ("PROJECTS", root / ".artel" / "projects")):
             patcher = mock.patch.object(config, attr, value)
             patcher.start()
             self.addCleanup(patcher.stop)
@@ -349,8 +352,11 @@ class FsmTest(unittest.TestCase):
         (`config.TASKS/<id>/`, откуда читает FSM/бриф через `disk_backed_
         show`): без файла именно здесь успешный (rc=0) прогон `run` честно
         ретраится вместо одного запуска, которого ждут тесты этого класса
-        (они проверяют лимитеры run, не факт отказа без артефакта)."""
-        tdir = config.WORKTREES / self.TASK / "tasks" / self.TASK
+        (они проверяют лимитеры run, не факт отказа без артефакта).
+
+        С ADR-0021 (этап 1) роль пишет документы в каталог документов
+        задачи (`artifact_branch.docs_dir`), не в рабочую копию кода."""
+        tdir = artifact_branch.docs_dir(self.TASK, config.DEFAULT_TARGET)
         tdir.mkdir(parents=True, exist_ok=True)
         (tdir / "PLAN.md").write_text("маркер\n", encoding="utf-8")
 
```

## Приложение 3: skills/conventions-core.md — где лежат документы задачи

```diff
diff --git a/skills/conventions-core.md b/skills/conventions-core.md
index e43a8d0f..28f07da8 100644
--- a/skills/conventions-core.md
+++ b/skills/conventions-core.md
@@ -18,11 +18,16 @@
   в T042 и повторно в T043 — за один и тот же урок заплатили дважды,
   потому что после первого раза его некуда было записать. Пустая секция
   и её отсутствие — оба валидны: копилка — приглашение, не повинность.
-- Каталог `tasks/<id>/` рабочего каталога роли материализуется заново на
-  старте КАЖДОГО шага из ГОЛОВЫ артефактной ветки (SPEC
+- Документы задачи (`tasks/<id>/`) лежат не в рабочем каталоге роли, а в
+  каталоге документов задачи `.artel/projects/<проект>/tasks/<id>/`
+  (ADR-0021, этап 1): он открыт роли на запись дополнительно к рабочему
+  каталогу, его точный путь называет миссия шага. Каталог материализуется
+  заново на старте КАЖДОГО шага из ГОЛОВЫ ссылки документов (SPEC
   01M1NKTF173WV5CPDZ1C3WW69K) — на диске всегда актуальная версия
   (в том числе правка Оператора на гейте между твоими шагами), отдельно
-  перечитывать её с диска после чужой правки не нужно.
+  перечитывать её с диска после чужой правки не нужно. `tasks/<id>/`,
+  записанный в рабочую копию кода, пульт убирает после шага, в ссылку он
+  не попадает.
 
 ## Git
 - Ветка задачи: `task/<id>-<slug>` от свежего main.
```

## Приложение 4: skills/test-authoring.md — где лежат документы задачи

```diff
diff --git a/skills/test-authoring.md b/skills/test-authoring.md
index 07d4a5fa..69f91375 100644
--- a/skills/test-authoring.md
+++ b/skills/test-authoring.md
@@ -129,8 +129,10 @@ guard разбирает её текстом, без импорта файлов
 Источник артефактов задачи в планке: только артефактная ветка через
 `gitcmd.show(artifact_branch.branch_name(TASK_ID), "tasks/<id>/PLAN.md")`;
 диск рабочей копии — не источник, пульт материализует только
-`acceptance_tests/`. В worktree `tasks/<id>/` лежит целиком, а в среде
-прогона гейта (`orchestrator/pull.py`, `orchestrator/acceptance.py::
+`acceptance_tests/`. В каталоге документов задачи
+(`.artel/projects/<проект>/tasks/<id>/`, ADR-0021 этап 1) `tasks/<id>/`
+лежит целиком, в рабочей копии кода его нет, а в среде прогона гейта
+(`orchestrator/pull.py`, `orchestrator/acceptance.py::
 materialize_from_branch`) — один `acceptance_tests/`: тест, читающий
 `PLAN.md`/`SPEC.md`/`REVIEW.md` через `Path(__file__)…/"PLAN.md"`,
 `open(`, `.read_text(`, `os.path.join`, `os.path.exists` по пути,
```

## Эскалация

**Вопросы** (по блокирующести):

1. Мандат на замену утверждений в четырёх существующих методах
   (перечень и основание — «Влияние на систему»). Варианты: (а) дать
   мандат строкой ANSWER
   `Ослабление тестов разрешено: tests/test_timeout_checkpoint.py::CommitAbnormalCheckpointTest::test_materialized_spec_is_absent_from_the_code_branch_after_abnormal_end, tests/test_timeout_checkpoint.py::CommitPauseNowCheckpointTest::test_materialized_spec_is_absent_from_the_code_branch_after_pause_now, tests/test_timeout_checkpoint.py::RoleCwdMaterializationSurvivesTimeoutCheckpointTest::test_materialized_spec_is_absent_from_the_code_branch_after_timeout, tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package`;
   (б) отказать — тогда эти методы останутся красными, задача не
   сдаётся. Дефолт: (а).
2. `codex exec --add-dir` в 0.155.1 (SPEC требование 2): в шаге не
   проверить. Варианты: (а) Оператор проверяет `codex exec --help` на
   0.155.1 (или принимает проверку 0.157.1) и подтверждает; (б) флаг
   отсутствует — тогда нужен подъём `min_cli_version` (в «Не входит»
   SPEC) отдельным решением. Дефолт: (а), считать флаг доступным.
3. Правило HOME роли «пиши `tasks/<id>/…` относительным путём»
   (`docs/reference/role-home/claude/CLAUDE.md`, вне зон задачи)
   противоречит выносу документов. Варианты: (а) Оператор правит
   референс и `.artel/home` в момент мержа (замена на «пиши по пути
   каталога документов из миссии шага»); (б) расширить зоны задачи на
   `docs/reference/role-home/` — разработчик правит сам. Дефолт: (а).

**Контекст**: код, документ стека, сторожа и приложения готовы; планка
(кроме AC-12, читающей PLAN из ссылки после автокоммита этого шага) и
долгоживущий файл зелёные, затронутые модули зелёные (перечень выше).

**Блокирует**: сдачу `ready` — переход `in_dev -> verifying` (п.1 —
правило неослабления скила; п.2 — сверка из SPEC требования 2; п.3 —
работоспособность шагов ролей после мержа).
