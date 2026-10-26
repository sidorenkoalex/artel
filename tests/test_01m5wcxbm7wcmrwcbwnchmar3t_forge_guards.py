"""Сторожа устройства хостинга разбором `ast`: сеть только в транспорте `gitlab_adapter` (AC-17), выбор хостинга только реестром `forge` (AC-21).

Группа: долгоживущий
Красен до реализации: модулей `orchestrator/forge.py` и `orchestrator/gitlab_adapter.py` ещё нет — чтение их исходного текста падает `FileNotFoundError` (самопроверка сторожа `ci.py` на мутациях AC-21 зелена уже сейчас: она разбирает существующий `ci.py`).

Свойство — текст модулей, поэтому песочница не нужна: сторож читает
исходный текст `orchestrator/ci.py`, `orchestrator/forge.py`,
`orchestrator/gitlab_adapter.py` из каталога пакета и разбирает его `ast`.
Каждый сторож сначала проверяет себя: к настоящему тексту модуля
дописывается мутация из AC, и сторож обязан её назвать; образцы,
которые AC прямо называет законными (`urllib.error` в `except`,
`<значение> not in <реестр>`), сторож пропускает.

Функция транспорта — `gitlab_adapter.transport`, функция запроса —
`gitlab_adapter.request` (ответ Оператора В-1, В-2). По ответу В-5 вне
транспорта законны `urllib.error` (исключения) и `urllib.parse` (разбор и
кодирование адреса без сети); `urllib.request`, прочий `urllib`,
`http.client` и `socket` — только в транспорте.

Имена в мутациях (псевдоним импорта, имя функции-мутанта, вызываемая
функция `forge`) порождаются модулем `random` при каждом запуске; зерно
печатается и входит в текст провала.
"""
import ast
import random
from pathlib import Path

import pytest

import orchestrator

PACKAGE = Path(orchestrator.__file__).resolve().parent
TRANSPORT = "transport"
REQUEST = "request"
HOSTING_LITERALS = {"github", "gitlab"}
FORGE_FUNCTIONS = ["pipeline_status", "job_result", "job_test_report",
                   "mr_status", "token_user", "protections"]


def module_text(name: str) -> str:
    return (PACKAGE / name).read_text(encoding="utf-8")


@pytest.fixture
def rng():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return random.Random(value), value


def ident(rng: random.Random, prefix: str) -> str:
    return prefix + "".join(rng.choice("abcdefghijkmnpqrstuvwxyz") for _ in range(6))


# --- сторож AC-17: urllib/http.client только в транспорте ---

NETWORK_FREE = ("urllib.error", "urllib.parse")
NETWORK_MODULES = ("http.client", "socket")


def _network_path(dotted: str) -> bool:
    """Путь имени — сеть: всё из `urllib`, кроме `urllib.error`/`urllib.parse`, `http.client`, `socket`."""
    if any(dotted == free or dotted.startswith(free + ".") for free in NETWORK_FREE):
        return False
    if dotted.startswith("urllib."):
        return True
    return any(dotted == mod or dotted.startswith(mod + ".") for mod in NETWORK_MODULES)


def _bind_imports(stmt: ast.stmt, env: dict) -> list:
    """Связывает имена импорта `stmt` в `env`; возвращает пути `from`-импорта."""
    imported = []
    if isinstance(stmt, ast.Import):
        for alias in stmt.names:
            if alias.asname:
                env[alias.asname] = alias.name
            else:
                head = alias.name.split(".")[0]
                env[head] = head
    elif isinstance(stmt, ast.ImportFrom) and stmt.level == 0 and stmt.module:
        for alias in stmt.names:
            path = f"{stmt.module}.{alias.name}"
            env[alias.asname or alias.name] = path
            imported.append(path)
    return imported


def _chain(node: ast.AST) -> tuple[str, list] | None:
    """(корневое имя, атрибуты) цепочки `a.b.c`; None — не цепочка имён."""
    attrs = []
    while isinstance(node, ast.Attribute):
        attrs.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        return node.id, list(reversed(attrs))
    return None


