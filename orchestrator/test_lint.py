"""Линт детерминизма тестов: ожидание по часам и чтение живых файлов репозитория.

Разбор перенесён из `tests/test_invariants.py::DeterministicTestsLintTest`
(SPEC 01M5MVSP9YW0DYA4YQ1KSG0AHF, решение Оператора 23.10.2026): тот же
разбор зовут инвариант дерева `tests/` и guard на выходе `tests_writing`
до лока планки и долгоживущих файлов. Только стандартная библиотека: модуль
импортирует guard, а модули `orchestrator` импортируют guard — импорт
`orchestrator` отсюда замкнул бы цикл.

Здесь же — правила метки размера долгоживущих файлов (ADR-0032 п. 2; SPEC
01M6XHJH6EJ8D0BR5PRNGZAY8C): `heavy_sandbox_names`, `size_findings` и
разбор `pytestmark`, перенесённый из guard (guard берёт его отсюда).
"""
import ast
import re

PYTESTMARK_NAME = "pytestmark"
PYTEST_MODULE = "pytest"


def is_pytestmark_assign(node: ast.AST, *, annotated: bool = False) -> bool:
    """Присваивание `pytestmark = …`; `annotated` — и `pytestmark: T = …`
    (с значением)."""
    if annotated and isinstance(node, ast.AnnAssign):
        return (node.value is not None and isinstance(node.target, ast.Name)
                and node.target.id == PYTESTMARK_NAME)
    return isinstance(node, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == PYTESTMARK_NAME
        for t in node.targets)


def pytestmark_marks(body: list, *, annotated: bool = False) -> list:
    """Элементы последнего присваивания `pytestmark = …` тела `body`
    (модуля или класса) — одна марка либо элементы списка/кортежа."""
    value = None
    for node in body:
        if is_pytestmark_assign(node, annotated=annotated):
            value = node.value
    if value is None:
        return []
    return value.elts if isinstance(value, (ast.List, ast.Tuple)) else [value]


def pytest_aliases(tree: ast.Module) -> dict:
    """{имя: точечное имя pytest, к которому оно привязано}: `import
    pytest as pt` → `pt: pytest`, `from pytest import mark as m` → `m:
    pytest.mark`. Само `pytest` видно всегда."""
    names = {PYTEST_MODULE: PYTEST_MODULE}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname and alias.name.split(".", 1)[0] == PYTEST_MODULE:
                    names[alias.asname] = alias.name
        elif isinstance(node, ast.ImportFrom) and not node.level and \
                node.module and \
                node.module.split(".", 1)[0] == PYTEST_MODULE:
            for alias in node.names:
                if alias.name != "*":
                    names[alias.asname or alias.name] = \
                        f"{node.module}.{alias.name}"
    return names

CLOCK_CALLS = ("monotonic", "time", "monotonic_ns", "time_ns")
LIVE_FILES = ("targets.yaml", "roles.yaml", "model_sets.yaml",
              ".artel/targets.yaml")
# Имена `config`, равные имени живого файла (относительный путь от
# корня, а не путь песочницы).
LIVE_FILE_CONFIG_ATTRS = ("MODEL_SETS_REL", "TARGETS_LOCAL_REL")


def _is_time_module(node) -> bool:
    return ((isinstance(node, ast.Name) and node.id == "time")
            or (isinstance(node, ast.Attribute) and node.attr == "time"))


def _is_clock_call(node, from_time: set) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return (func.attr in CLOCK_CALLS
                and _is_time_module(func.value))
    return isinstance(func, ast.Name) and func.id in from_time & set(
        CLOCK_CALLS)


def _is_sleep_call(node, from_time: set) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr == "sleep" and _is_time_module(func.value)
    return isinstance(func, ast.Name) and func.id == "sleep" and (
        "sleep" in from_time)


def _zero_pause(call: ast.Call) -> bool:
    args = list(call.args) + [k.value for k in call.keywords]
    return (len(args) == 1 and isinstance(args[0], ast.Constant)
            and not isinstance(args[0].value, bool)
            and args[0].value == 0)


