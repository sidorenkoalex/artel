#!/usr/bin/env python3
"""Справочник ядра проекта: «как пользоваться» модулями коммита, разбором `ast`.

Использование:
    python3 scripts/core_reference.py <корень дерева> <модуль>...
        [--constants-module <модуль> --constants <ИМЯ>...]
        [--min-uses N] [--sha <метка>]
печатает справочник по файлам диска в stdout и ничего не пишет на диск
(режим для деревьев Оператора). Пульт зовёт `build` из
`orchestrator/reference_cache.py` по исходникам коммита из git-объектов
(SPEC 01M4S24963R9H18AN2XDP6R15B, К-3а; ADR-0003 п.3а, п.3б).

Код проекта только разбирается (`ast`) — не импортируется и не
исполняется: чужое дерево — данные. Генератор импортирует только
стандартную библиотеку и не читает `config` пульта: порог использования,
sha источника и `generator_sha256` приходят параметрами. Выход
детерминирован: файлы обходятся в посимвольном порядке путей, порядок
ключей `sources` и зерно хэширования строк на текст не влияют.
"""
import argparse
import ast
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
import tokenize
import unicodedata
import warnings
from dataclasses import dataclass
from pathlib import Path

# Умолчание `--min-uses` повторяет `config.CORE_REFERENCE_MIN_USES`:
# генератор модулей пульта не импортирует (требование 1).
DEFAULT_MIN_USES = 3
DEFAULT_SHA = "рабочее дерево"

DOC_MAX = 100
EXAMPLE_MAX = 80
VALUE_MAX = 400
NOTE_MAX = 160
ELLIPSIS = "…"

TITLE = "# Справочник ядра"
ROLE_LINE = ("Для роли: справочник описывает код коммита built_at_sha — правки "
             "задачи после него здесь не отражены; полный текст модуля — в "
             "рабочем каталоге.")
NO_NOTE = "без пояснения"
NOT_IN_COMMIT = "нет в коммите"

# Исключения разбора, не роняющие сборку (требование 2): `ValueError`
# покрывает и нулевой байт, и `UnicodeEncodeError` одиночного суррогата.
PARSE_ERRORS = (SyntaxError, ValueError, RecursionError, MemoryError)

# Каталоги, не входящие в набор файлов командной строки без git.
EXCLUDED_DIRS = ("__pycache__", "node_modules", "venv")

# Концы строк — как у разбора `ast`: смещения узлов считаются по ним.
LINE_END = re.compile(r"\r\n|\r|\n")
SENTENCE_END = re.compile(r"[.:;](?=\s)")


class DeadlineExceeded(Exception):
    """Общий срок сборки исчерпан во время разбора."""


@dataclass(frozen=True)
class Report:
    """Итог сборки: текст справочника, число записей и сбои для алерта
    (тексты сбоев без sha, времени и размеров — требование 7)."""
    text: str
    records: int
    problems: tuple


@dataclass
class _File:
    path: str
    text: str
    tree: ast.Module
    lines: list


def build(sources: dict, setting: dict, sha: str, *, min_uses: int,
          generator_sha256: str, unparsed: int = 0, skipped: int = 0,
          deadline: float | None = None) -> str:
    """Текст справочника по набору исходников «путь → текст»."""
    return build_report(sources, setting, sha, min_uses=min_uses,
                        generator_sha256=generator_sha256, unparsed=unparsed,
                        skipped=skipped, deadline=deadline).text


