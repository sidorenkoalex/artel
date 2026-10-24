"""Общий разбор планки волны 3м-1 сведения тестов: тесты замка и очереди
мержа из `tests/test_merge_lock.py`, `tests/test_merge_queue.py`,
`tests/test_merge_lock_by_project.py` (база ветки) сводятся в
`tests/test_merge_lock_module.py` и переписанный `tests/test_merge_queue.py`
(HEAD ветки).

Только чистые функции и вызовы git по переданному репозиторию: модуль не
импортирует `_pult` — значения выкладки (корень рабочей копии, база диффа,
репозиторий и ревизия ссылки документов) передают сами тесты.

Соглашения разбора PLAN.md, которых держится вся планка:

- раздел — заголовок markdown (`#`…`######`) вне ограждения кода; строки
  шапки таблицы `mutation-run` (`# mutation-run №…`, `# источник патчей:`,
  `# ревизия прогона:`, `# тесты:`, `# рабочих процессов:`, `# патч …`)
  заголовками не считаются; раздел длится до следующего заголовка того же
  или более высокого уровня;
- таблица `mutation-run` — текст, напечатанный командой
  (`orchestrator/mutation_run.py::_header`, `_Run.row`): шапка из строк
  `# …`, строка колонок `номер<TAB>исход<TAB>узлы` и строки
  `<номер><TAB><исход><TAB><узлы через запятую>`; при делении набора
  `--patches` таблиц в разделе несколько, у мутации берётся её последняя
  строка в порядке текста;
- ссылка на мутацию в тексте PLAN — имя патча `mutation-<nnn>` (с `.diff`
  или без) либо `мутация <n>` / `мутация №<n>` (любая форма слова);
- ссылка на исходный тест — `<Класс>::<метод>`, с префиксом
  `tests/<файл>.py::` или без него; ссылка на функцию файла модуля —
  `test_merge_lock_module.py::<функция>` или
  `test_merge_queue.py::<функция>` (с префиксом `tests/` или без, с
  вариантом `[<вариант>]` или без);
- упавшее утверждение — ссылка `tests/<файл>.py:<строка>` (как в логе
  прогона патча `mutation-run`) в той же строке PLAN, что ссылка на
  мутацию и на убивший тест (функцию); исходный файл читается из базы
  ветки, файл модуля — из HEAD; путь `tests/test_merge_queue.py` есть и
  там, и там — какое дерево, решает объемлющая функция строки;
- сопоставление «тест — мутация» и перечни (удалённые дубли, находки) —
  строки PLAN вне таблиц, где ссылка на тест и ссылка на мутацию стоят в
  ОДНОЙ строке; удалённые дубли — строки раздела, в заголовке которого
  есть слово «дубл…»; находки — строки со словом «находк…» либо строки
  раздела, в заголовке которого оно есть.
"""
import ast
import copy
import os
import re
import subprocess
from pathlib import Path

LOCK_SOURCE = "tests/test_merge_lock.py"
QUEUE_FILE = "tests/test_merge_queue.py"
BY_PROJECT_SOURCE = "tests/test_merge_lock_by_project.py"
SOURCE_FILES = (LOCK_SOURCE, QUEUE_FILE, BY_PROJECT_SOURCE)
LOCK_MODULE = "tests/test_merge_lock_module.py"
MODULE_FILES = (LOCK_MODULE, QUEUE_FILE)
DELETED_FILES = (LOCK_SOURCE, BY_PROJECT_SOURCE)
MAP_FILE = "docs/codebase-map.md"
FIXTURES_FILE = "tests/fixtures.py"

# Куда переносится каждый исходный класс (требование 8 SPEC).
TARGET_OF_CLASS = {
    "AcquireReleaseTest": LOCK_MODULE,
    "ProcessOwnershipTest": LOCK_MODULE,
    "RunWindowTest": LOCK_MODULE,
    "ConcurrentAcquireTest": LOCK_MODULE,
    "LegacyTouchHeartbeatTest": LOCK_MODULE,
    "PruneDeadEntriesTest": QUEUE_FILE,
    "HeadTaskIdTest": QUEUE_FILE,
    "CurrentHolderIdTest": QUEUE_FILE,
    "QueueWaitMinutesAndStatusSuffixTest": QUEUE_FILE,
    "CurrentHolderLabelTest": QUEUE_FILE,
    "ProcessScopedQueueRowsTest": QUEUE_FILE,
    "WaitForWindowTest": QUEUE_FILE,
    "WaitForWindowOtherProjectQueueTest": QUEUE_FILE,
    "WaitTextsAnyOrderTest": QUEUE_FILE,
}

CLAIM = "Ловит мутацию"
CLAIM_COUNT = 19
TEST_COUNT = 40
# Файлы кода, мутацию которых называет новая заявка (AC-1).
CLAIM_CODE = ("orchestrator/merge_lock.py", "orchestrator/merge_queue.py",
              "orchestrator/store.py")