def network_violations(source: str, module: str, transport_owner: bool) -> list[str]:
    """Нарушения AC-17 в тексте модуля: «модуль:строка: что».

    Вне функции `transport` модуля (у `forge.py` такой функции нет вовсе)
    нарушение — `from`-импорт из `urllib`/`http.client` (кроме
    `urllib.error`) и любое обращение к имени, путь которого ведёт в
    `urllib`/`http.client` (кроме `urllib.error`). Вне функции `request`
    нарушение — любое обращение к имени `transport`.
    """
    found = []
    tree = ast.parse(source)

    def visit(node: ast.AST, env: dict, functions: tuple) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions = functions + (node.name,)
            env = dict(env)
        in_transport = transport_owner and functions[:1] == (TRANSPORT,)
        in_request = transport_owner and functions[:1] == (REQUEST,)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            paths = _bind_imports(node, env)
            if not in_transport:
                for path in paths:
                    if _network_path(path) or path == "http.client":
                        found.append(f"{module}:{node.lineno}: импорт {path} вне транспорта")
        if isinstance(node, (ast.Attribute, ast.Name)) and not in_transport:
            chain = _chain(node)
            if chain is not None and chain[0] in env:
                dotted = ".".join([env[chain[0]], *chain[1]])
                if _network_path(dotted):
                    found.append(f"{module}:{node.lineno}: обращение {dotted} вне транспорта")
                    return
        if not in_request:
            if isinstance(node, ast.Name) and node.id == TRANSPORT:
                found.append(f"{module}:{node.lineno}: транспорт вне функции запроса")
            if isinstance(node, ast.Attribute) and node.attr == TRANSPORT:
                found.append(f"{module}:{node.lineno}: транспорт вне функции запроса")
                return
        for child in ast.iter_child_nodes(node):
            visit(child, env, functions)

    # Импорты верхнего уровня видны всем функциям модуля, где бы ни стояли.
    module_env = {}
    for stmt in tree.body:
        _bind_imports(stmt, module_env)
    visit(tree, module_env, ())
    return found


def adapter_violations(source: str) -> list[str]:
    return network_violations(source, "gitlab_adapter.py", True)


def transport_uses_network(source: str) -> bool:
    """В модуле одна функция верхнего уровня `transport`, и в ней есть обращение к сети."""
    defs = [n for n in ast.parse(source).body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == TRANSPORT]
    if len(defs) != 1:
        return False
    module_env = {}
    for stmt in ast.parse(source).body:
        _bind_imports(stmt, module_env)
    env = dict(module_env)
    for node in ast.walk(defs[0]):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for path in _bind_imports(node, env):
                if _network_path(path) or path == "http.client":
                    return True
    for node in ast.walk(defs[0]):
        chain = _chain(node) if isinstance(node, (ast.Attribute, ast.Name)) else None
        if chain is not None and chain[0] in env:
            if _network_path(".".join([env[chain[0]], *chain[1]])):
                return True
    return False


def adapter_mutants(rng: random.Random) -> dict:
    alias = ident(rng, "_open_")
    fn = ident(rng, "_mutant_")
    return {
        "urlopen-вне-транспорта":
            f"import urllib.request\n\ndef {fn}(url):\n"
            f"    return urllib.request.urlopen(url)\n",
        "from-импорт-с-псевдонимом":
            f"from urllib.request import urlopen as {alias}\n\ndef {fn}(url):\n"
            f"    return {alias}(url)\n",
        "from-импорт-без-псевдонима":
            f"from urllib.request import urlopen\n\ndef {fn}(url):\n"
            f"    return urlopen(url)\n",
        "http.client-вне-транспорта":
            f"import http.client\n\ndef {fn}():\n"
            f"    return http.client.HTTPSConnection('localhost')\n",
        "socket-вне-транспорта":
            f"import socket\n\ndef {fn}():\n"
            f"    return socket.create_connection(('localhost', 443))\n",
        "urllib.request-рядом-с-parse":
            f"import urllib.parse\nimport urllib.request\n\ndef {fn}(url):\n"
            f"    return urllib.request.Request(urllib.parse.quote(url))\n",
        "транспорт-не-из-запроса":
            f"\ndef {fn}():\n    return {TRANSPORT}('GET', 'https://localhost/api/v4/user', "
            f"{{}}, None, 5)\n",
    }


ADAPTER_MUTANTS = ["urlopen-вне-транспорта", "from-импорт-с-псевдонимом",
                   "from-импорт-без-псевдонима", "http.client-вне-транспорта",
                   "socket-вне-транспорта", "urllib.request-рядом-с-parse",
                   "транспорт-не-из-запроса"]


