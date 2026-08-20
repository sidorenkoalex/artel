"""Вызовы git в корне репозитория и вопросы к ветке задачи."""
import subprocess

from . import config


def git(*args: str) -> subprocess.CompletedProcess:
    """git в корне репозитория; исход разбирает вызывающий.

    Ошибка запуска (git не установлен) — такой же ненулевой код возврата,
    как и ошибка самой команды: уборке достаточно знать, что ответа нет.
    """
    try:
        return subprocess.run(["git", *args], cwd=config.ROOT,
                              capture_output=True, text=True)
    except OSError as exc:
        return subprocess.CompletedProcess(args, 1, "", str(exc))


def current_branch() -> str:
    """Ветка под HEAD; пустая строка — git не ответил."""
    res = git("rev-parse", "--abbrev-ref", "HEAD")
    return res.stdout.strip() if res.returncode == 0 else ""


def branch_exists(branch: str) -> bool:
    return git("rev-parse", "--verify", "--quiet",
               f"refs/heads/{branch}").returncode == 0


def branch_merged(branch: str) -> bool:
    """Смержена ли ветка в main — тем же критерием, каким git защищает `-d`."""
    res = git("branch", "--merged", config.MAIN_BRANCH, "--list", branch)
    return res.returncode == 0 and bool(res.stdout.strip())
