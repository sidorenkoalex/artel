"""Свод шести файлов волны 3м-2б в стиль pytest — текстом, по позициям ast
исходника (комментарии и разметка строк сохраняются): разделы по файлам,
константы, фикстура стенда из `setUp`, помощники-функции с префиксом файла,
тесты-функции. Вывод — `sections.txt` рядом (дописывается в конец
`tests/test_merge_after_module.py` отдельным шагом).

Запуск из рабочей копии задачи: python3 <путь>/convert.py
"""
import ast
import pathlib
import re
import textwrap

DOCS = pathlib.Path(__file__).resolve().parent

FILES = [
    ("answer", "tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py",
     "AnswerMandateSandbox", "real_git", None),
    ("guard", "tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py",
     "GuardMergeAfterFieldTest", "tmp_dir", 3),
    ("plan", "tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py",
     "PlanChannelSandbox", "light_transition", None),
    ("spec_gate", "tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py",
     "MergeAfterSpecGateSandbox", "light_transition", None),
    ("status_show", "tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py",
     "DependencyOutputSandbox", "light_transition", None),
    ("new_declares", "tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py",
     "DeclaredMergeAfterSandbox", "light_transition", None),
]
SKIP_CONST = {"guard": {"FIELD"}, "spec_gate": {"ZONES"},
              "new_declares": {"ZONES", "CROCKFORD", "WAIT_PREFIX", "ids_of"},
              "plan": {"ids_of"}, "spec_gate_": set(),
              "status_show": {"ids_of"}}
SKIP_CONST["spec_gate"] |= {"ids_of"}
RENAMES = {
    "answer": {"MARKER": "ANSWER_MARKER"},
    "guard": {"SPEC_TEXT": "GUARD_SPEC_TEXT"},
    "plan": {"SPEC_TEXT": "PLAN_SPEC_TEXT"},
    "spec_gate": {"SPEC_TEXT": "SPEC_GATE_SPEC_TEXT"},
    "status_show": {"SPEC_TEXT": "STATUS_SHOW_SPEC_TEXT",
                    "UNFINISHED_STATES": "STATUS_SHOW_UNFINISHED_STATES"},
    "new_declares": {"UNFINISHED_STATES": "NEW_DECLARES_UNFINISHED_STATES"},
}
CASE_HELPERS = {("answer", "accepted"), ("answer", "assert_refused"),
                ("plan", "approve_spec"), ("plan", "prepared_task"),
                ("new_declares", "declared"),
                ("new_declares", "assert_refused_without_traces")}
LABEL_HELPERS = {("plan", "rejected_case")}
LABELLED = {m for _p, m in CASE_HELPERS | LABEL_HELPERS}
# Локальные, совпадающие с функциями модуля волны 3м-2 (требование 9).
LOCAL_RENAMES = {
    ("answer", "test_ac11_escalated_answer_sets_and_clears_value"): {"journal": "entries"},
    ("plan", "test_ac9_justified_plan_value_replaces_db_value"): {"journal": "entries"},
    ("plan", "test_ac9_empty_plan_value_clears_dependencies"): {"journal": "entries"},
    ("plan", "test_ac10_rejected_plan_value_keeps_db_and_transition"): {"journal": "entries"},
    ("spec_gate", "assert_refused"): {"journal": "entries"},
    ("spec_gate", "test_ac2_missing_task_keeps_spec_gate_and_column_empty"): {"task": "task_id"},
    ("new_declares", "test_ac1_order_line_declares_full_ids_in_line_order"): {"journal": "entries"},
    ("new_declares", "test_ac3_order_line_without_after_declares_nothing"): {"journal": "entries"},
    ("guard", "test_ac1_self_reference_names_field_and_element"): {"task": "task_id"},
    ("guard", "test_ac1_repeated_element_is_a_repeat_error"): {"task": "task_id"},
    ("guard", "test_ac1_element_not_in_task_id_format_is_a_form_error"): {"task": "task_id"},
    ("guard", "test_ac1_valid_list_and_missing_field_pass"): {"task": "task_id"},
}
CMP = {"assertEqual": "==", "assertNotEqual": "!=", "assertIn": "in",
       "assertNotIn": "not in", "assertIs": "is", "assertIsNot": "is not"}
ONE = {"assertTrue", "assertFalse", "assertIsNone", "assertIsNotNone"}
SAFE = (ast.Name, ast.Attribute, ast.Call, ast.Subscript, ast.Constant,
        ast.JoinedStr, ast.List, ast.Tuple, ast.Dict, ast.ListComp, ast.Set,
        ast.DictComp, ast.SetComp, ast.GeneratorExp, ast.BinOp)


def seg(src, node):
    return ast.get_source_segment(src, node)


def wrap(src, node, safe=SAFE):
    text = seg(src, node)
    return text if isinstance(node, safe) else f"({text})"


