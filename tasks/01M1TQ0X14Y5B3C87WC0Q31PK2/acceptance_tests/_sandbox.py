"""Общая песочница приёмочных тестов 01M1TQ0X14Y5B3C87WC0Q31PK2 (отказ push
артефактной ветки в журнал/на повтор; doctor сверяет локальный ref с
origin и CI артефактной ветки).

`PultOriginSandbox` расширяет `tests.sandbox.RealGitSandbox` (`self.root`
— пульт, реальный git-репозиторий с `main`) добавкой bare-репозитория,
играющего роль `origin` САМОГО ПУЛЬТА (инцидент 06.09, SPEC «Контекст»:
расхождение происходит между локальным `refs/heads/artifact/<id>` пульта
и его же origin — не origin внешнего target, как в `_sandbox.py`
соседних задач вроде T094). `add_origin()` — отдельным вызовом, не в
`setUp`: сценарии AC-1/AC-2 («нет origin») нужны ИМЕННО без него.

`push_external_commit` имитирует коммит Оператора прямо в origin в обход
пульта (тот самый инцидент) — клонирует `self.bare` во временный каталог,
коммитит и пушит обратно, не трогая рабочую копию/индекс `self.root`
вовсе, тем же приёмом, что уже проверяет `tests/test_gitcmd_branch_reads.
py::RemoteBranchShaTest`.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import artifact_branch, config, gitcmd, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

EXTERNAL_TARGET = "extproj"


class PultOriginSandbox(RealGitSandbox):

    def add_origin(self) -> str:
        """Заводит `self.bare` и подключает его как `origin` пульта."""
        self.bare = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.bare, ignore_errors=True)
        self.git("init", "-q", "--bare", self.bare)
        self.git("remote", "add", "origin", self.bare)
        return self.bare

    def origin_branch_sha(self, branch: str) -> str:
        """sha `branch` в `self.bare` напрямую (не через `gitcmd`, чтобы не
        зависеть от функции, чьё поведение как раз проверяет тест)."""
        out = subprocess.run(
            ["git", "ls-remote", self.bare, f"refs/heads/{branch}"],
            capture_output=True, text=True, check=True).stdout
        return out.split()[0] if out.strip() else ""

    def push_external_commit(self, task_id: str, rel: str, text: str) -> None:
        """Коммит в `self.bare` В ОБХОД пульта — тем же способом, каким
        Оператор 06.09 разошёлся с локальным ref (SPEC «Контекст»)."""
        branch = artifact_branch.branch_name(task_id)
        scratch = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        subprocess.run(["git", "clone", "-q", self.bare, scratch], check=True)
        subprocess.run(["git", "-C", scratch, "checkout", "-q", branch],
                       check=True)
        subprocess.run(["git", "-C", scratch, "config", "user.email",
                        "operator@example.invalid"], check=True)
        subprocess.run(["git", "-C", scratch, "config", "user.name",
                        "operator"], check=True)
        path = Path(scratch) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        subprocess.run(["git", "-C", scratch, "add", "-A"], check=True)
        subprocess.run(["git", "-C", scratch, "commit", "-q", "-m",
                        "внешний коммит Оператора"], check=True)
        subprocess.run(["git", "-C", scratch, "push", "-q", "origin", branch],
                       check=True)

    def new_external_task(self, task_id: str, state: str = "in_dev",
                          target: str = EXTERNAL_TARGET) -> Path:
        """Задача внешнего target с пустым `tasks/<id>/` рабочим каталогом
        клона роли (тот же приём, что `tests/test_checkpoint_external_
        step_artifacts.py`) — возвращает этот каталог."""
        store.insert_task(store.db(), task_id, "Задача", state,
                          f"task/{task_id.lower()}-x", target,
                          config.DEFAULT_BUDGET_USD)
        workspace_root = config.PROJECTS / target / "workspace"
        task_dir = workspace_root / "tasks" / task_id
        task_dir.mkdir(parents=True)
        return task_dir

    def new_artel_task(self, task_id: str, state: str = "in_dev") -> str:
        """Задача target `config.DEFAULT_TARGET` (артель) БЕЗ рабочего
        каталога — doctor-проверки AC-6/AC-7 читают только git-ветки/gh,
        рабочий каталог роли им не нужен. Возвращает имя артефактной
        ветки."""
        store.insert_task(store.db(), task_id, "Задача", state,
                          f"task/{task_id.lower()}-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        return artifact_branch.branch_name(task_id)

    def push_dir(self, task_dir: Path, task_id: str, rel: str,
                text: str) -> None:
        path = task_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def journal_rows(self, task_id: str) -> list:
        return store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (task_id,)).fetchall()


class DivergedArtifactBranchSandbox(PultOriginSandbox):
    """Общий сценарий AC-4/AC-5 (`test_ac4_push_never_uses_force.py`,
    `test_ac5_non_fast_forward_journal_names_both_sha.py`): origin —
    настоящий bare-репозиторий, разошедшийся с локальным ref РОВНО так,
    как описывает SPEC «Контекст» (инцидент 06.09) — коммит Оператора
    уходит в origin в обход пульта (`push_external_commit`), затем
    локальный автокоммит следующего шага роли не знает о нём и пытается
    push поверх — non-fast-forward. `setUp` доводит песочницу до момента
    ПЕРЕД этим вторым автокоммитом; `self.origin_sha_before` — sha origin
    сразу после внешнего коммита Оператора, до отклонённой попытки push.
    """

    def setUp(self):
        super().setUp()
        self.TASK = "01ACPUSHNFFDIVERGE1"
        self.task_dir = self.new_external_task(self.TASK)
        self.branch = artifact_branch.branch_name(self.TASK)

        self.add_origin()
        from orchestrator import checkpoint
        self.push_dir(self.task_dir, self.TASK, "PLAN.md", "план\n")
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")
        assert self.origin_branch_sha(self.branch) == \
            gitcmd.branch_head_sha(self.branch), (
            "предусловие: первый автокоммит с уже подключённым origin "
            "обязан синхронизировать его штатно")

        self.push_external_commit(
            self.TASK, f"tasks/{self.TASK}/EXTERNAL.md",
            "внешняя правка Оператора\n")
        self.origin_sha_before = self.origin_branch_sha(self.branch)

        self.task_dir.mkdir(parents=True)
        self.push_dir(self.task_dir, self.TASK, "REVIEW.md", "ревью\n")

    def run_reviewer_autocommit(self) -> None:
        from orchestrator import checkpoint
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "reviewer")
