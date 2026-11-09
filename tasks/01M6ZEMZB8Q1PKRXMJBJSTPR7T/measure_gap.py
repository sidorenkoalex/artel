"""Что компилируется в тёплом префиксе и предел с полностью общим кешем."""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, ".")
from orchestrator import acceptance, config, stack  # noqa: E402

base = Path(tempfile.mkdtemp(prefix="measure-gap-"))
root = base / "proj"
(root / "tests").mkdir(parents=True)
(root / "tests" / "test_three.py").write_text(
    "def test_a(): assert True\ndef test_b(): assert True\n"
    "def test_c(): assert True\n", encoding="utf-8")
config.PYCACHE_TEMPLATES_DIR = str(base / "templates")
argv = acceptance._pytest_command("tests") + ["-n", "1", "-p", "xdist"]
env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}


def bare(prefix):
    e = dict(env, PYTHONPYCACHEPREFIX=prefix)
    t = time.monotonic()
    subprocess.run(argv, cwd=root, env=e, capture_output=True)
    return time.monotonic() - t


shared = tempfile.mkdtemp()
bare(shared)
print("общий кеш:", [round(bare(shared), 3) for _ in range(3)])
p = tempfile.mkdtemp()
acceptance._warm_prefix(p, argv[0], root, env.get("PATH"), env)
before = {str(x.relative_to(p)) for x in Path(p).rglob("*.pyc")}
print("тёплый (без запроса):", round(bare(p), 3))
after = {str(x.relative_to(p)) for x in Path(p).rglob("*.pyc")}
for rel in sorted(after - before):
    print("  новое:", rel)
print("холодный голый pytest:", [round(bare(tempfile.mkdtemp()), 3) for _ in range(3)])
t = time.monotonic()
for _ in range(5):
    q = tempfile.mkdtemp()
    acceptance._warm_prefix(q, argv[0], root, env.get("PATH"), env)
print("наполнение целиком:", round((time.monotonic() - t) / 5, 3))
