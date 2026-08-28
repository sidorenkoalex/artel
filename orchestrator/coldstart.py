"""Наблюдаемый мир для холодного старта пульта (SPEC T049, ADR-0005 п.5).

`.artel/` — эфемерный кэш; истина при его потере (или при въезде нового
пульта в существующий проект) — то, что реально видно в репозитории:
каталоги задач, ветки, файлы RETRO, история `main`. Единственная функция
модуля, `observed_max_task_number`, отвечает на один вопрос — «какой
самый большой номер `Tnnn` уже где-то засвечен для этого target'а» — и
её зовут два независимых потребителя: `store.seed_task_counters`
(посев счётчика) и `doctor.check_task_counters` (проверка расхождения).

Ветки/RETRO/история `main` сканируются только для `config.DEFAULT_TARGET`:
сегодня `catalog.cmd_new` заводит номерные задачи только этого target'а
(ADR-0005 п.6 — формат id второго target ещё не выбран, tasks/T020/PLAN.md,
«Риски», п.2); для прочих target единственный источник — их собственный
`tasks/` под `.artel/projects/<target>/`.
"""
import re
from pathlib import Path

from . import config, gitcmd, store

_BRANCH_NUMBER_RE = re.compile(r"^task/t0*(\d+)-", re.IGNORECASE)
_MAIN_SUBJECT_RE = re.compile(r"^T0*(\d+):", re.IGNORECASE)
_RETRO_GLOB = "T*.md"


def observed_max_task_number(target: str) -> int:
    """Максимум номера `Tnnn`, наблюдаемый в мире для `target`; 0 — ничего
    не найдено (пустой проект — счётчик сеется от 1, как и раньше)."""
    best = _max_from_task_dirs(_tasks_dir(target))
    if target == config.DEFAULT_TARGET and _git_available():
        best = max(best, _max_from_branches())
        best = max(best, _max_from_retro())
        best = max(best, _max_from_main_history())
    return best


def _tasks_dir(target: str) -> Path:
    if target == config.DEFAULT_TARGET:
        return config.TASKS
    return config.PROJECTS / target / "tasks"


def _git_available() -> bool:
    """`.git` пульта — файл (worktree-gitlink, SPEC T045) либо каталог
    (обычный чекаут); `.exists()`, не `.is_dir()`, ловит оба случая."""
    return (config.ROOT / ".git").exists()


def _max_from_task_dirs(tasks_dir: Path) -> int:
    if not tasks_dir.is_dir():
        return 0
    best = 0
    for entry in tasks_dir.iterdir():
        if entry.is_dir():
            best = max(best, store.task_number(entry.name))
    return best


def _max_from_branches() -> int:
    branches = gitcmd.list_branches("task/")
    if not branches:
        return 0
    best = 0
    for branch in branches:
        match = _BRANCH_NUMBER_RE.match(branch)
        if match:
            best = max(best, int(match.group(1)))
    return best


def _max_from_retro() -> int:
    retro_dir = config.ROOT / "docs" / "retro"
    if not retro_dir.is_dir():
        return 0
    best = 0
    for path in retro_dir.glob(_RETRO_GLOB):
        best = max(best, store.task_number(path.stem))
    return best


def _max_from_main_history() -> int:
    """Best-effort (требование 1: «при доступности»): нет ветки `main` ещё
    (совсем свежий репозиторий) — 0, не отказ."""
    res = gitcmd.git("log", config.MAIN_BRANCH, "--format=%s")
    if res is None or res.returncode != 0:
        return 0
    best = 0
    for line in res.stdout.splitlines():
        match = _MAIN_SUBJECT_RE.match(line.strip())
        if match:
            best = max(best, int(match.group(1)))
    return best
