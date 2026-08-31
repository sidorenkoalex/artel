---
task: T083
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: Тестовая подметалка — уборка git-песочниц и изоляция от реального git

## Подход
Обе части — один класс дефекта «песочница тестов ведёт себя не по
прописанному», обе правки строго в `tests/`.

**Часть 1 (AC-1).** Уборка `tempfile.TemporaryDirectory()` с настоящим
git внутри падает `OSError: [Errno 39] Directory not empty` при удалении
`.git` на некоторых раннерах (гонка ФС между записью git-объекта и
`rmtree` того же каталога). Фикс — один общий хелпер в `tests/sandbox.py`
(`resilient_tmp_cleanup`): повтор `tmp.cleanup()` при `OSError(ENOTEMPTY)`,
финальная страховка `shutil.rmtree(..., ignore_errors=True)`, если повтор
не помог. `tests.sandbox.TmpRootTest.setUp` переключается на него сразу
для всех своих наследников. Отдельно нашлось **десять** мест в `tests/`,
которые держат СВОЮ копию `tempfile.TemporaryDirectory()` + голый
`self.addCleanup(tmp.cleanup)` в обход `TmpRootTest` (наследуют его ради
методов вроде `_patched_path`, но переопределяют `setUp` целиком, либо не
наследуют вовсе) — все переводятся на тот же `resilient_tmp_cleanup`, а
не отдельные локальные фиксы (принцип «чини класс, не экземпляр»,
`coding-standards`).

**Часть 2 (AC-2).** `tests/test_spec_budget.py::LegacyDbMigrationTest`
наследует `SpecBudgetOnTheGateTest`, но переопределяет `setUp` и патчит
только `DB`/`TASKS`/`LOGS` — `ROOT`/`WORKTREES`/`gitcmd.git` остаются
непропатченными. Унаследованные тестовые методы зовут `fsm.cmd_advance`,
который на `spec_writing` безусловно читает `gitcmd.on_foreign_branch` —
с непропатченным `ROOT` это самый настоящий `subprocess.run(["git", ...],
cwd=<реальный корень пульта>)`. Фикс — та же связка патчей, что уже несёт
`SpecBudgetOnTheGateTest.setUp` (`ROOT`, `WORKTREES`, `gitcmd.git = fake_git`),
добавленная в `LegacyDbMigrationTest.setUp`.

Поведение боевого кода не трогается нигде — оба фикса меняют только
подготовку тестовых песочниц.

## Шаги

1. `tests/sandbox.py`: добавить `resilient_tmp_cleanup(tmp)` — повтор
   `tmp.cleanup()` на `OSError` с `errno.ENOTEMPTY`, затем
   `shutil.rmtree(tmp.name, ignore_errors=True)`; `TmpRootTest.setUp`
   регистрирует его вместо голого `tmp.cleanup` (закрывает AC-1 для
   `ExternalTransitionCommitsTest`/`ExternalApproveDoesNotCommitOthers
   WorkInProgressTest` и всех прочих наследников `TmpRootTest`).

2. Перевести на `sandbox.resilient_tmp_cleanup` все найденные копии
   `tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)`
   с настоящим git внутри, что не проходят через `TmpRootTest.setUp`:
   - `tests/test_git_fixation.py::RealPultGitTest` (+ 4 дочерних сценарных
     класса — фикс через базовый `setUp`);
   - `tests/test_multitarget_invariants.py::PultArtifactIsolationTest`;
   - `tests/test_gitcmd_branch_reads.py::RealGitSandbox`;
   - `tests/test_fsm_branch_correct_status_reads.py::RealGitBranchTest`;
   - `tests/test_answer_branch_reads.py::RealGitSandbox`;
   - `tests/test_workspace.py::RealGitWorkspaceTest`;
   - `tests/test_kill_cleanup.py::TmpRepoTest`;
   - `tests/test_done_branch_cleanup.py::DropMergedTaskBranchTest`;
   - `tests/test_acceptance_tests_flow.py::LockTest`;
   - `tests/test_invariants.py::KillKeepsMainIntactTest.fresh_repo`
     (использует `ExitStack.enter_context`, а не голый `addCleanup` —
     переводится на `self.repo.callback(sandbox.resilient_tmp_cleanup, tmp)`
     с тем же хелпером).

3. `tests/test_spec_budget.py::LegacyDbMigrationTest.setUp`: добавить
   патчи `ROOT`/`WORKTREES` на временный каталог и `gitcmd.git` на
   `fake_git` — той же связкой, что уже есть в `SpecBudgetOnTheGateTest.
   setUp` (закрывает AC-2).

4. Прогон полного `tests/` в изолированной копии репозитория с
   посторонними ветками/worktree (ровно постановка приёмочного AC-3) —
   подтвердить 0 падений; прогон приёмочных тестов `tasks/T083/
   acceptance_tests/`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (устойчивая уборка, одно общее место) | 1, 2 |
| 2 (перевод на fake_git классов-родственников T047) | 3 |
| 3 (полный набор зелёный, независим от реального git) | 1, 2, 3, 4 |
| 4 (боевой код не меняется) | 1, 2, 3 (все правки — только tests/) |

## Влияние на систему
Правки ограничены `tests/sandbox.py` и десятком тестовых файлов —
`orchestrator/`/`scripts/` не затрагиваются (AC-4, проверяется механически
приёмочным тестом на диффе против `main`). Риск регрессии — только в самих
тестах: `resilient_tmp_cleanup` меняет ТОЛЬКО путь уборки временного
каталога (что происходит после того, как тестовые ассерты уже отработали),
поведение самого сценария не меняется; на «здоровом» прогоне (без
инъекции `OSError`) `tmp.cleanup()` отрабатывает с первой попытки — цикл
не выполняет лишней работы. Патчи `ROOT`/`WORKTREES`/`gitcmd.git` в
`LegacyDbMigrationTest` — копия уже существующей и проверенной связки из
`SpecBudgetOnTheGateTest`, не новая механика.

Существующие тесты/гейты/лимиты не ослабляются: `resilient_tmp_cleanup`
не глотает произвольные ошибки уборки — только конкретный `OSError`
с `errno.ENOTEMPTY`, всё остальное продолжает падать как раньше (ошибка
уборки по другой причине — сигнал, не шум, который стоит маскировать).
Откат — вернуть `self.addCleanup(tmp.cleanup)` и патчи `LegacyDbMigrationTest.
setUp` к исходному виду; ничего вне `tests/` откатывать не требуется.

## Риски
- Список из шага 2 составлен ручным разбором `tests/*.py` на паттерн
  `tempfile.TemporaryDirectory()` + `git("init"...)` в обход
  `TmpRootTest.setUp` — если после этой задачи в `tests/` появится новая
  копия того же паттерна, приёмочные тесты T083 её не поймают (они
  зафиксированы на конкретных классах из фактуры SPEC).
- Приёмочный тест AC-3 тяжёлый (копирует дерево, гоняет полный `tests/`
  подпроцессом, ~2 минуты) — ожидаемо по докстрингу приёмочного теста,
  не признак поломки.