# Помощники без утверждений (требование 10): имя функции модуля →
# [(файл источника, класс, метод)]; одинаковые по телу — одна функция.
HELPERS = {
    LOCK_MODULE: {
        "row": [(LOCK_SOURCE, "AcquireReleaseTest", "row"),
                (LOCK_SOURCE, "ProcessOwnershipTest", "row"),
                (LOCK_SOURCE, "RunWindowTest", "row")],
        "acquire_release_seed": [(LOCK_SOURCE, "AcquireReleaseTest", "seed")],
        "process_ownership_seed": [(LOCK_SOURCE, "ProcessOwnershipTest", "seed")],
        "new_task": [(BY_PROJECT_SOURCE, "_Base", "new_task")],
        "seed_lock": [(BY_PROJECT_SOURCE, "_Base", "seed_lock")],
        "locks": [(BY_PROJECT_SOURCE, "_Base", "locks")],
        "clear": [(BY_PROJECT_SOURCE, "_Base", "clear")],
    },
    QUEUE_FILE: {
        "enqueue": [(QUEUE_FILE, "_QueueTestBase", "enqueue")],
        "rows_by_pid": [(QUEUE_FILE, "ProcessScopedQueueRowsTest", "rows_by_pid")],
        "new_task": [(BY_PROJECT_SOURCE, "_Base", "new_task")],
        "seed_lock": [(BY_PROJECT_SOURCE, "_Base", "seed_lock")],
        "locks": [(BY_PROJECT_SOURCE, "_Base", "locks")],
        "clear": [(BY_PROJECT_SOURCE, "_Base", "clear")],
    },
}
# Имя метода `self.<метод>` в теле класса → имя функции модуля.
METHOD_RENAME = {("AcquireReleaseTest", "seed"): "acquire_release_seed",
                 ("ProcessOwnershipTest", "seed"): "process_ownership_seed"}
HELPER_METHODS = ("row", "seed", "enqueue", "rows_by_pid", "new_task",
                  "seed_lock", "locks", "clear")
NESTED = ("fake_sleep", "fake_monotonic", "worker")

# setUp-источники фикстур каждого файла модуля (требование 9).
SETUPS = {
    LOCK_MODULE: [(LOCK_SOURCE, "AcquireReleaseTest"),
                  (LOCK_SOURCE, "ProcessOwnershipTest"),
                  (LOCK_SOURCE, "RunWindowTest"),
                  (LOCK_SOURCE, "ConcurrentAcquireTest"),
                  (BY_PROJECT_SOURCE, "_Base")],
    QUEUE_FILE: [(QUEUE_FILE, "_QueueTestBase"),
                 (BY_PROJECT_SOURCE, "_Base")],
}

# Константы модуля (требование 9): файл модуля → имена; литерал — из базы.
CONSTANTS = {
    LOCK_MODULE: {"TASK": (LOCK_SOURCE, "AcquireReleaseTest"),
                  "HOLDER_TASK": (LOCK_SOURCE, "AcquireReleaseTest"),
                  "THREADS": (LOCK_SOURCE, "ConcurrentAcquireTest"),
                  "OTHER_HOST": (BY_PROJECT_SOURCE, None)},
    QUEUE_FILE: {"TASK_A": (QUEUE_FILE, "_QueueTestBase"),
                 "TASK_B": (QUEUE_FILE, "_QueueTestBase"),
                 "TASK_C": (QUEUE_FILE, "_QueueTestBase"),
                 "OTHER_HOST": (BY_PROJECT_SOURCE, None)},
}

# Функции пути взятия окна: патч, меняющий их строки, — «после него окно
# может не взяться» (требование 2, AC-2).
WINDOW_FUNCTIONS = {
    "orchestrator/merge_lock.py": ("acquire", "_holder_is_dead",
                                   "_is_own_process", "run_window"),
    "orchestrator/merge_queue.py": ("wait_for_window", "_head_task_id",
                                    "_prune_dead_entries"),
}

KILLED = "убита"
SURVIVED = "не убита"
COLLECTION = "ошибка сбора, импорта или setup"
UNKNOWN = "итог неизвестен"
LIMIT_OUTCOMES = ("оборвана по пределу", "не прогнана (предел)")
NOT_APPLIED = "патч не применяется"
TOUCHES = "патч трогает тесты"
INCONCLUSIVE = (UNKNOWN, NOT_APPLIED, TOUCHES, *LIMIT_OUTCOMES)
OUTCOMES = (KILLED, SURVIVED, COLLECTION, *INCONCLUSIVE)
MAX_PART = 25
MAX_WINDOW_PART = 8

PATCH_NAME = re.compile(r"^mutation-(\d{3,})\.diff$")

