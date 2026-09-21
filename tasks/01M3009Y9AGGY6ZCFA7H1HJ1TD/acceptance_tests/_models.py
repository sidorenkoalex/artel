"""Общий код планки: каталог моделей, локальный слой, разрешение цепочки.

Почему этот модуль вообще есть. SPEC называет по имени ровно ОДНУ точку
нового модуля — `models.resolve_role(role)` (требование 8). Имени функции
загрузки каталога, имени разбора локального слоя, имён полей результата
разрешения и ключа явного разрешения `experimental` критерии не называют.
Планка — лок (skills/test-authoring.md): диктовать разработчику имя,
которого SPEC не требовал, она не вправе. Отсюда три приёма:

- `module()` — ЛЕНИВЫЙ импорт `orchestrator.models`. На верхнем уровне
  файлов планки его нет намеренно: сухой сбор планки на выходе
  `tests_writing` (`orchestrator/advance_gates/tests_writing.py` ->
  `acceptance.collect`) импортирует каждый файл, и модуль, которого ещё
  нет, отказал бы переход «планка не собирается» вместо честной красноты
  самих тестов;
- `catalog_loader()`/`local_loader()` — функция ищется среди
  общепринятых имён, затем сканом публичных функций по смыслу имени;
- `flat_values()`/`has_value()` — результат сверяется по ЗНАЧЕНИЯМ, а не
  по именам полей.

Сломанные каталоги (AC-3) — ТЕКСТОВЫЕ мутации настоящего `models.yaml`
репозитория, а не собственная копия схемы: форму записи каталога SPEC
фиксирует только частично (`list_price_usd_per_mtok`, четыре вида
токенов, `cost_from_cli`, перечень статусов), и планка, сочинившая
остальное, краснела бы на законном варианте разработчика.
"""
import ast
import dataclasses
import importlib
import inspect
import re
from pathlib import Path
from unittest import mock

from orchestrator import config, yamlmini

# Корень РЕАЛЬНОГО дерева репозитория: `config.ROOT` песочницы подменён
# временным каталогом, а настоящие `models.yaml`/`roles.yaml`/`docs/`
# планка читает именно из рабочей копии задачи.
REPO_ROOT = Path(__file__).resolve().parents[3]

CATALOG_NAME = "models.yaml"
CATALOG_PATH = REPO_ROOT / CATALOG_NAME
LOCAL_DIR = ".artel"

# Имена, названные самими критериями (AC-1, AC-6).
PRICE_KEY = "list_price_usd_per_mtok"
PRICE_KINDS = ("input", "output", "cache_write", "cache_read")
STATUSES = ("supported", "experimental")
TIERS = ("strong", "standard", "cheap")

SONNET = "claude-sonnet-5"
OPUS = "claude-opus-5"
FABLE = "claude-fable-5-1"
MODEL_IDS = (SONNET, OPUS, FABLE)

# Прейскурант `claude-opus-5` и минимум CLI `claude-fable-5-1` — числа
# самого AC-2 (там они названы буквально). Динамически от
# `config.TOKEN_RATES`/`stack.MODEL_MIN_CLI_VERSION` их взять нельзя: обе
# таблицы уходят — вторая удаляется этой же задачей (AC-13), первая
# частью 2 линии.
OPUS_PRICES = {"input": 5.0, "output": 25.0,
               "cache_write": 6.25, "cache_read": 0.5}
FABLE_MIN_CLI = "2.1.251"

DATE_RE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")
VERSION_RE = re.compile(r"\A\d+\.\d+\.\d+\Z")

UNKNOWN_PROVIDER = "provayder-kotorogo-net-v-reestre"


# --- модуль и его функции ---------------------------------------------

def module():
    """`orchestrator.models` — импорт в момент вызова (см. докстринг)."""
    return importlib.import_module("orchestrator.models")


_CATALOG_LOADER_NAMES = ("load_catalog", "catalog", "load", "load_models",
                         "parse_catalog", "read_catalog")
_LOCAL_LOADER_NAMES = ("load_local", "load_local_layer", "local_layer",
                       "local", "parse_local", "read_local",
                       "load_local_models", "load_overrides")


