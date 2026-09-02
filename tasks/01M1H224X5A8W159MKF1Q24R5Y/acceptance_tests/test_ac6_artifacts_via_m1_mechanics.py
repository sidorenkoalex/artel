"""AC-6: `fixation.py`, `checkpoint.py`, `cleanup.py`, `runner.py`
(`role_cwd`), `fsm.py`/`fsm_advance.py`/`fsm_merge_gate.py` для НОВОЙ
задачи артели читают и пишут артефакты через артефактную ветку пульта и
снапшот-механику M1 (та же, что для любого внешнего target), не через
прямую запись в её ветку задачи. Дефолт `target` в схеме `store.py` не
меняется — историческая обратная совместимость (задачи без явного target
в БД) сохраняется.

Пять под-систем ниже — прямые вызывающие места из требования 2 SPEC,
проверенные напрямую (юнит-уровень), без прогона через полный FSM
(сквозной сценарий — `test_ac7_full_scenario_no_pult_writes.py`):

- `orchestrator/artifact_source.py::resolve` — единственная точка
  решения «self или артефактная ветка» (докстринг модуля прямо называет
  её общей для `fsm.py`/`fsm_advance.py`/`acceptance.py`/`brief.py`).
- `orchestrator/fixation.py::fix` — фиксация sha на переходах.
- `orchestrator/checkpoint.py::commit_step_artifacts` — автокоммит
  артефактов шага роли.
- `orchestrator/cleanup.py::_publish_snapshot_if_pending` (через
  публичный `cleanup.cmd_kill`) — снапшот закрытия в `refs/artifacts/<id>`.
- `orchestrator/runner.py::role_cwd` — рабочий каталог роли.

Красен до реализации: каждая из пяти несёт сегодня явную ветку `target ==
config.DEFAULT_TARGET` (или `target != config.DEFAULT_TARGET` —
зеркально), отдающую артели прежний однобраншевый путь вместо
generic-механики M1; конкретная мутация названа в докстринге каждого
теста.
"""
import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import (artifact_branch, artifact_source, catalog,  # noqa: E402
                          checkpoint, cleanup, config, fixation, gitcmd,
                          runner, store)
from tests.sandbox import RealGitSandbox, resilient_tmp_cleanup  # noqa: E402
import tempfile  # noqa: E402

