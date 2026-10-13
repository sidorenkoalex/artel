"""Декларация целевых проектов из targets.yaml: запись target'а читается кодом.

Подключение проекта декларативно (ADR-0003 п.2): forge, адрес, базовая
ветка, слот токена, запретные пути, курируемые проектные скилы
и исполнитель гейта мержа. Код спрашивает файл, а не константу рядом
с собой, — той же идиомой, что `roles.py` спрашивает roles.yaml.

Разбор — `yamlmini` (записи файла лежат в подмножестве YAML: вложенные
отображения по отступу, потоковые списки). Любой отказ назван причиной
и полем: Оператор чинит файл по тексту, а не по трейсбеку.

Проверяются все записи файла, а не только запрошенная: «невалидный
targets.yaml» — свойство файла, и узнать о сломанной записи лучше
на первом же чтении, чем на подключении того проекта через месяц.
"""
import re

from . import config, yamlmini

FORGES = ("github", "gitlab")
MERGE_GATES = ("operator", "target-human")

# Поля записи (ADR-0003 п.2) и их вид. "text" — непустая строка,
# "list" — список строк (возможно пустой).
FIELDS = {
    "forge": "text",          # github | gitlab — семейство API целевого
    "url": "text",            # адрес репозитория целевого
    "base": "text",           # базовая ветка: от неё ветки задач, в неё merge
    "token_slot": "text",     # имя слота в keychain (см. roles.yaml)
    "no_paths": "list",       # пути целевого, которые задачам трогать нельзя
    "project_skills": "list",  # курируемый список скилов (ADR-0003 3з)
    "merge_gate": "text",     # operator | target-human (ADR-0003 п.7)
}

# Профиль тестов проекта — необязательное поле записи (ADR-0021 пп. 8-9;
# SPEC 01M45FJVGQT1K0P8HDEXZX6HS7, требование 1). Вид подполя: "list" —
# непустой список строк, "list0" — список строк, возможно пустой, "dir" —
# относительный путь каталога, "template" — шаблон имени с `<id>` и
# `<name>`, "report" — одно из `PROFILE_REPORTS`, "positive_int" — целое > 0.
PROFILE_FIELD = "test_profile"
PROFILE_FIELDS = {
    "command": "list",               # начало команды прогона тестов
    "long_lived_dir": "dir",         # каталог долгоживущих тестов
    "long_lived_name": "template",   # шаблон имени долгоживущего файла
    "weakening_scope": "list",       # маски области гейта неослабления
    "mutation_claim_scope": "list",  # маски области заявки «Ловит мутацию»
    "report": "report",              # формат отчёта прогона
    "install": "list0",              # команда установки зависимостей
    "full_suite_timeout_sec": "positive_int",  # предел полного набора tests/
}
# `report` и `install` описываются и проверяются, но пультом не
# исполняются — их отсутствие поведения пульта не меняет.
PROFILE_OPTIONAL = ("report", "install", "full_suite_timeout_sec")
PROFILE_REPORTS = ("junit-xml",)

# Файл проектных карточек знаний — необязательное поле записи (SPEC
# 01M4S0JVB85W9TY1ESGNBH97FP, требование 6); читает его
# `knowledge_cards.read_cards`. Имя файла — один уровень каталога знаний.
KNOWLEDGE_FIELD = "knowledge"
KNOWLEDGE_FILE_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\.yaml")

# Настройка справочника ядра — необязательное поле записи (SPEC
# 01M4S24963R9H18AN2XDP6R15B, требование 3); читает её
# `reference_cache.get_reference` через `core_reference(name)`. Имена
# модулей и констант механизм не знает — всё берётся отсюда.
REFERENCE_FIELD = "core_reference"
REFERENCE_FIELDS = ("modules", "constants_module", "constants")


class TargetsError(Exception):
    """Декларацию target'а взять неоткуда: файл, формат или сама запись."""


def load() -> dict:
    """Все записи targets.yaml, проверенные. TargetsError — файл не годен.

    Порядок записей сохраняется: «первая запись — artel» видно и коду,
    и читателю файла.
    """
    try:
        text = config.TARGETS.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise TargetsError(f"{config.TARGETS} не прочитан: {exc}") from exc
    try:
        data = yamlmini.mapping(text)
    except yamlmini.YamlError as exc:
        raise TargetsError(f"{config.TARGETS} не разобран: {exc}") from exc
    entries = data.get("targets")
    if not isinstance(entries, dict):
        raise TargetsError(f"{config.TARGETS}: нет раздела 'targets:'")
    if not entries:
        raise TargetsError(f"{config.TARGETS}: раздел 'targets:' пуст")
    for name, entry in entries.items():
        check(name, entry)
    return entries


