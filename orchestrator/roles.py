"""Карта исполнителей из roles.yaml: состав скилов роли читается кодом.

До T017 состав дублировался константой в config.py «синхронно
с roles.yaml» — то есть руками и на честном слове. Теперь источник один:
правка roles.yaml меняет промпт роли без правки кода (SPEC T017,
требование 1). Формат файла при этом не менялся.
"""
from . import config, yamlmini


class RolesError(Exception):
    """Состав роли взять неоткуда: файл, формат или сама роль."""


def _document() -> dict:
    """Весь roles.yaml разобранным отображением. RolesError — не читается."""
    try:
        text = config.ROLES.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RolesError(f"{config.ROLES} не прочитан: {exc}") from exc
    try:
        return yamlmini.mapping(text)
    except yamlmini.YamlError as exc:
        raise RolesError(f"{config.ROLES} не разобран: {exc}") from exc


def load() -> dict:
    """Раздел `roles:` файла roles.yaml. RolesError — если его нет."""
    roles = _document().get("roles")
    if not isinstance(roles, dict):
        raise RolesError(f"{config.ROLES}: нет раздела 'roles:'")
    return roles


def token_slots(role: str | None) -> list[str]:
    """Слоты keychain для токена роли: свой token_slot, затем общий fallback.

    Порядок и есть политика ADR-0001: слоты раздельные с первого дня,
    но пока в keychain лежит один общий 'artel-token', все роли падают
    в него; разделение PAT — заведение отдельных записей без правки кода.
    Роль без слота (token_slot: null) или неописанная роль просто
    не добавляет своего элемента — это не ошибка.
    """
    data = _document()
    slots: list[str] = []
    entry = data.get("roles", {}).get(role) if isinstance(
        data.get("roles"), dict) else None
    if isinstance(entry, dict) and isinstance(entry.get("token_slot"), str):
        slots.append(entry["token_slot"])
    fallback = data.get("token_fallback")
    if isinstance(fallback, str) and fallback not in slots:
        slots.append(fallback)
    return slots


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


def model(role: str) -> str | None:
    """Идентификатор модели роли (поле `model:` в roles.yaml).

    `None` — поле не задано вовсе: роль идёт на дефолт CLI (SPEC
    01M2DTT96FS25SHXP0HDTWARQH, требование 2), в отличие от `skills()`,
    где отсутствие поля — отказ. Поле присутствует, но не является
    непустой строкой (число, bool, пустая строка) — `RolesError`, тем же
    приёмом, что `skills()` на неверном формате.
    """
    entry = load().get(role)
    if not isinstance(entry, dict):
        raise RolesError(f"{config.ROLES}: роль '{role}' не описана")
    value = entry.get("model")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise RolesError(
            f"{config.ROLES}: model роли '{role}' — не непустая строка")
    return value
