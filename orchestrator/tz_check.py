"""Механическая проверка содержания ТЗ в `new` по дереву проекта (SPEC
01M598KY8V2P2GRD5Q67DRAZNA): ссылки `файл:строка` и вызывающие вне зон.

Форма ТЗ (пути и зоны, «Порядок:», «Проект:») проверяется в
`catalog.cmd_new` до этого модуля; здесь — содержание, сверенное с
деревом проверки: у внешнего проекта — `origin/<base>` его клона без
подтяжки, у артели — HEAD главной копии (требование 2). Разбор синтаксиса
и индекс вызовов не строятся: вызывающие ищутся `git grep` по слову,
ложные срабатывания допустимы — это предупреждение, не отказ.
"""
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from scripts import guard

from . import config, gitcmd, repo_context, workspace

# Действие записи журнала задачи (требование 3): читатель журнала находит
# запись по действию, не по вариативному detail.
ACTION = "проверка ТЗ"
AMBIGUOUS = "имя файла неоднозначно — не проверено"
COMMON_MARK = "общее имя — не проверено"
TREE_UNAVAILABLE = "дерево недоступно — проверка ТЗ не выполнена"
CALLERS_HINT = "назови в Зонах, в „Не входит“ или в „Только чтение“"

# Требование 5.3: такие имена дают слишком много совпадений, чтобы поиск
# по слову что-то значил.
COMMON_NAMES = frozenset(("run", "main", "load", "get", "set", "check",
                          "parse", "cmd", "new"))
MIN_NAME_LEN = 4
CALLERS_LIMIT = 20
WINDOW = 3
# Требование 4.4: последняя часть содержимого кавычек с таким расширением —
# путь, не имя, даже если файла в дереве нет.
PATH_EXTENSIONS = frozenset(("py", "md", "yaml", "yml", "json", "toml", "txt",
                             "sh", "js", "jsx", "ts", "tsx", "cfg", "ini",
                             "lock"))

# Грамматика ссылки (требование 4): путь из `[A-Za-z0-9_./-]`, последняя
# часть — с расширением; слева — не середина пути, справа — не цифра.
# `host/api:8080` и `origin/main:12` (без расширения) ссылками не являются.
REF_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])"
    r"((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]*\.[A-Za-z0-9]+)"
    r":(\d+)(?:-(\d+))?(?!\d)")
BACKTICK_RE = re.compile(r"`([^`\n]+)`")
_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
NAME_RE = re.compile(rf"{_IDENT}(?:\.{_IDENT})*")
DOTTED_RE = re.compile(rf"{_IDENT}(?:\.{_IDENT})+")
DEF_RE = re.compile(r"^([ \t]*)(?:async[ \t]+)?(?:def|class)[ \t]+(" + _IDENT
                    + r")")


@dataclass
class Report:
    """Находки проверки: `sha` — коммит проверенного дерева (пусто —
    дерево недоступно), `marks` — пометки «общее имя», вне счёта
    предупреждений и вне `--strict-tz` (требование 5.3)."""
    sha: str = ""
    refusals: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    marks: list = field(default_factory=list)

    def empty(self) -> bool:
        return not (self.refusals or self.warnings or self.marks)

    def lines(self) -> list:
        """Строки вывода: заголовок со счётом и sha, затем находки."""
        header = (f"проверка ТЗ: {_count(len(self.refusals), 'отказ', 'отказа', 'отказов')}, "
                  f"{_count(len(self.warnings), 'предупреждение', 'предупреждения', 'предупреждений')}")
        if self.sha:
            header += f", дерево {self.sha}"
        return ([header] + [f"  отказ: {r}" for r in self.refusals]
                + [f"  предупреждение: {w}" for w in self.warnings]
                + [f"  {m}" for m in self.marks])


