"""Общий разбор планки волны 3м-2 сведения тестов: тесты пяти файлов волны
(база ветки) — долгоживущего `…merge_mutex_by_project.py`,
`tests/test_merge_after.py`, `tests/test_merge_after_declared.py`,
долгоживущих `…division_merge_after.py` и `…spec_gate_hint.py` —
сводятся в конец `tests/test_merge_lock_module.py` и
`tests/test_merge_queue.py` и в новый `tests/test_merge_after_module.py`
(HEAD ветки).

Только чистые функции и вызовы git по переданному репозиторию: модуль не
импортирует `_pult` — значения выкладки (корень рабочей копии, база диффа,
репозиторий и ревизия ссылки документов) передают сами тесты.

Соглашения разбора PLAN.md, которых держится вся планка (те же, что у
планки волны 3м-1):

- раздел — заголовок markdown (`#`…`######`) вне ограждения кода; строки
  шапки таблицы `mutation-run` (`# mutation-run №…`, `# источник патчей:`,
  `# ревизия прогона:`, `# тесты:`, `# рабочих процессов:`, `# патч …`)
  заголовками не считаются; раздел длится до следующего заголовка того же
  или более высокого уровня;
- таблица `mutation-run` — текст, напечатанный командой
  (`orchestrator/mutation_run.py`): шапка из строк `# …`, строка колонок
  `номер<TAB>исход<TAB>узлы` и строки `<номер><TAB><исход><TAB><узлы через
  запятую>`; при делении набора `--patches` таблиц в разделе несколько, у
  мутации берётся её последняя строка в порядке текста;
- ссылка на мутацию в тексте PLAN — имя патча `mutation-<nnn>` (с `.diff`
  или без) либо `мутация <n>` / `мутация №<n>` (любая форма слова);
- ссылка на исходный тест — `<Класс>::<метод>`, с префиксом
  `tests/<файл>.py::` или без него; ссылка на функцию файла модуля —
  `test_merge_lock_module.py::<функция>`, `test_merge_queue.py::<функция>`
  или `test_merge_after_module.py::<функция>` (с префиксом `tests/` или
  без);
- упавшее утверждение — ссылка `tests/<файл>.py:<строка>` (как в логе
  прогона патча) в той же строке PLAN, что ссылка на мутацию и на убивший
  тест (функцию); исходный файл читается из базы ветки, файл модуля — из
  HEAD;
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

MUTEX = "tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py"
AFTER_SOURCE = "tests/test_merge_after.py"
DECLARED = "tests/test_merge_after_declared.py"
DIVISION = "tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py"
HINT = "tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py"
SOURCE_FILES = (MUTEX, AFTER_SOURCE, DECLARED, DIVISION, HINT)
MERGE_AFTER_SOURCES = (AFTER_SOURCE, DECLARED, DIVISION, HINT)
LOCK_MODULE = "tests/test_merge_lock_module.py"
QUEUE_MODULE = "tests/test_merge_queue.py"
AFTER_MODULE = "tests/test_merge_after_module.py"
MODULE_FILES = (LOCK_MODULE, QUEUE_MODULE, AFTER_MODULE)
EXTENDED_FILES = (LOCK_MODULE, QUEUE_MODULE)
MAP_FILE = "docs/codebase-map.md"
FIXTURES_FILE = "tests/fixtures.py"

SPEC_IDS = ("01M44EP0D47F498TEE08MNGBYT", "01M45D29BQJE8FJYJA4JQWSYFZ",
            "01M4JC58GZFHZ4PZHW254P22M2", "01M5FGHNB29QA254FM07QR55AB")

# Куда переносится каждый исходный класс (требования 8, 9 SPEC).
TARGET_OF_CLASS = {
    "AcquireByProjectTest": LOCK_MODULE,
    "ReleaseAndHeartbeatTest": LOCK_MODULE,
    "StoreMergeLockTest": LOCK_MODULE,
    "QueueByProjectTest": QUEUE_MODULE,
    "WaitTextsByProjectTest": QUEUE_MODULE,
    "TaskIdFormTest": AFTER_MODULE,
    "TaskIdMatchesTest": AFTER_MODULE,
    "CheckTest": AFTER_MODULE,
    "MergeGateMissingDependencyTest": AFTER_MODULE,
    "MandateLineTest": AFTER_MODULE,
    "PlanChannelSameValueTest": AFTER_MODULE,
    "ReplaceDividedTest": AFTER_MODULE,
    "MigrationTest": AFTER_MODULE,
    "DeclaredFromTzTest": AFTER_MODULE,
    "SpecGateDeclaredRefusalTest": AFTER_MODULE,
    "DivisionRewritesDependentsTest": AFTER_MODULE,
    "LossRefusalTextTest": AFTER_MODULE,
    "DeclaredPathTest": AFTER_MODULE,
}
NO_STAND_CLASSES = ("TaskIdFormTest", "MigrationTest")

CLAIM = "Ловит мутацию"
TEST_COUNT = 37
CLAIM_COUNT = 37
SUBTEST_COUNT = 17

# Базовый класс стенда mutex_by_project и его помощники (требование 8).
MUTEX_BASE = "_ProjectMutexBase"
# Помощник `_ProjectMutexBase` → функция файла модуля: переименованные и
# не переносимые (`lock_by_task` → `locks`, `clear` → `clear` модуля).
MUTEX_RENAME = {"new_task": "project_mutex_new_task",
                "seed_lock": "project_mutex_seed_lock",
                "enqueue": "project_mutex_enqueue",
                "actions": "project_mutex_actions",
                "lock_by_task": "locks",
                "clear": "clear"}
MUTEX_NOT_MOVED = ("lock_by_task", "clear")
MUTEX_MODULE_NAMES = ("refusal_pattern", "TS_FORMAT", "TAKEOVER_ACTION",
                      "_ALPHABET")

# Помощники стендов merge_after (требование 9): (файл, класс) → {метод:
# функция модуля}.
AFTER_HELPERS = {
    (AFTER_SOURCE, "MergeAfterDbSandbox"): {"insert": "merge_after_db_insert",
                                            "set_deps": "set_deps"},
    (DECLARED, "DeclaredSandbox"): {"insert": "declared_insert"},
    (DECLARED, "SpecGateDeclaredRefusalTest"): {
        "spec_text": "spec_gate_declared_refusal_spec_text"},
    (DIVISION, "DivisionRewritesDependentsTest"): {
        "new_task": "new_task", "msg": "msg", "divide": "divide",
        "stored_deps": "stored_deps", "journal": "journal"},
    (HINT, "LossRefusalTextTest"): {"task": "task"},
    (HINT, "DeclaredPathTest"): {
        "note": "declared_path_note", "run_cmd": "run_cmd",
        "live_task": "live_task", "declared_task": "declared_task",
        "refusal": "refusal", "no_code_tree": "no_code_tree"},
}
# Помощник — функция модуля без параметра стенда (требование 9).
NO_STAND_FUNCS = ("no_code_tree",)
# Константы и функции модулей четырёх файлов merge_after — дословно.
AFTER_MODULE_NAMES = {
    AFTER_SOURCE: ("MARKER",),
    DECLARED: ("OTHER_TARGET",),
    DIVISION: ("ZONE", "DIVIDED_PREFIX", "division_spec"),
    HINT: ("FIELD", "MANDATE", "LOSS_START", "OLD_TAIL", "ZONES", "SPEC_TEXT",
           "spec_text", "meta_of"),
}
# Помощники с утверждениями: подготовки (не доказательство) и проверки.
PREP_HELPERS = ("divide", "declared_task", "wait_texts")
ASSERT_HELPERS = ("assert_fresh",)
# Утверждения подготовки в телах тестов и помощников (AC-4): файл → строки.
PREP_LINES = {DIVISION: (114, 119, 122), HINT: (175, 213),
              MUTEX: (597, 326), DECLARED: (87,)}

# Фикстуры стендов (требования 8–10): файл модуля → {имя: (параметр,
# [(файл, класс) источников setUp])}.
STANDS = {
    LOCK_MODULE: {"project_mutex_stand": ("tmp_root", [(MUTEX, MUTEX_BASE)])},
    QUEUE_MODULE: {"project_mutex_stand": ("tmp_root", [(MUTEX, MUTEX_BASE)])},
    AFTER_MODULE: {
        "merge_after_stand": ("light_transition",
                              [(AFTER_SOURCE, "MergeAfterDbSandbox"),
                               (DECLARED, "DeclaredSandbox")]),
        "loss_stand": ("initialized_tmp_root", [(HINT, "LossRefusalTextTest")]),
        "declared_path_stand": ("light_transition", [(HINT, "DeclaredPathTest")]),
        "division_stand": ("division_sandbox",
                           [(DIVISION, "DivisionRewritesDependentsTest")]),
    },
}
DIVISION_SANDBOX = "DivisionSandbox"
DIVISION_SANDBOX_FIXTURE = "division_sandbox"

# Функции пути взятия окна: патч, меняющий их строки, — «после него окно
# может не взяться или `wait_for_window` может не кончиться» (AC-2).
WINDOW_FUNCTIONS = {
    "orchestrator/merge_lock.py": ("acquire", "_holder_is_dead",
                                   "_is_own_process", "run_window"),
    "orchestrator/merge_queue.py": ("wait_for_window", "_head_task_id",
                                    "_prune_dead_entries"),
    "orchestrator/store.py": ("project_merge_lock_row", "set_merge_lock",
                              "merge_queue_rows", "project_merge_queue_rows",
                              "delete_merge_queue_row", "task_target"),
    "orchestrator/liveness.py": ("_age_seconds", "_pid_alive"),
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
    r"(test_merge_lock_module|test_merge_queue|test_merge_after_module)\.py::"
    r"(test\w*)(?!\w|::)(\[[^\]\s]*\])?")
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


def number_named(text: str, number: int) -> bool:
    """Число `number` стоит в тексте отдельным числом; группы разрядов
    могут разделяться пробелом (в том числе неразрывным и узким)."""
    digits = str(number)
    groups = []
    while digits:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    body = r"[   ]?".join(groups)
    return re.search(rf"(?<![\d.,]){body}(?![\d])", text) is not None


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


def class_methods(tree, cls: str) -> dict:
    node = class_node(tree, cls)
    if node is None:
        return {}
    return {i.name: i for i in node.body
            if isinstance(i, (ast.FunctionDef, ast.AsyncFunctionDef))}


def class_chain(tree, cls: str) -> list[str]:
    """Класс `cls` и его базы, определённые в том же файле (от `cls` вверх)."""
    chain, current = [], cls
    while current and current not in chain:
        node = class_node(tree, current)
        if node is None:
            break
        chain.append(current)
        current = next((b.id for b in node.bases if isinstance(b, ast.Name)
                        and class_node(tree, b.id) is not None), None)
    return chain


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


def top_level(tree, name: str):
    """Присваивание или функция верхнего уровня с именем `name`; нет — None."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == name:
            return node
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return node
    return None


