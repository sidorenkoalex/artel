"""Репозиторный контекст target'а: одно место, где живёт «куда клон, какой
форндж, какая базовая ветка» (SPEC 01M1R5B33CC7E6BZK085XV3ZCX, требование 1).

До этой задачи каждая из 13 точек реестра SPEC (git/gh-слой fsm.py,
ci.py, github_adapter.py, review.py, acceptance.py, doctor.py) решала
self/внешний-target развилку по-своему — большинство просто не решало
её вовсе и молча работало с `config.ROOT`, репозиторием ПУЛЬТА, для
ЛЮБОГО target. `resolve()` — единственный разумный шов.

С этапа 2 ADR-0021 (п.1, SPEC 01M42PENCS26D0656X8FR7DFA7, требования 1-3)
у ЛЮБОГО проекта, включая артель, путь контекста — клон области проекта
`.artel/projects/<имя>/repo` (`clone_path`): git главной копии пульта в
ходе задачи не меняется. Для артели `remote` — `"origin"`, базовая ветка —
`config.MAIN_BRANCH` без обращения к `targets.yaml`; для внешнего проекта
`remote` — адрес форджа (`targets.yaml[target]["url"]`, нужен вызовам
`gh --repo <url>`, НЕ имя локального git remote — клон несёт свой git
remote `origin`, поэтому git-уровневые команды (fetch/push) идут на
литеральное имя `"origin"`), базовая ветка — `targets.yaml[target]["base"]`.
Шаги, нужные только артели (гейт мержа: защищённые пути, guard, карта,
RETRO), включаются признаком проекта `is_artel(ctx)`, не сравнением пути
с `config.ROOT`.

`None` — target не читается (неизвестное имя, сломанный targets.yaml):
молчаливый откат на главную копию был бы ОПАСНЕЕ обычной деградации —
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
    target: str = ""


# Адрес области проектов при рассогласованных путях пульта: каталога нет и
# быть не может, `git -C` туда отказывает сразу, не поднимаясь вверх.
NO_AREA = Path("/dev/null/artel-no-project-area")


def projects_root() -> Path:
    """Корень областей проектов `config.PROJECTS` — если он лежит под
    `config.ROOT`; иначе `NO_AREA`. Рассогласование — песочница, подменившая
    корень пульта, но не область проектов: клон и рабочие копии ушли бы в
    боевую `.artel/projects`, а ссылки документов — в её `origin` (инцидент
    04.10.2026, задача 01M42PENCS26D0656X8FR7DFA7: 80 тестовых ссылок
    `refs/artifacts/*` в боевом origin)."""
    try:
        config.PROJECTS.resolve().relative_to(config.ROOT.resolve())
    except ValueError:
        return NO_AREA
    return config.PROJECTS


def clone_path(target_name: str) -> Path:
    """Клон проекта в его области: `.artel/projects/<имя>/repo` (ADR-0021
    п.1). Читается от `config.PROJECTS` в момент вызова — песочница,
    подменившая путь, видит свой клон."""
    return projects_root() / target_name / "repo"


def resolve(target_name: str) -> "RepoContext | None":
    if target_name == config.DEFAULT_TARGET:
        return RepoContext(path=clone_path(target_name), remote="origin",
                           base=config.MAIN_BRANCH, target=target_name)
    try:
        entry = targets.target(target_name)
    except targets.TargetsError:
        return None
    return RepoContext(path=clone_path(target_name), remote=entry["url"],
                       base=entry["base"], target=target_name)


def is_artel(ctx: "RepoContext | None") -> bool:
    """Проект контекста — артель (`config.DEFAULT_TARGET`): признак шагов
    гейта мержа, нужных только пульту (SPEC 01M42PENCS26D0656X8FR7DFA7,
    требование 3). Не путь: путь артели — клон, как у любого проекта."""
    return ctx is not None and ctx.target == config.DEFAULT_TARGET


def path_or_none(ctx: "RepoContext | None") -> Path | None:
    """Путь клона `ctx` — для любого разрешённого контекста, включая
    артель; `None` — только когда контекст не разрешён."""
    if ctx is None:
        return None
    return ctx.path


def git(ctx: "RepoContext", *args: str):
    """git-команда в клоне `ctx` (`gitcmd.in_repo`) — для любого проекта,
    включая артель."""
    return gitcmd.in_repo(ctx.path, *args)
