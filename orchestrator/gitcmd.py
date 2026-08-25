"""Вызовы git в корне репозитория, вопросы к ветке задачи и к произвольному
репозиторию (артефактные git-репо внешних target, ADR-0003 3д, tasks/T021)."""
import subprocess
from pathlib import Path

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


def in_repo(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """git-команда в произвольном репозитории (не ROOT пульта) через `-C`.

    Не `subprocess.run(..., cwd=repo)` внутри `git()`: существующие тесты
    подменяют саму функцию `gitcmd.git` заглушками сигнатуры `(*args: str)`
    (мультитаргет, FSM, бюджет, автоцикл) — добавь `git()` параметр `cwd`,
    эти заглушки упали бы `TypeError` на неожиданном keyword-аргументе.
    `-C <repo>` остаётся обычным позиционным аргументом `git(*args)`, тем
    же вызовом, который заглушки уже умеют разобрать (tasks/T021 PLAN,
    «Подход»).
    """
    return git("-C", str(repo), *args)


def head_sha(repo: Path | None = None) -> str:
    """sha текущего HEAD; пустая строка — нет коммитов или git не ответил.

    `res is None` — не только реальный отказ `subprocess.run` (уже
    свёрнут в `git()` в `CompletedProcess` с ненулевым кодом), но и
    подмена `gitcmd.git` в тестах, не связанных с git вовсе
    (test_advance_guard.py: `lambda *a: None`, задачам которого сама
    фиксация артефактов не нужна) — тот же смысл «ответа нет».
    """
    res = in_repo(repo, "rev-parse", "HEAD") if repo else git("rev-parse", "HEAD")
    return res.stdout.strip() if res is not None and res.returncode == 0 else ""


def is_clean(*paths: str, repo: Path | None = None) -> bool | None:
    """Нет незакоммиченных изменений по путям; None — git не ответил.

    Без путей — вся рабочая копия репозитория (`repo`, если задан).
    """
    args = ("status", "--porcelain") + (("--", *paths) if paths else ())
    res = in_repo(repo, *args) if repo else git(*args)
    if res is None or res.returncode != 0:
        return None
    return not res.stdout.strip()


def diff_paths(a: str, b: str, *paths: str) -> bool | None:
    """True — ревизии `a` и `b` расходятся по путям; None — git не ответил.

    `git diff --quiet` кодирует ответ кодом возврата (0 — совпадают,
    1 — расходятся), не выводом: достаточно для проверки лока
    acceptance_tests/ (orchestrator/fsm.py, tasks/T023, требование 5)
    без парсинга самого диффа. Тот же вырожденный случай «git не ответил»,
    что у `is_clean`/`head_sha`: заглушка `gitcmd.git = lambda *a: None`
    в тестах, не связанных с git, возвращает `None` тем же приёмом.
    """
    res = git("diff", "--quiet", a, b, "--", *paths)
    if res is None or res.returncode not in (0, 1):
        return None
    return res.returncode == 1


def has_no_remote(repo: Path) -> bool:
    """True — `git remote` пуст: ни одной записи (ADR-0003 3д, требование 7).

    Потребитель — doctor (A3); здесь только сама проверка.
    """
    res = in_repo(repo, "remote")
    return res is not None and res.returncode == 0 and not res.stdout.strip()
