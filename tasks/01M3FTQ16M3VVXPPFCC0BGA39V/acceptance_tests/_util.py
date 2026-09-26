"""Общий код планки 01M3FTQ16M3VVXPPFCC0BGA39V (карта кодовой базы с
подпакетами, рудимент NoteError, пин версии CLI).

Три группы помощников, каждая нужна больше чем одному `test_*.py`:

- дерево-фикстура генератора (`FIXTURE_TREE`, `write_tree`) и разбор
  готового текста карты (`section_headers`/`section_text`/`field_labels`)
  — AC-1..AC-5;
- git-состояние РЕАЛЬНОГО репозитория этого рабочего каталога
  (`merge_base`/`show_at_base`/`diff_since_base`) — критерии «не
  изменено»/«не ослаблено» (AC-6, AC-10, AC-11) говорят буквально о
  правках ветки задачи относительно базы интеграции, это не
  воспроизвести песочницей;
- прогон самого генератора процессом (`run_generator`,
  `detached_worktree_at_head`) — AC-4 (байт-идентичность повторного
  прогона) и AC-7 (чистота дерева на голове ветки).

Артефакты задачи (SPEC/PLAN/REVIEW) здесь не читаются ни с диска, ни из
ветки: ни один критерий этой задачи о них не говорит.
"""
import ast
import contextlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import codebase_map  # noqa: E402

# Пути зоны карты берутся от генератора, не литералом: `MODULE_DIRS` —
# крутилка того же модуля, и фикстура, собранная под сегодняшний список,
# обязана падать громко, а не тихо переставать что-либо проверять (урок
# 28.08, статическая самопроверка фикстуры).
PKG = "orchestrator"
TESTS_DIR = "tests"
assert PKG in codebase_map.MODULE_DIRS, (
    f"фикстура планки собрана для каталога {PKG!r}, которого больше нет в "
    f"codebase_map.MODULE_DIRS={codebase_map.MODULE_DIRS}")
assert TESTS_DIR in codebase_map.MODULE_DIRS, (
    f"фикстура планки собрана для каталога {TESTS_DIR!r}, которого больше "
    f"нет в codebase_map.MODULE_DIRS={codebase_map.MODULE_DIRS}")

# Подпакет и модули фикстуры названы как реальные адреса из SPEC
# («Критерии приёмки», AC-2/AC-4): `orchestrator/doctor/preflight.py`.
SUBPKG = "doctor"
SUB_MODULE = f"{PKG}/{SUBPKG}/preflight.py"
SUB_NEIGHBOUR = f"{PKG}/{SUBPKG}/misc_checks.py"
SUB_INIT = f"{PKG}/{SUBPKG}/__init__.py"
TOP_MODULE = f"{PKG}/config.py"
TOP_IMPORTER = f"{PKG}/cli.py"
TOP_INIT = f"{PKG}/__init__.py"
TESTS_MODULE = f"{TESTS_DIR}/test_fixture.py"
PYCACHE_TRASH = f"{PKG}/{SUBPKG}/__pycache__/preflight.py"

FAKE_SHA = "0" * 40

GENERATOR = REPO_ROOT / "scripts" / "codebase_map.py"
MAP_REL = codebase_map.OUTPUT_PATH.as_posix()
MAP_PATH = REPO_ROOT / codebase_map.OUTPUT_PATH

