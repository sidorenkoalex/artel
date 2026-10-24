"""Общий разбор планки задачи 01M5QAEPC6RF097YQ43T3Y56D9 (волна 2а-1б сведения
тестов: 42 теста `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py` —
функциями в `tests/test_outcome_gate_module.py`).

Только чистые функции и вызовы git по переданному репозиторию: модуль не
импортирует `_pult` — значения выкладки (корень рабочей копии, база диффа,
репозиторий и ревизия ссылки документов) передают сами тесты.

Соглашения разбора PLAN.md, которых держится вся планка:

- раздел — заголовок markdown (`#`…`######`) вне ограждения кода; строки
  шапки таблицы `mutation-run` (`# mutation-run №…`, `# источник патчей:`,
  `# ревизия прогона:`, `# тесты:`, `# патч …`) заголовками не считаются;
  раздел длится до следующего заголовка того же или более высокого уровня;
- таблица `mutation-run` — текст, напечатанный командой
  (`orchestrator/mutation_run.py::_header`, `_Run.row`): шапка из строк
  `# …` (в том числе `# рабочих процессов: <n>`), строка колонок
  `номер<TAB>исход<TAB>узлы` и строки
  `<номер><TAB><исход><TAB><узлы через запятую>`; при делении набора
  `--patches` таблиц в разделе несколько, у мутации берётся её последняя
  строка в порядке текста;
- ссылка на мутацию в тексте PLAN — имя патча `mutation-<nnn>` (с `.diff`
  или без) либо `мутация <n>` / `мутация №<n>` (любая форма слова);
- ссылка на тест исходных файлов — `<Класс>::<метод>`, с префиксом
  `tests/<файл>.py::` или без него; ссылка на узел нового файла —
  `test_outcome_gate_module.py::<функция>` (с префиксом `tests/` или без,
  с вариантом `[<вариант>]` или без — без варианта она покрывает все
  варианты функции);
- соответствие имён «до → после» — строка PLAN вне таблиц, где стоят
  ссылка на тест исходного файла и ссылка на функцию нового файла;
- упавшее утверждение — ссылка `tests/<файл>.py:<строка>` (как в логе
  прогона патча `mutation-run`) в той же строке PLAN, что ссылка на
  мутацию и на убивший узел;
- сопоставление «тест — мутация» и перечни (удалённые дубли, узлы,
  убитые падением подготовки, находки) — строки PLAN вне таблиц, где
  ссылка на тест (узел) и ссылка на мутацию стоят в ОДНОЙ строке;
  удалённые дубли — строки раздела, в заголовке которого есть слово
  «дубл…»; находки — строки со словом «находк…» либо строки раздела, в
  заголовке которого оно есть; узлы, убитые падением подготовки, — строки
  со словом `setUp` или «подготовк…».
"""
import ast
import copy
import os
import re
import subprocess
from pathlib import Path

OUTCOME_FILE = "tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py"
# Исходный файл свода (его тесты и заявки — предмет мутаций); на ветке
# удаляется (требование 15).
SOURCE_FILES = (OUTCOME_FILE,)
NEW_FILE = "tests/test_outcome_gate_module.py"
SANDBOX_FILE = "tests/outcome_gate_sandbox.py"
# Файлы, где «после» может лежать упавшее утверждение.
AFTER_FILES = (NEW_FILE, SANDBOX_FILE)
IMPORTERS = (
    "tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py",
    "tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py",
    "tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py",
)
# Файлы волны 2б-3: не меняются (требование 16).
WAVE_2B3_FILES = (
    "tests/report_outcome_sandbox.py",
    "tests/test_report_outcome_module.py",
    "tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py",
    "tests/test_component_report_gates.py",
)
MAP_FILE = "docs/codebase-map.md"
SANDBOX_MODULE = "tests.outcome_gate_sandbox"
CLAIM = "Ловит мутацию"
CLAIM_COUNT = 42
# Тесты модуля волны 2а-1а на базе (AC-6: не меняются).
BASE_MODULE_TESTS = 11

# Методы подготовки песочницы с утверждениями: падение в них — не
# доказательство (AC-4).
PREP_METHODS = ("setUp", "in_dev_task", "artel_in_dev_task", "operator_mandate")

