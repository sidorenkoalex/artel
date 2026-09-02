"""Общая песочница приёмочных тестов A7 (артель как внешний target).

`ArtelSelfTargetSandbox` расширяет `tests.sandbox.RealGitSandbox`
(`self.root` — реальный git-репозиторий пульта, ветка `main`, один
коммит) добавкой bare-репозитория `self.origin` — origin ПУЛЬТА (тот же
приём, что `tests/test_fsm_merge_gate_done_snapshot.py` заводит
`pult_origin`). После A7 «main артели» из критериев приёмки SPEC — это
именно `self.origin` (реальный GitHub в проде): плотницкая запись
merge-коммита (AC-8/AC-9/AC-12) обязана продвигать ЕГО `refs/heads/main`,
не трогая локальный чекаут/HEAD `self.root` — иначе `git rev-parse HEAD`
внутри `self.root` (стоящего на ветке `main`, символическая ссылка на
`refs/heads/main`) сдвинулся бы вместе с прямой правкой ЛОКАЛЬНОГО
`refs/heads/main`, что нарушило бы «HEAD идентичен» из AC-8. Поэтому
`advance_origin_main_without_touching_root` продвигает `self.origin`
ИЗДАЛЕКА — через отдельный временный клон, не трогая `self.root` вовсе.

`targets.yaml` песочницы объявляет `artel` обычной записью (требование 1
SPEC, AC-1) — без пометки «особый случай» ни в файле, ни в коде, который
её разбирает.
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


class ArtelSelfTargetSandbox(RealGitSandbox):
    """`self.root` — пульт (артель) с настоящим origin-remote локально на
    диске (без сети); `self.origin` — bare-репозиторий, играющий роль
    главной копии артели на GitHub из ANSWER-1/AC-8."""

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(ARTEL_TARGETS_YAML, encoding="utf-8")

        bare_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, bare_tmp)
        self.origin = Path(bare_tmp.name) / "origin.git"
        subprocess.run(
            ["git", "init", "-q", "--bare", "-b", config.MAIN_BRANCH,
             str(self.origin)], check=True, capture_output=True, text=True)
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)

    def origin_git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(self.origin), *args],
                              capture_output=True, text=True)

    def origin_main_sha(self) -> str:
        res = self.origin_git("rev-parse", "refs/heads/" + config.MAIN_BRANCH)
        return res.stdout.strip() if res.returncode == 0 else ""

    def origin_tree_files(self, ref: str) -> list:
        res = self.origin_git("ls-tree", "-r", "--name-only", ref)
        return [p for p in res.stdout.splitlines() if p] if res.returncode == 0 else []

    def root_head_sha(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def root_branch(self) -> str:
        return self.git("rev-parse", "--abbrev-ref", "HEAD").strip()

    def root_status_porcelain(self) -> str:
        return self.git("status", "--porcelain")

    def snapshot_root_state(self) -> dict:
        """(HEAD sha, ветка, статус, содержимое marker.txt) — «запущенная
        версия» ROOT одним объектом, для сверки байт-в-байт до/после."""
        return {
            "head": self.root_head_sha(),
            "branch": self.root_branch(),
            "status": self.root_status_porcelain(),
            "marker": (self.root / "marker.txt").read_text(encoding="utf-8"),
        }

    def advance_origin_main_without_touching_root(
            self, rel: str = "external-change.txt",
            text: str = "правка ушла вперёд без пульта\n",
            message: str = "правка main вне HEAD пульта") -> str:
        """Продвигает `refs/heads/main` ИЗДАЛЕКА (временный клон), локальный
        чекаут/HEAD/ветку `self.root` не трогает вовсе — симуляция «main
        артели ушёл вперёд» той же плотницкой природы, что и сам
        merge-коммит AC-8 обязан использовать."""
        clone_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, clone_tmp)
        clone = Path(clone_tmp.name) / "clone"
        subprocess.run(["git", "clone", "-q", str(self.origin), str(clone)],
                       check=True, capture_output=True, text=True)
        subprocess.run(["git", "-C", str(clone), "config", "user.email",
                        "artel@example.invalid"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(clone), "config", "user.name",
                        "artel tests"], check=True, capture_output=True)
        (clone / rel).parent.mkdir(parents=True, exist_ok=True)
        (clone / rel).write_text(text, encoding="utf-8")
        subprocess.run(["git", "-C", str(clone), "add", "-A"], check=True,
                       capture_output=True)
        subprocess.run(["git", "-C", str(clone), "commit", "-q", "-m", message],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(clone), "push", "-q", "origin",
                        config.MAIN_BRANCH], check=True, capture_output=True)
        rev = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                             capture_output=True, text=True)
        return rev.stdout.strip()

    def make_task_branch_in_root(self, branch: str, rel: str,
                                 text: str, message: str) -> None:
        """Заводит кодовую ветку задачи ПРЯМО в `self.root` (требование 3
        SPEC — код задачи артели живёт в её собственной ветке пульта, как
        и до A7; вне объёма этой песочницы — только первичка АРТЕФАКТОВ
        уходит с диска main в артефактную ветку/M1) и возвращает чекаут на
        `main`, откуда `approve` реально исполняется."""
        self.checkout(branch, create=True)
        (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.root / rel).write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        self.checkout(config.MAIN_BRANCH)

    def insert_task(self, task_id: str, branch: str, state: str,
                    **kwargs) -> None:
        store.insert_task(store.db(), task_id, f"Задача {task_id}", state,
                          branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD, **kwargs)