# Дерево-фикстура: пакет с `__init__.py`, модулем верхнего уровня и
# подпакетом (`__init__.py` + два модуля), внутрипакетные относительные
# импорты, абсолютный импорт модуля подпакета извне подпакета, секция
# вида `tests/*` и мусорный `.py` внутри `__pycache__`.
FIXTURE_TREE = {
    TOP_INIT: '"""Пакет-фикстура: корень зоны карты."""\n',
    TOP_MODULE: (
        '"""Конфиг-фикстура: модуль верхнего уровня пакета."""\n'
        "\n"
        "LIMIT = 1\n"
        "\n"
        "\n"
        "def limit_value():\n"
        "    return LIMIT\n"
    ),
    TOP_IMPORTER: (
        '"""CLI-фикстура: абсолютный импорт модуля подпакета."""\n'
        f"from {PKG}.{SUBPKG} import preflight\n"
        "\n"
        "\n"
        "def main():\n"
        "    return preflight.check_something()\n"
    ),
    SUB_INIT: '"""Подпакет-фикстура: pre-flight проверки."""\n',
    SUB_MODULE: (
        '"""Модуль подпакета: сосед по подпакету и модуль пакета."""\n'
        "from . import misc_checks\n"
        "from .. import config\n"
        "\n"
        "\n"
        "def check_something():\n"
        "    return misc_checks.helper(config.LIMIT)\n"
    ),
    SUB_NEIGHBOUR: (
        '"""Сосед по подпакету фикстуры."""\n'
        "\n"
        "\n"
        "def helper(value):\n"
        "    return value\n"
    ),
    TESTS_MODULE: (
        '"""Тест-фикстура: секция вида tests/*."""\n'
        f"from {PKG} import config\n"
        "\n"
        "\n"
        "def test_limit():\n"
        "    assert config.LIMIT == 1\n"
    ),
    PYCACHE_TRASH: '"""Мусор внутри __pycache__: в перечень карты не входит."""\n',
}


def write_tree(root: Path, files: dict | None = None) -> Path:
    """Файлы `files` (по умолчанию `FIXTURE_TREE`) на диск под `root`."""
    for rel, source in (FIXTURE_TREE if files is None else files).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    return root


def discovered_rel_paths(root: Path) -> list:
    """`discover_module_paths(root)` в относительных posix-путях."""
    return [p.relative_to(root).as_posix()
            for p in codebase_map.discover_module_paths(root)]


def built_map(root: Path, sha: str = FAKE_SHA):
    """(текст карты, resolved_imports, imported_by) для дерева `root` —
    та же пара вызовов, что делает `codebase_map.main()` между чтением
    дерева и записью файла, без диска и git."""
    modules, resolved_imports, imported_by = codebase_map.build_modules(root)
    text = codebase_map.render(modules, resolved_imports, imported_by, sha)
    return text, resolved_imports, imported_by


_SECTION_HEADER_RE = re.compile(r"^## (.+)$", re.M)
_FIELD_LABEL_RE = re.compile(r"^\*\*([^:*]+):\*\*", re.M)


def section_headers(map_text: str) -> list:
    """Имена секций карты в порядке их следования в тексте."""
    return _SECTION_HEADER_RE.findall(map_text)


def section_text(map_text: str, rel: str) -> str | None:
    """Текст секции `## rel` до следующего заголовка `## ` или конца
    текста; `None` — секции с таким именем в карте нет."""
    marker = f"## {rel}\n"
    start = map_text.find(marker)
    if start < 0:
        return None
    rest = map_text[start + len(marker):]
    nxt = rest.find("\n## ")
    return marker + (rest if nxt == -1 else rest[:nxt + 1])


def field_labels(section: str) -> list:
    """Имена полей секции (`Назначение`, `Публичные функции`, …) в
    порядке следования — по разметке `**<имя>:**`, которой их пишет
    `codebase_map.render`."""
    return [label.strip() for label in _FIELD_LABEL_RE.findall(section)]


def strip_built_at_sha(map_text: str) -> str:
    """Текст карты без строки `built_at_sha:` — ровно та нормализация,
    которой CI-джоб codebase-map сверяет закоммиченную карту с
    перегенерированной (`.github/workflows/ci.yml`, шаг «закоммиченная
    карта не стухла»): sha собственного коммита карта нести не может."""
    return "\n".join(line for line in map_text.splitlines()
                     if not line.startswith("built_at_sha:"))


# --- git реального репозитория рабочего каталога -----------------------

def git(*args: str, cwd: Path | None = None, check: bool = True):
    return subprocess.run(["git", *args], cwd=cwd or REPO_ROOT,
                          capture_output=True, text=True, check=check)


def merge_base() -> str:
    """sha точки расхождения ветки задачи с базой интеграции:
    `origin/main`, а при его отсутствии (репозиторий без remote) —
    локальная `main`."""
    for ref in ("origin/main", "main"):
        res = git("merge-base", ref, "HEAD", check=False)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    raise AssertionError(
        "не удалось определить точку расхождения ветки задачи: ни "
        "origin/main, ни main не отвечают на git merge-base")


