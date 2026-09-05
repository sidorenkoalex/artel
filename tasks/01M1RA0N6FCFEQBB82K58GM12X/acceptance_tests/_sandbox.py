"""Общая обвязка планки этой задачи (SPEC 01M1RA0N6FCFEQBB82K58GM12X):
настоящий git-репозиторий (`tests.sandbox.RealGitSandbox`), не подмена
`gitcmd.git` фейком — предмет проверки этой задачи именно байтовый размер
РЕАЛЬНОГО `git diff main...branch`, а способ исключения `tasks/<id>/`
(пример в SPEC — `-- . ':!tasks/'`, но точный вызов остаётся на
усмотрение реализации) тестами не навязывается.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402


class GitFeatureBranchSandbox(RealGitSandbox):
    """Ветка задачи поверх main с одним код-файлом на старте; `write`/
    `commit` — прямые запись+коммит в рабочее дерево `config.ROOT`
    (реальный чекаут ветки, не отдельный worktree — гейт и ревью-пакет
    читают именно `config.ROOT`)."""

    TASK = "T900"
    BRANCH = "task/t900-x"
    CODE_FILE = "orchestrator/feature.py"

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        (self.root / self.CODE_FILE).parent.mkdir(parents=True, exist_ok=True)
        (self.root / self.CODE_FILE).write_text("базовый код\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "код до задачи")
        self.checkout(self.BRANCH, create=True)

    def write(self, rel: str, content: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def journal_details(self) -> list:
        return [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]
