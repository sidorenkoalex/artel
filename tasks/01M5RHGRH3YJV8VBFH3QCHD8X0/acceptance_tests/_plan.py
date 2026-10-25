"""Общий разбор планки волны 3м-2б сведения тестов: тесты шести
долгоживущих файлов `merge_after` (база ветки) — `answer`, `guard`,
`plan`, `spec_gate`, `status_show` (SPEC 01M44EP0D47F498TEE08MNGBYT) и
`new_declares` (SPEC 01M45D29BQJE8FJYJA4JQWSYFZ) — дописываются в конец
`tests/test_merge_after_module.py` (HEAD ветки).

Только чистые функции и вызовы git по переданному репозиторию: модуль не
импортирует `_pult` — значения выкладки (корень рабочей копии, база диффа,
репозиторий и ревизия ссылки документов) передают сами тесты.

Соглашения разбора PLAN.md, которых держится вся планка (те же, что у
планок волн 3м-1 и 3м-2):

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
  `tests/<файл>.py::` или без него; ссылка на функцию модуля —
  `test_merge_after_module.py::<функция>` (с префиксом `tests/` или без);
- строка падения — ссылки `tests/<файл>.py:<строка>` (как в логе прогона
  патча) в той же строке PLAN, что ссылка на мутацию и на убивший тест
  (функцию): упавшее утверждение и строка вызова в теле теста (у
  утверждения в самом теле теста — одна и та же строка); исходный файл
  читается из базы ветки, модуль — из HEAD;
- сопоставление «тест — мутация» и перечни (удалённые дубли, находки) —
  строки PLAN вне таблиц, где ссылка на тест и ссылка на мутацию стоят в
  ОДНОЙ строке; удалённые дубли — строки раздела, в заголовке которого
  есть слово «дубл…»; находки — строки со словом «находк…» либо строки
  раздела, в заголовке которого оно есть;
- убийца «до», убивающий мутацию лишь на части зёрен (требование 13 SPEC
  выводит его из сравнения «до/после»), назван в строке PLAN со ссылкой
  на мутацию, его `<Класс>::<метод>` и словами «на части зёрен» (любая
  форма слова «часть», «зёрен»/«зерен»).
"""
import ast
import copy
import os
import re
import subprocess
from pathlib import Path

ANSWER = "tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py"
GUARD = "tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py"
PLAN_SRC = "tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py"
SPEC_GATE = "tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py"
STATUS_SHOW = "tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py"
NEW_DECLARES = "tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py"
SOURCE_FILES = (ANSWER, GUARD, PLAN_SRC, SPEC_GATE, STATUS_SHOW, NEW_DECLARES)
MODULE = "tests/test_merge_after_module.py"
MODULE_FILES = (MODULE,)
MAP_FILE = "docs/codebase-map.md"
FIXTURES_FILE = "tests/fixtures.py"

SPEC_OF = {ANSWER: "01M44EP0D47F498TEE08MNGBYT", GUARD: "01M44EP0D47F498TEE08MNGBYT",
           PLAN_SRC: "01M44EP0D47F498TEE08MNGBYT",
           SPEC_GATE: "01M44EP0D47F498TEE08MNGBYT",
           STATUS_SHOW: "01M44EP0D47F498TEE08MNGBYT",
           NEW_DECLARES: "01M45D29BQJE8FJYJA4JQWSYFZ"}
SPEC_IDS = ("01M44EP0D47F498TEE08MNGBYT", "01M45D29BQJE8FJYJA4JQWSYFZ")

# Префикс имени прежнего файла (требование 9 SPEC).
PREFIX = {ANSWER: "answer", GUARD: "guard", PLAN_SRC: "plan",
          SPEC_GATE: "spec_gate", STATUS_SHOW: "status_show",
          NEW_DECLARES: "new_declares"}
