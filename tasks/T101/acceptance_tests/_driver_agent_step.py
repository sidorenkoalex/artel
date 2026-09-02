"""Драйвер-подпроцесс приёмочных тестов T101 (не test_*.py, не участвует
в `unittest discover`): один прогон `runner.cmd_run` в изолированном
процессе — печатает JSON с журналом шага на stdout. См. `_sandbox.py`
про то, почему отдельный процесс на сценарий.

argv: <root_dir> <git_behavior> <claude_behavior>
  behavior ∈ {ok, missing, timeout}

Печатает одну строку JSON:
{"details": {"agent run started": [...], "agent run finished": [...], ...},
 "git_calls": [<timeout передан в subprocess.run для git --version>, ...],
 "claude_calls": [...],
 "state": "<состояние задачи после прогона>"}

Песочница — облегчённая, без реального git (по образцу
`tests/test_step_cost.py::CmdRunCostTest`): `gitcmd.git` подменён чистой
функцией `fake_git`, поэтому единственные РЕАЛЬНЫЕ вызовы `subprocess.run`
на этом пути — те, что (предположительно) сделает сам сборщик fingerprint
для `git --version`/`claude --version`; всё остальное git-общение уходит
в `fake_git` до `subprocess` вообще не добираясь.
"""
import io
import json
import shutil
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT_DIR = Path(sys.argv[1])
GIT_BEHAVIOR = sys.argv[2]
CLAUDE_BEHAVIOR = sys.argv[3]

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog, config, doctor, gitcmd, runner, store  # noqa: E402
from tests.sandbox import FakeProc, fake_git  # noqa: E402

TASK = "T001"

for _attr, _value in (
    ("ROOT", ROOT_DIR),
    ("DB", ROOT_DIR / ".artel" / "state.db"),
    ("TASKS", ROOT_DIR / "tasks"),
    ("LOGS", ROOT_DIR / ".artel" / "logs"),
    ("WORKTREES", ROOT_DIR / ".artel" / "worktrees"),
    ("ROLE_HOME", ROOT_DIR / ".artel" / "home"),
    ("ROLE_CONFIG_DIR", ROOT_DIR / ".artel" / "home" / ".claude"),
):
    setattr(config, _attr, _value)

shutil.copytree(REPO_ROOT / "templates", ROOT_DIR / "templates")
shutil.copytree(REPO_ROOT / "skills", ROOT_DIR / "skills")
(ROOT_DIR / "docs").mkdir(parents=True, exist_ok=True)
(ROOT_DIR / "docs" / "codebase-map.md").write_text(
    "---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
    "---\n\n# Карта\n", encoding="utf-8")
(ROOT_DIR / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")

gitcmd.git = fake_git
runner.keychain.token = lambda slot: "tok-test"
runner.time.sleep = lambda _: None
doctor.preflight_checks = lambda role, target: []

REAL_RUN = subprocess.run
GIT_CALLS: list = []
CLAUDE_CALLS: list = []


def custom_run(cmd, *a, **kw):
    if cmd and cmd[0] == "git" and "--version" in cmd:
        GIT_CALLS.append(kw.get("timeout"))
        if GIT_BEHAVIOR == "missing":
            raise FileNotFoundError("git не найден (симуляция T101)")
        if GIT_BEHAVIOR == "timeout":
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=kw.get("timeout") or 5)
        return subprocess.CompletedProcess(cmd, 0, "git version 2.43.0\n", "")
    if cmd and cmd[0] == "claude" and "--version" in cmd:
        CLAUDE_CALLS.append(kw.get("timeout"))
        if CLAUDE_BEHAVIOR == "missing":
            raise FileNotFoundError("claude не найден (симуляция T101)")
        if CLAUDE_BEHAVIOR == "timeout":
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=kw.get("timeout") or 5)
        return subprocess.CompletedProcess(
            cmd, 0, f"{config.CLI_VERSION_PIN} (Claude Code)\n", "")
    return REAL_RUN(cmd, *a, **kw)


subprocess.run = custom_run

catalog.cmd_init()
catalog.cmd_new("Fingerprint окружения — драйвер T101")

# Лёгкая песочница без реального git: `cmd_new` пишет SPEC только в
# worktree (`config.WORKTREES/<id>/tasks/<id>/`), легаси-путь чтения
# брифа разработчика читает `config.TASKS` — зеркалим (тот же приём, что
# `tests.sandbox.sync_spec_from_worktree`).
_wt_spec = config.WORKTREES / TASK / "tasks" / TASK / "SPEC.md"
_dest_dir = config.TASKS / TASK
_dest_dir.mkdir(parents=True, exist_ok=True)
(_dest_dir / "SPEC.md").write_text(
    _wt_spec.read_text(encoding="utf-8"), encoding="utf-8")

_conn = store.db()
_conn.execute("UPDATE tasks SET state='in_dev' WHERE id=?", (TASK,))
_conn.commit()

_result_event = json.dumps({
    "type": "result", "subtype": "success", "is_error": False,
    "result": "готово", "total_cost_usd": 0.01,
}, ensure_ascii=False) + "\n"
_proc = FakeProc([_result_event], 0)
runner.spawn_agent = lambda *a, **k: _proc

_buf = io.StringIO()
with redirect_stdout(_buf):
    runner.cmd_run(TASK)

subprocess.run = REAL_RUN

_conn = store.db()
_rows = _conn.execute(
    "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
    (TASK,)).fetchall()
_details: dict = {}
for _r in _rows:
    _details.setdefault(_r["action"], []).append(_r["detail"])
_state = _conn.execute(
    "SELECT state FROM tasks WHERE id=?", (TASK,)).fetchone()["state"]

print(json.dumps({
    "details": _details,
    "git_calls": GIT_CALLS,
    "claude_calls": CLAUDE_CALLS,
    "state": _state,
    "stdout": _buf.getvalue(),
}, ensure_ascii=False))