HEAD_RE = re.compile(r"^# mutation-run №(\d+) задачи (\S+)$")
_SOURCE = re.compile(r"^# источник патчей: (\S.*)$")
_REVISION = re.compile(r"^# ревизия прогона: (base|head|worktree) ([0-9a-f]{7,64})$")
_TESTS = re.compile(r"^# тесты: (\S.*)$")
_PATCH = re.compile(r"^# патч (\d+) (\S+) sha256 ([0-9a-f]{64})$")
_WORKERS = re.compile(r"^# рабочих процессов: (\S+)$")
COLUMNS = "номер\tисход\tузлы"
ROW_RE = re.compile(r"^(\d+)\t([^\t]+)(?:\t([^\t]*))?$")
_TABLE_LINE = (HEAD_RE, _SOURCE, _REVISION, _TESTS, _WORKERS, _PATCH)
_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")

_REF = (re.compile(r"mutation-0*(\d+)(?!\d)"),
        re.compile(r"[Мм]утаци[а-яё]*\s+№?\s*0*(\d+)(?!\d)"))
_TEST_KEY = re.compile(
    r"(?<![\w.])(?:tests/[\w./-]+\.py::)?([A-Za-z_]\w*)::(test\w*)")
_AFTER_REF = re.compile(
    r"(test_merge_lock_module|test_merge_queue)\.py::(test\w*)(?!\w|::)"
    r"(\[[^\]\s]*\])?")
_FILE_LINE = re.compile(r"(tests/[\w./-]+\.py):(\d+)(?!\d)")

_REPO_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
             "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
             "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX")


# ------------------------------------------------------------------- git

def git(repo, *args: str) -> subprocess.CompletedProcess:
    """`git -C <repo> <args>` без переменных, уводящих git в чужой репозиторий."""
    env = {k: v for k, v in os.environ.items() if k not in _REPO_ENV}
    env["GIT_CEILING_DIRECTORIES"] = str(Path(repo).parent)
    return subprocess.run(["git", "-C", str(repo), *args], env=env,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def git_out(repo, *args: str) -> str:
    res = git(repo, *args)
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} в {repo} вернул "
                           f"{res.returncode}: {res.stderr.strip()}")
    return res.stdout


def show(repo, revision: str, path: str) -> str | None:
    """Текст `path` ревизии `revision`; файла там нет — None."""
    res = git(repo, "show", f"{revision}:{path}")
    return res.stdout if res.returncode == 0 else None


def docs_entry_types(docs_repo, revision: str, task_id: str) -> dict[str, str]:
    """{имя первого уровня `tasks/<id>/`: тип объекта git (`blob`/`tree`)}."""
    rel = f"tasks/{task_id}/"
    out = git_out(docs_repo, "ls-tree", "-z", revision, "--", rel)
    found = {}
    for item in out.split("\0"):
        meta, _tab, path = item.partition("\t")
        if path.startswith(rel) and meta:
            found[path[len(rel):]] = meta.split()[1]
    return found


def patch_names(entries) -> dict[int, str]:
    """{номер: имя} патчей мутаций первого уровня каталога задачи."""
    found = {}
    for name in entries:
        match = PATCH_NAME.match(name)
        if match:
            found[int(match.group(1))] = name
    return found


# ---------------------------------------------------------------- патчи

def _strip_side(path: str) -> str | None:
    path = path.strip().strip('"')
    if path == "/dev/null":
        return None
    return path[2:] if path[:2] in ("a/", "b/") else path


def patch_paths(text: str) -> set[str]:
    """Пути патча: заголовки `diff --git`, `---`/`+++`, переименования."""
    paths = set()
    for line in text.splitlines():
        if line.startswith("diff --git "):
            left, sep, right = line[len("diff --git "):].partition(" b/")
            for part in ([left, "b/" + right] if sep else
                         line[len("diff --git "):].split()):
                stripped = _strip_side(part)
                if stripped:
                    paths.add(stripped)
        elif line.startswith(("--- ", "+++ ")):
            stripped = _strip_side(line[4:].split("\t", 1)[0])
            if stripped:
                paths.add(stripped)
        else:
            for head in ("rename from ", "rename to ", "copy from ",
                         "copy to "):
                if line.startswith(head):
                    paths.add(line[len(head):].strip())
    return {os.path.normpath(p).replace(os.sep, "/") for p in paths}


def changed_line_count(text: str) -> int:
    return sum(1 for line in text.splitlines()
               if line[:1] in "+-" and not line.startswith(("+++ ", "--- ")))


_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")


