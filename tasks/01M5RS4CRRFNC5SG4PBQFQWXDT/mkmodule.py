"""Временный генератор свода (удаляется после шага)."""
import ast
import re
import subprocess
from pathlib import Path

WT = Path("/Users/al.sidorenko/projects/artel/.artel/projects/artel/worktrees/01M5RS4CRRFNC5SG4PBQFQWXDT")
SOURCE = "tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py"
GATE = "tests/test_outcome_gate_module.py"
CLASSES = ("Ac3GreenPriorTest", "Ac10EmptyPriorSetTest", "Ac4PriorRedTest",
           "Ac5PriorUnstableTest", "Ac6OneFindingPerIdTest", "Ac7RunScopeTest",
           "Ac8RestoredPathsTest", "Ac9NoTestsFieldTest", "Ac11PrepareTest",
           "Ac12DiffFailureTest", "Ac13OwnerMarkerTest",
           "Ac32AddedFilesRemovedTest", "Ac33SkippedMissingRedTest",
           "Ac30OutOfBoundsTest")
SANDBOX_CLASSES = ("Moved", "Link", "PriorSandbox", "ReplacementSandbox",
                   "StrictSandbox")
HELPERS = ("refusal", "no_gate_refusal", "passed", "grant", "conftest_case")
CASE_CALLS = ("refusal", "no_gate_refusal", "passed")
OPS = {"assertEqual": "==", "assertIn": "in", "assertNotIn": "not in",
       "assertGreaterEqual": ">="}
WRAP = (ast.BoolOp, ast.Compare, ast.IfExp, ast.Lambda, ast.NamedExpr)


def show(path):
    return subprocess.run(["git", "-C", str(WT), "show", f"HEAD:{path}"],
                          capture_output=True, text=True, check=True).stdout


def seg(text, node):
    return ast.get_source_segment(text, node)


def offsets(text):
    starts, pos = [], 0
    for line in text.encode("utf-8").split(b"\n"):
        starts.append(pos)
        pos += len(line) + 1
    return starts


def apply(text, edits):
    data = text.encode("utf-8")
    for start, end, new in sorted(edits, key=lambda e: e[0], reverse=True):
        data = data[:start] + new.encode("utf-8") + data[end:]
    return data.decode("utf-8")


def subtest_withs(tree):
    return [n for n in ast.walk(tree) if isinstance(n, ast.With)
            and isinstance(n.items[0].context_expr, ast.Call)
            and getattr(n.items[0].context_expr.func, "attr", "") == "subTest"]


def inside(node, withs):
    return any(w.body[0].lineno <= node.lineno <= w.end_lineno for w in withs)


def operand(text, node, wrap_not=False):
    s = seg(text, node)
    if isinstance(node, WRAP) or (wrap_not and isinstance(node, ast.UnaryOp)
                                  and isinstance(node.op, ast.Not)):
        return f"({s})"
    return s


def convert_function(src: str) -> str:
    """Текст функции (def на уровне модуля) после замен требований 16–17."""
    src = re.sub(r"\bself\.(" + "|".join(HELPERS) + r")\(", r"\1(box, ", src)
    src = re.sub(r"\bself\b", "box", src)
    tree = ast.parse(src)
    func = tree.body[0]
    withs = subtest_withs(func)
    starts = offsets(src)
    lines = src.split("\n")

    def off(line, col):
        return starts[line - 1] + col

    edits = []
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in CASE_CALLS and inside(node, withs):
            end = off(node.end_lineno, node.end_col_offset) - 1
            edits.append((end, end, ", case=case"))
    for node in ast.walk(func):
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute)
                and isinstance(node.value.func.value, ast.Name)
                and node.value.func.value.id == "box"
                and node.value.func.attr.startswith("assert")):
            continue
        call = node.value
        attr = call.func.attr
        nargs = 1 if attr in ("assertTrue", "assertFalse") else 2
        msg = call.args[nargs] if len(call.args) > nargs else None
        if attr == "assertTrue":
            test = seg(src, call.args[0])
        elif attr == "assertFalse":
            test = "not " + operand(src, call.args[0])
        else:
            test = (operand(src, call.args[0], True) + f" {OPS[attr]} "
                    + operand(src, call.args[1], True))
        indent = " " * node.col_offset
        text = f"assert {test}"
        if msg is not None:
            m = seg(src, msg)
            # Вложенные правки внутри сообщения (case=case) здесь не нужны:
            # сообщения тестов не зовут помощников исхода.
            if inside(node, withs):
                m = "case + " + m
            one = f"{indent}{text}, {m}"
            if "\n" in one or len(one) > 99:
                text = f"{text}, (\n{indent}    {m})"
            else:
                text = f"{text}, {m}"
        start = off(node.lineno, node.col_offset)
        end = off(node.end_lineno, node.end_col_offset)
        # Помощники исхода в условии assert не встречаются — правки не пересекаются.
        edits = [e for e in edits if not (start <= e[0] < end)] + \
            [(start, end, text)] + [e for e in edits if start <= e[0] < end and False]
    src = apply(src, edits)
    # subTest → строка case и тело без лишнего отступа.
    tree = ast.parse(src)
    withs = sorted(subtest_withs(tree.body[0]), key=lambda w: w.lineno, reverse=True)
    lines = src.split("\n")
    for w in withs:
        label = w.items[0].context_expr.keywords[0].value
        indent = " " * w.col_offset
        if isinstance(label, ast.Constant):
            case = f'{indent}case = f"{label.value}, зерно {{box.seed}}: "'
        else:
            case = f'{indent}case = f"{{{seg(src, label)}}}, зерно {{box.seed}}: "'
        body = [line[4:] if line.strip() else line
                for line in lines[w.body[0].lineno - 1:w.end_lineno]]
        lines[w.lineno - 1:w.end_lineno] = [case, *body]
    return "\n".join(lines)


