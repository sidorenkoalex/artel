"""Конвертер свода (волна 2б-3): тестовые методы исходного файла -> тела функций pytest.

Печатает в stdout тело (помощники + тесты) для tests/test_report_outcome_module.py.
Запуск из корня рабочей копии: python3 <путь>/convert_report_outcome.py > ...
"""
import ast
import io
import re
import sys
import textwrap
import tokenize

P = sys.argv[1] if len(sys.argv) > 1 else "tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py"
src = open(P, encoding="utf-8").read()
lines = src.split("\n")
tree = ast.parse(src)

OFF = [0]
for _l in lines:
    OFF.append(OFF[-1] + len(_l) + 1)


def pos(l, c):
    return OFF[l - 1] + len(lines[l - 1].encode("utf-8")[:c].decode("utf-8"))


def seg(n):
    return src[pos(n.lineno, n.col_offset):pos(n.end_lineno, n.end_col_offset)]


ATOM = (ast.Name, ast.Attribute, ast.Call, ast.Subscript, ast.Constant, ast.List,
        ast.Dict, ast.Set, ast.JoinedStr, ast.ListComp, ast.DictComp, ast.SetComp)


def op(n):
    s = seg(n)
    if "\n" in s and isinstance(n, (ast.Constant, ast.JoinedStr, ast.Name, ast.Attribute)):
        return "(" + s + ")"
    return s if isinstance(n, ATOM) else "(" + s + ")"


par = {}
for n in ast.walk(tree):
    for ch in ast.iter_child_nodes(n):
        par[ch] = n


def is_subtest(item):
    c = item.context_expr
    return (isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
            and c.func.attr == "subTest")


def subtest_labels(n):
    labs = []
    p = par.get(n)
    while p is not None:
        if isinstance(p, ast.With):
            for it in p.items:
                if is_subtest(it):
                    labs = [(k.arg, seg(k.value)) for k in it.context_expr.keywords] + labs
        p = par.get(p)
    return labs


classes = [n for n in tree.body if isinstance(n, ast.ClassDef)
           and n.lineno >= 611 and n.name != "PytestSpy"]
edits = []
count = {}
OPS = {"assertEqual": "==", "assertNotEqual": "!=", "assertIn": "in",
       "assertNotIn": "not in"}
for c in classes:
    for m in c.body:
        if not (isinstance(m, ast.FunctionDef) and m.name.startswith("test")):
            continue
        for n in ast.walk(m):
            if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                    and isinstance(n.value.func, ast.Attribute)
                    and isinstance(n.value.func.value, ast.Name)
                    and n.value.func.value.id == "self"):
                continue
            a = n.value.func.attr
            args = n.value.args
            if not a.startswith("assert") or a == "assert_unknown":
                continue
            assert not n.value.keywords, (a, n.lineno)
            if a in OPS:
                cond = f"{op(args[0])} {OPS[a]} {op(args[1])}"
                msg = args[2] if len(args) > 2 else None
            elif a == "assertTrue":
                cond = (seg(args[0]) if isinstance(args[0], ast.Compare) and "\n" not in seg(args[0])
                        else op(args[0]))
                msg = args[1] if len(args) > 1 else None
            elif a == "assertFalse":
                cond = "not " + op(args[0])
                msg = args[1] if len(args) > 1 else None
            elif a == "assertIsNotNone":
                cond = f"{op(args[0])} is not None"
                msg = args[1] if len(args) > 1 else None
            else:
                raise SystemExit(f"неизвестное утверждение {a} :{n.lineno}")
            labs = subtest_labels(n)
            m_s = op(msg) if msg is not None else None
            if labs:
                lab = 'f"' + "; ".join(f"{k}={{{v}!r}}" for k, v in labs) + '"'
                m_s = f'{m_s} + "; " + {lab}' if m_s else lab
            new = "assert " + cond + (", " + m_s if m_s else "")
            indent = len(lines[n.lineno - 1]) - len(lines[n.lineno - 1].lstrip())
            if m_s and len(new.split("\n")[-1]) + indent > 79:
                new = ("assert " + cond + ", (\n" + " " * (indent + 4) + m_s + ")")
            edits.append((pos(n.lineno, n.col_offset),
                          pos(n.end_lineno, n.end_col_offset), new))
            count[a] = count.get(a, 0) + 1
print(count, file=sys.stderr)
out = src
for s, e, t in sorted(edits, reverse=True):
    out = out[:s] + t + out[e:]

while True:
    t2 = ast.parse(out)
    L = out.split("\n")
    for n in ast.walk(t2):
        if isinstance(n, ast.With) and any(is_subtest(i) for i in n.items):
            assert len(n.items) == 1
            b0, b1 = n.body[0].lineno - 1, n.end_lineno
            out = "\n".join(L[:n.lineno - 1]
                            + [l[4:] if l.startswith("    ") else l for l in L[b0:b1]]
                            + L[b1:])
            break
    else:
        break

toks = list(tokenize.generate_tokens(io.StringIO(out).readline))
L = out.split("\n")
for t in sorted((t for t in toks if t.type == tokenize.NAME and t.string == "self"),
                key=lambda t: t.start, reverse=True):
    (l, c), (_l2, c2) = t.start, t.end
    L[l - 1] = L[l - 1][:c] + "box" + L[l - 1][c2:]
out = "\n".join(L)

t3 = ast.parse(out)
L = out.split("\n")


def fsrc(n):
    return textwrap.dedent("\n".join(L[n.lineno - 1:n.end_lineno]))


PREF = {"VitestReporterTest": "vitest_reporter_", "InstallAndDepsTest": "install_and_deps_",
        "ArtelUnchangedTest": "artel_unchanged_"}
helpers, tests = [], []
for c in [n for n in t3.body if isinstance(n, ast.ClassDef)]:
    if c.name == "ReportSandbox":
        helpers += [fsrc(m) for m in c.body
                    if isinstance(m, ast.FunctionDef) and m.name == "assert_unknown"]
    if c.lineno < 611 or c.name == "PytestSpy":
        continue
    for m in c.body:
        if not isinstance(m, ast.FunctionDef):
            continue
        s = fsrc(m)
        if m.name.startswith("test"):
            s = s.replace("box.full_vitest(", PREF.get(c.name, "") + "full_vitest(box, ")
            s = s.replace("full_vitest(box, )", "full_vitest(box)")
            tests.append(s)
        else:
            if m.name in ("full_vitest", "channels"):
                s = s.replace(f"def {m.name}(", f"def {PREF[c.name]}{m.name}(", 1)
            helpers.append(s)
body = "\n\n\n".join(helpers) + "\n\n\n" + "\n\n\n".join(tests)
body = body.replace("box.channels()", "artel_unchanged_channels(box)")
body = re.sub(r"box\.(main_head|key_case|assert_unknown)\(", r"\1(box, ", body)
body = body.replace("box.FLAGS", "FLAGS")
body = body.replace('box.assertRaises(OSError, msg=box.note("запись в node_modules"))',
                    "pytest.raises(OSError)")
body = body.replace("box.assertRaises(SystemExit)", "pytest.raises(SystemExit)")
body = body.replace("raised.exception", "raised.value")
print(body)