def _walk_own(node):
    """Узлы `node` без тел вложенных функций и классов — у вложенной
    функции свой обход (её нарушение адресуется той же функцией
    верхнего уровня)."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        for child in ast.iter_child_nodes(current):
            if current is not node and isinstance(
                    current, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.Lambda, ast.ClassDef)):
                continue
            stack.append(child)


def _from_time_names(tree) -> set:
    return {alias.asname or alias.name for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "time"
            for alias in node.names}


def _wall_clock_waits(func, from_time: set) -> list:
    """Строки ожидания по часам внутри функции `func` (вместе с
    вложенными функциями)."""
    found = []
    for node in ast.walk(func):
        if _is_sleep_call(node, from_time) and not _zero_pause(node):
            found.append(f"строка {node.lineno}: time.sleep с ненулевой "
                         f"паузой")
        elif isinstance(node, (ast.While, ast.For, ast.AsyncFor)):
            # Условие цикла и условия `if` в его теле: срок проверяется
            # там; сравнение меток времени в утверждении — не ожидание.
            checks = [node.test] if isinstance(node, ast.While) else []
            checks += [sub.test for stmt in node.body
                       for sub in _walk_own(stmt)
                       if isinstance(sub, ast.If)]
            if any(_is_clock_call(sub, from_time)
                   for check in checks for sub in ast.walk(check)):
                found.append(f"строка {node.lineno}: цикл до срока по "
                             f"time.monotonic()/time.time()")
    return found


def _mentions_file(node) -> bool:
    return any(isinstance(sub, ast.Name) and sub.id == "__file__"
               or isinstance(sub, ast.Attribute) and sub.attr == "__file__"
               for sub in ast.walk(node))


def _is_live_name(node) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        value = node.value.strip("/")
        return (value in LIVE_FILES or value == "docs"
                or value.startswith("docs/"))
    return (isinstance(node, ast.Attribute)
            and node.attr in LIVE_FILE_CONFIG_ATTRS)


def _rooted(node, roots: set) -> bool:
    """Выражение — путь от настоящего корня: несёт `__file__` или имя,
    связанное с таким путём."""
    return _mentions_file(node) or any(
        isinstance(sub, ast.Name) and sub.id in roots
        for sub in ast.walk(node))


def _path_parts(node) -> list | None:
    """Части выражения-пути: операнды цепочки `/`, получатель и
    аргументы `joinpath`/`os.path.join`; `None` — не путь."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return [*(_path_parts(node.left) or [node.left]),
                *(_path_parts(node.right) or [node.right])]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "joinpath":
            return [node.func.value, *node.args]
        if node.func.attr == "join" and ast.unparse(node.func.value) in (
                "os.path", "path"):
            return list(node.args)
    return None


def _live_path(node, roots: set) -> bool:
    parts = _path_parts(node)
    return bool(parts) and any(_rooted(p, roots) for p in parts) and any(
        _is_live_name(p) for p in parts)


def _bound_names(statements, test) -> set:
    """Имена, связанные присваиванием в `statements` со значением,
    удовлетворяющим `test` (до неподвижной точки: имя от имени)."""
    names: set = set()
    assigns = [node for stmt in statements for node in ast.walk(stmt)
               if isinstance(node, (ast.Assign, ast.AnnAssign))
               and node.value is not None]
    changed = True
    while changed:
        changed = False
        for node in assigns:
            targets = node.targets if isinstance(node, ast.Assign) else [
                node.target]
            new = {t.id for t in targets if isinstance(t, ast.Name)} - names
            if new and test(node.value, names):
                names |= new
                changed = True
    return names


def _live_reads(func, module_roots: set, module_live: set) -> list:
    local_roots = _bound_names(
        func.body, lambda value, names: _rooted(
            value, module_roots | names))
    roots = module_roots | local_roots
    found = []
    for node in ast.walk(func):
        if _live_path(node, roots):
            found.append(f"строка {node.lineno}: путь к живому файлу "
                         f"репозитория {ast.unparse(node)}")
        elif (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
              and node.id in module_live):
            found.append(f"строка {node.lineno}: имя модуля {node.id} — "
                         f"путь к живому файлу репозитория")
    return found


