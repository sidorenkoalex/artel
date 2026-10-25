"""Линт детерминизма тестов: ожидание по часам и чтение живых файлов репозитория.

Разбор перенесён из `tests/test_invariants.py::DeterministicTestsLintTest`
(SPEC 01M5MVSP9YW0DYA4YQ1KSG0AHF, решение Оператора 23.10.2026): тот же
разбор зовут инвариант дерева `tests/` и guard на выходе `tests_writing`
до лока планки и долгоживущих файлов. Только стандартная библиотека: модуль
импортирует guard, а модули `orchestrator` импортируют guard — импорт
`orchestrator` отсюда замкнул бы цикл.
"""
import ast

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