# Помощники AC-8: имя функции модуля → (файл, класс, метод) источника.
HELPERS = {
    "refusal": (SANDBOX_FILE, "OutcomeGateSandbox", "refusal"),
    "no_gate_refusal": (SANDBOX_FILE, "OutcomeGateSandbox", "no_gate_refusal"),
    "assert_no_gate": (OUTCOME_FILE, "Ac1OutOfBoundsTest", "assert_no_gate"),
    "assert_prepare": (OUTCOME_FILE, "Ac4PrepareTest", "assert_prepare"),
    "prepared": (OUTCOME_FILE, "Ac4PrepareTest", "prepared"),
    "broken_task": (OUTCOME_FILE, "Ac11MandateTest", "broken_task"),
}
# Помощники, утверждающие исход: последний параметр `case: str = ""`.
OUTCOME_HELPERS = ("refusal", "no_gate_refusal", "assert_no_gate",
                   "assert_prepare")
# Имя метода `self.<метод>` внутри тела → имя функции модуля.
HELPER_CALLS = {name: name for name in HELPERS}
# Методы песочницы с утверждениями (AC-7: фикстура их не зовёт).
ASSERTING = ("in_dev_task", "artel_in_dev_task", "operator_mandate",
             *OUTCOME_HELPERS)
CASE = "case"

KILLED = "убита"
SURVIVED = "не убита"
COLLECTION = "ошибка сбора, импорта или setup"
LIMIT_OUTCOMES = ("оборвана по пределу", "не прогнана (предел)")
OUTCOMES = (KILLED, SURVIVED, COLLECTION, "итог неизвестен",
            *LIMIT_OUTCOMES, "патч не применяется", "патч трогает тесты")

MAX_PART = 15
MAX_PART_WORKERS_4 = 7

PATCH_NAME = re.compile(r"^mutation-(\d{3,})\.diff$")
# Справочная копия таблицы `--copy-table` (`mutation_run._copy_path`).
COPY_NAME = re.compile(r"^mutation-run-(\d+)\.tsv$")

_HEAD = re.compile(r"^# mutation-run №(\d+) задачи (\S+)$")
_SOURCE = re.compile(r"^# источник патчей: (\S.*)$")
_REVISION = re.compile(r"^# ревизия прогона: (base|head|worktree) ([0-9a-f]{7,64})$")
_TESTS = re.compile(r"^# тесты: (\S.*)$")
_WORKERS = re.compile(r"^# рабочих процессов: (\S+)$")
_PATCH = re.compile(r"^# патч (\d+) (\S+) sha256 ([0-9a-f]{64})$")
_COLUMNS = "номер\tисход\tузлы"
_ROW = re.compile(r"^(\d+)\t([^\t]+)(?:\t([^\t]*))?$")
_TABLE_LINE = (_HEAD, _SOURCE, _REVISION, _TESTS, _WORKERS, _PATCH)
_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")

_REF = (re.compile(r"mutation-0*(\d+)(?!\d)"),
        re.compile(r"[Мм]утаци[а-яё]*\s+№?\s*0*(\d+)(?!\d)"))
_TEST_KEY = re.compile(
    r"(?<![\w.])(?:tests/[\w./-]+\.py::)?([A-Za-z_]\w*)::(test\w*)")
_AFTER_REF = re.compile(
    r"test_outcome_gate_module\.py::(test\w*)(\[[^\]\s]*\])?")
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


def docs_entries(docs_repo, revision: str, task_id: str) -> list[str]:
    """Имена первого уровня `tasks/<id>/` ссылки документов (файлы и каталоги)."""
    rel = f"tasks/{task_id}/"
    out = git_out(docs_repo, "ls-tree", "-z", "--name-only", revision, "--", rel)
    return [p[len(rel):] for p in out.split("\0") if p.startswith(rel)]