def target(name: str) -> dict:
    """Запись одного target'а. TargetsError — файл не годен или записи нет."""
    entries = load()
    entry = entries.get(name)
    if entry is None:
        raise TargetsError(
            f"{config.TARGETS}: target '{name}' не объявлен "
            f"(есть: {', '.join(entries)})")
    return entry


def core_reference(name: str) -> dict | None:
    """Поле `core_reference` записи проекта `name`; None — записи или поля
    нет. TargetsError — файл не годен, запись проекта или её поле неверны.

    В отличие от `target()` проверяется только запись `name`: сломанная
    чужая запись не отключает справочник этого проекта (требование 3)."""
    try:
        text = config.TARGETS.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise TargetsError(f"{config.TARGETS} не прочитан: {exc}") from exc
    try:
        data = yamlmini.mapping(text)
    except yamlmini.YamlError as exc:
        raise TargetsError(f"{config.TARGETS} не разобран: {exc}") from exc
    entries = data.get("targets")
    if not isinstance(entries, dict):
        raise TargetsError(f"{config.TARGETS}: нет раздела 'targets:'")
    if name not in entries:
        return None
    entry = entries[name]
    check(name, entry)
    value = entry.get(REFERENCE_FIELD)
    return dict(value) if value is not None else None


def check(name: str, entry: object) -> None:
    """Проверка одной записи. TargetsError называет поле, а не только файл."""
    where = f"{config.TARGETS}: target '{name}'"
    if not isinstance(entry, dict):
        raise TargetsError(f"{where} — не набор полей")
    for field, kind in FIELDS.items():
        if field not in entry:
            raise TargetsError(f"{where}: нет поля '{field}'")
        value = entry[field]
        if kind == "list":
            if not isinstance(value, list) or not all(
                    isinstance(item, str) for item in value):
                raise TargetsError(f"{where}: поле '{field}' — не список строк")
        elif not isinstance(value, str) or not value.strip():
            raise TargetsError(f"{where}: поле '{field}' пусто")
    if entry["forge"] not in FORGES:
        raise TargetsError(f"{where}: поле 'forge' — '{entry['forge']}', "
                           f"ожидается {' | '.join(FORGES)}")
    if entry["merge_gate"] not in MERGE_GATES:
        raise TargetsError(f"{where}: поле 'merge_gate' — "
                           f"'{entry['merge_gate']}', "
                           f"ожидается {' | '.join(MERGE_GATES)}")
    if PROFILE_FIELD in entry:
        _check_profile(where, entry[PROFILE_FIELD])
    if KNOWLEDGE_FIELD in entry:
        reason = _knowledge_error(name, entry[KNOWLEDGE_FIELD])
        if reason:
            raise TargetsError(f"{where}: поле '{KNOWLEDGE_FIELD}' — {reason}")
    if REFERENCE_FIELD in entry:
        _check_reference(where, entry[REFERENCE_FIELD])


def _check_reference(where: str, value: object) -> None:
    """Проверка поля `core_reference`: отказ называет проект, поле и
    подполе — тот же приём, что `_check_profile` (требование 3)."""
    field = f"{where}: поле '{REFERENCE_FIELD}'"
    if not isinstance(value, dict):
        raise TargetsError(f"{field} — не набор подполей")
    for sub in value:
        if sub not in REFERENCE_FIELDS:
            raise TargetsError(f"{field}: неизвестное подполе '{sub}' (известны: "
                               f"{', '.join(REFERENCE_FIELDS)})")
    modules = value.get("modules")
    if not isinstance(modules, list) or not modules:
        raise TargetsError(f"{field}: подполе 'modules' — не непустой список")
    for module in modules:
        reason = _reference_module_error(module)
        if reason:
            raise TargetsError(f"{field}: подполе 'modules' — {reason}")
    if len(set(modules)) != len(modules):
        raise TargetsError(f"{field}: подполе 'modules' — модуль повторён")
    has_module = "constants_module" in value
    has_constants = "constants" in value
    if has_module and not has_constants:
        raise TargetsError(f"{field}: подполе 'constants' обязательно при "
                           f"'constants_module'")
    if has_constants and not has_module:
        raise TargetsError(f"{field}: подполе 'constants' без "
                           f"'constants_module' не годно")
    if not has_module:
        return
    if value["constants_module"] not in modules:
        raise TargetsError(f"{field}: подполе 'constants_module' — "
                           f"'{value['constants_module']}' нет в 'modules'")
    constants = value["constants"]
    if not isinstance(constants, list) or not constants:
        raise TargetsError(f"{field}: подполе 'constants' — не непустой список")
    for name in constants:
        if not isinstance(name, str) or not name.isidentifier():
            raise TargetsError(f"{field}: подполе 'constants' — '{name}' не "
                               f"идентификатор Python")
    if len(set(constants)) != len(constants):
        raise TargetsError(f"{field}: подполе 'constants' — имя повторено")


