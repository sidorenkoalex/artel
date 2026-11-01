"""Команда `mr-sync [<id>…] [--confirm [--by-content]]`: сверка MR задачи
проекта с `merge_gate: target-human` и нахождения её правки в `base`,
закрытие `done` по подтверждению Оператора (SPEC 01M6AB4VE2R0Q2V5D4MMJGNGH7;
ADR-0029 п. 2, 3, 10).

Сверка только читает: `fetch` базовой ветки в клон пульта и
`forge.mr_status`; MR и ветку задачи она не меняет. Итог — ровно один,
первая подошедшая строка таблицы требования 3 SPEC (порядок первых строк —
ANSWER-1 п. 1). Признаки нахождения правки считаются от точки ответвления,
записанной `approve` гейта мержа на переходе в `awaiting_human`
(`record_fork_point`), до подтверждённой Оператором головы
(`fsm_merge_gate._confirmed_code_head`):
(а) коммит вливания MR — предок `origin/<base>` (только у влитого MR,
ANSWER-1 п. 3); (б) коммиты задачи в `base` по содержимому (`git cherry`);
(в) обратное наложение диффа задачи на `origin/<base>` проходит, прямое —
нет.

`--confirm` пересчитывает итог той же сверкой и закрывает задачу только при
«влит этим MR» или «в базе, влит иначе» (по одному признаку (в) — ещё и с
`--by-content`). Надзор эпика (`auto.py`) зовёт сверку без `--confirm` —
закрытие остаётся командой Оператора (инвариант 18).
"""
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import (artifact_branch, forge, fsm, gitcmd, lease,
               repo_context, store, targets, workspace)

USAGE = "mr-sync [<id>…] | mr-sync <id> --confirm [--by-content]"
CONFIRM_FLAG = "--confirm"
BY_CONTENT_FLAG = "--by-content"

# Итоги сверки — тексты таблицы требования 3 SPEC.
UNKNOWN = "неизвестно"
NOT_FOUND = "MR не найден"
RETARGETED = "MR переведён на другую ветку"
MERGED_THIS = "влит этим MR"
OTHER_WAY = "в базе, влит иначе"
PARTIAL = "в базе частично"
ABSENT = "нет в базе"
CHANGED_AFTER = "после вливания файлы менялись"
BY_CONTENT = "по содержимому"
CLOSING_OUTCOMES = (MERGED_THIS, OTHER_WAY)

# Признаки нахождения правки (требование 3).
BY_MERGE, BY_COMMITS, BY_DIFF = "а", "б", "в"

MR_STATES = {"opened": "открыт", "merged": "влит",
             "closed": "закрыт без вливания"}
NOT_FOUND_CODE = "(404)"

# Действия журнала.
SYNC_ACTION = "mr-sync: сверка"
# Смена итога относительно прошлой сверки — значима для `watch`
# (требование 6).
OUTCOME_CHANGED_ACTION = "mr-sync: итог сменился"
FORK_POINT_ACTION = "точка ответвления записана"
ACCEPTED_HEAD_ACTION = "голова ветки на сервере принята"
CONFIRM_REFUSED_ACTION = "mr-sync --confirm отклонён"
DOCS_UNSYNCED_ACTION = "mr-sync --confirm отклонён: документы не совпадают с origin"
# Начало детали перехода в `escalated` по инцидентам требования 5: по нему
# возврат из эскалации узнаёт эскалацию «чужой коммит» (ANSWER-1 п. 6).
FOREIGN_COMMIT_DETAIL = "чужой коммит в ветке задачи на сервере"
MR_DONE_EARLY_DETAIL = "MR задачи влит или закрыт до awaiting_human"

CONFIRM_HINT = ("правки задачи в base нет или она не подтверждена — ожидание "
                "людей проекта (повтори mr-sync позже), либо artel.py kill "
                "{id} и новая задача")


@dataclass
class Sync:
    """Итог одной сверки задачи."""
    outcome: str
    reason: str = ""
    by: str = ""
    proof_sha: str = ""
    changed_after: bool = False
    lines: list = field(default_factory=list)
    incident: str = ""

    def text(self) -> str:
        if self.outcome == UNKNOWN:
            return f"{UNKNOWN} — {self.reason}"
        mark = f" ({CHANGED_AFTER})" if self.changed_after else ""
        if self.outcome == OTHER_WAY:
            mark = f" (по ({self.by}))"
        return self.outcome + mark


