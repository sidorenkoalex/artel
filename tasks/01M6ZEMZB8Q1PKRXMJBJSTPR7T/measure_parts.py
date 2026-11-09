"""Доли наполнения префикса: запрос сведений, чтение шаблона, копия."""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, ".")
from orchestrator import acceptance, config, stack  # noqa: E402

base = Path(tempfile.mkdtemp(prefix="measure-parts-"))
config.PYCACHE_TEMPLATES_DIR = str(base / "templates")
interp = stack.pytest_python_executable()
env = {k: v for k, v in os.environ.items()
       if k not in ("PYTHONPYCACHEPREFIX", "PYTHONDONTWRITEBYTECODE")}
prefix = tempfile.mkdtemp()
acceptance._warm_prefix(prefix, interp, base, env.get("PATH"), env)
for _ in range(3):
    t = time.monotonic()
    info = acceptance._interpreter_info(interp, env)
    t1 = time.monotonic()
    tpl = acceptance.template_dir(info["executable"], info["version"], info["prefix"])
    ok, adm = acceptance._read_template(tpl, acceptance._real_paths(info["paths"]),
                                        acceptance._real_paths([base]))
    t2 = time.monotonic()
    p = tempfile.mkdtemp()
    acceptance._copy_into(p, adm)
    t3 = time.monotonic()
    size = sum(len(b) for b in adm.values())
    print(f"запрос {t1 - t:.3f} чтение {t2 - t1:.3f} копия {t3 - t2:.3f} "
          f"файлов {len(adm)} байт {size}")
