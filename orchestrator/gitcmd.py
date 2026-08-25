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
    """Ветка под HEAD; пустая строка — git не ответил.

    `res is None` — заглушки `gitcmd.git` в тестах, не связанных с git,
    отвечают `None` тем же приёмом, что и у `head_sha` (T031: эта функция
    впервые попадает на горячий путь `set_state` через `on_foreign_branch`,
    где такие заглушки уже встречаются).
    """
    res = git("rev-parse", "--abbrev-ref", "HEAD")
    return res.stdout.strip() if res is not None and res.returncode == 0 else ""


def branch_exists(branch: str) -> bool:
    """`res is None` — тот же вырожденный случай, что у `head_sha`: заглушки
    `gitcmd.git` в тестах, не связанных с git, отвечают `None`."""
    res = git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
    return res is not None and res.returncode == 0


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


# --------------------------------------------------------------------------
# Ветко-корректные чтения артефактов задачи (SPEC T031): источник истины —
# ВЕТКА задачи, не рабочая копия пульта, которую чужой checkout (журнал
# T030, ~17:35 25.08.2026) может подменить у оркестратора под ногами.

def branch_head_sha(branch: str) -> str:
    """sha головы `branch` независимо от текущего чекаута; пустая строка —
    ветки нет в git или он не ответил (`res is None` — тот же вырожденный
    случай заглушек `gitcmd.git`, что у `head_sha`)."""
    res = git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
    return res.stdout.strip() if res is not None and res.returncode == 0 else ""


def on_foreign_branch(branch: str) -> bool:
    """True — рабочее дерево ТОЧНО стоит не на `branch`, и `branch` реально
    существует в git: единственный случай, когда чтение с ВЕТКИ задачи
    безопасно и осмысленно предпочесть рабочей копии (SPEC T031).

    Иначе (своя ветка и так выписана; ветка ещё не создана ролью — легитимный
    ранний момент жизни задачи до первого `git checkout -b`, ADR-0003 3д;
    git не ответил на сам вопрос «какая ветка сейчас») — прежнее поведение,
    рабочая копия: вырожденный случай, на котором стоял весь стенд
    заглушек `gitcmd.git` до этой задачи, остаётся вырожденным и после неё.
    """
    current = current_branch()
    return bool(branch and current and current != branch
               and branch_exists(branch))


def show(branch: str, rel: str) -> tuple[str | None, str]:
    """(текст, "") — файл `rel` из `branch`; (None, причина) — файла там
    нет, или git не ответил.

    Не путать с `review.artifact_text`: та ещё откатывается на рабочее
    дерево, если файла в ветке нет (законно для ревью WIP-diff'а, T011);
    здесь ветка — источник истины БЕЗ отката на дерево (SPEC T031,
    AC-1/AC-2) — откат на прежнее поведение делает вызывающий код через
    `on_foreign_branch`, а не эта функция молча.
    """
    try:
        res = git("show", f"{branch}:{rel}")
    except UnicodeDecodeError as exc:
        # git отдаёт байты файла как есть; strict-декодирование внутри
        # subprocess роняло бы всю команду трейсбеком (тот же приём, что
        # у review.artifact_text, T011 ревью 2).
        return None, f"не прочитан: {exc}"
    if res is None:
        return None, "git не ответил"
    if res.returncode == 0:
        return res.stdout, ""
    return None, res.stderr.strip()[:200] or f"git show вернул {res.returncode}"


def ls_tree_files(branch: str, rel_dir: str) -> list[str] | None:
    """Пути файлов под `rel_dir` в дереве `branch`; None — git не ответил.

    Пустой список — легитимный ответ (ветка есть, каталога в ней нет —
    тот же вырожденный случай, что у `guard.scan_acceptance_tests` для
    отсутствующей `acceptance_tests/` на диске), не путать с `None`.
    """
    res = git("ls-tree", "-r", "--name-only", branch, "--", rel_dir)
    if res is None or res.returncode != 0:
        return None
    return [p for p in res.stdout.splitlines() if p]