# ------------------------------------------------------------------ git


def _git(repo, *args, input: str | None = None):
    """git в клоне проекта, вывод строкой; `None` — git не запустился."""
    try:
        return gitcmd.read(repo, *args, text=True, input=input)
    except OSError:
        return None


def _out(repo, *args, input: str | None = None) -> str | None:
    """stdout git; `None` — git не ответил успехом."""
    res = _git(repo, *args, input=input)
    if res is None or res.returncode != 0:
        return None
    return res.stdout


def _apply_passes(repo, base_sha: str, patch: str, reverse: bool) -> bool:
    """`git apply --check` диффа `patch` на дерево `base_sha` — временным
    индексом, без рабочего дерева клона."""
    with tempfile.TemporaryDirectory(prefix="artel-mr-sync-") as tmp:
        env = gitcmd.pult_env({**os.environ,
                               "GIT_INDEX_FILE": os.path.join(tmp, "index")})
        read = subprocess.run(["git", "-C", str(repo), "read-tree", base_sha],
                              capture_output=True, text=True, env=env)
        if read.returncode != 0:
            raise GitFailure(f"read-tree {base_sha[:12]}: "
                              f"{read.stderr.strip()[:200]}")
        argv = ["git", "-C", str(repo), "apply", "--cached", "--check",
                "--binary", "--whitespace=nowarn"]
        if reverse:
            argv.append("-R")
        res = subprocess.run([*argv, "-"], input=patch, capture_output=True,
                             text=True, env=env)
        return res.returncode == 0


class GitFailure(Exception):
    """git не ответил на шаге сверки — итог «неизвестно»."""


def _need(value, what: str):
    if value is None:
        raise GitFailure(f"git не ответил: {what}")
    return value


def _patch_ids(repo, text: str) -> dict:
    """{sha коммита: patch-id} вывода `git log -p`/`git show`."""
    out = _need(_out(repo, "patch-id", "--stable", input=text), "patch-id")
    ids = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2:
            ids[parts[1]] = parts[0]
    return ids


def _commits_sign(repo, base_sha: str, fork: str, head: str) -> tuple:
    """Признак (б): (коммиты задачи, найденные в базе по содержимому, sha
    закрытия). sha закрытия — самый поздний коммит `base` после точки
    ответвления с patch-id последнего коммита задачи (ANSWER-1 п. 2); "" —
    такого нет."""
    commits = _need(_out(repo, "rev-list", "--no-merges", f"{fork}..{head}"),
                    "rev-list коммитов задачи").split()
    cherry = _need(_out(repo, "cherry", base_sha, head, fork),
                   "cherry").splitlines()
    marks = {line[2:].strip(): line[:1] for line in cherry if len(line) > 2}
    found = [sha for sha in commits if marks.get(sha) == "-"]
    closing = ""
    if commits and commits[0] in found:
        last = _patch_ids(repo, _need(_out(repo, "show", "--no-color",
                                           commits[0]), "show"))
        wanted = last.get(commits[0])
        log = _need(_out(repo, "log", "-p", "--no-color", "--no-merges",
                         f"{fork}..{base_sha}"), "log базы")
        base_ids = _patch_ids(repo, log)
        order = _need(_out(repo, "rev-list", "--no-merges",
                           f"{fork}..{base_sha}"), "rev-list базы").split()
        closing = next((sha for sha in order
                        if wanted and base_ids.get(sha) == wanted), "")
    return commits, found, closing


def _diff_sign(repo, base_sha: str, fork: str, head: str) -> tuple:
    """Признак (в): (проходит ли, строки доказательства по файлам)."""
    files = _need(_out(repo, "diff", "--name-only", fork, head),
                  "diff --name-only").split("\n")
    files = [f for f in files if f]
    lines = []
    for rel in files:
        patch = _need(_out(repo, "diff", "--binary", fork, head, "--", rel),
                      f"diff {rel}")
        back = _apply_passes(repo, base_sha, patch, reverse=True)
        ahead = _apply_passes(repo, base_sha, patch, reverse=False)
        lines.append(f"  (в) {rel}: обратное наложение — "
                     f"{'проходит' if back else 'не проходит'}, прямое — "
                     f"{'проходит' if ahead else 'не проходит'}")
    if not files:
        return False, ["  (в) дифф задачи пуст"]
    whole = _need(_out(repo, "diff", "--binary", fork, head), "diff задачи")
    passes = (_apply_passes(repo, base_sha, whole, reverse=True)
              and not _apply_passes(repo, base_sha, whole, reverse=False))
    return passes, lines