def top_level_assignments(tree, name: str) -> list:
    return [n for n in tree.body if isinstance(n, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == name for t in n.targets)]


def self_refs(node) -> set[str]:
    """Имена `self.<имя>` внутри узла."""
    return {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name) and n.value.id == "self"}


def name_loads(node) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def mutex_needs(tree, classes) -> tuple[set[str], set[str]]:
    """(методы `_ProjectMutexBase` и классов `classes`, нужные их тестам
    и `setUp` стенда, транзитивно; имена модуля из `MUTEX_MODULE_NAMES`,
    которые они читают)."""
    methods = {}
    for cls in (MUTEX_BASE, *classes):
        for name, func in class_methods(tree, cls).items():
            if not name.startswith("test") and name != "setUp":
                methods[name] = func
    roots = [class_method(tree, MUTEX_BASE, "setUp")]
    for cls in classes:
        roots += [f for n, f in class_methods(tree, cls).items()
                  if n.startswith("test")]
    need, module_names, queue = set(), set(), list(roots)
    while queue:
        node = queue.pop()
        module_names |= name_loads(node) & set(MUTEX_MODULE_NAMES)
        for ref in self_refs(node):
            if ref in methods and ref not in need:
                need.add(ref)
                queue.append(methods[ref])
    for name in list(module_names):
        func = top_level(tree, name)
        if isinstance(func, ast.FunctionDef):
            module_names |= name_loads(func) & set(MUTEX_MODULE_NAMES)
    return need, module_names


