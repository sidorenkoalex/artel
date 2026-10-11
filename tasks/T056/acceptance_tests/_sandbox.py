"""Общая песочница приёмочных тестов T056 (не test_*.py — не подхватывается
`unittest discover` напрямую, только импортом из test_ac*.py).

Инвариант проверяется на уровне настоящего CLI-процесса
(`python3 orchestrator/artel.py <команда>`), а не подменённых модулей:
SPEC требует отказа `artel.py` на самом входе, до диспетчеризации команды
и до обращения к БД (требование 1), а признак worktree — фактический
файл `ROOT/.git` (требование 2). `mock.patch.object(config, "ROOT", ...)`
(идиома `tests/test_invariants.py`) этого не проверяет: `Path(__file__)`
внутри самого запущенного `artel.py` не подчиняется моку процесса теста —
только тому, где на диске реально лежит запускаемый скрипт. Поэтому
песочница строит настоящий git-репозиторий с копией `orchestrator/` +
`scripts/` (актуальный код — с проверяемым guard'ом, если он уже
реализован) и настоящим `git worktree add`.
"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# Полный перечень команд из таблицы `orchestrator/artel.py::main` (17 штук,
# включая читающие) — предмет требования 4 SPEC: отказ распространяется на
# ВСЕ команды CLI, не только мутирующие. `-h`/`--help` не входит — это не
# диспетчеризация команды (`main` возвращается раньше таблицы).
ALL_CLI_COMMANDS = (
    ("init",), ("new", "Задача"), ("status",), ("show", "T001"),
    ("advance", "T001"), ("workspace", "T001"), ("run", "T001"),
    ("auto", "T001"), ("approve", "T001"), ("reject", "T001", "причина"),
    ("kill", "T001"), ("log", "T001"), ("budget", "T001", "50"),
    ("target-init", "sled"), ("doctor",), ("alert-ack", "T001", "решение"),
    ("version",),
)


class WorktreeGuardSandbox(unittest.TestCase):
    """Базовый класс: изолированный временный каталог, в который копируется
    актуальный `orchestrator/`+`scripts/` — тесты не трогают настоящий
    пульт (его БД, git, `.artel/`) ни на чтение, ни тем более на запись.
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # resolve(): на macOS /var — симлинк на /private/var (тот же приём,
        # что и tests/test_invariants.py::KillKeepsMainIntactTest) — без
        # него сравнение путей в тексте отказа с фактическим ROOT
        # разошлось бы на резолве симлинка внутри самого CLI
        # (`Path(__file__).resolve()` в orchestrator/config.py).
        self.sandbox = Path(tmp.name).resolve()

    def seed_copy(self, dest: Path) -> None:
        """Копия актуального `orchestrator/`+`scripts/` в `dest`."""
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(REPO_ROOT / "orchestrator", dest / "orchestrator",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(REPO_ROOT / "scripts", dest / "scripts")

    def git(self, *args: str, cwd: Path) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], cwd=cwd, timeout=30,
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0,
                         f"git {' '.join(args)} упал: {res.stderr}")
        return res

    def init_git_repo(self, root: Path) -> None:
        self.git("init", "-q", "-b", "main", cwd=root)
        self.git("config", "user.email", "artel-tests@example.invalid",
                 cwd=root)
        self.git("config", "user.name", "artel tests", cwd=root)
        self.git("add", "-A", cwd=root)
        self.git("commit", "-q", "-m", "init", cwd=root)

    def run_cli(self, root: Path, *args: str) -> subprocess.CompletedProcess:
        """Настоящий процесс `python3 <root>/orchestrator/artel.py <args>` —
        так, как его реально зовёт Оператор (SPEC, «Контекст»)."""
        return subprocess.run(
            ["python3", str(root / "orchestrator" / "artel.py"), *args],
            cwd=root, timeout=30, capture_output=True, text=True,
            encoding="utf-8")
