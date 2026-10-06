"""Контекст проекта: клон, база, защищённые пути проекта, признак артели.

Репозиторный контекст target'а: одно место, где живёт «куда клон, какой
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
Шаги, нужные только артели (гейт мержа: guard, RETRO), включаются
признаком проекта `is_artel(ctx)`, не сравнением пути с `config.ROOT`;
защищённые пути сверяются у любого проекта — по его перечню
(`protected_paths`).

Оставленные развилки «артель или нет» (SPEC 01M484RNV3QBDY3B0M16J916ZP,
требование 2) узнают пульт одной функцией `is_artel` этого модуля.

`None` — target не читается (неизвестное имя, сломанный targets.yaml):
молчаливый откат на главную копию был бы ОПАСНЕЕ обычной деградации —
вызывающий код обязан получить сигнал «конфигурация не читается».
"""
import sqlite3
from dataclasses import dataclass
from os import PathLike
from pathlib import Path

from . import config, gitcmd, targets


@dataclass(frozen=True)
class RepoContext:
    path: Path
    remote: str
    base: str
    target: str = ""
    # Поле `no_paths` записи внешнего проекта; у артели не читается
    # (`protected_paths`).
    no_paths: tuple = ()


# Адрес области проектов при рассогласованных путях пульта: каталога нет и
# быть не может, `git -C` туда отказывает сразу, не поднимаясь вверх.
NO_AREA = Path("/dev/null/artel-no-project-area")

# Пути пульта на момент загрузки пакета — боевые для этого процесса.
_LOADED_ROOT = config.ROOT
_LOADED_PROJECTS = config.PROJECTS


def projects_root() -> Path:
    """Корень областей проектов `config.PROJECTS`; `NO_AREA` — если корень
    пульта подменён, а область проектов осталась боевой. Это песочница,
    подменившая корень пульта, но не область проектов: клон и рабочие копии
    ушли бы в боевую `.artel/projects`, а ссылки документов — в её `origin`
    (инцидент 04.10.2026, задача 01M42PENCS26D0656X8FR7DFA7: 80 тестовых
    ссылок `refs/artifacts/*` в боевом origin). Обратная подмена (своя
    область проектов при настоящем корне) боевого клона не задевает."""
    if (config.PROJECTS == _LOADED_PROJECTS
            and config.ROOT != _LOADED_ROOT):
        return NO_AREA
    return config.PROJECTS


def clone_path(target_name: str) -> Path:
    """Клон проекта в его области: `.artel/projects/<имя>/repo` (ADR-0021
    п.1). Читается от `config.PROJECTS` в момент вызова — песочница,
    подменившая путь, видит свой клон."""
    return projects_root() / target_name / "repo"


def resolve(target_name: str) -> "RepoContext | None":
    """Контекст проекта `target_name`. Артель разрешается без чтения
    `targets.yaml` (`remote="origin"`, база `config.MAIN_BRANCH`): пульт
    обязан работать над собой и при сломанном файле, который сам чинится
    задачей артели (SPEC 01M484RNV3QBDY3B0M16J916ZP, строка 16)."""
    if is_artel(target_name):
        return RepoContext(path=clone_path(target_name), remote="origin",
                           base=config.MAIN_BRANCH, target=target_name)
    try:
        entry = targets.target(target_name)
    except targets.TargetsError:
        return None
    return RepoContext(path=clone_path(target_name), remote=entry["url"],
                       base=entry["base"], target=target_name,
                       no_paths=tuple(entry["no_paths"]))


def unresolved_reason(target_name: str) -> str:
    """Причина отказа проверки, которой нужен контекст проекта, а он не
    разрешён (`resolve` вернул `None`) — называет проект."""
    return (f"контекст проекта «{target_name}» не разрешён: записи проекта "
            f"нет в targets.yaml или файл не читается")


def protected_paths(ctx: RepoContext) -> tuple:
    """Перечень защищённых путей проекта контекста — один на все места
    сверки (ADR-0021 п.8; SPEC 01M45FK56DWMNBRKA1VWM12H19, требование 1),
    формула сверки — `config.is_protected_path(путь, перечень)`.

    Внешний проект — поле `no_paths` его записи `targets.yaml`. Артель —
    `config.PROTECTED_PATHS`, прочитанный в момент вызова: его
    `docs/invariants.md` называет единым источником защищённых путей, а
    поле `no_paths` записи `artel` — лишь его зеркало под сторожем, на
    результат оно не влияет. Контекст артели разрешается без чтения
    `targets.yaml`, поэтому защита путей пульта от этого файла не
    зависит."""
    if is_artel(ctx):
        return tuple(config.PROTECTED_PATHS)
    return tuple(ctx.no_paths)


PROFILE_PRESENT = "есть"
PROFILE_ABSENT = "нет"
PROFILE_UNREAD = "не прочитан"


@dataclass(frozen=True)
class ProfileAnswer:
    """Профиль тестов проекта из его записи `targets.yaml` (ADR-0021 пп.
    8-9; SPEC 01M45FJVGQT1K0P8HDEXZX6HS7, требование 2): `outcome` — один
    из трёх исходов, `values` — разобранные подполя (только при
    `PROFILE_PRESENT`), `reason` — почему не прочитан."""
    outcome: str
    values: dict | None = None
    reason: str = ""


def profile_of(target_name: str) -> ProfileAnswer:
    """Профиль тестов проекта `target_name` — у артели тоже из её записи
    `targets.yaml`, как у любого проекта. Три исхода: профиль есть, у
    записи нет поля, профиль не прочитан (файл или запись не годны —
    `targets.check` проверяет и само поле)."""
    try:
        entry = targets.target(target_name)
    except targets.TargetsError as exc:
        return ProfileAnswer(PROFILE_UNREAD, reason=str(exc))
    values = entry.get(targets.PROFILE_FIELD)
    if values is None:
        return ProfileAnswer(PROFILE_ABSENT)
    return ProfileAnswer(PROFILE_PRESENT, values=dict(values))


def is_artel(subject) -> bool:
    """Проект — артель (`config.DEFAULT_TARGET`): единственный признак, по
    которому оставленные развилки узнают пульт (SPEC
    01M484RNV3QBDY3B0M16J916ZP, требование 2; шаги гейта мержа, нужные
    только пульту, — SPEC 01M42PENCS26D0656X8FR7DFA7, требование 3).

    `subject` — контекст (`RepoContext`), имя проекта, строка задачи (её
    колонка `target`; пустая — артель, умолчание колонки) или путь клона
    (клон артели — `clone_path(config.DEFAULT_TARGET)`). `None` — не
    артель: неразрешённый контекст признаком пульта не считается."""
    if subject is None:
        return False
    if isinstance(subject, RepoContext):
        name = subject.target
    elif isinstance(subject, str):
        name = subject
    elif isinstance(subject, PathLike):
        return Path(subject) == clone_path(config.DEFAULT_TARGET)
    elif isinstance(subject, (dict, sqlite3.Row)):
        name = subject["target"] or config.DEFAULT_TARGET
    else:
        name = getattr(subject, "target", None)
    return name == config.DEFAULT_TARGET


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