# ------------------------------------------------------- голова на сервере


def expected_server_head(conn, task_id: str) -> str:
    """Голова ветки задачи на сервере, которую пульт считает своей:
    последняя из записей «ветка отправлена» и «голова принята» (требование
    5); "" — ни одной."""
    row = store.last_task_step_of(conn, task_id, (
        gitcmd.PUSH_SENT_ACTION, gitcmd.PUSH_SENT_LEGACY_ACTION,
        ACCEPTED_HEAD_ACTION))
    return (row["detail"] or "").split(" ")[0] if row is not None else ""


def foreign_commit(conn, task_id: str, branch: str, repo) -> str:
    """Инцидент «чужой коммит» при открытом MR (требование 5): голова
    ветки на сервере не равна своей; "" — инцидента нет (в том числе ветки
    на сервере нет). Сбой чтения сервера — `GitFailure`."""
    expected = expected_server_head(conn, task_id)
    remote, why = gitcmd.remote_ref_state(branch, repo=repo)
    if why:
        raise GitFailure(f"голова ветки {branch} на сервере не прочитана: "
                          f"{why}")
    if not remote or not expected or remote == expected:
        return ""
    return (f"{FOREIGN_COMMIT_DETAIL}: голова {branch} {remote} — не "
            f"последняя своя {expected}; ветка не перезаписана")


def accept_server_head(conn, task_id: str) -> None:
    """Возврат из эскалации «чужой коммит» (`fsm._approve_escalated`,
    ANSWER-1 п. 6): голова ветки на сервере на момент этого `approve`
    записывается принятой — дальше чужой коммит сверяется с ней. Иная
    эскалация голову не принимает."""
    steps = store.task_steps(conn, task_id)
    last = next((r for r in reversed(steps)
                 if r["action"] == "state -> escalated"), None)
    if last is None or not (last["detail"] or "").startswith(
            FOREIGN_COMMIT_DETAIL):
        return
    row = store.get_task(conn, task_id)
    ctx = repo_context.resolve(row["target"])
    remote = gitcmd.remote_branch_sha(row["branch"],
                                      repo=repo_context.path_or_none(ctx))
    if not remote:
        return
    store.journal(conn, task_id, "operator", ACCEPTED_HEAD_ACTION,
                  f"{remote} {row['branch']}")


def record_fork_point(conn, task_id: str, head: str, ctx) -> str:
    """Точка ответвления `git merge-base <подтверждённая голова>
    origin/<base>` на `approve` гейта мержа (требование 2) — в БД и журнал;
    "" — не вычислена (тоже в журнал)."""
    base_sha, why = gitcmd.fetch_ref_sha("origin", ctx.base, repo=ctx.path)
    fork = (_out(ctx.path, "merge-base", head, base_sha) or "").strip() \
        if base_sha else ""
    if not fork:
        store.journal(conn, task_id, "orchestrator", FORK_POINT_ACTION,
                      f"не вычислена: {why or 'merge-base не ответил'}")
        return ""
    store.update_task(conn, task_id, fork_point=fork)
    store.journal(conn, task_id, "orchestrator", FORK_POINT_ACTION,
                  f"{fork} (merge-base {head} и {ctx.base} {base_sha})")
    return fork


# --------------------------------------------------------------- сверка


def _mr_state_text(mr: forge.MergeRequest) -> str:
    return MR_STATES.get(mr.state or "", f"статус {mr.state!r}")