def top_level_functions(tree):
    """(«Класс::метод» или «функция», узел) — функции верхнего уровня
    модуля и методы его классов."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{node.name}::{item.name}", item


def findings(source: str, rel: str) -> dict:
    """{«файл::метод»: [нарушения]} исходника `source` файла `rel`.

    Код модуля вне функций (кроме определений имён) не исполняет
    ожиданий — его присваивания лишь связывают имена корня.
    `SyntaxError` разбора пробрасывается: пропуск сломанного файла решает
    вызывающий."""
    tree = ast.parse(source)
    from_time = _from_time_names(tree)
    module_stmts = [node for node in tree.body
                    if isinstance(node, (ast.Assign, ast.AnnAssign))]
    module_roots = _bound_names(
        module_stmts, lambda value, names: _rooted(value, names))
    module_live = _bound_names(
        module_stmts, lambda value, names: (
            _live_path(value, module_roots)
            or any(isinstance(sub, ast.Name) and sub.id in names
                   for sub in ast.walk(value))))
    result = {}
    for qualname, func in top_level_functions(tree):
        hits = (_wall_clock_waits(func, from_time)
                + _live_reads(func, module_roots, module_live))
        if hits:
            result[f"{rel}::{qualname}"] = hits
    return result


# Метка размера долгоживущего файла (ADR-0032 п. 2). Корни песочниц с
# настоящим git или БД пульта: перечень `heavy_sandbox_names` — они и их
# подклассы, найденные в исходниках модулей песочниц дерева проверки.
SIZE_MARK = "pytest.mark.size"
USEFIXTURES_MARK = "pytest.mark.usefixtures"
SIZE_SMALL, SIZE_MEDIUM, SIZE_LARGE = "small", "medium", "large"
SIZE_NAMES = (SIZE_SMALL, SIZE_MEDIUM, SIZE_LARGE)
HEAVY_SANDBOX_ROOTS = ("RealGitSandbox", "InitializedTmpRootTest",
                       "SchemaTmpRootTest", "SchemaSeededTmpRootTest",
                       "TaskIdSchemaConnTmpRootTest")
HEAVY_FIXTURES = ("real_git", "origin_real_git", "initialized_tmp_root")
PROCESS_MODULES = ("subprocess", "multiprocessing")
OS_PROCESS_CALLS = ("os.system", "os.popen", "os.fork")
OS_SPAWN_PREFIX = "os.spawn"
SUBPROCESS_CALLS = ("run", "Popen", "call", "check_call", "check_output")
CHILD_ARTEL_SUFFIX = "artel.py"
CHILD_PYTEST = "pytest"
SIZE_NO_MARK = ("нет метки размера — объяви `pytestmark = "
                "pytest.mark.size(\"small\")` (\"medium\", \"large\") на "
                "уровне модуля")
SIZE_SEVERAL = "несколько меток размера"
SIZE_CHILD = "дочерний artel.py или pytest в среднем файле"
# Путь модуля песочниц в дереве проверки: `tests/sandbox.py`,
# `tests/*_sandbox.py`.
SANDBOX_SOURCE_PATH = re.compile(r"tests/([^/]*_)?sandbox\.py")


def is_sandbox_source_path(rel: str) -> bool:
    return SANDBOX_SOURCE_PATH.fullmatch(rel) is not None


def _dotted(node) -> str:
    """`a.b.c` узла имени или атрибута; пустая строка — не имя."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return ""
    parts.append(node.id)
    return ".".join(reversed(parts))


def _base_name(node) -> str:
    """Имя класса базы — последний сегмент (`sb.RealGitSandbox` →
    `RealGitSandbox`)."""
    return _dotted(node).rsplit(".", 1)[-1]


def heavy_sandbox_names(sources: dict) -> frozenset:
    """Имена корней `HEAVY_SANDBOX_ROOTS`, определённых в исходниках
    `sources` ({путь: текст} модулей песочниц), и всех их подклассов там же
    — через примеси и цепочки, в том числе между файлами. Классы всех
    исходников собираются до обхода: результат не зависит от порядка
    словаря. Сломанный исходник пропускается."""
    bases: dict[str, set] = {}
    for text in sources.values():
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases.setdefault(node.name, set()).update(
                    _base_name(b) for b in node.bases)
    heavy = {name for name in bases if name in HEAVY_SANDBOX_ROOTS}
    changed = True
    while changed:
        changed = False
        for name, own in bases.items():
            if name not in heavy and own & heavy:
                heavy.add(name)
                changed = True
    return frozenset(heavy)


