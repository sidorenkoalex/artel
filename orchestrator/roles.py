"""Карта исполнителей из roles.yaml: состав скилов роли читается кодом.

До T017 состав дублировался константой в config.py «синхронно
с roles.yaml» — то есть руками и на честном слове. Теперь источник один:
правка roles.yaml меняет промпт роли без правки кода (SPEC T017,
требование 1). Формат файла при этом не менялся.
"""
from . import config, yamlmini


class RolesError(Exception):
    """Состав роли взять неоткуда: файл, формат или сама роль."""


def load() -> dict:
    """Раздел `roles:` файла roles.yaml. RolesError — если его нет."""
    try:
        text = config.ROLES.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RolesError(f"{config.ROLES} не прочитан: {exc}") from exc
    try:
        data = yamlmini.mapping(text)
    except yamlmini.YamlError as exc:
        raise RolesError(f"{config.ROLES} не разобран: {exc}") from exc
    roles = data.get("roles")
    if not isinstance(roles, dict):
        raise RolesError(f"{config.ROLES}: нет раздела 'roles:'")
    return roles


def skills(role: str) -> list[str]:
    """Имена скилов роли по порядку из roles.yaml.

    Каждый отказ назван причиной: `cmd_run` печатает её Оператору вместо
    трейсбека, а починка (дописать роль, дописать skills) видна из текста.
    """
    entry = load().get(role)
    if not isinstance(entry, dict):
        raise RolesError(f"{config.ROLES}: роль '{role}' не описана")
    names = entry.get("skills")
    if names is None:
        raise RolesError(f"{config.ROLES}: у роли '{role}' не заданы skills")
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise RolesError(
            f"{config.ROLES}: skills роли '{role}' — не список имён")
    return names
