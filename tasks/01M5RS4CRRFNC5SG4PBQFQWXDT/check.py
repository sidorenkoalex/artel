"""Временная сверка свода помощниками планки (удаляется после шага)."""
import ast
import subprocess
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent
sys.path.insert(0, str(DOCS / "acceptance_tests"))
import _plan  # noqa: E402

WT = Path("/Users/al.sidorenko/projects/artel/.artel/projects/artel/worktrees/01M5RS4CRRFNC5SG4PBQFQWXDT")
BASE = sys.argv[1] if len(sys.argv) > 1 else "HEAD"


def base(path):
    return subprocess.run(["git", "-C", str(WT), "show", f"{BASE}:{path}"],
                          capture_output=True, text=True, check=True).stdout


def disk(path):
    return (WT / path).read_text(encoding="utf-8")


old = ast.parse(base(_plan.SOURCE))
# песочница
want = _plan.sandbox_statements(old)
got = _plan.strip_docstring(ast.parse(disk(_plan.SANDBOX)).body)
print("песочница: операторов", len(want), len(got),
      "равны" if [ast.dump(w) for w in want] == [ast.dump(g) for g in got] else "НЕ РАВНЫ")
# сокращённый файл
removed = set(_plan.SANDBOX_CLASSES) | set(_plan.CLASSES)
kept = [n for n in old.body if not (isinstance(n, ast.ClassDef) and n.name in removed)]
head = ast.parse(disk(_plan.SOURCE)).body
at = next(i for i, n in enumerate(head) if isinstance(n, ast.ImportFrom)
          and n.module == _plan.MERGE_IMPORT_MODULE)
imp_ok = ast.dump(head[at + 1]) == ast.dump(ast.parse(_plan.NEW_IMPORT).body[0])
rest = head[:at + 1] + head[at + 2:]
print("долгоживущий: импорт", imp_ok, "операторов", len(kept), len(rest),
      "равны" if [ast.dump(w) for w in kept] == [ast.dump(g) for g in rest] else "НЕ РАВНЫ")
# тесты
mod = ast.parse(disk(_plan.MODULE))
funcs = _plan.module_functions(mod)
bad = []
for t in _plan.task_tests(base(_plan.SOURCE)):
    f = funcs.get(t.func.name)
    if f is None or _plan.actual_test_body(f) != _plan.expected_test_body(t.func):
        bad.append(t.key)
    if f is not None and _plan.attribute_assignments(f, "box") != [
            x.replace("self", "box", 1) for x in _plan.attribute_assignments(t.func, "self")]:
        bad.append("присваивания " + t.key)
print("тела тестов: несовпадений", len(bad), bad)
for name, (cls, with_case) in _plan.HELPER_SOURCE.items():
    m = _plan.class_method(old, cls, name)
    print("помощник", name, _plan.actual_helper_body(funcs[name]) == _plan.expected_helper_body(m, "box", with_case),
          _plan.signature_dump(funcs[name]) == _plan.reference_signature(name))
gate = _plan.module_functions(ast.parse(base(_plan.GATE_TESTS)))
for name in _plan.GATE_HELPERS:
    print("помощник", name, ast.dump(funcs[name]) == ast.dump(gate[name]),
          _plan.signature_dump(funcs[name]) == _plan.reference_signature(name))
print("тестов в модуле", len(_plan.module_tests(mod)),
      "строк", disk(_plan.MODULE).count("\n"), "строк исходного", base(_plan.SOURCE).count("\n"))
