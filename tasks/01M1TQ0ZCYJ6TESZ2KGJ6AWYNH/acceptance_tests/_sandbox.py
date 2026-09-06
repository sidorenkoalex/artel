"""Общая песочница приёмочных тестов задачи 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH
(«артефактная ветка новой задачи заводится от origin/main, а не от
пина»).

`ArtifactBranchOriginSandbox` — надстройка над `tests.sandbox.
RealGitSandbox` (настоящий git-репозиторий вместо заглушки `gitcmd.git`:
предмет проверки — реальное поведение `git fetch`/`merge-base` этой
задачи, заглушкой не изобразить, тот же довод, что у `tests/
test_gitcmd_branch_reads.py::RemoteBranchShaTest`). Добавляет три
операции над `origin`, которых нет в общей песочнице:

- `add_origin()` — bare-remote, синхронный с текущим локальным main
  (воспроизводит нормальное состояние ДО инцидента 06.09);
- `advance_origin_main(files)` — коммитит `files` в origin/main из
  ОТДЕЛЬНОГО клона, не трогая локальный main пульта (`self.root`) —
  воспроизводит сам инцидент: origin ушёл вперёд от пина;
- `make_origin_disjoint()` — заменяет origin/main на историю, вообще не
  связанную с локальным main (крайняя форма расхождения: родитель
  первого коммита артефактной ветки перестаёт быть предком origin/main
  — сценарий AC-5, doctor).

Не сканируется guard'ом как тест (только test_*.py несёт AC-разметку/
тестовые методы, SPEC T081) — файлы test_ac*.py этого каталога делят с
ним фикстуры.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402


class ArtifactBranchOriginSandbox(RealGitSandbox):

    bare: str | None = None

    def add_origin(self, sync: bool = True) -> None:
        """origin (bare). `sync=True` (по умолчанию) сразу пушит текущий
        локальный main — нормальное состояние ДО инцидента 06.09.
        `sync=False` — origin остаётся пустым (используется
        `make_origin_disjoint`, которой синхронизация не нужна)."""
        bare = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, bare, ignore_errors=True)
        self.git("init", "-q", "--bare", bare)
        self.git("remote", "add", "origin", bare)
        if sync:
            self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)
        self.bare = bare

    def _scratch_clone(self) -> str:
        scratch = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        subprocess.run(["git", "clone", "-q", self.bare, scratch], check=True)
        subprocess.run(["git", "-C", scratch, "config", "user.email",
                        "artel@example.invalid"], check=True)
        subprocess.run(["git", "-C", scratch, "config", "user.name",
                        "artel tests"], check=True)
        return scratch

    def advance_origin_main(self, files: dict,
                            message: str = "origin ушёл вперёд от пина") -> str:
        """Коммитит `files` ({путь: текст}) в origin/main из отдельного
        клона, НЕ трогая локальный main пульта (`self.root`) —
        воспроизводит инцидент 06.09. Возвращает sha новой головы
        origin/main."""
        assert self.bare, "сначала add_origin()"
        scratch = self._scratch_clone()
        for rel, content in files.items():
            path = Path(scratch) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "-C", scratch, "add", "-A"], check=True)
        subprocess.run(["git", "-C", scratch, "commit", "-q", "-m", message],
                       check=True)
        subprocess.run(["git", "-C", scratch, "push", "-q", "origin",
                        config.MAIN_BRANCH], check=True)
        res = subprocess.run(["git", "-C", scratch, "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=True)
        return res.stdout.strip()

    def make_origin_disjoint(self) -> str:
        """Заменяет origin/main на историю, НЕ связанную с локальным
        main (AC-5, doctor): родитель первого коммита артефактной ветки,
        взятый от локального пина ДО этого вызова, перестаёт быть
        предком origin/main вовсе — не просто отстаёт. Возвращает sha
        новой головы origin/main."""
        assert self.bare, "сначала add_origin()"
        scratch = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        subprocess.run(["git", "init", "-q", "-b", config.MAIN_BRANCH, scratch],
                       check=True)
        subprocess.run(["git", "-C", scratch, "config", "user.email",
                        "artel@example.invalid"], check=True)
        subprocess.run(["git", "-C", scratch, "config", "user.name",
                        "artel tests"], check=True)
        (Path(scratch) / "unrelated.txt").write_text(
            "история, не связанная с пином\n", encoding="utf-8")
        subprocess.run(["git", "-C", scratch, "add", "-A"], check=True)
        subprocess.run(["git", "-C", scratch, "commit", "-q", "-m",
                        "история без общих предков с пином"], check=True)
        subprocess.run(["git", "-C", scratch, "remote", "add", "origin",
                        self.bare], check=True)
        subprocess.run(["git", "-C", scratch, "push", "-q", "-f", "origin",
                        config.MAIN_BRANCH], check=True)
        res = subprocess.run(["git", "-C", scratch, "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=True)
        return res.stdout.strip()

    def local_main_head(self) -> str:
        return self.git("rev-parse", config.MAIN_BRANCH).strip()

    def commit_parent_sha(self, commit_sha: str) -> str:
        return self.git("log", "--pretty=%P", "-1", commit_sha).strip()