def class_calls(tree, path: str, cls: str) -> dict:
    """{метод стенда класса `cls` файла `path`: имя функции модуля} —
    помощники, которые тест класса зовёт `self.<метод>`."""
    if path == MUTEX:
        calls = {}
        for owner in (MUTEX_BASE, cls):
            for name in class_methods(tree, owner):
                if not name.startswith("test") and name != "setUp":
                    calls[name] = MUTEX_RENAME.get(name, name)
        return calls
    calls = {}
    for owner in reversed(class_chain(tree, cls)):
        calls.update(AFTER_HELPERS.get((path, owner), {}))
    return calls


def bare_funcs(calls: dict) -> set[str]:
    return {name for name in calls if name in NO_STAND_FUNCS}


def helper_sources(base_trees: dict, target: str) -> dict:
    """{функция модуля `target`: (файл, класс, метод)} перенесённых помощников."""
    found = {}
    if target in EXTENDED_FILES:
        tree = base_trees[MUTEX]
        classes = [c for c, t in TARGET_OF_CLASS.items() if t == target]
        need, _names = mutex_needs(tree, classes)
        for method in sorted(need):
            if method in MUTEX_NOT_MOVED:
                continue
            owner = next(c for c in (MUTEX_BASE, *classes)
                         if method in class_methods(tree, c))
            found[MUTEX_RENAME.get(method, method)] = (MUTEX, owner, method)
        return found
    for (path, cls), helpers in AFTER_HELPERS.items():
        for method, name in helpers.items():
            found[name] = (path, cls, method)
    return found