# Класс, чей `setUp` становится фикстурой стенда, и параметр фикстуры
# (требование 10 SPEC).
SETUP_CLASS = {ANSWER: "AnswerMandateSandbox", GUARD: "GuardMergeAfterFieldTest",
               PLAN_SRC: "PlanChannelSandbox", SPEC_GATE: "MergeAfterSpecGateSandbox",
               STATUS_SHOW: "DependencyOutputSandbox",
               NEW_DECLARES: "DeclaredMergeAfterSandbox"}
STAND_PARAM = {ANSWER: "real_git", GUARD: "tmp_dir", PLAN_SRC: "light_transition",
               SPEC_GATE: "light_transition", STATUS_SHOW: "light_transition",
               NEW_DECLARES: "light_transition"}
# У `guard_stand` — только первые три строки `setUp` (зерно, print, rng).
SETUP_HEAD = {GUARD: 3}
# Статический метод → функция модуля без параметра стенда.
STATIC_HELPERS = {(PLAN_SRC, "branch_not_behind")}

# Константы, совпадающие по имени и литералу с константой модуля, — не
# переопределяются.
MODULE_SAME = {GUARD: ("FIELD",), SPEC_GATE: ("ZONES",), NEW_DECLARES: ("ZONES",)}
# Одно определение — в разделе первого по порядку прежнего файла.
SHARED_HOME = {"CROCKFORD": SPEC_GATE, "WAIT_PREFIX": STATUS_SHOW, "ids_of": ANSWER}
# Совпадающие по имени с иным значением — с префиксом имени прежнего файла.
CONST_RENAMES = {
    ANSWER: {"MARKER": "ANSWER_MARKER"},
    GUARD: {"SPEC_TEXT": "GUARD_SPEC_TEXT"},
    PLAN_SRC: {"SPEC_TEXT": "PLAN_SPEC_TEXT"},
    SPEC_GATE: {"SPEC_TEXT": "SPEC_GATE_SPEC_TEXT"},
    STATUS_SHOW: {"SPEC_TEXT": "STATUS_SHOW_SPEC_TEXT",
                  "UNFINISHED_STATES": "STATUS_SHOW_UNFINISHED_STATES"},
    NEW_DECLARES: {"UNFINISHED_STATES": "NEW_DECLARES_UNFINISHED_STATES"},
}
# Локальные, совпадающие с именем функции модуля, — переименовываются.
LOCALS_TO_RENAME = ("journal", "task")
# Помощники с утверждениями, которые тест зовёт голым именем (требование 11).
ASSERTING_HELPERS = ("answer_accepted", "answer_assert_refused", "plan_approve_spec",
                     "spec_gate_assert_refused", "status_show_with_dependencies",
                     "status_show_status_line", "new_declares_declared",
                     "new_declares_assert_refused_without_traces",
                     "new_declares_status_line")
# Помощники с ярлыком подслучая (требование 11, AC-12).
CASE_HELPERS = ("answer_accepted", "answer_assert_refused", "plan_approve_spec",
                "plan_prepared_task", "new_declares_declared",
                "new_declares_assert_refused_without_traces")
LABEL_HELPERS = ("plan_rejected_case",)
# Функции волны 3м-2, которыми помощники стендов не заменяются.
WAVE_3M2_HELPERS = ("merge_after_db_insert", "set_deps", "declared_insert",
                    "spec_gate_declared_refusal_spec_text", "new_task", "msg",
                    "divide", "stored_deps", "journal", "task", "declared_path_note",
                    "run_cmd", "live_task", "declared_task", "refusal", "no_code_tree")

CLAIM = "Ловит мутацию"
TEST_COUNT = 33
CLAIM_COUNT = 33
SUBTEST_COUNT = 8
MODULE_BASE_TESTS = 20

# Утверждения, не доказательство (требование 4, AC-4): строки базы.
# Утверждение подготовки, наблюдения, предпосылки или до действия теста.
PREP_ASSERT_LINES = {GUARD: (160,), PLAN_SRC: (160,), SPEC_GATE: (276, 305),
                     STATUS_SHOW: (104, 108, 116), NEW_DECLARES: (180,)}
