"""Пакет orchestrator/doctor -- файлы БД пульта в рабочих копиях задач.

SPEC 01M4FYTB8QWJNHYCP35K8QC4E3, требование 6: `.artel/state.db` и его
спутники SQLite в `.artel/projects/<проект>/worktrees/<id>/` тест,
импортировавший пакет из этой рабочей копии, читает как БД пульта — 09.10
так дважды подряд краснели одни и те же 7 тестов приёмки.
"""

from orchestrator import doctor

WORKTREE_DB_CHECK = "worktree-db-files"


def check_worktree_db_files() -> doctor.Check:
    root = doctor.repo_context.projects_root()
    if root == doctor.repo_context.NO_AREA:
        return doctor.Check(WORKTREE_DB_CHECK, "skip",
                            doctor.workspace.AREA_MISMATCH_REASON)
    found = []
    for worktrees in sorted(root.glob("*/worktrees")):
        for wt in sorted(p for p in worktrees.iterdir() if p.is_dir()):
            files = doctor.store.tree_db_files(wt)
            if files:
                paths = ", ".join(str(wt / rel) for rel in files)
                found.append(f"{paths} — убрать: artel.py worktree-db-clean "
                             f"{wt.name}")
    if not found:
        return doctor.Check(WORKTREE_DB_CHECK, "ok",
                            "в рабочих копиях задач файлов БД пульта нет")
    return doctor.Check(WORKTREE_DB_CHECK, "warn",
                        "файлы БД пульта в рабочих копиях задач: "
                        + "; ".join(found))
