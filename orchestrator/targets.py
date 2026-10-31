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
import posixpath
import re
import shlex
from pathlib import Path

from . import config, yamlmini

FORGES = ("github", "gitlab")
MERGE_GATES = ("operator", "target-human")
# Значения, которые пульт исполняет (ADR-0029 п. 8; SPEC
# 01M5W27CY7K7NR9347NKD8F0NX): запись принимает весь `FORGES`/`MERGE_GATES`,
# а задачу, отправку и мерж ведёт только этот список — расширение (адаптер
# GitLab, гейт людей проекта) — одна строка здесь.
SUPPORTED_FORGES = ("github",)
SUPPORTED_MERGE_GATES = ("operator",)

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
# `<name>`, "report" — одно из `PROFILE_REPORTS`, "positive_int" — целое > 0,
# "runner" — одно из `PROFILE_RUNNERS`, "mapping" — отображение строк без
# имён секретов (SPEC 01M52EEDEYV14658X8VFNHCW8K, требования 2-4),
# "identifiers" — список идентификаторов Python, возможно пустой.
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
    "runner": "runner",              # чей раннер гоняет тесты
    "workdir": "dir",                # каталог прогона от корня репозитория
    "env": "mapping",                # окружение прогона
    # Верхние имена импорта, разрешённые долгоживущим файлам сверх
    # стандартной библиотеки и пакетов пульта (SPEC
    # 01M5633WZ3Y3A0P4KKBZDB3KER): список идентификаторов, возможно пустой.
    "long_lived_imports": "identifiers",
}
# `report` и `install` описываются и проверяются, но пультом не
# исполняются — их отсутствие поведения пульта не меняет. Так же пока
# `runner`, `workdir`, `env`: потребители — следующие части D0.
PROFILE_OPTIONAL = ("report", "install", "full_suite_timeout_sec", "runner",
                    "workdir", "env", "long_lived_imports")
# Подполе, недопустимое у артели: её правило импортов — правило пульта.
PROFILE_EXTERNAL_ONLY = ("long_lived_imports",)
PROFILE_REPORTS = ("junit-xml",)
PROFILE_RUNNER_DEFAULT = "pult-pytest"
PROFILE_RUNNER_OWN = "pytest-own"
PROFILE_RUNNERS = (PROFILE_RUNNER_DEFAULT, PROFILE_RUNNER_OWN)
# Подполя, осмысленные только у собственного раннера проекта.
PROFILE_OWN_RUNNER_ONLY = ("workdir", "env")

# Компоненты проекта — необязательное поле записи вместо `test_profile`
# (ADR-0026 пп. 1-3; SPEC 01M58FNWBV25FF26E7AZ9Q9912, требования 1-3):
# отображение «имя компонента → поля». Виды полей сверх видов профиля:
# "command" — непустой список непустых строк (одна команда),
# "path_template" — шаблон пути от корня репозитория с `<id>` (и только
# `<id>`/`<dir>`/`<name>`), "layout" — шаблон пути с `<id>`, "repo" —
# непустая строка, "repo_paths" — список путей от корня репозитория,
# "masks" — маски `project_profile.mask_matches` без альтернатив `{a,b}`,
# "regexes" — регулярные выражения путей строкой или потоковым списком,
# "paths_source", "depends_on", "tools" — отображения своей формы.
COMPONENTS_FIELD = "components"
COMPONENT_FIELDS = dict(PROFILE_FIELDS, **{
    "report": "component_report",
    "install": "command",
    "checks_local": "command",
    "long_lived": "path_template",
    "plank_layout": "layout",
    "repo": "repo",
    "report_args": "list0",
    "select": "list0",
    "failure_errors": "list0",
    "layers": "list0",
    "knowledge": "repo_paths",
    "tests": "masks",
    "test_support": "masks",
    "paths": "regexes",
    "paths_source": "paths_source",
    "depends_on": "depends_on",
    "tools": "tools",
})
# `pult-vitest` только допустим: отчётчик появится в G1б.
COMPONENT_REPORTS = ("junit-xml", "pult-vitest")
COMPONENT_TEMPLATE_MARKS = ("<id>", "<dir>", "<name>")
COMPONENT_DEPENDS_VIA = ("paths", "files", "contract")
COMPONENT_PATHS_SOURCE = ("file", "key")
# Символы, которые потоковый список `yamlmini` не передаст выражению как
# есть (кавычки, запятая, скобки списка): громкий отказ вместо молчаливо
# другого выражения (ANSWER-1, п. 1).
COMPONENT_REGEX_FORBIDDEN = ('"', "'", ",", "[", "]")
# Причина отказа читателей профиля записи с несколькими компонентами до G1б.
MULTI_COMPONENT_PENDING = ("запись проекта с несколькими компонентами: "
                           "профиль выбирается по зонам задачи")
# Токены форжа — вне реестра провайдеров, но тоже секреты окружения.
FORGE_SECRET_ENV_NAMES = ("GITHUB_TOKEN", "GH_TOKEN")

# Файл проектных карточек знаний — необязательное поле записи (SPEC
# 01M4S0JVB85W9TY1ESGNBH97FP, требование 6); читает его
# `knowledge_cards.read_cards`. Имя файла — один уровень каталога знаний.
KNOWLEDGE_FIELD = "knowledge"
KNOWLEDGE_FILE_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\.yaml")

# Пути агентской обвязки проекта сверх стандартных маркеров — необязательное
# поле записи, «список строк», как `no_paths` (SPEC
# 01M5T19041XE2KB6A52F0AT0NF, требование 4); в локальном слое — раздел
# `policy`.
WRAPPER_FIELD = "agent_wrapper"
# Корневые файлы обвязки, которые элемент `knowledge` компонента называть
# может (ANSWER-2, ответ 1): их канал в бриф — задача
# 01M5T18K1YFBYA7MM1BBRV869A.
KNOWLEDGE_WRAPPER_ALLOWED = ("CLAUDE.md", "AGENTS.md")

# Настройка справочника ядра — необязательное поле записи (SPEC
# 01M4S24963R9H18AN2XDP6R15B, требование 3); читает её
# `reference_cache.get_reference` через `core_reference(name)`. Имена
# модулей и констант механизм не знает — всё берётся отсюда.
REFERENCE_FIELD = "core_reference"
REFERENCE_FIELDS = ("modules", "constants_module", "constants", "min_uses")
# Порог использования справочника — необязательное подполе (SPEC
# 01M4TVBT9ZCRQDY669QV3S95MA, требование 1); без него действует
# `config.CORE_REFERENCE_MIN_USES`.
REFERENCE_MIN_USES = "min_uses"
REFERENCE_MIN_USES_RANGE = (1, 1000)


class TargetsError(Exception):
    """Декларацию target'а взять неоткуда: файл, формат или сама запись."""


class ComponentsPending(TargetsError):
    """Запись проекта с несколькими компонентами — компонент задачи не
    выбран (`project_profile.for_task` отказал; SPEC
    01M5JGSAANR1NZYQD4FCSVE48Y, требование 2). Отдельный класс — чтобы
    перехват отказа не был шире него."""


def local_path() -> Path:
    """Файл локального слоя записей внешних проектов (SPEC
    01M5SCGSQN0AT0B07H7M9803RA, требование 1): от `config.TARGETS` в
    момент вызова — подмена `config.TARGETS` уводит и слой."""
    return config.TARGETS.parent / config.TARGETS_LOCAL_REL