# Вызовы помощника с утверждениями, которые — подготовка, а не действие.
PREP_CALL_LINES = {ANSWER: (198, 233, 242, 261), NEW_DECLARES: (419,)}
# Помощник с утверждениями результата: (файл, метод) → его вызовы-действия
# доказательство, вызовы `PREP_CALL_LINES` — нет.
RESULT_HELPERS = {(ANSWER, "accepted"), (ANSWER, "assert_refused"),
                  (SPEC_GATE, "assert_refused"), (NEW_DECLARES, "declared"),
                  (NEW_DECLARES, "assert_refused_without_traces")}

# Узлы, способные зациклиться: патч, меняющий их строки, — один в части.
LOOP_NODES = {
    "orchestrator/merge_after.py": ("check", "_cycle_path", "declared_from_tz",
                                    "_mandate_items", "ORDER_LINE",
                                    "_ORDER_LINE_RE", "_ORDER_LIST_END"),
    "scripts/guard.py": ("merge_after_items",),
    "orchestrator/store.py": ("task_id_matches", "resolve_task_id"),
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
_AFTER_REF = re.compile(r"test_merge_after_module\.py::(test\w*)(?!\w|::)(\[[^\]\s]*\])?")
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
            found.setdefault(current, set()).add(max(line_no - 1, 1))
            found.setdefault(current, set()).add(max(line_no, 1))
        elif line.startswith(" "):
            line_no += 1
    return found


def enclosing_names(text: str, line: int) -> set[str]:
    """Имена функций исходного текста, объемлющих строку `line`, и имена
    присваиваний верхнего уровня, покрывающих её."""
    tree = ast.parse(text)
    names = {n.name for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
             and n.lineno <= line <= (n.end_lineno or n.lineno)}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and \
                node.lineno <= line <= (node.end_lineno or node.lineno):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names |= {t.id for t in targets if isinstance(t, ast.Name)}
    return names


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
    """Ссылки строки на функции модуля: {(файл, функция)}."""
    return {(MODULE, func) for func, _v in _AFTER_REF.findall(line)}


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


def finding_keys(plan: str) -> set[str]:
    found = set()
    for line in prose_lines(plan):
        if "находк" in line.casefold():
            found |= test_keys(line)
    for text in sections(plan, "находк"):
        for line in prose_lines(text):
            found |= test_keys(line)
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
    body = r"[   ]?".join(groups)
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
        self.target = MODULE


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


def class_nodes(tree) -> list:
    return [n for n in tree.body if isinstance(n, ast.ClassDef)]


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


def helper_methods(tree) -> dict:
    """{метод: (класс, узел)} — методы классов файла, кроме `test*` и `setUp`."""
    found = {}
    for cls in class_nodes(tree):
        for item in cls.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and not item.name.startswith("test") and item.name != "setUp":
                found[item.name] = (cls.name, item)
    return found


def file_calls(tree, path: str) -> dict:
    """{метод файла: функция модуля} — `<префикс>_<метод>`."""
    return {m: f"{PREFIX[path]}_{m}" for m in helper_methods(tree)}


def bare_methods(path: str) -> set[str]:
    return {m for p, m in STATIC_HELPERS if p == path}


def helper_sources(base_trees: dict) -> dict:
    """{функция модуля: (файл, класс, метод)} перенесённых помощников."""
    found = {}
    for path in SOURCE_FILES:
        for method, (cls, _node) in helper_methods(base_trees[path]).items():
            found[f"{PREFIX[path]}_{method}"] = (path, cls, method)
    return found


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


def top_level_defs(tree, name: str) -> list:
    """Все определения верхнего уровня имени `name` (присваивания, функции,
    классы)."""
    found = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                and node.name == name:
            found.append(node)
        elif isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            found.append(node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and node.target.id == name:
            found.append(node)
    return found


def module_level_names(tree) -> list[str]:
    """Имена констант и функций верхнего уровня (без классов и импортов)."""
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            names += [t.id for t in node.targets if isinstance(t, ast.Name)]
    return names


def self_refs(node) -> set[str]:
    """Имена `self.<имя>` внутри узла."""
    return {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name) and n.value.id == "self"}


def name_loads(node) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


_ONE_ARG = {"assertTrue", "assertFalse", "assertIsNone", "assertIsNotNone"}


def is_self_assert(node) -> bool:
    """`self.assertX(…)` — не `assertRaises` и не помощник `assert_*` файла."""
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("assert")
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and not node.func.attr.startswith("assertRaises")
            and not node.func.attr.startswith("assert_"))


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