def docs_typed_entries(docs_repo, revision: str,
                       task_id: str) -> list[tuple[str, str]]:
    """[(тип git-объекта, имя)] первого уровня `tasks/<id>/` ссылки
    документов: `blob` — файл, `tree` — подкаталог."""
    rel = f"tasks/{task_id}/"
    out = git_out(docs_repo, "ls-tree", "-z", revision, "--", rel)
    found = []
    for item in out.split("\0"):
        if not item:
            continue
        meta, _tab, path = item.partition("\t")
        if path.startswith(rel):
            found.append((meta.split()[1], path[len(rel):]))
    return found


def patch_names(entries: list[str]) -> dict[int, str]:
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


# ------------------------------------------------------------- разделы PLAN

def _is_table_line(line: str) -> bool:
    return any(p.match(line) for p in _TABLE_LINE)


def _headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """[(индекс строки, уровень, текст)] заголовков вне ограждений кода."""
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
            if not _is_table_line(line) and line != _COLUMNS
            and not _ROW.match(line)]


def refs(line: str) -> set[int]:
    """Номера мутаций, на которые ссылается строка."""
    found = set()
    for pattern in _REF:
        found.update(int(m) for m in pattern.findall(line))
    return found


def test_keys(line: str) -> set[str]:
    """Ссылки строки на тесты исходных файлов в виде `<Класс>::<метод>`."""
    return {f"{c}::{m}" for c, m in _TEST_KEY.findall(line)}


def after_refs(line: str) -> set[tuple[str, str]]:
    """Ссылки строки на узлы нового файла: {(функция, вариант или "")}."""
    return {(func, variant) for func, variant in _AFTER_REF.findall(line)}


def transfer_map(plan: str) -> dict[str, set[str]]:
    """{`<Класс>::<метод>` исходного теста: функции нового файла} по строкам
    PLAN вне таблиц, где стоят обе ссылки."""
    mapped: dict[str, set[str]] = {}
    for line in prose_lines(plan):
        funcs = {func for func, _variant in after_refs(line)}
        if not funcs:
            continue
        for key in test_keys(line):
            mapped.setdefault(key, set()).update(funcs)
    return mapped


def file_lines(line: str) -> list[tuple[str, int]]:
    """Ссылки строки вида `tests/<файл>.py:<строка>`."""
    return [(path, int(n)) for path, n in _FILE_LINE.findall(line)]


def node_key(node: str) -> str:
    """`tests/<файл>.py::<Класс>::<метод>` → `<Класс>::<метод>`."""
    keys = test_keys(node)
    return next(iter(keys)) if len(keys) == 1 else node


def after_node_parts(node: str) -> tuple[str, str]:
    """`tests/test_outcome_gate_module.py::<функция>[<вариант>]` →
    (функция, `[<вариант>]` или "")."""
    tail = node.rsplit("::", 1)[-1]
    func, bracket, rest = tail.partition("[")
    return func, (bracket + rest) if bracket else ""


def after_marked(node: str, marks: set[tuple[str, str]]) -> bool:
    """Узел нового файла попадает под отметку: та же функция и тот же
    вариант, либо отметка без варианта."""
    func, variant = after_node_parts(node)
    return (func, "") in marks or (func, variant) in marks


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
        # Строки таблицы как в тексте: от `# mutation-run №…` до последней
        # строки мутации; `start` — индекс первой строки в тексте.
        self.lines: list[str] = []
        self.start = 0


def tables(text: str) -> tuple[list[Table], list[str]]:
    """(таблицы `mutation-run` текста, ошибки формата шапки)."""
    lines = text.split("\n")
    found, errors = [], []
    i = 0
    while i < len(lines):
        head = _HEAD.match(lines[i])
        if not head:
            i += 1
            continue
        table = Table()
        table.run_no, table.task = int(head.group(1)), head.group(2)
        table.start = i
        i += 1
        expected = ((_SOURCE, "источник патчей"), (_REVISION, "ревизия прогона"),
                    (_TESTS, "тесты"))
        broken = False
        for pattern, what in expected:
            match = pattern.match(lines[i]) if i < len(lines) else None
            if not match:
                errors.append(f"таблица №{table.run_no}: нет строки шапки "
                              f"«# {what}: …» на своём месте (строка "
                              f"{lines[i] if i < len(lines) else '<конец>'!r})")
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
        workers = _WORKERS.match(lines[i]) if i < len(lines) else None
        if workers:
            table.workers = workers.group(1)
            i += 1
        while i < len(lines) and _PATCH.match(lines[i]):
            match = _PATCH.match(lines[i])
            table.patches[int(match.group(1))] = (match.group(2), match.group(3))
            i += 1
        if i >= len(lines) or lines[i] != _COLUMNS:
            errors.append(f"таблица №{table.run_no}: после строк патчей нет "
                          f"строки колонок {_COLUMNS!r}")
            continue
        i += 1
        while i < len(lines) and _ROW.match(lines[i]):
            match = _ROW.match(lines[i])
            nodes = [n for n in (match.group(3) or "").split(",") if n]
            table.rows.append((int(match.group(1)), match.group(2), nodes))
            i += 1
        table.lines = lines[table.start:i]
        found.append(table)
    return found, errors


