"""Общая надстройка для приёмочных тестов задачи 01M2ARQGY51B99YNP9PY806AN1
(SPEC: «Гонка на FETCH_HEAD — приватная ссылка fetch в трёх местах»).

`PrivateFetchSandbox` — настоящий git-репозиторий (`tests.sandbox.
RealGitSandbox`, тот же приём, что `tests/test_gitcmd_branch_reads.py`:
предмет проверки — поведение относительно НАСТОЯЩЕГО git, заглушкой не
изобразить) плюс bare `origin`, продвигаемый из ОДНОРАЗОВОГО отдельного
клона (`advance_origin`) — так, чтобы новый коммит на origin гарантированно
отсутствовал в локальной объектной базе `self.root` ДО вызова примитива под
проверкой: иначе `git cat-file -e` проходил бы и без настоящего fetch, и
тест ничего не доказывал бы об объектах, реально попавших в базу.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402


class PrivateFetchSandbox(RealGitSandbox):

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def private_refs(self) -> list[str]:
        """Ссылки под `refs/artel/fetch/` в `self.root` прямо сейчас —
        пусто, если ни одна не осталась висеть после вызова примитива."""
        out = self.git("for-each-ref", "--format=%(refname)",
                       "refs/artel/fetch/")
        return [line for line in out.splitlines() if line]

    def advance_origin(self, origin: Path, filename: str, content: str) -> str:
        """Коммитит и пушит новый коммит в `origin` из отдельного
        одноразового клона — не через `self.root` (объект нового коммита
        обязан отсутствовать в объектной базе `self.root` до вызова
        примитива под проверкой). Возвращает sha нового коммита."""
        clone = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, clone, ignore_errors=True)
        subprocess.run(["git", "clone", "-q", "--branch", config.MAIN_BRANCH,
                       str(origin), str(clone)],
                      check=True, capture_output=True)
        subprocess.run(["git", "-C", str(clone), "config", "user.email",
                       "artel@example.invalid"],
                      check=True, capture_output=True)
        subprocess.run(["git", "-C", str(clone), "config", "user.name",
                       "artel tests"], check=True, capture_output=True)
        (clone / filename).write_text(content, encoding="utf-8")
        subprocess.run(["git", "-C", str(clone), "add", "-A"],
                      check=True, capture_output=True)
        subprocess.run(["git", "-C", str(clone), "commit", "-q", "-m",
                       "advance"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(clone), "push", "-q", "origin",
                       f"HEAD:{config.MAIN_BRANCH}"],
                      check=True, capture_output=True)
        res = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=True)
        return res.stdout.strip()

    def object_present(self, sha: str) -> bool:
        res = subprocess.run(
            ["git", "-C", str(self.root), "cat-file", "-e", f"{sha}^{{commit}}"],
            capture_output=True, text=True)
        return res.returncode == 0