_ONE_ARG = {"assertTrue", "assertFalse", "assertIsNone", "assertIsNotNone"}


def is_self_assert(node) -> bool:
    """`self.assertX(…)` — не `assertRaises` и не помощник `assert_fresh`."""
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("assert")
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and not node.func.attr.startswith("assertRaises")
            and node.func.attr not in ASSERT_HELPERS)


def constants(node) -> set:
    found = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and not isinstance(sub.value, bool) \
                and isinstance(sub.value, (str, int, float)):
            found.add(sub.value)
    return found


def assert_calls(tree) -> list[ast.Call]:
    return [n for n in ast.walk(tree) if is_self_assert(n)]


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


def ulid_test(test: BaseTest) -> bool:
    """Тест со случайным ULID из `idgen`: тело обращается к `idgen` или зовёт
    `self.insert(<состояние>)` без явного id (оба `insert` берут id из
    `idgen.new_task_id`)."""
    if "idgen" in name_loads(test.func):
        return True
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
               and n.func.attr == "insert" and isinstance(n.func.value, ast.Name)
               and n.func.value.id == "self" and len(n.args) == 1
               for n in ast.walk(test.func))


def seeded_test(test: BaseTest) -> bool:
    """Тест со случайными входами (AC-5): mutex_by_project, division,
    spec_gate_hint либо тест с ULID из `idgen`."""
    return test.path in (MUTEX, DIVISION, HINT) or ulid_test(test)


