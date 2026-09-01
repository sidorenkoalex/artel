"""Общая песочница приёмочных тестов T094 (SPEC: M1 «артефактный контур —
Б₃ + ULID»).

`ExternalTargetGitSandbox` расширяет `tests.sandbox.RealGitSandbox`
(`self.root` — реальный git-репозиторий пульта, ветка `main`, один
коммит) добавкой внешнего target: bare-репозиторий `self.target_origin`
(имитирует форндж целевого — сеть не участвует, тот же приём, что и у
`RealGitSandbox` для пульта) и его рабочий клон
`config.PROJECTS/<target>/workspace/` — то же место, что уже сегодня
использует `orchestrator.runner.role_env` для роли внешнего target
(«эфемерный клон целевого», ADR-0003 §4, `orchestrator/projects.py`).

Задачи внешнего target песочница заводит НАПРЯМУЮ через
`store.insert_task` (тем же приёмом, что и `tests/test_multitarget.py`),
не через `catalog.cmd_new` — сегодняшний `cmd_new` заводит задачи только
для `config.DEFAULT_TARGET` (self/догфуд, требование 16 SPEC исключает
именно его из механики этой задачи); тесты внешнего target конструируют
сценарий на уровне ниже, тем же способом, каким уже устроен
`test_multitarget.py`.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

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
    merge_gate: target-human
"""


class ExternalTargetGitSandbox(RealGitSandbox):
    """`self.root` — пульт (как у `RealGitSandbox`); `self.target_origin` —
    bare-репозиторий, имитирующий origin внешнего target на фордже;
    `self.target_workspace` — его рабочий клон
    (`config.PROJECTS/<TARGET>/workspace/`), уже с одним коммитом на
    `main` и настроенным `remote origin`."""

    TARGET = EXTERNAL_TARGET

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(TARGETS_YAML, encoding="utf-8")

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
            "main\n", encoding="utf-8")
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
