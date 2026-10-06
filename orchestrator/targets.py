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
# `<name>`, "report" — одно из `PROFILE_REPORTS`.
PROFILE_FIELD = "test_profile"
PROFILE_FIELDS = {
    "command": "list",               # начало команды прогона тестов
    "long_lived_dir": "dir",         # каталог долгоживущих тестов
    "long_lived_name": "template",   # шаблон имени долгоживущего файла
    "weakening_scope": "list",       # маски области гейта неослабления
    "mutation_claim_scope": "list",  # маски области заявки «Ловит мутацию»
    "report": "report",              # формат отчёта прогона
    "install": "list0",              # команда установки зависимостей
}
# `report` и `install` описываются и проверяются, но пультом не
# исполняются — их отсутствие поведения пульта не меняет.
PROFILE_OPTIONAL = ("report", "install")
PROFILE_REPORTS = ("junit-xml",)


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