def show_at_base(rel: str) -> str | None:
    """Текст файла `rel` на точке расхождения с базой интеграции;
    `None` — файла там не было."""
    res = git("show", f"{merge_base()}:{rel}", check=False)
    return res.stdout if res.returncode == 0 else None


def diff_since_base(*pathspecs: str) -> str:
    """`git diff <merge-base>..рабочее дерево` — и закоммиченные, и
    незакоммиченные правки ветки задачи."""
    args = ["diff", merge_base()]
    if pathspecs:
        args.append("--")
        args.extend(pathspecs)
    return git(*args).stdout


def changed_paths_since_base(*pathspecs: str) -> list:
    args = ["diff", "--name-only", merge_base()]
    if pathspecs:
        args.append("--")
        args.extend(pathspecs)
    return [line for line in git(*args).stdout.splitlines() if line]


def function_source(text: str, name: str) -> str | None:
    """Исходный текст функции `name` в тексте модуля `text`; `None` —
    функции с таким именем на верхнем уровне модуля нет."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(text, node)
    return None


def first_if_test_source(text: str, function_name: str) -> str | None:
    """Текст условия первого `if` внутри функции `function_name` модуля
    `text` — то самое условие, которое критерий называет «условием
    алерта»; `None` — функции или `if` в ней нет."""
    source = function_source(text, function_name)
    if source is None:
        return None
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            return ast.get_source_segment(source, node.test)
    return None


# --- прогон генератора процессом ---------------------------------------

def run_generator(cwd: Path, script: Path | None = None):
    """`python3 scripts/codebase_map.py` отдельным процессом с рабочим
    каталогом `cwd` — тот же вызов, что делает CI-джоб codebase-map.

    `script` — какой именно генератор запускается; по умолчанию генератор
    рабочей копии шага. Для сверки дерева на голове ветки (AC-7) сюда
    обязан передаваться генератор ТОГО ЖЕ дерева (`cwd/scripts/
    codebase_map.py`): CI гоняет карту генератором из своего checkout, а
    не чужим, и генератор рабочей копии с незакоммиченной правкой дал бы
    сверке карту, которой на голове ветки нет."""
    return subprocess.run([sys.executable, str(script or GENERATOR)], cwd=cwd,
                          capture_output=True, text=True)


def subprocess_pytest(paths: list):
    """pytest отдельным процессом по перечисленным путям тестов, из корня
    рабочей копии (там лежит `conftest.py`, которым пульт собирает
    набор). Пути передаются поимённо — сторож роли в `conftest.py`
    отказывает только нецелевым аргументам (`pytest .`, голый `pytest`),
    перечисление файлов `tests/*` для него легитимно."""
    return subprocess.run(
        [sys.executable, "-m", "pytest", *paths, "-q", "-p", "no:cacheprovider"],
        cwd=REPO_ROOT, capture_output=True, text=True)


def init_git_repo(root: Path) -> None:
    """Дерево `root` — одиночный git-репозиторий с одним коммитом:
    генератор резолвит корень через `git rev-parse --show-toplevel` и
    читает sha головы, без git он не запускается вовсе. `--no-verify` —
    чтобы возможные хуки Оператора не участвовали в фикстуре."""
    git("init", "-q", cwd=root)
    git("add", "-A", cwd=root)
    git("-c", "user.email=fixture@artel.invalid", "-c", "user.name=Fixture",
        "commit", "--no-verify", "-q", "-m", "фикстура", cwd=root)


@contextlib.contextmanager
def detached_worktree_at_head():
    """Отдельная рабочая копия ГОЛОВЫ ветки задачи во временном каталоге
    (не в `.artel/worktrees` — чтобы не мусорить в пульте): в ней
    гоняется генератор, поэтому настоящая рабочая копия шага остаётся
    нетронутой, а сверяется ровно то дерево, которое получит CI после
    checkout."""
    tmp = tempfile.mkdtemp(prefix="artel-map-head-")
    git("worktree", "add", "--detach", "--quiet", tmp, "HEAD")
    try:
        yield Path(tmp)
    finally:
        git("worktree", "remove", "--force", tmp, check=False)
        shutil.rmtree(tmp, ignore_errors=True)
        git("worktree", "prune", check=False)