def test_ac17_real_modules_keep_network_inside_transport():
    """В настоящих `forge.py` и `gitlab_adapter.py` сеть стоит только в транспорте.

    Сценарий: разбираются оба модуля; нарушений сторожа нет ни в одном, а
    в `gitlab_adapter.py` есть ровно одна функция `transport`, и именно
    она обращается к `urllib`/`http.client` (иначе сторож был бы пуст).

    Ловит мутацию: функция запроса сама зовёт `urllib.request.urlopen`
    (или `forge.py` импортирует `from urllib.request import urlopen`) —
    сторож называет модуль и строку обращения вне транспорта.
    """
    adapter = module_text("gitlab_adapter.py")
    forge_src = module_text("forge.py")
    found = adapter_violations(adapter) + network_violations(forge_src, "forge.py", False)
    assert found == [], "\n".join(found)
    assert transport_uses_network(adapter), \
        "в gitlab_adapter.py нет единственной функции transport с обращением к urllib/http.client"


@pytest.mark.parametrize("kind", ADAPTER_MUTANTS)
def test_ac17_guard_catches_mutation(kind, rng):
    """Мутация из AC-17, дописанная к настоящему `gitlab_adapter.py`, краснит сторож.

    Сценарий: к тексту модуля дописывается вызов `urlopen` вне
    транспорта, `from`-импорт `urlopen` (с псевдонимом и без) с вызовом,
    обращение к `http.client` либо вызов транспорта из посторонней
    функции; сторож обязан назвать нарушение. Тот же вызов `urlopen`,
    дописанный к `forge.py`, тоже нарушение.

    Ловит мутацию: сторож, глядящий только на `urllib.request.urlopen`
    полным путём (без разрешения псевдонимов импорта) или не проверяющий,
    откуда зовут транспорт, пропустит мутацию — список нарушений пуст.
    """
    gen, seed = rng
    snippet = adapter_mutants(gen)[kind]
    adapter = module_text("gitlab_adapter.py")
    found = adapter_violations(adapter + "\n\n" + snippet)
    assert found, f"зерно: {seed}; мутация «{kind}» не поймана:\n{snippet}"
    if kind == "urlopen-вне-транспорта":
        forge_found = network_violations(module_text("forge.py") + "\n\n" + snippet,
                                         "forge.py", False)
        assert forge_found, f"зерно: {seed}; мутация в forge.py не поймана"


@pytest.mark.parametrize("snippet", [
    "from urllib.error import URLError, HTTPError\n\n"
    "def _not_mutant_a():\n    try:\n        return 1\n"
    "    except (URLError, HTTPError):\n        return 0\n",
    "import urllib.error\n\n"
    "def _not_mutant_b():\n    try:\n        return 1\n"
    "    except urllib.error.URLError:\n        return 0\n",
    "import urllib.parse\n\n"
    "def _not_mutant_c(path):\n    return urllib.parse.quote(path, safe='')\n",
    "from urllib.parse import quote as _q, urlsplit\n\n"
    "def _not_mutant_d(url):\n    return _q(urlsplit(url).path, safe='')\n",
])
def test_ac17_exception_classes_are_not_violations(snippet):
    """Исключения `urllib.error` и разбор адреса `urllib.parse` вне транспорта — не нарушение.

    Сценарий: к настоящему `gitlab_adapter.py` дописывается импорт
    `URLError`/`HTTPError` из `urllib.error` и их ловля в `except` вне
    транспорта, либо кодирование и разбор адреса `urllib.parse` (модулем
    и `from`-импортом с псевдонимом) вне транспорта; список нарушений не
    меняется.

    Ловит мутацию: сторож, считающий нарушением любое имя из `urllib`,
    запретил бы законную ловлю исключений и кодирование пути проекта —
    список нарушений вырастет.
    """
    adapter = module_text("gitlab_adapter.py")
    assert adapter_violations(adapter + "\n\n" + snippet) == adapter_violations(adapter)


# --- сторож AC-21: выбор хостинга только реестром forge ---