def contains_block(text: str, block: list[str]) -> bool:
    """Строки `block` стоят в `text` подряд и дословно."""
    lines = text.split("\n")
    width = len(block)
    return width > 0 and any(lines[k:k + width] == block
                             for k in range(len(lines) - width + 1))


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
        self.key = f"{cls}::{func.name}"
        self.claim = CLAIM in (ast.get_docstring(func) or "")


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


# Число смысловых позиционных аргументов `self.assert*`: дальше — msg.
_ONE_ARG = {"assertTrue", "assertFalse", "assertIsNone", "assertIsNotNone"}


def _is_self_assert(node) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("assert")
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and not node.func.attr.startswith("assertRaises"))


def is_method_assert(node) -> bool:
    """Вызов `<что угодно>.assert*(...)` (кроме `assertRaises*`)."""
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


def assertion_literals(tree) -> set:
    """Литералы (строки и числа) смысловых аргументов `self.assert*`."""
    found = set()
    for call in assert_calls(tree):
        for arg in semantic_args(call):
            found |= constants(arg)
    return found


def assertion_constant_names(tree) -> set:
    """Имена констант модуля (`ВЕРХНИЙ_РЕГИСТР`) в смысловых аргументах
    `self.assert*`."""
    found = set()
    for call in assert_calls(tree):
        for arg in semantic_args(call):
            found |= {n.id for n in ast.walk(arg) if isinstance(n, ast.Name)
                      and re.fullmatch(r"[A-Z][A-Z0-9_]*", n.id)}
    return found


def assertion_kinds(tree) -> set[str]:
    return {call.func.attr for call in assert_calls(tree)}


def equality_literals(tree) -> tuple[set, set]:
    """(литералы аргументов равенства `assertEqual`/`assert*Equal` кроме
    `assertCountEqual`/`assertNotEqual`, литералы аргументов `assertIn`/
    `assertNotIn`)."""
    equal, member = set(), set()
    for call in assert_calls(tree):
        name = call.func.attr
        lits = set()
        for arg in semantic_args(call):
            lits |= constants(arg)
        if name.endswith("Equal") and name not in ("assertCountEqual",
                                                   "assertNotEqual",
                                                   "assertAlmostEqual",
                                                   "assertNotAlmostEqual"):
            equal |= lits
        elif name in ("assertIn", "assertNotIn"):
            member |= lits
    return equal, member


def text_raises_sites(tree) -> int:
    """Места исходного файла, где проверялся текст исключения:
    `with self.assertRaises(E) as x` с чтением `x.exception` в той же
    функции и вызовы `assertRaisesRegex`/`assertRaisesRegexp`."""
    count = 0
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        read = {n.value.id for n in ast.walk(func)
                if isinstance(n, ast.Attribute) and n.attr == "exception"
                and isinstance(n.value, ast.Name)}
        for node in ast.walk(func):
            if isinstance(node, ast.With):
                for item in node.items:
                    call = item.context_expr
                    if isinstance(call, ast.Call) and \
                            isinstance(call.func, ast.Attribute) and \
                            call.func.attr == "assertRaises" and \
                            isinstance(item.optional_vars, ast.Name) and \
                            item.optional_vars.id in read:
                        count += 1
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr in ("assertRaisesRegex",
                                           "assertRaisesRegexp"):
                count += 1
    return count