def patch_old_lines(text: str) -> dict[str, set[int]]:
    """{путь: номера строк старой стороны, которые патч удаляет или около
    которых вставляет} — по заголовкам хунков и строкам `-`/`+`."""
    found: dict[str, set[int]] = {}
    current, line_no = None, 0
    for line in text.splitlines():
        if line.startswith("--- "):
            current = _strip_side(line[4:].split("\t", 1)[0])
            continue
        if line.startswith("+++ "):
            if current is None:
                current = _strip_side(line[4:].split("\t", 1)[0])
            continue
        match = _HUNK.match(line)
        if match:
            line_no = int(match.group(1))
            continue
        if current is None or line.startswith(("diff --git", "index ")):
            continue
        if line.startswith("-"):
            found.setdefault(current, set()).add(line_no)
            line_no += 1
        elif line.startswith("+"):
            found.setdefault(current, set()).add(max(line_no, 1))
        elif line.startswith(" "):
            line_no += 1
    return found


def enclosing_functions(text: str, line: int) -> list[str]:
    """Имена функций исходного текста, объемлющих строку `line`."""
    tree = ast.parse(text)
    return [n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.lineno <= line <= (n.end_lineno or n.lineno)]


# ------------------------------------------------------------- разделы PLAN

def _is_table_line(line: str) -> bool:
    return any(p.match(line) for p in _TABLE_LINE)


def _headings(lines: list[str]) -> list[tuple[int, int, str]]:
    found, fenced = [], False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced or _is_table_line(line):
            continue
        match = _HEADING.match(line)
        if match:
            found.append((i, len(match.group(1)), match.group(2)))
    return found


def sections(plan: str, word: str) -> list[str]:
    """Тексты разделов, в заголовке которых есть `word` (без учёта
    регистра); раздел — до заголовка того же или более высокого уровня."""
    lines = plan.split("\n")
    heads = _headings(lines)
    result = []
    for n, (start, level, title) in enumerate(heads):
        if word.casefold() not in title.casefold():
            continue
        end = len(lines)
        for nxt, nlevel, _t in heads[n + 1:]:
            if nlevel <= level:
                end = nxt
                break
        result.append("\n".join(lines[start + 1:end]))
    return result


def prose_lines(text: str) -> list[str]:
    """Строки текста без строк таблиц `mutation-run` (шапка, колонки, строки)."""
    return [line for line in text.split("\n")
            if not _is_table_line(line) and line != COLUMNS
            and not ROW_RE.match(line)]


def refs(line: str) -> set[int]:
    found = set()
    for pattern in _REF:
        found.update(int(m) for m in pattern.findall(line))
    return found


def test_keys(line: str) -> set[str]:
    """Ссылки строки на исходные тесты в виде `<Класс>::<метод>`."""
    return {f"{c}::{m}" for c, m in _TEST_KEY.findall(line)}


def after_refs(line: str) -> set[tuple[str, str]]:
    """Ссылки строки на функции файлов модулей: {(файл, функция)}."""
    return {(f"tests/{stem}.py", func) for stem, func, _v in _AFTER_REF.findall(line)}


def file_lines(line: str) -> list[tuple[str, int]]:
    return [(path, int(n)) for path, n in _FILE_LINE.findall(line)]


def node_key(node: str) -> str:
    keys = test_keys(node)
    return next(iter(keys)) if len(keys) == 1 else node


def after_node(node: str) -> tuple[str, str]:
    """`tests/<файл>.py::<функция>[<вариант>]` → (файл, функция)."""
    path, _sep, tail = node.partition("::")
    return path, tail.split("[", 1)[0]


def finding_refs(plan: str) -> set[int]:
    found = set()
    for line in prose_lines(plan):
        if "находк" in line.casefold():
            found |= refs(line)
    for text in sections(plan, "находк"):
        for line in prose_lines(text):
            found |= refs(line)
    return found


def removed_duplicates(plan: str) -> dict[str, set[int]]:
    removed: dict[str, set[int]] = {}
    for text in sections(plan, "дубл"):
        for line in prose_lines(text):
            for key in test_keys(line):
                removed.setdefault(key, set()).update(refs(line))
    return removed


# ------------------------------------------------------------ таблицы

class Table:
    def __init__(self):
        self.run_no = None
        self.task = ""
        self.source = ""
        self.ref = ""
        self.sha = ""
        self.tests: list[str] = []
        self.workers = ""
        self.patches: dict[int, tuple[str, str]] = {}
        self.rows: list[tuple[int, str, list[str]]] = []


