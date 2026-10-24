import ast, re, subprocess
STANDS = r'(lock_stand|ownership_stand|race_stand|project_stand|queue_stand)'
OPS = {'assertEqual': '==', 'assertNotEqual': '!=', 'assertIn': 'in', 'assertLess': '<',
       'assertGreaterEqual': '>=', 'assertNotIn': 'not in'}


def src(ref, p):
    return subprocess.run(['git', 'show', ref + ':' + p], capture_output=True, text=True).stdout


def norm(s):
    s = s.replace('self.', '').replace('ctx.exception', 'EXC').replace('excinfo.value', 'EXC')
    s = re.sub(r'\b' + STANDS + r'\.', '', s)
    s = re.sub(r'\(' + STANDS + r'(, )?', '(', s)
    s = re.sub(r'\block_row\(', 'row(', s)
    return s


def old_asserts(fn):
    out = []
    for n in ast.walk(fn):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr.startswith('assert') and isinstance(n.func.value, ast.Name)
                and n.func.value.id == 'self'):
            a = n.func.attr
            args = [ast.unparse(x) for x in n.args]
            if a in OPS:
                e = args[0] + ' ' + OPS[a] + ' ' + args[1]; m = args[2:]
            elif a == 'assertIsNone':
                e = args[0] + ' is None'; m = args[1:]
            elif a == 'assertIsNotNone':
                e = args[0] + ' is not None'; m = args[1:]
            elif a == 'assertTrue':
                e = args[0]; m = args[1:]
            elif a == 'assertRaises':
                e = 'RAISES ' + args[0]; m = []
            else:
                e = '??' + a; m = []
            out.append((n.lineno, norm(e), norm(m[0]) if m else None))
    return [x[1:] for x in sorted(out)]


def new_asserts(fn):
    out = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Assert):
            out.append((n.lineno, norm(ast.unparse(n.test)),
                        norm(ast.unparse(n.msg)) if n.msg else None))
        if isinstance(n, ast.Call) and ast.unparse(n.func) == 'pytest.raises':
            out.append((n.lineno, 'RAISES ' + ast.unparse(n.args[0]), None))
    return [x[1:] for x in sorted(out)]


old = {}
for p in ['tests/test_merge_lock.py', 'tests/test_merge_queue.py', 'tests/test_merge_lock_by_project.py']:
    for c in ast.parse(src('9c0e8b8c', p)).body:
        if isinstance(c, ast.ClassDef):
            for f in c.body:
                if isinstance(f, ast.FunctionDef) and f.name.startswith('test_'):
                    old[f.name] = old_asserts(f)
new = {}
for p in ['tests/test_merge_lock_module.py', 'tests/test_merge_queue.py']:
    for f in ast.parse(open(p).read()).body:
        if isinstance(f, ast.FunctionDef) and f.name.startswith('test_'):
            new[f.name] = new_asserts(f)
print(len(old), len(new), set(old) ^ set(new))
bad = 0
for k in old:
    o, n = old[k], new[k]
    if o != n:
        bad += 1
        print('==', k)
        for a, b in zip(o, n):
            if a != b:
                print('  old', a)
                print('  new', b)
        if len(o) != len(n):
            print('  len', len(o), len(n))
print('mismatched tests', bad)