def _count(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        word = one
    elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        word = few
    else:
        word = many
    return f"{n} {word}"


@dataclass(frozen=True)
class _Ref:
    text: str
    path: str
    first: int
    last: int
    line_no: int
    start: int
    end: int


class _TreeError(Exception):
    """Дерево проверки недоступно; текст — причина для предупреждения."""


class _Tree:
    """Дерево проверки одного коммита: список файлов, содержимое, поиск."""

    def __init__(self, repo: Path, sha: str):
        self.repo = repo
        self.sha = sha
        out = _git_ok(repo, "ls-tree", "-r", "-z", "--name-only", sha)
        self.files = [p for p in out.decode("utf-8", "replace").split("\0")
                      if p]
        self.file_set = set(self.files)
        self.by_name: dict = {}
        for path in self.files:
            self.by_name.setdefault(path.rsplit("/", 1)[-1], []).append(path)
        self.extensions = {name.rsplit(".", 1)[1] for name in self.by_name
                           if "." in name}
        self._blobs: dict = {}

    def blob(self, path: str) -> bytes:
        if path not in self._blobs:
            self._blobs[path] = _git_ok(self.repo, "show",
                                        f"{self.sha}:{path}")
        return self._blobs[path]

    def grep_word(self, name: str) -> list:
        """(путь, строка, текст) строк `*.py` дерева со словом `name`."""
        res = _git(self.repo, "grep", "-n", "-w", "-F", "-e", name,
                   self.sha, "--", "*.py")
        if res.returncode == 1:
            return []
        if res.returncode != 0:
            raise _TreeError(f"git grep: {_stderr(res)}")
        found = []
        prefix = f"{self.sha}:"
        for raw in res.stdout.decode("utf-8", "replace").splitlines():
            if raw.startswith(prefix):
                raw = raw[len(prefix):]
            parts = raw.split(":", 2)
            if len(parts) == 3 and parts[1].isdigit():
                found.append((parts[0], int(parts[1]), parts[2]))
        return found


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """git в `repo` с выводом байтами: содержимое файла дерева может быть
    не текстом, а `gitcmd.git` декодирует вывод строго."""
    try:
        return gitcmd.read(repo, *args)
    except OSError as exc:
        return subprocess.CompletedProcess(args, 127, b"", str(exc).encode())


def _stderr(res) -> str:
    err = res.stderr
    if isinstance(err, bytes):
        err = err.decode("utf-8", "replace")
    return (err or "").strip() or f"код {res.returncode}"


def _git_ok(repo: Path, *args: str) -> bytes:
    res = _git(repo, *args)
    if res.returncode != 0:
        raise _TreeError(f"git {args[0]}: {_stderr(res)}")
    return res.stdout


def _open_tree(target: str) -> _Tree:
    """Дерево проверки проекта `target` (требование 2) без `fetch`."""
    if repo_context.is_artel(target):
        repo = config.ROOT
        # Корень, лежащий внутри чужого репозитория, git принял бы за его
        # часть — главная копия обязана быть репозиторием сама.
        if not (repo / ".git").exists():
            raise _TreeError(f"главная копия {repo} — не git-репозиторий")
        rev = "HEAD"
    else:
        ctx = repo_context.resolve(target)
        if ctx is None:
            raise _TreeError(repo_context.unresolved_reason(target))
        repo = workspace.repo(target)
        rev = f"origin/{ctx.base}"
    res = _git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}")
    sha = res.stdout.decode("utf-8", "replace").strip()
    if res.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise _TreeError(f"в {repo} нет {rev}")
    return _Tree(repo, sha)


def _refs(text: str) -> list:
    refs = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for m in REF_RE.finditer(line):
            first = int(m.group(2))
            last = int(m.group(3)) if m.group(3) else first
            refs.append(_Ref(m.group(0), m.group(1), first, last, line_no,
                             m.start(), m.end()))
    return refs


def _static_path(content: str) -> bool:
    """Путь по требованию 4.4 без дерева: `/` или расширение из списка."""
    return "/" in content or (
        "." in content and content.rsplit(".", 1)[1] in PATH_EXTENSIONS)


