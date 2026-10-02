"""Общий код разовых файлов планки задачи 01M3YS928033B1QF89VN2N5KC3.

Не тестовый модуль: префикс `_` обязателен (skills/test-authoring.md).
Держит корень чекаута планки, базу диффа задачи (`gitcmd.diff_base`),
запуск pytest отдельным процессом и поддельный CLI `claude` в PATH.
"""
import os
import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import gitcmd  # noqa: E402

TARGET_FILE = "tests/test_agent_failure.py"
TARGET_CLASS = "CmdRunFailureTest"
TARGET_METHOD = "test_missing_cli_is_not_retried"
TARGET_NODE = f"{TARGET_FILE}::{TARGET_CLASS}::{TARGET_METHOD}"

#: Таймаут одного прогона pytest отдельным процессом — ниже потолка
#: pytest-timeout пульта на один тест (120 с).
PYTEST_TIMEOUT_SEC = 100

#: Имя CLI провайдера по умолчанию — из реестра провайдеров, не литерал.
def cli_name() -> str:
    from orchestrator.providers import DEFAULT_PROVIDER, PROVIDERS
    return PROVIDERS[DEFAULT_PROVIDER].cli_tool().name


def diff_base() -> str | None:
    """База диффа задачи — точка расхождения HEAD чекаута планки с
    `origin/<основная>` (`gitcmd.diff_base`), посчитанная в самом чекауте."""
    return gitcmd.diff_base("HEAD", repo=REPO_ROOT)


def git(*args, cwd: Path = REPO_ROOT, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          timeout=120, **kw)


def show_at(rev: str, rel: str) -> str | None:
    """Текст файла `rel` в ревизии `rev`; `None` — файла там нет."""
    res = git("show", f"{rev}:{rel}", text=True)
    return res.stdout if res.returncode == 0 else None


def changed_paths(base: str) -> list[str]:
    """Пути, изменённые веткой задачи от `base`: отслеживаемые (коммиты и
    рабочее дерево) плюс неотслеживаемые новые файлы вне `tasks/`
    (артефакты задачи в кодовую ветку не идут — их несёт артефактная)."""
    tracked = git("diff", "--name-only", base, text=True)
    assert tracked.returncode == 0, tracked.stderr
    untracked = git("ls-files", "--others", "--exclude-standard", text=True)
    assert untracked.returncode == 0, untracked.stderr
    paths = set(tracked.stdout.split())
    paths |= {p for p in untracked.stdout.split()
              if not p.startswith("tasks/")}
    return sorted(paths)


def added_paths(base: str) -> list[str]:
    """Новые (не существовавшие в `base`) файлы ветки задачи."""
    added = git("diff", "--name-only", "--diff-filter=A", base, text=True)
    assert added.returncode == 0, added.stderr
    untracked = git("ls-files", "--others", "--exclude-standard", text=True)
    paths = set(added.stdout.split())
    paths |= {p for p in untracked.stdout.split()
              if not p.startswith("tasks/")}
    return sorted(paths)


def run_pytest(paths, cwd: Path = REPO_ROOT,
               env: dict | None = None) -> subprocess.CompletedProcess:
    """pytest по относительным путям `paths` в каталоге `cwd`."""
    return subprocess.run(
        [sys.executable, "-m", "pytest", *paths, "-p", "no:cacheprovider",
         "-q"],
        cwd=cwd, capture_output=True, text=True, timeout=PYTEST_TIMEOUT_SEC,
        env=env if env is not None else dict(os.environ))


def tail(res: subprocess.CompletedProcess) -> str:
    return f"{res.stdout[-3000:]}\n{res.stderr[-2000:]}"


def path_without_cli(path: str, name: str) -> str:
    """PATH без каталогов, где лежит исполняемый `name`."""
    kept = []
    for entry in path.split(os.pathsep):
        if not entry:
            continue
        candidate = Path(entry) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            continue
        kept.append(entry)
    return os.pathsep.join(kept)


def env_with_fake_cli(tdir: Path, script_body: str | None) -> dict:
    """Окружение, где CLI провайдера — поддельный скрипт `script_body`
    (sh), либо (`None`) где такого CLI в PATH нет вовсе."""
    name = cli_name()
    env = dict(os.environ)
    base_path = path_without_cli(env.get("PATH", ""), name)
    if script_body is None:
        env["PATH"] = base_path
        return env
    bindir = tdir / "fakebin"
    bindir.mkdir(parents=True, exist_ok=True)
    fake = bindir / name
    fake.write_text("#!/bin/sh\n" + script_body + "\n", encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP
               | stat.S_IXOTH)
    env["PATH"] = os.pathsep.join([str(bindir), base_path])
    return env
