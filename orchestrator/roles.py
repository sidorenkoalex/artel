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


def provider(role: str) -> str:
    """Имя провайдера исполнителя роли (поле `provider:` в roles.yaml).

    Поле не задано — `providers.DEFAULT_PROVIDER` (`claude`), в отличие
    от `model()`, где отсутствие поля отдаёт `None`: провайдер обязан
    быть у каждой роли, а сегодняшний `roles.yaml` поля не несёт вовсе
    (SPEC 01M2ZNTHSNFYSTF904P6SZTPYF, требование 3 — сам файл эта задача
    не меняет). Роль не описана либо значение не является непустой
    строкой — `RolesError`, тем же приёмом, что `skills()`/`model()`.

    Реестр импортируется лениво: `orchestrator/providers/` читается
    манифестом стека на пути импорта точки входа, и обычный импорт
    отсюда замкнул бы круг.
    """
    from .providers import DEFAULT_PROVIDER
    entry = load().get(role)
    if not isinstance(entry, dict):
        raise RolesError(f"{config.ROLES}: роль '{role}' не описана")
    value = entry.get("provider")
    if value is None:
        return DEFAULT_PROVIDER
    if not isinstance(value, str) or not value:
        raise RolesError(
            f"{config.ROLES}: provider роли '{role}' — не непустая строка")
    return value


def model_tier(role: str) -> str:
    """Ярус роли (поле `model_tier:` в roles.yaml) — одно из значений
    закрытого перечня `models.TIERS` (SPEC 01M3009Y9AGGY6ZCFA7H1HJ1TD,
    требование 5).

    Заменяет прежнее поле `model:` (SPEC 01M2DTT96FS25SHXP0HDTWARQH):
    какую модель запускает ярус, решает локальный слой пульта
    (`.artel/models.yaml`), а не карта исполнителей в git — иначе смена
    модели у одного пульта меняла бы её у всех клонов.

    В отличие от прежнего `model()`, отсутствие поля — ОТКАЗ, а не
    дефолт CLI (требование 5, принцип 5 docs/research/
    providers-codex-plan.md): шаг agent-роли без явной модели не
    стартует. Значение вне перечня — тоже отказ, названный перечнем:
    опечатка в ярусе иначе уехала бы в «ярус не назван в tiers:» и
    Оператор чинил бы не тот файл.

    Перечень читается ленивым импортом: `models` знает о ярусах как о
    части схемы локального слоя, а эта карта — только о поле роли.
    """
    from .models import TIERS
    entry = load().get(role)
    if not isinstance(entry, dict):
        raise RolesError(f"{config.ROLES}: роль '{role}' не описана")
    value = entry.get("model_tier")
    if value is None:
        raise RolesError(
            f"{config.ROLES}: у роли '{role}' не задан model_tier "
            f"(ярус из перечня {', '.join(TIERS)})")
    if value not in TIERS:
        raise RolesError(
            f"{config.ROLES}: model_tier роли '{role}' = {value!r} — не из "
            f"перечня {', '.join(TIERS)}")
    return value
