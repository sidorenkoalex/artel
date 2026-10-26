"""Коммит закрытия задачи (`done`/`killed`) — последний коммит RETRO в
ссылку документов `refs/artifacts/<id>` пульта (ADR-0021 п.3); снимка
закрытия больше нет. Имя модуля историческое (ADR-0018 п.1).

Коммит закрытия записывается в журнал (`CLOSING_ACTION`) — с ним `doctor`
сверяет неизменность закрытой ссылки (`closing_sha`).

Исторический снимок (ADR-0021, этап 4; SPEC 01M4M68557TT4KYN814H8AZ01A) —
ссылка документов задачи, у которой есть каталог `tasks/<id>/` в
`origin/main`, но ссылки не было: команда Оператора
`artifact-history-snapshots` пишет её из дерева main
(`cmd_artifact_history_snapshots`), журнал (`HISTORY_ACTION`) несёт коммит
снимка, `doctor` сверяет с ним голову так же, как закрытую ссылку
(`history_snapshots`).
"""
import os
import sys

from . import (alerts, artifact_branch, config, fixation, fsm_postmerge,
               gitcmd, retro, store)

SNAPSHOT_REF_TMPL = "refs/artifacts/{task_id}"
RETRO_REL_TMPL = "tasks/{task_id}/RETRO.md"


def _operator_identity() -> str:
    """Идентичность закрывающего Оператора для поля `operator` RETRO
    (значение AC-13 не диктует — берётся то же, что уже читает `runner.
    git_identity` для авторства шага роли: `git config user.name`,
    иначе — системный пользователь)."""
    res = gitcmd.git("config", "--get", "user.name")
    name = res.stdout.strip() if res is not None and res.returncode == 0 else ""
    return name or os.environ.get("USER") or os.environ.get("LOGNAME") or "unknown"


def _model_identifier() -> str:
    """Идентификатор модели для поля `model` RETRO — источник вне объёма
    этой задачи (SPEC «Не входит»: пошаговые метаданные RETRO); значение
    берётся из окружения, если задано Оператором/раннером, иначе
    `"unknown"` — поле обязано СУЩЕСТВОВАТЬ (AC-13), не гадать значение."""
    return os.environ.get("ARTEL_MODEL") or os.environ.get("ANTHROPIC_MODEL") or "unknown"


def _retro_with_frontmatter(conn, task_id: str, outcome: str,
                            merge_sha: str = "",
                            applied_appendices=None) -> str:
    """Ретроспектива коммита закрытия: `outcome` — ФАКТИЧЕСКИЙ исход
    задачи, не литерал (SPEC 01M3KE80RNBCY9G48E75Z14TA7, требования 1-4). У
    смерженной задачи это «Итог: done, sha …» и вечный адрес
    `refs/artifacts/<id>` (ADR-0005 п.4, ADR-0018 п.1). У ликвидированной —
    прежние «Итог: killed — причина: …» и прежняя строка адреса.

    С ADR-0021 п.4 это единственное RETRO задачи — в main оно больше не
    коммитится (SPEC 01M4M67SGNEYMN9F1C7XVX24XE, требование 3), поэтому
    несёт то, что раньше несло только `docs/retro/<id>.md`: `merge_sha` —
    коммит мержа задачи в main проекта (merge кодовой ветки плюс приложения
    PLAN, без карты), его передаёт тело гейта мержа; без него (прямой вызов
    узла закрытия) — прежний `gitcmd.head_sha()` пульта. `applied_appendices`
    — пути приложений PLAN, применённых этим мержем: строка с их перечнем
    (`fsm_postmerge._with_appendices_line`); без приложений текст прежний."""
    if outcome == "killed":
        body = retro.build_killed(conn, task_id)
    else:
        body = fsm_postmerge._with_appendices_line(
            retro.build_done(conn, task_id, merge_sha or gitcmd.head_sha(),
                             address=SNAPSHOT_REF_TMPL.format(task_id=task_id)),
            applied_appendices)
    header = (
        "---\n"
        f"operator: {_operator_identity()}\n"
        f"model: {_model_identifier()}\n"
        f"artel_sha: {gitcmd.head_sha()}\n"
        "---\n\n"
    )
    return header + body


