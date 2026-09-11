"""Репозиторный контекст target'а: одно место, где живёт «куда клон, какой
форндж, какая базовая ветка» (SPEC 01M1R5B33CC7E6BZK085XV3ZCX, требование 1).

До этой задачи каждая из 13 точек реестра SPEC (git/gh-слой fsm.py,
ci.py, github_adapter.py, review.py, acceptance.py, doctor.py) решала
self/внешний-target развилку по-своему — большинство просто не решало
её вовсе и молча работало с `config.ROOT`, репозиторием ПУЛЬТА, для
ЛЮБОГО target. `resolve()` — единственный разумный шов: self — путь
клона `config.ROOT`, remote (имя, используемое git-командами) —
`"origin"`, базовая ветка — `config.MAIN_BRANCH`, без обращения к
`targets.yaml` (self всегда так, `orchestrator/fsm.py::
_origin_main_source` уже несёт тот же принцип); любой другой target —
путь клона `.artel/projects/<target>/workspace` (тот же адрес, что уже
использует `orchestrator/snapshot.py`), `remote` — адрес форджа
(`targets.yaml[target]["url"]`, нужен вызовам `gh --repo <url>`, НЕ
имя локального git remote — клон внешнего target несёт свой git remote
`origin` по тому же соглашению, что и пульт, поэтому git-уровневые
команды (fetch/push) идут на литеральное имя `"origin"`, а не на это
поле), базовая ветка — `targets.yaml[target]["base"]`.

`None` — target не читается (неизвестное имя, сломанный targets.yaml):
молчаливый откат на self/`config.ROOT` был бы ОПАСНЕЕ обычной
деградации (`orchestrator/fsm.py::_origin_main_source`, тот же довод) —
вызывающий код обязан получить сигнал «конфигурация не читается».
"""
from dataclasses import dataclass
from pathlib import Path

from . import config, gitcmd, targets


@dataclass(frozen=True)
class RepoContext:
    path: Path
    remote: str
    base: str


def resolve(target_name: str) -> "RepoContext | None":
    if target_name == config.DEFAULT_TARGET:
        return RepoContext(path=config.ROOT, remote="origin",
                           base=config.MAIN_BRANCH)
    try:
        entry = targets.target(target_name)
    except targets.TargetsError:
        return None
    return RepoContext(path=config.PROJECTS / target_name / "workspace",
                       remote=entry["url"], base=entry["base"])


def path_or_none(ctx: "RepoContext | None") -> Path | None:
    """`None` — self (или контекст не резолвился): сигнал вызывающему коду
    «параметр `repo=` можно не подставлять, поведение прежнее» — тот же
    вырожденный случай, которым уже пользуются `gitcmd.is_clean`/
    `commit_committer_dates`. Иначе — путь клона `ctx`."""
    if ctx is None or ctx.path == config.ROOT:
        return None
    return ctx.path


def git(ctx: "RepoContext", *args: str):
    """git-команда в клоне `ctx` — для self байт-в-байт `gitcmd.git`
    (без `-C`), иначе `gitcmd.in_repo(ctx.path, ...)`."""
    if ctx.path == config.ROOT:
        return gitcmd.git(*args)
    return gitcmd.in_repo(ctx.path, *args)