def tables(text: str) -> tuple[list[Table], list[str]]:
    """(таблицы `mutation-run` текста, ошибки формата шапки)."""
    lines = text.split("\n")
    found, errors = [], []
    i = 0
    while i < len(lines):
        head = HEAD_RE.match(lines[i])
        if not head:
            i += 1
            continue
        table = Table()
        table.run_no, table.task = int(head.group(1)), head.group(2)
        i += 1
        expected = ((_SOURCE, "источник патчей"), (_REVISION, "ревизия прогона"),
                    (_TESTS, "тесты"))
        broken = False
        for pattern, what in expected:
            match = pattern.match(lines[i]) if i < len(lines) else None
            if not match:
                errors.append(f"таблица №{table.run_no}: нет строки шапки "
                              f"«# {what}: …» на своём месте")
                broken = True
                break
            if pattern is _SOURCE:
                table.source = match.group(1)
            elif pattern is _REVISION:
                table.ref, table.sha = match.group(1), match.group(2)
            else:
                table.tests = [t.strip() for t in match.group(1).split(",")]
            i += 1
        if broken:
            continue
        if i < len(lines) and _WORKERS.match(lines[i]):
            table.workers = _WORKERS.match(lines[i]).group(1)
            i += 1
        while i < len(lines) and _PATCH.match(lines[i]):
            match = _PATCH.match(lines[i])
            table.patches[int(match.group(1))] = (match.group(2), match.group(3))
            i += 1
        if i >= len(lines) or lines[i] != COLUMNS:
            errors.append(f"таблица №{table.run_no}: после строк патчей нет "
                          f"строки колонок {COLUMNS!r}")
            continue
        i += 1
        while i < len(lines) and ROW_RE.match(lines[i]):
            match = ROW_RE.match(lines[i])
            nodes = [n.strip() for n in (match.group(3) or "").split(",") if n.strip()]
            table.rows.append((int(match.group(1)), match.group(2), nodes))
            i += 1
        found.append(table)
    return found, errors


def last_rows(found: list[Table]) -> dict[int, tuple[str, list[str]]]:
    rows = {}
    for table in found:
        for number, outcome, nodes in table.rows:
            rows[number] = (outcome, nodes)
    return rows


def last_patch_sha(found: list[Table]) -> dict[int, str]:
    shas = {}
    for table in found:
        for number, (_name, sha) in table.patches.items():
            shas[number] = sha
    return shas


def killed(rows: dict) -> dict[int, list[str]]:
    """{номер: убившие узлы} мутаций с исходом «убита» и непустыми узлами."""
    return {n: nodes for n, (outcome, nodes) in rows.items()
            if outcome == KILLED and nodes}


# --------------------------------------------------- исходные тесты (ast)

class BaseTest:
    def __init__(self, path: str, cls: str, func: ast.FunctionDef):
        self.path, self.cls, self.func = path, cls, func
        self.name = func.name
        self.key = f"{cls}::{func.name}"
        self.claim = CLAIM in (ast.get_docstring(func) or "")
        self.target = TARGET_OF_CLASS.get(cls)


def base_tests(path: str, text: str) -> list[BaseTest]:
    tree = ast.parse(text)
    found = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and item.name.startswith("test"):
                    found.append(BaseTest(path, node.name, item))
    return found


def class_node(tree, cls: str):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            return node
    return None


def class_method(tree, cls: str, method: str):
    node = class_node(tree, cls)
    if node is None:
        return None
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and item.name == method:
            return item
    return None


def class_constant(tree, cls: str | None, name: str):
    """Литерал атрибута класса `cls` (или константы модуля при `cls=None`)."""
    body = tree.body if cls is None else (class_node(tree, cls) or ast.Module([], [])).body
    for node in body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id == name \
                and isinstance(node.value, ast.Constant):
            return node.value.value
    raise LookupError(f"{cls or '<модуль>'}.{name} не найден")


_ONE_ARG = {"assertTrue", "assertFalse", "assertIsNone", "assertIsNotNone"}


def _is_self_assert(node) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("assert")
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and not node.func.attr.startswith("assertRaises"))


def is_method_assert(node) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("assert")
            and not node.func.attr.startswith("assertRaises"))


def constants(node) -> set:
    found = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and not isinstance(sub.value, bool) \
                and isinstance(sub.value, (str, int, float)):
            found.add(sub.value)
    return found


def assert_calls(tree) -> list[ast.Call]:
    return [n for n in ast.walk(tree) if _is_self_assert(n)]


def semantic_args(call: ast.Call) -> list:
    count = 1 if call.func.attr in _ONE_ARG else 2
    return list(call.args[:count])


def msg_arg(call: ast.Call):
    """Аргумент msg вызова `self.assert*` (позиционный за смысловыми или
    именованный); нет — None."""
    count = 1 if call.func.attr in _ONE_ARG else 2
    if len(call.args) > count:
        return call.args[count]
    for kw in call.keywords:
        if kw.arg == "msg":
            return kw.value
    return None


def assertion_literals(tree) -> set:
    found = set()
    for call in assert_calls(tree):
        for arg in semantic_args(call):
            found |= constants(arg)
    return found


def assertion_kinds(tree) -> set[str]:
    return {call.func.attr for call in assert_calls(tree)}