# Действие журнала коммита закрытия: `doctor` ищет по нему sha, с которым
# сверяет голову закрытой ссылки.
CLOSING_ACTION = "коммит закрытия"
# Источник incident-алерта о незаписанном коммите закрытия (SPEC
# 01M4M67SGNEYMN9F1C7XVX24XE, требования 4-5): RETRO задачи живёт только в
# нём, и молча пропасть оно не вправе.
CLOSING_INCIDENT_SOURCE = "snapshot.closing"


def _closing_failed(conn, task_id: str, note: str) -> str:
    """Незаписанный коммит закрытия — incident-алерт с target проекта
    задачи (тем же адресом, что прочие инциденты задачи на мерже), не отказ
    перехода: задача уже закрыта, уборка идёт дальше."""
    alerts.raise_alert(conn, store.task_target(conn, task_id), "incident",
                       CLOSING_INCIDENT_SOURCE, note)
    return note


def commit_closing(conn, task_id: str, outcome: str, merge_sha: str = "",
                   applied_appendices=None) -> str:
    """Коммит `tasks/<id>/RETRO.md` поверх головы ссылки документов;
    строка — что вышло. `outcome` — фактическое состояние закрытой задачи
    из БД (`done`/`killed`): его называют и ретроспектива, и сообщение
    коммита. `merge_sha`/`applied_appendices` — см. `_retro_with_frontmatter`.

    Ссылки локально нет (задача заведена до ADR-0021 и на новое
    устройство не переносилась, п.13) — коммит не пишется: первый коммит
    без родителя с одним RETRO.md выдал бы себя за историю документов.
    Записанный коммит фиксируется (`store.record_fixation`) — фиксация
    закрытой задачи указывает на коммит закрытия.

    Голова, разошедшаяся с фиксацией (`fixation.ref_drift`), коммита
    закрытия не получает: RETRO поверх подмены узаконил бы её; голова
    остаётся как есть для разбора.

    Любой незаписанный коммит — ссылки нет, расхождение с фиксацией, git
    не ответил, построение RETRO бросило исключение — кроме записи журнала
    поднимает incident-алерт (`_closing_failed`, SPEC
    01M4M67SGNEYMN9F1C7XVX24XE, требование 4) и исключения наружу не
    выпускает: переход и уборка задачи от него не зависят."""
    ref = artifact_branch.branch_name(task_id)
    if not artifact_branch.ref_head(task_id):
        note = f"коммит закрытия {task_id} не записан: {ref} нет локально"
        store.journal(conn, task_id, "orchestrator",
                      "коммит закрытия не записан", note)
        return _closing_failed(conn, task_id, note)
    drift = fixation.ref_drift(conn, task_id)
    if drift is not None:
        what = f"коммит закрытия {task_id} ({outcome}) не записан"
        fixation.journal_drift(conn, task_id, drift, "orchestrator", what)
        return _closing_failed(conn, task_id, f"{what}: {drift.text()}")
    try:
        text = _retro_with_frontmatter(conn, task_id, outcome, merge_sha,
                                       applied_appendices)
    except Exception as exc:  # noqa: BLE001 — см. докстринг: сбой не отменяет закрытие
        note = (f"коммит закрытия {task_id} не записан: RETRO не построено: "
                f"{exc}")
        store.journal(conn, task_id, "orchestrator",
                      "коммит закрытия не записан", note)
        return _closing_failed(conn, task_id, note)
    sha = artifact_branch.commit_files(
        task_id, {RETRO_REL_TMPL.format(task_id=task_id): text},
        f"{task_id}: закрытие ({outcome}) — RETRO")
    if not sha:
        note = f"коммит закрытия {task_id} не записан: git не ответил"
        store.journal(conn, task_id, "orchestrator",
                      "коммит закрытия не записан", note)
        return _closing_failed(conn, task_id, note)
    # Коммит закрытия — в origin до уборки, ожидания CI main и пересборки
    # справочника, вместе с недосланной строкой паспорта (ADR-0021 п.3).
    artifact_branch.send_pending(task_id)
    store.journal(conn, task_id, "orchestrator", CLOSING_ACTION,
                  f"{ref} <- {sha} ({outcome})")
    store.record_fixation(conn, task_id)
    return f"коммит закрытия {task_id}: {ref} <- {sha}"