def prep_line_nodes(base_trees: dict) -> dict:
    """{файл: [узел утверждения подготовки]} по строкам `PREP_LINES`."""
    found = {}
    for path, lines in PREP_LINES.items():
        for line in lines:
            node = assertion_at(base_trees[path], line)
            if node is None:
                raise LookupError(f"{path}:{line} в базе — не утверждение; "
                                  f"база прочитана не та")
            found.setdefault(path, []).append(node)
    return found


# ------------------------------------------------------ преобразования (ast)

_CMP = {"assertEqual": ast.Eq, "assertNotEqual": ast.NotEq,
        "assertIn": ast.In, "assertNotIn": ast.NotIn,
        "assertIs": ast.Is, "assertIsNot": ast.IsNot,
        "assertLess": ast.Lt, "assertLessEqual": ast.LtE,
        "assertGreater": ast.Gt, "assertGreaterEqual": ast.GtE}


def plain_assert_test(call: ast.Call):
    """Выражение `assert …` для `self.assertX(…)` по соответствию
    требования 12 SPEC; не из перечня — None."""
    name, args = call.func.attr, call.args
    if name in _CMP and len(args) >= 2:
        return ast.Compare(left=args[0], ops=[_CMP[name]()], comparators=[args[1]])
    if name in ("assertIsNone", "assertIsNotNone") and args:
        op = ast.Is() if name == "assertIsNone" else ast.IsNot()
        return ast.Compare(left=args[0], ops=[op],
                           comparators=[ast.Constant(value=None)])
    if name == "assertTrue" and args:
        return args[0]
    if name == "assertFalse" and args:
        return ast.UnaryOp(op=ast.Not(), operand=args[0])
    if name == "assertRegex" and len(args) >= 2:
        return ast.Call(func=ast.Attribute(value=ast.Name(id="re", ctx=ast.Load()),
                                           attr="search", ctx=ast.Load()),
                        args=[args[1], args[0]], keywords=[])
    return None


class _SelfToParam(ast.NodeTransformer):
    """`self.<помощник>(…)` → `<функция>(<стенд>, …)` (помощник без
    стенда — `<функция>(…)`); `self.<помощник без стенда>` → имя функции;
    `self.assertX(…)` как оператор → `assert …` (соответствие требования
    12); прочие `self` → имя стенда."""

    def __init__(self, param: str, calls: dict, bare: set):
        self.param, self.calls, self.bare = param, calls, bare

    def visit_Expr(self, node):
        if is_self_assert(node.value):
            test = plain_assert_test(node.value)
            if test is not None:
                msg = msg_arg(node.value)
                new = ast.Assert(test=test, msg=msg)
                return self.visit(ast.copy_location(new, node))
        self.generic_visit(node)
        return node

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id == "self" and func.attr in self.calls:
            node.args = [self.visit(a) for a in node.args]
            node.keywords = [self.visit(k) for k in node.keywords]
            name = self.calls[func.attr]
            node.func = ast.Name(id=name, ctx=ast.Load())
            if func.attr not in self.bare:
                node.args = [ast.Name(id=self.param, ctx=ast.Load()), *node.args]
            return node
        self.generic_visit(node)
        return node

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == "self" \
                and node.attr in self.bare:
            return ast.copy_location(
                ast.Name(id=self.calls[node.attr], ctx=node.ctx), node)
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


def _clean(node):
    """Копия узла без позиций — для сравнения `ast.dump`."""
    node = copy.deepcopy(node)
    for sub in ast.walk(node):
        for attr in ("lineno", "col_offset", "end_lineno", "end_col_offset"):
            if hasattr(sub, attr):
                setattr(sub, attr, None)
    return node


clean = _clean


def _dump_body(body: list) -> str:
    return ast.dump(_clean(ast.Module(body=body, type_ignores=[])))