ARTEL_TARGETS_YAML = """targets:
  artel:
    forge: github
    url: https://example.invalid/artel
    base: main
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


class ArtelM1Sandbox(RealGitSandbox):
    """Пульт (`self.root`) с `origin` (bare) — «главная копия артели» и
    «origin артели» из ANSWER-1/требования 3 — тот же приём, что уже
    заведён в `_sandbox.py::ArtelSelfTargetSandbox` (WIP-чекпоинт этой же
    задачи), продублирован здесь минимально, чтобы этот файл не зависел
    от AC-8/9/12-специфичных хелперов соседнего модуля."""

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(ARTEL_TARGETS_YAML, encoding="utf-8")
        bare_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, bare_tmp)
        self.origin = Path(bare_tmp.name) / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b",
                        config.MAIN_BRANCH, str(self.origin)],
                       check=True, capture_output=True, text=True)
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)


class ArtifactSourceResolvesToArtifactBranchTest(ArtelM1Sandbox):

    def test_ac6_artifact_source_resolve_points_at_artifact_branch_for_artel(self):
        """`artifact_source.resolve(conn, task_id)` задачи с `target="artel"`
        обязана вернуть `(artifact_branch.branch_name(task_id), True)` —
        тот же ответ, что и для любого внешнего target, а не имя кодовой
        ветки задачи с `foreign`, вычисленным по чекауту пульта.

        Ловит мутацию: условие `if target != config.DEFAULT_TARGET` в
        `artifact_source.resolve` — тогда для 'artel' вернётся
        `(store.task_branch(...), gitcmd.on_foreign_branch(...))`, не
        имя артефактной ветки.
        """
        task_id = "01ARTELSOURCERESOLVE01"
        store.insert_task(store.db(), task_id, "Задача артели", "in_dev",
                          f"task/{task_id.lower()}", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

        branch, foreign = artifact_source.resolve(store.db(), task_id)

        self.assertEqual(branch, artifact_branch.branch_name(task_id))
        self.assertTrue(foreign)


class FixationUsesArtifactRepoForArtelTest(ArtelM1Sandbox):

    def test_ac6_fix_commits_the_artel_artifact_repo_not_the_task_branch(self):
        """`fixation.fix(task_id, "artel")` обязана закоммитить
        `.artel/projects/artel/` целиком (путь `_fix_external`) — так,
        чтобы незакоммиченная правка ИМЕННО там попала в sha фиксации, а
        не проверять чистоту кодовой ветки задачи в `config.ROOT`.

        Ловит мутацию: `if target == config.DEFAULT_TARGET: return
        _fix_dogfood(task_id)` в `fixation.fix` — тогда для 'artel'
        вызовется `_fix_dogfood`, которая коммитить артефактный репозиторий
        не станет вовсе (`.artel/projects/artel/` даже не существует
        сегодня для 'artel'), и `sha`/`clean` придут с пустой строкой или
        от чужого места.
        """
        task_id = "01ARTELFIXEXTERNAL0001"
        store.insert_task(store.db(), task_id, "Задача артели", "in_dev",
                          f"task/{task_id.lower()}", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        repo = config.PROJECTS / config.DEFAULT_TARGET
        repo.mkdir(parents=True)
        gitcmd.in_repo(repo, "init", "-q")
        (repo / "tasks").mkdir()
        (repo / "tasks" / "marker.txt").write_text("артефакт\n", encoding="utf-8")

        sha, clean = fixation.fix(task_id, config.DEFAULT_TARGET)

        self.assertNotEqual(sha, "")
        self.assertTrue(clean)
        head_in_artifact_repo = gitcmd.head_sha(repo)
        self.assertEqual(sha, head_in_artifact_repo,
                         "fix() обязана коммитить и вернуть sha именно "
                         "артефактного репо артели")


class CheckpointCommitsToArtifactBranchForArtelTest(ArtelM1Sandbox):

    TASK = "01ARTELCHECKPOINTSTEP1"

    def setUp(self):
        super().setUp()
        store.insert_task(store.db(), self.TASK, "Задача артели", "in_dev",
                          f"task/{self.TASK.lower()}-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.workspace_root = config.PROJECTS / config.DEFAULT_TARGET / "workspace"
        self.task_dir = self.workspace_root / "tasks" / self.TASK
        self.task_dir.mkdir(parents=True)

    def artifact_branch_files(self) -> list:
        return gitcmd.ls_tree_files(
            artifact_branch.branch_name(self.TASK), f"tasks/{self.TASK}") or []

    def test_ac6_role_step_artifacts_of_an_artel_task_land_in_artifact_branch(self):
        """Роль пишет `PLAN.md` в свой рабочий каталог (`.artel/projects/
        artel/workspace/tasks/<id>/`) — `checkpoint.commit_step_artifacts`
        обязана перенести его в артефактную ветку пульта `artifact/<id>` и
        убрать исходник, тем же путём, что уже работает для любого
        внешнего target (`test_checkpoint_external_step_artifacts.py`).

        Ловит мутацию: `if target != config.DEFAULT_TARGET: return
        _commit_external_step_artifacts(...)` в `commit_step_artifacts` —
        тогда для 'artel' сработает self-ветка `_commit_worktree_change`,
        которая ищет `workspace.path(task_id)` (worktree кодовой ветки —
        artel-задача, заведённая под M1, такого worktree не имеет), и
        `PLAN.md` в артефактную ветку не попадёт.
        """
        (self.task_dir / "PLAN.md").write_text("план\n", encoding="utf-8")

        detail = checkpoint.commit_step_artifacts(store.db(), self.TASK,
                                                   "developer")

        self.assertIn(f"tasks/{self.TASK}/PLAN.md", self.artifact_branch_files())
        self.assertFalse(self.task_dir.exists(),
                         "tasks/<id>/ обязан быть убран из рабочего "
                         "каталога роли после переноса в артефактную ветку")
        self.assertNotEqual(detail, "")


class RoleCwdUsesProjectsWorkspaceForArtelTest(ArtelM1Sandbox):

    def test_ac6_role_cwd_returns_projects_workspace_not_a_task_worktree(self):
        """`runner.role_cwd(conn, task_id, "artel")` обязана вернуть
        `.artel/projects/artel/workspace/` (тот же путь, что для любого
        внешнего target) — не заводить/возвращать git-worktree кодовой
        ветки задачи (`workspace.ensure`).

        Ловит мутацию: `if target == config.DEFAULT_TARGET: ... return
        wt_path` в `role_cwd` — тогда для 'artel' будет вызван
        `workspace.ensure(task_id, branch)`, заводящий worktree
        `.artel/worktrees/<id>/`, а не `.artel/projects/artel/workspace/`.
        """
        task_id = "01ARTELROLECWDTASK0001"
        store.insert_task(store.db(), task_id, "Задача артели", "in_dev",
                          f"task/{task_id.lower()}", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

        cwd = runner.role_cwd(store.db(), task_id, config.DEFAULT_TARGET)

        self.assertEqual(cwd, config.PROJECTS / config.DEFAULT_TARGET / "workspace")
        self.assertFalse((config.WORKTREES / task_id).exists(),
                         "role_cwd не должна заводить worktree кодовой "
                         "ветки для артели")


class KillPublishesSnapshotForArtelTest(ArtelM1Sandbox):

    def test_ac6_kill_publishes_a_snapshot_ref_for_a_new_artel_task(self):
        """`cleanup.cmd_kill` НОВОЙ задачи артели публикует снапшот в
        `refs/artifacts/<id>` артели (`self.origin` — главная копия
        артели на фордже, ANSWER-1) — тем же порядком, что уже
        сегодня работает для любого внешнего target
        (`tasks/T094/acceptance_tests/test_ac13_ac14_snapshot_on_close.py`).

        Ловит мутацию: `if target == config.DEFAULT_TARGET or is_canary:
        return` в начале `cleanup._publish_snapshot_if_pending` — тогда
        `killed` артели молча пропускает публикацию снапшота, и
        `refs/artifacts/<id>` в `self.origin` не появится вовсе.
        """
        task_id = catalog.cmd_new("Задача артели на снапшот")

        cleanup.cmd_kill(task_id)

        ref = subprocess.run(
            ["git", "-C", str(self.origin), "show-ref", "--verify", "--quiet",
             f"refs/artifacts/{task_id}"], capture_output=True, text=True)
        self.assertEqual(ref.returncode, 0,
                         f"refs/artifacts/{task_id} не найден в origin "
                         f"артели после kill")


if __name__ == "__main__":
    unittest.main()
