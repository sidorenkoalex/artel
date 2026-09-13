import ast
import hashlib
from pathlib import Path
from collections import defaultdict

TESTS = Path("tests")
EXCLUDE = {"test_invariants.py", "sandbox.py"}

setups = defaultdict(list)

for path in sorted(TESTS.glob("*.py")):
    if path.name in EXCLUDE:
        continue
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "setUp":
                    seg = ast.get_source_segment(text, item)
                    h = hashlib.sha256(seg.encode()).hexdigest()
                    setups[h].append((str(path), node.name, item.lineno, seg))

groups = [e for e in setups.values() if len(e) >= 2]
groups.sort(key=lambda e: -len(e))
for i, entries in enumerate(groups, 1):
    seg = entries[0][3]
    nlines = seg.count("\n") + 1
    print(f"=== group {i}: {len(entries)} occ, {nlines} lines ===")
    for f, cls, ln, s in entries:
        print(f"  {f}:{ln} {cls}")
    print("--- body ---")
    print(seg)
    print()
