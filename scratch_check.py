import re
from pathlib import Path
files = ['tests/sandbox.py', 'tests/test_canary.py', 'tests/test_doctor.py',
        'tests/test_invariants.py', 'tests/test_multitarget.py',
        'tests/test_multitarget_invariants.py', 'tests/test_review_package.py']
for f in files:
    text = Path(f).read_text(encoding='utf-8')
    print('---', f)
    for line_no, line in enumerate(text.splitlines(), 1):
        if 'role_env(' in line:
            print(line_no, line.strip())
