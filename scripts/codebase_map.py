#!/usr/bin/env python3
"""Codebase-map пульта: детерминированная карта модулей верхнего уровня.

Использование:
    python3 scripts/codebase_map.py
Корень дерева, которое картируется, — `git rev-parse --show-toplevel` от
cwd (SPEC 01M1SAA01YRRTWAVADT2F81RRQ, AC-4/AC-7), НЕ сам cwd: запуск из
подкаталога (например, изнутри `tasks/<id>/acceptance_tests/` — реальный
инцидент 05.09, где `scripts/codebase_map.py` запускался тестом планки
приёмки) кладёт карту в корень репозитория, а не рядом с cwd запуска.
В CI — корень пульта после checkout, тот же результат, что раньше давал
голый `Path.cwd()`.

Перебирает `orchestrator/*.py`, `scripts/*.py`, `tests/*.py` без захода во
вложенные директории. Разбор — статический (`ast`), файлы не исполняются
и не импортируются: содержимое чужого дерева — данные, не код для запуска.
Выход: `<cwd>/docs/codebase-map.md`. Код возврата: 0 — успех, иначе — сбой
(ADR-0003 3б: карта никогда не выдаётся за актуальную молча).
"""
import ast
import re
import subprocess
import sys
from pathlib import Path

MODULE_DIRS = ("orchestrator", "scripts", "tests")
OUTPUT_PATH = Path("docs") / "codebase-map.md"
NO_DOCSTRING_MARK = "нет docstring"


class ModuleInfo:
    def __init__(self, rel_path, purpose, public_functions, imports):
        self.rel_path = rel_path
        self.purpose = purpose
        self.public_functions = public_functions
        self.imports = imports  # dotted-имена, до резолюции в перечень


def discover_module_paths(root: Path) -> list:
    """Отсортированный список путей .py-модулей верхнего уровня перечня."""
    paths = []
    for directory in MODULE_DIRS:
        dir_path = root / directory
        if not dir_path.is_dir():
            continue
        paths.extend(sorted(dir_path.glob("*.py"), key=lambda p: p.name))
    return paths


def module_dotted_name(rel_path: Path) -> str:
    """Путь модуля -> dotted-имя для сопоставления с import-выражениями.

    `__init__.py` пакета называется именем директории (`orchestrator`),
    а не `orchestrator.__init__` — так на него ссылаются `import orchestrator`
    и `from . import config` внутри пакета.
    """
    package = rel_path.parts[0]
    if rel_path.stem == "__init__":
        return package
    return f"{package}.{rel_path.stem}"


def extract_purpose(tree: ast.Module) -> str:
    docstring = ast.get_docstring(tree)
    if not docstring:
        return NO_DOCSTRING_MARK
    first_line = docstring.strip().splitlines()[0].strip()
    return first_line or NO_DOCSTRING_MARK


def extract_public_functions(tree: ast.Module) -> list:
    """Публичные функции верхнего уровня — только `tree.body`, не
    `ast.walk`: методы классов и вложенные def'ы не входят в перечень."""
    names = [
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]
    return sorted(names)


def extract_imported_dotted_names(tree: ast.Module, package: str) -> set:
    """Dotted-имена, на которые модуль похоже ссылается импортом.

    `ast.walk`, не только `tree.body`: импорт бывает под `if`/`try`
    (см. orchestrator/artel.py). Уровень 1 (`from . import x`) —
    единственный вид относительного импорта, достижимый без захода
    в подпакеты, раз карта модулей сама не рекурсирует.
    """
    referenced = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                referenced.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if not node.module:
                    continue
                base = node.module
            elif node.level == 1:
                base = f"{package}.{node.module}" if node.module else package
            else:
                continue
            referenced.add(base)
            for alias in node.names:
                referenced.add(f"{base}.{alias.name}")
    return referenced


def parse_module(path: Path, root: Path) -> ModuleInfo:
    rel_path = path.relative_to(root)
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(rel_path))
    purpose = extract_purpose(tree)
    public_functions = extract_public_functions(tree)
    imports = extract_imported_dotted_names(tree, rel_path.parts[0])
    return ModuleInfo(rel_path, purpose, public_functions, imports)