def evaluate(conn, task_id: str) -> Sync:
    """Итог сверки задачи по таблице требования 3 (без записи в БД)."""
    from . import fsm_merge_gate
    row = store.get_task(conn, task_id)
    target, branch = row["target"], row["branch"]
    ctx = repo_context.resolve(target)
    if ctx is None:
        return Sync(UNKNOWN, reason=f"запись проекта {target} не прочитана")
    iid, _url = store.mr_link(row)
    if iid is None:
        return Sync(NOT_FOUND, lines=["  MR: ссылки на MR в БД нет"])
    mr = forge.mr_status(target, iid)
    if mr.reason:
        if NOT_FOUND_CODE in mr.reason:
            return Sync(NOT_FOUND, lines=[f"  MR !{iid}: {mr.reason}"])
        return Sync(UNKNOWN, reason=f"статус MR !{iid} не прочитан: {mr.reason}")
    lines = [f"  MR !{iid}: {_mr_state_text(mr)}, целевая ветка "
             f"{mr.target_branch or '—'}"]
    if mr.target_branch is None:
        return Sync(UNKNOWN, lines=lines,
                    reason=f"в ответе хостинга о MR !{iid} нет target_branch")
    if mr.target_branch != ctx.base:
        return Sync(RETARGETED, lines=lines + [
            f"  целевая ветка MR {mr.target_branch} — не base проекта {ctx.base}"])
    repo = ctx.path
    try:
        if mr.state == "opened":
            incident = foreign_commit(conn, task_id, branch, repo)
            if incident:
                return Sync(UNKNOWN, lines=lines, incident=incident,
                            reason="инцидент: " + incident)
        return _signs(conn, task_id, row, ctx, mr, lines,
                      fsm_merge_gate._confirmed_code_head(conn, task_id))
    except GitFailure as exc:
        return Sync(UNKNOWN, lines=lines, reason=str(exc))


def _signs(conn, task_id: str, row, ctx, mr, lines: list, head: str) -> Sync:
    repo, base = ctx.path, ctx.base
    base_sha, why = gitcmd.fetch_ref_sha("origin", base, repo=repo)
    if not base_sha:
        raise GitFailure(f"git fetch origin {base} не удался: {why}")
    fork = row["fork_point"] or ""
    if not fork:
        raise GitFailure("точка ответвления задачи не записана")
    if not head:
        raise GitFailure("подтверждённой головы задачи нет")
    lines.append(f"  точка ответвления {fork}, подтверждённая голова {head}, "
                 f"origin/{base} {base_sha}")
    merge_commit = ""
    if mr.state == "merged":
        merge_commit = mr.merge_commit_sha or mr.squash_commit_sha or mr.sha or ""
    by_merge = bool(merge_commit) and gitcmd.is_ancestor(merge_commit, base_sha,
                                                         repo=repo)
    if mr.state != "merged":
        lines.append("  (а) не применяется: MR не влит")
    else:
        lines.append(f"  (а) коммит вливания {merge_commit or '—'} — предок "
                     f"origin/{base}: {'да' if by_merge else 'нет'}")
    commits, found, closing = _commits_sign(repo, base_sha, fork, head)
    lines.append(f"  (б) коммитов задачи в origin/{base} по содержимому: "
                 f"{len(found)} из {len(commits)}"
                 + (f"; найден в базе {closing}" if closing else ""))
    by_diff, diff_lines = _diff_sign(repo, base_sha, fork, head)
    lines += diff_lines
    if by_merge:
        return Sync(MERGED_THIS, by=BY_MERGE, proof_sha=merge_commit,
                    changed_after=not by_diff, lines=lines)
    if commits and len(found) == len(commits) and closing:
        return Sync(OTHER_WAY, by=BY_COMMITS, proof_sha=closing, lines=lines)
    if by_diff:
        return Sync(OTHER_WAY, by=BY_DIFF, proof_sha=base_sha, lines=lines)
    if found:
        return Sync(PARTIAL, lines=lines)
    return Sync(ABSENT, lines=lines)


def _escalate(conn, task_id: str, detail: str) -> None:
    store.update_task(conn, task_id, escalated_from=fsm.AWAITING_HUMAN)
    store.set_state(conn, task_id, "escalated", "fsm",
                    expected_state=fsm.AWAITING_HUMAN, detail=detail)


def sync_task(conn, task_id: str, actor: str = "operator") -> Sync:
    """Сверка задачи в `awaiting_human`: вывод, запись журнала, последний
    итог и время сверки в строке задачи; инцидент «чужой коммит» —
    эскалация."""
    result = evaluate(conn, task_id)
    print(f"[{task_id}] mr-sync: {result.text()}")
    for line in result.lines:
        print(line)
    if result.proof_sha:
        print(f"  доказательство: {result.proof_sha}"
              + (f" ({BY_CONTENT})" if result.by == BY_DIFF else ""))
    detail = "; ".join([f"итог: {result.text()}",
                        *(line.strip() for line in result.lines),
                        *([f"доказательство {result.proof_sha}"]
                          if result.proof_sha else [])])
    store.journal(conn, task_id, actor, SYNC_ACTION, detail)
    previous = store.get_task(conn, task_id)["mr_sync_outcome"]
    store.update_task(conn, task_id, mr_sync_outcome=result.text(),
                      mr_sync_at=store.now())
    if previous and previous != result.text():
        store.journal(conn, task_id, actor, OUTCOME_CHANGED_ACTION,
                      f"{previous} → {result.text()}")
    if result.incident:
        _escalate(conn, task_id, result.incident)
    return result


