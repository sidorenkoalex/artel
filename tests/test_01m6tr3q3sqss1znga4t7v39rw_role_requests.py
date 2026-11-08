"""Прогоны в контейнере по запросу роли: запрос `plank-run`/`suite-run` в шаге роли проекта с раннером `compose`, исполнитель шага роли, привязка запроса к шагу, снятие стенда в конце шага.

Группа: долгоживущий
Красен до реализации: в процессе роли `plank-run`/`suite-run` проекта с раннером compose отказывают «раннер compose в шаге роли не исполняется» (или уводят прогон в отвязанный фон), очереди запросов `suite-run/<id>/requests/` и исполнителя в `runner.run_agent_once` нет — запрос не записан, итога «принят шагом …» нет, `--wait` у `plank-run` разбирается как имя файла, лишний аргумент молча отбрасывается, в конце шага `docker ps`/явного `down` нет.

Песочница — настоящий git (`real_git`) и КОПИЯ кода пульта (`orchestrator/`,
`scripts/`) в её корне: `config.ROOT` копии считается от расположения
`config.py`, поэтому команды `artel.py` копии, процесс шага роли и дочерние
прогоны исполнителя видят пути песочницы (БД, логи, каталог `suite-run`,
`targets.yaml`, область проектов) — те же, что подменены в процессе теста.
Карта исполнителей и каталог моделей копии — фикстуры `tests/sandbox.py`.

Проекты — вымышленные: проект с раннером `compose` (учебный Compose-файл,
шаблон файла окружения, тест в `workdir`), проект с раннером `pytest-own` с
командой-заглушкой и проект из двух компонентов (`pytest-own` и `compose`).
Клоны и рабочие копии задач — `make_project_repo`/`workspace.ensure`.

Программа `docker` подменена исполнителем на Python в каталоге PATH: каждый
вызов дописывает строку журнала (argv, pid, ppid и сессия вызвавшего
процесса), отвечает `config --format json` заданной конфигурацией, `run` —
отчётом JUnit под монтированием (зелёным или красным), `ps -a --filter
label=com.docker.compose.project --format {{json .}}` — проектами, поднятыми
и ещё не снятыми (метки — из файла пульта `-f`), и проектами сценария.
`run` держится, пока есть файл-«шлагбаум» сценария; `down -v` может
зависать на заданное число секунд.

Шаг роли — `runner.run_agent_once` в процессе-драйвере копии пульта
(подменены только `spawn_agent`, `role_env`, `role_cwd` и слот связки
ключей): «агент» — настоящий процесс в окружении роли (`ARTEL_ROLE`, `HOME` —
дом роли), исполняющий список действий сценария (команды `artel.py` копии,
подложить файл запроса, ждать итог или вызов `docker`) и пишущий журнал
действий. Драйвер, «агент» и все команды — с пределом времени и в своей
группе процессов; уборка снимает группы и процессы по журналу вызовов
заглушек.

Имена проектов, сервисов, каталогов, id задач, номера и поля запросов —
случайные на каждом прогоне; зерно печатается и входит в текст провала.
"""
import json
import os
import random
import re
import shutil
import signal
import socket
import string
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

import pytest

import orchestrator
from orchestrator import (acceptance, agent_log, config, stack, store,
                          suite_lock, workspace)
from tests.sandbox import (_REAL_WHICH, CATALOG_FIXTURE_TEXT,
                           artel_target_entry, make_project_repo)

CODE_ROOT = Path(orchestrator.__file__).resolve().parent.parent
SLEEP = shutil.which("sleep") or "/bin/sleep"
LETTERS = string.ascii_lowercase
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
REQUEST_KEYS = {"kind", "file", "task_id", "time"}
ROLE_COMMAND_REFUSAL = "команда недоступна процессу роли"
NOT_IN_FLIGHT = "запрос без шага роли этой задачи в полёте"
STEP_OVER = "не исполнен: шаг роли завершён"
INTERRUPTED = "прерван: шаг роли завершён"
LOCK_BUSY = "прогон не начат: замок занят"
QUEUED = re.compile(r"запрос в очереди \(позиция (\d+)\), прогон не начат")
STILL_RUNNING = "прогон не прерван, повтори"
REQUEST_ACTION = "прогон по запросу роли"
PS_ARGV = ["ps", "-a", "--filter", "label=com.docker.compose.project",
           "--format", "{{json .}}"]
FULL_ALLOWED_ROLES = ("test_author", "reviewer")