def build_modules(root: Path) -> list:
    modules = [parse_module(p, root) for p in discover_module_paths(root)]
    dotted_to_module = {module_dotted_name(m.rel_path): m for m in modules}

    resolved_imports = {}
    imported_by = {m.rel_path.as_posix(): [] for m in modules}
    for module in modules:
        # `__init__.py` исключён как ЦЕЛЬ зависимости (SPEC T034, требование
        # 8, ревью T027): `from . import x, y` резолвит уровень-1 импорт без
        # имени (см. `extract_imported_dotted_names`) в том числе к голому
        # имени пакета — почти каждый модуль пакета попутно "импортирует"
        # __init__.py, и он же оказывается в «Импортируется» почти у всех.
        # Это шум формы, а не сигнал о зависимости от содержимого файла;
        # единственный код-потребитель карты (`orchestrator/brief.py`)
        # встраивает карту целиком и по этим спискам не ходит — исключение
        # им ничего не ломает.
        targets = sorted({
            dotted_to_module[d].rel_path.as_posix()
            for d in module.imports
            if d in dotted_to_module and dotted_to_module[d] is not module
            and dotted_to_module[d].rel_path.name != "__init__.py"
        })
        resolved_imports[module.rel_path.as_posix()] = targets
        for target in targets:
            imported_by[target].append(module.rel_path.as_posix())

    for key in imported_by:
        imported_by[key].sort()

    return modules, resolved_imports, imported_by


def map_stats(map_text: str) -> dict:
    """Статистика уже готового текста карты — чистая функция, без диска
    и git (01M1RFVWV6WWTXRC5F40K61632, требование 1, AC-1).

    Секция — тот же структурный разбор, что и сам формат `render()`:
    `## <путь>` до следующего `## ` или до конца текста. `bytes_by_dir`
    суммирует байты секций по каталогу верхнего уровня их пути;
    `top_sections` — пять самых крупных по убыванию размера.
    `bytes_projection` кладётся только если в модуле уже есть
    `project_for_brief` (AC-3) — на сегодня нет, ключ отсутствует
    целиком.
    """
    headers = re.findall(r"^## (.+)$", map_text, re.M)
    bytes_by_dir = {d: 0 for d in MODULE_DIRS}
    sizes = []
    search_start = 0
    for header in headers:
        marker = f"## {header}"
        start = map_text.index(marker, search_start)
        rest = map_text[start + len(marker):]
        next_marker = rest.find("\n## ")
        block = marker + (rest if next_marker == -1 else rest[:next_marker])
        size = len(block.encode("utf-8"))
        top_dir = header.split("/")[0]
        bytes_by_dir[top_dir] = bytes_by_dir.get(top_dir, 0) + size
        sizes.append((header, size))
        search_start = start + len(marker)

    top_sections = sorted(sizes, key=lambda item: -item[1])[:5]
    result = {
        "bytes_total": len(map_text.encode("utf-8")),
        "sections_total": len(headers),
        "bytes_by_dir": bytes_by_dir,
        "top_sections": [{"name": name, "bytes": size}
                         for name, size in top_sections],
    }
    project_for_brief = globals().get("project_for_brief")
    if project_for_brief is not None:
        result["bytes_projection"] = len(
            project_for_brief(map_text).encode("utf-8"))
    return result
_SECTION_START_RE = re.compile(r"(?m)^(?=## )")
_SECTION_FIELDS = ("purpose", "functions", "imports", "imported_by")
# Поля, оставляемые проекцией по виду секции (SPEC
# 01M1RFQ52S0VD22J628TXX96XS, требование 1, AC-2/AC-3) — единственное
# место правил проекции, таблица вместо регулярок по вызывающему коду.
_KEPT_FIELDS_BY_KIND = {
    "orchestrator": ("purpose", "functions", "imports"),
    "scripts": ("purpose", "functions", "imports"),
    "tests": ("purpose",),
}


def _section_kind(rel: str) -> str | None:
    top = rel.split("/", 1)[0]
    return top if top in _KEPT_FIELDS_BY_KIND else None


