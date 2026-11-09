"""Замер требования 12: полный прогон пульта на проекте из трёх тестов, -n 1."""
import contextlib
import io
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, ".")
from orchestrator import acceptance, config  # noqa: E402

base = Path(tempfile.mkdtemp(prefix="measure-warm-"))
root = base / "proj"
(root / "tests").mkdir(parents=True)
(root / "tests" / "test_three.py").write_text(
    "def test_a(): assert True\n"
    "def test_b(): assert True\n"
    "def test_c(): assert True\n", encoding="utf-8")
config.LOGS = base / "logs"
config.FULL_SUITE_WORKERS = 1
os.environ.pop("PYTHONPYCACHEPREFIX", None)


def once() -> float:
    err = io.StringIO()
    start = time.monotonic()
    with contextlib.redirect_stderr(err):
        green, out = acceptance.run_full_suite(root)
    took = time.monotonic() - start
    assert green, out
    return took


config.PYCACHE_TEMPLATES_DIR = None
cold = [once() for _ in range(5)]
config.PYCACHE_TEMPLATES_DIR = str(base / "templates")
first = once()
warm = [once() for _ in range(5)]
print(f"холодный префикс (до): медиана {statistics.median(cold):.3f} с, {cold}")
print(f"первый прогон со сборкой шаблона: {first:.3f} с")
print(f"тёплый префикс (после): медиана {statistics.median(warm):.3f} с, {warm}")
