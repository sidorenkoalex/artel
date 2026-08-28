"""Общая тестовая песочница (SPEC T037, требование 1; SPEC T061 —
второй заход: `FakeProc` и claude-only side_effect).

`TmpRootTest`, `capture` и `fake_git` копировались по 9/17/8 тестовым
файлам с расхождениями в наборе подменяемых путей `config` —
непропатченный путь в очередной копии означал тихую утечку теста на
реальное дерево пульта (SPEC T037, «Контекст»). Файлы, которым нужен
не полный набор или доп. подготовка (git-заглушка, `cmd_init`, копия
`skills/`/`templates/`), наследуют `TmpRootTest` и переопределяют
`PATCHED_ATTRS`/`setUp` — см. tasks/T037/PLAN.md, «Таблица переносов».

`FakeProc` и пара `claude_only_run`/`claude_only_popen` копировались
той же дорогой (SPEC T061, находка CR-2026-08-28-2, ★5): подмена
только запуска `claude`, настоящий git — тем же общим `subprocess`,
что и у `runner`/`gitcmd`.
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


def seed_developer_brief_fixtures(root: Path) -> None:
    """Синтетические `docs/codebase-map.md`/`CLAUDE.md` в `root` (T028):
    бриф роли developer/analyst (`orchestrator/brief.py`) читает оба из
    `config.ROOT` — без них шаг падает ENOENT ещё до сценария, который
    песочница проверяет. Тот же приём, что уже был у `tests/test_doctor.py`
    `_DoctorTmpRootTest.setUp` до этой задачи (SPEC T049 добавила
    сканирование `config.ROOT` холодным стартом и туда, где раньше он
    оставался непропатченным реальным деревом пульта, — остальные
    песочницы, гоняющие `cmd_run` роли developer/analyst, этот же
    минимум теперь заводят себе явно, а не получают его случайно от
    реального ROOT)."""
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "codebase-map.md").write_text(
        "---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
        "---\n\n# Карта\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")


def sync_spec_from_worktree(task_id: str) -> None:
    """Зеркалит SPEC.md из воркт-дерева задачи в `config.TASKS` (легаси-путь
    чтения брифа разработчика).

    `cmd_new` (SPEC T048) пишет SPEC.md в worktree
    (`config.WORKTREES/<id>/tasks/<id>/`), не в `config.TASKS`.
    `brief._developer_spec_text` при этом падает на `config.TASKS`, когда
    `gitcmd.on_foreign_branch` — False (в лёгких песочницах с `fake_git`
    выше — всегда: `current_branch()` там пустая строка). Без зеркала
    следующий `cmd_run` роли developer получает `FileNotFoundError` на
    путь, которого `cmd_new` с T048 больше не пишет.
    """
    wt_spec = config.WORKTREES / task_id / "tasks" / task_id / "SPEC.md"
    dest_dir = config.TASKS / task_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "SPEC.md").write_text(
        wt_spec.read_text(encoding="utf-8"), encoding="utf-8")


def fake_git_for(responses: dict) -> callable:
    """Параметризуемая заглушка `gitcmd.git`: подкоманда (первый позиционный
    аргумент вызова) ищется в `responses` и отвечает фиксированным
    `(returncode, stdout, stderr)`; всё остальное — чисто (rc=0, пустой
    вывод), без git-идентичности и отказа `rev-parse --verify`, которые
    несёт `fake_git` (эти сценарии — сверка свежести карты/её регенерация
    в tests/test_brief.py — идентичности и веток не касаются)."""
    def fake(*args: str) -> subprocess.CompletedProcess:
        if args and args[0] in responses:
            rc, out, err = responses[args[0]]
            return subprocess.CompletedProcess(list(args), rc, out, err)
        return subprocess.CompletedProcess(list(args), 0, "", "")
    return fake


class _FakeStream:
    """Пайп процесса: отдаёт заготовленные строки, помнит своё закрытие."""

    def __init__(self, lines):
        self.lines = iter(lines)
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self) -> str:
        return next(self.lines)

    def close(self) -> None:
        self.closed = True


class FakeProc:
    """Процесс агента: отдаёт заготовленные строки, wait() — сразу rc."""

    def __init__(self, lines, returncode: int = 0):
        self.stdout = _FakeStream(lines)
        self.returncode = returncode

    def wait(self, timeout=None) -> int:
        return self.returncode


_REAL_RUN = subprocess.run
_REAL_POPEN = subprocess.Popen


def claude_only_run(claude_stdout: str, claude_returncode: int = 0):
    """`subprocess.run` side_effect: отвечает только на `claude ...`, остальное
    (например, `git config --get ...` внутри `gitcmd.git` — тот же общий
    модуль `subprocess`) уходит в настоящий `subprocess.run`: подмена
    атрибута `subprocess.run` глобальна на модуль."""
    def run(args, **kwargs):
        if args and args[0] == "claude":
            return subprocess.CompletedProcess(args, claude_returncode,
                                               claude_stdout, "")
        return _REAL_RUN(args, **kwargs)
    return run


def claude_only_popen(fake_proc):
    """Аналог `claude_only_run` для `subprocess.Popen`/`runner.spawn_agent`."""
    def popen(cmd, *args, **kwargs):
        if cmd and cmd[0] == "claude":
            return fake_proc
        return _REAL_POPEN(cmd, *args, **kwargs)
    return popen


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