def method_text(text, method):
    lines = text.split("\n")
    body = lines[method.lineno - 1:method.end_lineno]
    return "\n".join(line[4:] if line.strip() else line for line in body)


def main():
    text = show(SOURCE)
    tree = ast.parse(text)
    lines = text.split("\n")
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}

    # --- песочница
    first = next(n for n in tree.body if isinstance(n, ast.Import)
                 and n.names[0].name == "contextlib")
    claim = next(n for n in tree.body if isinstance(n, ast.Assign)
                 and n.targets[0].id == "CLAIM")
    parts = ['"""Песочницы гейта исходов G3б-2: прежние версии, заменяемые тесты, строгий режим."""',
             "\n".join(lines[first.lineno - 1:claim.end_lineno])]
    for name in SANDBOX_CLASSES:
        node = classes[name]
        parts.append("\n".join(lines[node.lineno - 1:node.end_lineno]))
    (WT / "tests/prior_outcome_sandbox.py").write_text(
        parts[0] + "\n" + parts[1] + "\n\n\n" + "\n\n\n".join(parts[2:]) + "\n",
        encoding="utf-8")

    # --- сокращённый долгоживущий файл
    drop = set()
    for name in (*SANDBOX_CLASSES, *CLASSES):
        node = classes[name]
        drop.update(range(node.lineno, node.end_lineno + 1))
        if name in CLASSES or name in ("Moved", "Link", "PriorSandbox"):
            k = node.lineno - 1
            while k >= 1 and not lines[k - 1].strip():
                k -= 1
            if lines[k - 1].startswith("# ---") and name != "Moved":
                drop.add(k)
    kept = [line for i, line in enumerate(lines, start=1) if i not in drop]
    out, blank = [], 0
    for line in kept:
        blank = blank + 1 if not line.strip() else 0
        if blank <= 2:
            out.append(line)
    short = "\n".join(out)
    anchor = "from tests.merge_outcome_sandbox import (\n    MergeOutcomeSandbox)\n"
    assert short.count(anchor) == 1
    short = short.replace(anchor, anchor + "from tests.prior_outcome_sandbox import "
                          "(Moved, ReplacementSandbox, StrictSandbox)\n")
    (WT / SOURCE).write_text(short, encoding="utf-8")

    # --- модуль тестов
    gate = show(GATE)
    gtree = ast.parse(gate)
    glines = gate.split("\n")
    gfuncs = {n.name: n for n in gtree.body if isinstance(n, ast.FunctionDef)}
    helpers = ["\n".join(glines[gfuncs[n].lineno - 1:gfuncs[n].end_lineno])
               for n in ("refusal", "no_gate_refusal")]
    tests = []
    for name in CLASSES:
        for item in classes[name].body:
            if isinstance(item, ast.FunctionDef) and item.name.startswith("test"):
                src = method_text(text, item)
                src = src.replace(f"def {item.name}(self):", f"def {item.name}(box):", 1)
                tests.append(convert_function(src))
    header = (WT / "tests/.prior_module_head.txt")
    head = Path(__file__).with_name("module_head.txt").read_text(encoding="utf-8")
    body = head + "\n\n\n".join(helpers) + "\n\n\n" + \
        Path(__file__).with_name("module_helpers.txt").read_text(encoding="utf-8") + \
        "\n\n# ---------------------------------------------------------------- тесты\n\n\n" + \
        "\n\n\n".join(tests) + "\n"
    (WT / "tests/test_outcome_prior_module.py").write_text(body, encoding="utf-8")


main()
