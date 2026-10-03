"""Пакет orchestrator/doctor -- сверка ссылок документов задач
`refs/artifacts/<id>` (ADR-0021 п.3): ссылка живой задачи совпадает с
`origin`, закрытая ссылка не менялась после коммита закрытия.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""

from orchestrator import doctor

ARTIFACT_REF_SYNC_CHECK = "artifact-ref-sync"
_ARTIFACT_REFS_GLOB = "refs/artifacts/*"


def _origin_artifact_refs() -> tuple[dict | None, str]:
    """({ссылка: sha} всех `refs/artifacts/*` в `origin`, "") — одним
    `ls-remote` на все задачи, а не по запросу на каждую: закрытых задач
    сотни. (None, причина) — `origin` не ответил."""
    res = doctor.gitcmd.git("ls-remote", "origin", _ARTIFACT_REFS_GLOB)
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
    закрытия ссылку не досылает; `push` без force."""
    closed = _closed_with_closing_sha(conn, doctor.store.all_tasks(conn))
    if not closed or doctor.gitcmd.has_no_remote(doctor.config.ROOT):
        return
    remote, reason = doctor._origin_artifact_refs()
    if remote is None:
        print(f"  [FIX] закрытые ссылки документов не досланы: origin не "
              f"ответил — {reason}")
        return
    for task_id, closing in closed:
        ref = doctor.artifact_branch.branch_name(task_id)
        if doctor.artifact_branch.ref_head(task_id) != closing:
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

    `origin` не настроен или не ответил — `skip`, не `ok`."""
    tasks = doctor.store.all_tasks(conn)
    closed = _closed_with_closing_sha(conn, tasks)
    live = [t["id"] for t in tasks
            if t["state"] not in ("done", "killed")
            and doctor.artifact_branch.ref_head(t["id"])]
    if not live and not closed:
        return [doctor.Check(ARTIFACT_REF_SYNC_CHECK, "ok",
                             "ссылок документов для сверки нет")]
    if doctor.gitcmd.has_no_remote(doctor.config.ROOT):
        return [doctor.Check(ARTIFACT_REF_SYNC_CHECK, "skip",
                             "origin пульта не настроен — ссылки документов "
                             "не сверены")]
    remote, reason = doctor._origin_artifact_refs()
    if remote is None:
        return [doctor.Check(ARTIFACT_REF_SYNC_CHECK, "skip",
                             f"origin не ответил — ссылки документов не "
                             f"сверены: {reason}")]
    problems = []
    for task_id in live:
        ref = doctor.artifact_branch.branch_name(task_id)
        problem = _live_ref_problem(task_id, ref,
                                    doctor.artifact_branch.ref_head(task_id),
                                    remote.get(ref, ""))
        if problem:
            problems.append(problem)
    for task_id, closing in closed:
        ref = doctor.artifact_branch.branch_name(task_id)
        problem = _closed_ref_problem(task_id, ref, closing,
                                      doctor.artifact_branch.ref_head(task_id),
                                      remote.get(ref, ""))
        if problem:
            problems.append(problem)
    if problems:
        return [doctor.Check(ARTIFACT_REF_SYNC_CHECK, "warn", p)
                for p in problems]
    return [doctor.Check(ARTIFACT_REF_SYNC_CHECK, "ok",
                         f"ссылки документов совпадают с origin (живых "
                         f"{len(live)}), закрытые — с коммитом закрытия "
                         f"({len(closed)})")]