PROJECT_HEAD = """  {name}:
    forge: github
    url: file://{origin}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

COMPOSE_FIELDS = """runner: compose
workdir: "{app}"
long_lived_dir: "{app}/tests"
long_lived_name: "test_<id>_<name>.py"
report: junit-xml
compose_file: "deploy/compose.yaml"
compose_service: "{service}"
compose_env_file: "deploy/.env.run"
compose_env_template: "deploy/env.template"
compose_mount: "{left}:{right}"
weakening_scope: [{app}/tests/**/*.py]
mutation_claim_scope: [{app}/tests/test_*.py]
"""

OWN_FIELDS = """runner: pytest-own
command: [{stub}]
long_lived_dir: {lld}
long_lived_name: test_<id>_<name>.py
weakening_scope: [{lld}/**/*.py]
mutation_claim_scope: [{lld}/test_*.py]
"""

PROBE_TEST = "def test_ok():\n    assert True\n"

JUNIT = ('<?xml version="1.0" encoding="utf-8"?><testsuites>'
         '<testsuite name="pytest" errors="0" failures="{failures}" '
         'skipped="0" tests="1" time="0.01"><testcase '
         'classname="tests.test_probe" name="test_ok" time="0.001">{body}'
         '</testcase></testsuite></testsuites>')

FAKE_DOCKER = r'''#!@PYTHON@
import json
import os
import sys
import time

STATE = @STATE@
SLEEP = @SLEEP@
VALUED = ("--project-name", "-p", "--project-directory", "-f", "--file",
          "--env-file", "--profile", "--ansi", "--progress", "--parallel")


def load():
    try:
        with open(os.path.join(STATE, "scenario.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def lines(name):
    try:
        with open(os.path.join(STATE, name), encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]
    except (OSError, ValueError):
        return []


def append(name, record):
    with open(os.path.join(STATE, name), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def parse(args):
    kind = args[0] if args else ""
    opts = {}
    if kind != "compose":
        return kind, (args[1] if len(args) > 1 else ""), opts, args[1:]
    i = 1
    while i < len(args) and args[i].startswith("-"):
        key, eq, value = args[i].partition("=")
        if eq and key in VALUED:
            opts.setdefault(key, []).append(value)
            i += 1
        elif args[i] in VALUED and i + 1 < len(args):
            opts.setdefault(args[i], []).append(args[i + 1])
            i += 2
        else:
            opts.setdefault(args[i], []).append("")
            i += 1
    sub = args[i] if i < len(args) else ""
    return kind, sub, opts, args[i + 1:]


def option(opts, *names):
    for name in names:
        if opts.get(name):
            return opts[name][-1]
    return ""


def file_labels(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    for service in (data.get("services") or {}).values():
        labels = (service or {}).get("labels") or {}
        if isinstance(labels, list):
            labels = dict(item.split("=", 1) for item in labels if "=" in item)
        if labels:
            return {str(k): str(v) for k, v in labels.items()}
    return {}


def junit_target(rest):
    for i, arg in enumerate(rest):
        if arg == "--junitxml" and i + 1 < len(rest):
            return rest[i + 1]
        if arg.startswith("--junitxml="):
            return arg.split("=", 1)[1]
    return ""


def listing(kind, sc):
    downed = {d["project"] for d in lines("downed.jsonl")}
    seen = {}
    child = ""
    for call in lines("calls.jsonl"):
        if call.get("labels") and call.get("project"):
            seen.setdefault(call["project"], call["labels"])
        if call.get("sub") == "run":
            child = str(call.get("ppid"))
    for extra in sc.get("extra_projects", []):
        labels = {k: (child if v == "@CHILD@" else v)
                  for k, v in extra["labels"].items()}
        seen.setdefault(extra["project"], labels)
    key = "Names" if kind == "ps" else "Name"
    for name, labels in seen.items():
        if name in downed:
            continue
        text = ",".join([f"com.docker.compose.project={name}"]
                        + [f"{k}={v}" for k, v in labels.items()])
        print(json.dumps({key: f"{name}-x-1", "Labels": text}))


def main():
    args = sys.argv[1:]
    sc = load()
    kind, sub, opts, rest = parse(args)
    ppid = os.getppid()
    try:
        psid = os.getsid(ppid)
    except OSError:
        psid = None
    files = opts.get("-f", []) + opts.get("--file", [])
    labels = (file_labels(files[-1]) if kind == "compose" and files
              and sub in ("run", "up", "kill", "down") else {})
    project = option(opts, "--project-name", "-p")
    append("calls.jsonl", {"argv": args, "kind": kind, "sub": sub,
                           "project": project, "rest": rest,
                           "pid": os.getpid(), "ppid": ppid, "psid": psid,
                           "labels": labels, "at": time.time()})
    if kind == "compose" and sub == "config":
        tree = os.path.dirname(option(opts, "--project-directory").rstrip("/"))
        sys.stdout.write(json.dumps(sc.get("config", {}))
                         .replace("@PROJECT@", project).replace("@TREE@", tree))
    elif kind == "compose" and sub == "run":
        hold = sc.get("hold")
        if hold and os.path.exists(hold):
            append("blocked.jsonl", {"pid": os.getpid(), "project": project})
            deadline = time.time() + 100
            while os.path.exists(hold) and time.time() < deadline:
                time.sleep(0.1)
        if sc.get("run_sleep"):
            time.sleep(sc["run_sleep"])
        tree = os.path.dirname(option(opts, "--project-directory").rstrip("/"))
        target = junit_target(rest)
        right = sc.get("right", "/nonexistent").rstrip("/") + "/"
        if target.startswith(right):
            host = os.path.join(tree, sc["left"], target[len(right):])
            os.makedirs(os.path.dirname(host), exist_ok=True)
            with open(host, "w", encoding="utf-8") as fh:
                fh.write(sc["junit_red"] if sc.get("red") else sc["junit_green"])
    elif kind == "compose" and sub == "down":
        if sc.get("down_hang") and "-v" in rest:
            os.execv(SLEEP, [SLEEP, str(sc["down_hang"])])
        append("downed.jsonl", {"project": project})
    elif kind == "ps" or (kind == "network" and sub == "ls"):
        listing(kind, sc)
    elif kind == "context":
        host = sc.get("context_host", "unix:///nonexistent/docker.sock")
        if any("{{" in a for a in args):
            print(host)
        else:
            print(json.dumps([{"Name": "default", "Current": True,
                               "Endpoints": {"docker": {"Host": host}}}]))
    elif kind == "version":
        print("Docker version 27.0.0, build fake")
    sys.stdout.flush()
    sys.exit(0)


main()
'''

OWN_STUB = r'''#!@PYTHON@
import json
import os
import sys

with open(@CALLS@, "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(),
                         "pid": os.getpid(), "ppid": os.getppid(),
                         "role": os.environ.get("ARTEL_ROLE")}) + "\n")
print("tests/test_probe.py::test_ok PASSED")
print("============================== 1 passed in 0.01s ==============================")
sys.exit(0)
'''

AGENT = r'''import json
import os
import subprocess
import sys
import time

with open(sys.argv[1], encoding="utf-8") as fh:
    spec = json.load(fh)


def note(record):
    with open(spec["log"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def count(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return sum(1 for line in fh if line.strip())
    except OSError:
        return 0


def results():
    try:
        return {n for n in os.listdir(spec["queue"]) if n.endswith(".result.json")}
    except OSError:
        return set()


def until(check, limit):
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.1)
    return check()


known = results()
note({"tag": "agent", "pid": os.getpid()})
for act in spec["actions"]:
    do = act["do"]
    tag = act.get("tag", "")
    if do == "cmd":
        try:
            proc = subprocess.run([sys.executable, spec["pult"], *act["args"]],
                                  capture_output=True, text=True,
                                  stdin=subprocess.DEVNULL,
                                  timeout=act.get("limit", 80))
            note({"tag": tag, "args": act["args"], "code": proc.returncode,
                  "out": proc.stdout + proc.stderr})
        except subprocess.TimeoutExpired as exc:
            note({"tag": tag, "args": act["args"], "code": None,
                  "out": f"timeout: {exc}"})
    elif do == "write":
        os.makedirs(spec["queue"], exist_ok=True)
        tmp = os.path.join(spec["queue"], "." + act["name"] + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(act["data"], fh, ensure_ascii=False)
        os.replace(tmp, os.path.join(spec["queue"], act["name"]))
        note({"tag": tag, "wrote": act["name"]})
    elif do == "await_result":
        path = os.path.join(spec["queue"], act["name"])
        ok = until(lambda: os.path.exists(path), act.get("limit", 60))
        note({"tag": tag, "ok": ok})
    elif do == "await_results":
        ok = until(lambda: len(results() - known) >= act["count"],
                   act.get("limit", 60))
        note({"tag": tag, "ok": ok, "new": sorted(results() - known)})
    elif do == "await_blocked":
        ok = until(lambda: count(spec["blocked"]) >= act["count"],
                   act.get("limit", 60))
        note({"tag": tag, "ok": ok})
    elif do == "calls":
        note({"tag": tag, "calls": count(spec["calls"]),
              "own": count(spec["own_calls"])})
    elif do == "read":
        try:
            with open(act["path"], encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            text = None
        note({"tag": tag, "text": text})
note({"tag": "done"})
'''

DRIVER = r'''import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

ROOT, SPEC = sys.argv[1], sys.argv[2]
sys.path.insert(0, ROOT)
with open(SPEC, encoding="utf-8") as fh:
    spec = json.load(fh)

from orchestrator import config, keychain, runner, stack, store

keychain.token = lambda *args, **kwargs: "tok-test"
stack.check_stack = lambda: []


def role_env(role=None, task_id=None, **kwargs):
    env = dict(os.environ)
    env["PATH"] = spec["role_path"]
    env[config.ARTEL_ROLE_ENV] = role
    env[config.ARTEL_TASK_ENV] = task_id
    Path(config.ROLE_HOME).mkdir(parents=True, exist_ok=True)
    env["HOME"] = str(config.ROLE_HOME)
    return env


def role_cwd(conn, task_id, target, **kwargs):
    return Path(spec["cwd"])


def spawn_agent(cmd, **kwargs):
    return subprocess.Popen(
        [sys.executable, spec["agent"], spec["agent_spec"]],
        cwd=kwargs["cwd"], env=kwargs["env"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        bufsize=1, start_new_session=True)


runner.role_env = role_env
runner.role_cwd = role_cwd
runner.spawn_agent = spawn_agent
conn = store.db()
try:
    outcome = runner.run_agent_once(conn, spec["task"], spec["role"],
                                    "промпт шага", spec["attempt"])
    print("DRIVER-RESULT " + json.dumps(list(outcome), ensure_ascii=False),
          flush=True)
except BaseException:
    traceback.print_exc()
    print("DRIVER-EXCEPTION", flush=True)
'''


def word(rng, k: int = 6) -> str:
    return "".join(rng.choices(LETTERS, k=k))


def new_task_id(rng) -> str:
    return "01" + "".join(rng.choices(CROCKFORD, k=24))


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def flat_text(data) -> str:
    """Все строки и числа объекта JSON одной строкой — итог запроса по
    существу, без опоры на имена его полей."""
    if isinstance(data, dict):
        return " ".join(flat_text(v) for v in data.values())
    if isinstance(data, list):
        return " ".join(flat_text(v) for v in data)
    if data is None:
        return ""
    return str(data)


def indent(text: str, pad: str) -> str:
    return "".join(f"{pad}{line}\n" for line in text.splitlines())


class Step:
    """Итог шага роли в драйвере копии пульта."""

    def __init__(self, code, out, records, driver_pid):
        self.code, self.out, self.records = code, out, records
        self.driver_pid = driver_pid
        agents = [r for r in records if r.get("tag") == "agent"]
        self.agent_pid = agents[0]["pid"] if agents else None

    def tagged(self, tag: str) -> dict:
        found = [r for r in self.records if r.get("tag") == tag]
        return found[-1] if found else {}

    def output(self, tag: str) -> str:
        return self.tagged(tag).get("out", "")

    @property
    def finished(self) -> bool:
        return "DRIVER-RESULT" in self.out and self.code == 0


class Pult:
    """Копия пульта в корне `real_git`, подменённый `docker`, проекты и задачи."""

    def __init__(self, rg, seed: int):
        self.rg, self.seed = rg, seed
        self.rng = random.Random(seed)
        self.root = Path(rg.root).resolve()
        self.probe = Path(tempfile.mkdtemp(prefix="artel-rr-")).resolve()
        self.state = self.probe / "docker"
        self.bin = self.probe / "bin"
        self.tools = self.probe / "tools"
        self.home = self.probe / "home"
        self.hold_file = self.probe / "hold"
        self.own_calls = self.probe / "own_calls.jsonl"
        self.procs = []
        self.entries = {}
        self.sc = {}
        self.compose = None

    # --- сборка
    def build(self) -> None:
        for name in ("orchestrator", "scripts"):
            shutil.copytree(CODE_ROOT / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        fixture = self.rg.use_role_map()
        (self.root / "roles.yaml").write_text(fixture.roles_text,
                                              encoding="utf-8")
        (self.root / "models.yaml").write_text(CATALOG_FIXTURE_TEXT,
                                               encoding="utf-8")
        self.set_config(AGENT_TIMEOUT_SEC=100)
        for folder in (self.state, self.bin, self.tools, self.home):
            folder.mkdir(parents=True)
        docker = self.bin / "docker"
        docker.write_text(FAKE_DOCKER.replace("@PYTHON@", sys.executable)
                          .replace("@STATE@", repr(str(self.state)))
                          .replace("@SLEEP@", repr(SLEEP)), encoding="utf-8")
        docker.chmod(0o755)
        own = self.probe / "own"
        own.mkdir()
        self.stub = own / "pytest"
        self.stub.write_text(OWN_STUB.replace("@PYTHON@", sys.executable)
                             .replace("@CALLS@", repr(str(self.own_calls))),
                             encoding="utf-8")
        self.stub.chmod(0o755)
        for name in stack.DECLARED_TOOLS:
            # Настоящий поиск: `tests.sandbox` подменяет `shutil.which`
            # ответом-заглушкой для `gh`/`claude`, и без этого заглушка
            # не создаётся на машине без них (CI) — процесс-водитель
            # резолвит инструменты по-настоящему.
            if _REAL_WHICH(name) is None:
                tool = self.tools / name
                tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                tool.chmod(0o755)
        (self.probe / "agent.py").write_text(AGENT, encoding="utf-8")
        (self.probe / "driver.py").write_text(DRIVER, encoding="utf-8")
        self.entries = {config.DEFAULT_TARGET: artel_target_entry()}
        self.write_targets()
        self.sc = {"config": {}, "left": "", "right": "/nonexistent",
                   "junit_green": JUNIT.format(failures=0, body=""),
                   "junit_red": JUNIT.format(
                       failures=1, body='<failure message="boom">boom</failure>'),
                   "red": False, "hold": str(self.hold_file), "run_sleep": 0,
                   "down_hang": 0, "extra_projects": []}
        self.save_scenario()

    def set_config(self, **values) -> None:
        """Дописывает значения в `config.py` копии: их видят процессы,
        запущенные после вызова."""
        with open(self.root / "orchestrator" / "config.py", "a",
                  encoding="utf-8") as fh:
            fh.write("\n\n# Песочница теста запросов роли.\n")
            for name, value in values.items():
                fh.write(f"{name} = {value!r}\n")

    def save_scenario(self, **changes) -> None:
        self.sc.update(changes)
        (self.state / "scenario.json").write_text(json.dumps(self.sc),
                                                  encoding="utf-8")

    def write_targets(self) -> None:
        text = "targets:\n" + "".join(self.entries.values())
        for path in {Path(config.TARGETS), self.root / "targets.yaml"}:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def where(self, *parts) -> str:
        return "; ".join([*map(str, parts), f"зерно: {self.seed}"])

    # --- проекты
    def _commit(self, clone: Path, files: dict) -> None:
        for rel, text in files.items():
            path = clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.rg.git("-C", str(clone), "add", "-A")
        self.rg.git("-C", str(clone), "commit", "-q", "-m", "проект")
        self.rg.git("-C", str(clone), "push", "-q", "origin",
                    config.MAIN_BRANCH)

    def _compose_parts(self) -> dict:
        left = "src" + word(self.rng, 4)
        parts = {"left": left, "app": f"{left}/app{word(self.rng, 4)}",
                 "service": "svc" + word(self.rng, 4),
                 "right": f"/w{word(self.rng, 4)}/{word(self.rng, 4)}"}
        self.compose = parts
        cfg = {"name": "@PROJECT@",
               "services": {parts["service"]: {
                   "build": {"context": "@TREE@/deploy",
                             "dockerfile": "Dockerfile"},
                   "networks": {"default": None},
                   "volumes": [{"type": "bind",
                                "source": f"@TREE@/{left}",
                                "target": parts["right"]}],
                   "working_dir": parts["right"]}},
               "networks": {"default": {"name": "@PROJECT@_default"}}}
        self.save_scenario(config=cfg, left=left, right=parts["right"])
        return parts

    def _compose_files(self, parts: dict) -> dict:
        return {f"{parts['app']}/tests/test_probe.py": PROBE_TEST,
                "deploy/compose.yaml":
                    f"services:\n  {parts['service']}:\n    build: .\n",
                "deploy/env.template": "PROBE=1\n",
                ".gitignore": "deploy/.env.run\n"}

    def _declare(self, name: str, body: str) -> Path:
        origin = config.PROJECTS / name / "origin.git"
        self.entries[name] = PROJECT_HEAD.format(
            name=name, origin=origin, base=config.MAIN_BRANCH) + body
        self.write_targets()
        return make_project_repo(name)

    def compose_project(self) -> str:
        name = "c" + word(self.rng, 8)
        parts = self._compose_parts()
        clone = self._declare(name, "    test_profile:\n" + indent(
            COMPOSE_FIELDS.format(**parts), " " * 6))
        self._commit(clone, self._compose_files(parts))
        return name

    def own_project(self) -> str:
        name = "o" + word(self.rng, 8)
        clone = self._declare(name, "    test_profile:\n" + indent(
            OWN_FIELDS.format(stub=self.stub, lld="tests"), " " * 6))
        self._commit(clone, {"tests/test_probe.py": PROBE_TEST})
        return name

    def multi_project(self) -> tuple:
        """(имя, зона компонента `pytest-own`, зона компонента `compose`)."""
        name = "m" + word(self.rng, 8)
        parts = self._compose_parts()
        own = indent(OWN_FIELDS.format(stub=self.stub, lld="own/tests")
                     + "paths: [^own/]\n", " " * 8)
        box = indent(COMPOSE_FIELDS.format(**parts)
                     + f"paths: [^{parts['left']}/]\n", " " * 8)
        clone = self._declare(name, "    components:\n      own:\n" + own
                              + "      box:\n" + box)
        files = self._compose_files(parts)
        files["own/tests/test_probe.py"] = PROBE_TEST
        self._commit(clone, files)
        return name, "own/probe.py", f"{parts['app']}/probe.py"

    # --- задачи
    def task(self, target: str, state: str = "tests_writing",
             zones: str | None = None) -> tuple:
        """(id задачи, рабочая копия, имя файла черновика планки)."""
        task_id = new_task_id(self.rng)
        branch = f"task/{task_id.lower()}-req"
        conn = store.db()
        store.insert_task(conn, task_id, "Задача запросов роли", state,
                          branch, target, 25.0)
        if zones is not None:
            store.update_task(conn, task_id, zones=zones)
        wt, error = workspace.ensure(task_id, branch)
        if error:
            raise RuntimeError(f"рабочая копия не заведена: {error}")
        plank = f"test_{word(self.rng)}.py"
        draft = config.PROJECTS / target / "tasks" / task_id / "acceptance_tests"
        draft.mkdir(parents=True, exist_ok=True)
        (draft / plank).write_text(PROBE_TEST, encoding="utf-8")
        return task_id, Path(wt).resolve(), plank

    def lease(self, task_id: str, session: str | None = None) -> str:
        session = session or f"s{word(self.rng, 10)}"
        conn = store.db()
        conn.execute("DELETE FROM leases WHERE task_id = ?", (task_id,))
        conn.commit()
        store.insert_lease(conn, task_id, session, os.getpid(),
                           socket.gethostname(), store.now())
        return session

    # --- каталог suite-run
    def task_dir(self, task_id: str) -> Path:
        return suite_lock.directory() / task_id

    def queue(self, task_id: str) -> Path:
        return self.task_dir(task_id) / "requests"

    def requests(self, task_id: str) -> list:
        folder = self.queue(task_id)
        if not folder.is_dir():
            return []
        return sorted((p for p in folder.iterdir()
                       if re.fullmatch(r"\d+\.json", p.name)),
                      key=lambda p: int(p.stem))

    def results(self, task_id: str) -> dict:
        folder = self.queue(task_id)
        out = {}
        if not folder.is_dir():
            return out
        for path in sorted(folder.glob("*.result.json")):
            raw = path.read_text(encoding="utf-8")
            try:
                out[path.name] = flat_text(json.loads(raw))
            except ValueError:
                out[path.name] = raw
        return out

    def result(self, task_id: str, number: int) -> str:
        return self.results(task_id).get(f"{number}.result.json", "")

    def request(self, task_id: str, kind: str = "plank", file=None,
                **extra) -> dict:
        data = {"kind": kind, "file": file, "task_id": task_id,
                "time": store.now()}
        data.update(extra)
        return data

    def plant(self, task_id: str, number: int, data: dict) -> None:
        folder = self.queue(task_id)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{number}.json").write_text(json.dumps(data),
                                               encoding="utf-8")

    def plant_failed(self, task_id: str) -> None:
        folder = self.task_dir(task_id)
        folder.mkdir(parents=True, exist_ok=True)
        node = f"{self.compose['app']}/tests/test_probe.py::test_ok"
        (folder / "failed.json").write_text(
            json.dumps({"run": 1, "failed": [node]}), encoding="utf-8")

    def plant_run(self, task_id: str, pid: int) -> None:
        folder = self.task_dir(task_id)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "run.json").write_text(json.dumps(
            {"run": 1 + self.rng.randrange(50), "pid": pid,
             "log": str(folder / "x.log"), "mode": "full",
             "started": time.time()}), encoding="utf-8")

    # --- наблюдение
    @staticmethod
    def read_jsonl(path: Path) -> list:
        if not path.exists():
            return []
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
        return out

    def calls(self) -> list:
        return self.read_jsonl(self.state / "calls.jsonl")

    def own(self) -> list:
        return self.read_jsonl(self.own_calls)

    def journal(self, task_id: str) -> list:
        return [dict(row) for row in store.task_steps(store.db(), task_id)]

    def request_records(self, task_id: str) -> list:
        return [r for r in self.journal(task_id)
                if REQUEST_ACTION in f"{r['action']} {r['detail']}"]

    # --- процессы
    def env(self, role: str | None = None, home: str | None = None) -> dict:
        env = {k: v for k, v in os.environ.items()
               if k not in (config.ARTEL_ROLE_ENV, config.ARTEL_TASK_ENV,
                            "DOCKER_HOST", "DOCKER_CONFIG")}
        env["PATH"] = os.pathsep.join(
            [str(self.bin), *[d for d in os.environ.get("PATH", "").split(
                os.pathsep) if d], str(self.tools)])
        env["HOME"] = home or str(self.home)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if role is not None:
            env[config.ARTEL_ROLE_ENV] = role
        return env

    def _run(self, argv: list, env: dict, timeout: float) -> tuple:
        proc = subprocess.Popen(argv, cwd=str(self.root), env=env,
                                stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                start_new_session=True)
        self.procs.append(proc)
        try:
            raw, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.kill_group(proc.pid)
            raw, _ = proc.communicate()
            raw += f"\n[тест: процесс снят по пределу {timeout} с]".encode()
        return proc.returncode, raw.decode("utf-8", errors="replace"), proc.pid

    def cli(self, *args: str, role: str | None = None,
            timeout: float = 80) -> tuple:
        """(код выхода, вывод) `artel.py <args>` копии пульта."""
        code, out, _pid = self._run(
            [sys.executable, str(self.root / "orchestrator" / "artel.py"),
             *args], self.env(role), timeout)
        return code, out

    def step(self, task_id: str, role: str, actions: list, *,
             attempt: int = 1, timeout: float = 100) -> Step:
        """Шаг роли `role` задачи: `runner.run_agent_once` в драйвере копии
        пульта, «агент» исполняет `actions`."""
        n = len(self.procs)
        log = self.probe / f"agent-{n}.jsonl"
        agent_spec = self.probe / f"agent-{n}.json"
        agent_spec.write_text(json.dumps({
            "actions": actions, "log": str(log),
            "pult": str(self.root / "orchestrator" / "artel.py"),
            "queue": str(self.queue(task_id)),
            "blocked": str(self.state / "blocked.jsonl"),
            "calls": str(self.state / "calls.jsonl"),
            "own_calls": str(self.own_calls)}), encoding="utf-8")
        target = store.task_target(store.db(), task_id)
        driver_spec = self.probe / f"driver-{n}.json"
        driver_spec.write_text(json.dumps({
            "task": task_id, "role": role, "attempt": attempt,
            "cwd": str(workspace.path(task_id, target)),
            "agent": str(self.probe / "agent.py"),
            "agent_spec": str(agent_spec),
            "role_path": self.env()["PATH"]}), encoding="utf-8")
        code, out, pid = self._run(
            [sys.executable, str(self.probe / "driver.py"), str(self.root),
             str(driver_spec)], self.env(), timeout)
        return Step(code, out, self.read_jsonl(log), pid)

    def sleeper(self) -> int:
        """Живой процесс-заглушка в своей группе процессов — его pid."""
        proc = subprocess.Popen([SLEEP, "300"], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                start_new_session=True)
        self.procs.append(proc)
        return proc.pid

    @staticmethod
    def kill_group(pgid: int) -> None:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def stop(self) -> None:
        self.hold_file.unlink(missing_ok=True)
        mine = {os.getpid(), os.getppid(), os.getpgrp()}
        for proc in self.procs:
            self.kill_group(proc.pid)
        for log in self.probe.glob("agent-*.jsonl"):
            for record in self.read_jsonl(log):
                if record.get("tag") == "agent":
                    self.kill_group(record["pid"])
        pids = set()
        for call in self.calls() + self.own():
            pids.update((call.get("pid"), call.get("ppid")))
        for pid in pids:
            if isinstance(pid, int) and pid > 1 and pid not in mine:
                try:
                    os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
        for proc in self.procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        shutil.rmtree(self.probe, ignore_errors=True)


@pytest.fixture
def pult(real_git):
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    sandbox = Pult(real_git, seed)
    try:
        sandbox.build()
        yield sandbox
    finally:
        sandbox.stop()


# ------------------------------------------------------------ помощники тела

def executor_calls(p: Pult, step: Step, sub: str | None = None) -> list:
    """Вызовы `docker` из сессии драйвера шага (исполнитель и его дочерние
    прогоны), по подкоманде `sub` или все."""
    return [c for c in p.calls() if c.get("psid") == step.driver_pid
            and (sub is None or c.get("sub") == sub)]


def role_calls(p: Pult, step: Step) -> list:
    """Вызовы `docker` из сессии процесса «агента» (процесс роли)."""
    return [c for c in p.calls() if step.agent_pid is not None
            and c.get("psid") == step.agent_pid]


PLANK_REPORT = r"\[{task}\] plank-run: итог pytest: .*; код выхода pytest: \d+"
SUITE_REPORT = r"\[{task}\] suite-run №\d+ \((полный набор|повтор упавших)\): "


# --------------------------------------------------------------- AC-1

def test_ac1_role_plank_run_writes_request_without_docker(pult):
    """`plank-run <id>` в процессе роли проекта `compose` с живым lease — запрос в очереди задачи, `docker` не вызван.

    Сценарий: задача проекта с раннером `compose` в `tests_writing`, черновик
    планки в каталоге документов, живой lease шага; команда `artel.py
    plank-run <id>` копии пульта с `ARTEL_ROLE` (роль — случайная из ролей
    шагов). В каталоге `suite-run/<id>/requests/` ровно один файл
    `<номер>.json` — объект JSON ровно с ключами `kind`, `file`, `task_id`,
    `time` (`kind` — `plank`, `file` — `null`, `task_id` — id задачи, `time` —
    непустая строка); журнал вызовов подменённого `docker` пуст; вывод
    называет `--wait`.

    Ловит мутацию: команда в процессе роли ведёт прогон сама (журнал
    `docker` не пуст) или отказывает прежним «раннер compose в шаге роли не
    исполняется» (файла запроса нет); запрос несёт лишнее поле (роль,
    сессию, имя проекта Compose) или другое имя ключа; вывод не подсказывает
    `--wait`.
    """
    p = pult
    task, _wt, _plank = p.task(p.compose_project())
    p.lease(task)
    role = p.rng.choice(sorted(set(config.STATE_ROLE.values())))
    code, out = p.cli("plank-run", task, role=role)
    where = p.where(f"роль {role}", f"код {code}", out[-1500:])
    assert p.calls() == [], f"{where}: docker вызван: {p.calls()}"
    files = p.requests(task)
    assert len(files) == 1, f"{where}: файлы очереди {files}"
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert set(data) == REQUEST_KEYS, f"{where}: ключи запроса {sorted(data)}"
    assert data["kind"] == "plank" and data["file"] is None, f"{where}: {data}"
    assert data["task_id"] == task, f"{where}: {data}"
    assert isinstance(data["time"], str) and data["time"], f"{where}: {data}"
    assert "--wait" in out, where


# --------------------------------------------------------------- AC-2

def test_ac2_executor_runs_request_and_wait_reports_acceptance(pult):
    """Исполнитель шага берёт запрос `plank-run`, вызывает `docker`; `plank-run --wait` отдаёт прежний отчёт со строкой «принят шагом <session>/<попытка>».

    Сценарий: живой lease с сессией `S`, шаг роли test_author с попыткой `N`
    (случайной из `1..config.AGENT_ATTEMPTS`); «агент» в окружении роли
    зовёт `plank-run <id>`, затем `plank-run <id> --wait 1`. Подменённый
    `docker` вызван из сессии процесса пульта (исполнителя), не из сессии
    процесса роли; вывод `--wait` — строки отчёта `plank-run` («[<id>]
    plank-run: итог pytest: …; код выхода pytest: …») и «принят шагом S/N».

    Ловит мутацию: исполнитель не запущен или не берёт запрос (вызовов
    `docker` нет, `--wait` не дождался); итог пишется без строки «принят
    шагом» или с номером попытки/сессией не того шага; `--wait` печатает итог
    иным форматом, а не строками отчёта `plank-run`.
    """
    p = pult
    task, _wt, _plank = p.task(p.compose_project())
    session = p.lease(task)
    attempt = p.rng.randint(1, config.AGENT_ATTEMPTS)
    step = p.step(task, "test_author", [
        {"do": "cmd", "args": ["plank-run", task], "tag": "request"},
        {"do": "cmd", "args": ["plank-run", task, "--wait", "1"],
         "tag": "wait"}], attempt=attempt)
    out = step.output("wait")
    where = p.where(f"сессия {session}, попытка {attempt}", out[-1500:],
                    step.output("request")[-600:], step.out[-1500:])
    assert executor_calls(p, step, "run"), \
        f"{where}: исполнитель не вызвал docker run: {p.calls()}"
    assert role_calls(p, step) == [], f"{where}: docker из процесса роли"
    assert re.search(PLANK_REPORT.format(task=re.escape(task)), out), where
    assert f"принят шагом {session}/{attempt}" in out, where


# --------------------------------------------------------------- AC-3

@pytest.mark.parametrize("variant", ["failed", "full"])
@pytest.mark.timeout(240)
def test_ac3_role_suite_run_request_and_executor_report(pult, variant):
    """`suite-run <id> --failed` (и `suite-run <id>` роли с правом полного прогона) в процессе роли — запрос без `docker`; итог исполнителя — прежний отчёт `suite-run --wait`.

    Сценарий: проект `compose`, живой lease, перечень упавших прошлого
    прогона (для `--failed`). Сначала команда копии пульта в процессе роли
    (test_author или reviewer) — журнал `docker` пуст, в очереди задачи
    запрос вида `failed`/`full`, вывод называет `--wait`. Затем шаг роли:
    «агент» пишет такой же запрос командой и ждёт `suite-run <id> --wait 1`
    — вывод в прежнем формате отчёта (`[<id>] suite-run №N (полный набор|
    повтор упавших): …`, «прошло: …, упало: …, пропущено: …»), `docker`
    вызван из сессии исполнителя. Отвязанный фон, если его запустила
    команда, снимает уборка по pid/ppid журнала заглушек.

    Ловит мутацию: `suite-run` в процессе роли по-прежнему запускает
    отвязанный фон (запроса нет, `docker` зовёт фон), вид запроса `--failed`
    пишется как `full`; итог полного набора исполнитель пишет вне места,
    откуда его читает `--wait` (вывод «нет ни одного прогона»/не дождался).
    """
    p = pult
    task, _wt, _plank = p.task(p.compose_project())
    p.lease(task)
    p.plant_failed(task)
    role = p.rng.choice(FULL_ALLOWED_ROLES)
    flags = ["--failed"] if variant == "failed" else []
    code, out = p.cli("suite-run", task, *flags, role=role)
    where = p.where(variant, role, f"код {code}", out[-1500:])
    assert p.calls() == [], f"{where}: docker вызван: {p.calls()}"
    files = p.requests(task)
    assert len(files) == 1, f"{where}: файлы очереди {files}"
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data.get("kind") == variant, f"{where}: {data}"
    assert "--wait" in out, where
    step = p.step(task, role, [
        {"do": "cmd", "args": ["suite-run", task, *flags], "tag": "request"},
        {"do": "cmd", "args": ["suite-run", task, "--wait", "1"],
         "tag": "wait"}])
    report = step.output("wait")
    where = p.where(variant, role, report[-1500:], step.out[-1500:])
    assert executor_calls(p, step, "run"), f"{where}: {p.calls()}"
    assert re.search(SUITE_REPORT.format(task=re.escape(task)), report), where
    assert re.search(r"прошло: \d+, упало: \d+, пропущено: \d+", report), where


# --------------------------------------------------------------- AC-4

@pytest.mark.timeout(400)
def test_ac4_wait_reports_queue_position_and_running_without_old_result(pult):
    """`--wait 0` у невзятого запроса — «запрос в очереди (позиция N), прогон не начат»; у идущего — «прогон не прерван, повтори `--wait`»; итог прошлого прогона не выдаётся.

    Сценарий: шаг 1 (сессия `S0`) исполняет запрос планки и запрос полного
    набора — у задачи есть итоги прошлых прогонов обоих видов. Шаг 2 (сессия
    `S1`): «шлагбаум» держит `docker run`; запрос планки взят и идёт —
    `plank-run --wait 0` отвечает «прогон не прерван, повтори» с подсказкой
    `--wait`; запрос полного набора стоит за ним — `suite-run --wait 0`
    отвечает «запрос в очереди (позиция 1), прогон не начат» с `--wait`.
    Шаг 3 (сессия `S2`) — то же с обменом видов. Ни один из этих выводов не
    несёт итога шага 1 (строки «принят шагом S0/…», отчёта прошлого прогона).

    Ловит мутацию: `--wait` отдаёт последний записанный итог своего вида, не
    сверив номер запроса (итог шага 1 вместо ожидания); позиция в очереди не
    считается или прогон, взятый исполнителем, называется «в очереди»;
    `--wait` у идущего прогона молчит без подсказки повтора.
    """
    p = pult
    task, _wt, _plank = p.task(p.compose_project())
    role = p.rng.choice(FULL_ALLOWED_ROLES)
    s0 = p.lease(task)
    first = p.step(task, role, [
        {"do": "cmd", "args": ["plank-run", task], "tag": "p"},
        {"do": "cmd", "args": ["plank-run", task, "--wait", "1"], "tag": "pw"},
        {"do": "cmd", "args": ["suite-run", task], "tag": "s"},
        {"do": "cmd", "args": ["suite-run", task, "--wait", "1"],
         "tag": "sw"}])
    old_plank, old_suite = first.output("pw"), first.output("sw")
    where = p.where(old_plank[-800:], old_suite[-800:], first.out[-1000:])
    assert f"принят шагом {s0}/" in old_plank, where
    assert re.search(SUITE_REPORT.format(task=re.escape(task)), old_suite), \
        where
    old_head = re.search(SUITE_REPORT.format(task=re.escape(task)) + ".*",
                         old_suite).group(0)
    outputs = {}
    for kind_first in ("plank", "suite"):
        p.lease(task)
        p.hold_file.write_text("hold", encoding="utf-8")
        blocked = len(p.read_jsonl(p.state / "blocked.jsonl")) + 1
        first_cmd = "plank-run" if kind_first == "plank" else "suite-run"
        second_cmd = "suite-run" if kind_first == "plank" else "plank-run"
        step = p.step(task, role, [
            {"do": "cmd", "args": [first_cmd, task], "tag": "a"},
            {"do": "await_blocked", "count": blocked, "limit": 60,
             "tag": "blocked"},
            {"do": "cmd", "args": [first_cmd, task, "--wait", "0"],
             "tag": "running"},
            {"do": "cmd", "args": [second_cmd, task], "tag": "b"},
            {"do": "cmd", "args": [second_cmd, task, "--wait", "0"],
             "tag": "queued"}])
        p.hold_file.unlink(missing_ok=True)
        outputs[kind_first] = (step.output("running"), step.output("queued"),
                               step.out)
    for kind_first, (running, queued, driver) in outputs.items():
        where = p.where(kind_first, running[-800:], queued[-800:],
                        driver[-800:])
        assert STILL_RUNNING in running and "--wait" in running, where
        match = QUEUED.search(queued)
        assert match and int(match.group(1)) == 1, where
        assert "--wait" in queued, where
        for text in (running, queued):
            assert f"принят шагом {s0}/" not in text, where
            assert old_head not in text, where
            assert "код выхода pytest" not in text, where


# --------------------------------------------------------------- AC-5

@pytest.mark.parametrize("kind", ["compose", "own"])
def test_ac5_wait_limit_and_extra_argument_refused_by_text(pult, kind):
    """`plank-run <id> --wait <сверх предела>` — отказ, называющий `SUITE_RUN_MAX_WAIT_MIN` и диапазон; `plank-run <id> <файл> <лишний>` — отказ, называющий лишний аргумент.

    Сценарий: задача проекта `compose` или `pytest-own` (команда-заглушка),
    вне шага роли. Число минут — `config.SUITE_RUN_MAX_WAIT_MIN` плюс
    случайное 1..50: код выхода не 0, текст несёт имя
    `SUITE_RUN_MAX_WAIT_MIN` и диапазон «0 … <предел>». Третий аргумент —
    случайное слово: код выхода не 0, текст называет это слово.

    Ловит мутацию: `--wait` по-прежнему разбирается как имя файла планки
    (отказ «файла --wait нет в планке», без предела); предел не сверяется
    (ожидание сверх предела); диспетчер отрезает `rest[1]` и лишний аргумент
    молча отбрасывается — прогон идёт, слова в выводе нет.
    """
    p = pult
    target = p.compose_project() if kind == "compose" else p.own_project()
    task, _wt, plank = p.task(target)
    limit = config.SUITE_RUN_MAX_WAIT_MIN
    minutes = limit + p.rng.randint(1, 50)
    code, out = p.cli("plank-run", task, "--wait", str(minutes))
    where = p.where(kind, f"минут {minutes}", f"код {code}", out[-1200:])
    assert code != 0, where
    assert "SUITE_RUN_MAX_WAIT_MIN" in out, where
    assert re.search(rf"(?<!\d)0(?!\d).*(?<!\d){limit}(?!\d)", out), where
    extra = "x" + word(p.rng, 9)
    code, out = p.cli("plank-run", task, plank, extra)
    where = p.where(kind, f"лишний {extra}", f"код {code}", out[-1200:])
    assert code != 0, where
    assert extra in out, where


# --------------------------------------------------------------- AC-6

def test_ac6_role_check_lets_wait_forms_through(pult):
    """`plank-run <id> --wait <минуты>` и `suite-run <id> --wait <минуты>` в процессе роли проекта `compose` не отказываются проверкой команд роли.

    Сценарий: роль — случайная из ролей шагов, задача проекта `compose`;
    обе формы зовутся с `--wait 0`. Вывод не содержит отказа проверки
    команд роли «команда недоступна процессу роли».

    Ловит мутацию: `plank-run`/`suite-run` выпали из белого списка команд
    роли или флаг `--wait` попал в запрещённые флаги роли — обе формы
    отказывают текстом проверки команд роли.
    """
    p = pult
    task, _wt, _plank = p.task(p.compose_project())
    p.lease(task)
    role = p.rng.choice(sorted(set(config.STATE_ROLE.values())))
    for command in ("plank-run", "suite-run"):
        code, out = p.cli(command, task, "--wait", "0", role=role)
        assert ROLE_COMMAND_REFUSAL not in out, \
            p.where(command, role, f"код {code}", out[-800:])


# --------------------------------------------------------------- AC-7

def test_ac7_no_live_lease_refused_without_request(pult):
    """Процесс роли, проект `compose`, у задачи нет lease — `plank-run <id>` отказывает, запроса нет, `docker` не вызван.

    Сценарий: задача заведена в БД копии пульта, lease не заведён;
    `plank-run <id>` идёт подпроцессом через `artel.py` копии (её
    `config.ROOT` — корень песочницы). Код выхода не 0, очередь задачи пуста,
    журнал `docker` пуст.

    Ловит мутацию: команда пишет запрос без проверки живого lease шага
    задачи (файл запроса появляется).
    """
    p = pult
    task, _wt, _plank = p.task(p.compose_project())
    role = p.rng.choice(sorted(set(config.STATE_ROLE.values())))
    code, out = p.cli("plank-run", task, role=role)
    where = p.where(role, f"код {code}", out[-800:])
    assert code != 0, where
    assert p.requests(task) == [], where
    assert p.calls() == [], f"{where}: {p.calls()}"


# ------------------------------------------------ AC-8 … AC-10: отказы с парой

def refusal_pair_step(p: Pult, task: str, bad: dict, good: dict, *,
                      role: str = "test_author") -> tuple:
    """Шаг роли: «агент» подкладывает `bad`, ждёт итог, снимает счёт вызовов
    `docker`, затем подкладывает `good` и ждёт итог. (шаг, номер bad, номер
    good)."""
    first = 1 + p.rng.randrange(40)
    second = first + 1 + p.rng.randrange(40)
    step = p.step(task, role, [
        {"do": "write", "name": f"{first}.json", "data": bad},
        {"do": "await_result", "name": f"{first}.result.json", "limit": 40},
        {"do": "calls", "tag": "between"},
        {"do": "write", "name": f"{second}.json", "data": good},
        {"do": "await_result", "name": f"{second}.result.json",
         "limit": 60}])
    return step, first, second


def test_ac8_foreign_task_id_refused_then_own_executed(pult):
    """Запрос с чужим `task_id` — отказ итогом с этим id, `docker` не вызван; тот же файл с id задачи шага — исполнен.

    Ловит мутацию: исполнитель не сверяет `task_id` запроса с задачей своего
    шага (чужой запрос исполнен — `docker` вызван до второго запроса) или
    отказ не называет чужой id; исполнитель отказывает и своему запросу
    (вызовов `docker` нет вовсе).
    """
    p = pult
    task, _wt, _plank = p.task(p.compose_project())
    p.lease(task)
    other = new_task_id(p.rng)
    bad = p.request(task)
    bad["task_id"] = other
    step, first, second = refusal_pair_step(p, task, bad, p.request(task))
    where = p.where(other, p.results(task), step.out[-1200:])
    assert other in p.result(task, first), where
    assert step.tagged("between").get("calls") == 0, where
    assert executor_calls(p, step, "run"), where


def test_ac9_plank_file_outside_task_refused_then_plank_file_executed(pult):
    """Запрос планки с файлом вне долгоживущих файлов задачи и её планки — отказ итогом с этим файлом, `docker` не вызван; тот же файл с файлом планки — исполнен.

    Файл вне — существующий тест рабочей копии, не долгоживущий файл задачи
    (`<workdir>/tests/test_probe.py`). Исправленный — имя файла черновика
    планки задачи.

    Ловит мутацию: исполнитель передаёт `file` запроса прогону без сверки с
    файлами задачи (чужой тест рабочей копии прогнан — `docker` вызван до
    второго запроса); отказ не называет файл; файл планки задачи тоже
    отказан.
    """
    p = pult
    task, _wt, plank = p.task(p.compose_project())
    p.lease(task)
    outside = f"{p.compose['app']}/tests/test_probe.py"
    step, first, second = refusal_pair_step(
        p, task, p.request(task, file=outside), p.request(task, file=plank))
    where = p.where(outside, plank, p.results(task), step.out[-1200:])
    assert outside in p.result(task, first), where
    assert step.tagged("between").get("calls") == 0, where
    assert executor_calls(p, step, "run"), where


@pytest.mark.parametrize("defect", ["extra_key", "kind"])
def test_ac10_extra_key_or_unknown_kind_refused_then_fixed_executed(pult,
                                                                     defect):
    """Запрос с ключом сверх четырёх или с видом вне `plank`/`full`/`failed` — отказ итогом с ключом/видом, `docker` не вызван; исправленный файл — исполнен.

    Ловит мутацию: исполнитель читает только нужные ключи и молча
    пропускает лишний (запрос исполнен — `docker` вызван до второго
    запроса); неизвестный вид прогоняется как планка или полный набор; отказ
    не называет ключ/вид.
    """
    p = pult
    task, _wt, _plank = p.task(p.compose_project())
    p.lease(task)
    name = "x" + word(p.rng, 7)
    if defect == "extra_key":
        bad = p.request(task, **{name: word(p.rng)})
    else:
        bad = p.request(task, kind=name)
    step, first, second = refusal_pair_step(p, task, bad, p.request(task))
    where = p.where(defect, name, p.results(task), step.out[-1200:])
    assert name in p.result(task, first), where
    assert step.tagged("between").get("calls") == 0, where
    assert executor_calls(p, step, "run"), where


# --------------------------------------------------------------- AC-11

@pytest.mark.parametrize("stamp", ["now", "future"])
@pytest.mark.timeout(240)
def test_ac11_request_queued_before_step_refused_after_start_executed(pult,
                                                                       stamp):
    """Запрос, лежавший в очереди до начала шага (и со временем из будущего), — итог «запрос без шага роли этой задачи в полёте», `docker` не вызван; тот же файл после начала шага — исполнен.

    Сценарий: файл запроса кладётся в очередь до запуска шага; «агент»
    шага только ждёт его итога. Затем второй шаг: «агент» кладёт тот же
    объект запроса новым файлом после начала шага и ждёт итога.

    Ловит мутацию: привязка к шагу по полю `time` запроса (запрос со
    временем из будущего исполнен) или её нет вовсе (лежавший до шага
    исполнен — `docker` вызван в первом шаге); исполнитель отказывает и
    запросу, положенному в своём шаге.
    """
    p = pult
    task, _wt, _plank = p.task(p.compose_project())
    p.lease(task)
    data = p.request(task)
    if stamp == "future":
        data["time"] = f"{2100 + p.rng.randrange(800)}-01-01 00:00:00Z"
    first = 1 + p.rng.randrange(40)
    p.plant(task, first, data)
    before = p.step(task, "test_author", [
        {"do": "await_result", "name": f"{first}.result.json", "limit": 40}])
    where = p.where(stamp, p.results(task), before.out[-1200:])
    assert NOT_IN_FLIGHT in p.result(task, first), where
    assert p.calls() == [], f"{where}: {p.calls()}"
    second = first + 1 + p.rng.randrange(40)
    after = p.step(task, "test_author", [
        {"do": "write", "name": f"{second}.json", "data": data},
        {"do": "await_result", "name": f"{second}.result.json",
         "limit": 60}])
    where = p.where(stamp, p.results(task), after.out[-1200:])
    assert executor_calls(p, after, "run"), where


# --------------------------------------------------------------- AC-12

def test_ac12_requests_left_at_step_end_get_step_over_result(pult):
    """Шаг завершён, в очереди невзятые запросы — каждому итог «не исполнен: шаг роли завершён», `docker` по ним не вызван.

    Сценарий: «шлагбаум» держит `docker run` первого запроса; «агент»
    дожидается его и кладёт ещё 1–2 запроса, затем шаг завершается. Итог
    каждого оставшегося — «не исполнен: шаг роли завершён»; `docker run`
    вызван ровно один раз (по первому запросу).

    Ловит мутацию: в конце шага очередь не разбирается (у оставшихся нет
    итога) или оставшиеся исполняются после конца шага (лишние `docker run`).
    """
    p = pult
    task, _wt, _plank = p.task(p.compose_project())
    p.lease(task)
    p.hold_file.write_text("hold", encoding="utf-8")
    first = 1 + p.rng.randrange(20)
    left = [first + 1 + i for i in range(1 + p.rng.randrange(2))]
    actions = [{"do": "write", "name": f"{first}.json",
                "data": p.request(task)},
               {"do": "await_blocked", "count": 1, "limit": 60}]
    actions += [{"do": "write", "name": f"{n}.json", "data": p.request(task)}
                for n in left]
    step = p.step(task, "test_author", actions)
    p.hold_file.unlink(missing_ok=True)
    where = p.where(first, left, p.results(task), step.out[-1200:])
    for number in left:
        assert STEP_OVER in p.result(task, number), where
    runs = [c for c in p.calls() if c.get("sub") == "run"]
    assert len(runs) == 1, f"{where}: {runs}"


# --------------------------------------------------------------- AC-13

def test_ac13_busy_suite_lock_result_without_docker(pult):
    """Замок полных прогонов занят — запрос полного набора получает итог «прогон не начат: замок занят <держатель>», `docker` не вызван.

    Сценарий: процесс теста держит замок `suite_lock` (держатель — его pid);
    «агент» шага test_author подкладывает запрос `full` и ждёт итога.

    Ловит мутацию: исполнитель ждёт замок или берёт прогон в обход замка
    (`docker` вызван, итога «замок занят» нет); итог не называет держателя.
    """
    p = pult
    task, _wt, _plank = p.task(p.compose_project())
    p.lease(task)
    holder = suite_lock.acquire(new_task_id(p.rng))
    try:
        number = 1 + p.rng.randrange(40)
        step = p.step(task, "test_author", [
            {"do": "write", "name": f"{number}.json",
             "data": p.request(task, kind="full")},
            {"do": "await_result", "name": f"{number}.result.json",
             "limit": 40}])
    finally:
        suite_lock.release()
    text = p.result(task, number)
    where = p.where(f"держатель {holder}", text, step.out[-1200:])
    assert LOCK_BUSY in text, where
    assert str(os.getpid()) in text, where
    assert p.calls() == [], f"{where}: {p.calls()}"


# --------------------------------------------------------------- AC-14

@pytest.mark.parametrize("kind", ["plank", "full", "failed"])
@pytest.mark.timeout(240)
def test_ac14_step_end_interrupts_child_and_child_tears_down(pult, kind):
    """Шаг завершился до итога прогона — дочерний прогон получил сигнал и сам снял стенд `down -v` раньше `docker ps` исполнителя; итог «прерван: шаг роли завершён».

    Сценарий: «шлагбаум» держит `docker run`; «агент» роли test_author пишет
    запрос командой (`plank-run`, `suite-run`, `suite-run --failed`),
    дожидается `docker run` и завершается. В `run.json` каталога `suite-run`
    подложен pid живого процесса-заглушки; подменённый `docker ps` кроме
    своего проекта называет проект с префиксом задачи и этим pid. Проверка:
    `run` вызван процессом в сессии драйвера (дочерний прогон не в чужой
    сессии), метка `artel.run-pid` проекта — pid этого процесса; `down -v
    --remove-orphans` того же проекта вызван этим же процессом раньше
    `docker ps` исполнителя; проект с pid из `run.json` `down` не получил,
    заглушка жива; итог запроса — «прерван: шаг роли завершён»; для полного
    набора и повтора замок свободен; процесс пульта довёл шаг сам.

    Ловит мутацию: исполнитель снимает группу дочернего прогона сразу, без
    ожидания его выхода (`finally` дочернего прогона не исполнен — `down -v`
    от него нет); тело полного набора уходит в отвязанный фон в своей сессии
    (сессия вызова `run` не сессия драйвера); замок не снят после обрыва;
    pid для выбора проекта берётся из `run.json`.
    """
    p = pult
    task, _wt, _plank = p.task(p.compose_project())
    p.lease(task)
    if kind == "failed":
        p.plant_failed(task)
    stub = p.sleeper()
    p.plant_run(task, stub)
    decoy = f"artel-{task.lower()}-{os.urandom(4).hex()}"
    p.save_scenario(extra_projects=[{"project": decoy, "labels": {
        "artel.run-pid": str(stub), "artel.run-host": socket.gethostname(),
        "artel.run-started": store.now()}}])
    p.hold_file.write_text("hold", encoding="utf-8")
    args = {"plank": ["plank-run", task], "full": ["suite-run", task],
            "failed": ["suite-run", task, "--failed"]}[kind]
    step = p.step(task, "test_author", [
        {"do": "cmd", "args": args, "tag": "request"},
        {"do": "await_blocked", "count": 1, "limit": 60}])
    calls = p.calls()
    where = p.where(kind, step.output("request")[-600:], p.results(task),
                    step.out[-1500:], [(c["sub"], c["ppid"], c["psid"])
                                       for c in calls])
    runs = [c for c in calls if c.get("sub") == "run"]
    assert runs, where
    run = runs[0]
    child = run["ppid"]
    assert run["psid"] == step.driver_pid, where
    assert run["labels"].get("artel.run-pid") == str(child), where
    downs = [i for i, c in enumerate(calls) if c.get("sub") == "down"
             and c.get("project") == run["project"] and c.get("ppid") == child
             and "-v" in c["rest"] and "--remove-orphans" in c["rest"]]
    assert downs, f"{where}: down -v от дочернего прогона нет"
    pss = [i for i, c in enumerate(calls) if c["argv"] == PS_ARGV
           and c.get("ppid") == step.driver_pid]
    assert pss and downs[0] < pss[0], where
    assert not [c for c in calls if c.get("sub") == "down"
                and c.get("project") == decoy], where
    assert pid_alive(stub), where
    assert any(INTERRUPTED in text for text in p.results(task).values()), where
    if kind != "plank":
        taken = suite_lock.acquire(task)
        if taken is None:
            suite_lock.release()
        assert taken is None, f"{where}: замок держит {taken}"
    assert step.finished, where


# --------------------------------------------------------------- AC-15

def test_ac15_fourth_request_refused_naming_queue_limit(pult):
    """Три запроса командами в очереди — четвёртый подряд отказан при записи с пределом 3, не записан.

    Сценарий: живой lease, перечень упавших прошлого прогона; в процессе
    роли test_author три команды — случайная смесь `plank-run <id>` и
    `suite-run <id> --failed`; в очереди три файла. Четвёртая команда
    (`plank-run <id>`): код выхода не 0, текст называет 3, файлов по-прежнему
    три. Отвязанный фон, если его запустила команда, снимает уборка по
    журналу вызовов заглушек.

    Ловит мутацию: предел очереди не проверяется (четвёртый файл записан)
    или считается иначе (отказ уже на третьем); отказ без числа предела.
    """
    p = pult
    task, _wt, _plank = p.task(p.compose_project())
    p.lease(task)
    p.plant_failed(task)
    commands = [p.rng.choice([["plank-run", task],
                              ["suite-run", task, "--failed"]])
                for _ in range(3)]
    outs = [p.cli(*command, role="test_author") for command in commands]
    where = p.where(commands, [o[1][-300:] for o in outs])
    assert len(p.requests(task)) == 3, f"{where}: {p.requests(task)}"
    code, out = p.cli("plank-run", task, role="test_author")
    where = p.where(commands, f"код {code}", out[-800:])
    assert code != 0, where
    assert re.search(r"(?<!\d)3(?!\d)", out), where
    assert len(p.requests(task)) == 3, f"{where}: {p.requests(task)}"


# --------------------------------------------------------------- AC-16

def test_ac16_second_request_starts_after_first_result(pult):
    """Два запроса задачи — второй начинает исполняться только после итога первого.

    Сценарий: подменённый `docker run` длится заметно (сон заглушки);
    «агент» пишет два запроса `plank-run` подряд и ждёт двух итогов.
    Вызовы `docker` двух прогонов (разные имена проектов Compose) не
    перемежаются: все вызовы второго проекта — после последнего вызова
    первого (его `down`).

    Ловит мутацию: исполнитель запускает дочерний прогон на каждый запрос
    сразу (вызовы `config`/`run` второго проекта идут во время `run`
    первого).
    """
    p = pult
    task, _wt, _plank = p.task(p.compose_project())
    p.lease(task)
    p.save_scenario(run_sleep=1.5)
    step = p.step(task, "test_author", [
        {"do": "cmd", "args": ["plank-run", task], "tag": "one"},
        {"do": "cmd", "args": ["plank-run", task], "tag": "two"},
        {"do": "await_results", "count": 2, "limit": 80}])
    calls = [c for c in executor_calls(p, step) if c.get("kind") == "compose"]
    order = []
    for c in calls:
        if c["project"] not in order:
            order.append(c["project"])
    where = p.where(order, [(c["sub"], c["project"]) for c in calls],
                    step.out[-1200:])
    assert len(order) >= 2, where
    last_first = max(i for i, c in enumerate(calls)
                     if c["project"] == order[0])
    first_second = min(i for i, c in enumerate(calls)
                       if c["project"] == order[1])
    assert last_first < first_second, where


# --------------------------------------------------------------- AC-17

def test_ac17_executor_journals_and_deferred_record_not_delivered(pult):
    """Исполненный и отказанный запросы — записи журнала «прогон по запросу роли» автора пульта; отложенная запись с этим действием досылкой не переносится.

    Сценарий: «агент» подкладывает запрос с чужим id (отказ) и пишет запрос
    командой (исполнение). В журнале задачи — записи с «прогон по запросу
    роли» на оба запроса, автор — не роль шага. Затем в очередь отложенных
    записей кладётся запись с тем же действием (через
    `suite_lock.defer_journal`, допуск действия подменён только на время
    записи) — `suite_lock.deliver_journal` её в журнал не переносит.

    Ловит мутацию: исполнитель не пишет журнал (или пишет только об
    исполненных); пишет его от имени роли шага или через очередь отложенных
    записей с расширенным перечнем `deferrable` (досылка переносит
    подложенную ролью запись).
    """
    p = pult
    task, _wt, _plank = p.task(p.compose_project())
    p.lease(task)
    bad = p.request(task)
    bad["task_id"] = new_task_id(p.rng)
    number = 1 + p.rng.randrange(40)
    role = "test_author"
    step = p.step(task, role, [
        {"do": "write", "name": f"{number}.json", "data": bad},
        {"do": "await_result", "name": f"{number}.result.json", "limit": 40},
        {"do": "cmd", "args": ["plank-run", task], "tag": "request"},
        {"do": "await_results", "count": 2, "limit": 60}])
    records = p.request_records(task)
    where = p.where(records, step.out[-1200:])
    assert len(records) >= 2, where
    assert all(r["actor"] != role for r in records), where
    action = records[0]["action"]
    marker = "m" + word(p.rng, 12)
    with mock.patch.object(suite_lock, "deferrable", lambda _action: True):
        suite_lock.defer_journal({"task_id": task, "action": action,
                                  "detail": marker, "session_id": None,
                                  "at": store.now()})
    suite_lock.deliver_journal()
    delivered = [r for r in p.journal(task) if marker in r["detail"]]
    assert delivered == [], p.where(action, delivered)


# --------------------------------------------------------------- AC-18

def test_ac18_gate_plank_run_red_despite_green_request_result(pult,
                                                              monkeypatch):
    """Подложенный зелёный итог запроса в каталоге `suite-run` не меняет красный итог прогона планки узлом пульта.

    Сценарий: в очереди задачи лежат запрос и его «зелёный» итог; отчёт
    JUnit подменённого `docker` — красный. Планка выложена узлом пульта
    (`acceptance.plank_in_code_copy`) и прогнана `acceptance.run_plank` с
    профилем задачи вне процесса роли: код выхода не 0. Контроль: тот же
    прогон с зелёным отчётом — код 0.

    Ловит мутацию: прогон планки пульта берёт итог из файла итога запроса
    роли (красная планка сходит за зелёную).
    """
    p = pult
    task, wt, plank = p.task(p.compose_project())
    number = 1 + p.rng.randrange(40)
    p.plant(task, number, p.request(task))
    (p.queue(task) / f"{number}.result.json").write_text(json.dumps(
        {"kind": "plank", "green": True, "code": 0,
         "report": f"[{task}] plank-run: итог pytest: 1 passed in 0.01s; "
                   f"код выхода pytest: 0"}), encoding="utf-8")
    monkeypatch.setenv("PATH", p.env()["PATH"])
    for name in ("DOCKER_HOST", "DOCKER_CONFIG", config.ARTEL_ROLE_ENV):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(p.home))
    own = acceptance.task_own_profile(store.db(), task)
    codes = {}
    for red in (True, False):
        p.save_scenario(red=red)
        with acceptance.plank_in_code_copy(task, "unused", wt, files={
                plank: PROBE_TEST.encode()}) as tdir:
            rel = (tdir / "acceptance_tests").relative_to(wt).as_posix()
            codes[red] = acceptance.run_plank([rel], wt, profile=own,
                                              task_id=task)
    where = p.where(codes, [c["sub"] for c in p.calls()])
    assert codes[True][0] not in (0, None), where
    assert codes[False][0] == 0, where


# --------------------------------------------------------------- AC-19

def test_ac19_developer_full_suite_refused_without_request(pult):
    """Роль developer, `suite-run <id>` без флагов в проекте `compose` — прежний отказ разработчику, запрос не записан.

    Ловит мутацию: в режиме запроса проверка роли разработчика пропущена —
    команда пишет запрос `full` (файл в очереди) вместо отказа.
    """
    p = pult
    task, _wt, _plank = p.task(p.compose_project(), state="in_dev")
    p.lease(task)
    code, out = p.cli("suite-run", task, role="developer")
    where = p.where(f"код {code}", out[-800:])
    assert code != 0, where
    assert "недоступен роли developer" in out, where
    assert p.requests(task) == [], where
    assert p.calls() == [], where


# --------------------------------------------------------------- AC-21

@pytest.mark.parametrize("sign", ["artel_role", "role_home"])
def test_ac21_direct_compose_run_in_role_refused(pult, monkeypatch, sign):
    """Прямой прогон `compose` в процессе роли (не через исполнителя) — прежний отказ `COMPOSE_ROLE_REFUSAL`, `docker` не вызван.

    Сценарий: признак роли — `ARTEL_ROLE` либо `HOME`, равный дому роли, без
    маркера; места `acceptance.report_run` и `acceptance.run_plank` с
    профилем задачи проекта `compose`. Отказ несёт
    `acceptance.COMPOSE_ROLE_REFUSAL`, журнал `docker` пуст. Контроль: без
    признака роли тот же прогон вызывает `docker run`.

    Ловит мутацию: исполнитель открыт через ослабленную проверку признака
    роли в узле прогона (дом роли без маркера или маркер проходят до
    `docker`).
    """
    p = pult
    task, wt, _plank = p.task(p.compose_project())
    monkeypatch.setenv("PATH", p.env()["PATH"])
    for name in ("DOCKER_HOST", "DOCKER_CONFIG", config.ARTEL_ROLE_ENV):
        monkeypatch.delenv(name, raising=False)
    if sign == "artel_role":
        monkeypatch.setenv(config.ARTEL_ROLE_ENV, "developer")
        monkeypatch.setenv("HOME", str(p.home))
    else:
        monkeypatch.setenv("HOME", str(config.ROLE_HOME))
    own = acceptance.task_own_profile(store.db(), task)
    test_rel = f"{p.compose['app']}/tests/test_probe.py"
    run = acceptance.report_run(own, wt, [test_rel], 60.0, task_id=task)
    code, output = acceptance.run_plank([test_rel], wt, profile=own,
                                        compose_task_id=task)
    where = p.where(sign, run.text()[-400:], output[-400:])
    assert acceptance.COMPOSE_ROLE_REFUSAL in (run.refusal or ""), where
    assert acceptance.COMPOSE_ROLE_REFUSAL in output and code != 0, where
    assert p.calls() == [], f"{where}: {p.calls()}"
    monkeypatch.delenv(config.ARTEL_ROLE_ENV, raising=False)
    monkeypatch.setenv("HOME", str(p.home))
    acceptance.report_run(own, wt, [test_rel], 60.0, task_id=task)
    assert [c for c in p.calls() if c.get("sub") == "run"], \
        p.where("контроль вне роли", p.calls())


# --------------------------------------------------------------- AC-22

@pytest.mark.timeout(240)
def test_ac22_fallback_ps_and_down_only_own_child_project(pult):
    """Дочерний прогон не снял стенд (`down -v` завис) — исполнитель спрашивает `docker ps` и делает `down --remove-orphans` без `-v` только проекту своего дочернего прогона.

    Сценарий: в `config.py` копии пульта `COMPOSE_TEARDOWN_TIMEOUT_SEC` — 2–3
    с; `down -v` подменённого `docker` висит; «шлагбаум» держит `run`; в
    `run.json` каталога `suite-run` — pid живой заглушки. `docker ps`
    называет три проекта: (а) свой — префикс задачи, метка — pid дочернего
    прогона; (б) префикс задачи, метка — pid заглушки; (в) префикс другой
    задачи, метка — pid дочернего прогона. «Агент» пишет `plank-run`,
    дожидается `run` и завершается. От процесса исполнителя (ppid —
    драйвер): вызов `docker ps -a --filter label=com.docker.compose.project
    --format {{json .}}` и `compose --project-name (а) down --remove-orphans`
    без `-v`; (б) и (в) — ни одного `down`; заглушка жива; итог «прерван: шаг
    роли завершён» и запись журнала «прогон по запросу роли» — раньше записи
    учёта шага; процесс пульта довёл шаг сам.

    Ловит мутацию: исполнитель без запасного пути (`docker ps` и явного
    `down` нет); `down` с `-v` или по одному префиксу задачи (проект (б)
    снят) или по одной метке pid (проект (в) снят); pid из `run.json`;
    `killpg` не своей группы (драйвер или заглушка убиты); итог и журнал —
    после учёта шага.
    """
    p = pult
    p.set_config(COMPOSE_TEARDOWN_TIMEOUT_SEC=p.rng.choice([2, 3]))
    task, _wt, _plank = p.task(p.compose_project())
    p.lease(task)
    stub = p.sleeper()
    p.plant_run(task, stub)
    other = new_task_id(p.rng)
    by_stub = f"artel-{task.lower()}-{os.urandom(4).hex()}"
    foreign = f"artel-{other.lower()}-{os.urandom(4).hex()}"
    host, started = socket.gethostname(), store.now()
    p.save_scenario(down_hang=60, extra_projects=[
        {"project": by_stub, "labels": {"artel.run-pid": str(stub),
                                        "artel.run-host": host,
                                        "artel.run-started": started}},
        {"project": foreign, "labels": {"artel.run-pid": "@CHILD@",
                                        "artel.run-host": host,
                                        "artel.run-started": started}}])
    p.hold_file.write_text("hold", encoding="utf-8")
    step = p.step(task, "test_author", [
        {"do": "cmd", "args": ["plank-run", task], "tag": "request"},
        {"do": "await_blocked", "count": 1, "limit": 60}])
    calls = p.calls()
    where = p.where(p.results(task), step.out[-1500:],
                    [(c["sub"], c["project"], c["ppid"], c["rest"])
                     for c in calls])
    runs = [c for c in calls if c.get("sub") == "run"]
    assert runs, where
    own_project, child = runs[0]["project"], runs[0]["ppid"]
    executor = [c for c in calls if c.get("ppid") == step.driver_pid]
    assert [c for c in executor if c["argv"] == PS_ARGV], where
    fallback = [c for c in executor if c.get("sub") == "down"
                and c.get("project") == own_project]
    assert fallback, f"{where}: явного down проекта {own_project} нет"
    assert all("--remove-orphans" in c["rest"] and "-v" not in c["rest"]
               for c in fallback), where
    assert not [c for c in calls if c.get("sub") == "down"
                and c.get("project") in (by_stub, foreign)], where
    assert child != step.driver_pid, where
    assert pid_alive(stub), where
    assert any(INTERRUPTED in text for text in p.results(task).values()), where
    rows = p.journal(task)
    marks = [i for i, r in enumerate(rows)
             if REQUEST_ACTION in f"{r['action']} {r['detail']}"]
    friction = [i for i, r in enumerate(rows)
                if r["action"] == agent_log.FRICTION_JOURNAL_ACTION]
    assert marks and friction and marks[0] < friction[-1], \
        p.where([(r["action"], r["detail"][:80]) for r in rows])
    assert step.finished, where


# --------------------------------------------------------------- AC-23

@pytest.mark.timeout(300)
def test_ac23_plank_and_full_results_kept_apart(pult):
    """Итог запроса планки не меняет `failed.json` и вывод `suite-run --wait`; итог полного набора не меняет вывод `plank-run --wait`.

    Сценарий одного шага роли test_author: полный набор (красный отчёт
    JUnit) → `suite-run --wait` (вывод S1) и `failed.json` (F1); запрос
    планки (зелёный отчёт) → `plank-run --wait` (P1), затем снова
    `failed.json` (F2) и `suite-run --wait` (S2); второй полный набор →
    `suite-run --wait`, затем `plank-run --wait` (P2). S1 — отчёт
    `suite-run`, P1 — отчёт `plank-run`, F1 есть; F1 = F2, S1 = S2, P1 = P2.

    Ловит мутацию: исполнитель пишет итог запроса планки в общий
    `result.json`/`failed.json` хозяйства `suite-run` (S2 или F2 — итог
    планки) или `plank-run --wait` читает последний итог любого вида (P2 —
    отчёт полного набора).
    """
    p = pult
    task, _wt, _plank = p.task(p.compose_project())
    p.lease(task)
    failed = str(p.task_dir(task) / "failed.json")
    step = p.step(task, "test_author", [
        {"do": "cmd", "args": ["suite-run", task], "tag": "s"},
        {"do": "cmd", "args": ["suite-run", task, "--wait", "1"], "tag": "s1"},
        {"do": "read", "path": failed, "tag": "f1"},
        {"do": "cmd", "args": ["plank-run", task], "tag": "p"},
        {"do": "cmd", "args": ["plank-run", task, "--wait", "1"], "tag": "p1"},
        {"do": "read", "path": failed, "tag": "f2"},
        {"do": "cmd", "args": ["suite-run", task, "--wait", "1"], "tag": "s2"},
        {"do": "cmd", "args": ["suite-run", task], "tag": "s3"},
        {"do": "cmd", "args": ["suite-run", task, "--wait", "1"],
         "tag": "s3w"},
        {"do": "cmd", "args": ["plank-run", task, "--wait", "1"],
         "tag": "p2"}], timeout=200)
    s1, s2 = step.output("s1"), step.output("s2")
    p1, p2 = step.output("p1"), step.output("p2")
    f1, f2 = step.tagged("f1").get("text"), step.tagged("f2").get("text")
    where = p.where(s1[-600:], p1[-600:], f1, step.output("s3w")[-400:],
                    step.out[-1000:])
    assert re.search(SUITE_REPORT.format(task=re.escape(task)), s1), where
    assert re.search(PLANK_REPORT.format(task=re.escape(task)), p1), where
    assert f1 is not None, where
    assert re.search(SUITE_REPORT.format(task=re.escape(task)),
                     step.output("s3w")), where
    assert f2 == f1, p.where(f1, f2)
    assert s2 == s1, p.where(s1[-600:], s2[-600:])
    assert p2 == p1, p.where(p1[-600:], p2[-600:])


# --------------------------------------------------------------- AC-25

@pytest.mark.timeout(240)
def test_ac25_planted_full_request_refused_for_developer_step(pult):
    """Подложенный в обход команды запрос `full` в шаге разработчика — отказ итогом с причиной (роль), `docker` не вызван; тот же файл в шаге роли с правом полного набора — исполнен.

    Ловит мутацию: запрет полного набора разработчику держит только
    команда, исполнитель вид запроса с ролью своего шага не сверяет
    (подложенный `full` исполнен в шаге developer — `docker` вызван).
    """
    p = pult
    task, _wt, _plank = p.task(p.compose_project(), state="in_dev")
    p.lease(task)
    data = p.request(task, kind="full")
    first = 1 + p.rng.randrange(40)
    dev = p.step(task, "developer", [
        {"do": "write", "name": f"{first}.json", "data": data},
        {"do": "await_result", "name": f"{first}.result.json",
         "limit": 40}])
    text = p.result(task, first)
    where = p.where(text, dev.out[-1200:])
    assert text and ("developer" in text or "разработчик" in text), where
    assert p.calls() == [], f"{where}: {p.calls()}"
    role = p.rng.choice(FULL_ALLOWED_ROLES)
    second = first + 1 + p.rng.randrange(40)
    allowed = p.step(task, role, [
        {"do": "write", "name": f"{second}.json", "data": data},
        {"do": "await_result", "name": f"{second}.result.json",
         "limit": 80}], timeout=110)
    assert executor_calls(p, allowed, "run"), \
        p.where(role, p.results(task), allowed.out[-1200:])


# --------------------------------------------------------------- AC-26

def test_ac26_executor_refuses_request_of_pytest_own_task(pult):
    """Задача проекта с раннером `pytest-own`: подложенный запрос планки — отказ итогом с причиной (раннер), ни команда-заглушка, ни `docker` не запущены; тот же запрос у задачи проекта `compose` — исполнен.

    Ловит мутацию: исполнитель не сверяет раннер профиля задачи (запрос
    задачи `pytest-own` исполнен на хосте процессом пульта — заглушка
    вызвана); отказ без причины.
    """
    p = pult
    task, _wt, _plank = p.task(p.own_project())
    p.lease(task)
    number = 1 + p.rng.randrange(40)
    step = p.step(task, "test_author", [
        {"do": "write", "name": f"{number}.json", "data": p.request(task)},
        {"do": "await_result", "name": f"{number}.result.json",
         "limit": 40}])
    text = p.result(task, number)
    where = p.where(text, step.out[-1200:])
    assert "раннер" in text or "pytest-own" in text, where
    assert p.own() == [], f"{where}: {p.own()}"
    assert p.calls() == [], f"{where}: {p.calls()}"
    task, _wt, _plank = p.task(p.compose_project())
    p.lease(task)
    step = p.step(task, "test_author", [
        {"do": "write", "name": f"{number}.json", "data": p.request(task)},
        {"do": "await_result", "name": f"{number}.result.json",
         "limit": 60}])
    assert executor_calls(p, step, "run"), \
        p.where(p.results(task), step.out[-1200:])


def test_ac26_request_mode_by_task_component_runner(pult):
    """Проект из двух компонентов (`pytest-own` и `compose`): `plank-run` задачи компонента `pytest-own` в процессе роли — прежний путь (заглушка вызвана, запроса нет, `docker` не вызван); задачи компонента `compose` — запрос записан, `docker` не вызван.

    Ловит мутацию: режим запроса включается по проекту целиком (задача
    `pytest-own` получает запрос вместо прогона) или по раннеру первого
    компонента записи (задача `compose` идёт прежним путём — запроса нет).
    """
    p = pult
    target, own_zone, box_zone = p.multi_project()
    role = "test_author"
    own_task, _wt, _plank = p.task(target, zones=own_zone)
    p.lease(own_task)
    code, out = p.cli("plank-run", own_task, role=role)
    where = p.where("pytest-own", f"код {code}", out[-1200:])
    assert p.own(), f"{where}: заглушка не вызвана"
    assert p.requests(own_task) == [], where
    assert p.calls() == [], where
    box_task, _wt, _plank = p.task(target, zones=box_zone)
    p.lease(box_task)
    code, out = p.cli("plank-run", box_task, role=role)
    where = p.where("compose", f"код {code}", out[-1200:])
    assert len(p.requests(box_task)) == 1, where
    assert p.calls() == [], where
