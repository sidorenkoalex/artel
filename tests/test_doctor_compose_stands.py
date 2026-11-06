"""Строка `doctor` «забытые стенды пульта» и её починка (SPEC 01M6PAJ61DP2R2CMM71PJ8W0KF, требование 14).

Сторож после мержа: планка задачи для этой строки разовая, а ключевые
свойства починки — тома не удаляются, стенды живых прогонов и стенды с
испорченными метками не снимаются, процесс роли и `conn=None` не зовут
`docker` — должны держаться и дальше.

Программа `docker` подменена исполнителем на Python в каталоге PATH теста:
он пишет argv, рабочий каталог и его содержимое и отвечает на `context
inspect`/`ps`/`network ls`/`compose down` заданным текстом. Метки в ответе
`ps`/`network ls` — строка `ключ=значение` через запятую, как у Docker.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from orchestrator import acceptance, config, doctor, repo_context, store, targets

PROJECT_LABEL = "com.docker.compose.project"
DEAD_STAND = "artel-01m6paj61dp2r2cmm71pj8w0kf-0123abcd"
LIVE_STAND = "artel-01m6paj61dp2r2cmm71pj8w0kf-4567cdef"
BROKEN_STAND = "artel-01m6paj61dp2r2cmm71pj8w0kf-89abef01"
OLD_START = "2001-01-01 00:00:00Z"

FAKE_DOCKER = r'''#!@PYTHON@
import json
import os
import sys

STATE = @STATE@
args = sys.argv[1:]
if args[:1] == ["compose"]:
    k = "compose down" if "down" in args else "compose"
elif args[:1] == ["network"]:
    k = "network ls"
elif args[:1] == ["context"]:
    k = "context inspect"
else:
    k = args[0] if args else ""
with open(os.path.join(STATE, "scenario.json"), encoding="utf-8") as fh:
    act = json.load(fh).get(k, {})
with open(os.path.join(STATE, "calls.jsonl"), "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"kind": k, "argv": args, "cwd": os.getcwd(),
                         "cwd_entries": sorted(os.listdir("."))}) + "\n")
sys.stdout.write(act.get("stdout", ""))
sys.exit(act.get("code", 0))
'''


def _dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", ""])
    proc.wait()
    return proc.pid


def _labels(project: str, run: dict) -> str:
    labels = {PROJECT_LABEL: project, "com.docker.compose.service": "app",
              **run}
    return ",".join(f"{k}={v}" for k, v in labels.items())


def _run(pid, started: str) -> dict:
    return {"artel.run-pid": str(pid), "artel.run-host": "host-a",
            "artel.run-started": started}


@pytest.fixture
def pult(initialized_tmp_root, monkeypatch, tmp_path):
    """Песочница пульта с проектом `compose`, подменённый `docker` в PATH,
    `ARTEL_ROLE` снят, `HOME` — не дом роли."""
    state = tmp_path / "docker-state"
    state.mkdir()
    bindir = tmp_path / "docker-bin"
    bindir.mkdir()
    fake = bindir / "docker"
    fake.write_text(FAKE_DOCKER.replace("@PYTHON@", sys.executable)
                    .replace("@STATE@", repr(str(state))), encoding="utf-8")
    fake.chmod(0o755)
    home = tmp_path / "pult-home"
    home.mkdir()
    dconf = tmp_path / "docker-config"
    dconf.mkdir()
    monkeypatch.setenv("PATH", os.pathsep.join(
        [str(bindir), *acceptance._OWN_SYSTEM_PATH_DIRS]))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("DOCKER_CONFIG", str(dconf))
    monkeypatch.delenv(config.ARTEL_ROLE_ENV, raising=False)
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    name = "pcompose"
    lines = [f"  {name}:", "    description:", f"      base: {config.MAIN_BRANCH}",
             "      test_profile:", '        workdir: "src/app"',
             '        long_lived_dir: "src/app/tests"',
             '        long_lived_name: "test_<id>_<name>.py"',
             '        report: "junit-xml"',
             '        runner: "compose"',
             '        compose_file: "deploy/compose.yaml"',
             '        compose_service: "app"',
             '        compose_env_file: "deploy/.env"',
             '        compose_env_template: "deploy/env.template"',
             '        compose_mount: "src:/w"',
             "    policy:", "      no_paths: []", "      project_skills: []",
             "      merge_gate: operator",
             "      weakening_scope: [src/app/tests/**/*.py]",
             "      mutation_claim_scope: [src/app/tests/test_*.py]",
             "    machine:", "      forge: github",
             f"      url: https://localhost/team/{name}",
             f"      token_slot: {name}-token"]
    path = targets.local_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("targets:\n" + "\n".join(lines) + "\n", encoding="utf-8")
    targets.load()
    repo_context.clone_path(name).mkdir(parents=True, exist_ok=True)
    stands = [(DEAD_STAND, _run(_dead_pid(), store.now())),
              (LIVE_STAND, _run(os.getpid(), store.now())),
              (BROKEN_STAND, {"artel.run-pid": "12x3",
                              "artel.run-host": "host-a",
                              "artel.run-started": store.now()})]
    ps = [json.dumps({"Names": f"{p}-app-1", "Labels": _labels(p, run)})
          for p, run in stands]
    nets = [json.dumps({"Name": f"{p}_default", "Labels": _labels(p, run)})
            for p, run in stands]
    (state / "scenario.json").write_text(json.dumps({
        "context inspect": {"stdout": "unix:///var/run/docker.sock\n"},
        "ps": {"stdout": "\n".join(ps) + "\n"},
        "network ls": {"stdout": "\n".join(nets) + "\n"},
    }), encoding="utf-8")
    return state


def _calls(state: Path) -> list:
    path = state / "calls.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


def _downs(state: Path) -> list:
    return [c for c in _calls(state) if c["kind"] == "compose down"]


def test_fix_takes_down_only_dead_stand_keeping_volumes(pult):
    """Починка снимает только мёртвый стенд: `down --remove-orphans` без `-v`/`-f` в пустом временном каталоге; живой стенд и стенд с испорченными метками не снимаются.

    Ловит мутацию: `down -v` (тома забытого стенда удаляются); `down` с `-f`
    или в корне пульта/клоне; живость не проверяется (снят стенд живого
    прогона); стенд с неразобранным `artel.run-pid` считается мёртвым и
    снимается.
    """
    row = doctor.check_compose_stands(store.db())
    assert row.status == "warn", row.detail
    assert f"{DEAD_STAND}-app-1" in row.detail, row.detail
    assert f"{LIVE_STAND}-app-1" not in row.detail, row.detail
    doctor._fix_compose_stands(store.db())
    downs = _downs(pult)
    assert len(downs) == 1, downs
    argv = downs[0]["argv"]
    assert argv[argv.index("--project-name") + 1] == DEAD_STAND, argv
    assert "down" in argv and "--remove-orphans" in argv, argv
    for flag in ("-v", "--volumes", "-f", "--file"):
        assert flag not in argv, argv
    assert downs[0]["cwd_entries"] == [], downs[0]
    cwd = os.path.realpath(downs[0]["cwd"])
    assert cwd != os.path.realpath(str(config.ROOT)), cwd
    assert cwd != os.path.realpath(os.getcwd()), cwd


def test_broken_labels_warned_by_project_name(pult):
    """Стенд с `artel.run-pid` не числом — в тексте строки «метки стенда не разобраны» с именем проекта, строка не падает.

    Ловит мутацию: `int()` pid без проверки (исключение наружу); стенд с
    порчей меток молча пропущен.
    """
    row = doctor.check_compose_stands(store.db())
    assert "метки стенда не разобраны" in row.detail, row.detail
    assert BROKEN_STAND in row.detail, row.detail


def test_role_process_calls_no_docker(pult, monkeypatch):
    """В процессе роли (`ARTEL_ROLE` выставлен) строка — `skip`, ни строка, ни починка не зовут `docker`.

    Ловит мутацию: признак процесса роли не проверяется строкой или
    починкой — `docker ps`/`down` зовутся из шага роли.
    """
    monkeypatch.setenv(config.ARTEL_ROLE_ENV, "developer")
    row = doctor.check_compose_stands(store.db())
    assert row.status == "skip", row.detail
    doctor._fix_compose_stands(store.db())
    assert _calls(pult) == []


def test_fix_without_conn_calls_no_docker(pult):
    """Починка при `conn=None` с мёртвым стендом — ни одного вызова `docker`.

    Ловит мутацию: починка не смотрит на `conn` и снимает стенды из
    `cmd_doctor` без БД (настоящий `down` из чужих тестов).
    """
    doctor._fix_compose_stands(None)
    assert _calls(pult) == []
