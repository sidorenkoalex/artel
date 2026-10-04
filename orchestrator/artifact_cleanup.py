"""Команда `artifact-branches-cleanup [--execute]`: уборка веток
`artifact/**` в `origin` артели и локальных `artifact/*` главной копии
(ADR-0021 п.13, этап 1; решение Оператора 02.10.2026; SPEC
01M41VTSE5N15P5P2WZF4GF2BQ, требование 6).

До ADR-0021 документы задачи жили в ветке `artifact/<id>`; теперь — в
ссылке `refs/artifacts/<id>`, и ветки остались хвостом. Без флага —
предпросмотр: перечень веток обеих сторон, ничего не удаляется. С
`--execute` — сначала сверка: у каждой задачи перечня (id из имени ветки)
есть `refs/artifacts/<id>` в `origin` (одним `ls-remote`); нехватка —
отказ, называющий задачи, и ни одна ветка не удалена. Сверка прошла —
ветки удаляются в `origin` (одним `push --delete`), затем локально.
Ссылки `refs/artifacts/*` не трогаются.

Процессу роли команда недоступна (её нет в `artel._ROLE_ALLOWED_COMMANDS`).
"""
import sys

from . import config, gitcmd, workspace

BRANCH_PREFIX = "artifact/"
_HEADS = "refs/heads/"
_ARTIFACT_REFS = "refs/artifacts/"


def _ls_remote(pattern: str, repo) -> tuple[list[str] | None, str]:
    """(имена ссылок `origin` под `pattern`, "") либо (None, причина).

    `repo` — клон артели (ADR-0021 п.13), в котором стоит `origin`."""
    res = gitcmd.in_repo(repo, "ls-remote", "origin", pattern)
    if res is None:
        return None, "git не ответил"
    if res.returncode != 0:
        return None, (res.stderr or "").strip()[:200] or "ls-remote не удался"
    refs = []
    for line in res.stdout.splitlines():
        _sha, _, ref = line.partition("\t")
        if ref.strip():
            refs.append(ref.strip())
    return refs, ""


def _task_key(branch: str) -> str:
    """id задачи из имени ветки `artifact/<id>[/...]` — в нижнем регистре:
    ветки названы id в нижнем регистре, ссылки — в исходном."""
    return branch[len(BRANCH_PREFIX):].split("/")[0].lower()


def _inventory() -> tuple[list[str], list[str], list[str]]:
    """(ветки `artifact/**` в origin, локальные ветки `artifact/*`, ключи
    задач перечня без `refs/artifacts/<id>` в origin). Не прочитано —
    отказ: уборка вслепую недопустима, предпросмотр вслепую бесполезен."""
    repo = workspace.repo(config.DEFAULT_TARGET)
    remote, reason = _ls_remote(f"{_HEADS}{BRANCH_PREFIX}*", repo)
    if remote is None:
        sys.exit(f"artifact-branches-cleanup: ветки origin не прочитаны — "
                 f"{reason}")
    origin_branches = sorted(r[len(_HEADS):] for r in remote
                             if r.startswith(_HEADS + BRANCH_PREFIX))
    local = gitcmd.list_branches(BRANCH_PREFIX, repo=repo)
    if local is None:
        sys.exit("artifact-branches-cleanup: локальные ветки не прочитаны — "
                 "git не ответил")
    local_branches = sorted(local)
    refs, reason = _ls_remote(f"{_ARTIFACT_REFS}*", repo)
    if refs is None:
        sys.exit(f"artifact-branches-cleanup: ссылки документов origin не "
                 f"прочитаны — {reason}")
    have = {r[len(_ARTIFACT_REFS):].lower() for r in refs
            if r.startswith(_ARTIFACT_REFS)}
    keys = sorted({_task_key(b) for b in origin_branches + local_branches})
    missing = [k for k in keys if k not in have]
    return origin_branches, local_branches, missing


def cmd_artifact_branches_cleanup(execute: bool) -> None:
    origin_branches, local_branches, missing = _inventory()
    print(f"ветки {BRANCH_PREFIX}** в origin: {len(origin_branches)}")
    for branch in origin_branches:
        print(f"  {branch}")
    print(f"локальные ветки {BRANCH_PREFIX}* главной копии: "
          f"{len(local_branches)}")
    for branch in local_branches:
        print(f"  {branch}")
    if missing:
        print(f"задачи без {_ARTIFACT_REFS}<id> в origin: {len(missing)}")
        for key in missing:
            print(f"  {key}")
    if not execute:
        print("предпросмотр: ничего не удалено; удалить — artel.py "
              "artifact-branches-cleanup --execute")
        return
    if missing:
        sys.exit(f"artifact-branches-cleanup --execute: отказ — у задач "
                 f"{', '.join(missing)} нет {_ARTIFACT_REFS}<id> в origin; "
                 f"ни одна ветка не удалена")
    repo = workspace.repo(config.DEFAULT_TARGET)
    if origin_branches:
        res = gitcmd.in_repo(repo, "push", "-q", "origin", "--delete",
                             *(_HEADS + b for b in origin_branches))
        if res is None or res.returncode != 0:
            stderr = (res.stderr or "").strip()[:300] if res is not None else ""
            sys.exit(f"artifact-branches-cleanup --execute: удаление веток "
                     f"в origin не удалось — {stderr or 'git не ответил'}; "
                     f"локальные ветки не тронуты")
    if local_branches:
        res = gitcmd.in_repo(repo, "branch", "-D", *local_branches)
        if res is None or res.returncode != 0:
            stderr = (res.stderr or "").strip()[:300] if res is not None else ""
            sys.exit(f"artifact-branches-cleanup --execute: ветки origin "
                     f"удалены ({len(origin_branches)}), локальные — не "
                     f"удалось: {stderr or 'git не ответил'}")
    print(f"удалено: в origin {len(origin_branches)}, локально "
          f"{len(local_branches)}; {_ARTIFACT_REFS}* не тронуты")