def build_report(sources: dict, setting: dict, sha: str, *, min_uses: int,
                 generator_sha256: str, unparsed: int = 0, skipped: int = 0,
                 deadline: float | None = None) -> Report:
    """Сборка справочника с числом записей и сбоями.

    `unparsed`/`skipped` — файлы, отсеянные до `build` (не UTF-8; ссылки,
    подмодули, крупные и отсутствующие blob): входят в числа шапки.
    `deadline` — момент `time.monotonic()`, после которого разбор
    прерывается `DeadlineExceeded`."""
    files = {}
    for path in sorted(sources):
        text = sources[path]
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tree = ast.parse(text, filename=path)
        except PARSE_ERRORS:
            unparsed += 1
            tree = None
        _check_deadline(deadline)
        if tree is not None:
            files[path] = _File(path, text, tree, LINE_END.split(text))
    modules = list(setting["modules"])
    stems = {_stem(module) for module in modules}
    uses = {}
    for path, item in files.items():
        uses[path] = _usage(item.tree, stems)
        _check_deadline(deadline)

    body, records, problems = [], 0, []
    calls = None
    for module in modules:
        item = files.get(module)
        if module not in sources:
            body.append(f"## {module} — модуль отсутствует в коммите")
            problems.append(f"справочник ядра: модуль {module} не найден в коммите")
        elif item is None:
            body.append(f"## {module} — модуль не разобран")
            problems.append(f"справочник ядра: модуль {module} не разобран")
        else:
            if calls is None:
                calls = _all_calls(files, stems, deadline)
            lines, count = _module_section(item, files, uses, calls, min_uses)
            body += lines
            records += count
        if module == setting.get("constants_module"):
            lines, count, missing = _constants_section(
                item, setting.get("constants") or [])
            body += lines
            records += count
            problems += [f"справочник ядра: константа {name} не найдена в "
                         f"модуле {module}" for name in missing]
        body.append("")
    body_text = _clean("\n".join(body).rstrip("\n") + "\n")
    header = _header(sha, generator_sha256, setting, min_uses, unparsed,
                     skipped, body_text)
    return Report(header + "\n\n" + body_text, records,
                  tuple(_clean(problem) for problem in problems))


# --- шапка и сверка ---------------------------------------------------------

def setting_fields(setting: dict, min_uses: int) -> dict:
    """Настройка в шапке: одна строка на поле, значения — JSON."""
    return {
        "modules": _one_line(json.dumps(list(setting["modules"]),
                                        ensure_ascii=False)),
        "constants_module": _one_line(json.dumps(
            setting.get("constants_module"), ensure_ascii=False)),
        "constants": _one_line(json.dumps(list(setting.get("constants") or []),
                                          ensure_ascii=False)),
        "CORE_REFERENCE_MIN_USES": str(min_uses),
    }


def _header(sha, generator_sha256, setting, min_uses, unparsed, skipped,
            body_text) -> str:
    lines = [TITLE,
             f"built_at_sha: {_one_line(str(sha))}",
             f"generator_sha256: {_one_line(str(generator_sha256))}"]
    lines += [f"{key}: {value}"
              for key, value in setting_fields(setting, min_uses).items()]
    lines += [f"unparsed_files: {unparsed}",
              f"skipped_files: {skipped}",
              f"body_sha256: {_digest(body_text)}",
              ROLE_LINE]
    return "\n".join(lines)


def header_fields(text: str) -> tuple[dict, str] | None:
    """Поля шапки и тело справочника из одного текста; None — не справочник."""
    header, sep, body = text.partition("\n\n")
    lines = header.split("\n")
    if not sep or lines[0] != TITLE:
        return None
    fields = {}
    for line in lines[1:]:
        key, colon, value = line.partition(": ")
        if colon and key not in fields:
            fields[key] = value
    return fields, body


def reference_sha(text: str, setting: dict, *, min_uses: int,
                  generator_sha256: str) -> str | None:
    """`built_at_sha` справочника, годного для этой настройки и генератора
    (настройка, генератор и sha256 тела совпадают); None — не годен."""
    parsed = header_fields(text)
    if parsed is None:
        return None
    fields, body = parsed
    if fields.get("generator_sha256") != generator_sha256:
        return None
    for key, value in setting_fields(setting, min_uses).items():
        if fields.get(key) != value:
            return None
    if fields.get("body_sha256") != _digest(body):
        return None
    return fields.get("built_at_sha")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


# --- использование и примеры ------------------------------------------------

def _stem(module: str) -> str:
    name = module.rsplit("/", 1)[-1]
    return name[:-3] if name.endswith(".py") else name


