"""Git-хелперы планки: дифф КОДОВОЙ ветки задачи и текст PLAN.md.

Критерии AC-18/AC-19 говорят буквально о дифе ветки задачи относительно
базы интеграции и о приложении к PLAN.md — это состояние настоящего
репозитория рабочей копии, песочницей с фейковым git его не изобразить
(тот же приём, что `tests/test_git_fixation.py::RealPultGitTest`).

PLAN.md читается ТОЛЬКО с артефактной ветки (`gitcmd.show`): на диске в
среде прогона планки пультом лежит один `acceptance_tests/`
(`orchestrator/acceptance.py::materialize_from_branch`), и чтение его с
диска зелено у автора планки и красно на гейте.
"""
import subprocess
import tempfile
from pathlib import Path

from orchestrator import artifact_branch, gitcmd

REPO_ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "01M3009Y9AGGY6ZCFA7H1HJ1TD"


def merge_base() -> str:
    """sha точки расхождения ветки задачи с базой интеграции: `origin/main`,
    а при его отсутствии — локальная `main` (у клона без origin-ссылок
    сверять больше не с чем)."""
    for ref in ("origin/main", "main"):
        res = subprocess.run(["git", "merge-base", ref, "HEAD"],
                             cwd=REPO_ROOT, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    raise AssertionError("git не ответил на merge-base ни с origin/main, "
                         "ни с main")


def changed_paths_since_main(*pathspecs: str) -> list:
    """Пути, изменённые веткой задачи от точки расхождения до РАБОЧЕГО
    дерева (закоммиченное и незакоммиченное разом)."""
    args = ["git", "diff", "--name-only", merge_base()]
    if pathspecs:
        args.append("--")
        args.extend(pathspecs)
    res = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True,
                         check=True)
    return [line for line in res.stdout.splitlines() if line]


def plan_text() -> str | None:
    """Текст PLAN.md с артефактной ветки задачи; `None` — его там ещё нет."""
    text, _reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                f"tasks/{TASK_ID}/PLAN.md")
    return text or None


def applies_to_integration_base(diff_text: str) -> tuple:
    """(применяется ли, диагностика) — `git apply --check` диффа на чистом
    дереве базы интеграции: отдельный git-worktree во временном каталоге.

    Дифф, уже применённый Оператором в main (штатный путь приложения к
    PLAN), принимается обратным наложением — он корректен, просто мир
    ушёл вперёд."""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "worktree", "add", "--detach", "--quiet", tmp,
                        merge_base()],
                       cwd=REPO_ROOT, check=True, capture_output=True,
                       text=True)
        try:
            forward = subprocess.run(["git", "apply", "--check", "-"],
                                     cwd=tmp, input=diff_text,
                                     capture_output=True, text=True)
            if forward.returncode == 0:
                return True, ""
            reverse = subprocess.run(
                ["git", "apply", "--check", "--reverse", "-"],
                cwd=tmp, input=diff_text, capture_output=True, text=True)
            if reverse.returncode == 0:
                return True, ""
            return False, f"{forward.stderr}\n{reverse.stderr}"
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", tmp],
                           cwd=REPO_ROOT, check=True, capture_output=True,
                           text=True)