def _read_section(path: Path, *, missing_ok: bool = False,
                  only_root: bool = False) -> dict | None:
    """Сырые записи раздела `targets:` файла `path` в порядке файла;
    None — файла нет и `missing_ok`. TargetsError — файл не годен (тексты
    одни на оба слоя)."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        if missing_ok:
            return None
        raise TargetsError(f"{path} не прочитан: {exc}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise TargetsError(f"{path} не прочитан: {exc}") from exc
    try:
        data = yamlmini.mapping(text)
    except yamlmini.YamlError as exc:
        raise TargetsError(f"{path} не разобран: {exc}") from exc
    entries = data.get("targets")
    if not isinstance(entries, dict):
        raise TargetsError(f"{path}: нет раздела 'targets:'")
    if only_root:
        # В локальном слое — только раздел записей (ANSWER-1, п. 7).
        extra = [key for key in data if key != "targets"]
        if extra:
            raise TargetsError(f"{path}: корневой ключ '{extra[0]}' — в "
                               f"локальном слое допустим только 'targets:'")
    return entries


def _repo_entries() -> dict:
    """Проверенные записи слоя репозитория прежнего плоского вида."""
    entries = _read_section(config.TARGETS)
    if not entries:
        raise TargetsError(f"{config.TARGETS}: раздел 'targets:' пуст")
    for name, entry in entries.items():
        check(name, entry)
    return entries


def _local_entries() -> dict | None:
    """Записи локального слоя, сведённые в прежний вид и проверенные;
    None — файла слоя нет."""
    path = local_path()
    entries = _read_section(path, missing_ok=True, only_root=True)
    if entries is None:
        return None
    if not entries:
        raise TargetsError(f"{path}: раздел 'targets:' пуст")
    return {name: merge_local(name, entry, path)
            for name, entry in entries.items()}


def layers() -> tuple[dict, dict | None]:
    """(записи слоя репозитория, записи локального слоя или None — файла
    нет), обе проверенные, в прежнем плоском виде, без производных пар
    `long_lived`. TargetsError — слой не годен."""
    return _repo_entries(), _local_entries()


def load() -> dict:
    """Все записи обоих слоёв, проверенные. TargetsError — слой не годен.

    Порядок записей сохраняется: «первая запись — artel» видно и коду,
    и читателю файла. Записи локального слоя (требование 5) перекрывают
    одноимённые записи репозитория на их месте, прочие идут следом в
    порядке файла слоя.
    """
    repo, local = layers()
    entries = dict(repo)
    entries.update(local or {})
    # Производная пара шаблона `long_lived` — только в отданной копии
    # (SPEC 01M5AA5TS90RDJ2AFXB882WTPD, требование 2): её читают
    # `repo_context.profile_of` и `project_profile` без смены своей логики.
    return {name: _with_long_lived_pairs(entry)
            for name, entry in entries.items()}


def target(name: str) -> dict:
    """Запись одного target'а. TargetsError — слой не годен или записи нет.

    Запись берётся из `load()` — единой точки чтения записей: подмена
    `load` в тесте или вызывающем видна и здесь (ANSWER-3, п. 3)."""
    entries = load()
    if name in entries:
        return entries[name]
    repo, local = layers()
    layer = (f"записи {', '.join(local)}" if local is not None
             else "файла нет")
    raise TargetsError(
        f"{config.TARGETS}: target '{name}' не объявлен "
        f"(есть: {', '.join(repo)}); локальный слой {local_path()}: "
        f"{layer} — записи внешних проектов лежат в локальном слое")


def unsupported_reason(name: str) -> str | None:
    """Причина, по которой пульт не ведёт задачи проекта `name`: значение
    `forge` или `merge_gate` записи вне исполняемых (`SUPPORTED_FORGES`,
    `SUPPORTED_MERGE_GATES`); None — проект поддержан.

    Отказ ставят действия, ведущие к задаче, отправке и мержу (`new`,
    `run`, `auto`, `approve`), а не загрузка записи: чтение, `doctor` и
    уборка такой записи безопасны (SPEC 01M5W27CY7K7NR9347NKD8F0NX,
    требование 2). Нечитаемый слой или необъявленный проект — тоже None:
    их отказ называет своя проверка (`target`, сверка проекта `new`), а
    не эта."""
    try:
        entry = target(name)
    except TargetsError:
        return None
    if entry["forge"] not in SUPPORTED_FORGES:
        return f"хостинг {entry['forge']} не поддержан: адаптера нет (ADR-0029)"
    if entry["merge_gate"] not in SUPPORTED_MERGE_GATES:
        return (f"гейт мержа {entry['merge_gate']} не исполняется "
                f"(ADR-0029)")
    return None


def core_reference(name: str) -> dict | None:
    """Поле `core_reference` записи проекта `name`; None — записи или поля
    нет. TargetsError — слой не годен, запись проекта или её поле неверны.

    В отличие от `target()` проверяется только запись `name`: сломанная
    чужая запись не отключает справочник этого проекта (требование 3).
    Артель — только слой репозитория; внешний проект — запись локального
    слоя, если она там есть (требование 5)."""
    if name != config.DEFAULT_TARGET:
        path = local_path()
        local = _read_section(path, missing_ok=True, only_root=True)
        if local and name in local:
            value = merge_local(name, local[name], path).get(REFERENCE_FIELD)
            return dict(value) if value is not None else None
    entries = _read_section(config.TARGETS)
    if name not in entries:
        return None
    entry = entries[name]
    check(name, entry)
    value = entry.get(REFERENCE_FIELD)
    return dict(value) if value is not None else None


# Политика внешних ссылок задач проекта (SPEC 01M5TBFH5VZ7GSRXX7VNKHFCCQ,
# требования 6, 9) — необязательные поля раздела `policy`:
# `ref_required` — система, ссылка которой обязательна задаче проекта;
# `ref_systems` — список допустимых систем ссылок.
REF_REQUIRED_FIELD = "ref_required"
REF_SYSTEMS_FIELD = "ref_systems"

# Формат записи локального слоя (требование 2): ровно три раздела.
# Значение — обязательна ли запись поля в разделе.
LOCAL_SECTIONS = ("description", "policy", "machine")
LOCAL_FIELDS = {
    "description": {"base": True, PROFILE_FIELD: False,
                    COMPONENTS_FIELD: False, KNOWLEDGE_FIELD: False,
                    REFERENCE_FIELD: False},
    "policy": {"no_paths": True, "project_skills": True, "merge_gate": True,
               "sandbox": False, WRAPPER_FIELD: False,
               "weakening_scope": False,
               "mutation_claim_scope": False, COMPONENTS_FIELD: False,
               REF_REQUIRED_FIELD: False, REF_SYSTEMS_FIELD: False,
               "branch_template": False, "ref_pattern": False,
               "freshness": False, "squash_before_mr": False,
               "commit_template": False, "co_author": False,
               "push_options": False, "push_options_forbidden": False,
               "ci_required_jobs": False, "mr_assignee": False,
               "draft_mr": False, "max_in_flight": False,
               "max_awaiting": False, "awaiting_holds_zones": False},
    "machine": {"forge": True, "url": True, "token_slot": True,
                "path": False, COMPONENTS_FIELD: False,
                "commit_author": False},
}

# Доставка через MR (SPEC 01M5WDB7F14SQ30QVWJY2XYBG2, требование 1; ADR-0029
# п. 4-6, 11, 13): поля только локального слоя. Значения по умолчанию в
# плоскую запись не подставляются — их берут читатели через `.get`.
DEFAULT_BRANCH_TEMPLATE = "task/{id}-{slug}"
BRANCH_PLACEHOLDERS = ("{id}", "{slug}", "{ref}")
DEFAULT_COMMIT_TEMPLATE = "{id}: {text}"
COMMIT_PLACEHOLDERS = ("{id}", "{ref}", "{text}")
FRESHNESS = ("merge", "rebase")
CO_AUTHOR_PREFIX = "Co-authored-by: "
PUSH_OPTION_CI_VARIABLE = "ci.variable="
PUSH_OPTION_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
DELIVERY_POLICY_FIELDS = (
    "branch_template", "ref_pattern", "freshness", "squash_before_mr",
    "commit_template", "co_author", "push_options", "push_options_forbidden",
    "ci_required_jobs", "mr_assignee", "draft_mr", "max_in_flight",
    "max_awaiting", "awaiting_holds_zones")
# Умолчания полей доставки, которые читает `delivery_policy` (SPEC
# 01M5XZ9Z68V75VXF5Z66C708T4, требование 2): отдаёт их только она.
DELIVERY_DEFAULTS = {"max_awaiting": 3, "awaiting_holds_zones": True,
                     "draft_mr": True, "max_in_flight": None,
                     "mr_assignee": None}
DELIVERY_MACHINE_FIELDS = ("commit_author",)
# Подполя профиля и компонента, которые живут в разделе `policy`.
LOCAL_POLICY_SCOPES = ("weakening_scope", "mutation_claim_scope")
LOCAL_MACHINE_COMPONENT_FIELDS = ("path",)
# Заполнитель каталога кэша проекта в значении `env` раздела `description`.
CACHE_MARK = "<cache>"


def cache_dir(name: str) -> str:
    """Каталог кэша проекта `name` в области пульта — значение `<cache>`."""
    return str(config.PROJECTS / name / "cache")


def _section_of(field: str) -> str | None:
    """Раздел, которому принадлежит поле верхнего уровня записи."""
    for section, fields in LOCAL_FIELDS.items():
        if field in fields and field != COMPONENTS_FIELD:
            return section
    return None


def _strings(value: object, prefix: str):
    """(поле, строка) всех строк значения на любой глубине."""
    if isinstance(value, str):
        yield prefix, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, f"{prefix}.{key}")
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item, prefix)


def _env_cache_value(value: str) -> bool:
    return value == CACHE_MARK or value.startswith(CACHE_MARK + "/")


def _description_envs(description: dict) -> list[tuple[str, dict]]:
    """(поле, env) профиля и компонентов раздела `description`."""
    found = []
    profile = description.get(PROFILE_FIELD)
    if isinstance(profile, dict) and isinstance(profile.get("env"), dict):
        found.append((f"description.{PROFILE_FIELD}.env", profile["env"]))
    comps = description.get(COMPONENTS_FIELD)
    if isinstance(comps, dict):
        for comp, fields in comps.items():
            if isinstance(fields, dict) and isinstance(fields.get("env"), dict):
                found.append((f"description.{COMPONENTS_FIELD}.{comp}.env",
                              fields["env"]))
    return found


def merge_local(name: str, entry: object, source: Path | None = None) -> dict:
    """Запись локального слоя в трёх разделах → проверенная запись прежнего
    плоского вида (требования 2-4). TargetsError называет файл слоя,
    запись, раздел и поле."""
    source = local_path() if source is None else source
    where = f"{source}: target '{name}'"
    if name == config.DEFAULT_TARGET:
        raise TargetsError(f"{where}: запись артели — только в targets.yaml "
                           f"репозитория")
    if not isinstance(entry, dict):
        raise TargetsError(f"{where} — не набор разделов "
                           f"{', '.join(LOCAL_SECTIONS)}")
    for key in entry:
        if key in LOCAL_SECTIONS:
            continue
        home = _section_of(key)
        if home is not None or key in (PROFILE_FIELD, COMPONENTS_FIELD):
            raise TargetsError(
                f"{where}: поле '{key}' вне раздела — плоская запись прежнего "
                f"вида не принимается, нужны разделы "
                f"{', '.join(LOCAL_SECTIONS)} (перенос: artel.py "
                f"targets-migrate {name})")
        raise TargetsError(f"{where}: неизвестный раздел '{key}' (известны: "
                           f"{', '.join(LOCAL_SECTIONS)})")
    for section in LOCAL_SECTIONS:
        if section not in entry:
            raise TargetsError(f"{where}: нет раздела '{section}'")
        if not isinstance(entry[section], dict):
            raise TargetsError(f"{where}: раздел '{section}' — не набор полей")
    description, policy, machine = (entry[s] for s in LOCAL_SECTIONS)
    _check_local_sections(where, description, policy, machine)
    _check_delivery(where, policy, machine)
    _check_local_values(name, where, entry)
    flat = _flatten(name, description, policy, machine)
    check(name, flat, source)
    return flat


def _check_local_sections(where: str, description: dict, policy: dict,
                          machine: dict) -> None:
    """Поля каждого раздела — на своём месте; компоненты `policy`/`machine`
    — из `description.components`."""
    for section, fields in (("description", description), ("policy", policy),
                            ("machine", machine)):
        known = LOCAL_FIELDS[section]
        for field in fields:
            if field in known:
                continue
            home = _section_of(field)
            if home is not None:
                raise TargetsError(f"{where}: раздел '{section}': поле "
                                   f"'{field}' не в своём разделе — его "
                                   f"раздел '{home}'")
            raise TargetsError(f"{where}: раздел '{section}': неизвестное "
                               f"поле '{field}' (известны: "
                               f"{', '.join(known)})")
        for field, required in known.items():
            if required and field not in fields:
                raise TargetsError(f"{where}: раздел '{section}': нет поля "
                                   f"'{field}'")
    has_profile = PROFILE_FIELD in description
    comps = description.get(COMPONENTS_FIELD)
    if has_profile == (comps is not None):
        raise TargetsError(f"{where}: раздел 'description': нужно ровно одно "
                           f"из полей '{PROFILE_FIELD}' и '{COMPONENTS_FIELD}'")
    if has_profile:
        profiles = [(f"description.{PROFILE_FIELD}", description[PROFILE_FIELD])]
    elif isinstance(comps, dict):
        profiles = [(f"description.{COMPONENTS_FIELD}.{comp}", fields)
                    for comp, fields in comps.items()]
    else:
        profiles = []
    for here, fields in profiles:
        if not isinstance(fields, dict):
            continue
        for sub in LOCAL_POLICY_SCOPES:
            if sub in fields:
                raise TargetsError(f"{where}: поле '{here}.{sub}' не в своём "
                                   f"разделе — его раздел 'policy'")
    for field, env in _description_envs(description):
        if "PATH" in env:
            raise TargetsError(f"{where}: поле '{field}.PATH' — PATH "
                               f"задаётся в разделе 'machine' (machine.path)")
    if "sandbox" in policy and not (isinstance(policy["sandbox"], str)
                                    and policy["sandbox"].strip()):
        raise TargetsError(f"{where}: поле 'policy.sandbox' — "
                           f"{policy['sandbox']!r}, не непустая строка")
    for sub in LOCAL_POLICY_SCOPES:
        if sub in policy and not has_profile:
            raise TargetsError(f"{where}: поле 'policy.{sub}' — только при "
                               f"'description.{PROFILE_FIELD}'; у компонентов "
                               f"— policy.{COMPONENTS_FIELD}.<имя>.{sub}")
    names = comps if isinstance(comps, dict) else {}
    for section, allowed in (("policy", LOCAL_POLICY_SCOPES),
                             ("machine", LOCAL_MACHINE_COMPONENT_FIELDS)):
        own = (policy if section == "policy" else machine).get(COMPONENTS_FIELD)
        if own is None:
            continue
        field = f"{section}.{COMPONENTS_FIELD}"
        if not isinstance(own, dict):
            raise TargetsError(f"{where}: поле '{field}' — не отображение "
                               f"«имя компонента → поля»")
        for comp, fields in own.items():
            if comp not in names:
                raise TargetsError(f"{where}: поле '{field}': компонента "
                                   f"'{comp}' нет в description.{COMPONENTS_FIELD}")
            if not isinstance(fields, dict):
                raise TargetsError(f"{where}: поле '{field}.{comp}' — не "
                                   f"набор полей")
            for sub in fields:
                if sub not in allowed:
                    raise TargetsError(f"{where}: поле '{field}.{comp}': "
                                       f"неизвестное поле '{sub}' (известны: "
                                       f"{', '.join(allowed)})")
    paths = [("machine.path", machine.get("path"))] if "path" in machine else []
    for comp, fields in (machine.get(COMPONENTS_FIELD) or {}).items():
        if "path" in fields:
            paths.append((f"machine.{COMPONENTS_FIELD}.{comp}.path",
                          fields["path"]))
    for field, value in paths:
        if not isinstance(value, str) or not value.strip():
            raise TargetsError(f"{where}: поле '{field}' — не непустая строка")


def push_whitelisted(entry: dict) -> bool:
    """Действует ли белый список отправок проекта с записью `entry`:
    `merge_gate` отличен от `operator` (ADR-0029 п. 13; SPEC
    01M5WDB7F14SQ30QVWJY2XYBG2, требование 3 (в)). Единственное место
    сравнения — `gitcmd` зовёт предикат, а не литерал."""
    return entry.get("merge_gate") != "operator"


def merged_by_project_people(entry: dict) -> bool:
    """Вливают ли MR проекта с записью `entry` люди проекта: `merge_gate`
    — `target-human` (ADR-0029 п. 1; SPEC 01M5XZ9Z68V75VXF5Z66C708T4,
    требование 4). Сравнение с литералом — только здесь."""
    return entry.get("merge_gate") == "target-human"


def delivery_policy(entry: dict) -> dict:
    """Поля доставки плоской записи `entry` с умолчаниями
    `DELIVERY_DEFAULTS` (SPEC 01M5XZ9Z68V75VXF5Z66C708T4, требования 2-3).
    `mr_assignee` целым или строкой цифр — id исполнителя (целое), иной
    строкой — имя как есть."""
    policy = {field: entry.get(field, default)
              for field, default in DELIVERY_DEFAULTS.items()}
    assignee = policy["mr_assignee"]
    if isinstance(assignee, str) and assignee.strip().isdigit():
        policy["mr_assignee"] = int(assignee.strip())
    return policy


def push_option_error(option: object, forbidden: list | tuple = ()) -> str | None:
    """Причина отказа опции отправки `option` — та же норма для элемента
    `policy.push_options` при загрузке и для `-o` в argv отправки; None —
    опция годна. Формы — `ci.variable=ИМЯ=значение` и `ИМЯ=значение`;
    `ci.skip` и любая `merge_request.*` запрещены всегда."""
    if not isinstance(option, str):
        return f"{option!r} — не строка"
    if option == "ci.skip" or option.startswith("ci.skip="):
        return f"{option!r}: ci.skip запрещён"
    if option.startswith("merge_request."):
        return (f"{option!r}: merge_request.* запрещены — создание и слияние "
                f"MR при отправке")
    body = option.removeprefix(PUSH_OPTION_CI_VARIABLE)
    var, sep, _value = body.partition("=")
    if not sep or not PUSH_OPTION_NAME.fullmatch(var):
        return (f"{option!r} — не вида ci.variable=ИМЯ=значение или "
                f"ИМЯ=значение")
    if var in forbidden:
        return f"{option!r}: имя {var} в policy.push_options_forbidden"
    return None


def _string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _check_delivery(where: str, policy: dict, machine: dict) -> None:
    """Поля доставки через MR (SPEC 01M5WDB7F14SQ30QVWJY2XYBG2, требование
    1): форма и связи между полями; отказ называет поле."""
    def refuse(field: str, text: str):
        section = "machine" if field in DELIVERY_MACHINE_FIELDS else "policy"
        raise TargetsError(f"{where}: поле '{section}.{field}' — {text}")

    template = policy.get("branch_template", DEFAULT_BRANCH_TEMPLATE)
    if "branch_template" in policy:
        if not isinstance(template, str) or not template.strip():
            refuse("branch_template", "не непустая строка")
        rest = template
        for mark in BRANCH_PLACEHOLDERS:
            rest = rest.replace(mark, "")
        if "{" in rest or "}" in rest:
            refuse("branch_template", f"{template!r}: подстановки — только "
                                      f"{', '.join(BRANCH_PLACEHOLDERS)}")
        if "{ref}" in template and REF_REQUIRED_FIELD not in policy:
            refuse("branch_template", f"{template!r}: {{ref}} без "
                                      f"policy.{REF_REQUIRED_FIELD}")
    if "ref_pattern" in policy:
        pattern = policy["ref_pattern"]
        if not isinstance(pattern, str) or not pattern:
            refuse("ref_pattern", "не непустая строка")
        try:
            re.compile(pattern)
        except re.error as exc:
            refuse("ref_pattern", f"{pattern!r} не компилируется: {exc}")
        if "{ref}" not in template:
            refuse("ref_pattern", "задан при branch_template без {ref}")
    squash = policy.get("squash_before_mr", False)
    if not isinstance(squash, bool):
        refuse("squash_before_mr", f"{squash!r}, не true/false")
    freshness = policy.get("freshness", FRESHNESS[0])
    if freshness not in FRESHNESS:
        refuse("freshness", f"{freshness!r}, ожидается {' | '.join(FRESHNESS)}")
    if freshness == "rebase" and not squash:
        refuse("freshness", "rebase только при squash_before_mr: true")
    if "commit_template" in policy:
        commit = policy["commit_template"]
        if not isinstance(commit, str) or not commit.strip():
            refuse("commit_template", "не непустая строка")
        rest = commit
        for mark in COMMIT_PLACEHOLDERS:
            rest = rest.replace(mark, "")
        if "{" in rest or "}" in rest:
            refuse("commit_template", f"{commit!r}: подстановки — только "
                                      f"{', '.join(COMMIT_PLACEHOLDERS)}")
        if commit != DEFAULT_COMMIT_TEMPLATE and not squash:
            refuse("commit_template", "отличный от умолчания — только при "
                                      "squash_before_mr: true")
    if "commit_author" in machine:
        author = machine["commit_author"]
        if not (isinstance(author, dict) and set(author) == {"name", "email"}
                and all(isinstance(v, str) and v.strip()
                        for v in author.values())):
            refuse("commit_author", "нужно {name, email} — обе непустые строки")
    if "co_author" in policy:
        co_author = policy["co_author"]
        if not (isinstance(co_author, str)
                and co_author.startswith(CO_AUTHOR_PREFIX)
                and co_author[len(CO_AUTHOR_PREFIX):].strip()):
            refuse("co_author", f"{co_author!r}: нужна строка, начинающаяся "
                                f"с {CO_AUTHOR_PREFIX!r}")
    forbidden = policy.get("push_options_forbidden", [])
    if not _string_list(forbidden):
        refuse("push_options_forbidden", "не список строк")
    options = policy.get("push_options", [])
    if not _string_list(options):
        refuse("push_options", "не список строк")
    for option in options:
        reason = push_option_error(option, forbidden)
        if reason is not None:
            refuse("push_options", reason)
    jobs = policy.get("ci_required_jobs", [])
    if not _string_list(jobs):
        refuse("ci_required_jobs", "не список строк")
    if "mr_assignee" in policy:
        assignee = policy["mr_assignee"]
        # Целое (не bool) — id исполнителя (SPEC 01M5XZ9Z68V75VXF5Z66C708T4,
        # требование 3); прочее — по-прежнему только непустая строка.
        if isinstance(assignee, bool) or not (
                isinstance(assignee, int)
                or (isinstance(assignee, str) and assignee.strip())):
            refuse("mr_assignee", "не непустая строка и не целое")
    if not isinstance(policy.get("draft_mr", True), bool):
        refuse("draft_mr", f"{policy['draft_mr']!r}, не true/false")
    if "max_in_flight" in policy:
        limit = policy["max_in_flight"]
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            refuse("max_in_flight", f"{limit!r}, не целое > 0")
    if "max_awaiting" in policy:
        limit = policy["max_awaiting"]
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            refuse("max_awaiting", f"{limit!r}, не целое > 0")
    if not isinstance(policy.get("awaiting_holds_zones", True), bool):
        refuse("awaiting_holds_zones",
               f"{policy['awaiting_holds_zones']!r}, не true/false")


def _check_local_values(name: str, where: str, entry: dict) -> None:
    """`<cache>` — только в начале значения `env` раздела `description`;
    абсолютных путей в `description` и `policy` нет (требования 3-4)."""
    envs = {field for field, _env in _description_envs(entry["description"])}
    for section in LOCAL_SECTIONS:
        for field, value in _strings(entry[section], section):
            if CACHE_MARK not in value:
                continue
            if not (field.rsplit(".", 1)[0] in envs
                    and _env_cache_value(value)):
                raise TargetsError(
                    f"{where}: поле '{field}' — {CACHE_MARK} допустим только "
                    f"в начале значения env раздела 'description'")
            if ".." in value[len(CACHE_MARK):].split("/"):
                raise TargetsError(f"{where}: поле '{field}' — путь после "
                                   f"{CACHE_MARK} выходит за каталог кэша")
    for section in ("description", "policy"):
        for field, value in _strings(entry[section], section):
            if value.startswith(("/", "~")):
                raise TargetsError(
                    f"{where}: абсолютный путь в записи {name}: {field} — "
                    f"каталог кэша задаётся `{CACHE_MARK}`, PATH — "
                    f"`machine.path`")
    machine = entry["machine"]
    description = entry["description"]
    profile = description.get(PROFILE_FIELD)
    if isinstance(profile, dict) and "path" in machine:
        runner = profile.get("runner", PROFILE_RUNNER_DEFAULT)
        if runner != PROFILE_RUNNER_OWN:
            raise TargetsError(
                f"{where}: поле 'machine.path' — PATH профиля допустим только "
                f"при 'runner: {PROFILE_RUNNER_OWN}' (runner — '{runner}')")
    comps = description.get(COMPONENTS_FIELD)
    if isinstance(comps, dict) and len(comps) == 1:
        comp, fields = next(iter(comps.items()))
        own = (machine.get(COMPONENTS_FIELD) or {}).get(comp) or {}
        field = (f"machine.{COMPONENTS_FIELD}.{comp}.path" if "path" in own
                 else "machine.path" if "path" in machine else None)
        runner = (fields.get("runner", PROFILE_RUNNER_DEFAULT)
                  if isinstance(fields, dict) else PROFILE_RUNNER_DEFAULT)
        if field and runner != PROFILE_RUNNER_OWN:
            raise TargetsError(
                f"{where}: поле '{field}' — PATH единственного компонента "
                f"допустим только при 'runner: {PROFILE_RUNNER_OWN}' (runner "
                f"— '{runner}')")


def _with_env(fields: dict, name: str, path: str | None) -> dict:
    """Копия профиля или компонента: `<cache>` в `env` подставлен, PATH
    раздела `machine` дописан. Не набор полей — как есть: отказ даст
    `check()`."""
    if not isinstance(fields, dict):
        return fields
    fields = dict(fields)
    env = fields.get("env")
    if isinstance(env, dict):
        env = {key: (cache_dir(name) + value[len(CACHE_MARK):]
                     if isinstance(value, str) and _env_cache_value(value)
                     else value)
               for key, value in env.items()}
    if path is not None:
        env = dict(env or {}, PATH=path)
    if env is not None:
        fields["env"] = env
    return fields


def _flatten(name: str, description: dict, policy: dict,
             machine: dict) -> dict:
    """Три раздела → запись прежнего вида (требование 3)."""
    flat = {field: machine[field] for field in ("forge", "url")}
    flat["base"] = description["base"]
    flat["token_slot"] = machine["token_slot"]
    for field in ("no_paths", "project_skills", "merge_gate", "sandbox",
                  WRAPPER_FIELD, REF_REQUIRED_FIELD, REF_SYSTEMS_FIELD,
                  *DELIVERY_POLICY_FIELDS):
        if field in policy:
            flat[field] = policy[field]
    for field in DELIVERY_MACHINE_FIELDS:
        if field in machine:
            flat[field] = machine[field]
    common = machine.get("path")
    if PROFILE_FIELD in description:
        profile = _with_env(description[PROFILE_FIELD], name, common)
        for sub in LOCAL_POLICY_SCOPES:
            if sub in policy and isinstance(profile, dict):
                profile[sub] = policy[sub]
        flat[PROFILE_FIELD] = profile
    comps = description.get(COMPONENTS_FIELD)
    if isinstance(comps, dict):
        scopes = policy.get(COMPONENTS_FIELD) or {}
        paths = machine.get(COMPONENTS_FIELD) or {}
        merged = {}
        for comp, fields in comps.items():
            path = (paths.get(comp) or {}).get("path", common)
            fields = _with_env(fields, name, path)
            if isinstance(fields, dict):
                fields.update(scopes.get(comp) or {})
            merged[comp] = fields
        flat[COMPONENTS_FIELD] = merged
    elif comps is not None:
        flat[COMPONENTS_FIELD] = comps
    for field in (KNOWLEDGE_FIELD, REFERENCE_FIELD):
        if field in description:
            flat[field] = description[field]
    return flat


def check(name: str, entry: object, source: Path | None = None) -> None:
    """Проверка одной записи. TargetsError называет поле, а не только файл.

    `source` — файл слоя, из которого пришла запись (требование 7); по
    умолчанию — `config.TARGETS`, текст прежний."""
    where = f"{config.TARGETS if source is None else source}: target '{name}'"
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
    if WRAPPER_FIELD in entry:
        value = entry[WRAPPER_FIELD]
        if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value):
            raise TargetsError(f"{where}: поле '{WRAPPER_FIELD}' — не список "
                               f"строк")
    if REF_REQUIRED_FIELD in entry:
        value = entry[REF_REQUIRED_FIELD]
        if not isinstance(value, str) or not value.strip():
            raise TargetsError(f"{where}: поле '{REF_REQUIRED_FIELD}' — "
                               f"{value!r}, не непустая строка")
    if REF_SYSTEMS_FIELD in entry:
        value = entry[REF_SYSTEMS_FIELD]
        if not isinstance(value, list) or not all(
                isinstance(item, str) and item.strip() for item in value):
            raise TargetsError(f"{where}: поле '{REF_SYSTEMS_FIELD}' — не "
                               f"список непустых строк")
    if entry["forge"] not in FORGES:
        raise TargetsError(f"{where}: поле 'forge' — '{entry['forge']}', "
                           f"ожидается {' | '.join(FORGES)}")
    if entry["merge_gate"] not in MERGE_GATES:
        raise TargetsError(f"{where}: поле 'merge_gate' — "
                           f"'{entry['merge_gate']}', "
                           f"ожидается {' | '.join(MERGE_GATES)}")
    if PROFILE_FIELD in entry:
        _check_profile(where, entry[PROFILE_FIELD])
        if name == config.DEFAULT_TARGET:
            for sub in PROFILE_EXTERNAL_ONLY:
                if sub in entry[PROFILE_FIELD]:
                    raise TargetsError(
                        f"{where}: подполе '{PROFILE_FIELD}.{sub}' — "
                        f"недопустимо у артели (правило импортов "
                        f"долгоживущих файлов пульта не расширяется)")
    if COMPONENTS_FIELD in entry:
        if PROFILE_FIELD in entry:
            raise TargetsError(f"{where}: поля '{PROFILE_FIELD}' и "
                               f"'{COMPONENTS_FIELD}' вместе недопустимы — "
                               f"оставь одно")
        _check_components(name, where, entry[COMPONENTS_FIELD])
        if name != config.DEFAULT_TARGET:
            _check_knowledge_outside_wrapper(where, entry)
    if KNOWLEDGE_FIELD in entry:
        reason = _knowledge_error(name, entry[KNOWLEDGE_FIELD])
        if reason:
            raise TargetsError(f"{where}: поле '{KNOWLEDGE_FIELD}' — {reason}")
    if REFERENCE_FIELD in entry:
        _check_reference(where, entry[REFERENCE_FIELD])


def wrapper_paths(agent_wrapper=()) -> tuple:
    """Действующий список обвязки внешнего проекта (SPEC
    01M5T19041XE2KB6A52F0AT0NF, требование 5): `config.AGENT_WRAPPER_MARKERS`,
    за ними элементы поля `agent_wrapper` записи в их порядке; строка, уже
    стоящая в списке, повторно не добавляется."""
    return tuple(dict.fromkeys((*config.AGENT_WRAPPER_MARKERS,
                                *agent_wrapper)))


def _check_knowledge_outside_wrapper(where: str, entry: dict) -> None:
    """Элемент `knowledge` компонента внешнего проекта не указывает в его
    обвязку (SPEC 01M5T19041XE2KB6A52F0AT0NF, требование 8): элемент,
    нормализованный так же, как его читает бриф (`posixpath.normpath`),
    совпадающий с путём действующего списка обвязки или лежащий внутри
    него, — отказ загрузки записи. Корневые `KNOWLEDGE_WRAPPER_ALLOWED` и
    элемент-каталог выше обвязки (`./`, `docs/`) загружаются."""
    wrapper = wrapper_paths(entry.get(WRAPPER_FIELD) or ())
    for comp, fields in entry[COMPONENTS_FIELD].items():
        for item in fields.get("knowledge") or ():
            rel = posixpath.normpath(item)
            if rel == "." or rel in KNOWLEDGE_WRAPPER_ALLOWED:
                continue
            hit = next((path for path in wrapper
                        if config.is_protected_path(rel, (path,))
                        or config.is_protected_zone(rel + "/", (path,))), None)
            if hit is not None:
                raise TargetsError(
                    f"{where}: компонент '{comp}': поле 'knowledge' — элемент "
                    f"'{item}' ({rel}) лежит в агентской обвязке проекта "
                    f"(путь обвязки '{hit}'): обвязка в бриф не передаётся")


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
    if REFERENCE_MIN_USES in value:
        low, high = REFERENCE_MIN_USES_RANGE
        threshold = value[REFERENCE_MIN_USES]
        # `type(...) is int`: булево — подкласс int, `true` не порог 1.
        if type(threshold) is not int or not low <= threshold <= high:
            raise TargetsError(f"{field}: подполе '{REFERENCE_MIN_USES}' — "
                               f"{threshold!r}, ожидается целое от {low} до {high}")
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
    runner = profile.get("runner", PROFILE_RUNNER_DEFAULT)
    if runner != PROFILE_RUNNER_OWN:
        for sub in PROFILE_OWN_RUNNER_ONLY:
            if sub in profile:
                raise TargetsError(
                    f"{where}: подполе '{PROFILE_FIELD}.{sub}' — допустимо "
                    f"только при 'runner: {PROFILE_RUNNER_OWN}' (runner — "
                    f"'{runner}')")


def _check_components(name: str, where: str, comps: object) -> None:
    """Проверка поля `components:` записи: отказ называет проект,
    компонент и поле (SPEC 01M58FNWBV25FF26E7AZ9Q9912, требования 2-3)."""
    if not isinstance(comps, dict) or not comps:
        raise TargetsError(f"{where}: поле '{COMPONENTS_FIELD}' — не непустое "
                           f"отображение «имя компонента → поля»")
    single = len(comps) == 1
    for comp, fields in comps.items():
        here = f"{where}: компонент '{comp}'"
        if ":" in comp:
            raise TargetsError(f"{here}: имя компонента с ':' — идентификатор "
                               f"теста компонента не разобрать")
        if not isinstance(fields, dict) or not fields:
            raise TargetsError(f"{here}: поля компонента — не непустое "
                               f"отображение")
        for field in fields:
            if field not in COMPONENT_FIELDS:
                raise TargetsError(f"{here}: неизвестное поле '{field}' "
                                   f"(известны: {', '.join(COMPONENT_FIELDS)})")
        for field, value in fields.items():
            reason = _component_value_error(COMPONENT_FIELDS[field], value,
                                            comp, comps)
            if reason:
                raise TargetsError(f"{here}: поле '{field}' — {reason}")
        _check_component_rules(name, here, fields, single)
        _check_rerun_ban(here, fields)


# Плагины повторов pytest и их аргументы (SPEC 01M5FRYVP4NF81VT00FYPHPWJH,
# требование 3; ADR-0026, «Решение» п. 4): итог компонента с `report`
# берётся из отчёта, а в junit-xml перезапуск не виден.
RERUN_FLAGS = ("--reruns", "--reruns-delay", "--force-flaky", "--max-runs")
RERUN_PLUGINS = ("rerunfailures", "pytest_rerunfailures", "flaky",
                 "flaky.flaky_pytest_plugin")


def _rerun_argument(args: list) -> str:
    """Первый запрещённый аргумент повторов в `args`; пусто — его нет."""
    for i, arg in enumerate(args):
        if any(arg == flag or arg.startswith(flag + "=") for flag in RERUN_FLAGS):
            return arg
        if arg == "-p" and i + 1 < len(args):
            if args[i + 1].strip() in RERUN_PLUGINS:
                return f"{arg} {args[i + 1]}"
        elif arg.startswith("-p") and arg[2:].strip() in RERUN_PLUGINS:
            return arg
    return ""


def _check_rerun_ban(here: str, fields: dict) -> None:
    """Отказ компоненту с `report` и командой pytest, которому заданы
    повторы: аргументы `command`/`report_args`/`select`, `PYTEST_ADDOPTS`
    и `PYTEST_PLUGINS`. Команда-обёртка (голова не pytest) — осознанная
    граница: что она запускает, пульт не разбирает."""
    if "report" not in fields or not _is_pytest_command(fields.get("command")):
        return
    env = fields.get("env") or {}
    sources = [(field, list(fields.get(field) or ()))
               for field in ("command", "report_args", "select")]
    if "PYTEST_ADDOPTS" in env:
        try:
            sources.append(("env.PYTEST_ADDOPTS",
                            shlex.split(env["PYTEST_ADDOPTS"])))
        except ValueError as exc:
            raise TargetsError(f"{here}: поле 'env' — PYTEST_ADDOPTS не "
                               f"разбирается ({exc})") from exc
    for field, args in sources:
        found = _rerun_argument(args)
        if found:
            raise TargetsError(
                f"{here}: поле '{field}' — {found!r}: повторы тестов внутри "
                f"прогона запрещены (в отчёте перезапуск не виден)")
    plugins = [part.strip() for part in env.get("PYTEST_PLUGINS", "").split(",")]
    found = [part for part in plugins if part in RERUN_PLUGINS]
    if found:
        raise TargetsError(
            f"{here}: поле 'env' — PYTEST_PLUGINS с {', '.join(found)}: "
            f"повторы тестов внутри прогона запрещены")


def _check_component_rules(name: str, here: str, fields: dict,
                           single: bool) -> None:
    """Правила компонента, зависящие от записи и соседних полей. Шаблон
    `long_lived`: форма → «шаблон или пара» → наличие (SPEC
    01M5AA5TS90RDJ2AFXB882WTPD, требование 1)."""
    # Слои (SPEC 01M5J0JYW3GZSSHHK3TYCYTQ3J, требование 1): разбор Python
    # годен только тестам pytest.
    layers = fields.get("layers") or ()
    for layer in layers:
        if layer != "python-ast":
            raise TargetsError(f"{here}: поле 'layers' — '{layer}': допустим "
                               f"только python-ast")
    if layers and not _is_pytest_command(fields.get("command")):
        raise TargetsError(f"{here}: поле 'layers' — python-ast у команды "
                           f"не pytest")
    pair = ("long_lived_dir", "long_lived_name")
    if "long_lived" in fields:
        reason = _long_lived_shape_error(fields)
        if reason:
            raise TargetsError(f"{here}: поле 'long_lived' — {reason}")
        for sub in pair:
            if sub in fields:
                raise TargetsError(f"{here}: поле 'long_lived' вместе с "
                                   f"'{sub}' — либо шаблон, либо пара полей")
    elif single and not any(sub in fields for sub in pair):
        raise TargetsError(f"{here}: нет ни шаблона long_lived, ни пары "
                           f"long_lived_dir/long_lived_name — обязательно у "
                           f"единственного компонента записи")
    if single:
        for sub in pair:
            if "long_lived" not in fields and sub not in fields:
                raise TargetsError(f"{here}: нет поля '{sub}' — обязательно "
                                   f"у единственного компонента записи")
        runner = fields.get("runner", PROFILE_RUNNER_DEFAULT)
        if runner != PROFILE_RUNNER_OWN:
            for sub in PROFILE_OWN_RUNNER_ONLY:
                if sub in fields:
                    raise TargetsError(
                        f"{here}: поле '{sub}' — у единственного компонента "
                        f"допустимо только при 'runner: {PROFILE_RUNNER_OWN}' "
                        f"(runner — '{runner}')")
    elif not fields.get("paths"):
        raise TargetsError(f"{here}: поле 'paths' — обязательно и непусто у "
                           f"записи с несколькими компонентами")
    if name == config.DEFAULT_TARGET:
        for sub in PROFILE_EXTERNAL_ONLY:
            if sub in fields:
                raise TargetsError(
                    f"{here}: поле '{sub}' — недопустимо у артели (правило "
                    f"импортов долгоживущих файлов пульта не расширяется)")
    if fields.get("repo", name) != name:
        raise TargetsError(f"{here}: поле 'repo' — '{fields['repo']}': "
                           f"несколько репозиториев не исполняются")


# Образцы заполнителей шаблона `long_lived` для сверки его последнего
# сегмента с масками `tests` (требование 1): идентификатор задачи — в
# нижнем регистре, как его подставляет правило имени.
_LONG_LIVED_SAMPLES = {"<id>": "0" * 26, "<name>": "a", "<dir>": "a"}


def _long_lived_shape_error(fields: dict) -> str:
    """Причина, по которой форма шаблона `long_lived` компонента не годна;
    пусто — годна (требование 1). Базовую форму пути уже проверил
    `_template_path_error`."""
    template = fields["long_lived"]
    segments = template.split("/")
    last = segments[-1]
    for mark in ("<id>", "<name>"):
        if template.count(mark) != 1 or last.count(mark) != 1:
            return (f"'{template}' — {mark} ровно один раз и только в "
                    f"последнем сегменте")
    if template.count("<dir>") > 1 or (
            "<dir>" in template and "<dir>" not in segments):
        return (f"'{template}' — <dir> не больше одного раза и только целым "
                f"сегментом")
    first = next(i for i, seg in enumerate(segments)
                 if any(mark in seg for mark in COMPONENT_TEMPLATE_MARKS))
    if first == 0:
        return (f"'{template}' — у шаблона long_lived нет каталога до первого "
                f"заполнителя")
    masks = fields.get("tests") or ()
    if masks and not _is_pytest_command(fields.get("command")):
        sample = last
        for mark, value in _LONG_LIVED_SAMPLES.items():
            sample = sample.replace(mark, value)
        if not any(_mask_segment_matches(mask.rsplit("/", 1)[-1], sample)
                   for mask in masks):
            return (f"'{template}' — последний сегмент не подходит под маски "
                    f"tests ({', '.join(masks)}): файл не признать файлом с "
                    f"меткой AC-<n>: ")
    return ""


def long_lived_pair(template: str) -> tuple[str, str]:
    """(`long_lived_dir`, `long_lived_name`) из шаблона `long_lived`
    (требование 2): каталог — сегменты до сегмента с первым заполнителем,
    имя — остаток (может начинаться с `<dir>/`)."""
    segments = template.split("/")
    first = next(i for i, seg in enumerate(segments)
                 if any(mark in seg for mark in COMPONENT_TEMPLATE_MARKS))
    return "/".join(segments[:first]), "/".join(segments[first:])


def _with_long_lived_pairs(entry: dict) -> dict:
    """Копия записи, у компонентов которой шаблон `long_lived` дополнен
    производной парой (требование 2): записи на диске и словарю,
    поданному `check`, пара не дописывается."""
    comps = entry.get(COMPONENTS_FIELD)
    if not isinstance(comps, dict) or not any(
            isinstance(fields, dict) and "long_lived" in fields
            for fields in comps.values()):
        return entry
    copied = {}
    for comp, fields in comps.items():
        if isinstance(fields, dict) and "long_lived" in fields:
            directory, name = long_lived_pair(fields["long_lived"])
            fields = dict(fields, long_lived_dir=directory,
                          long_lived_name=name)
        copied[comp] = fields
    return dict(entry, **{COMPONENTS_FIELD: copied})


# Повторы `guard._mask_segment_matches` и `acceptance.is_pytest_command`:
# импорт `scripts/guard.py` и `orchestrator/acceptance.py` отсюда — цикл
# импорта (требование 1).
def _mask_segment_matches(segment: str, name: str) -> bool:
    regex = "".join("[^/]*" if ch == "*" else re.escape(ch) for ch in segment)
    return re.fullmatch(regex, name) is not None


def _is_pytest_command(command) -> bool:
    command = list(command or ())
    if any(Path(part).name in ("pytest", "py.test") for part in command):
        return True
    return any(flag == "-m" and module == "pytest"
               for flag, module in zip(command, command[1:]))


def _component_value_error(kind: str, value: object, comp: str,
                           comps: dict) -> str:
    """Причина, по которой значение поля компонента не годно; пусто —
    годно. Виды профиля — прежним `_profile_value_error`."""
    if kind == "command":
        return _profile_value_error("list", value)
    if kind == "component_report":
        if value not in COMPONENT_REPORTS:
            return f"{value!r}, ожидается {' | '.join(COMPONENT_REPORTS)}"
        return ""
    if kind in ("path_template", "layout"):
        return _template_path_error(value, kind == "path_template")
    if kind == "repo":
        return "" if isinstance(value, str) and value.strip() else (
            "не непустая строка")
    if kind == "repo_paths":
        if not isinstance(value, list):
            return "не список путей от корня репозитория"
        for item in value:
            if (not isinstance(item, str) or not item or item.startswith("/")
                    or ".." in item.split("/")):
                return (f"элемент {item!r} — не относительный путь от корня "
                        f"репозитория (без ведущего '/' и '..')")
        return ""
    if kind == "masks":
        reason = _profile_value_error("list0", value)
        if reason:
            return reason
        for mask in value:
            if "{" in mask or "}" in mask:
                return (f"маска '{mask}': альтернативы `{{a,b}}` не "
                        f"поддерживаются — разверните в несколько масок")
        return ""
    if kind == "regexes":
        return _regexes_error(value)
    if kind == "paths_source":
        return _exact_strings_error(value, COMPONENT_PATHS_SOURCE)
    if kind == "depends_on":
        return _depends_on_error(value, comp, comps)
    if kind == "tools":
        if not isinstance(value, dict):
            return "не отображение «имя инструмента → строка версии»"
        for tool, version in value.items():
            if not isinstance(version, str):
                return (f"версия '{tool}' — {version!r}, не строка (пиши в "
                        f"кавычках)")
        return ""
    return _profile_value_error(kind, value)


def _template_path_error(value: object, marks_only: bool) -> str:
    """Шаблон пути от корня репозитория с обязательным `<id>`; при
    `marks_only` допустимы только заполнители `COMPONENT_TEMPLATE_MARKS`."""
    if not isinstance(value, str) or not value.strip():
        return "не непустая строка"
    parts = value.split("/")
    if value.startswith("/") or ".." in parts or "" in parts:
        return (f"'{value}' — не относительный путь от корня репозитория "
                f"(без ведущего '/', '..' и пустых сегментов)")
    if "<id>" not in value:
        return f"'{value}' — нет заполнителя <id>"
    if marks_only:
        foreign = [m for m in re.findall(r"<[^<>]*>", value)
                   if m not in COMPONENT_TEMPLATE_MARKS]
        if foreign:
            return (f"'{value}' — заполнитель {', '.join(foreign)}; допустимы "
                    f"только {', '.join(COMPONENT_TEMPLATE_MARKS)}")
    return ""


def _regexes_error(value: object) -> str:
    """Регулярные выражения путей: строка или потоковый список строк,
    каждая компилируется и без символов `COMPONENT_REGEX_FORBIDDEN`."""
    items = [value] if isinstance(value, str) else value
    if not isinstance(items, list):
        return "не строка и не список регулярных выражений"
    for item in items:
        if not isinstance(item, str) or not item:
            return f"элемент {item!r} — не непустая строка"
        bad = [ch for ch in COMPONENT_REGEX_FORBIDDEN if ch in item]
        if bad:
            return (f"выражение '{item}' содержит {' '.join(bad)} — потоковый "
                    f"список targets.yaml такие символы не передаёт")
        try:
            re.compile(item)
        except re.error as exc:
            return f"выражение '{item}' не компилируется: {exc}"
    return ""


def _exact_strings_error(value: object, keys: tuple) -> str:
    """Отображение ровно из подполей `keys`, каждое — непустая строка."""
    if not isinstance(value, dict):
        return f"не отображение подполей {', '.join(keys)}"
    extra = [key for key in value if key not in keys]
    if extra:
        return f"лишнее подполе '{extra[0]}' (допустимы: {', '.join(keys)})"
    for key in keys:
        item = value.get(key)
        if not isinstance(item, str) or not item.strip():
            return f"подполе '{key}' — нет или не непустая строка"
    return ""


def _depends_on_error(value: object, comp: str, comps: dict) -> str:
    """`depends_on`: «имя поставщика → поля `via`, `paths`»; поставщик —
    другой компонент той же записи."""
    if not isinstance(value, dict):
        return "не отображение «имя компонента-поставщика → поля»"
    for supplier, spec in value.items():
        if supplier == comp:
            return f"поставщик '{supplier}' — сам компонент"
        if supplier not in comps:
            return f"поставщик '{supplier}' — нет такого компонента в записи"
        if not isinstance(spec, dict):
            return f"поставщик '{supplier}' — поля не отображение"
        extra = [key for key in spec if key not in ("via", "paths")]
        if extra:
            return (f"поставщик '{supplier}': лишнее поле '{extra[0]}' "
                    f"(допустимы: via, paths)")
        for key in ("via", "paths"):
            if key not in spec:
                return f"поставщик '{supplier}': нет поля '{key}'"
        if spec["via"] not in COMPONENT_DEPENDS_VIA:
            return (f"поставщик '{supplier}': via — {spec['via']!r}, "
                    f"ожидается {' | '.join(COMPONENT_DEPENDS_VIA)}")
        reason = _regexes_error(spec["paths"])
        if reason:
            return f"поставщик '{supplier}': paths — {reason}"
    return ""


def secret_env_names() -> set[str]:
    """Имена переменных-секретов, которых не может задать `env` профиля:
    `secret_env_names()` всех провайдеров реестра на момент вызова плюс
    токены форжа. Реестр, а не литералы: новый провайдер со своим
    секретом не придётся дописывать сюда."""
    # Импорт здесь: providers → claude → runner → store → targets — на
    # уровне модуля это цикл.
    from .providers import PROVIDERS
    names = set(FORGE_SECRET_ENV_NAMES)
    for provider in PROVIDERS.values():
        names.update(provider.secret_env_names())
    return names


def _profile_value_error(kind: str, value: object) -> str:
    """Причина, по которой значение подполя профиля не годно; пусто —
    годно."""
    if kind == "mapping":
        if not isinstance(value, dict):
            return "не отображение имён переменных в строки"
        for key, item in value.items():
            # bool, int, float и None — то, что `yamlmini.scalar` даёт из
            # значения без кавычек; окружению процесса нужны строки.
            if not isinstance(item, str):
                return f"значение '{key}' — {item!r}, не строка"
        secrets = sorted(set(value) & secret_env_names())
        if secrets:
            return f"имя секрета {', '.join(secrets)} — секреты в env не задаются"
        return ""
    if kind == "positive_int":
        return "не положительное целое число секунд" if (
            type(value) is not int or value <= 0) else ""
    if kind == "identifiers":
        if not isinstance(value, list):
            return "не список верхних имён импорта"
        for item in value:
            if not isinstance(item, str) or not item.isidentifier():
                return (f"элемент {item!r} — не верхнее имя импорта "
                        f"(идентификатор Python без точек и шаблонов)")
        return ""
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
    elif kind == "runner" and value not in PROFILE_RUNNERS:
        return f"'{value}', ожидается {' | '.join(PROFILE_RUNNERS)}"
    return ""
