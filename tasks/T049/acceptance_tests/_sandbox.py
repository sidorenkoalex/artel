"""Общая песочница приёмочных тестов T049 (не test_*.py — не подхватывается
unittest discover напрямую, только импортом из test_ac*.py).

Два уровня песочницы, по образцу соседних задач:

- `tests.sandbox.TmpRootTest` (реэкспортируется как `TmpRootTest`) — там,
  где реальный git не нужен (AC-2..AC-4).
- `ColdStartGitRepoTest` — настоящий временный git-репозиторий поверх
  `TmpRootTest` (тот же приём, что `tasks/T048/acceptance_tests/_sandbox.py`
  `TmpGitTaskTest`): требование 1 SPEC называет ветки `task/t*` источником
  наблюдаемого мира — без настоящего git их не из чего сканировать (AC-1).
- `FullRepoCopyRootTest` — копия ВСЕГО дерева пульта (кроме `.git/`,
  `.artel/`, `tasks/`) поверх `TmpRootTest`: SPEC (требование 8) сознательно
  оставляет конкретное место референса слоя ролей на усмотрение PLAN
  разработчика, поэтому песочница не имеет права угадывать путь — она
  копирует всё дерево, и что бы разработчик ни выбрал местом референса,
  оно окажется в песочнице (AC-5).
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402
from tests.sandbox import TmpRootTest, capture, fake_git  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]

__all__ = ["TmpRootTest", "capture", "fake_git", "REPO_ROOT",
          "ColdStartGitRepoTest", "FullRepoCopyRootTest"]


class ColdStartGitRepoTest(TmpRootTest):
    """`config.ROOT` — настоящий временный git-репозиторий с веткой main;
    `templates/` скопирован (нужен `cmd_new` для шаблонного SPEC.md)."""

    def setUp(self):
        super().setUp()
        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel-tests@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        if check:
            assert res.returncode == 0, f"git {' '.join(args)}: {res.stderr}"
        return res

    def make_task_dir(self, task_id: str) -> None:
        """Источник 1 (требование 1): каталог задачи без строки БД."""
        d = self.root / "tasks" / task_id
        d.mkdir(parents=True)
        (d / "SPEC.md").write_text(f"# SPEC: {task_id}\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", f"{task_id}: тестовый артефакт")

    def make_branch(self, branch: str) -> None:
        """Источник 2 (требование 1): ветка задачи без строки БД."""
        self.git("branch", branch)

    def make_retro(self, task_id: str, cost_usd: float = 1.0) -> None:
        """Источник 3 (требование 1): файл RETRO."""
        d = self.root / "docs" / "retro"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{task_id}.md").write_text(
            f"# RETRO: {task_id} — тестовая задача\n\n"
            f"Итог: done, sha 0000000000000000000000000000000000000000\n"
            f"Стоимость итого: ${cost_usd:.2f}\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", f"retro {task_id}")


class FullRepoCopyRootTest(TmpRootTest):
    """`config.ROOT` — копия всего дерева пульта (кроме `.git/`, `.artel/`,
    `tasks/`), не только фиксированного пути: место референса слоя ролей
    решает PLAN разработчика (SPEC требование 8), не эта задача."""

    def setUp(self):
        super().setUp()
        shutil.copytree(
            REPO_ROOT, self.root, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(
                ".git", ".artel", "tasks", "__pycache__", "*.pyc"))