def _forge_aliases(tree: ast.Module) -> set:
    """Имена, под которыми `ci.py` видит модуль `forge` (`from . import forge`)."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (
                (node.level >= 1 and node.module is None)
                or (node.level == 0 and node.module == "orchestrator")):
            names |= {a.asname or a.name for a in node.names if a.name == "forge"}
        if isinstance(node, ast.Import):
            names |= {a.asname for a in node.names if a.name == "orchestrator.forge" and a.asname}
    return names


def _forge_field_access(node: ast.AST) -> bool:
    if isinstance(node, ast.Subscript):
        return isinstance(node.slice, ast.Constant) and node.slice.value == "forge"
    if isinstance(node, ast.Call):
        func = node.func
        return (isinstance(func, ast.Attribute) and func.attr == "get" and bool(node.args)
                and isinstance(node.args[0], ast.Constant) and node.args[0].value == "forge")
    return False


def ci_violations(source: str) -> list[str]:
    """Нарушения AC-21 в `ci.py`: литерал хостинга в любом узле, `FORGES`,
    поле `forge` записи не аргументом вызова функции модуля `forge`."""
    tree = ast.parse(source)
    aliases = _forge_aliases(tree)
    parents = {child: parent for parent in ast.walk(tree)
               for child in ast.iter_child_nodes(parent)}
    found = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", "?")
        if isinstance(node, ast.Constant) and node.value in HOSTING_LITERALS:
            found.append(f"ci.py:{line}: литерал {node.value!r}")
        if isinstance(node, ast.Attribute) and node.attr == "FORGES":
            found.append(f"ci.py:{line}: обращение к FORGES")
        if isinstance(node, ast.Name) and node.id == "FORGES":
            found.append(f"ci.py:{line}: обращение к FORGES")
        if isinstance(node, ast.ImportFrom) and any(a.name == "FORGES" for a in node.names):
            found.append(f"ci.py:{line}: импорт FORGES")
        if _forge_field_access(node):
            parent = parents.get(node)
            ok = (isinstance(parent, ast.Call) and isinstance(parent.func, ast.Attribute)
                  and isinstance(parent.func.value, ast.Name)
                  and parent.func.value.id in aliases
                  and (node in parent.args or any(k.value is node for k in parent.keywords)))
            if not ok:
                found.append(f"ci.py:{line}: поле forge вне аргумента функции forge: "
                             f"{ast.unparse(parent or node)}")
    return found


def forge_violations(source: str) -> list[str]:
    """Нарушения AC-21 в `forge.py`: литерал хостинга не ключом словаря
    либо ключом второго словаря."""
    tree = ast.parse(source)
    parents = {child: parent for parent in ast.walk(tree)
               for child in ast.iter_child_nodes(parent)}
    found = []
    registries = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value in HOSTING_LITERALS:
            parent = parents.get(node)
            if isinstance(parent, ast.Dict) and any(k is node for k in parent.keys):
                registries.add(id(parent))
            else:
                found.append(f"forge.py:{node.lineno}: литерал {node.value!r} не ключом реестра: "
                             f"{ast.unparse(parent) if parent is not None else node.value}")
    if len(registries) > 1:
        found.append(f"forge.py: литералы хостинга — ключи {len(registries)} словарей, не одного")
    return found


def forge_registry_name(source: str) -> str | None:
    """Имя, которому присвоен словарь с ключами `"github"` и `"gitlab"`."""
    for node in ast.walk(ast.parse(source)):
        value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
        if not isinstance(value, ast.Dict):
            continue
        keys = {k.value for k in value.keys if isinstance(k, ast.Constant)}
        if HOSTING_LITERALS <= keys:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    return target.id
    return None


def ci_mutants(rng: random.Random) -> dict:
    fn = ident(rng, "_mutant_")
    call = rng.choice(FORGE_FUNCTIONS)
    return {
        "ветвление-по-FORGES":
            f"def {fn}(entry):\n    if entry[\"forge\"] == targets.FORGES[1]:\n"
            f"        return 1\n    return 0\n",
        "сравнение-результата-forge":
            f"def {fn}(target):\n    return forge.{call}(target) == \"gitlab\"\n",
        "промежуточная-переменная":
            f"def {fn}(target):\n    k = forge.{call}(target)\n    if k == \"gitlab\":\n"
            f"        return 1\n    return 0\n",
        "match-case":
            f"def {fn}(target):\n    match forge.{call}(target):\n"
            f"        case \"gitlab\":\n            return 1\n        case _:\n"
            f"            return 0\n",
        "второй-словарь":
            f"{fn.upper()} = {{\"github\": 1, \"gitlab\": 2}}\n",
    }


CI_MUTANTS = ["ветвление-по-FORGES", "сравнение-результата-forge",
              "промежуточная-переменная", "match-case", "второй-словарь"]


def forge_mutants(rng: random.Random) -> dict:
    fn = ident(rng, "_mutant_")
    return {
        "if-вместо-индекса":
            f"def {fn}(value):\n    if value == \"gitlab\":\n        return 1\n    return 0\n",
        "match-case":
            f"def {fn}(value):\n    match value:\n        case \"gitlab\":\n"
            f"            return 1\n        case _:\n            return 0\n",
    }


FORGE_MUTANTS = ["if-вместо-индекса", "match-case"]


def test_ac21_real_modules_select_forge_by_registry():
    """Настоящие `ci.py` и `forge.py` выбирают хостинг только реестром.

    Сценарий: в `ci.py` нет литералов `"github"`/`"gitlab"` ни в одном
    узле, нет `targets.FORGES`, поле `forge` записи стоит только
    аргументом вызова функции модуля `forge`; в `forge.py` литералы стоят
    только ключами одного словаря, и этот словарь — с обоими ключами —
    присвоен имени (реестр существует, сторож не пуст).

    Ловит мутацию: `ci.py` ветвится `if entry["forge"] == "gitlab":` или
    `forge.py` выбирает реализацию `if value == "gitlab":` — сторож
    называет файл и строку.
    """
    found = ci_violations(module_text("ci.py")) + forge_violations(module_text("forge.py"))
    assert found == [], "\n".join(found)
    assert forge_registry_name(module_text("forge.py")) is not None, \
        "в forge.py нет словаря-реестра с ключами 'github' и 'gitlab'"


@pytest.mark.parametrize("kind", CI_MUTANTS)
def test_ac21_ci_guard_catches_mutation(kind, rng):
    """Мутация `ci.py` из AC-21, дописанная к настоящему модулю, краснит сторож.

    Сценарий: к тексту `ci.py` дописывается ветвление по
    `targets.FORGES[1]`, сравнение результата функции `forge` с
    `"gitlab"` (прямо и через переменную), `match`/`case "gitlab"` или
    второй словарь с ключами хостингов; сторож обязан назвать нарушение.

    Ловит мутацию: сторож, проверяющий только сравнения поля `forge`
    (как сторож А0), пропустит переменную `k`, `match` и словарь —
    список нарушений пуст.
    """
    gen, seed = rng
    snippet = ci_mutants(gen)[kind]
    found = ci_violations(module_text("ci.py") + "\n\n" + snippet)
    assert found, f"зерно: {seed}; мутация «{kind}» не поймана:\n{snippet}"


@pytest.mark.parametrize("kind", FORGE_MUTANTS)
def test_ac21_forge_guard_catches_mutation(kind, rng):
    """Мутация `forge.py` из AC-21 краснит сторож, проверка членства — нет.

    Сценарий: к тексту `forge.py` дописывается выбор `if value ==
    "gitlab":` или `match value: case "gitlab":` — сторож называет
    нарушение; дописанная проверка `if value not in <реестр>:` по имени
    настоящего реестра список нарушений не меняет.

    Ловит мутацию: сторож, считающий нарушением любое `in`/`not in` в
    `forge.py`, запретит законную проверку членства; сторож, не
    видящий литерал в `case`, пропустит `match`.
    """
    gen, seed = rng
    source = module_text("forge.py")
    snippet = forge_mutants(gen)[kind]
    assert forge_violations(source + "\n\n" + snippet), \
        f"зерно: {seed}; мутация «{kind}» не поймана:\n{snippet}"
    registry = forge_registry_name(source)
    assert registry is not None, "в forge.py нет словаря-реестра"
    member = (f"def {ident(gen, '_member_')}(value):\n    if value not in {registry}:\n"
              f"        return None\n    return {registry}[value]\n")
    assert forge_violations(source + "\n\n" + member) == forge_violations(source), \
        f"зерно: {seed}; проверка членства названа нарушением:\n{member}"
