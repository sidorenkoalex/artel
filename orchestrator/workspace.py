"""Рабочая поверхность задачи: git worktree в стандартном месте (SPEC T045).

Решение Оператора 27.08 (P3, «параллельные сессии», docs/roadmap.md):
агентные шаги задачи исполняются в её собственном git worktree
(`.artel/worktrees/<id>`), не в общей рабочей копии пульта — так два
`auto` разных задач не пересекаются рабочей поверхностью, а работа
Оператора в главной копии не задевается переключением ветки агентом
(инцидент 26–27.08, когда правка роадмапа Оператором ушла в ветку
чужой задачи).

Все операции идут через `gitcmd.git` (единственная точка мокинга,
которой уже пользуется весь пакет) — модуль сам не делает ни одного
сырого `Path.mkdir`/`shutil` вне `_seed_uncommitted_artifacts` (та
касается только уже реально созданного git'ом worktree).
"""
import shutil
import sys
from pathlib import Path

from . import config, gitcmd, store


def path(task_id: str) -> Path:
    """Стандартный путь worktree задачи (AC-1)."""
    return config.WORKTREES / task_id


def registered_paths() -> list[str]:
    """Пути всех worktree репозитория; первая запись — основной checkout
    (ROOT). Пустой список — git не ответил (вырожденный случай песочниц
    без реального git, тот же приём, что у `doctor._orphan_worktrees` до
    этой задачи)."""
    res = gitcmd.git("worktree", "list", "--porcelain")
    if res is None or res.returncode != 0:
        return []
    return [line.split(" ", 1)[1] for line in res.stdout.splitlines()
           if line.startswith("worktree ")]


def _registered(wt_path: Path) -> bool:
    return str(wt_path) in registered_paths()


def _seed_uncommitted_artifacts(task_id: str, wt_path: Path) -> None:
    """Переносит в свежий worktree то, что `cmd_new`/Оператор оставили
    некоммиченным в главной копии (`tasks/<id>/`).

    До этой задачи ветку задачи заводила сама роль (`git checkout -b`)
    В ТОЙ ЖЕ рабочей копии, где `cmd_new` уже положил SPEC.md/TZ.md на
    диск некоммичено — checkout untracked-файлы не трогает, и они просто
    оставались на месте. Отдельный worktree их не наследует: без явного
    переноса первый агентный шаг (например analyst) не увидел бы TZ.md
    вовсе. Только для СВЕЖЕЙ ветки: если ветка уже существовала, нужное
    содержимое уже закоммичено предыдущим шагом и лежит в самом checkout'е.
    """
    src = config.TASKS / task_id
    if not src.is_dir():
        return
    dst = wt_path / "tasks" / task_id
    if dst.exists():
        return
    shutil.copytree(src, dst)


def ensure(task_id: str, branch: str) -> tuple[Path, str | None]:
    """Создаёт (если нет) worktree задачи на её ветке; идемпотентно
    (AC-1, AC-2). (путь, причина отказа) — причина `None` при успехе.

    Идемпотентность — по факту регистрации в `git worktree list`, не по
    существованию каталога на диске (тот мог остаться после ручной
    уборки). Ветки ещё нет в git (роль до этой задачи создавала её сама
    первым действием миссии — с T045 это делает сама worktree-норма) —
    заводится от `config.MAIN_BRANCH` тем же действием, что и сам
    worktree (`git worktree add -b`), а не отдельным `checkout -b`.
    """
    wt_path = path(task_id)
    if _registered(wt_path):
        return wt_path, None
    if gitcmd.branch_exists(branch):
        res = gitcmd.git("worktree", "add", str(wt_path), branch)
    else:
        res = gitcmd.git("worktree", "add", "-b", branch, str(wt_path),
                         config.MAIN_BRANCH)
        if res is not None and res.returncode == 0:
            _seed_uncommitted_artifacts(task_id, wt_path)
    if res is None or res.returncode != 0:
        reason = (res.stderr.strip()[:300] if res is not None and res.stderr
                  else f"git worktree add вернул {res.returncode if res else '—'}")
        return wt_path, reason
    return wt_path, None


def on_task_branch(task_id: str, branch: str) -> bool | None:
    """True/False — worktree существует и стоит/не стоит на ветке задачи;
    `None` — worktree ещё не заведён (сверять не с чем, AC-8)."""
    wt_path = path(task_id)
    if not _registered(wt_path):
        return None
    res = gitcmd.in_repo(wt_path, "rev-parse", "--abbrev-ref", "HEAD")
    if res is None or res.returncode != 0:
        return None
    return res.stdout.strip() == branch


def remove(task_id: str) -> str:
    """Убирает worktree задачи (`kill`/`done`, требования 5, 6); строка —
    что вышло (по образцу `cleanup.drop_task_dir`/`drop_task_branch`)."""
    wt_path = path(task_id)
    if not _registered(wt_path):
        return f"worktree {wt_path} не найден — нечего убирать"
    res = gitcmd.git("worktree", "remove", "--force", str(wt_path))
    if res is None or res.returncode != 0:
        reason = res.stderr.strip()[:200] if res is not None else "git не ответил"
        return f"worktree {wt_path} не убран: {reason}"
    return f"убран worktree {wt_path}"


def cmd_workspace(task_id: str) -> None:
    """CLI `workspace <id>` (AC-1, AC-2): создаёт или выдаёт путь
    существующего worktree задачи."""
    conn = store.db()
    t = store.get_task(conn, task_id)
    wt_path, error = ensure(task_id, t["branch"])
    if error is not None:
        sys.exit(f"[{task_id}] worktree не создан: {error}")
    print(f"[{task_id}] worktree: {wt_path}")
