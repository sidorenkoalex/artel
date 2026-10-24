"""Сборка tests/test_report_outcome_module.py (волна 2б-3): шапка + PytestSpy/pytest_output/FLAGS дословно + тело конвертера.

Запуск из корня рабочей копии: python3 <каталог>/assemble_report_outcome.py <файл-тела>
Без аргумента — печатает сводку имён, нужных импортам.
"""
import ast
import builtins
import subprocess
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = "tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py"
src = subprocess.run(["git", "show", f"HEAD:{SOURCE}"], capture_output=True,
                     text=True, check=True).stdout
L = src.split("\n")
t = ast.parse(src)
spy = [n for n in t.body if getattr(n, "name", "") in ("PytestSpy", "pytest_output")]
spy_src = "\n\n\n".join("\n".join(L[n.lineno - 1:n.end_lineno]) for n in spy)
au = [n for n in t.body if getattr(n, "name", "") == "ArtelUnchangedTest"][0]
fl = [n for n in au.body if isinstance(n, ast.Assign)][0]
flags = textwrap.dedent("\n".join(L[fl.lineno - 1:fl.end_lineno]))

body = subprocess.run([sys.executable, str(HERE / "convert_report_outcome.py"), "/dev/stdin"],
                      input=src, capture_output=True, text=True, check=True).stdout

sandbox = ast.parse(Path("tests/report_outcome_sandbox.py").read_text(encoding="utf-8"))
sb = set()
for n in sandbox.body:
    if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
        sb.add(n.name)
    elif isinstance(n, ast.Assign):
        sb |= {tg.id for tg in n.targets if isinstance(tg, ast.Name)}
rest_tree = ast.parse(spy_src + "\n" + flags + "\n" + body)
used = {n.id for n in ast.walk(rest_tree) if isinstance(n, ast.Name)}
STD = ["contextlib", "hashlib", "importlib", "inspect", "io", "json", "os", "random",
       "re", "shutil", "signal", "stat", "subprocess", "sys", "tempfile", "unittest"]
ORCH = ["acceptance", "config", "doctor", "idgen", "project_profile", "stack",
        "store", "suite_run"]
FD = ["high_fd", "select_limited", "wait_readable"]
std = [m for m in STD if m in used]
orch = [m for m in ORCH if m in used]
fd = [m for m in FD if m in used]
sbn = sorted(sb & used)
other = sorted(used - sb - set(STD) - set(ORCH) - set(FD) - {"box", "pytest", "FLAGS", "mock",
              "Path", "Mapping", "two_sided", "make_project_repo", "artel_target_entry",
              "dataclasses", "_sandbox", "ReportSandbox"} - set(dir(builtins))
               - {n.name for n in rest_tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))})
print("std", std, "orch", orch, "fd", fd, "sb", sbn, "other", other,
      "mock" in used, "Path" in used, "two_sided" in used, "make_project_repo" in used,
      file=sys.stderr)

if len(sys.argv) < 2:
    raise SystemExit(0)
head = Path(sys.argv[1]).read_text(encoding="utf-8")
print(head.rstrip("\n") + "\n\n\n" + spy_src + "\n\n\n" + flags + "\n\n\n"
      + "@pytest.fixture\ndef box():\n    yield from _sandbox(ReportSandbox)\n\n\n"
      + body.rstrip("\n"))