def translated_body(method, calls: dict, param: str,
                    drop_super: bool = False) -> str:
    """`ast.dump` тела метода, переведённого в функцию модуля."""
    node = copy.deepcopy(method)
    body = strip_docstring(node.body)
    if drop_super:
        body = [s for s in body if not _is_super_setup(s)]
    trans = _SelfToParam(param, calls, bare_funcs(calls))
    body = [trans.visit(s) for s in body]
    return _dump_body(body)


def body_dump(func, drop_trailing_return: bool = False) -> str:
    body = strip_docstring(copy.deepcopy(func).body)
    if drop_trailing_return and body:
        last = body[-1]
        if isinstance(last, ast.Return) or (
                isinstance(last, ast.Expr)
                and isinstance(last.value, (ast.Yield, ast.YieldFrom))):
            body = body[:-1]
    return _dump_body(body)


def trailing_return_name(func) -> str | None:
    """Имя в хвостовом `return <имя>` тела; иначе None."""
    body = strip_docstring(func.body)
    if body and isinstance(body[-1], ast.Return) and \
            isinstance(body[-1].value, ast.Name):
        return body[-1].value.id
    return None


def rest_args_dump(args: ast.arguments, drop_first: bool) -> str:
    node = copy.deepcopy(args)
    if drop_first:
        node.args = node.args[1:]
    return ast.dump(_clean(node))


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
    """Функции-тесты, в которые перенесён исходный тест `name`: функция с
    тем же именем, а если её нет — функции, имя которых содержит его."""
    exact = [f for f in funcs if f.name == name]
    return exact or [f for f in funcs if name in f.name]


def compare_operands(tree) -> list[tuple[str, set]]:
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        lits = set()
        for operand in [node.left, *node.comparators]:
            lits |= constants(operand)
        found.append((type(node.ops[0]).__name__, lits))
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
        return (func.attr.startswith("assert") and func.attr not in ASSERT_HELPERS) \
            or func.attr in ("fail", "raises")
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


def _calls_helper(func, name: str) -> bool:
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name) and target.id == name:
                return True
            if isinstance(target, ast.Attribute) and target.attr == name:
                return True
    return False


def site_ok(tree, line: int, test_func, prep_names=(), prep_forms=(),
            canon=None) -> bool:
    """Строка `line` — в утверждении, внутри функции-теста `test_func` либо
    внутри помощника проверки (`assert_fresh`), который она зовёт; не
    внутри фикстуры, `setUp` и помощника подготовки `prep_names`; не
    утверждение подготовки (нормальная форма из `prep_forms`)."""
    if tree is None:
        return False
    node = assertion_at(tree, line)
    if node is None:
        return False
    chain = function_chain(tree, line)
    names = [f.name for f in chain]
    if any(is_fixture(f) or f.name in prep_names or f.name == "setUp"
           for f in chain):
        return False
    if test_func.name in names:
        if prep_forms and canon is not None and normal_form(node, canon) in prep_forms:
            return False
        return True
    return any(name in names and _calls_helper(test_func, name)
               for name in ASSERT_HELPERS)


# --------------------------------------- нормальная форма утверждения

class Canon(ast.NodeTransformer):
    """Общая форма операндов: стенд (`self`, параметры функции-теста) →
    `STAND`; `self.<помощник>(…)` → `<функция>(STAND, …)`; `self.<помощник
    без стенда>` → имя функции; локальные имена функции модуля,
    переименованные при переносе (`locals_`: новое → прежнее), — прежним
    именем."""

    def __init__(self, stands: set, calls: dict, locals_: dict | None = None):
        self.stands, self.calls = stands, calls
        self.bare = bare_funcs(calls)
        self.locals = locals_ or {}

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id == "self" and func.attr in self.calls:
            node.args = [self.visit(a) for a in node.args]
            node.keywords = [self.visit(k) for k in node.keywords]
            node.func = ast.Name(id=self.calls[func.attr], ctx=ast.Load())
            if func.attr not in self.bare:
                node.args = [ast.Name(id="STAND", ctx=ast.Load()), *node.args]
            return node
        self.generic_visit(node)
        return node

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == "self" \
                and node.attr in self.bare:
            return ast.Name(id=self.calls[node.attr], ctx=ast.Load())
        self.generic_visit(node)
        return node

    def visit_Name(self, node):
        if node.id == "self" or node.id in self.stands:
            return ast.Name(id="STAND", ctx=ast.Load())
        return ast.Name(id=self.locals.get(node.id, node.id), ctx=ast.Load())


