"""Локальный кэш ретро-корпуса — расходный, пересобирается ЛОКАЛЬНО
(SPEC T094, требование 14; ANSWER-1, tasks/T094/ANSWER-1.md).

ANSWER-1 разводит объёмы буквального требования 14 («fetch'ем
`refs/artifacts/*`»): в M1 кэш пересобирается проходом по УЖЕ
СУЩЕСТВУЮЩИМ ЛОКАЛЬНЫМ `refs/artifacts/*` целевых (их локальные клоны —
`config.PROJECTS/<target>/workspace`, тот же адрес, что и `runner.
role_cwd`) — без сети. Сетевой `fetch` чужих refs из origin'ов целевых
как фоновая машинная обвязка — M2, вне объёма этой задачи.

`CACHE_PATH` — расходный файл под `.artel/`: `rebuild_cache()` полностью
восстанавливает его содержимое с нуля из локальных refs, поэтому его
удаление не теряет данных (AC-16), пока хотя бы один локальный клон
целевого несёт нужный `refs/artifacts/<id>`.
"""
import json

from . import config, gitcmd, targets, yamlmini

CACHE_PATH = config.ROOT / ".artel" / "retro-corpus-cache.json"

RETRO_FIELDS = ("operator", "model", "artel_sha")


def _target_workspace(target: str):
    return config.PROJECTS / target / "workspace"


def _local_artifact_refs(target: str) -> list[str]:
    """`refs/artifacts/*` ЛОКАЛЬНОГО клона `target`; пустой список — клона
    нет, git не ответил, или рефов нет вовсе."""
    workspace = _target_workspace(target)
    if not (workspace / ".git").exists():
        return []
    res = gitcmd.in_repo(workspace, "for-each-ref", "--format=%(refname)",
                         "refs/artifacts/")
    if res is None or res.returncode != 0:
        return []
    return [ref for ref in res.stdout.splitlines() if ref]


def _retro_entry(target: str, ref: str) -> dict | None:
    """Запись кэша из снапшота `ref` локального клона `target`; `None` —
    ни один файл снапшота не несёт frontmatter с тремя полями RETRO."""
    workspace = _target_workspace(target)
    task_id = ref.rsplit("/", 1)[-1]
    files = gitcmd.in_repo(workspace, "ls-tree", "-r", "--name-only", ref)
    if files is None or files.returncode != 0:
        return None
    for rel in files.stdout.splitlines():
        if not rel:
            continue
        show = gitcmd.in_repo(workspace, "show", f"{ref}:{rel}")
        if show is None or show.returncode != 0:
            continue
        meta = yamlmini.frontmatter(show.stdout)
        if meta and all(field in meta for field in RETRO_FIELDS):
            return {"task_id": task_id, "target": target,
                   **{field: meta[field] for field in RETRO_FIELDS}}
    return None


def rebuild_cache() -> list[dict]:
    """Пересобирает `CACHE_PATH` с нуля проходом по ЛОКАЛЬНЫМ
    `refs/artifacts/*` всех target'ов `targets.yaml` (AC-16). Сеть не
    участвует — только `git for-each-ref`/`git show` в уже существующих
    локальных клонах."""
    try:
        declared = targets.load()
    except targets.TargetsError:
        declared = {}
    rows = []
    for target in sorted(declared):
        for ref in _local_artifact_refs(target):
            entry = _retro_entry(target, ref)
            if entry is not None:
                rows.append(entry)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    return rows


def read_cache() -> list[dict]:
    """Содержимое кэша без пересборки; пустой список — файла ещё нет."""
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