def closing_sha(conn, task_id: str) -> str:
    """sha последнего записанного коммита закрытия задачи; пустая строка —
    записи нет (задача не закрыта или закрыта до ADR-0021: исторический
    снимок записи о коммите закрытия не несёт)."""
    for row in reversed(store.task_steps(conn, task_id)):
        if row["action"] == CLOSING_ACTION:
            return _recorded_sha(row["detail"])
    return ""


def _recorded_sha(detail: str | None) -> str:
    """sha из детали записи вида `<ссылка> <- <sha> (…)`."""
    _, _, rest = (detail or "").partition(" <- ")
    return rest.split(" ", 1)[0]


# --- исторические снимки (ADR-0021, этап 4) ---------------------------------

# Действие журнала исторического снимка: `doctor` ищет по нему коммит, с
# которым сверяет голову ссылки, — как `CLOSING_ACTION` у закрытой задачи.
HISTORY_ACTION = "исторический снимок"
HISTORY_COMMAND = "artifact-history-snapshots"
# Приватное пространство подтягивания ссылок из origin на время команды:
# в `refs/artifacts/*` напрямую fetch не пишет — существующие ссылки
# команда не меняет ни при каких условиях.
_HISTORY_FETCH_NS = "refs/artel/history-snapshots"
_TASKS_DIR = "tasks"


def history_snapshots(conn) -> dict:
    """{id задачи: коммит снимка} — по последней записи `HISTORY_ACTION`
    каждой задачи. Строка `tasks` не нужна: у задачи T-серии её нет, а
    запись журнала есть (у `steps` нет внешнего ключа). Target снимка —
    всегда артель (`config.DEFAULT_TARGET`): команда пишет снимки только
    из `origin/main` клона артели."""
    found = {}
    for row in store.steps_of_action(conn, HISTORY_ACTION):
        sha = _recorded_sha(row["detail"])
        if sha:
            found[row["task_id"]] = sha
    return found


def _out(res) -> str | None:
    """stdout удавшейся git-команды; `None` — git отказал или не ответил."""
    if res is None or res.returncode != 0:
        return None
    out = res.stdout
    return out.decode() if isinstance(out, bytes) else (out or "")


def _ls_tree(repo, *args: str) -> dict | None:
    """{путь: sha} строк `git ls-tree <args>`; `None` — git отказал."""
    out = _out(gitcmd.in_repo(repo, "ls-tree", *args))
    if out is None:
        return None
    entries = {}
    for line in out.splitlines():
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if path and len(parts) == 3:
            entries[path] = parts[2]
    return entries


def _last_change_ts(repo, rev: str, path: str) -> int:
    """Время (коммиттера) последнего коммита истории `rev`, менявшего
    `path`; 0 — не прочитано."""
    out = _out(gitcmd.in_repo(repo, "log", "-1", "--format=%ct", rev, "--",
                              path))
    try:
        return int((out or "").strip() or 0)
    except ValueError:
        return 0


def _newer_in_main(repo, task_id: str, origin_main: str,
                   head: str) -> list[str] | None:
    """Строки отчёта «путь, sha main, sha снимка» по файлам `tasks/<id>/`,
    которые в main новее, чем в снимке `head`: блоб другой (или файла в
    снимке нет), а последний коммит main, менявший путь, позже последнего
    коммита снимка, менявшего его. `None` — деревья не прочитаны."""
    prefix = f"{_TASKS_DIR}/{task_id}/"
    main_files = _ls_tree(repo, "-r", origin_main, prefix)
    snap_files = _ls_tree(repo, "-r", head, prefix)
    if main_files is None or snap_files is None:
        return None
    lines = []
    for path, blob in sorted(main_files.items()):
        snap_blob = snap_files.get(path)
        if snap_blob == blob:
            continue
        if snap_blob is not None and (
                _last_change_ts(repo, origin_main, path)
                <= _last_change_ts(repo, head, path)):
            continue
        lines.append(f"  {path}  main {blob}  снимок {snap_blob or 'нет'} "
                     f"(коммит снимка {head})")
    return lines


