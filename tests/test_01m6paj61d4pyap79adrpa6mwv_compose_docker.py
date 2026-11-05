"""Необязательный прогон вымышленного Compose-файла настоящим Docker и условия его пропуска.

Группа: долгоживущий

`test_ac17_real_docker_compose_run` гоняет место `acceptance.report_run` с
профилем `compose` настоящим Docker: вымышленный проект во временной
песочнице (`real_git`), образ `IMAGE` только из локального кэша (у каждого
сервиса `pull_policy: never`, сети нет), `DOCKER_CONFIG` — каталог песочницы,
`down -v` стендов прогона — в `finally`. Он пропускается с именованной
причиной (`docker_skip_reason`): выставлена переменная `CI`, Docker не
отвечает на пробу за `PROBE_TIMEOUT_SEC` (10 с), образа нет в локальном кэше
(`docker image inspect`).

Остальные методы проверяют сами условия пропуска и форму вымышленного
Compose-файла без настоящего Docker: программа `docker` подменена
исполнителем на Python в каталоге PATH теста (журнал вызовов, ответ по
сценарию, зависание — `os.execv` программы `sleep`).

Красен до реализации: прогон с настоящим Docker отказывает — раннера `compose` нет (запись не загружается); без Docker, без образа или при `CI` он пропускается. Методы условий пропуска и формы Compose-файла держат свойство самого файла и зелены с рождения.
"""
import json
import os
import random
import shutil
import signal
import string
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from orchestrator import acceptance, config, project_profile, targets, yamlmini

IMAGE = "alpine:3"
PROBE_TIMEOUT_SEC = 10
SLEEP = shutil.which("sleep") or "/bin/sleep"
LETTERS = string.ascii_lowercase
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

COMPOSE_TEMPLATE = """services:
  tests:
    image: {image}
    pull_policy: never
    depends_on: [cache]
    volumes: [../{left}:/work]
    working_dir: /work
  cache:
    image: {image}
    pull_policy: never
    command: sleep 300
"""

RUN_TESTS = """#!/bin/sh
out=""
while [ $# -gt 0 ]; do
  if [ "$1" = "--junitxml" ]; then out="$2"; shift; fi
  shift
done
mkdir -p "$(dirname "$out")"
printf '%s' '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" errors="0" failures="0" skipped="0" tests="1"><testcase classname="tests.test_probe" name="test_ok" time="0.001"/></testsuite></testsuites>' > "$out"
"""

PROBE_TEST = '''def test_ok():
    assert True
'''

FAKE_DOCKER = r'''#!@PYTHON@
import json
import os
import sys

STATE = @STATE@
with open(os.path.join(STATE, "scenario.json"), encoding="utf-8") as fh:
    sc = json.load(fh)
args = sys.argv[1:]
with open(os.path.join(STATE, "calls.jsonl"), "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"argv": args, "env": dict(os.environ)}) + "\n")
key = " ".join(args[:2])
act = sc.get(key, {})
if act.get("hang"):
    os.execv(@SLEEP@, [@SLEEP@, "600"])
sys.stdout.write(act.get("stdout", ""))
sys.exit(act.get("code", 0))
'''


def compose_text(left: str, image: str = IMAGE) -> str:
    return COMPOSE_TEMPLATE.format(left=left, image=image)


def docker_skip_reason() -> str | None:
    """Причина пропуска прогона с настоящим Docker; None — прогон идёт.

    Проба — с `DOCKER_CONFIG` во временном каталоге (настоящий `~/.docker` не
    читается) и пределом `PROBE_TIMEOUT_SEC` на каждый вызов."""
    if os.environ.get("CI"):
        return "выставлена переменная CI — прогон с настоящим Docker не идёт"
    docker = shutil.which("docker")
    if docker is None:
        return "Docker не отвечает: программы docker нет в PATH"
    with tempfile.TemporaryDirectory(prefix="artel-docker-probe-") as home:
        env = dict(os.environ, DOCKER_CONFIG=home)
        try:
            probe = subprocess.run(
                [docker, "version", "--format", "{{.Server.Version}}"],
                env=env, capture_output=True, text=True,
                timeout=PROBE_TIMEOUT_SEC, start_new_session=True)
            if probe.returncode != 0:
                return (f"Docker не отвечает на пробу: код {probe.returncode} "
                        f"{probe.stderr.strip()[:200]}")
            image = subprocess.run(
                [docker, "image", "inspect", IMAGE], env=env,
                capture_output=True, text=True, timeout=PROBE_TIMEOUT_SEC,
                start_new_session=True)
        except subprocess.TimeoutExpired:
            return (f"Docker не отвечает на пробу за {PROBE_TIMEOUT_SEC} с")
        except OSError as exc:
            return f"Docker не отвечает на пробу: {exc}"
    if image.returncode != 0:
        return f"образа {IMAGE} нет в локальном кэше Docker (docker image inspect)"
    return None


