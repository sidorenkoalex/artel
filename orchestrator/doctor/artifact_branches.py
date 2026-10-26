"""Пакет orchestrator/doctor -- сверка ссылок документов задач
`refs/artifacts/<id>` (ADR-0021 п.3): ссылка живой задачи совпадает с
`origin`, закрытая ссылка не менялась после коммита закрытия. Ссылка и
`origin` — репозитория задачи (`artifact_branch.repo_for_target`): git
пульта для артели, git проекта для внешнего target.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""

from orchestrator import doctor, fsm

ARTIFACT_REF_SYNC_CHECK = "artifact-ref-sync"
_ARTIFACT_REFS_GLOB = "refs/artifacts/*"


def _origin_artifact_refs(repo) -> tuple[dict | None, str]:
    """({ссылка: sha} всех `refs/artifacts/*` в `origin`, "") — одним
    `ls-remote` на все задачи репозитория, а не по запросу на каждую:
    закрытых задач сотни. (None, причина) — `origin` не ответил. `repo` —
    клон проекта (ADR-0021 п.1-3), включая артель."""
    args = ("ls-remote", "origin", _ARTIFACT_REFS_GLOB)
    res = doctor.gitcmd.in_repo(repo, *args)
    if res is None:
        return None, "git не ответил"
    if res.returncode != 0:
        return None, (res.stderr or "").strip()[:200] or "ls-remote не удался"
    refs = {}
    epic_refs = "refs/artifacts/" + doctor.config.EPIC_REF_NAME_PREFIX
    for line in res.stdout.splitlines():
        sha, _, ref = line.partition("\t")
        # Ссылка эпика `refs/artifacts/epic-<id>` — не задача (SPEC
        # 01M5TBFCVFNN95BHH0E9C6KBKB, требование 15).
        if sha and ref and not ref.strip().startswith(epic_refs):
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
    """`_origin_artifact_refs` для репозитория задачи — клон артели или
    клон внешнего проекта, явно (ADR-0021 п.1-3)."""
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
        if t["state"] in fsm.TERMINAL_STATES:
            closing = doctor.snapshot.closing_sha(conn, t["id"])
            if closing:
                closed.append((t["id"], closing))
    return closed


def _historical_snapshots(conn, tasks, closed: dict, target_of: dict) -> dict:
    """{id: коммит снимка} исторических снимков, которые сверяются по
    правилу закрытой ссылки: без записи о коммите закрытия и не живые.
    `target_of` дополняется артелью — у задачи T-серии строки `tasks` нет,
    а снимки команда пишет только в клоне артели."""
    live_ids = {t["id"] for t in tasks if t["state"] not in fsm.TERMINAL_STATES}
    historical = {}
    for task_id, sha in doctor.snapshot.history_snapshots(conn).items():
        if task_id in closed or task_id in live_ids:
            continue
        historical[task_id] = sha
        target_of.setdefault(task_id, doctor.config.DEFAULT_TARGET)
    return historical


def _historical_ref_problem(task_id: str, ref: str, snapshot_sha: str,
                            local: str, origin: str) -> str | None:
    if local != snapshot_sha:
        return (f"{task_id}: историческая {ref} изменилась после "
                f"исторического снимка {snapshot_sha} — голова "
                f"{local or '(нет локально)'}")
    if origin != snapshot_sha:
        return (f"{task_id}: историческая {ref} в origin ({origin or 'нет'}) "
                f"не совпадает с историческим снимком {snapshot_sha}")
    return None


def _historical_summary(historical: dict) -> str:
    """Хвост строки `ok`: число сверенных исторических снимков (пусто — их
    нет, прежний текст строки не меняется)."""
    return (f", исторические — с коммитом снимка ({len(historical)})"
            if historical else "")


def _push_closing_sha(source, repo, task_id: str, closing: str) -> None:
    """Досылка коммита закрытия `closing` из репозитория `source` (клон или
    главная копия пульта) в `origin` клона `repo` — продвижением
    `refs/artifacts/<id>` без force: непродвигающее обновление `origin`
    отклоняет, и это называется строкой `[FIX]`."""
    ref = doctor.artifact_branch.branch_name(task_id)
    url = doctor.gitcmd.in_repo(repo, "remote", "get-url", "origin")
    if url is None or url.returncode != 0 or not url.stdout.strip():
        print(f"  [FIX] {task_id}: коммит закрытия {closing} в origin не "
              f"дослан — адрес origin клона не прочитан")
        return
    res = doctor.gitcmd.in_repo(source, "push", "-q", url.stdout.strip(),
                                f"{closing}:{ref}")
    if res is not None and res.returncode == 0:
        print(f"  [FIX] {task_id}: коммит закрытия {closing} дослан в origin "
              f"из {source}")
        return
    stderr = ((res.stderr or "").strip()[:200] if res is not None
              else "git не ответил")
    print(f"  [FIX] {task_id}: коммит закрытия {closing} в origin не дослан "
          f"из {source} — {stderr}")


def _fix_unsent_closed_ref(task_id: str, target: str | None, repo,
                           closing: str) -> None:
    """Одна закрытая задача, чья ссылка в `origin` ≠ коммиту закрытия.

    Объект коммита закрытия в клоне есть — прежнее правило: голова ссылки
    = коммиту закрытия — `artifact_branch.push`; голова другая (ссылку
    меняли после закрытия) — не досылается; локальной ссылки нет —
    досылается сам коммит из клона. Объекта в клоне нет — у задачи артели
    (признак `repo_context.is_artel`) он ищется в git главной копии пульта
    (переходный период этапа 2 ADR-0021: коммиты закрытия, сделанные до
    клона, жили только там; SPEC 01M484RNV3QBDY3B0M16J916ZP, строка 28).
    Не нашёлся — строка `[FIX]`, не молчание (SPEC
    01M446WV7S94FTZGJCGMPJ667F, требование 3)."""
    if doctor.gitcmd.commit_exists(closing, repo=repo):
        local = _local_head(task_id, target)
        if local == closing:
            ok = doctor.artifact_branch.push(task_id)
            print(f"  [FIX] {task_id}: коммит закрытия {closing} "
                  f"{'дослан в origin' if ok else 'в origin не дослан — см. журнал задачи'}")
        elif not local:
            _push_closing_sha(repo, repo, task_id, closing)
        return
    main_copy = doctor.config.ROOT
    if (doctor.repo_context.is_artel(target or doctor.config.DEFAULT_TARGET)
            and doctor.gitcmd.commit_exists(closing, repo=main_copy)):
        _push_closing_sha(main_copy, repo, task_id, closing)
        return
    print(f"  [FIX] {task_id}: коммит закрытия {closing} не найден ни в "
          f"клоне, ни в главной копии — в origin не дослан")


def _fix_unsent_closed_refs(conn) -> None:
    """`doctor --fix`: досылает в `origin` коммит закрытия, который `origin`
    не получил: досылка идёт коммитом паспорта на переходе (`store.set_state`
    → `append_passport_line`), а у закрытой задачи переходов больше нет.
    Изменённую после закрытия ссылку не досылает; `push` без force.
    `origin` — репозитория задачи; правило по задаче —
    `_fix_unsent_closed_ref`."""
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
            if remote.get(ref, "") == closing:
                continue
            _fix_unsent_closed_ref(task_id, target_of[task_id], repo, closing)


def check_artifact_ref_sync(conn) -> list[doctor.Check]:
    """Два условия ADR-0021 п.3 для ссылок документов:

    - живая задача: локальная `refs/artifacts/<id>` ≠ ей же в `origin`
      (задача без локальной ссылки, заведённая до ADR-0021, не сверяется);
    - закрытая задача: голова ссылки (локально и в `origin`) ≠ коммиту
      закрытия из журнала (снимок закрытия ADR-0018 записи не несёт — не
      сверяется). Локальной ссылки нет, а в `origin` она равна коммиту
      закрытия — не расхождение: такие задачи считаются в одной строке
      `ok` с подсказкой `docs --fetch-all`;
    - исторический снимок команды `artifact-history-snapshots` (ADR-0021,
      этап 4): то же правило с коммитом снимка из журнала
      (`snapshot.HISTORY_ACTION`), в том числе для задачи без строки
      `tasks` — target берётся из записи журнала. Запись о коммите
      закрытия и живое состояние задачи главнее записи о снимке.

    Ссылка и `origin` — репозитория задачи: задачи внешнего проекта
    сверяются в его git и с его `origin`, не с пультом. `origin`
    репозитория не настроен или не ответил — `skip`, не `ok`."""
    tasks = doctor.store.all_tasks(conn)
    target_of = {t["id"]: t["target"] for t in tasks}
    closed = dict(_closed_with_closing_sha(conn, tasks))
    live = [t["id"] for t in tasks
            if t["state"] not in fsm.TERMINAL_STATES
            and _local_head(t["id"], t["target"])]
    historical = _historical_snapshots(conn, tasks, closed, target_of)
    if not live and not closed and not historical:
        return [doctor.Check(ARTIFACT_REF_SYNC_CHECK, "ok",
                             "ссылок документов для сверки нет")]
    problems, skips = [], []
    only_in_origin = 0
    fixed = {**historical, **closed}
    for repo, ids in _by_repo(live + list(fixed), target_of).items():
        if (repo == doctor.artifact_branch._NO_REPO
                or doctor.gitcmd.has_no_remote(repo)):
            where = ("origin пульта" if repo == doctor.workspace.repo(
                        doctor.config.DEFAULT_TARGET)
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
            if task_id in fixed:
                if not local and remote.get(ref, "") == fixed[task_id]:
                    only_in_origin += 1
                    continue
                problem = (_closed_ref_problem if task_id in closed
                           else _historical_ref_problem)(
                    task_id, ref, fixed[task_id], local, remote.get(ref, ""))
            else:
                problem = _live_ref_problem(task_id, ref, local,
                                            remote.get(ref, ""))
            if problem:
                problems.append(problem)
    summary = _only_in_origin_summary(only_in_origin)
    if problems:
        return [doctor.Check(ARTIFACT_REF_SYNC_CHECK, "warn", p)
                for p in problems] + skips + summary
    if skips:
        return skips + summary
    return [doctor.Check(ARTIFACT_REF_SYNC_CHECK, "ok",
                         f"ссылки документов совпадают с origin (живых "
                         f"{len(live)}), закрытые — с коммитом закрытия "
                         f"({len(closed) - only_in_origin})"
                         + _historical_summary(historical))] + summary


def _only_in_origin_summary(count: int) -> list:
    """Одна строка `ok` на прогон о закрытых задачах, чья ссылка есть только
    в `origin` и равна там коммиту закрытия (SPEC 01M446WV7S94FTZGJCGMPJ667F,
    требование 2): это не расхождение, клону просто не хватает ссылок."""
    if not count:
        return []
    return [doctor.Check(ARTIFACT_REF_SYNC_CHECK, "ok",
                         f"закрытых задач без локальной ссылки, совпадающих в "
                         f"origin с коммитом закрытия: {count} — подтянуть: "
                         f"artel.py docs --fetch-all")]