def _is_path(content: str, tree: _Tree) -> bool:
    if _static_path(content):
        return True
    if "." in content and content.rsplit(".", 1)[1] in tree.extensions:
        return True
    return content in tree.by_name or content in tree.file_set


def _dotted_names(text: str) -> list:
    """`модуль.функция`/`Класс.метод` в обратных кавычках, не пути."""
    return [m.group(1) for m in BACKTICK_RE.finditer(text)
            if DOTTED_RE.fullmatch(m.group(1)) and not _static_path(m.group(1))]


def check(tz_raw: str, candidate_text: str, target: str, zones,
          declared_text: str) -> Report | None:
    """Находки ТЗ `tz_raw` по дереву проекта `target`; `None` — в ТЗ нет ни
    ссылок, ни кандидатов, дерево не открывалось (требование 2.4).

    `candidate_text` — текст ТЗ до первой строки-метки (требование 5.1),
    `zones`/`declared_text` — элементы «Зоны:» и тела объявляющих
    разделов: по ним вызывающий считается покрытым (требование 5.4)."""
    refs = _refs(tz_raw)
    candidate_refs = _refs(candidate_text)
    named = _dotted_names(candidate_text)
    if not refs and not named:
        return None
    report = Report()
    try:
        tree = _open_tree(target)
        report.sha = tree.sha
        _check_refs(tree, tz_raw, refs, report)
        candidates = [n.rsplit(".", 1)[1] for n in named
                      if not _is_path(n, tree)]
        candidates += _ref_candidates(tree, candidate_refs)
        _check_callers(tree, list(dict.fromkeys(candidates)), zones,
                       declared_text, report)
    except _TreeError as exc:
        return Report(warnings=[f"{TREE_UNAVAILABLE}: {exc}"])
    return report


def _resolve(tree: _Tree, ref: _Ref, report: Report) -> str | None:
    """Путь файла ссылки в дереве; `None` — ссылка дальше не проверяется."""
    if "/" in ref.path:
        return ref.path
    found = tree.by_name.get(ref.path, [])
    if len(found) > 1:
        report.warnings.append(f"`{ref.text}` — {AMBIGUOUS} "
                               f"(в дереве {len(found)} раз)")
        return None
    return found[0] if found else None


def _line_count(blob: bytes) -> int:
    return blob.count(b"\n") + (1 if blob and not blob.endswith(b"\n") else 0)


def _check_refs(tree: _Tree, tz_raw: str, refs: list, report: Report) -> None:
    """Существование файла, длина и «имя рядом» (требования 4.1-4.3)."""
    lines = tz_raw.splitlines()
    seen_refusals = set()
    for index, ref in enumerate(refs):
        if "/" not in ref.path and ref.path not in tree.by_name:
            continue
        path = _resolve(tree, ref, report)
        if path is None:
            continue
        if path not in tree.file_set:
            refusal = f"`{ref.text}` — файла {path} нет в дереве"
        else:
            blob = tree.blob(path)
            length = _line_count(blob)
            if max(ref.first, ref.last) <= length and min(ref.first, ref.last) >= 1:
                _check_near_name(tree, path, blob, ref, refs[index + 1:],
                                 lines[ref.line_no - 1], report)
                continue
            refusal = (f"`{ref.text}` — строка за концом файла {path} "
                       f"({length} строк)")
        if refusal not in seen_refusals:
            seen_refusals.add(refusal)
            report.refusals.append(refusal)