def class_method(tree, cls: str, method: str):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and item.name == method:
                    return item
    return None


def top_level(tree, lines: tuple[int, int]) -> list:
    """Утверждения верхнего уровня модуля, начинающиеся в строках `lines`."""
    first, last = lines
    return [n for n in tree.body if first <= n.lineno <= last]


def bound_names(node) -> list[str]:
    """Имена, которые связывает утверждение верхнего уровня модуля."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return [(a.asname or a.name).split(".")[0] for a in node.names]
    targets = []
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    names = []
    for target in targets:
        names += [n.id for n in ast.walk(target) if isinstance(n, ast.Name)]
    return names


# ------------------------------------------------------ преобразования (ast)

class _SelfToParam(ast.NodeTransformer):
    """`self.<помощник>(…)` → `<функция>(<стенд>, …)`; прочие `self` →
    имя стенда."""

    def __init__(self, param: str, calls: dict):
        self.param, self.calls = param, calls

    def visit_Call(self, node):
        self.generic_visit(node)
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id == self.param and func.attr in self.calls:
            node.func = ast.Name(id=self.calls[func.attr], ctx=ast.Load())
            node.args = [ast.Name(id=self.param, ctx=ast.Load()), *node.args]
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


class _AddCase(ast.NodeTransformer):
    """Приписывает `case` спереди к тексту сообщения каждого
    `<стенд>.assert*` (позиционный аргумент после смысловых или `msg=`) и
    передаёт `case=case` во вложенные вызовы помощников исхода."""

    def __init__(self, param: str, outcome_helpers):
        self.param, self.outcome = param, set(outcome_helpers)

    def visit_Call(self, node):
        self.generic_visit(node)
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id == self.param and func.attr.startswith("assert") \
                and not func.attr.startswith("assertRaises"):
            count = 1 if func.attr in _ONE_ARG else 2
            if len(node.args) > count:
                node.args[count] = _prefixed(node.args[count])
            for kw in node.keywords:
                if kw.arg == "msg":
                    kw.value = _prefixed(kw.value)
        elif isinstance(func, ast.Name) and func.id in self.outcome:
            node.keywords.append(ast.keyword(arg=CASE,
                                             value=ast.Name(id=CASE, ctx=ast.Load())))
        return node


def _prefixed(msg):
    return ast.BinOp(left=ast.Name(id=CASE, ctx=ast.Load()), op=ast.Add(),
                     right=msg)


class _FlattenAdd(ast.NodeTransformer):
    """Цепочка `a + b + c` при любой расстановке скобок → один вызов
    `__add__(a, b, c)`: `case + x + y` и `case + (x + y)` сравниваются
    равными."""

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if not isinstance(node.op, ast.Add):
            return node
        parts = []
        for side in (node.left, node.right):
            if isinstance(side, ast.Call) and isinstance(side.func, ast.Name) \
                    and side.func.id == "__add__":
                parts += side.args
            else:
                parts.append(side)
        return ast.Call(func=ast.Name(id="__add__", ctx=ast.Load()),
                        args=parts, keywords=[])


def _canonical(body: list) -> str:
    module = ast.Module(body=copy.deepcopy(body), type_ignores=[])
    return ast.dump(_FlattenAdd().visit(module))


def expected_helper_body(method, param: str, calls: dict,
                         with_case: bool) -> str:
    """Каноничный `ast.dump` тела метода-источника, переведённого в функцию
    модуля: `self.` → стенд, вызовы помощников перечня — голым именем со
    стендом первым аргументом; у помощника исхода (`with_case`) — `case`
    спереди к каждому тексту сообщения и `case=case` во вложенные вызовы
    помощников исхода."""
    node = _SelfToParam(param, calls).visit(copy.deepcopy(method))
    if with_case:
        node = _AddCase(param, OUTCOME_HELPERS).visit(node)
    return _canonical(strip_docstring(node.body))


def body_dump(func) -> str:
    return _canonical(strip_docstring(copy.deepcopy(func).body))


def params(args: ast.arguments) -> list[tuple[str, str, str]]:
    """[(имя, дамп аннотации, дамп умолчания)] позиционных и только
    именованных параметров по порядку."""
    positional = [*args.posonlyargs, *args.args]
    pad = [None] * (len(positional) - len(args.defaults))
    found = []
    for arg, default in zip(positional, pad + list(args.defaults)):
        found.append((arg.arg, ast.dump(arg.annotation) if arg.annotation else "",
                      ast.dump(default) if default is not None else ""))
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        found.append((arg.arg, ast.dump(arg.annotation) if arg.annotation else "",
                      ast.dump(default) if default is not None else ""))
    return found


CASE_PARAM = (CASE, ast.dump(ast.Name(id="str", ctx=ast.Load())),
              ast.dump(ast.Constant(value="")))


# ------------------------------------------------------- новый файл (ast)

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


def parametrize_decorators(func) -> list[ast.Call]:
    return [d for d in func.decorator_list
            if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
            and d.func.attr == "parametrize"]


def parametrize_names(func) -> set[str]:
    names = set()
    for deco in parametrize_decorators(func):
        if not deco.args:
            continue
        first = deco.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            names |= {n.strip() for n in first.value.split(",") if n.strip()}
        elif isinstance(first, (ast.List, ast.Tuple)):
            names |= {e.value for e in first.elts
                      if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    return names


def is_pytest_raises(node) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "raises"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "pytest")


def non_docstring_constants(tree) -> set:
    """Литералы файла без докстрингов модуля, классов и функций."""
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
    """[(вид сравнения, литералы операндов)] каждого `ast.Compare` и
    каждого вызова `<стенд>.assert*Equal`: вид — `eq` (==, !=, is,
    `assertEqual`), `in` (in, not in), `order` (<, <=, >, >=)."""
    found = []
    for node in ast.walk(tree):
        if is_method_assert(node) and node.func.attr in ("assertEqual",
                                                         "assertNotEqual"):
            lits = set()
            for arg in node.args[:2]:
                lits |= constants(arg)
            found.append(("eq", lits))
            continue
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


def parametrize_columns(tree) -> list[list]:
    """Столбцы литеральных значений `@pytest.mark.parametrize`: для каждого
    декоратора со списком/кортежем литералов — список значений каждого
    имени параметра."""
    columns = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for deco in parametrize_decorators(node):
            if len(deco.args) < 2:
                continue
            values = deco.args[1]
            if not isinstance(values, (ast.List, ast.Tuple)):
                continue
            try:
                literal = ast.literal_eval(values)
            except (ValueError, TypeError, SyntaxError):
                continue
            names = deco.args[0]
            width = 1
            if isinstance(names, ast.Constant) and isinstance(names.value, str):
                width = len([n for n in names.value.split(",") if n.strip()])
            elif isinstance(names, (ast.List, ast.Tuple)):
                width = len(names.elts)
            if width == 1:
                columns.append(list(literal))
            else:
                for k in range(width):
                    columns.append([row[k] for row in literal
                                    if isinstance(row, (list, tuple))
                                    and len(row) > k])
    return columns


# ------------------------------------------- место упавшего утверждения

def _is_assertion_node(node) -> bool:
    if isinstance(node, ast.Assert):
        return True
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr.startswith("assert") or func.attr in ("fail", "raises")
    return isinstance(func, ast.Name) and func.id == "fail"


def assertion_site(text: str, line: int) -> tuple[bool, list[str]]:
    """(строка `line` лежит в утверждении, имена объемлющих функций —
    от внешней к внутренней)."""
    tree = ast.parse(text)
    inside = any(_is_assertion_node(n) and n.lineno <= line <= (n.end_lineno or n.lineno)
                 for n in ast.walk(tree))
    chain = sorted((n for n in ast.walk(tree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.lineno <= line <= (n.end_lineno or n.lineno)),
                   key=lambda n: (n.lineno, -(n.end_lineno or n.lineno)))
    return inside, chain


def in_preparation(chain: list) -> bool:
    """Объемлющая функция — метод подготовки песочницы или фикстура."""
    return any(f.name in PREP_METHODS or is_fixture(f) for f in chain)
