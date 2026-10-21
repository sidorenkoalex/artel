import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
out = HERE / "spycheck.tsv"
out.unlink(missing_ok=True)
env = dict(os.environ, SPY_OUT=str(out), PYTHONPATH=str(HERE))
r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "spyplug", "-p", "no:xdist",
                    "--no-header", "-p", "no:cacheprovider", *sys.argv[1:]],
                   env=env, capture_output=True, text=True)
print(r.stdout[-1500:], r.stderr[-1500:])
print(out.read_text() if out.exists() else "NO HITS")
out.unlink(missing_ok=True)