def is_self_call(node, names=None):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "self"
            and (names is None or node.func.attr in names))


def assert_text(src, call, extra, col):
    """`assert …` для `self.assertX(…)`; `extra(msg_text)` — сообщение."""
    name, args = call.func.attr, call.args
    count = 1 if name in ONE else 2
    msg = args[count] if len(args) > count else next(
        (k.value for k in call.keywords if k.arg == "msg"), None)
    if name in CMP:
        test = f"{wrap(src, args[0])} {CMP[name]} {wrap(src, args[1])}"
    elif name == "assertIsNone":
        test = f"{wrap(src, args[0])} is None"
    elif name == "assertIsNotNone":
        test = f"{wrap(src, args[0])} is not None"
    elif name == "assertTrue":
        test = seg(src, args[0])
    elif name == "assertFalse":
        test = f"not {wrap(src, args[0], SAFE + (ast.Compare,))}"
    elif name == "assertRegex":
        test = f"re.search({seg(src, args[1])}, {seg(src, args[0])})"
    else:
        raise ValueError(name)
    msg_text = None if msg is None else wrap(src, msg)
    msg_text = extra(msg_text)
    inner = col + 4
    if "\n" in test:
        test = "(" + rebase(test, inner + 1) + ")"
    if msg_text is None:
        return f"assert {test}"
    one = f"assert {test}, {msg_text}"
    if "\n" not in one and col + len(one) <= 79:
        return one
    return f"assert {test}, (\n{' ' * inner}{rebase(msg_text, inner)})"


def rebase(text: str, indent: int) -> str:
    """Строки продолжения `text` — с отступом `indent` (относительный
    сдвиг между ними сохраняется)."""
    lines = text.split("\n")
    rest = [l for l in lines[1:] if l.strip()]
    if not rest:
        return text
    low = min(len(l) - len(l.lstrip()) for l in rest)
    return "\n".join([lines[0]] + [" " * indent + l[low:] if l.strip() else l
                                   for l in lines[1:]])


def subtest_label(with_node):
    for item in with_node.items:
        call = item.context_expr
        if is_self_call(call, {"subTest"}):
            return " + ".join(
                ['"; "'] + [f'f"{k.arg}={{{ast.unparse(k.value)}!r}}"' for k in call.keywords])
    return None


def convert_method(prefix, method, helpers, param, *, kind):
    """Текст функции модуля из исходника метода (уже без отступа класса)."""
    src = method
    tree = ast.parse(src)
    func = tree.body[0]
    case_name = ("case" if (prefix, func.name) in CASE_HELPERS else
                 "label" if (prefix, func.name) in LABEL_HELPERS else None)
    lines = src.split("\n")
    offs = [0]
    for line in lines:
        offs.append(offs[-1] + len(line) + 1)

    # col_offset у ast — в байтах utf-8; перевод в символы строки.
    def cpos(ln, col):
        raw = lines[ln - 1].encode("utf-8")[:col].decode("utf-8")
        return offs[ln - 1] + len(raw)

    withs = []
    for node in ast.walk(func):
        if isinstance(node, ast.With):
            label = subtest_label(node)
            if label:
                withs.append((node, label))

    def label_of(node):
        for w, label in withs:
            if w.lineno <= node.lineno <= w.end_lineno:
                return label
        return None

    edits = []
    for node in ast.walk(func):
        if isinstance(node, ast.Expr) and is_self_call(node.value) \
                and node.value.func.attr.startswith("assert") \
                and not node.value.func.attr.startswith("assert_"):
            label = label_of(node)

            def extra(m, label=label):
                if case_name:
                    return f"{m} + {case_name}"
                if label:
                    return f'{m} + {label}' if m is not None else label.split(" + ", 1)[1]
                return m
            text = assert_text(src, node.value, extra, node.col_offset)
            edits.append((cpos(node.lineno, node.col_offset),
                          cpos(node.end_lineno, node.end_col_offset), text))
        elif is_self_call(node, LABELLED) and (prefix, node.func.attr) in \
                CASE_HELPERS | LABEL_HELPERS:
            label = label_of(node)
            add = case_name if case_name else label
            if add:
                end = cpos(node.end_lineno, node.end_col_offset) - 1
                sep = ", " if (node.args or node.keywords) else ""
                edits.append((end, end, f"{sep}{add}"))
    if case_name:
        last = func.args.args[-1]
        at = cpos(last.end_lineno, last.end_col_offset)
        edits.append((at, at, f", {case_name}: str = \"\""))
    edits.sort(key=lambda e: (e[0], e[1]), reverse=True)
    for start, end, text in edits:
        src = src[:start] + text + src[end:]
    # subTest: строка `with` уходит, тело — на 4 пробела левее.
    while True:
        tree = ast.parse(src)
        found = [n for n in ast.walk(tree) if isinstance(n, ast.With) and subtest_label(n)]
        if not found:
            break
        w = max(found, key=lambda n: n.lineno)
        lines = src.split("\n")
        body = lines[w.body[0].lineno - 1:w.end_lineno]
        body = [b[4:] if b.startswith("    ") else b for b in body]
        lines[w.lineno - 1:w.end_lineno] = body
        src = "\n".join(lines)
    # self.<помощник>(…) → <префикс>_<помощник>(<стенд>, …); статический — без стенда.
    def call_sub(m):
        name = m.group(1)
        if name in helpers["static"]:
            return f"{prefix}_{name}("
        return f"{prefix}_{name}({param}, "
    names = "|".join(sorted(helpers["all"], key=len, reverse=True))
    src = re.sub(rf"\bself\.({names})\(", call_sub, src)
    src = src.replace(f"({param}, )", f"({param})")
    for name in helpers["static"]:
        src = re.sub(rf"\bself\.{name}\b", f"{prefix}_{name}", src)
    src = re.sub(r"\bself\b", param, src)
    for old, new in RENAMES.get(prefix, {}).items():
        src = re.sub(rf"(?<![\w.]){old}\b", new, src)
    for old, new in LOCAL_RENAMES.get((prefix, func.name), {}).items():
        src = re.sub(rf"(?<![\w.]){old}(?!\w|=[^=])", new, src)
    if kind == "helper":
        src = re.sub(r"^def (\w+)\(", lambda m: f"def {prefix}_{m.group(1)}(", src, count=1)
    return src


