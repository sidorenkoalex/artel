"""Общие хелперы приёмочных тестов задачи 01M2DC6SQVSANMECXPDZJDP75D
(рефакторинг R8: общая песочница тестов).

Git-хелперы читают состояние РЕАЛЬНОГО репозитория этого рабочего
каталога (worktree задачи), тем же приёмом, что и прецедент
`tasks/01M2CN465WEDCF6D77V37FJ82E/acceptance_tests/_util.py` — критерии
AC-3/AC-6 говорят буквально о дифе КОДОВОЙ ветки задачи относительно
`main`, песочницей с фейковым git это не воспроизвести.
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TESTS_DIR = REPO_ROOT / "tests"


def merge_base(ref: str = "origin/main") -> str:
    """sha точки расхождения ветки задачи с `ref` (по умолчанию
    `origin/main` — база интеграции; локальная `main` рабочей копии пульта
    — пин и может отставать от origin)."""
    res = subprocess.run(["git", "merge-base", ref, "HEAD"], cwd=REPO_ROOT,
                         capture_output=True, text=True, check=True)
    return res.stdout.strip()


def diff_since_main(*pathspecs: str, unified: int = None,
                    diff_filter: str = None) -> str:
    """`git diff <merge-base>..рабочее дерево` — включает и закоммиченные,
    и незакоммиченные правки ветки задачи."""
    args = ["git", "diff"]
    if unified is not None:
        args.append(f"--unified={unified}")
    if diff_filter:
        args.append(f"--diff-filter={diff_filter}")
    args.append(merge_base())
    if pathspecs:
        args.append("--")
        args.extend(pathspecs)
    res = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True,
                         check=True)
    return res.stdout


def changed_paths_since_main(*pathspecs: str, diff_filter: str = None) -> list:
    args = ["git", "diff", "--name-only"]
    if diff_filter:
        args.append(f"--diff-filter={diff_filter}")
    args.append(merge_base())
    if pathspecs:
        args.append("--")
        args.extend(pathspecs)
    res = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True,
                         check=True)
    return [line for line in res.stdout.splitlines() if line]


def plan_text(task_id: str) -> str | None:
    """Текст PLAN.md — из артефактной ветки задачи (там он живёт по
    ADR-0016; на диске при прогоне планки пультом лежит только
    `acceptance_tests/`), тем же примитивом, что читает артефакты сам
    пульт (`gitcmd.show`). Диск — запасной источник для ручного прогона
    роли до автокоммита (тот же приём, что и прецедент AC-4
    01M2CN465WEDCF6D77V37FJ82E)."""
    from orchestrator import artifact_branch, gitcmd

    text, _reason = gitcmd.show(artifact_branch.branch_name(task_id),
                                f"tasks/{task_id}/PLAN.md")
    if text:
        return text
    disk_path = REPO_ROOT / "tasks" / task_id / "PLAN.md"
    if disk_path.is_file():
        return disk_path.read_text(encoding="utf-8")
    return None