def _mark_name(node, aliases: dict) -> str:
    """Каноническое имя pytest марки (`pt.mark.size(…)` →
    `pytest.mark.size`); пустая строка — не имя pytest."""
    if isinstance(node, ast.Call):
        node = node.func
    first, sep, rest = _dotted(node).partition(".")
    bound = aliases.get(first)
    return f"{bound}{sep}{rest}" if bound else ""


def _size_value(mark) -> str | None:
    """Имя размера марки — строковый литерал единственного аргумента;
    `None` — не строковый литерал."""
    if isinstance(mark, ast.Call) and len(mark.args) == 1 \
            and not mark.keywords and isinstance(mark.args[0], ast.Constant) \
            and isinstance(mark.args[0].value, str):
        return mark.args[0].value
    return None


def _size_shown(mark) -> str:
    value = _size_value(mark)
    if value is not None:
        return f"\"{value}\""
    if isinstance(mark, ast.Call):
        args = [*mark.args, *(k.value for k in mark.keywords)]
        return ", ".join(ast.unparse(a) for a in args) or ast.unparse(mark)
    return ast.unparse(mark)


def _module_size_marks(tree: ast.Module, aliases: dict) -> list:
    return [m for m in pytestmark_marks(tree.body, annotated=True)
            if _mark_name(m, aliases) == SIZE_MARK]


