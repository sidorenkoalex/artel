"""Общая тестовая песочница (SPEC T037, требование 1).

`TmpRootTest`, `capture` и `fake_git` копировались по 9/17/8 тестовым
файлам с расхождениями в наборе подменяемых путей `config` —
непропатченный путь в очередной копии означал тихую утечку теста на
реальное дерево пульта (SPEC T037, «Контекст»). Файлы, которым нужен
не полный набор или доп. подготовка (git-заглушка, `cmd_init`, копия
`skills/`/`templates/`), наследуют `TmpRootTest` и переопределяют
`PATCHED_ATTRS`/`setUp` — см. tasks/T037/PLAN.md, «Таблица переносов».
"""
import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import config

# Все пути `config`, которые сегодня подменяет хотя бы одна песочница
# (SPEC T037, AC-2) — порядок как в orchestrator/config.py.
ALL_CONFIG_ATTRS = (
    "DB", "TASKS", "LOGS", "ROOT", "PROJECTS", "TARGETS",
    "ROLE_HOME", "ROLE_CONFIG_DIR", "BACKUP_MARKER", "WORKTREES",
)


def capture(fn, *args) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


def fake_git(*args: str) -> subprocess.CompletedProcess:
    """Подмена `gitcmd.git`: git-идентичность роли, без обращения к репозиторию.

    Нужна, потому что подмена `subprocess.Popen` глобальна: настоящий
    `gitcmd.git` (его зовёт `runner.role_env` за авторством коммита шага)
    ушёл бы через неё в фейковый процесс.

    `rev-parse --verify --quiet refs/heads/<ветка>` (`gitcmd.branch_exists`)
    — отдельно, с отказом (SPEC T048): `cmd_new` с этой задачи сам решает,
    заводить ли задачу, по ответу этого вызова (AC-3, требование 1) — если
    отвечать успехом на любой git-вызов, как раньше, `cmd_new` увидел бы
    ЛЮБУЮ ветку как уже существующую и отказывал бы всегда. В лёгких
    песочницах реальных веток нет ни одной — ответ «нет» тут не заглушка
    ради прохождения теста, а корректная симуляция вырожденного случая.
    """
    if (len(args) >= 3 and args[0] == "rev-parse" and args[1] == "--verify"
            and args[-1].startswith("refs/heads/")):
        return subprocess.CompletedProcess(list(args), 1, "", "")
    identity = {"user.name": "Роль Артели", "user.email": "role@artel.invalid"}
    value = identity.get(args[-1], "") if args[:2] == ("config", "--get") else ""
    return subprocess.CompletedProcess(list(args), 0, f"{value}\n", "")


class TmpRootTest(unittest.TestCase):
    """Общая песочница: пути `config` — во временном каталоге.

    `PATCHED_ATTRS` — параметризуемый набор патчей (SPEC T037,
    требование 1); по умолчанию — все десять путей `config` (AC-2).
    """

    PATCHED_ATTRS = ALL_CONFIG_ATTRS

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

        for attr in self.PATCHED_ATTRS:
            patcher = mock.patch.object(config, attr, self._patched_path(attr))
            patcher.start()
            self.addCleanup(patcher.stop)

    def _patched_path(self, attr: str) -> Path:
        return {
            "ROOT": self.root,
            "DB": self.root / ".artel" / "state.db",
            "TASKS": self.root / "tasks",
            "LOGS": self.root / ".artel" / "logs",
            "PROJECTS": self.root / ".artel" / "projects",
            "TARGETS": self.root / "targets.yaml",
            "ROLE_HOME": self.root / ".artel" / "home",
            "ROLE_CONFIG_DIR": self.root / ".artel" / "home" / ".claude",
            "BACKUP_MARKER": self.root / ".artel" / "backup-marker",
            "WORKTREES": self.root / ".artel" / "worktrees",
        }[attr]

    def capture(self, fn, *args) -> str:
        return capture(fn, *args)