def dump_canon(node, canon: Canon) -> str:
    return ast.dump(_clean(canon.visit(copy.deepcopy(node))),
                    annotate_fields=False)


def normal_form(node, canon: Canon):
    """Нормальная форма утверждения (требование 12, решение 5 ANSWER-1):
    `assertX(a, b)` ↔ `assert a <op> b`, `assertTrue(x)` ↔ `assert x`,
    `assertFalse(x)` ↔ `assert not x`, `assertIsNone(x)` ↔ `assert x is
    None`, `assertIsNotNone(x)` ↔ `assert x is not None`, `assertRegex(t, p)`
    ↔ `assert re.search(p, t)`; сообщение отбрасывается."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr.startswith("assert"):
        test = plain_assert_test(node)
        if test is None:
            return ("other", ast.dump(_clean(node)))
        node = ast.Assert(test=test, msg=None)
    if isinstance(node, ast.Assert):
        test = node.test
        if isinstance(test, ast.Compare) and len(test.ops) == 1:
            return ("cmp", type(test.ops[0]).__name__, dump_canon(test.left, canon),
                    dump_canon(test.comparators[0], canon))
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            return ("false", dump_canon(test.operand, canon))
        return ("true", dump_canon(test, canon))
    return ("other", ast.dump(_clean(node)))


def message_of(node):
    """Сообщение утверждения: `msg` у `self.assertX`, второй операнд у
    `assert`; нет — None."""
    if isinstance(node, ast.Assert):
        return node.msg
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return msg_arg(node)
    return None


def base_canon(tree, path: str, cls: str) -> Canon:
    return Canon(set(), class_calls(tree, path, cls))


def local_names(func) -> set[str]:
    return {n.id for n in ast.walk(func) if isinstance(n, ast.Name)
            and isinstance(n.ctx, ast.Store)}


def local_renames(base_func, base_c: Canon, new_func, new_params: set) -> dict:
    """{новое имя: прежнее} локальных переменных, переименованных при
    переносе: присваивание того же значения (по общей форме) имени, которого
    нет среди локальных исходного теста, тогда как прежнего имени нет среди
    локальных функции модуля (`rows`/`before` с равным значением — не
    переименование)."""
    plain = Canon(new_params, {})
    base_locals, new_locals = local_names(base_func), local_names(new_func)
    old = {}
    for node in ast.walk(base_func):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            old.setdefault(dump_canon(node.value, base_c), node.targets[0].id)
    found = {}
    for node in ast.walk(new_func):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            want = old.get(dump_canon(node.value, plain))
            if want and want != node.targets[0].id and want not in new_locals \
                    and node.targets[0].id not in base_locals:
                found[node.targets[0].id] = want
    return found


def new_canon(func, base_func=None, base_c: Canon | None = None) -> Canon:
    """Нормализатор функции модуля: её параметры — стенд; при переданном
    исходном тесте — с картой переименованных локальных имён."""
    params = {a.arg for a in func.args.args}
    renames = local_renames(base_func, base_c, func, params) \
        if base_func is not None else {}
    return Canon(params, {}, renames)


def self_assertions(func) -> list:
    """Утверждения исходного метода: `self.assert*` (кроме `assertRaises`)."""
    return [n for n in ast.walk(func) if is_self_assert(n)]


def plain_assertions(func) -> list:
    return [n for n in ast.walk(func) if isinstance(n, ast.Assert)]