SKIP_REASON = docker_skip_reason()


def word(rng, k: int = 6) -> str:
    return "".join(rng.choices(LETTERS, k=k))


@pytest.fixture
def fake_docker(tmp_path, monkeypatch):
    """Подменённый `docker` в начале PATH теста; `CI` снят."""
    state = tmp_path / "state"
    state.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    docker = bindir / "docker"
    docker.write_text(FAKE_DOCKER.replace("@PYTHON@", sys.executable)
                      .replace("@STATE@", repr(str(state)))
                      .replace("@SLEEP@", repr(SLEEP)), encoding="utf-8")
    docker.chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join(
        [str(bindir), os.environ.get("PATH", "")]))
    monkeypatch.delenv("CI", raising=False)
    procs = []
    real_popen = subprocess.Popen

    class TrackedPopen(real_popen):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            procs.append(self)

    monkeypatch.setattr(subprocess, "Popen", TrackedPopen)
    try:
        yield state
    finally:
        for proc in procs:
            if proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    proc.kill()
                proc.wait(timeout=5)


def write_scenario(state: Path, scenario: dict) -> None:
    (state / "scenario.json").write_text(json.dumps(scenario), encoding="utf-8")


def calls(state: Path) -> list:
    path = state / "calls.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] \
        if path.exists() else []


@pytest.mark.parametrize("condition, expected", [
    ("silent", "Docker не отвечает"),
    ("hang", "Docker не отвечает"),
    ("no_image", IMAGE),
    ("ci", "CI"),
])
def test_ac17_skip_reason_named_for_each_condition(fake_docker, monkeypatch,
                                                   condition, expected):
    """Каждое условие пропуска даёт свою именованную причину; без условий — прогон идёт.

    Подменённый `docker`: `version` с ненулевым кодом; `version`, зависающий
    дольше предела пробы (предел подменён 1 с, его значение в файле — 10 с);
    `image inspect` с ненулевым кодом; выставленная `CI` — `docker` не
    вызывается вовсе. Контроль: `version` и `image inspect` с кодом 0 —
    причины нет. Проба идёт с `DOCKER_CONFIG` не из `HOME`.

    Ловит мутацию: проба без предела (зависание висит до предела теста),
    проверка `CI` после вызова `docker` или пропущена, отсутствие образа не
    проверено (прогон тянул бы образ из сети), проба читает настоящий
    `~/.docker`.
    """
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    assert PROBE_TIMEOUT_SEC == 10
    module = sys.modules[__name__]
    monkeypatch.setattr(module, "PROBE_TIMEOUT_SEC", 1)
    scenario = {"version --format": {"stdout": "27.0.0"},
                "image inspect": {"stdout": "[]"}}
    if condition == "silent":
        scenario["version --format"] = {"code": 1}
    elif condition == "hang":
        scenario["version --format"] = {"hang": True}
    elif condition == "no_image":
        scenario["image inspect"] = {"code": 1}
    else:
        monkeypatch.setenv("CI", "true")
    write_scenario(fake_docker, scenario)
    reason = docker_skip_reason()
    where = f"зерно {seed}, {condition}: {reason!r}"
    assert reason and expected in reason, where
    if condition == "ci":
        assert calls(fake_docker) == [], where
    for call in calls(fake_docker):
        assert call["env"].get("DOCKER_CONFIG") and not call["env"][
            "DOCKER_CONFIG"].startswith(os.environ.get("HOME", "\0")), where
    monkeypatch.delenv("CI", raising=False)
    write_scenario(fake_docker, {"version --format": {"stdout": "27.0.0"},
                                 "image inspect": {"stdout": "[]"}})
    assert docker_skip_reason() is None, where


def test_ac17_fictional_compose_file_never_pulls():
    """У каждого сервиса вымышленного Compose-файла — `pull_policy: never`, образы — только `IMAGE`.

    Ловит мутацию: сервис без `pull_policy: never` (или с другим образом) —
    прогон с настоящим Docker скачал бы образ из сети.
    """
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    left = f"src_{word(random.Random(seed))}"
    services = yamlmini.mapping(compose_text(left))["services"]
    assert services, f"зерно {seed}"
    for name, fields in services.items():
        assert fields.get("pull_policy") == "never", f"зерно {seed}: {name}"
        assert fields.get("image") == IMAGE, f"зерно {seed}: {name}"


