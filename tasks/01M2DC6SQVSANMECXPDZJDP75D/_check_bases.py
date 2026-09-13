import ast
import sys

for path in sys.argv[1:]:
    text = open(path, encoding="utf-8").read()
    tree = ast.parse(text)
    imported = set()
    other_imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                name = a.asname or a.name
                if node.module and "sandbox" in node.module:
                    imported.add(name)
                else:
                    other_imports.add(name)
        if isinstance(node, ast.Import):
            for a in node.names:
                other_imports.add(a.asname or a.name.split(".")[0])
    used_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for b in node.bases:
                for sub in ast.walk(b):
                    if isinstance(sub, ast.Name):
                        used_names.add(sub.id)
    defined_locally = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    missing = used_names - imported - other_imports - defined_locally
    if missing:
        print(f"{path}: POSSIBLY UNDEFINED bases: {missing}")
    else:
        print(f"{path}: ok")