# ------------------------------------------------------ преобразования (ast)

_CMP = {"assertEqual": ast.Eq, "assertNotEqual": ast.NotEq,
        "assertIn": ast.In, "assertNotIn": ast.NotIn,
        "assertIs": ast.Is, "assertIsNot": ast.IsNot,
        "assertLess": ast.Lt, "assertLessEqual": ast.LtE,
        "assertGreater": ast.Gt, "assertGreaterEqual": ast.GtE}


def plain_assert_test(call: ast.Call):
    """Выражение `assert …` для `self.assertX(…)` по соответствию
    требования 11 SPEC; не из перечня — None."""
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


class SelfToParam(ast.NodeTransformer):
    """`self.<помощник>(…)` → `<функция>(<стенд>, …)` (статический — без
    стенда); `self.<статический>` → имя функции; `self.assertX(…)` как
    оператор → `assert …`; прочие `self` → имя стенда; имена констант
    файла — по `renames`."""

    def __init__(self, param: str, calls: dict, bare: set, renames: dict):
        self.param, self.calls, self.bare = param, calls, bare
        self.renames = renames

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
            node.func = ast.Name(id=self.calls[func.attr], ctx=ast.Load())
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
        elif node.id in self.renames:
            node.id = self.renames[node.id]
        return node


def strip_docstring(body: list) -> list:
    if body and isinstance(body[0], ast.Expr) and \
            isinstance(body[0].value, ast.Constant) and \
            isinstance(body[0].value.value, str):
        return body[1:]
    return body


def is_super_setup(stmt) -> bool:
    return (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Attribute)
            and stmt.value.func.attr == "setUp"
            and isinstance(stmt.value.func.value, ast.Call)
            and isinstance(stmt.value.func.value.func, ast.Name)
            and stmt.value.func.value.func.id == "super")


def clean(node):
    """Копия узла без позиций — для сравнения `ast.dump`."""
    node = copy.deepcopy(node)
    for sub in ast.walk(node):
        for attr in ("lineno", "col_offset", "end_lineno", "end_col_offset"):
            if hasattr(sub, attr):
                setattr(sub, attr, None)
    return node


def translate(path: str, tree, node, param: str):
    """Копия узла `node` файла `path`, переведённая правилами требований
    9–11: `self.` → `param`, помощники — функции модуля, константы —
    новыми именами, `self.assertX` → `assert`."""
    calls = file_calls(tree, path)
    trans = SelfToParam(param, calls, bare_methods(path), CONST_RENAMES.get(path, {}))
    return trans.visit(copy.deepcopy(node))


def match_nodes(a, b, free: set, mapping: dict) -> bool:
    """Равенство деревьев `a` (перевод источника) и `b` (функция модуля)
    без позиций; имя `Name` из `free` в `a` может быть иным в `b` —
    согласованно по всему дереву (`mapping`: прежнее → новое)."""
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(
            match_nodes(x, y, free, mapping) for x, y in zip(a, b))
    if isinstance(a, ast.AST):
        if type(a) is not type(b):
            return False
        for field in a._fields:
            if field in ("ctx", "type_comment"):
                continue
            va, vb = getattr(a, field, None), getattr(b, field, None)
            if isinstance(a, ast.Name) and field == "id" and va in free:
                if mapping.setdefault(va, vb) != vb:
                    return False
                continue
            if not match_nodes(va, vb, free, mapping):
                return False
        return True
    return a == b