def compose_projects(prefix: str, env: dict) -> list:
    docker = shutil.which("docker")
    res = subprocess.run([docker, "compose", "ls", "-a", "--format", "json"],
                         env=env, capture_output=True, text=True, timeout=60,
                         start_new_session=True)
    try:
        rows = json.loads(res.stdout or "[]")
    except ValueError:
        return []
    return [row.get("Name", "") for row in rows
            if row.get("Name", "").startswith(prefix)]


@pytest.mark.skipif(SKIP_REASON is not None, reason=SKIP_REASON or "")
def test_ac17_real_docker_compose_run(real_git, monkeypatch):
    """Настоящий Docker: прогон вымышленного Compose-файла — зелёный итог по отчёту, стенд снят.

    Проект песочницы: Compose-файл (служба-зависимость и сервис тестов на
    образе `IMAGE` из кэша), команда записи — сценарий `sh`, пишущий отчёт
    JUnit по пути `--junitxml`. `report_run` с `task_id` — зелёный, без
    отказа; после прогона проектов Compose с префиксом `artel-<id>-` нет. В
    `finally` — `down -v` каждого такого проекта.

    Ловит мутацию: перекрытие ломает настоящую конфигурацию Compose (сеть,
    метки, путь отчёта под монтированием) — `config`/`run` настоящего Docker
    падают или отчёт не читается с машины; стенд не снимается — проект
    остаётся в `docker compose ls`.
    """
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    tree = Path(real_git.root)
    left, deploy = f"src_{word(rng)}", f"deploy_{word(rng)}"
    (tree / left / "tests").mkdir(parents=True)
    (tree / left / "tests" / "test_probe.py").write_text(PROBE_TEST,
                                                         encoding="utf-8")
    (tree / left / "run_tests.sh").write_text(RUN_TESTS, encoding="utf-8")
    (tree / deploy).mkdir()
    (tree / deploy / "compose.yaml").write_text(compose_text(left),
                                                encoding="utf-8")
    (tree / deploy / "env.template").write_text("PROBE=1\n", encoding="utf-8")
    real_git.git("add", "-A")
    real_git.git("commit", "-q", "-m", "вымышленный проект compose")
    name = f"proj{word(rng)}"
    record = "\n".join([
        f"  {name}:", "    description:", "      base: main",
        "      test_profile:", '        runner: "compose"',
        f'        workdir: "{left}"', f'        long_lived_dir: "{left}/tests"',
        '        long_lived_name: "test_<id>_<name>.py"',
        '        report: "junit-xml"', "        command: [sh, run_tests.sh]",
        f'        compose_file: "{deploy}/compose.yaml"',
        '        compose_service: "tests"',
        f'        compose_env_file: "{deploy}/.env.test"',
        f'        compose_env_template: "{deploy}/env.template"',
        f'        compose_mount: "{left}:/work"',
        "    policy:", "      no_paths: []", "      project_skills: []",
        "      merge_gate: operator",
        f"      weakening_scope: [{left}/tests/**/*.py]",
        f"      mutation_claim_scope: [{left}/tests/test_*.py]",
        "    machine:", "      forge: github",
        f"      url: https://localhost/team/{name}",
        f"      token_slot: {name}-token"]) + "\n"
    path = targets.local_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("targets:\n" + record, encoding="utf-8")
    values = targets.target(name)[targets.PROFILE_FIELD]
    profile = project_profile.with_tools(
        name, project_profile.Profile.from_values(values))
    docker_config = Path(tempfile.mkdtemp(prefix="artel-docker-config-"))
    real_git.addCleanup(shutil.rmtree, docker_config, True)
    monkeypatch.setenv("DOCKER_CONFIG", str(docker_config))
    monkeypatch.setenv("HOME", str(docker_config.parent))
    monkeypatch.delenv(config.ARTEL_ROLE_ENV, raising=False)
    task = "01" + "".join(rng.choices(CROCKFORD, k=24))
    prefix = f"artel-{task.lower()}-"
    env = dict(os.environ)
    try:
        run = acceptance.report_run(profile, tree, [f"{left}/tests/test_probe.py"],
                                    300.0, task_id=task)
        where = f"зерно {seed}: {run.text()[-800:]}"
        assert run.green and not run.refusal, where
        assert compose_projects(prefix, env) == [], where
    finally:
        docker = shutil.which("docker")
        for project in compose_projects(prefix, env):
            subprocess.run([docker, "compose", "--project-name", project,
                            "down", "-v", "--remove-orphans"], env=env,
                           capture_output=True, timeout=120,
                           start_new_session=True)