def main():
    out = []
    for prefix, path, setup_cls, stand_param, head in FILES:
        text = pathlib.Path(path).read_text(encoding="utf-8")
        tree = ast.parse(text)
        lines = text.split("\n")
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        out.append(f"# --- {', '.join(c.name for c in classes)} (бывший "
                   f"{pathlib.Path(path).name}) ---\n")
        skip = SKIP_CONST.get(prefix, set())
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.FunctionDef)):
                name = node.name if isinstance(node, ast.FunctionDef) else node.targets[0].id
                if name in skip:
                    continue
                block = "\n".join(lines[node.lineno - 1:node.end_lineno])
                for old, new in RENAMES.get(prefix, {}).items():
                    block = re.sub(rf"^{old}\b", new, block)
                out.append(block + ("\n\n" if isinstance(node, ast.FunctionDef) else ""))
        out.append("")
        methods, static = {}, set()
        for cls in classes:
            for item in cls.body:
                if isinstance(item, ast.FunctionDef):
                    methods.setdefault(cls.name, []).append(item)
                    if any(isinstance(d, ast.Name) and d.id == "staticmethod"
                           for d in item.decorator_list):
                        static.add(item.name)
        helper_names = {m.name for ms in methods.values() for m in ms
                        if not m.name.startswith("test") and m.name != "setUp"}
        helpers = {"all": helper_names, "static": static}

        def method_src(m):
            start = m.lineno
            return textwrap.dedent("\n".join(lines[start - 1:m.end_lineno]))

        # фикстура стенда
        setup = next(m for m in methods[setup_cls] if m.name == "setUp")
        body = [s for s in setup.body
                if not (isinstance(s, ast.Expr) and "super().setUp()" in ast.unparse(s))]
        if head:
            body = body[:head]
        body_src = textwrap.dedent("\n".join(lines[body[0].lineno - 1:body[-1].end_lineno]))
        fake = "def setUp(self):\n" + textwrap.indent(body_src, "    ")
        conv = convert_method(prefix, fake, helpers, stand_param, kind="fixture")
        conv_body = conv.split("\n", 1)[1]
        out.append(f"@pytest.fixture\ndef {prefix}_stand({stand_param}):\n"
                   f"    \"\"\"Стенд бывшего `{setup_cls}`: тело его `setUp`.\"\"\"\n"
                   f"{conv_body}\n    return {stand_param}\n\n")
        for cls in classes:
            for m in methods.get(cls.name, []):
                if m.name.startswith("test") or m.name == "setUp":
                    continue
                src = method_src(m)
                if m.name in static:
                    src = "\n".join(l for l in src.split("\n") if l.strip() != "@staticmethod")
                conv = convert_method(prefix, src, helpers, "stand", kind="helper")
                out.append(conv + "\n\n")
        for cls in classes:
            for m in methods.get(cls.name, []):
                if not m.name.startswith("test"):
                    continue
                conv = convert_method(prefix, method_src(m), helpers,
                                      f"{prefix}_stand", kind="test")
                out.append(conv + "\n\n")
    (DOCS / "sections.txt").write_text("\n".join(out).rstrip("\n") + "\n", encoding="utf-8")
    print("готово")


if __name__ == "__main__":
    main()