def strip_case(func, name: str, helpers: set):
    """Копия функции без последнего параметра `name` с умолчанием `""`,
    без `… + name` в сообщениях `assert` и без последнего аргумента `name`
    (позиционного или `name=name`) в вызовах помощников `helpers`."""
    node = clean(func)
    args = node.args
    if args.args and args.args[-1].arg == name and args.defaults and \
            isinstance(args.defaults[-1], ast.Constant) and args.defaults[-1].value == "":
        args.args = args.args[:-1]
        args.defaults = args.defaults[:-1]
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assert) and isinstance(sub.msg, ast.BinOp) \
                and isinstance(sub.msg.op, ast.Add) \
                and isinstance(sub.msg.right, ast.Name) and sub.msg.right.id == name:
            sub.msg = sub.msg.left
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                and sub.func.id in helpers:
            if sub.args and isinstance(sub.args[-1], ast.Name) and sub.args[-1].id == name:
                sub.args = sub.args[:-1]
            sub.keywords = [k for k in sub.keywords if not (
                k.arg in ("case", "label") and isinstance(k.value, ast.Name)
                and k.value.id == name)]
    return node


def body_without_tail_return(func) -> tuple[list, str | None]:
    """(тело без докстринга и хвостового `return <имя>`, это имя)."""
    body = strip_docstring(clean(func).body)
    if body and isinstance(body[-1], ast.Return) and isinstance(body[-1].value, ast.Name):
        return body[:-1], body[-1].value.id
    return body, None


def setup_body(path: str, tree, param: str) -> list:
    """Тело `setUp` стенда файла `path`, переведённое для фикстуры."""
    method = class_method(tree, SETUP_CLASS[path], "setUp")
    if method is None:
        raise LookupError(f"{path}::{SETUP_CLASS[path]}.setUp нет в базе")
    node = translate(path, tree, method, param)
    body = [s for s in strip_docstring(node.body) if not is_super_setup(s)]
    if path in SETUP_HEAD:
        body = body[:SETUP_HEAD[path]]
    return [clean(s) for s in body]