def _mktree(repo, entry: str) -> str:
    res = gitcmd.carpentry(repo, ["mktree"], dict(os.environ),
                           input=entry.encode("utf-8"), text=False)
    return (_out(res) or "").strip()


def _history_commit(repo, task_id: str, dir_tree: str,
                    origin_main: str) -> str:
    """Коммит без родителя, дерево которого — только `tasks/<id>/`, тот же
    объект дерева, что в `origin/main` (как есть, без перечитывания
    файлов). Пустая строка — git не ответил."""
    inner = _mktree(repo, f"040000 tree {dir_tree}\t{task_id}\n")
    root = _mktree(repo, f"040000 tree {inner}\t{_TASKS_DIR}\n") if inner else ""
    if not root:
        return ""
    env = {**os.environ,
           "GIT_AUTHOR_NAME": fixation.FIXATION_AUTHOR_NAME,
           "GIT_AUTHOR_EMAIL": fixation.FIXATION_AUTHOR_EMAIL,
           "GIT_COMMITTER_NAME": fixation.FIXATION_AUTHOR_NAME,
           "GIT_COMMITTER_EMAIL": fixation.FIXATION_AUTHOR_EMAIL}
    message = (f"{task_id}: {HISTORY_ACTION} tasks/{task_id}/ из origin/main "
               f"{origin_main}\n\nДерево — каталог задачи из origin/main "
               f"{origin_main} как есть (ADR-0021, этап 4; команда "
               f"{HISTORY_COMMAND}).\n")
    res = gitcmd.carpentry(repo, ["commit-tree", root, "-m", message], env)
    return (_out(res) or "").strip()


def _create_history_ref(conn, repo, task_id: str, dir_tree: str,
                        origin_main: str) -> tuple[bool, str]:
    """(создана, строка вывода) — один исторический снимок.

    Сначала push коммита в `origin` без force (ссылки там нет — origin
    заводит её; появилась тем временем — отклоняет), затем локальная
    ссылка со сверкой «её не было», затем запись журнала: запись обещает
    `doctor`'у ссылку в origin, поэтому пишется только после удачного
    push. Отказ push — ни ссылки, ни записи."""
    ref = artifact_branch.branch_name(task_id)
    sha = _history_commit(repo, task_id, dir_tree, origin_main)
    if not sha:
        return False, f"  {ref}: не создана — коммит снимка не записан"
    push = gitcmd.in_repo(repo, "push", "-q", "origin", f"{sha}:{ref}")
    if _out(push) is None:
        reason = ((push.stderr or "").strip()[:200] if push is not None
                  else "git не ответил")
        return False, f"  {ref}: не создана — push в origin отклонён: {reason}"
    line = f"  {ref} <- {sha}"
    upd = gitcmd.in_repo(repo, "update-ref", ref, sha, "0" * 40)
    if _out(upd) is None:
        line += (" (в origin; локальная ссылка не записана — подтянуть: "
                 "artel.py docs --fetch-all)")
    store.journal(conn, task_id, "operator", HISTORY_ACTION,
                  f"{ref} <- {sha} (origin/main {origin_main})",
                  target=config.DEFAULT_TARGET)
    return True, line