# --------------------------------------------------------------- отбор


def _project_people(target: str) -> bool:
    try:
        return targets.merged_by_project_people(targets.target(target))
    except targets.TargetsError:
        return False


def _refusal(conn, task_id: str) -> str:
    """Причина отказа сверки названной задачи; "" — сверять можно."""
    row = store.get_task(conn, task_id) if store.task_exists(conn, task_id) \
        else None
    if row is None:
        return f"[{task_id}] mr-sync отклонён: задачи нет в БД"
    if row["state"] != fsm.AWAITING_HUMAN:
        return (f"[{task_id}] mr-sync отклонён: задача в {row['state']}, "
                f"сверка — только в {fsm.AWAITING_HUMAN}")
    if not _project_people(row["target"]):
        return (f"[{task_id}] mr-sync отклонён: проект {row['target']} — "
                f"merge_gate не target-human")
    return ""


def _resolve(conn, task_id: str) -> str:
    try:
        return store.resolve_task_id(conn, task_id)
    except SystemExit:
        return task_id


def awaiting_tasks(conn) -> list:
    """Задачи проектов `target-human` в `awaiting_human`."""
    return [r["id"] for r in store.all_tasks(conn)
            if r["state"] == fsm.AWAITING_HUMAN and _project_people(r["target"])]


# --------------------------------------------------------------- закрытие


def _confirm(conn, task_id: str, by_content: bool) -> None:
    result = sync_task(conn, task_id)
    if result.incident:
        sys.exit(f"[{task_id}] mr-sync --confirm отклонён: {result.incident}; "
                 f"задача эскалирована")
    if result.outcome not in CLOSING_OUTCOMES:
        _refuse_confirm(conn, task_id, f"итог «{result.text()}» не закрывает "
                        f"задачу; {CONFIRM_HINT.format(id=task_id)}")
    if result.by == BY_DIFF and not by_content:
        _refuse_confirm(conn, task_id, f"итог «{result.text()}» — только по "
                        f"содержимому (признак (в)): закрытие — "
                        f"artel.py mr-sync {task_id} {CONFIRM_FLAG} "
                        f"{BY_CONTENT_FLAG}")
    refusal = artifact_branch.origin_sync_refusal(task_id)
    if refusal is not None:
        store.journal(conn, task_id, "operator", DOCS_UNSYNCED_ACTION, refusal)
        sys.exit(f"[{task_id}] ссылка документов не сверена с origin: "
                 f"{refusal}; повтори mr-sync {task_id} {CONFIRM_FLAG} после "
                 f"docs --fetch-all\n  задача осталась в {fsm.AWAITING_HUMAN}")
    _close(conn, task_id, result)


def _refuse_confirm(conn, task_id: str, detail: str) -> None:
    store.journal(conn, task_id, "operator", CONFIRM_REFUSED_ACTION, detail)
    sys.exit(f"[{task_id}] mr-sync --confirm отклонён: {detail}\n"
             f"  задача осталась в {fsm.AWAITING_HUMAN}")