def _pick(names: tuple, needle: str, forbidden: tuple):
    """Функция модуля по одному из общепринятых имён `names`, иначе — по
    смыслу имени (`needle` в имени, ничего из `forbidden`)."""
    mod = module()
    for name in names:
        fn = getattr(mod, name, None)
        if callable(fn) and not isinstance(fn, type):
            return fn
    # Имена, похожие на чтение (`load_*`/`parse_*`/`read_*`), — раньше
    # остальных: у модуля может быть и `local_path()`, отдающий путь, а не
    # разбор.
    def rank(name: str) -> tuple:
        return (0 if name.split("_")[0] in ("load", "parse", "read") else 1,
                name)

    for name in sorted(vars(mod), key=rank):
        if name.startswith("_"):
            continue
        fn = getattr(mod, name)
        if not callable(fn) or isinstance(fn, type):
            continue
        low = name.lower()
        if needle in low and not any(f in low for f in forbidden):
            return fn
    raise AssertionError(
        f"в orchestrator/models.py нет функции разбора «{needle}»: "
        f"планка принимает любое из имён {names} либо любое публичное имя "
        f"со словом «{needle}» (SPEC требование 3 называет разбор, но не "
        f"имя функции)")


def catalog_loader():
    return _pick(_CATALOG_LOADER_NAMES, "catalog", ("local", "role"))


def local_loader():
    return _pick(_LOCAL_LOADER_NAMES, "local", ("role",))