# ------------------------------------------------------- файл модуля (ast)

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
    тем же именем (имена тестов — прежние, требование 9)."""
    return [f for f in funcs if f.name == name]


# ------------------------------------------- место упавшего утверждения

def is_assertion_error_raise(node) -> bool:
    if not isinstance(node, ast.Raise) or node.exc is None:
        return False
    exc = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
    return isinstance(exc, ast.Name) and exc.id == "AssertionError"


def is_assertion_node(node) -> bool:
    """`assert`, `raise AssertionError(…)`, `self.assertX`/`fail`/`raises`,
    голый `fail(…)`."""
    if isinstance(node, ast.Assert) or is_assertion_error_raise(node):
        return True
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return (func.attr.startswith("assert") and not func.attr.startswith("assert_")) \
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


def calls_in_order(func, name: str, via_self: bool) -> list[ast.Call]:
    """Вызовы `self.<name>(…)` (`via_self`) или `<name>(…)` в функции,
    по порядку строк."""
    found = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if via_self and isinstance(target, ast.Attribute) and target.attr == name \
                and isinstance(target.value, ast.Name) and target.value.id == "self":
            found.append(node)
        elif not via_self and isinstance(target, ast.Name) and target.id == name:
            found.append(node)
    return sorted(found, key=lambda n: (n.lineno, n.col_offset))


def covers(node, line: int) -> bool:
    return node.lineno <= line <= (node.end_lineno or node.lineno)


# --------------------------------------- нормальная форма утверждения

class Canon(ast.NodeTransformer):
    """Общая форма операндов: стенд (`self`, параметры функции-теста) →
    `STAND`; `self.<помощник>(…)` → `<функция>(STAND, …)`; `self.<статический>`
    → имя функции; константы файла — новыми именами (`renames`); локальные
    имена функции модуля, переименованные при переносе (`locals_`: новое →
    прежнее), — прежним именем."""

    def __init__(self, stands: set, calls: dict, bare: set = frozenset(),
                 renames: dict | None = None, locals_: dict | None = None):
        self.stands, self.calls, self.bare = stands, calls, bare
        self.renames = renames or {}
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
        name = self.renames.get(node.id, node.id)
        return ast.Name(id=self.locals.get(name, name), ctx=ast.Load())


def dump_canon(node, canon: Canon) -> str:
    return ast.dump(clean(canon.visit(copy.deepcopy(node))), annotate_fields=False)


def normal_form(node, canon: Canon):
    """Нормальная форма утверждения (требование 11): `assertX(a, b)` ↔
    `assert a <op> b`, `assertTrue(x)` ↔ `assert x`, `assertFalse(x)` ↔
    `assert not x`, `assertIsNone(x)` ↔ `assert x is None`,
    `assertIsNotNone(x)` ↔ `assert x is not None`, `assertRegex(t, p)` ↔
    `assert re.search(p, t)`; сообщение отбрасывается."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr.startswith("assert"):
        test = plain_assert_test(node)
        if test is None:
            return ("other", ast.dump(clean(node)))
        node = ast.Assert(test=test, msg=None)
    if isinstance(node, ast.Assert):
        test = node.test
        if isinstance(test, ast.Compare) and len(test.ops) == 1:
            return ("cmp", type(test.ops[0]).__name__, dump_canon(test.left, canon),
                    dump_canon(test.comparators[0], canon))
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            return ("false", dump_canon(test.operand, canon))
        return ("true", dump_canon(test, canon))
    return ("other", ast.dump(clean(node)))


def base_canon(tree, path: str) -> Canon:
    return Canon(set(), file_calls(tree, path), bare_methods(path),
                 CONST_RENAMES.get(path, {}))


def local_names(func) -> set[str]:
    return {n.id for n in ast.walk(func) if isinstance(n, ast.Name)
            and isinstance(n.ctx, ast.Store)}


def local_renames(base_func, base_c: Canon, new_func, new_params: set) -> dict:
    """{новое имя: прежнее} локальных переменных, переименованных при
    переносе: присваивание того же значения (по общей форме) имени, которого
    нет среди локальных исходного теста, тогда как прежнего имени нет среди
    локальных функции модуля."""
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
    return Canon(params, {}, locals_=renames)


def self_assertions(func) -> list:
    """Утверждения исходного метода: `self.assert*` (кроме `assertRaises`)."""
    return [n for n in ast.walk(func) if is_self_assert(n)]


def plain_assertions(func) -> list:
    return [n for n in ast.walk(func) if isinstance(n, ast.Assert)]


# ------------------------------------------------------- разделы модуля

def section_marks(text: str, base_end: int, base_trees: dict) -> dict:
    """{файл: номер строки комментария раздела} — первая строка `# …` ниже
    `base_end`, несущая имя прежнего файла и имя одного из его классов."""
    lines = text.split("\n")
    marks = {}
    for path in SOURCE_FILES:
        stem = Path(path).stem
        classes = [c.name for c in class_nodes(base_trees[path])]
        for i, line in enumerate(lines):
            n = i + 1
            if n <= base_end or not line.lstrip().startswith("#"):
                continue
            if stem in line and any(c in line for c in classes):
                marks[path] = n
                break
    return marks


def section_of(marks: dict, line: int) -> str | None:
    """Прежний файл, в разделе которого стоит строка `line` модуля."""
    owner, best = None, 0
    for path, mark in marks.items():
        if best < mark <= line:
            owner, best = path, mark
    return owner