def has_module_size_mark(source: str) -> bool:
    """Исходник несёт метку размера на уровне модуля (любого значения);
    сломанный исходник — не несёт."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    return bool(_module_size_marks(tree, pytest_aliases(tree)))


def _test_size_marks(tree: ast.Module, aliases: dict) -> list:
    """Метки размера тестов и классов: декораторы и `pytestmark` тела
    класса."""
    marks = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            candidates = list(node.decorator_list)
            if isinstance(node, ast.ClassDef):
                candidates += pytestmark_marks(node.body, annotated=True)
            marks += [m for m in candidates
                      if _mark_name(m, aliases) == SIZE_MARK]
    return marks


def _imported_names(tree: ast.Module) -> dict:
    """{локальное имя: исходное имя} импортов `from x import y as z`."""
    return {alias.asname or alias.name: alias.name
            for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
            for alias in node.names if alias.name != "*"}


def _heavy_classes(tree: ast.Module, heavy: frozenset) -> list:
    """[(строка, класс, песочница перечня)] классов файла, наследующих имя
    из `heavy` прямо, через псевдоним импорта или цепочку локальных
    классов. Локальный класс с именем из перечня — свой класс файла, не
    песочница."""
    imported = _imported_names(tree)
    classes = [node for node in ast.walk(tree)
               if isinstance(node, ast.ClassDef)]
    local = {node.name for node in classes}
    reached: dict[str, str] = {}
    changed = True
    while changed:
        changed = False
        for node in classes:
            if node.name in reached:
                continue
            for base in node.bases:
                name = (imported.get(base.id, base.id)
                        if isinstance(base, ast.Name) else _base_name(base))
                sandbox = reached.get(name) or (
                    name if name in heavy and name not in local else "")
                if sandbox:
                    reached[node.name] = sandbox
                    changed = True
                    break
    return [(node.lineno, node.name, reached[node.name])
            for node in classes if node.name in reached]


def _function_params(func) -> list:
    args = func.args
    return [a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)]


def _small_findings(tree: ast.Module, heavy: frozenset, aliases: dict) -> list:
    found = []
    for line, cls, sandbox in _heavy_classes(tree, heavy):
        found.append((line, f"малый файл: класс {cls} наследует {sandbox} — "
                            f"песочница настоящего git или БД пульта"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for param in _function_params(node):
                if param in HEAVY_FIXTURES:
                    found.append((node.lineno, f"малый файл: {node.name} "
                                               f"берёт фикстуру {param}"))
        elif isinstance(node, ast.Call):
            if _mark_name(node, aliases) == USEFIXTURES_MARK:
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and \
                            arg.value in HEAVY_FIXTURES:
                        found.append((node.lineno, f"малый файл: usefixtures "
                                                   f"берёт фикстуру "
                                                   f"{arg.value}"))
            called = _dotted(node.func)
            if called in OS_PROCESS_CALLS or called.startswith(OS_SPAWN_PREFIX):
                found.append((node.lineno, f"малый файл вызывает {called} — "
                                           f"процессы"))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = ([alias.name for alias in node.names]
                       if isinstance(node, ast.Import) else [node.module or ""])
            for module in {m.split(".", 1)[0] for m in modules}:
                if module in PROCESS_MODULES:
                    found.append((node.lineno, f"малый файл импортирует "
                                               f"{module} — процессы"))
    return found


def _is_child_literal(node) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and (
        node.value.endswith(CHILD_ARTEL_SUFFIX) or node.value == CHILD_PYTEST)


def _carries_child(node, names: set) -> bool:
    return any(_is_child_literal(sub)
               or isinstance(sub, ast.Name) and sub.id in names
               for sub in ast.walk(node))


def _subprocess_calls(tree: ast.Module) -> set:
    """Точечные имена вызовов `SUBPROCESS_CALLS` с учётом псевдонима
    модуля и `from subprocess import …`."""
    calls = {f"subprocess.{name}" for name in SUBPROCESS_CALLS}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "subprocess" and alias.asname:
                    calls |= {f"{alias.asname}.{n}" for n in SUBPROCESS_CALLS}
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            calls |= {alias.asname or alias.name for alias in node.names
                      if alias.name in SUBPROCESS_CALLS}
    return calls


def _medium_findings(tree: ast.Module) -> list:
    """Вызовы `subprocess` с литералом `…artel.py`/`"pytest"` в любом узле
    аргументов либо с именем модуля или той же функции, присвоенным
    выражению с таким литералом."""
    calls = _subprocess_calls(tree)
    module_names = _bound_names(
        [n for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))],
        lambda value, names: _carries_child(value, names))
    scopes = [(tree, module_names)]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scopes.append((node, module_names | _bound_names(
                node.body, lambda value, names: _carries_child(
                    value, module_names | names))))
    found = []
    for scope, names in scopes:
        for node in _walk_own(scope):
            if isinstance(node, ast.Call) and _dotted(node.func) in calls and \
                    any(_carries_child(arg, names) for arg in
                        [*node.args, *(k.value for k in node.keywords)]):
                found.append((node.lineno,
                              f"{SIZE_CHILD}: {_dotted(node.func)}"))
    return found


def size_findings(source: str, label: str, heavy: frozenset) -> list:
    """[(строка, нарушение)] метки размера исходника `source` файла
    `label` (ADR-0032 п. 2): метка на уровне модуля — одна на файл, имя из
    `SIZE_NAMES` строковым литералом; ресурсы файла ей не противоречат —
    малый без песочниц перечня `heavy` (`heavy_sandbox_names`), их фикстур
    и процессов, средний без дочернего `artel.py` и pytest. Проверка
    статическая — сигнал, не гарантия. Сломанный исходник — без нарушений:
    его называет сухой сбор. Метку файла к тексту добавляет вызывающий."""
    del label
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    aliases = pytest_aliases(tree)
    module_marks = _module_size_marks(tree, aliases)
    if not module_marks:
        return [(1, SIZE_NO_MARK)]
    marks = module_marks + _test_size_marks(tree, aliases)
    if len(marks) > 1:
        shown = ", ".join(_size_shown(m) for m in marks)
        return [(marks[1].lineno, f"{SIZE_SEVERAL}: {shown} — у файла одна "
                                  f"метка на уровне модуля")]
    mark = module_marks[0]
    size = _size_value(mark)
    if size is None:
        return [(mark.lineno, f"имя размера {_size_shown(mark)} — не "
                              f"строковый литерал из {', '.join(SIZE_NAMES)}")]
    if size not in SIZE_NAMES:
        return [(mark.lineno, f"имя размера {_size_shown(mark)} вне "
                              f"{', '.join(SIZE_NAMES)}")]
    if size == SIZE_SMALL:
        return sorted(set(_small_findings(tree, heavy, aliases)))
    if size == SIZE_MEDIUM:
        return sorted(set(_medium_findings(tree)))
    return []
