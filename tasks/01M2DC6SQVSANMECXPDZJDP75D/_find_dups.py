import ast
import hashlib
import sys
from pathlib import Path
from collections import defaultdict

TESTS = Path("tests")
EXCLUDE = {"test_invariants.py", "sandbox.py"}

def norm_body(src_lines, node):
    # get source segment of function/method body via lineno/end_lineno
    seg = ast.get_source_segment("\n".join(src_lines), node)
    return seg

setups = defaultdict(list)  # hash -> list of (file, class, lineno, code)
helpers = defaultdict(list)  # name -> hash -> list of (file, lineno, code)
patched_attrs = []  # (file, class, lineno, value_src)

for path in sorted(TESTS.glob("*.py")):
    if path.name in EXCLUDE:
        continue
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as e:
        print("SYNTAX ERROR", path, e)
        continue
    lines = text.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "setUp":
                    seg = ast.get_source_segment(text, item)
                    h = hashlib.sha256(seg.encode()).hexdigest()
                    setups[h].append((str(path), node.name, item.lineno, seg))
                if isinstance(item, ast.Assign):
                    for t in item.targets:
                        if isinstance(t, ast.Name) and t.id == "PATCHED_ATTRS":
                            seg = ast.get_source_segment(text, item)
                            patched_attrs.append((str(path), node.name, item.lineno, seg))
        if isinstance(node, ast.FunctionDef) and node.col_offset == 0:
            # top-level function (helper)
            seg = ast.get_source_segment(text, node)
            h = hashlib.sha256(seg.encode()).hexdigest()
            helpers[node.name].append((str(path), node.lineno, seg, h))

print("=== setUp duplicate groups (>=2 files/classes) ===")
count = 0
for h, entries in setups.items():
    if len(entries) >= 2:
        count += 1
        print(f"--- group {count} ({len(entries)} occurrences) ---")
        for f, cls, ln, seg in entries:
            print(f"  {f}:{ln} class {cls}")

print()
print("=== helper function duplicate groups (same name, same body, >=2 files) ===")
for name, entries in helpers.items():
    by_hash = defaultdict(list)
    for f, ln, seg, h in entries:
        by_hash[h].append((f, ln))
    if len(entries) >= 2:
        # only interesting if appears in >1 file
        files = set(f for f, ln, seg, h in entries)
        if len(files) >= 2:
            print(f"--- helper: {name} ({len(entries)} defs across {len(files)} files) ---")
            for h, occ in by_hash.items():
                same = "SAME BODY" if len(occ) >= 2 else "diff body"
                print(f"  [{same}]")
                for f, ln in occ:
                    print(f"    {f}:{ln}")

print()
print("=== PATCHED_ATTRS occurrences ===")
for f, cls, ln, seg in patched_attrs:
    print(f"{f}:{ln} class {cls}: {seg}")
