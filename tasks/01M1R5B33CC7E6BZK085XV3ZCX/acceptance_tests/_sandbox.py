"""Общая песочница приёмочных тестов этой задачи (SPEC: B2 ТЗ-1
«репозиторный контекст target»).

`ExternalTargetGitSandbox` — тот же приём, что уже несёт
`tasks/T094/acceptance_tests/_sandbox.py::ExternalTargetGitSandbox`
(`self.root` — реальный git-репозиторий пульта на `main`, `self.
target_origin` — bare-репозиторий, имитирующий форндж целевого,
`self.target_workspace` — рабочий клон `config.PROJECTS/<target>/
workspace/`), с двумя отличиями, нужными именно этой SPEC:

1. `merge_gate: operator` для целевого (не `target-human` — тот гейт
   вне объёма этой задачи, C1, «Не входит»): критерии AC-12/AC-15/AC-16
   гоняют настоящий плотницкий merge через `_cmd_approve_merge_gate`,
   который сегодня понимает только `operator`-стиль подтверждения.
2. У пульта (`self.root`) тоже есть bare `origin` (`self.pult_origin`):
   требование 6/AC-15 явно требует доказать ОТСУТСТВИЕ нового коммита в
   `main` пульта — без настоящего origin утечка кода внешнего target в
   пульт («старый», дозадачный баг реестра точек SPEC) осталась бы
   незамеченной, если бы код по ошибке толкнул её именно туда.

Задачи внешнего target заводятся напрямую через `store.insert_task`
(не через `catalog.cmd_new` — тот сегодня заводит задачи только для
`config.DEFAULT_TARGET`), тем же приёмом, что и `tests/
test_multitarget.py`/`tasks/T094/acceptance_tests/_sandbox.py`.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config, store  # noqa: E402
from tests.sandbox import RealGitSandbox, resilient_tmp_cleanup  # noqa: E402

EXTERNAL_TARGET = "extproj"

TARGETS_YAML = f"""targets:
  artel:
    forge: github
    url: https://example.invalid/artel
    base: main
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
  {EXTERNAL_TARGET}:
    forge: github
    url: https://example.invalid/{EXTERNAL_TARGET}
    base: main
    token_slot: {EXTERNAL_TARGET}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


class ExternalTargetGitSandbox(RealGitSandbox):
    """`self.root` — пульт; `self.pult_origin` — bare-репо пульта;
    `self.target_origin` — bare-репо, имитирующий origin внешнего
    target; `self.target_workspace` — его рабочий клон, уже с одним
    коммитом на `main` и настроенным `remote origin`."""

    TARGET = EXTERNAL_TARGET

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(TARGETS_YAML, encoding="utf-8")

        pult_origin_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, pult_origin_tmp)
        self.pult_origin = Path(pult_origin_tmp.name) / "origin.git"
        subprocess.run(
            ["git", "init", "-q", "--bare", "-b", config.MAIN_BRANCH,
             str(self.pult_origin)], check=True, capture_output=True, text=True)
        self.git("remote", "add", "origin", str(self.pult_origin))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)

        bare_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, bare_tmp)
        self.target_origin = Path(bare_tmp.name) / "origin.git"
        subprocess.run(
            ["git", "init", "-q", "--bare", "-b", config.MAIN_BRANCH,
             str(self.target_origin)],
            check=True, capture_output=True, text=True)

        self.target_workspace = config.PROJECTS / self.TARGET / "workspace"
        self.target_workspace.mkdir(parents=True)
        self.wgit("init", "-q", "-b", config.MAIN_BRANCH)
        self.wgit("remote", "add", "origin", str(self.target_origin))
        self.wgit("config", "user.email", "artel@example.invalid")
        self.wgit("config", "user.name", "artel tests")
        (self.target_workspace / "marker.txt").write_text(
            "target\n", encoding="utf-8")
        self.wgit("add", "-A")
        self.wgit("commit", "-q", "-m", "init")
        self.wgit("push", "-q", "origin", config.MAIN_BRANCH)

    def wgit(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.target_workspace,
                             capture_output=True, text=True)
        assert res.returncode == 0, f"git {' '.join(args)}: {res.stderr}"
        return res.stdout

    def origin_git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=self.target_origin,
                              capture_output=True, text=True)

    def pult_origin_git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=self.pult_origin,
                              capture_output=True, text=True)

    def insert_external_task(self, task_id: str, branch: str,
                             state: str = "in_dev", **kwargs) -> None:
        """Заводит строку задачи внешнего target напрямую в БД (без
        `cmd_new` — см. докстринг модуля)."""
        conn = store.db()
        store.insert_task(conn, task_id, f"Задача {task_id} внешнего target",
                          state, branch, self.TARGET,
                          config.DEFAULT_BUDGET_USD, **kwargs)

    def checkout_task_branch(self, branch: str) -> None:
        self.wgit("checkout", "-q", "-b", branch)

    def commit_workspace_file(self, rel: str, text: str, message: str) -> str:
        path = self.target_workspace / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.wgit("add", "-A")
        self.wgit("commit", "-q", "-m", message)
        return self.wgit("rev-parse", "HEAD").strip()

    def pult_main_state(self) -> tuple:
        """(sha, дерево) `main` пульта — то, что задача внешнего target
        не имеет права сдвинуть (AC-15)."""
        return (self.git("rev-parse", config.MAIN_BRANCH),
                self.git("ls-tree", "-r", config.MAIN_BRANCH))


def write_plan_ready(task_id: str) -> None:
    """PLAN.md со статусом ready, проходящий структурный guard (RULES
    "plan" в scripts/guard.py: секции Подход/Шаги/Покрытие требований/
    Влияние на систему)."""
    from orchestrator import artifact_branch
    text = (
        "---\n"
        f"task: {task_id}\n"
        "type: plan\n"
        "author_role: developer\n"
        "status: ready\n"
        "schema_version: 4\n"
        "---\n\n"
        f"# PLAN: {task_id}\n\n"
        "## Подход\nправка кода целевого.\n\n"
        "## Шаги\n1. правка feature.py\n\n"
        "## Покрытие требований\n| Требование | Шаг |\n|---|---|\n| 1 | 1 |\n\n"
        "## Влияние на систему\nтолько код целевого, гейты не ослабляются.\n")
    artifact_branch.commit_files(
        task_id, {f"tasks/{task_id}/PLAN.md": text}, f"{task_id}: план")


def write_review_approved(task_id: str, iteration: int = 1) -> None:
    """REVIEW.md со статусом approved, пустым реестром замечаний,
    проходящий структурный guard (RULES "review" + registry gate)."""
    from orchestrator import artifact_branch
    text = (
        "---\n"
        f"task: {task_id}\n"
        "type: review\n"
        "author_role: reviewer\n"
        "status: approved\n"
        f"iteration: {iteration}\n"
        "schema_version: 4\n"
        "---\n\n"
        f"# REVIEW: {task_id}\n\n"
        "## Соответствие SPEC\n| Требование | Вердикт | Комментарий |\n"
        "|---|---|---|\n| 1 | OK | |\n\n"
        "## Замечания\n(нет)\n\n"
        "## Реестр замечаний\n"
        "| id | статус | файл/строка | суть | последствие | решение |\n"
        "|---|---|---|---|---|---|\n\n"
        "## Вердикт\napproved\n\n"
        "## Проверено исполнением\n"
        "python3 -m unittest discover -s tasks/"
        f"{task_id}/acceptance_tests — зелено.\n")
    artifact_branch.commit_files(
        task_id, {f"tasks/{task_id}/REVIEW.md": text}, f"{task_id}: ревью")