def _accepts_argument(fn) -> bool:
    try:
        params = [p for p in inspect.signature(fn).parameters.values()
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    except (TypeError, ValueError):
        return False
    return bool(params)


def _call_loader(fn, path: Path):
    """Загрузка файла `path`: аргументом, если функция его принимает; иначе
    — своим путём, который песочница уже подменила (`path_patchers`)."""
    if not _accepts_argument(fn):
        return fn()
    try:
        return fn(path)
    except TypeError:
        return fn(path.read_text(encoding="utf-8"))


def load_catalog(path: Path):
    return _call_loader(catalog_loader(), path)


def load_local(path: Path):
    return _call_loader(local_loader(), path)


def model_field_reads() -> list:
    """«путь:строка: код» каждого чтения поля `model` записи роли в
    `orchestrator/` — разбором AST, не текстом (AC-6).

    По AST, потому что упоминание `roles.model(role)` в докстринге или
    комментарии («раньше читалось отсюда») — не чтение поля: тем же
    приёмом `scripts/guard.py` отличает имя артефакта в докстринге от
    настоящего доступа к файлу.

    Формы: `roles.model(...)`, `<что-угодно>.get("model")`,
    `<что-угодно>["model"]` — все три встречаются в сегодняшнем коде
    (`orchestrator/runner.py`, `orchestrator/roles.py`,
    `orchestrator/stack.py`).
    """
    found = []
    for path in sorted((REPO_ROOT / "orchestrator").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            found.append(f"{path}: не разобран: {exc}")
            continue
        lines = source.splitlines()
        for node in ast.walk(tree):
            hit = False
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                attr = node.func.attr
                receiver = _dotted(node.func.value)
                if attr == "model" and receiver is not None \
                        and receiver.split(".")[-1] == "roles":
                    hit = True
                if attr in ("get", "pop") and node.args \
                        and isinstance(node.args[0], ast.Constant) \
                        and node.args[0].value == "model":
                    hit = True
            if isinstance(node, ast.Subscript) \
                    and isinstance(node.slice, ast.Constant) \
                    and node.slice.value == "model":
                hit = True
            if hit:
                text = lines[node.lineno - 1].strip()
                found.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}: {text}")
    return sorted(set(found))


def _dotted(node) -> str | None:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def resolve(role: str):
    """`models.resolve_role(role)` — единственная точка нового модуля,
    названная SPEC по имени (требование 8)."""
    return module().resolve_role(role)


def roles_tier_reader():
    """Функция `orchestrator/roles.py`, отдающая ярус роли. Имени SPEC не
    называет (требование 5 называет только поле `model_tier`), поэтому —
    общепринятые имена, затем скан публичных функций со словом «tier»."""
    from orchestrator import roles
    for name in ("model_tier", "tier", "role_tier", "model_tier_of"):
        fn = getattr(roles, name, None)
        if callable(fn) and not isinstance(fn, type):
            return fn
    for name in sorted(vars(roles)):
        if name.startswith("_"):
            continue
        fn = getattr(roles, name)
        if callable(fn) and not isinstance(fn, type) and "tier" in name.lower():
            return fn
    raise AssertionError(
        "в orchestrator/roles.py нет функции, отдающей ярус роли: планка "
        "принимает имя model_tier/tier/role_tier либо любое публичное имя "
        "со словом «tier»")


def role_tier(role: str):
    return roles_tier_reader()(role)


def path_patchers(root: Path) -> list:
    """Патчи путей каталога и локального слоя на временный корень `root`.

    `tests/sandbox.py::TmpRootTest` подменяет ФИКСИРОВАННЫЙ список путей
    `config` (`_patched_path`): новая константа пути каталога, если
    разработчик её заведёт, в этот список не входит и продолжала бы
    смотреть в настоящее дерево пульта. Патчится всё, что выглядит путём
    к `models.yaml`, — и в `config`, и в самом `orchestrator/models.py`.
    """
    mods = [config]
    try:
        mods.append(module())
    except ImportError:
        pass
    patchers = []
    for mod in mods:
        for name, value in list(vars(mod).items()):
            if not isinstance(value, Path) or value.name != CATALOG_NAME:
                continue
            target = (root / LOCAL_DIR / CATALOG_NAME
                      if value.parent.name == LOCAL_DIR else root / CATALOG_NAME)
            patchers.append(mock.patch.object(mod, name, target))
    return patchers


# --- разбор структуры каталога ----------------------------------------

def catalog_text() -> str:
    return CATALOG_PATH.read_text(encoding="utf-8")


def catalog_document() -> dict:
    return yamlmini.mapping(catalog_text())


def mappings(doc, path: tuple = ()):
    """(путь ключей, отображение) для документа и каждого вложенного в него.

    Форму записи каталога SPEC не фиксирует (раздел провайдера может быть
    как верхним ключом, так и лежать под `providers:`), поэтому структура
    ищется обходом, а не по фиксированному адресу."""
    if isinstance(doc, dict):
        yield path, doc
        for key, value in doc.items():
            yield from mappings(value, path + (key,))


def provider_sections(doc) -> dict:
    """{имя раздела провайдера: отображение} — раздел узнаётся по ключу
    `cost_from_cli`, который AC-1 называет дословно."""
    return {(path[-1] if path else None): m
            for path, m in mappings(doc) if "cost_from_cli" in m}


def provider_name(doc=None) -> str:
    doc = catalog_document() if doc is None else doc
    names = [n for n in provider_sections(doc) if isinstance(n, str)]
    assert len(names) == 1, f"ожидался один раздел провайдера, найдено: {names}"
    return names[0]


def section(doc, name: str):
    """Значение ключа `name` в документе или в любом вложенном
    отображении; `None` — ключа нет. Ключи `tiers:`/`overrides:` названы
    самим AC-8, а вот уровень вложенности — нет."""
    for _path, mapping in mappings(doc):
        if name in mapping:
            return mapping[name]
    return None


def model_entries(doc) -> dict:
    """{идентификатор модели: (путь, запись)} — запись узнаётся по ключу
    прейскуранта `list_price_usd_per_mtok`; идентификатор — ключ записи у
    родителя либо строковое поле записи, похожее на идентификатор."""
    out = {}
    for path, m in mappings(doc):
        if PRICE_KEY not in m:
            continue
        ident = path[-1] if path else None
        if not (isinstance(ident, str) and ident in MODEL_IDS):
            ident = next((v for v in m.values()
                          if isinstance(v, str) and v in MODEL_IDS), ident)
        out[ident] = (path, m)
    return out


# --- сверка результата по значениям -----------------------------------

def supported_models() -> list:
    """Идентификаторы моделей каталога со статусом `supported` — статус
    записи каталога задаёт разработчик, планка его не назначает."""
    entries = model_entries(catalog_document())
    return [model for model, (_path, entry) in entries.items()
            if any(v == "supported" for v in entry.values())]


def two_supported_models() -> tuple:
    """Две РАЗНЫЕ поддерживаемые модели каталога (вторая совпадает с
    первой, если поддерживаемая модель всего одна) — чтобы ярусы в
    сценарии указывали на разные модели."""
    models = supported_models()
    assert models, f"в каталоге {CATALOG_PATH} нет ни одной модели supported"
    first = OPUS if OPUS in models else models[0]
    second = next((m for m in models if m != first), first)
    return first, second


def flat_values(obj, depth: int = 4) -> list:
    """Плоский список значений результата (namedtuple / dataclass / dict /
    объект с атрибутами). Имён полей результата `resolve_role` SPEC не
    называет — сверять по значениям единственный способ проверить AC-10,
    ничего не диктуя разработчику."""
    out: list = []

    def walk(x, d):
        out.append(x)
        if d <= 0 or x is None or isinstance(x, (str, bytes, int, float, bool)):
            return
        if isinstance(x, dict):
            for key, value in x.items():
                out.append(key)
                walk(value, d - 1)
            return
        if dataclasses.is_dataclass(x) and not isinstance(x, type):
            walk(dataclasses.asdict(x), d)
            return
        if isinstance(x, (list, tuple, set, frozenset)):
            for value in x:
                walk(value, d - 1)
            return
        attrs = getattr(x, "__dict__", None)
        if attrs:
            walk(dict(attrs), d)
        return

    walk(obj, depth)
    return out


def _version_text(value) -> str | None:
    if isinstance(value, str) and VERSION_RE.match(value.strip()):
        return value.strip()
    if (isinstance(value, tuple) and value
            and all(isinstance(p, int) for p in value)):
        return ".".join(str(p) for p in value)
    return None


def has_value(result, wanted) -> bool:
    """`wanted` встречается среди значений результата. Версия принимается и
    строкой `2.1.251`, и кортежем `(2, 1, 251)` — формой её хранения SPEC
    не распоряжается."""
    wanted_version = _version_text(wanted)
    for value in flat_values(result):
        if isinstance(value, bool) != isinstance(wanted, bool):
            pass
        elif value == wanted:
            return True
        if (isinstance(wanted, float) and isinstance(value, (int, float))
                and not isinstance(value, bool)
                and abs(float(value) - wanted) < 1e-9):
            return True
        if isinstance(wanted, str) and isinstance(value, str) \
                and value.strip() == wanted:
            return True
        if wanted_version is not None and _version_text(value) == wanted_version:
            return True
    return False


def strings(result) -> list:
    return [v.strip() for v in flat_values(result) if isinstance(v, str)]


def nonnumeric(result) -> set:
    """Значения результата, кроме чисел — строки, перечисления, `None`.

    Источник тарифа сверяется через них: поля результата SPEC не называет,
    но «источник» — не число, а сами цены в двух сценариях и так разные."""
    return {repr(v) for v in flat_values(result)
            if not isinstance(v, (int, float)) or isinstance(v, bool)}


# --- фикстуры: роли, локальный слой, сломанные каталоги ---------------

def real_roles_document() -> dict:
    return yamlmini.mapping(
        (REPO_ROOT / "roles.yaml").read_text(encoding="utf-8"))


def agent_roles() -> list:
    """Роли настоящего `roles.yaml` с `executor: agent` — динамически, не
    списком в планке: состав ролей правит Оператор."""
    entries = real_roles_document().get("roles", {})
    return [name for name, entry in entries.items()
            if isinstance(entry, dict) and entry.get("executor") == "agent"]


_ROLE_ANCHOR = re.compile(r"^  ([A-Za-z_][A-Za-z0-9_]*):[^\S\n]*$")
_ROLE_MODEL_LINE = re.compile(r"^    model:[^\S\n]")


def roles_yaml_with_tiers(tier_by_role: dict, drop_model: bool = True) -> str:
    """Настоящий `roles.yaml` репозитория с `model_tier:` у названных ролей
    (и без строк `model:` — тем же приёмом, что `tests/
    test_runner_role_model.py::_roles_yaml_text` снимает поле модели).

    Сам `roles.yaml` задача не правит (требование 15 — приложение к PLAN),
    поэтому карта исполнителей сценария собирается здесь, а не берётся с
    диска: на приёмке в ветке она ещё с полем `model:` и без ярусов.
    `tier_by_role[role] = None` — роль остаётся без `model_tier` вовсе.
    """
    text = (REPO_ROOT / "roles.yaml").read_text(encoding="utf-8")
    out = []
    for line in text.splitlines(keepends=True):
        match = _ROLE_ANCHOR.match(line)
        if match:
            out.append(line)
            role = match.group(1)
            if tier_by_role.get(role) is not None:
                out.append(f"    model_tier: {tier_by_role[role]}\n")
            continue
        if drop_model and _ROLE_MODEL_LINE.match(line):
            continue
        out.append(line)
    return "".join(out)


def all_agent_tiers(tier: str = "strong") -> dict:
    return {role: tier for role in agent_roles()}


def _tiers_block(tiers: dict) -> str:
    body = "".join(f"  {name}: {model}\n" for name, model in tiers.items())
    return f"tiers:\n{body}"


def _override_block(model: str, prices: dict, calibrated_at: str,
                    source: str, form: int) -> str:
    kinds = "".join(f"      {kind}: {prices[kind]}\n" for kind in PRICE_KINDS)
    if form == 0:
        # Плоская форма: «собственный тариф по тем же четырём видам
        # токенов с полями calibrated_at и source» (требование 6).
        body = "".join(f"    {kind}: {prices[kind]}\n" for kind in PRICE_KINDS)
        return (f"overrides:\n  {model}:\n{body}"
                f"    calibrated_at: {calibrated_at}\n    source: {source}\n")
    # Вложенная форма: тот же ключ прейскуранта, что у каталога.
    return (f"overrides:\n  {model}:\n    {PRICE_KEY}:\n{kinds}"
            f"    calibrated_at: {calibrated_at}\n    source: {source}\n")


def _allow_block(model: str, form: int) -> str:
    return (f"allow_experimental: [{model}]\n",
            f"experimental_allowed: [{model}]\n",
            f"allow_experimental:\n  {model}: true\n",
            f"experimental:\n  {model}: true\n")[form]


def local_texts(tiers: dict, override: tuple | None = None,
                allow: str | None = None) -> list:
    """Тексты локального слоя во всех формах записи, которые SPEC
    допускает одинаково.

    Форму `overrides:` (плоские четыре вида токенов против вложенного
    прейскуранта) и написание явного разрешения `experimental` критерии
    не фиксируют — планка пробует каждую и принимает разработчика,
    выбравшего любую (см. `first_success`)."""
    override_forms = [None] if override is None else [0, 1]
    allow_forms = [None] if allow is None else [0, 1, 2, 3]
    texts = []
    for of in override_forms:
        for af in allow_forms:
            text = _tiers_block(tiers)
            if of is not None:
                model, prices, calibrated_at, source = override
                text += _override_block(model, prices, calibrated_at,
                                        source, of)
            if af is not None:
                text += _allow_block(allow, af)
            texts.append(text)
    return texts


def first_success(texts: list, attempt):
    """Результат `attempt(text)` на ПЕРВОЙ форме записи, где он не
    провалился; все формы провалились — `AssertionError` с перечнем
    попыток и причин (иначе разработчик увидел бы отказ последней формы и
    не понял, что планка пробовала остальные)."""
    failures = []
    for text in texts:
        try:
            return attempt(text)
        except Exception as exc:  # noqa: BLE001 — перебор форм записи
            failures.append(f"--- форма:\n{text}--- отказ: "
                            f"{type(exc).__name__}: {exc}")
    raise AssertionError(
        "ни одна форма записи локального слоя не подошла:\n"
        + "\n".join(failures))


def _entry_span(lines: list, model: str) -> tuple:
    """(первая, последняя+1) строки блока записи модели `model` в тексте
    каталога: ключ записи либо строка с её идентификатором."""
    for i, line in enumerate(lines):
        match = re.match(rf"^(\s*){re.escape(model)}:", line)
        if match is None:
            match = re.match(rf"^(\s*)\w+:\s*{re.escape(model)}\s*$", line)
            if match is None:
                continue
            # Идентификатор полем записи — начало блока ищем выше, на
            # строке с меньшим отступом.
            indent = len(match.group(1))
            start = i
            while start > 0:
                start -= 1
                head = lines[start]
                if head.strip() and len(head) - len(head.lstrip()) < indent:
                    break
            match = re.match(r"^(\s*)", lines[start])
        else:
            start = i
        indent = len(match.group(1))
        j = start + 1
        while j < len(lines):
            nxt = lines[j]
            if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                break
            j += 1
        return start, j
    raise AssertionError(f"запись модели {model} не найдена в {CATALOG_PATH}")


def with_unknown_provider() -> str:
    """Каталог, раздел провайдера которого назван именем вне реестра
    провайдеров пульта."""
    text = catalog_text()
    name = provider_name()
    pattern = re.compile(rf"^(\s*){re.escape(name)}:[^\S\n]*(#.*)?$", re.M)
    mutated, count = pattern.subn(rf"\g<1>{UNKNOWN_PROVIDER}:", text, count=1)
    assert count == 1, f"раздел провайдера {name} не найден в {CATALOG_PATH}"
    return mutated


def without_price(model: str) -> str:
    """Каталог, где у записи `model` вырезан весь блок прейскуранта."""
    lines = catalog_text().splitlines(keepends=True)
    start, end = _entry_span(lines, model)
    kept, dropping, drop_indent = [], False, 0
    for i, line in enumerate(lines):
        if start <= i < end:
            match = re.match(rf"^(\s*){re.escape(PRICE_KEY)}:", line)
            if match:
                dropping, drop_indent = True, len(match.group(1))
                continue
            if dropping:
                indent = len(line) - len(line.lstrip())
                if line.strip() and indent <= drop_indent:
                    dropping = False
                else:
                    continue
        kept.append(line)
    assert len(kept) < len(lines), f"прейскурант {model} не найден"
    return "".join(kept)


def with_partial_price(model: str, kind: str = "cache_read") -> str:
    """Каталог, где у записи `model` в прейскуранте не хватает одного из
    четырёх видов токенов."""
    lines = catalog_text().splitlines(keepends=True)
    start, end = _entry_span(lines, model)
    kept = [line for i, line in enumerate(lines)
            if not (start <= i < end and re.match(rf"^\s*{kind}:", line))]
    assert len(kept) == len(lines) - 1, f"цена {kind} у {model} не найдена"
    return "".join(kept)


def with_zero_price(model: str, kind: str = "input") -> str:
    """Каталог, где у записи `model` одна из четырёх цен — ноль."""
    lines = catalog_text().splitlines(keepends=True)
    start, end = _entry_span(lines, model)
    changed = False
    for i in range(start, end):
        match = re.match(rf"^(\s*{kind}:)\s*\S+", lines[i])
        if match:
            lines[i] = f"{match.group(1)} 0\n"
            changed = True
            break
    assert changed, f"цена {kind} у {model} не найдена"
    return "".join(lines)


def with_experimental(model: str) -> str:
    """Каталог, где у записи `model` статус `experimental`."""
    lines = catalog_text().splitlines(keepends=True)
    start, end = _entry_span(lines, model)
    changed = False
    for i in range(start, end):
        match = re.match(r"^(\s*\w+:)\s*supported\s*$", lines[i])
        if match:
            lines[i] = f"{match.group(1)} experimental\n"
            changed = True
            break
    assert changed, f"статус supported у {model} не найден"
    return "".join(lines)