def _check_near_name(tree: _Tree, path: str, blob: bytes, ref: _Ref,
                     later: list, line: str, report: Report) -> None:
    """Первое имя в кавычках после ссылки до следующей ссылки строки — в
    окне ±3 строк файла (требование 4.3); нетекстовый файл не сверяется."""
    if b"\0" in blob:
        return
    stop = next((r.start for r in later if r.line_no == ref.line_no),
                len(line))
    name = None
    for m in BACKTICK_RE.finditer(line):
        if m.start() < ref.end or m.start() >= stop:
            continue
        content = m.group(1)
        if content.endswith("()"):
            content = content[:-2]
        if NAME_RE.fullmatch(content) and not _is_path(content, tree):
            name = content
            break
    if name is None:
        return
    word = name.rsplit(".", 1)[-1]
    file_lines = blob.decode("utf-8", "replace").splitlines()
    lo = max(1, min(ref.first, ref.last) - WINDOW)
    hi = min(len(file_lines), max(ref.first, ref.last) + WINDOW)
    pattern = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(word)
                         + r"(?![A-Za-z0-9_])")
    if any(pattern.search(file_lines[i - 1]) for i in range(lo, hi + 1)):
        return
    report.warnings.append(f"`{name}` рядом со ссылкой `{ref.text}` — "
                           f"нет в строках {lo}-{hi} файла {path}")


def _indent(text: str) -> int:
    return len(text) - len(text.lstrip(" \t"))


def _enclosing(lines: list, number: int) -> str | None:
    """Ближайшее выше строки `number` определение с меньшим отступом;
    у строки уровня модуля — `None` (требование 5.1). Пустая строка
    берёт отступ следующей непустой."""
    probe = number
    while probe <= len(lines) and not lines[probe - 1].strip():
        probe += 1
    if probe > len(lines):
        return None
    indent = _indent(lines[probe - 1])
    if indent == 0:
        return None
    for i in range(number - 1, 0, -1):
        m = DEF_RE.match(lines[i - 1])
        if m and len(m.group(1)) < indent:
            return m.group(2)
    return None


def _ref_candidates(tree: _Tree, refs: list) -> list:
    """Определения, на которые указывают ссылки `файл.py:строка`."""
    names = []
    for ref in refs:
        if "/" in ref.path:
            path = ref.path
        else:
            found = tree.by_name.get(ref.path, [])
            path = found[0] if len(found) == 1 else None
        if not path or not path.endswith(".py") or path not in tree.file_set:
            continue
        lines = tree.blob(path).decode("utf-8", "replace").splitlines()
        first, last = sorted((ref.first, ref.last))
        if first < 1 or last > len(lines):
            continue
        if first == last:
            m = DEF_RE.match(lines[first - 1])
            name = m.group(2) if m else _enclosing(lines, first)
            if name:
                names.append(name)
            continue
        names += [m.group(2) for m in (DEF_RE.match(lines[i - 1])
                                       for i in range(first, last + 1)) if m]
        enclosing = _enclosing(lines, first)
        if enclosing:
            names.append(enclosing)
    return names


def _is_call(name: str, text: str) -> bool:
    word = re.escape(name)
    if re.match(r"\s*(?:async\s+)?(?:def|class)\s+" + word + r"\b", text):
        return False
    return re.search(r"(?<![A-Za-z0-9_])" + word + r"\s*\(", text) is not None \
        or re.search(r"\." + word + r"(?![A-Za-z0-9_])", text) is not None


def _check_callers(tree: _Tree, names: list, zones, declared_text: str,
                   report: Report) -> None:
    """Вызывающие кандидатов вне зон (требования 5.2-5.4)."""
    zone_set = set(zones)
    declared = guard._path_mention_candidates(declared_text)
    for name in names:
        if len(name) < MIN_NAME_LEN or name in COMMON_NAMES:
            report.marks.append(f"{COMMON_MARK}: `{name}`")
            continue
        places = [f"{path}:{number}"
                  for path, number, text in tree.grep_word(name)
                  if not path.startswith("tests/") and _is_call(name, text)
                  and not guard._classified(path, zone_set, declared)]
        if not places:
            continue
        listed = ", ".join(f"`{p}`" for p in places[:CALLERS_LIMIT])
        rest = len(places) - CALLERS_LIMIT
        if rest > 0:
            listed += f" и ещё {rest}"
        report.warnings.append(f"в зонах нет вызывающих `{name}`: {listed} — "
                               f"{CALLERS_HINT}")