def _tail(node: ast.AST) -> str | None:
    """Последнее имя выражения `a.b.core` / `core`; None — не имя."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _usage(tree: ast.Module, stems: set) -> tuple[set, set]:
    """Обращения файла к модулям настройки: (`<модуль>.<имя>`, `from …
    <модуль> import <имя>`), пары (модуль, имя)."""
    attrs, imported = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            stem = _tail(node.value)
            if stem in stems:
                attrs.add((stem, node.attr))
        elif isinstance(node, ast.ImportFrom) and node.module:
            stem = node.module.rsplit(".", 1)[-1]
            if stem in stems:
                imported.update((stem, alias.name) for alias in node.names)
    return attrs, imported


def _all_calls(files: dict, stems: set, deadline) -> dict:
    """Однострочные вызовы не длиннее `EXAMPLE_MAX` по файлам: ключ —
    ("attr", модуль, имя) или ("name", имя), значение — (строка, столбец,
    текст) в порядке строк."""
    found = {}
    for path, item in files.items():
        per_file = {}
        for node in ast.walk(item.tree):
            if not isinstance(node, ast.Call) or node.lineno != node.end_lineno:
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and _tail(func.value) in stems:
                key = ("attr", _tail(func.value), func.attr)
            elif isinstance(func, ast.Name):
                key = ("name", func.id)
            else:
                continue
            text = _segment(item.lines, node)
            if text is None or len(text) > EXAMPLE_MAX:
                continue
            per_file.setdefault(key, []).append((node.lineno, node.col_offset, text))
        found[path] = {key: sorted(values) for key, values in per_file.items()}
        _check_deadline(deadline)
    return found


def _example(module: str, name: str, files: dict, uses: dict, calls: dict) -> str:
    """Пример вызова: `<модуль>.<имя>(` в любом файле → `<имя>(` в файле,
    импортирующем имя из модуля → `<имя>(` в самом модуле (требование 2г)."""
    stem = _stem(module)
    stages = (
        (("attr", stem, name), lambda path: True),
        (("name", name),
         lambda path: path != module and (stem, name) in uses[path][1]),
        (("name", name), lambda path: path == module),
    )
    for key, admits in stages:
        for path in sorted(files):
            hits = calls.get(path, {}).get(key)
            if hits and admits(path):
                return hits[0][2]
    return ""


def _users(module: str, name: str, uses: dict) -> int:
    stem = _stem(module)
    return sum(1 for path, (attrs, imported) in uses.items()
               if path != module and ((stem, name) in attrs
                                      or (stem, name) in imported))


# --- разделы ----------------------------------------------------------------

def _module_section(item: _File, files, uses, calls, min_uses) -> tuple[list, int]:
    doc = _doc_line(item.tree) or "без docstring"
    lines = [f"## {item.path} — {doc}"]
    definitions = {}
    for node in item.tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions.pop(node.name, None)
            definitions[node.name] = node
    count = 0
    for name, node in sorted(definitions.items(), key=lambda kv: kv[1].lineno):
        if name.startswith("_") or _users(item.path, name, uses) < min_uses:
            continue
        if isinstance(node, ast.ClassDef):
            lines.append(_class_line(item, node))
        else:
            lines.append(_function_line(item, node, files, uses, calls))
        count += 1
    if not count:
        lines.append("- публичных функций и классов с использованием от порога нет")
    return lines, count


def _function_line(item: _File, node, files, uses, calls) -> str:
    line = f"- `{_signature(item, node)}`"
    doc = _doc_line(node)
    if doc:
        line += f" — {doc}"
    example = _example(item.path, node.name, files, uses, calls)
    if example:
        line += f" — пример: `{example}`"
    return line


def _class_line(item: _File, node: ast.ClassDef) -> str:
    bases = ", ".join(_expr(item, base) for base in node.bases)
    methods = []
    for child in node.body:
        if (isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not child.name.startswith("_") and child.name not in methods):
            methods.append(child.name)
    head = f"class {node.name}({bases})" if bases else f"class {node.name}"
    return f"- `{head}` — методы: {', '.join(methods) or 'публичных нет'}"


def _signature(item: _File, node) -> str:
    args = node.args
    positional = args.posonlyargs + args.args
    first_default = len(positional) - len(args.defaults)
    parts = []
    for index, arg in enumerate(positional):
        default = (args.defaults[index - first_default]
                   if index >= first_default else None)
        parts.append(_param(item, arg, default))
        if args.posonlyargs and index == len(args.posonlyargs) - 1:
            parts.append("/")
    if args.vararg:
        parts.append("*" + _param(item, args.vararg, None))
    elif args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        parts.append(_param(item, arg, default))
    if args.kwarg:
        parts.append("**" + _param(item, args.kwarg, None))
    text = f"{node.name}({', '.join(parts)})"
    if node.returns is not None:
        text += f" -> {_expr(item, node.returns)}"
    if isinstance(node, ast.AsyncFunctionDef):
        text = "async " + text
    return text


def _param(item: _File, arg: ast.arg, default) -> str:
    text = arg.arg
    if arg.annotation is not None:
        text += f": {_expr(item, arg.annotation)}"
        if default is not None:
            text += f" = {_expr(item, default)}"
    elif default is not None:
        text += f"={_expr(item, default)}"
    return text


def _constants_section(item: _File | None, names: list) -> tuple[list, int, list]:
    """Константы перечня из модуля констант: (строки, число записей, не
    найденные имена). Модуль не разобран — имена не ищутся и не считаются
    ненайденными: причина уже в строке раздела."""
    if not names:
        return [], 0, []
    lines = ["Константы:"]
    if item is None:
        lines += [f"- `{name}` — модуль констант недоступен" for name in names]
        return lines, 0, []
    assigned = {}
    for node in item.tree.body:
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif (isinstance(node, ast.AnnAssign) and node.value is not None
              and isinstance(node.target, ast.Name)):
            targets = [node.target.id]
        else:
            continue
        for target in targets:
            assigned[target] = node
    own, inline = _comments(item.text)
    count, missing = 0, []
    for name in names:
        node = assigned.get(name)
        if node is None:
            lines.append(f"- `{name}` — {NOT_IN_COMMIT}")
            missing.append(name)
            continue
        value = _cut(_expr(item, node.value), VALUE_MAX)
        note = _note(node, own, inline) or NO_NOTE
        lines.append(f"- `{name}` = {value} — {note}")
        count += 1
    return lines, count, missing


def _comments(text: str) -> tuple[dict, dict]:
    """Комментарии модуля по строкам: (комментарий — вся строка,
    комментарий после кода)."""
    own, inline = {}, {}
    try:
        for token in tokenize.generate_tokens(io.StringIO(text, newline=None).readline):
            if token.type != tokenize.COMMENT:
                continue
            row, col = token.start
            body = token.string[1:].strip()
            if token.line[:col].strip():
                inline[row] = body
            else:
                own[row] = body
    except (tokenize.TokenError, SyntaxError, ValueError):
        pass
    return own, inline


def _note(node: ast.AST, own: dict, inline: dict) -> str:
    """Пояснение константы: комментарий в строке присваивания, иначе
    первое предложение сплошного блока комментариев над ним.

    «Строка присваивания» — первая: у многострочного значения комментарий
    последней строки поясняет последний элемент, а не константу."""
    if inline.get(node.lineno):
        return _cut(inline[node.lineno], NOTE_MAX)
    block = []
    row = node.lineno - 1
    while row in own:
        block.insert(0, own[row])
        row -= 1
    text = " ".join(part for part in block if part)
    match = SENTENCE_END.search(text)
    if match:
        text = text[:match.start()]
    return _cut(text.strip(), NOTE_MAX)


# --- текст ------------------------------------------------------------------

def _doc_line(node: ast.AST) -> str:
    """Первая непустая строка docstring (деление только по `\\n`), не
    длиннее `DOC_MAX`."""
    try:
        doc = ast.get_docstring(node, clean=False)
    except TypeError:
        return ""
    for line in (doc or "").split("\n"):
        if line.strip():
            return _cut(line.strip(), DOC_MAX)
    return ""


def _segment(lines: list, node: ast.AST) -> str | None:
    """Текст узла как в коде (смещения `ast` — в байтах UTF-8)."""
    first, last = node.lineno - 1, (node.end_lineno or node.lineno) - 1
    start, end = node.col_offset, node.end_col_offset
    if end is None or last >= len(lines):
        return None
    if first == last:
        return _bytes_slice(lines[first], start, end)
    return (_bytes_slice(lines[first], start, None) + "\n"
            + "\n".join(lines[first + 1:last]) + ("\n" if last > first + 1 else "")
            + _bytes_slice(lines[last], 0, end))


def _bytes_slice(line: str, start, end) -> str:
    return line.encode("utf-8", "surrogatepass")[start:end].decode(
        "utf-8", "replace")


def _expr(item: _File, node: ast.AST) -> str:
    """Выражение одной строкой как в коде (пробелы схлопнуты, комментарии
    многострочного выражения вырезаны — в одной строке они съели бы хвост)."""
    text = _segment(item.lines, node)
    if text is None:
        try:
            text = ast.unparse(node)
        except (RecursionError, ValueError, AttributeError):
            text = "…"
    elif "\n" in text and "#" in text:
        text = _drop_comments(text)
    return " ".join(text.split())


def _drop_comments(text: str) -> str:
    lines = text.split("\n")
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError, ValueError):
        return text
    for token in reversed(tokens):
        if token.type == tokenize.COMMENT:
            row, start = token.start
            end = token.end[1]
            line = lines[row - 1]
            lines[row - 1] = line[:start] + line[end:]
    return "\n".join(lines)


def _cut(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit - 1] + ELLIPSIS


def _clean(text: str) -> str:
    """Символы категории Cc (кроме `\\n`) — пробел (требование 2)."""
    return "".join(" " if ch != "\n" and unicodedata.category(ch) == "Cc" else ch
                   for ch in text)


def _one_line(text: str) -> str:
    return _clean(text).replace("\n", " ")


def _check_deadline(deadline) -> None:
    if deadline is not None and time.monotonic() > deadline:
        raise DeadlineExceeded("общий срок сборки справочника исчерпан во время разбора")


# --- командная строка -------------------------------------------------------

def disk_sources(root: Path) -> tuple[dict, int, int]:
    """Исходники дерева диска: (путь → текст, не UTF-8, пропущенные).

    В git-дереве — обычные `.py` из `git ls-files` (символьная ссылка
    пропускается и считается); без git — `.py` вне каталогов с ведущей
    точкой, `__pycache__`, `node_modules`, `venv`."""
    listed = _git_listed(root)
    if listed is None:
        listed = []
        for current, dirs, names in os.walk(root):
            dirs[:] = sorted(d for d in dirs
                             if not d.startswith(".") and d not in EXCLUDED_DIRS)
            rel_dir = Path(current).relative_to(root)
            listed += [(rel_dir / name).as_posix() for name in names]
    sources, unparsed, skipped = {}, 0, 0
    for rel in sorted(set(listed)):
        if not rel.endswith(".py"):
            continue
        path = root / rel
        if path.is_symlink() or not path.is_file():
            skipped += 1
            continue
        try:
            sources[rel] = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            unparsed += 1
        except OSError:
            skipped += 1
    return sources, unparsed, skipped


def _git_listed(root: Path) -> list | None:
    try:
        res = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                             capture_output=True)
    except OSError:
        return None
    if res.returncode != 0:
        return None
    return [name for name in res.stdout.decode("utf-8", "surrogateescape").split("\0")
            if name]


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Справочник ядра по файлам дерева диска — в stdout.")
    parser.add_argument("root", help="корень дерева")
    parser.add_argument("modules", nargs="+", help="модули настройки")
    parser.add_argument("--constants-module", help="модуль констант")
    parser.add_argument("--constants", nargs="+", help="имена констант")
    parser.add_argument("--min-uses", type=int, default=DEFAULT_MIN_USES,
                        help=f"порог использования (умолчание {DEFAULT_MIN_USES})")
    parser.add_argument("--sha", default=DEFAULT_SHA, help="метка источника")
    args = parser.parse_args(argv)
    if bool(args.constants_module) != bool(args.constants):
        parser.error("--constants-module и --constants задаются вместе")
    setting = {"modules": args.modules}
    if args.constants_module:
        setting["constants_module"] = args.constants_module
        setting["constants"] = args.constants
    generator = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    sources, unparsed, skipped = disk_sources(Path(args.root))
    text = build(sources, setting, args.sha, min_uses=args.min_uses,
                 generator_sha256=generator, unparsed=unparsed, skipped=skipped)
    sys.stdout.buffer.write(text.encode("utf-8", "replace"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