def equality_literals(tree) -> tuple[set, set]:
    """(литералы аргументов `assertEqual`, литералы аргументов `assertIn`/
    `assertNotIn`)."""
    equal, member = set(), set()
    for call in assert_calls(tree):
        name = call.func.attr
        lits = set()
        for arg in semantic_args(call):
            lits |= constants(arg)
        if name in ("assertEqual",):
            equal |= lits
        elif name in ("assertIn", "assertNotIn"):
            member |= lits
    return equal, member


# ------------------------------------------------------ преобразования (ast)

class _SelfToParam(ast.NodeTransformer):
    """`self.<КОНСТАНТА>` → имя константы модуля; `self.<помощник>(…)` →
    `<функция>(<стенд>, …)`; прочие `self` → имя стенда."""

    def __init__(self, param: str, calls: dict, consts: set):
        self.param, self.calls, self.consts = param, calls, consts

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id == "self" and func.attr in self.calls:
            node.args = [self.visit(a) for a in node.args]
            node.keywords = [self.visit(k) for k in node.keywords]
            node.func = ast.Name(id=self.calls[func.attr], ctx=ast.Load())
            node.args = [ast.Name(id=self.param, ctx=ast.Load()), *node.args]
            return node
        self.generic_visit(node)
        return node

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == "self" \
                and node.attr in self.consts:
            return ast.copy_location(ast.Name(id=node.attr, ctx=node.ctx), node)
        self.generic_visit(node)
        return node

    def visit_Name(self, node):
        if node.id == "self":
            node.id = self.param
        return node


def strip_docstring(body: list) -> list:
    if body and isinstance(body[0], ast.Expr) and \
            isinstance(body[0].value, ast.Constant) and \
            isinstance(body[0].value.value, str):
        return body[1:]
    return body


def _is_super_setup(stmt) -> bool:
    return (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Attribute)
            and stmt.value.func.attr == "setUp"
            and isinstance(stmt.value.func.value, ast.Call)
            and isinstance(stmt.value.func.value.func, ast.Name)
            and stmt.value.func.value.func.id == "super")


def class_constants(tree) -> set[str]:
    """Имена атрибутов классов вида `ВЕРХНИЙ_РЕГИСТР = литерал`."""
    found = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and \
                                re.fullmatch(r"[A-Z][A-Z0-9_]*", target.id):
                            found.add(target.id)
    return found


def helper_calls(cls: str) -> dict:
    """{метод класса `cls`: имя функции модуля} для `self.<помощник>(…)`."""
    calls = {m: m for m in HELPER_METHODS}
    for (owner, method), name in METHOD_RENAME.items():
        if owner == cls:
            calls[method] = name
    if cls not in {owner for owner, _m in METHOD_RENAME}:
        calls.pop("seed", None)
    return calls


def translated_body(method, cls: str, param: str, consts: set,
                    drop_super: bool = False) -> str:
    """`ast.dump` тела метода, переведённого в функцию модуля."""
    node = copy.deepcopy(method)
    body = strip_docstring(node.body)
    if drop_super:
        body = [s for s in body if not _is_super_setup(s)]
    trans = _SelfToParam(param, helper_calls(cls), consts)
    body = [trans.visit(s) for s in body]
    return ast.dump(ast.Module(body=body, type_ignores=[]))


def body_dump(func, drop_trailing_return: bool = False) -> str:
    body = strip_docstring(copy.deepcopy(func).body)
    if drop_trailing_return and body:
        last = body[-1]
        if isinstance(last, ast.Return) or (
                isinstance(last, ast.Expr)
                and isinstance(last.value, (ast.Yield, ast.YieldFrom))):
            body = body[:-1]
    return ast.dump(ast.Module(body=body, type_ignores=[]))


def rest_args_dump(args: ast.arguments, drop_first: bool) -> str:
    node = copy.deepcopy(args)
    if drop_first:
        node.args = node.args[1:]
    return ast.dump(node)


# ------------------------------------------------------- файлы модулей (ast)

def is_fixture(func) -> bool:
    for deco in func.decorator_list:
        target = deco.func if isinstance(deco, ast.Call) else deco
        if isinstance(target, ast.Attribute) and target.attr == "fixture":
            return True
        if isinstance(target, ast.Name) and target.id == "fixture":
            return True
    return False


def module_tests(tree) -> list[ast.FunctionDef]:
    return [n for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name.startswith("test")]


def module_functions(tree) -> dict:
    return {n.name: n for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def fixtures(tree) -> list:
    return [n for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and is_fixture(n)]


def moved_to(name: str, funcs) -> list:
    """Функции-тесты, в которые перенесён исходный тест `name`: имя функции
    равно имени теста или содержит его."""
    return [f for f in funcs if f.name == name or name in f.name]


def is_pytest_raises(node) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "raises"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "pytest")


