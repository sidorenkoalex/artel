"""Пакет orchestrator/doctor -- сверка ссылок документов задач
`refs/artifacts/<id>` (ADR-0021 п.3): ссылка живой задачи совпадает с
`origin`, закрытая ссылка не менялась после коммита закрытия. Ссылка и
`origin` — репозитория задачи (`artifact_branch.repo_for_target`): git
пульта для артели, git проекта для внешнего target.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""

from orchestrator import doctor

ARTIFACT_REF_SYNC_CHECK = "artifact-ref-sync"
_ARTIFACT_REFS_GLOB = "refs/artifacts/*"


def _origin_artifact_refs(repo=None) -> tuple[dict | None, str]:
    """({ссылка: sha} всех `refs/artifacts/*` в `origin`, "") — одним
    `ls-remote` на все задачи репозитория, а не по запросу на каждую:
    закрытых задач сотни. (None, причина) — `origin` не ответил. `repo` —
    клон проекта; `None` — репозиторий пульта."""
    args = ("ls-remote", "origin", _ARTIFACT_REFS_GLOB)
    res = (doctor.gitcmd.in_repo(repo, *args) if repo is not None
           else doctor.gitcmd.git(*args))
    if res is None:
        return None, "git не ответил"
    if res.returncode != 0:
        return None, (res.stderr or "").strip()[:200] or "ls-remote не удался"
    refs = {}
    for line in res.stdout.splitlines():
        sha, _, ref = line.partition("\t")
        if sha and ref:
            refs[ref.strip()] = sha.strip()
    return refs, ""


def _by_repo(task_ids, target_of) -> dict:
    """{репозиторий задачи: [id]} — порядок задач внутри группы прежний,
    группы — в порядке первой встречи (у артели одна группа, пульт)."""
    groups: dict = {}
    for task_id in task_ids:
        repo = doctor.artifact_branch.repo_for_target(target_of[task_id])
        groups.setdefault(repo, []).append(task_id)
    return groups


def _local_head(task_id: str, target: str | None) -> str:
    """Голова ссылки задачи в её репозитории — target уже известен из строки
    задачи, БД заново не спрашивается (закрытых задач сотни)."""
    repo = doctor.artifact_branch.repo_for_target(target)
    return doctor.artifact_branch._head(task_id, repo)


def _remote_refs(repo) -> tuple[dict | None, str]:
    """`_origin_artifact_refs` для репозитория задачи: пульт — прежний
    вызов без аргументов (его подменяют тесты фасада)."""
    if repo == doctor.config.ROOT:
        return doctor._origin_artifact_refs()
    return doctor._origin_artifact_refs(repo)


def _live_ref_problem(task_id: str, ref: str, local: str,
                      origin: str) -> str | None:
    if local == origin:
        return None
    if not origin:
        return (f"{task_id}: {ref} нет в origin (локально {local}) — "
                f"документы задачи не отправлены")
    return (f"{task_id}: {ref} расходится с origin — локально {local}, "
            f"в origin {origin}")


def _closed_ref_problem(task_id: str, ref: str, closing: str, local: str,
                        origin: str) -> str | None:
    if local != closing:
        return (f"{task_id}: закрытая {ref} изменилась после коммита "
                f"закрытия {closing} — голова {local or '(нет локально)'}")
    if origin != closing:
        return (f"{task_id}: закрытая {ref} в origin ({origin or 'нет'}) не "
                f"совпадает с коммитом закрытия {closing}")
    return None


def _closed_with_closing_sha(conn, tasks) -> list:
    """[(id, коммит закрытия)] закрытых задач с записью о коммите закрытия."""
    closed = []
    for t in tasks:
        if t["state"] in ("done", "killed"):
            closing = doctor.snapshot.closing_sha(conn, t["id"])
            if closing:
                closed.append((t["id"], closing))
    return closed


def _fix_unsent_closed_refs(conn) -> None:
    """`doctor --fix`: досылает в `origin` закрытую ссылку, чья локальная
    голова — коммит закрытия из журнала, а `origin` её не получил: у
    закрытой задачи переходов (`send_pending`) больше нет. Изменённую после
    закрытия ссылку не досылает; `push` без force. `origin` — репозитория
    задачи."""
    tasks = doctor.store.all_tasks(conn)
    target_of = {t["id"]: t["target"] for t in tasks}
    closed = dict(_closed_with_closing_sha(conn, tasks))
    for repo, ids in _by_repo(closed, target_of).items():
        if (repo == doctor.artifact_branch._NO_REPO
                or doctor.gitcmd.has_no_remote(repo)):
            continue
        remote, reason = _remote_refs(repo)
        if remote is None:
            print(f"  [FIX] закрытые ссылки документов не досланы: origin не "
                  f"ответил — {reason}")
            continue
        for task_id in ids:
            closing = closed[task_id]
            ref = doctor.artifact_branch.branch_name(task_id)
            if _local_head(task_id, target_of[task_id]) != closing:
                continue
            if remote.get(ref, "") == closing:
                continue
            ok = doctor.artifact_branch.push(task_id)
            print(f"  [FIX] {task_id}: коммит закрытия {closing} "
                  f"{'дослан в origin' if ok else 'в origin не дослан — см. журнал задачи'}")


def check_artifact_ref_sync(conn) -> list[doctor.Check]:
    """Два условия ADR-0021 п.3 для ссылок документов:

    - живая задача: локальная `refs/artifacts/<id>` ≠ ей же в `origin`
      (задача без локальной ссылки, заведённая до ADR-0021, не сверяется);
    - закрытая задача: голова ссылки (локально и в `origin`) ≠ коммиту
      закрытия из журнала (исторический снимок записи не несёт — не
      сверяется).

    Ссылка и `origin` — репозитория задачи: задачи внешнего проекта
    сверяются в его git и с его `origin`, не с пультом. `origin`
    репозитория не настроен или не ответил — `skip`, не `ok`."""
    tasks = doctor.store.all_tasks(conn)
    target_of = {t["id"]: t["target"] for t in tasks}
    closed = dict(_closed_with_closing_sha(conn, tasks))
    live = [t["id"] for t in tasks
            if t["state"] not in ("done", "killed")
            and _local_head(t["id"], t["target"])]
    if not live and not closed:
        return [doctor.Check(ARTIFACT_REF_SYNC_CHECK, "ok",
                             "ссылок документов для сверки нет")]
    problems, skips = [], []
    for repo, ids in _by_repo(live + list(closed), target_of).items():
        if (repo == doctor.artifact_branch._NO_REPO
                or doctor.gitcmd.has_no_remote(repo)):
            where = ("origin пульта" if repo == doctor.config.ROOT
                     else f"origin репозитория проекта ({', '.join(ids)})")
            skips.append(doctor.Check(ARTIFACT_REF_SYNC_CHECK, "skip",
                                      f"{where} не настроен — ссылки "
                                      f"документов не сверены"))
            continue
        remote, reason = _remote_refs(repo)
        if remote is None:
            skips.append(doctor.Check(ARTIFACT_REF_SYNC_CHECK, "skip",
                                      f"origin не ответил — ссылки документов "
                                      f"не сверены: {reason}"))
            continue
        for task_id in ids:
            ref = doctor.artifact_branch.branch_name(task_id)
            local = _local_head(task_id, target_of[task_id])
            if task_id in closed:
                problem = _closed_ref_problem(task_id, ref, closed[task_id],
                                              local, remote.get(ref, ""))
            else:
                problem = _live_ref_problem(task_id, ref, local,
                                            remote.get(ref, ""))
            if problem:
                problems.append(problem)
    if problems:
        return [doctor.Check(ARTIFACT_REF_SYNC_CHECK, "warn", p)
                for p in problems] + skips
    if skips:
        return skips
    return [doctor.Check(ARTIFACT_REF_SYNC_CHECK, "ok",
                         f"ссылки документов совпадают с origin (живых "
                         f"{len(live)}), закрытые — с коммитом закрытия "
                         f"({len(closed)})")]