def _project_section(section: str) -> str:
    """Одна секция `## <путь>\\n\\n...` — блоки полей разделены пустой
    строкой в том же порядке, в котором их пишет `render` (Назначение,
    Публичные функции, Импортирует, Импортируется), без пустых строк
    внутри блока (список функций — подряд идущие `- \\`имя\\``) — деление
    по `\\n\\n` режет ровно по границам полей. `rstrip("\\n")` перед
    делением снимает разницу в хвостовых переводах строк последней секции
    файла (`render` завершает документ ровно одним `\\n`, а не секцию
    отдельно) — иначе он прилипал бы к значению последнего поля и терялся
    бы вместе с ним, когда это поле как раз отбрасывается проекцией."""
    parts = section.rstrip("\n").split("\n\n")
    heading, field_blocks = parts[0], parts[1:1 + len(_SECTION_FIELDS)]
    rel = heading[len("## "):].strip()
    kind = _section_kind(rel)
    if kind is None or len(field_blocks) < len(_SECTION_FIELDS):
        return section
    fields = dict(zip(_SECTION_FIELDS, field_blocks))
    kept = [heading] + [fields[name] for name in _KEPT_FIELDS_BY_KIND[kind]]
    return "\n\n".join(kept) + "\n\n"


def project_for_brief(map_text: str) -> str:
    """Облегчённая проекция карты для брифа роли (SPEC
    01M1RFQ52S0VD22J628TXX96XS, требование 1): чистая функция
    строка-в-строку, без чтения диска и без git — вызывающий код
    (`orchestrator/brief.py`) сам решает, какой текст ей передать (уже
    сверенный на свежесть/регенерированный).

    Шапка и порядок/заголовки секций не меняются (AC-4/AC-5). Для секций
    `orchestrator/*`/`scripts/*` остаются блоки «Назначение»/«Публичные
    функции»/«Импортирует», блок «Импортируется» удаляется (AC-2). Для
    секций `tests/*` остаются только заголовок секции и «Назначение»
    (AC-3). Идемпотентна (AC-7): секция короче четырёх полей (уже
    спроецированная) возвращается как есть, а не режется повторно."""
    chunks = _SECTION_START_RE.split(map_text)
    header, sections = chunks[0], chunks[1:]
    return header + "".join(_project_section(s) for s in sections)


def git_head_sha(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root,
        capture_output=True, text=True, check=True)
    return result.stdout.strip()


def repo_root(cwd: Path) -> Path:
    """Корень git-дерева, содержащего `cwd` (SPEC 01M1SAA01YRRTWAVADT2F81RRQ,
    AC-4/AC-7): `git rev-parse --show-toplevel`, не сам `cwd` — единственный
    способ узнать корень, не зависящий от того, на какой глубине подкаталога
    запущен генератор."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=cwd,
        capture_output=True, text=True, check=True)
    return Path(result.stdout.strip()).resolve()


def render(modules, resolved_imports, imported_by, sha: str) -> str:
    lines = ["---", f"built_at_sha: {sha}", "---", "",
             "# Codebase-map пульта", "",
             "Автосгенерировано `scripts/codebase_map.py` — правки руками "
             "теряются при следующем запуске.", ""]

    for module in modules:
        rel = module.rel_path.as_posix()
        lines.append(f"## {rel}")
        lines.append("")
        lines.append(f"**Назначение:** {module.purpose}")
        lines.append("")
        if module.public_functions:
            lines.append("**Публичные функции:**")
            for name in module.public_functions:
                lines.append(f"- `{name}`")
        else:
            lines.append("**Публичные функции:** (нет)")
        lines.append("")

        imports_of = resolved_imports[rel]
        lines.append("**Импортирует:** " +
                     (", ".join(f"`{m}`" for m in imports_of) or "—"))
        lines.append("")

        importers = imported_by[rel]
        lines.append("**Импортируется:** " +
                     (", ".join(f"`{m}`" for m in importers) or "—"))
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def main() -> int:
    root = repo_root(Path.cwd())
    sha = git_head_sha(root)
    modules, resolved_imports, imported_by = build_modules(root)
    text = render(modules, resolved_imports, imported_by, sha)

    output_path = root / OUTPUT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