def _close(conn, task_id: str, result: Sync) -> None:
    """`awaiting_human -> done` (требование 4): `closed_as`, lease, коммит
    закрытия с sha доказательства, рабочая копия и локальная ветка. Ветка
    на сервере и MR не трогаются."""
    from . import cleanup
    row = store.get_task(conn, task_id)
    closed_as = (store.CLOSED_AS_MERGED_UPSTREAM if result.by == BY_MERGE
                 else store.CLOSED_AS_MERGED_UPSTREAM_OTHER)
    store.set_state(conn, task_id, "done", "operator",
                    expected_state=fsm.AWAITING_HUMAN,
                    detail=f"mr-sync --confirm: {result.text()}, sha "
                           f"{result.proof_sha}")
    store.update_task(conn, task_id, closed_as=closed_as)
    lease.release_any(conn, task_id, "operator", "lease снят: задача done")
    note = (f"mr-sync --confirm — {result.text()}, признак ({result.by}), "
            f"closed_as {closed_as}")
    if result.by == BY_DIFF:
        note += f"; sha — голова base {BY_CONTENT}"
    cleanup._commit_closing(conn, task_id, merge_sha=result.proof_sha,
                            note=note)
    store.journal(conn, task_id, "orchestrator", "worktree убран",
                  workspace.remove(task_id))
    store.journal(conn, task_id, "orchestrator", "ветка убрана",
                  cleanup.drop_task_branch(row["branch"],
                                           workspace.task_repo(task_id)))
    print(f"[{task_id}] закрыта: done, closed_as {closed_as}; ветка задачи на "
          f"сервере и MR не тронуты")


# --------------------------------------------------------------- надзор


def interval_min(target: str) -> int | None:
    """`policy.mr_sync_interval_min` записи проекта; None — опрос выключен."""
    try:
        return targets.delivery_policy(targets.target(target))[
            "mr_sync_interval_min"]
    except targets.TargetsError:
        return None


def _stamp(text: str | None) -> datetime | None:
    try:
        return datetime.strptime(text or "", "%Y-%m-%d %H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        return None


def due(row, interval: int) -> bool:
    """Прошло ли с последней сверки задачи `interval` минут по часам пульта."""
    last, now = _stamp(row["mr_sync_at"]), _stamp(store.now())
    return last is None or now is None or (now - last).total_seconds() >= interval * 60


def supervised(conn, task_ids: list) -> None:
    """Опрос надзора эпика (требование 6): сверка без `--confirm` задач в
    `awaiting_human`, у проекта которых задан `policy.mr_sync_interval_min`
    и с прошлой сверки прошло не меньше этих минут. Закрытия нет никогда."""
    for task_id in task_ids:
        row = store.get_task(conn, task_id)
        if row is None or row["state"] != fsm.AWAITING_HUMAN:
            continue
        if not _project_people(row["target"]):
            continue
        interval = interval_min(row["target"])
        if interval is None or not due(row, interval):
            continue
        try:
            sync_task(conn, task_id, actor=store.EPIC_SUPERVISOR_ACTOR)
        except (Exception, SystemExit) as exc:  # noqa: BLE001 — надзор живёт дальше
            store.journal(conn, task_id, store.EPIC_SUPERVISOR_ACTOR,
                          SYNC_ACTION, f"сверка не выполнена: "
                                       f"{type(exc).__name__}: {exc}")


# --------------------------------------------------------------- команда


def cmd_mr_sync(rest: list) -> None:
    confirm = CONFIRM_FLAG in rest
    by_content = BY_CONTENT_FLAG in rest
    unknown = [a for a in rest if a.startswith("-")
               and a not in (CONFIRM_FLAG, BY_CONTENT_FLAG)]
    if unknown:
        sys.exit(f"mr-sync: неизвестный флаг {unknown[0]}; использование: {USAGE}")
    if by_content and not confirm:
        sys.exit(f"mr-sync: {BY_CONTENT_FLAG} — только с {CONFIRM_FLAG}; "
                 f"использование: {USAGE}")
    conn = store.db()
    ids = [_resolve(conn, a) for a in rest if not a.startswith("-")]
    if confirm:
        if len(ids) != 1:
            sys.exit(f"mr-sync {CONFIRM_FLAG}: ровно одна задача, названо "
                     f"{len(ids)}; ни одна не закрыта. Использование: {USAGE}")
        refusal = _refusal(conn, ids[0])
        if refusal:
            sys.exit(refusal)
        lease.run_task_command(ids[0], None,
                               lambda c, tid: _confirm(c, tid, by_content))
        return
    if not ids:
        ids = awaiting_tasks(conn)
        if not ids:
            print(f"mr-sync: задач в {fsm.AWAITING_HUMAN} проектов "
                  f"target-human нет")
            return
    refusals = []
    for task_id in ids:
        refusal = _refusal(conn, task_id)
        if refusal:
            print(refusal)
            refusals.append(task_id)
            continue
        sync_task(conn, task_id)
    if refusals:
        sys.exit(f"mr-sync: отказано по {', '.join(refusals)}")