def non_docstring_constants(tree) -> set:
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                docstrings.add(id(first.value))
    found = set()
    for sub in ast.walk(tree):
        if isinstance(sub, ast.Constant) and id(sub) not in docstrings \
                and not isinstance(sub.value, bool) \
                and isinstance(sub.value, (str, int, float)):
            found.add(sub.value)
    return found


def compare_operands(tree) -> list[tuple[str, set]]:
    """[(вид сравнения, литералы операндов)] каждого `ast.Compare`: вид —
    `eq` (==, !=, is), `in` (in, not in), `order` (<, <=, >, >=)."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        kinds = set()
        for op in node.ops:
            if isinstance(op, (ast.Eq, ast.NotEq, ast.Is, ast.IsNot)):
                kinds.add("eq")
            elif isinstance(op, (ast.In, ast.NotIn)):
                kinds.add("in")
            else:
                kinds.add("order")
        lits = set()
        for operand in [node.left, *node.comparators]:
            lits |= constants(operand)
        for kind in kinds:
            found.append((kind, lits))
    return found


# ------------------------------------------- место упавшего утверждения

def is_assertion_error_raise(node) -> bool:
    if not isinstance(node, ast.Raise) or node.exc is None:
        return False
    exc = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
    return isinstance(exc, ast.Name) and exc.id == "AssertionError"


def is_assertion_node(node) -> bool:
    """`assert`, `raise AssertionError(…)`, `<что-то>.assert*`/`fail`/`raises`,
    голый `fail(…)`."""
    if isinstance(node, ast.Assert) or is_assertion_error_raise(node):
        return True
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr.startswith("assert") or func.attr in ("fail", "raises")
    return isinstance(func, ast.Name) and func.id == "fail"


def assertion_at(tree, line: int):
    """Внешний узел утверждения, покрывающий строку `line`; нет — None."""
    covering = [n for n in ast.walk(tree) if is_assertion_node(n)
                and n.lineno <= line <= (n.end_lineno or n.lineno)]
    if not covering:
        return None
    return max(covering, key=lambda n: ((n.end_lineno or n.lineno) - n.lineno,
                                        -n.lineno))


def function_chain(tree, line: int) -> list:
    """Функции, объемлющие строку `line`, от внешней к внутренней."""
    return sorted((n for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and n.lineno <= line <= (n.end_lineno or n.lineno)),
                  key=lambda n: (n.lineno, -(n.end_lineno or n.lineno)))


def site_ok(tree, line: int, test_name: str, prep_names=()) -> bool:
    """Строка `line` — в утверждении, внутри функции-теста `test_name`, не
    внутри фикстуры и не внутри помощника подготовки `prep_names`."""
    if tree is None or assertion_at(tree, line) is None:
        return False
    chain = function_chain(tree, line)
    names = [f.name for f in chain]
    if test_name not in names:
        return False
    return not any(is_fixture(f) or f.name in prep_names or f.name == "setUp"
                   for f in chain)


# --------------------------------------- нормальная форма утверждения

_CMP = {"assertEqual": ast.Eq, "assertNotEqual": ast.NotEq,
        "assertIn": ast.In, "assertNotIn": ast.NotIn,
        "assertIs": ast.Is, "assertIsNot": ast.IsNot,
        "assertLess": ast.Lt, "assertLessEqual": ast.LtE,
        "assertGreater": ast.Gt, "assertGreaterEqual": ast.GtE}


class Canon(ast.NodeTransformer):
    """Общая форма операндов: стенд (`self`, параметры функции-теста) →
    `STAND`; `self.<КОНСТАНТА>` → константа; `self.<помощник>(…)` →
    `<функция>(STAND, …)`; `<x>.exception`/`<x>.value` → `EXC`; вызов
    переименованного помощника (`renames`: имя в файле → имя перечня) —
    вызовом по имени перечня."""

    def __init__(self, stands: set, calls: dict, consts: set, excs: set,
                 renames: dict | None = None):
        self.stands, self.calls, self.consts, self.excs = stands, calls, consts, excs
        self.renames = renames or {}

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Name) and func.id in self.renames:
            node.func = ast.Name(id=self.renames[func.id], ctx=ast.Load())
            node.args = [self.visit(a) for a in node.args]
            node.keywords = [self.visit(k) for k in node.keywords]
            return node
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id == "self" and func.attr in self.calls:
            node.args = [self.visit(a) for a in node.args]
            node.keywords = [self.visit(k) for k in node.keywords]
            node.func = ast.Name(id=self.calls[func.attr], ctx=ast.Load())
            node.args = [ast.Name(id="STAND", ctx=ast.Load()), *node.args]
            return node
        self.generic_visit(node)
        return node

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name):
            if node.value.id == "self" and node.attr in self.consts:
                return ast.Name(id=node.attr, ctx=ast.Load())
            if node.value.id in self.excs and node.attr in ("exception", "value"):
                return ast.Name(id="EXC", ctx=ast.Load())
        self.generic_visit(node)
        return node

    def visit_Name(self, node):
        if node.id == "self" or node.id in self.stands:
            return ast.Name(id="STAND", ctx=ast.Load())
        return ast.Name(id=node.id, ctx=ast.Load())


def dump_canon(node, canon: Canon) -> str:
    return ast.dump(canon.visit(copy.deepcopy(node)), annotate_fields=False)


def normal_form(node, canon: Canon):
    """Нормальная форма утверждения (решение 1 ANSWER-1): `assertX(a, b)` ↔
    `assert a <op> b`, `assertTrue(x)` ↔ `assert x`, `assertFalse(x)` ↔
    `assert not x`, `assertIsNone(x)` ↔ `assert x is None`, `assertIsNotNone(x)`
    ↔ `assert x is not None`; сообщение отбрасывается; `raise
    AssertionError(<текст>)` — сам текст; `pytest.raises(E)`/
    `assertRaises(E)` — тип исключения."""
    if isinstance(node, ast.Raise):
        exc = node.exc
        args = exc.args if isinstance(exc, ast.Call) else []
        return ("raise", tuple(dump_canon(a, canon) for a in args))
    if isinstance(node, ast.Assert):
        test = node.test
        if isinstance(test, ast.Compare) and len(test.ops) == 1:
            return ("cmp", type(test.ops[0]).__name__, dump_canon(test.left, canon),
                    dump_canon(test.comparators[0], canon))
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            return ("false", dump_canon(test.operand, canon))
        return ("true", dump_canon(test, canon))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        name = node.func.attr
        if name in ("raises", "assertRaises"):
            return ("raises", tuple(dump_canon(a, canon) for a in node.args[:1]))
        args = node.args
        if name in _CMP and len(args) >= 2:
            return ("cmp", _CMP[name].__name__, dump_canon(args[0], canon),
                    dump_canon(args[1], canon))
        none = ast.Constant(value=None)
        if name == "assertIsNone" and args:
            return ("cmp", "Is", dump_canon(args[0], canon), dump_canon(none, canon))
        if name == "assertIsNotNone" and args:
            return ("cmp", "IsNot", dump_canon(args[0], canon), dump_canon(none, canon))
        if name == "assertTrue" and args:
            return ("true", dump_canon(args[0], canon))
        if name == "assertFalse" and args:
            return ("false", dump_canon(args[0], canon))
    return ("other", ast.dump(node))


def canon_for(tree, func, cls: str | None, renames: dict | None = None) -> Canon:
    """Нормализатор операндов для функции-теста `func` (класс `cls` — у
    исходного метода, None — у функции модуля; `renames` — имена
    помощников файла модуля, `helper_renames`)."""
    stands = set() if cls is not None else {a.arg for a in func.args.args}
    calls = helper_calls(cls) if cls is not None else {}
    excs = set()
    for node in ast.walk(func):
        if isinstance(node, ast.With):
            for item in node.items:
                if isinstance(item.optional_vars, ast.Name):
                    excs.add(item.optional_vars.id)
    return Canon(stands, calls, class_constants(tree), excs, renames)


def helper_names(tree, path: str) -> dict:
    """{имя перечня `HELPERS[path]`: имя функции в файле модуля}. Имя
    функции — имя перечня либо (кроме двух `seed`, имена которых задаёт
    SPEC) имя с префиксом `<префикс>_<имя>`: помощник `row` сталкивается с
    локальной `row = self.row()` исходных тестов. Не найдено или найдено
    несколько — имени в словаре нет."""
    funcs = [f for f in module_functions(tree).values()
             if not f.name.startswith("test") and not is_fixture(f)]
    fixed = set(METHOD_RENAME.values())
    found = {}
    for name in HELPERS[path]:
        exact = [f.name for f in funcs if f.name == name]
        prefixed = [] if name in fixed else \
            [f.name for f in funcs if f.name.endswith("_" + name)]
        if exact:
            found[name] = name
        elif len(prefixed) == 1:
            found[name] = prefixed[0]
    return found


def helper_renames(tree, path: str) -> dict:
    """{имя функции в файле модуля: имя перечня} для переименованных помощников."""
    return {actual: name for name, actual in helper_names(tree, path).items()
            if actual != name}


class _CallRenamer(ast.NodeTransformer):
    def __init__(self, renames: dict):
        self.renames = renames

    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id in self.renames:
            node.func = ast.Name(id=self.renames[node.func.id], ctx=ast.Load())
        return node


def renamed_calls(func, renames: dict):
    """Копия `func`, где вызовы переименованных помощников — по имени перечня."""
    return _CallRenamer(renames).visit(copy.deepcopy(func)) if renames else func