def cmd_artifact_history_snapshots(dry_run: bool) -> None:
    """Команда Оператора `artifact-history-snapshots [--dry-run]`: ссылка
    `refs/artifacts/<id>` для каждого каталога `tasks/<id>/` текущего
    `origin/main` артели, у которого её нет ни локально, ни в origin.
    Существующие ссылки не меняются; файлы, где main новее снимка, только
    перечисляются. `--dry-run` — перечень без записи ссылок и журнала.

    origin не ответил — отказ до любой записи: без перечня ссылок origin
    нельзя отличить задачу без ссылки от задачи, чья ссылка есть только
    там."""
    repo = artifact_branch.repo_for_target(config.DEFAULT_TARGET)
    if repo == artifact_branch._NO_REPO:
        sys.exit(f"{HISTORY_COMMAND}: {artifact_branch.NO_REPO_REASON}")
    ns = f"{_HISTORY_FETCH_NS}/{os.getpid()}"
    main_ref = f"refs/remotes/origin/{config.MAIN_BRANCH}"
    fetch = gitcmd.in_repo(repo, "fetch", "-q", "--no-tags", "origin",
                           f"+refs/heads/{config.MAIN_BRANCH}:{main_ref}",
                           f"+refs/artifacts/*:{ns}/*")
    fetched = artifact_branch._refs_with_prefix(repo, f"{ns}/") or {}
    try:
        if _out(fetch) is None:
            reason = ((fetch.stderr or "").strip()[:200] if fetch is not None
                      else "git не ответил")
            sys.exit(f"{HISTORY_COMMAND}: origin не ответил — ссылки не "
                     f"созданы: {reason}")
        _history_pass(repo, main_ref, ns, fetched, dry_run)
    finally:
        artifact_branch._drop_fetch_refs(repo, list(fetched))


def _history_pass(repo, main_ref: str, ns: str, fetched: dict,
                  dry_run: bool) -> None:
    origin_main = gitcmd.branch_head_sha(main_ref, repo=repo)
    dirs = _ls_tree(repo, "-d", origin_main, f"{_TASKS_DIR}/") if origin_main else None
    local = artifact_branch._refs_with_prefix(repo, "refs/artifacts/")
    if dirs is None or local is None:
        sys.exit(f"{HISTORY_COMMAND}: origin/main или локальные ссылки "
                 f"документов не прочитаны — ссылки не созданы")
    # Ссылка эпика `epic-<id>` — не задача (SPEC 01M5TBFCVFNN95BHH0E9C6KBKB,
    # требование 15): перечень задач строится по каталогам main.
    remote = {ref[len(ns) + 1:]: sha for ref, sha in fetched.items()
              if not artifact_branch.is_epic_ref_key(ref[len(ns) + 1:])}
    candidates, newer, unread = [], [], []
    for path, tree in sorted(dirs.items()):
        task_id = path[len(_TASKS_DIR) + 1:]
        head = (local.get(artifact_branch.branch_name(task_id))
                or remote.get(task_id))
        if not head:
            candidates.append((task_id, tree))
            continue
        lines = _newer_in_main(repo, task_id, origin_main, head)
        if lines is None:
            unread.append(task_id)
        else:
            newer += lines
    print(f"{HISTORY_COMMAND}: origin/main {origin_main}; каталогов задач "
          f"{len(dirs)}, со ссылкой {len(dirs) - len(candidates)}, без "
          f"ссылки {len(candidates)}")
    failed = 0
    if dry_run:
        print("пробный режим — ссылки и журнал не пишутся; были бы созданы:")
        for task_id, _tree in candidates:
            print(f"  {artifact_branch.branch_name(task_id)}")
    elif candidates:
        conn = store.db()
        print("исторические снимки:")
        for task_id, tree in candidates:
            ok, line = _create_history_ref(conn, repo, task_id, tree,
                                           origin_main)
            failed += not ok
            print(line)
    if newer:
        print("файлы, где main новее снимка (ссылки не менялись, решение — "
              "за Оператором):")
        for line in newer:
            print(line)
    if unread:
        print(f"снимки не сверены с main (git не прочитал дерево): "
              f"{', '.join(unread)}")
    if failed:
        sys.exit(f"{HISTORY_COMMAND}: не созданы {failed} из "
                 f"{len(candidates)} ссылок — см. строки выше")
