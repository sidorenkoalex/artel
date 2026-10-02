"""Пакет orchestrator/doctor -- уборка игнорируемых файлов ссылок документов задач.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""

from orchestrator import doctor


# --- уборка игнорируемых файлов артефактных веток (SPEC ------------------
# 01M1KVG3KSCY47HWXWF5HM0E76, требование 4, AC-5) -------------------------

def _fix_ignored_artifact_files(conn) -> None:
    """`doctor --fix`: убирает из ссылки документов `refs/artifacts/<id>`
    (ADR-0021 п.3) КАЖДОЙ живой задачи файлы, которые `.gitignore` пульта (`config.ROOT`) считает
    игнорируемыми (тот же критерий, что `checkpoint._commit_external_
    step_artifacts` уже применяет к новым автокоммитам, `gitcmd.
    check_ignore`) — легализация ADR-0013 «вариант A» для файлов,
    занесённых ДО этой задачи (инцидент 03.09, SPEC «Контекст»).

    Плотницкая запись (`artifact_branch.commit_files`, `remove=`) пишет
    прямо в объектную базу `config.ROOT`, не в рабочее дерево — `main`
    этим действием не трогается (AC-5, третья проверка); новый коммит
    перефиксирует документы задачи (`store.record_fixation`) — это запись
    пульта, не правка мимо гейтов. `done`/`killed` задачи пропускаются —
    их ссылка закрыта коммитом закрытия и не меняется (тот же
    фильтр, что `check_branch_freshness`/`check_orphans` уже применяют к
    активным задачам).

    Задача без затронутых файлов — без изменений и без записи в журнал
    (нечего убирать); `git check-ignore` не ответил — тихая деградация,
    та же, что у `checkpoint` (не коммитить вслепую без фильтрации).
    """
    for row in doctor.store.all_tasks(conn):
        if row["state"] in ("done", "killed"):
            continue
        task_id = row["id"]
        branch = doctor.artifact_branch.branch_name(task_id)
        existing = doctor.gitcmd.ls_tree_files(branch, f"tasks/{task_id}") or []
        if not existing:
            continue
        ignored = doctor.gitcmd.check_ignore(existing)
        if not ignored:
            continue
        to_remove = sorted(ignored)
        message = (f"{task_id}: уборка игнорируемых файлов артефактной "
                  f"ветки (doctor --fix)")
        commit_sha = doctor.artifact_branch.commit_files(task_id, {}, message,
                                                   remove=to_remove)
        if not commit_sha:
            continue
        detail = f"{message} (sha {commit_sha}); убрано: {', '.join(to_remove)}"
        doctor.store.journal(conn, task_id, "doctor",
                      "уборка игнорируемых файлов артефактной ветки", detail)
        doctor.store.record_fixation(conn, task_id)
        print(f"  [FIX] {task_id}: убрано {len(to_remove)} игнорируемых "
              f"файлов из артефактной ветки")