def _reference_module_error(module: object) -> str:
    """Причина, по которой путь модуля настройки справочника не годен;
    пусто — годен."""
    if not isinstance(module, str):
        return f"'{module}' — не строка"
    if not module.endswith(".py"):
        return f"'{module}' — нет суффикса '.py'"
    if module.startswith("/") or "\\" in module:
        return f"'{module}' — не относительный путь с '/'"
    if any(part in ("", ".", "..") for part in module.split("/")):
        return f"'{module}' — пустой сегмент, '.' или '..'"
    return ""


def _knowledge_error(name: str, value: object) -> str:
    """Причина, по которой путь файла проектных карточек не годен; пусто —
    годен. Форма точная: у артели — `knowledge/<имя>.yaml` (не системный
    файл), у внешнего проекта — каталог знаний ЭТОГО проекта в области
    пульта: не клон `repo/` (репозиторий целевого недоверенный), не кэш
    `derived/`, не каталог другого проекта."""
    if not isinstance(value, str):
        return "не строка"
    if ".." in value.split("/") or "//" in value or "\\" in value:
        return f"'{value}' — путь с '..', '//' или обратной косой чертой"
    if value.startswith("./"):
        return f"'{value}' — путь с префиксом './'"
    if not value.endswith(".yaml"):
        return f"'{value}' — нет суффикса '.yaml'"
    if name == config.DEFAULT_TARGET:
        expected = "knowledge/<имя>.yaml (не системный файл)"
        head, _, file_name = value.partition("/")
        ok = (head == "knowledge" and KNOWLEDGE_FILE_NAME.fullmatch(file_name)
              and value != config.KNOWLEDGE_CARD_SYSTEM_REL)
    else:
        expected = f".artel/projects/{name}/knowledge/<имя>.yaml"
        prefix = f".artel/projects/{name}/knowledge/"
        ok = (value.startswith(prefix)
              and KNOWLEDGE_FILE_NAME.fullmatch(value[len(prefix):]))
    return "" if ok else f"'{value}', ожидается ровно {expected}"


def _check_profile(where: str, profile: object) -> None:
    """Проверка поля `test_profile` записи: причина называет поле и
    подполе (требование 1)."""
    if not isinstance(profile, dict):
        raise TargetsError(f"{where}: поле '{PROFILE_FIELD}' — не набор "
                           f"подполей")
    for sub in profile:
        if sub not in PROFILE_FIELDS:
            raise TargetsError(f"{where}: поле '{PROFILE_FIELD}': неизвестное "
                               f"подполе '{sub}' (известны: "
                               f"{', '.join(PROFILE_FIELDS)})")
    for sub, kind in PROFILE_FIELDS.items():
        name = f"'{PROFILE_FIELD}.{sub}'"
        if sub not in profile:
            if sub in PROFILE_OPTIONAL:
                continue
            raise TargetsError(f"{where}: нет подполя {name}")
        reason = _profile_value_error(kind, profile[sub])
        if reason:
            raise TargetsError(f"{where}: подполе {name} — {reason}")


def _profile_value_error(kind: str, value: object) -> str:
    """Причина, по которой значение подполя профиля не годно; пусто —
    годно."""
    if kind == "positive_int":
        return "не положительное целое число секунд" if (
            type(value) is not int or value <= 0) else ""
    if kind in ("list", "list0"):
        if not isinstance(value, list) or not all(
                isinstance(item, str) and item for item in value):
            return "не список непустых строк"
        if kind == "list" and not value:
            return "пустой список"
        return ""
    if not isinstance(value, str) or not value.strip():
        return "не непустая строка"
    if kind == "dir":
        parts = value.split("/")
        if value.startswith("/") or ".." in parts or "" in parts:
            return (f"'{value}' — не относительный путь каталога (без "
                    f"ведущего '/', '..' и пустых сегментов)")
    elif kind == "template":
        missing = [mark for mark in ("<id>", "<name>") if mark not in value]
        if missing:
            return f"'{value}' — нет {' и '.join(missing)}"
        if "/" in value:
            return f"'{value}' — шаблон имени файла, не путь"
    elif kind == "report" and value not in PROFILE_REPORTS:
        return f"'{value}', ожидается {' | '.join(PROFILE_REPORTS)}"
    return ""
