import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAT = (r"all_checks|cmd_doctor|cmd_note|cmd_doc_commit|cmd_approve|fsm_merge_gate|"
       r"_refuse_during_canary|live_run|cmd_canary|cmd_pool_seal|_silence_window|"
       r"refuse_main_move|\"doctor\"|\"note\"|\"approve\"|\"doc-commit\"|\"canary\"|"
       r"'doctor'|'approve'|'note'|artel\.main|artel\.py")
files = subprocess.run(["git", "grep", "-l", "-E", PAT, "tests/"], capture_output=True,
                       text=True, check=True).stdout.split()
files = [f for f in files if f.endswith(".py") and Path(f).name.startswith("test")]
print(len(files), "files", flush=True)
out = HERE / "spy.tsv"
out.unlink(missing_ok=True)
env = dict(os.environ, SPY_OUT=str(out), PYTHONPATH=str(HERE))
N = 8
procs = []
for i in range(N):
    chunk = files[i::N]
    log = open(HERE / f"spylog{i}.txt", "w")
    procs.append((subprocess.Popen(
        [sys.executable, "-m", "pytest", "-q", "-p", "spyplug", "-p", "no:xdist",
         "--no-header", "-p", "no:cacheprovider", *chunk],
        env=env, stdout=log, stderr=subprocess.STDOUT), log))
for p, log in procs:
    p.wait()
    log.close()
for i in range(N):
    lines = (HERE / f"spylog{i}.txt").read_text().splitlines()
    print(i, lines[-1] if lines else "")
