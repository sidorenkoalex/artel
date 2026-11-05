"""Прогон места с раннером `compose`: argv, сборка конфигурации, отказы запуска, жизненный цикл стенда.

Группа: долгоживущий

Песочница — настоящий git (`real_git`): дерево прогона — репозиторий
песочницы с учебным проектом (тест в `workdir`, Compose-файл, шаблон файла
окружения), запись проекта — локальный слой (`targets.local_path()`), профиль
`test_profile` — `Profile.from_values` + `with_tools` (тот же путь, что
`project_profile.decide`), компонента — `component_profiles`.

Программа `docker` подменена исполнителем на Python в каталоге PATH теста
(без настоящего Docker): каждый вызов дописывает строку журнала (argv,
окружение, рабочий каталог, содержимое файлов `-f`/`--env-file` в момент
вызова) и отвечает по файлу сценария: `config --format json` — заданной
конфигурацией (или текстом, кодом, зависанием), `context inspect` — адресом
сокета, `run` — отчётом JUnit по пути `--junitxml`, переведённому из
контейнера в дерево по `compose_mount`. Зависание — `os.execv` программы
`sleep` (без процесса-внука). `subprocess.Popen` подменён наследником
настоящего: он запоминает пределы `communicate`/`wait` каждого процесса
(так наблюдаются пределы вызовов `docker`) и может бросить исключение
внутри вызова `run`; в уборке фикстура снимает группы всех порождённых
процессов. Окружение теста: `HOME` — каталог песочницы, переменная-метка
теста, `ARTEL_ROLE` снят, `DOCKER_HOST`/`DOCKER_CONFIG` сняты (тест, которому
они нужны, ставит их сам), сокет Docker — файл-сокет во временном каталоге.
Константы пределов `config.COMPOSE_*` тест подменяет малыми значениями.

Имена проекта, сервисов, сетей, томов, каталогов, id задачи — случайные на
каждом прогоне; зерно печатается и входит в текст провала.

Красен до реализации: раннера `compose` в пульте нет — запись `runner: compose` не загружается (`TargetsError`), у `acceptance.report_run`/`run_plank`/`run_repeat`/`run_full_suite` нет параметров `task_id`/`compose_task_id`, подменённый `docker` не вызывается ни разу.
"""
import json
import os
import random
import shutil
import signal
import socket
import string
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

import orchestrator
from orchestrator import acceptance, config, lease, project_profile, store, targets
from orchestrator.advance_gates import acceptance as gate_acceptance
from orchestrator.advance_gates import two_sided

REAL_POPEN = subprocess.Popen
REAL_MONOTONIC = time.monotonic
SLEEP = shutil.which("sleep") or "/bin/sleep"
LETTERS = string.ascii_lowercase
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ROLE_REFUSAL = ("раннер compose в шаге роли не исполняется — прогон в "
                "контейнере делают гейты пульта")
RUN_LABELS = ("artel.run-pid", "artel.run-host", "artel.run-started")
VALUED = ("--project-name", "-p", "--project-directory", "-f", "--file",
          "--env-file", "--profile", "--ansi", "--progress", "--parallel")
REPO_ROOT = Path(orchestrator.__file__).resolve().parent.parent
# `LC_CTYPE`, который ставит сам интерпретатор подменённого `docker` при
# локали «C» (PEP 538), — не переменная пульта.
PY_COERCED_LOCALES = ("C.UTF-8", "C.utf8", "UTF-8")

FAKE_DOCKER = r'''#!@PYTHON@
import json
import os
import sys
import time

STATE = @STATE@
SLEEP = @SLEEP@
VALUED = @VALUED@


def parse(args):
    kind = args[0] if args else ""
    opts = {}
    if kind != "compose":
        return kind, (args[1] if len(args) > 1 else ""), opts, args[2:]
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


def snapshot(paths):
    out = {}
    for path in paths:
        try:
            with open(path, encoding="utf-8") as fh:
                out[path] = fh.read()
        except OSError:
            out[path] = None
    return out


def option(opts, *names):
    for name in names:
        if opts.get(name):
            return opts[name][-1]
    return ""


def junit_path(rest):
    for i, arg in enumerate(rest):
        if arg == "--junitxml" and i + 1 < len(rest):
            return rest[i + 1]
        if arg.startswith("--junitxml="):
            return arg.split("=", 1)[1]
    return ""


def main():
    args = sys.argv[1:]
    with open(os.path.join(STATE, "scenario.json"), encoding="utf-8") as fh:
        sc = json.load(fh)
    kind, sub, opts, rest = parse(args)
    record = {"argv": args, "env": dict(os.environ), "cwd": os.getcwd(),
              "kind": kind, "sub": sub, "pid": os.getpid(),
              "files": snapshot(opts.get("-f", []) + opts.get("--file", [])
                                + opts.get("--env-file", []))}
    with open(os.path.join(STATE, "calls.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    act = sc.get("acts", {}).get(sub if kind == "compose" else kind, {})
    if act.get("hang"):
        os.execv(SLEEP, [SLEEP, "600"])
    if act.get("sleep"):
        time.sleep(act["sleep"])
    project = option(opts, "--project-name", "-p")
    tree = os.path.dirname(option(opts, "--project-directory").rstrip("/"))
    if kind == "compose" and sub == "config":
        out = act.get("stdout")
        if out is None:
            out = (json.dumps(sc["config"]).replace("@PROJECT@", project)
                   .replace("@TREE@", tree))
        sys.stdout.write(out)
    elif kind == "compose" and sub == "run":
        target = junit_path(rest)
        right = sc["right"].rstrip("/") + "/"
        if target.startswith(right) and sc.get("junit") is not None:
            host = os.path.join(tree, sc["left"], target[len(right):])
            os.makedirs(os.path.dirname(host), exist_ok=True)
            with open(host, "w", encoding="utf-8") as fh:
                fh.write(sc["junit"])
    elif kind == "context":
        host = sc.get("context_host", "unix:///nonexistent/docker.sock")
        if any("{{" in a for a in args):
            print(host)
        else:
            print(json.dumps([{"Name": "default", "Current": True,
                               "Endpoints": {"docker": {"Host": host}}}]))
    elif kind == "version":
        print("Docker version 27.0.0, build fake")
    elif kind == "compose" and sub == "version":
        print("Docker Compose version v2.29.0")
    sys.stdout.flush()
    sys.stderr.write(act.get("stderr", ""))
    sys.exit(act.get("code", 0))


main()
'''

PROBE_TEST = '''import unittest


class ProbeTest(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(True)
'''

JUNIT = ('<?xml version="1.0" encoding="utf-8"?><testsuites>'
         '<testsuite name="pytest" errors="0" failures="{failures}" '
         'skipped="0" tests="1" time="0.01"><testcase classname="{classname}" '
         'name="test_ok" time="0.001">{body}</testcase></testsuite>'
         '</testsuites>')


def word(rng, k: int = 6) -> str:
    return "".join(rng.choices(LETTERS, k=k))


def docker_sub(argv) -> tuple:
    """(вид, подкоманда) argv вызова `docker` — тем же разбором, что у
    подменённой программы."""
    args = [str(a) for a in argv][1:]
    kind = args[0] if args else ""
    if kind != "compose":
        return kind, (args[1] if len(args) > 1 else "")
    i = 1
    while i < len(args) and args[i].startswith("-"):
        key, eq, _value = args[i].partition("=")
        i += 2 if (not eq and args[i] in VALUED) else 1
    return kind, (args[i] if i < len(args) else "")


def global_opts(argv: list) -> dict:
    """Опции `docker compose` до подкоманды: имя → список значений."""
    opts, i = {}, 1
    while i < len(argv) and argv[i].startswith("-"):
        key, eq, value = argv[i].partition("=")
        if eq and key in VALUED:
            opts.setdefault(key, []).append(value)
            i += 1
        elif argv[i] in VALUED and i + 1 < len(argv):
            opts.setdefault(argv[i], []).append(argv[i + 1])
            i += 2
        else:
            opts.setdefault(argv[i], []).append("")
            i += 1
    return opts


def after_sub(argv: list) -> list:
    """Аргументы `docker compose` после подкоманды."""
    i = 1
    while i < len(argv) and argv[i].startswith("-"):
        key, eq, _value = argv[i].partition("=")
        i += 2 if (not eq and argv[i] in VALUED) else 1
    return argv[i + 1:]


def project_of(call: dict) -> str:
    opts = global_opts(call["argv"])
    return (opts.get("--project-name") or opts.get("-p") or [""])[-1]


def labels_of(obj: dict) -> dict:
    labels = obj.get("labels") or {}
    if isinstance(labels, list):
        return dict(item.split("=", 1) for item in labels if "=" in item)
    return dict(labels)


def parse_file(text: str) -> dict:
    """Файл пульта: JSON (вывод `config --format json` с правкой)."""
    return json.loads(text)


def task_id(rng) -> str:
    return "01" + "".join(rng.choices(CROCKFORD, k=24))


class Stand:
    """Учебный проект `compose` в дереве песочницы и подменённый `docker`."""

    def __init__(self, sandbox, monkeypatch, rng, seed):
        self.sandbox, self.mp, self.rng, self.seed = sandbox, monkeypatch, rng, seed
        self.tree = Path(sandbox.root)
        self.left = f"src_{word(rng)}"
        self.app = f"{self.left}/app_{word(rng)}"
        self.deploy = f"deploy_{word(rng)}"
        self.right = f"/w_{word(rng)}/{word(rng)}"
        self.name = f"proj{word(rng)}"
        self.comp = f"comp{word(rng)}"
        self.service = f"svc_{word(rng)}"
        self.db = f"db_{word(rng)}"
        self.task = task_id(rng)
        self.module = f"test_probe_{word(rng)}"
        self.test_rel = f"{self.app}/tests/{self.module}.py"
        self.compose_rel = f"{self.deploy}/compose.yaml"
        self.env_rel = f"{self.deploy}/.env.{word(rng)}"
        self.template_rel = f"{self.deploy}/env.{word(rng)}.template"
        self.template_text = f"PROBE_{word(rng).upper()}={word(rng)}\n"
        self.up_down = None
        self.procs = []
        self.raise_in = None
        self.jump_after = None
        self.offset = 0.0

    # --- дерево и запись
    def build_tree(self) -> None:
        (self.tree / self.app / "tests").mkdir(parents=True)
        (self.tree / self.test_rel).write_text(PROBE_TEST, encoding="utf-8")
        (self.tree / self.deploy).mkdir()
        (self.tree / self.compose_rel).write_text(
            f"services:\n  {self.service}:\n    build: .\n", encoding="utf-8")
        (self.tree / self.template_rel).write_text(self.template_text,
                                                   encoding="utf-8")
        self.sandbox.git("add", "-A")
        self.sandbox.git("commit", "-q", "-m", "учебный проект compose")

    def fields(self, **extra) -> dict:
        fields = {"runner": "compose", "workdir": self.app,
                  "long_lived_dir": f"{self.app}/tests",
                  "long_lived_name": "test_<id>_<name>.py",
                  "report": "junit-xml", "compose_file": self.compose_rel,
                  "compose_service": self.service,
                  "compose_env_file": self.env_rel,
                  "compose_env_template": self.template_rel,
                  "compose_mount": f"{self.left}:{self.right}"}
        if self.up_down is not None:
            fields["compose_up_down_sec"] = self.up_down
        fields.update(extra)
        return {k: v for k, v in fields.items() if v is not None}

    def write_record(self, fields: dict, form: str = "test_profile",
                     machine_path: str | None = None) -> None:
        def render(values, pad):
            out = []
            for key, value in values.items():
                if isinstance(value, list):
                    out.append(f"{pad}{key}: [{', '.join(value)}]")
                elif isinstance(value, int):
                    out.append(f"{pad}{key}: {value}")
                else:
                    out.append(f'{pad}{key}: "{value}"')
            return out
        lld = fields.get("long_lived_dir", "tests")
        scopes = {"weakening_scope": [f"{lld}/**/*.py"],
                  "mutation_claim_scope": [f"{lld}/test_*.py"]}
        lines = [f"  {self.name}:", "    description:", "      base: main"]
        if form == "test_profile":
            lines += ["      test_profile:", *render(fields, " " * 8)]
        else:
            lines += ["      components:", f"        {self.comp}:",
                      *render(fields, " " * 10)]
        lines += ["    policy:", "      no_paths: []",
                  "      project_skills: []", "      merge_gate: operator"]
        if form == "test_profile":
            lines += render(scopes, " " * 6)
        else:
            lines += ["      components:", f"        {self.comp}:",
                      *render(scopes, " " * 10)]
        lines += ["    machine:", "      forge: github",
                  f"      url: https://localhost/team/{self.name}",
                  f"      token_slot: {self.name}-token"]
        if machine_path is not None:
            lines.append(f'      path: "{machine_path}"')
        path = targets.local_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("targets:\n" + "\n".join(lines) + "\n",
                        encoding="utf-8")

    def profile(self, form: str = "test_profile", machine_path=None, **extra):
        self.write_record(self.fields(**extra), form, machine_path)
        if form == "test_profile":
            values = targets.target(self.name)[targets.PROFILE_FIELD]
            return project_profile.with_tools(
                self.name, project_profile.Profile.from_values(values))
        (profile,) = project_profile.component_profiles(self.name)
        return profile

    # --- подменённый docker
    def install_docker(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="artel-compose-test-")).resolve()
        self.sandbox.addCleanup(shutil.rmtree, base, True)
        self.state = base / "state"
        self.state.mkdir()
        self.bindir = base / "bin"
        self.bindir.mkdir()
        self.noise = base / "noise"
        self.noise.mkdir()
        self.home = base / "home"
        self.home.mkdir()
        self.docker = self.bindir / "docker"
        self.docker.write_text(
            FAKE_DOCKER.replace("@PYTHON@", sys.executable)
            .replace("@STATE@", repr(str(self.state)))
            .replace("@SLEEP@", repr(SLEEP))
            .replace("@VALUED@", repr(VALUED)), encoding="utf-8")
        self.docker.chmod(0o755)
        # PATH вызывающего: каталог `docker`, каталог-«шум» и прежний PATH
        # (git пульта — в нём, у роли это обёртка, которой нужен python3).
        self.caller_path = os.pathsep.join(
            [str(self.bindir), str(self.noise),
             *[d for d in os.environ.get("PATH", "").split(os.pathsep) if d]])
        self.marker = f"ARTEL_PROBE_{word(self.rng).upper()}"
        mp = self.mp
        mp.setenv("PATH", self.caller_path)
        mp.setenv("HOME", str(self.home))
        mp.setenv(self.marker, word(self.rng))
        for name in (config.ARTEL_ROLE_ENV, "DOCKER_HOST", "DOCKER_CONFIG",
                     "CI", "LC_CTYPE"):
            mp.delenv(name, raising=False)
        sock_dir = Path(tempfile.mkdtemp(prefix="ds", dir="/tmp")).resolve()
        self.sandbox.addCleanup(shutil.rmtree, sock_dir, True)
        self.socket_path = sock_dir / "docker.sock"
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(str(self.socket_path))
        self.sandbox.addCleanup(self.sock.close)
        self.scenario()

    def base_config(self, tests_image: bool = False) -> dict:
        tests = {"depends_on": {self.db: {"condition": "service_started",
                                          "required": True}},
                 "networks": {"default": None},
                 "volumes": [{"type": "bind",
                              "source": f"@TREE@/{self.left}",
                              "target": self.right}],
                 "working_dir": self.right}
        if tests_image:
            tests["image"] = f"probe/{word(self.rng)}:latest"
        else:
            tests["build"] = {"context": f"@TREE@/{self.deploy}",
                              "dockerfile": "Dockerfile"}
        return {"name": "@PROJECT@",
                "services": {
                    self.service: tests,
                    self.db: {"image": "postgres:16-alpine",
                              "networks": {"default": None},
                              "ports": [{"mode": "ingress", "target": 5432,
                                         "published": "5432",
                                         "protocol": "tcp"}]}},
                "networks": {"default": {"name": "@PROJECT@_default"}}}

    def junit(self, failed: bool = False) -> str:
        rel = os.path.relpath(self.test_rel, self.app)
        classname = rel[:-3].replace("/", ".")
        body = '<failure message="assert False">boom</failure>' if failed else ""
        return JUNIT.format(failures=int(failed), classname=classname,
                            body=body)

    def scenario(self, config_obj=None, acts=None, junit=None,
                 context_host=None) -> None:
        data = {"config": config_obj if config_obj is not None
                else self.base_config(),
                "acts": acts or {}, "left": self.left, "right": self.right,
                "junit": junit if junit is not None else self.junit()}
        if context_host is not None:
            data["context_host"] = context_host
        (self.state / "scenario.json").write_text(json.dumps(data),
                                                  encoding="utf-8")
        calls = self.state / "calls.jsonl"
        if calls.exists():
            calls.unlink()

    def calls(self) -> list:
        path = self.state / "calls.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in
                path.read_text(encoding="utf-8").splitlines() if line]

    def compose(self, sub: str) -> list:
        return [c for c in self.calls() if c["kind"] == "compose"
                and c["sub"] == sub]

    def subs(self) -> list:
        return [c["sub"] if c["kind"] == "compose" else c["kind"]
                for c in self.calls()]

    def where(self, *parts) -> str:
        return ", ".join([*map(str, parts), f"зерно {self.seed}"])

    # --- процессы
    def spy_popen(self):
        stand = self

        class SpyPopen(REAL_POPEN):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.spy_timeouts = []
                argv = args[0] if args else kwargs.get("args")
                self.spy_argv = [str(a) for a in argv] \
                    if isinstance(argv, (list, tuple)) else [str(argv)]
                self.spy_docker = bool(self.spy_argv) and \
                    os.path.basename(self.spy_argv[0]) == "docker"
                stand.procs.append(self)

            def spy_hook(self, timeout):
                self.spy_timeouts.append(timeout)
                sub = docker_sub(self.spy_argv)[1] if self.spy_docker else ""
                if self.spy_docker and stand.raise_in == sub:
                    stand.raise_in = None
                    # Вызов успевает записать журнал и отчёт — исключение
                    # бросается «внутри» уже прошедшего вызова.
                    REAL_POPEN.wait(self, timeout=30)
                    raise RuntimeError(f"сбой внутри прогона {stand.seed}")

            def communicate(self, input=None, timeout=None):
                self.spy_hook(timeout)
                out = super().communicate(input, timeout)
                self.spy_jump()
                return out

            def wait(self, timeout=None):
                self.spy_hook(timeout)
                code = super().wait(timeout)
                self.spy_jump()
                return code

            def spy_jump(self):
                if self.spy_docker and stand.jump_after and \
                        docker_sub(self.spy_argv)[1] == stand.jump_after:
                    stand.offset += 100000.0
                    stand.jump_after = None

        self.mp.setattr(subprocess, "Popen", SpyPopen)

    def timeouts(self, sub: str) -> list:
        """Наибольший предел каждого процесса `docker compose <sub>`."""
        out = []
        for proc in self.procs:
            if proc.spy_docker and docker_sub(proc.spy_argv)[1] == sub:
                limits = [t for t in proc.spy_timeouts if t is not None]
                out.append(max(limits) if limits else None)
        return out

    def shifted_clock(self):
        """`time.monotonic`/`time.time` со сдвигом `self.offset`: сдвиг
        растёт после вызова, названного `jump_after`. Таймауты самого
        `subprocess` идут по его собственной ссылке на часы и не сдвигаются."""
        real_time = time.time
        self.mp.setattr(time, "monotonic", lambda: REAL_MONOTONIC() + self.offset)
        self.mp.setattr(time, "time", lambda: real_time() + self.offset)

    def reap(self) -> None:
        for proc in self.procs:
            if proc.poll() is not None:
                continue
            try:
                group = os.getpgid(proc.pid)
                if group != os.getpgrp():
                    os.killpg(group, signal.SIGKILL)
                else:
                    proc.kill()
            except (ProcessLookupError, PermissionError):
                pass
            try:
                REAL_POPEN.wait(proc, timeout=5)
            except subprocess.TimeoutExpired:
                pass

    # --- места
    def report_run(self, profile, subset=None, timeout=60.0, **kwargs):
        kwargs.setdefault("task_id", self.task)
        if kwargs["task_id"] is None:
            kwargs.pop("task_id")
        subset = [self.test_rel] if subset is None else subset
        return acceptance.report_run(profile, self.tree, subset, timeout,
                                     **kwargs)


@pytest.fixture
def stand(real_git, monkeypatch):
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    st = Stand(real_git, monkeypatch, random.Random(seed), seed)
    st.build_tree()
    st.install_docker()
    st.spy_popen()
    conn = store.db()
    store.insert_task(conn, st.task, "Задача compose", "in_dev",
                      f"task/{st.task.lower()}-compose", st.name, 25.0)
    try:
        yield st
    finally:
        st.reap()


def run_call(st) -> dict:
    runs = st.compose("run")
    return runs[-1] if runs else {}


def service_tail(st, argv: list) -> list:
    """Аргументы после имени сервиса в `run`."""
    rest = after_sub(argv)
    return rest[rest.index(st.service) + 1:] if st.service in rest else []


def container_target(st, arg: str, workdir: str) -> str:
    """Путь цели в контейнере: абсолютный — как есть, относительный — от `-w`."""
    path = arg.partition("::")[0]
    return os.path.normpath(path if os.path.isabs(path)
                            else os.path.join(workdir, path))


def w_of(argv: list) -> str:
    rest = after_sub(argv)
    for i, arg in enumerate(rest):
        if arg in ("-w", "--workdir") and i + 1 < len(rest):
            return rest[i + 1]
        if arg.startswith("--workdir="):
            return arg.split("=", 1)[1]
    return ""


def junit_arg(argv: list) -> str:
    for i, arg in enumerate(argv):
        if arg == "--junitxml" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--junitxml="):
            return arg.split("=", 1)[1]
    return ""


def name_pattern_ok(name: str, tid: str) -> bool:
    prefix = f"artel-{tid.lower()}-"
    run = name[len(prefix):]
    return (name.startswith(prefix) and len(run) == 8
            and all(c in "0123456789abcdef" for c in run)
            and all(c in LETTERS + "0123456789-" for c in name))


# --------------------------------------------------------------- AC-3

@pytest.mark.parametrize("failed", [False, True])
def test_ac3_plank_run_argv_and_outcome_from_report(stand, failed):
    """Прогон планки `compose`: argv `run` по форме требования, отчёт под монтированием, итог — из отчёта.

    `acceptance.run_plank` долгоживущего файла (`compose_task_id`) с
    профилем `compose`. Вызов `run`: `docker compose --project-name
    artel-<id строчными>-<8 hex> --project-directory <каталог compose_file в
    дереве> -f <файл пульта, не Compose-файл проекта> run --rm -w <workdir в
    контейнере> <сервис> pytest <цель> --junitxml <путь в контейнере>`; цель
    в контейнере — файл теста под правой частью монтирования; путь отчёта —
    `<правая часть>/.artel-report/<прогон>.xml`, где `<прогон>` — хвост имени
    проекта. Подменённый `run` выходит с кодом 0 всегда, а отчёт несёт
    падение или нет: код `run_plank` — 0 только при зелёном отчёте.

    Ловит мутацию: `-f` указывает на Compose-файл проекта вместо файла
    пульта, `-w` — путь машины, цель не переведена в контейнер, отчёт пишется
    вне монтирования (его не прочесть с машины — исход «неизвестно»), итог —
    по коду возврата `run` (красный отчёт сходит за зелёный).
    """
    st = stand
    profile = st.profile()
    st.scenario(junit=st.junit(failed=failed))
    code, output = acceptance.run_plank([st.test_rel], st.tree,
                                        profile=profile,
                                        compose_task_id=st.task)
    where = st.where(f"failed={failed}", output[-600:])
    call = run_call(st)
    assert call, f"{where}: run не вызван: {st.subs()}"
    argv = call["argv"]
    assert argv[0] == "compose", where
    opts = global_opts(argv)
    name = project_of(call)
    assert name_pattern_ok(name, st.task), f"{where}: имя {name!r}"
    assert Path(opts.get("--project-directory", [""])[-1]).resolve() == \
        (st.tree / st.deploy).resolve(), f"{where}: {opts}"
    pult_file = (opts.get("-f") or opts.get("--file") or [""])[-1]
    assert pult_file and Path(pult_file).resolve() != \
        (st.tree / st.compose_rel).resolve(), f"{where}: -f {pult_file}"
    rest = after_sub(argv)
    assert st.service in rest, f"{where}: {rest}"
    assert "--rm" in rest[:rest.index(st.service)], f"{where}: {rest}"
    workdir = w_of(argv)
    rel_app = os.path.relpath(st.app, st.left)
    assert os.path.normpath(workdir) == os.path.normpath(
        f"{st.right}/{rel_app}"), f"{where}: -w {workdir}"
    tail = service_tail(st, argv)
    assert tail[:1] == ["pytest"], f"{where}: {tail}"
    expected = os.path.normpath(
        f"{st.right}/{os.path.relpath(st.test_rel, st.left)}")
    assert expected in [container_target(st, a, workdir) for a in tail[1:]
                        if not a.startswith("-")], f"{where}: {tail}"
    report = junit_arg(tail)
    run_id = name.rsplit("-", 1)[1]
    assert report == f"{st.right}/.artel-report/{run_id}.xml", \
        f"{where}: {report}"
    assert (code == 0) is (not failed), f"{where}: код {code}"


# --------------------------------------------------------------- AC-4

def test_ac4_config_call_env_copy_and_pult_file(stand):
    """Сборка `config` с `--env-file` дерева после копии шаблона; файл пульта — изолированные сети, без `ports`, с метками.

    До прогона в `compose_env_file` лежит устаревший текст. Вызов `config`
    несёт `--project-name` и `--project-directory` того же прогона, `-f
    <compose_file дерева>`, `--env-file <compose_env_file дерева>`; в
    момент вызова файл окружения — точная копия шаблона. Файл пульта (`-f`
    вызовов `up`/`run`): у сети `default` и у объявленной сети проекта —
    `internal: true`, ни у одного сервиса нет `ports`, у сервисов и сетей —
    метки `artel.run-pid`/`artel.run-host`/`artel.run-started`, и тройка
    меток — живой процесс пульта (`lease.process_alive`).

    Ловит мутацию: шаблон не копируется (или копируется после `config`),
    `config` идёт без `--env-file`/с другим именем проекта, правка не снимает
    `ports` у службы-зависимости, `internal` ставится только явным сетям
    (неявная `default` открыта), метки — только контейнерам или pid не тот.
    """
    st = stand
    profile = st.profile()
    net = f"net_{word(st.rng)}"
    cfg = st.base_config()
    cfg["networks"][net] = {"name": f"@PROJECT@_{net}"}
    cfg["services"][st.db]["networks"] = {"default": None, net: None}
    st.scenario(config_obj=cfg)
    (st.tree / st.env_rel).write_text(f"STALE={word(st.rng)}\n",
                                      encoding="utf-8")
    run = st.report_run(profile)
    where = st.where(run.text()[-600:] if run else "")
    configs = st.compose("config")
    assert len(configs) >= 1, f"{where}: {st.subs()}"
    call = configs[0]
    opts = global_opts(call["argv"])
    env_file = (opts.get("--env-file") or [""])[-1]
    compose_file = (opts.get("-f") or opts.get("--file") or [""])[-1]
    assert Path(compose_file).resolve() == (st.tree / st.compose_rel).resolve(), where
    assert Path(env_file).resolve() == (st.tree / st.env_rel).resolve(), where
    assert call["files"].get(env_file) == st.template_text, \
        f"{where}: файл окружения в момент config: {call['files']!r}"
    rest = after_sub(call["argv"])
    assert "--format=json" in rest or any(
        a == "--format" and b == "json" for a, b in zip(rest, rest[1:])), \
        f"{where}: {rest}"
    run_c = run_call(st)
    assert project_of(call) == project_of(run_c), where
    assert global_opts(call["argv"]).get("--project-directory") == \
        global_opts(run_c["argv"]).get("--project-directory"), where
    pult_file = (global_opts(run_c["argv"]).get("-f") or [""])[-1]
    data = parse_file(run_c["files"][pult_file])
    networks = data.get("networks") or {}
    assert "default" in networks and net in networks, f"{where}: {networks}"
    for key, value in networks.items():
        assert (value or {}).get("internal") is True, f"{where}: сеть {key}"
        labels = labels_of(value or {})
        assert all(label in labels for label in RUN_LABELS), \
            f"{where}: метки сети {key}: {labels}"
    for key, service in data["services"].items():
        assert "ports" not in service, f"{where}: ports у {key}"
        labels = labels_of(service)
        assert all(label in labels for label in RUN_LABELS), \
            f"{where}: метки сервиса {key}: {labels}"
        assert labels["artel.run-pid"] == str(os.getpid()), where
        assert lease.process_alive(int(labels["artel.run-pid"]),
                                   labels["artel.run-host"],
                                   labels["artel.run-started"]), \
            f"{where}: метки {labels}"


# --------------------------------------------------------------- AC-5, AC-6

SOCKET_LITERALS = ["/var/run/docker.sock", "/run/docker.sock", "/var/run",
                   "/run", "/var", "/"]
LOCAL_DRIVER_OPTS = [("local", {"o": "bind", "type": "none", "device": "/x"}),
                     (None, {"o": "bind,ro", "type": "none", "device": "/x"}),
                     ("local", {"o": "rbind", "type": "none", "device": "/x"}),
                     (None, {"type": "none", "device": "/srv/x"}),
                     ("local", {"type": "tmpfs", "device": "tmpfs"})]

REFUSAL_CASES = (
    [("network_mode", None), ("external_network", None),
     ("bind_socket_docker_host", None), ("bind_socket_link", None),
     ("bind_socket_dir", None), ("bind_socket_context", None),
     ("volumes_from", None), ("secret_literal", "/var/run/docker.sock"),
     ("secret_literal", "/var/run"), ("secret_link", None),
     ("config_literal", "/run/docker.sock"), ("config_link", None)]
    + [("bind_literal", path) for path in SOCKET_LITERALS]
    + [("driver_opts", index) for index in range(len(LOCAL_DRIVER_OPTS))])
NAME_CASES = ["container_name", "network_name", "volume_name",
              "network_name_prefix2"]


def refusal_variant(st, case: str, arg) -> tuple:
    """(конфигурация, имя в тексте отказа, переменные окружения теста)."""
    cfg = st.base_config(tests_image=True)
    svc = cfg["services"][st.service]
    other = f"x_{word(st.rng)}"
    env = {"DOCKER_HOST": f"unix://{st.socket_path}"}
    link = st.socket_path.parent / f"link_{word(st.rng)}.sock"
    if case in ("bind_socket_link", "secret_link", "config_link"):
        link.symlink_to(st.socket_path)
    if case == "network_mode":
        svc["network_mode"] = "host"
        return cfg, st.service, env
    if case == "external_network":
        cfg["networks"][other] = {"name": other, "external": True}
        return cfg, other, env
    if case.startswith("bind_"):
        source = {"bind_socket_docker_host": str(st.socket_path),
                  "bind_socket_link": str(link),
                  "bind_socket_dir": str(st.socket_path.parent),
                  "bind_socket_context": str(st.socket_path),
                  "bind_literal": arg}[case]
        svc["volumes"].append({"type": "bind", "source": source,
                               "target": f"/mnt/{word(st.rng)}"})
        if case in ("bind_socket_context", "bind_literal"):
            env = {}
        return cfg, st.service, env
    if case == "volumes_from":
        svc["volumes_from"] = [st.db]
        return cfg, st.service, env
    if case.startswith(("secret_", "config_")):
        section = "secrets" if case.startswith("secret_") else "configs"
        path = arg if case.endswith("_literal") else str(link)
        cfg[section] = {other: {"name": f"@PROJECT@_{other}", "file": path}}
        svc[section] = [{"source": other}]
        return cfg, other, env
    if case == "container_name":
        svc["container_name"] = other
        return cfg, st.service, env
    if case == "network_name":
        cfg["networks"][other] = {"name": f"foreign_{word(st.rng)}"}
        return cfg, other, env
    if case == "network_name_prefix2":
        cfg["networks"][other] = {"name": "@PROJECT@2_db"}
        return cfg, other, env
    if case == "volume_name":
        cfg["volumes"] = {other: {"name": f"foreign_{word(st.rng)}"}}
        svc["volumes"].append({"type": "volume", "source": other,
                               "target": "/data"})
        return cfg, other, env
    if case == "driver_opts":
        driver, opts = LOCAL_DRIVER_OPTS[arg]
        volume = {"name": f"@PROJECT@_{other}", "driver_opts": dict(opts)}
        if driver:
            volume["driver"] = driver
        cfg["volumes"] = {other: volume}
        svc["volumes"].append({"type": "volume", "source": other,
                               "target": "/data"})
        return cfg, other, env
    raise AssertionError(f"неизвестный случай {case}")


def assert_refused_naming(st, case: str, arg) -> None:
    """Прогон с конфигурацией случая — отказ с именем объекта, без `up`/`run`."""
    profile = st.profile()
    cfg, named, env = refusal_variant(st, case, arg)
    for key, value in env.items():
        st.mp.setenv(key, value)
    context = f"unix://{st.socket_path}" if case == "bind_socket_context" \
        else None
    st.scenario(config_obj=cfg, context_host=context)
    run = st.report_run(profile)
    where = st.where(case, arg, run.text()[-400:])
    assert run.refusal, f"{where}: отказа нет: {st.subs()}"
    assert named in run.refusal, f"{where}: отказ не называет {named}"
    assert "config" in st.subs(), f"{where}: config не вызван"
    assert not {"up", "run"} & set(st.subs()), f"{where}: {st.subs()}"


@pytest.mark.parametrize("case, arg", REFUSAL_CASES)
def test_ac5_assembled_config_refusals_name_object(stand, case, arg):
    """Собранная конфигурация с опасной конструкцией — отказ запуска с именем объекта, `up` и `run` не зовутся.

    Ответ `config --format json` подменённого `docker` несёт одну
    конструкцию случая: `network_mode`, внешнюю сеть, bind-монтирование
    сокета Docker (сокет-файл песочницы по `DOCKER_HOST=unix://…`, ссылка на
    него, его каталог; сокет из ответа `context inspect` при не заданном
    `DOCKER_HOST`; литералы `/var/run/docker.sock`, `/run/docker.sock`,
    `/var/run`, `/run`, `/var`, `/` — без проверки существования путей),
    `volumes_from`, секрет/конфигурацию с `file:` на сокет, именованный том
    с `driver_opts` у `local`/без драйвера. Итог — отказ (`refusal`), текст
    называет сервис, сеть, том, секрет или конфигурацию; в журнале вызовов
    нет `up` и `run`. Функции модуля не подменяются — канал один, ответ
    `config`.

    Ловит мутацию: правило проверяет исходный Compose-файл вместо вывода
    `config`; сверка сокета только литералом (ссылка и каталог сокета
    песочницы проходят); `driver_opts` разбирается по `o: bind` (`rbind`,
    `type: none` проходят); `volumes_from`/секреты не проверены — стенд
    поднимается.
    """
    assert_refused_naming(stand, case, arg)


@pytest.mark.parametrize("case", NAME_CASES)
def test_ac6_container_and_foreign_names_refused(stand, case):
    """`container_name`, чужое `name:` сети или тома, имя `<проект>2_db` — отказ запуска с именем объекта.

    Ответ `config` несёт `container_name` у сервиса, сеть или том с явным
    `name:`, не равным имени проекта и без префикса `<имя проекта>_`, либо
    сеть с именем `<имя проекта>2_db`. Отказ называет сервис, сеть или
    том; `up` и `run` не зовутся. Контроль — сеть `default` с именем
    `<имя проекта>_default` в каждом зелёном прогоне файла.

    Ловит мутацию: `container_name` пропущен (контейнеры параллельных
    прогонов столкнутся), имя сверяется префиксом без `_` (`<проект>2_db`
    проходит) или проверяются только сети (том с чужим именем проходит).
    """
    assert_refused_naming(stand, case, None)


@pytest.mark.parametrize("mode", ["code", "not_json", "hang"])
def test_ac5_config_failure_refused_without_stand(stand, mode):
    """`config` с ненулевым кодом, не-JSON выводом или зависанием — отказ с текстом вызова, ни `up`, ни `run`, ни `down`.

    Зависание — дольше подменённого `config.COMPOSE_CONFIG_TIMEOUT_SEC`
    (1 с): прогон завершается быстро (предел места — 60 с). Текст отказа
    называет вызов `config`.

    Ловит мутацию: `config` без предела (прогон висит до предела места),
    ненулевой код принят за пустую конфигурацию, вывод не JSON проглочен —
    стенд поднимается; после провала `config` зовётся `down` (стенда не
    было).
    """
    st = stand
    profile = st.profile()
    st.mp.setattr(config, "COMPOSE_CONFIG_TIMEOUT_SEC", 1)
    act = {"code": {"code": 3, "stderr": f"bad {word(st.rng)}"},
           "not_json": {"stdout": f"services: {word(st.rng)}"},
           "hang": {"hang": True}}[mode]
    st.scenario(acts={"config": act})
    start = REAL_MONOTONIC()
    run = st.report_run(profile, timeout=60.0)
    elapsed = REAL_MONOTONIC() - start
    where = st.where(mode, f"{elapsed:.1f} с", run.text()[-400:])
    assert run.refusal, f"{where}: {st.subs()}"
    assert "config" in run.refusal, where
    assert not {"up", "run", "down"} & set(st.subs()), f"{where}: {st.subs()}"
    assert elapsed < 30, where


def test_ac5_remote_docker_host_refused_before_config(stand):
    """`DOCKER_HOST=tcp://…` — отказ с именем `DOCKER_HOST`, `config` не зовётся, шаблон не скопирован.

    Ловит мутацию: удалённый демон принят (проверяется только `unix://`
    сокет), проверка идёт после сборки конфигурации или после копии
    шаблона — в журнале появляется `config`, `compose_env_file` создан.
    """
    st = stand
    profile = st.profile()
    st.mp.setenv("DOCKER_HOST", f"tcp://127.0.0.{st.rng.randrange(2, 250)}:2375")
    run = st.report_run(profile)
    where = st.where(run.text()[-400:])
    assert run.refusal and "DOCKER_HOST" in run.refusal, where
    assert "config" not in st.subs(), f"{where}: {st.subs()}"
    assert not (st.tree / st.env_rel).exists(), f"{where}: шаблон скопирован"


# --------------------------------------------------------------- AC-7

def test_ac7_place_paths_translated_or_refused(stand):
    """Путь машины под левой частью монтирования — путь контейнера в argv; вне её — отказ с именем пути.

    Абсолютный путь файла теста в дереве под левой частью: в argv `run`
    после сервиса нет пути машины дерева, цель — путь контейнера под правой
    частью. Абсолютный путь файла вне левой части (существующий файл
    дерева): отказ запуска, текст называет путь, `up`/`run` не зовутся.

    Ловит мутацию: путь машины уходит в контейнер как есть (pytest в
    контейнере его не найдёт), путь вне монтирования молча пропущен или
    передан как есть.
    """
    st = stand
    profile = st.profile()
    inside = str(st.tree / st.test_rel)
    run = st.report_run(profile, subset=[inside])
    where = st.where(run.text()[-400:])
    call = run_call(st)
    assert call, f"{where}: {st.subs()}"
    tail = service_tail(st, call["argv"])
    assert not any(str(st.tree) in a for a in tail), f"{where}: {tail}"
    expected = os.path.normpath(
        f"{st.right}/{os.path.relpath(st.test_rel, st.left)}")
    workdir = w_of(call["argv"])
    assert expected in [container_target(st, a, workdir) for a in tail
                        if not a.startswith("-")], f"{where}: {tail}"
    outside_rel = f"other_{word(st.rng)}/test_out.py"
    (st.tree / outside_rel).parent.mkdir(parents=True)
    (st.tree / outside_rel).write_text(PROBE_TEST, encoding="utf-8")
    outside = str(st.tree / outside_rel)
    st.scenario()
    run = st.report_run(profile, subset=[outside])
    where = st.where(run.text()[-400:])
    assert run.refusal and outside in run.refusal, where
    assert not {"up", "run"} & set(st.subs()), f"{where}: {st.subs()}"


# --------------------------------------------------------------- AC-8

def assert_teardown(st, where, *, kill_first: bool) -> None:
    calls = st.calls()
    names = {project_of(c) for c in calls if c["kind"] == "compose"}
    assert len(names) == 1, f"{where}: имена проекта {names}"
    downs = [i for i, c in enumerate(calls)
             if c["kind"] == "compose" and c["sub"] == "down"]
    assert downs, f"{where}: down не вызван: {st.subs()}"
    rest = after_sub(calls[downs[-1]]["argv"])
    assert "-v" in rest or "--volumes" in rest, f"{where}: {rest}"
    assert "--remove-orphans" in rest, f"{where}: {rest}"
    if kill_first:
        kills = [i for i, c in enumerate(calls)
                 if c["kind"] == "compose" and c["sub"] == "kill"]
        assert kills and kills[0] < downs[-1], f"{where}: {st.subs()}"


@pytest.mark.parametrize("failed", [False, True])
def test_ac8_down_after_green_and_red(stand, failed):
    """Зелёный и красный исход — затем `down -v --remove-orphans` с тем же именем проекта; без `image:` — `--rmi local`.

    Ловит мутацию: `down` только на зелёном пути (или только в `except`),
    без `-v`/`--remove-orphans`, с новым именем проекта; `--rmi local`
    забыт у сервиса со сборкой образа.
    """
    st = stand
    profile = st.profile()
    st.scenario(junit=st.junit(failed=failed))
    run = st.report_run(profile)
    where = st.where(f"failed={failed}", run.text()[-400:])
    assert run.green is (not failed) and not run.refusal, where
    assert_teardown(st, where, kill_first=False)
    rest = after_sub(st.compose("down")[-1]["argv"])
    assert "--rmi" in rest and rest[rest.index("--rmi") + 1] == "local", \
        f"{where}: {rest}"


def test_ac8_no_rmi_local_when_every_service_has_image(stand):
    """Все сервисы с `image:` — `down` без `--rmi local`.

    Ловит мутацию: `--rmi local` ставится всегда — снятие стенда удаляет
    образы, которые проект не собирал.
    """
    st = stand
    profile = st.profile()
    st.scenario(config_obj=st.base_config(tests_image=True))
    run = st.report_run(profile)
    where = st.where(run.text()[-400:])
    assert run.green, where
    assert_teardown(st, where, kill_first=False)
    assert "--rmi" not in after_sub(st.compose("down")[-1]["argv"]), where


def test_ac8_run_timeout_kills_then_downs(stand):
    """Зависший `run` — таймаут места, затем `kill` и `down -v --remove-orphans` того же проекта.

    Предел места — `config.ACCEPTANCE_TIMEOUT_SEC` прогона планки,
    подменённый 3 с, плюс `compose_up_down_sec` 2 с. Код `run_plank` —
    `None` (таймаут), прогон завершается быстро.

    Ловит мутацию: на таймауте зовётся только `down` (контейнер one-off
    держит сеть), `kill` после `down`, таймаут не снимает стенд вовсе.
    """
    st = stand
    st.up_down = 2
    profile = st.profile()
    st.mp.setattr(config, "ACCEPTANCE_TIMEOUT_SEC", 3)
    st.scenario(acts={"run": {"hang": True}})
    start = REAL_MONOTONIC()
    code, output = acceptance.run_plank([st.test_rel], st.tree,
                                        profile=profile,
                                        compose_task_id=st.task)
    where = st.where(f"{REAL_MONOTONIC() - start:.1f} с", output[-400:])
    assert code is None, where
    assert REAL_MONOTONIC() - start < 60, where
    assert_teardown(st, where, kill_first=True)


def test_ac8_exception_inside_run_kills_then_downs(stand):
    """Исключение внутри вызова `run` — `kill`, затем `down -v --remove-orphans` того же проекта.

    Подменённый `Popen` бросает `RuntimeError` в ожидании процесса `run`;
    исключение доходит до вызывающего либо превращается в отказ — в обоих
    случаях стенд снят.

    Ловит мутацию: снятие стенда только на штатном пути (`try/except
    TimeoutExpired` без `finally`) — после исключения `down` нет.
    """
    st = stand
    profile = st.profile()
    st.raise_in = "run"
    try:
        run = st.report_run(profile)
        text = run.text()[-400:]
    except RuntimeError as exc:
        text = str(exc)
    where = st.where(text)
    assert "run" in st.subs(), f"{where}: {st.subs()}"
    assert_teardown(st, where, kill_first=True)


def test_ac8_up_failure_refused_with_output_and_downed(stand):
    """Провал `up` — отказ прогона с выводом Compose, `run` не зовётся, затем `down` того же проекта.

    Ловит мутацию: провал `up` не проверен (прогон идёт без служб), отказ
    без вывода Compose, после провала `up` стенд не снимается (подняться
    мог частично).
    """
    st = stand
    profile = st.profile()
    noise = f"compose-up-failed-{word(st.rng)}"
    st.scenario(acts={"up": {"code": 1, "stderr": noise}})
    run = st.report_run(profile)
    where = st.where(run.text()[-400:])
    ups = st.compose("up")
    assert ups, f"{where}: up не вызван: {st.subs()}"
    rest = after_sub(ups[0]["argv"])
    assert "-d" in rest and "--wait" in rest and st.db in rest, \
        f"{where}: {rest}"
    assert not run.green and noise in run.text(), where
    assert "run" not in st.subs(), f"{where}: {st.subs()}"
    assert_teardown(st, where, kill_first=False)
    downs = [i for i, s in enumerate(st.subs()) if s == "down"]
    assert downs[-1] > st.subs().index("up"), where


def test_ac8_no_up_without_dependencies(stand):
    """Сервис без `depends_on` — `up` не зовётся, прогон идёт.

    Ловит мутацию: `up` зовётся всегда (пустой список служб поднимает весь
    проект, в том числе сам сервис тестов).
    """
    st = stand
    profile = st.profile()
    cfg = st.base_config()
    cfg["services"][st.service].pop("depends_on")
    st.scenario(config_obj=cfg)
    run = st.report_run(profile)
    where = st.where(run.text()[-400:])
    assert run.green, where
    assert "up" not in st.subs() and "run" in st.subs(), f"{where}: {st.subs()}"


def test_ac8_hanging_up_times_out_and_downs(stand):
    """Зависший `up` — отказ по таймауту за подменённый `COMPOSE_UP_TIMEOUT_SEC`, затем `down`.

    Предел места — 60 с, `COMPOSE_UP_TIMEOUT_SEC` — 1 с: прогон
    завершается быстро, не зелёный, `run` не зовётся, `down` с тем же
    именем проекта вызван.

    Ловит мутацию: `up` идёт без своего предела (ждёт предела места) или
    стенд после таймаута `up` не снимается.
    """
    st = stand
    profile = st.profile()
    st.mp.setattr(config, "COMPOSE_UP_TIMEOUT_SEC", 1)
    st.scenario(acts={"up": {"hang": True}})
    start = REAL_MONOTONIC()
    run = st.report_run(profile, timeout=60.0)
    elapsed = REAL_MONOTONIC() - start
    where = st.where(f"{elapsed:.1f} с", run.text()[-400:])
    assert not run.green and (run.timed_out or run.refusal), where
    assert elapsed < 40, where
    assert "run" not in st.subs(), f"{where}: {st.subs()}"
    assert_teardown(st, where, kill_first=False)


def test_ac8_hanging_down_bounded_and_journaled(stand):
    """Зависший `down` — прогон завершается за подменённый `COMPOSE_TEARDOWN_TIMEOUT_SEC`, исход прежний, журнал задачи называет проект.

    Запись журнала — `store.task_steps` задачи, id которой передан в
    `report_run`: действие или деталь несёт имя проекта Compose.

    Ловит мутацию: снятие стенда без предела (прогон висит), превышение
    предела снятия молча (в журнале нет имени проекта — остатки не найти),
    таймаут снятия портит зелёный исход.
    """
    st = stand
    profile = st.profile()
    st.mp.setattr(config, "COMPOSE_TEARDOWN_TIMEOUT_SEC", 1)
    st.scenario(acts={"down": {"hang": True}})
    start = REAL_MONOTONIC()
    run = st.report_run(profile, timeout=60.0)
    elapsed = REAL_MONOTONIC() - start
    where = st.where(f"{elapsed:.1f} с", run.text()[-400:])
    assert elapsed < 40, where
    assert run.green, where
    name = project_of(st.compose("down")[-1])
    steps = store.task_steps(store.db(), st.task)
    assert any(name in f"{row['action']} {row['detail']}" for row in steps), \
        f"{where}: журнал {[(r['action'], r['detail']) for r in steps]}"


def test_ac8_no_run_when_nothing_left_after_up(stand):
    """Остаток предела места после `up` не больше нуля — отказ по таймауту без `run`, затем `kill` и `down`.

    Часы пульта (`time.monotonic`/`time.time`) сдвигаются вперёд сразу после
    завершения `up`; собственные таймауты `subprocess` идут по своей ссылке
    на часы и не сдвигаются.

    Ловит мутацию: предел `run` — полный предел места, а не остаток (прогон
    идёт после исчерпания предела), или остаток ≤ 0 передан в `run` как
    «без предела».
    """
    st = stand
    profile = st.profile()
    st.shifted_clock()
    st.jump_after = "up"
    run = st.report_run(profile, timeout=60.0)
    where = st.where(run.text()[-400:])
    assert "up" in st.subs(), f"{where}: {st.subs()}"
    assert not run.green and (run.timed_out or run.refusal), where
    assert "run" not in st.subs(), f"{where}: {st.subs()}"
    assert_teardown(st, where, kill_first=True)


@pytest.mark.parametrize("small", ["up", "place"])
def test_ac8_up_limit_is_min_of_constant_and_place(stand, small):
    """Предел `up` — меньшее из `COMPOSE_UP_TIMEOUT_SEC` и остатка предела места.

    Предел наблюдается подменённым `Popen` (наибольший `timeout` ожидания
    процесса `up`). Случай `up`: константа 7 с при пределе места 500 с;
    случай `place`: константа 10000 с при пределе места 40 с (плюс
    `compose_up_down_sec` 1 с).

    Ловит мутацию: `up` получает константу без сверки с остатком места (или
    наоборот — остаток без константы).
    """
    st = stand
    st.up_down = 1
    profile = st.profile()
    if small == "up":
        st.mp.setattr(config, "COMPOSE_UP_TIMEOUT_SEC", 7)
        run = st.report_run(profile, timeout=500.0)
        bound = 7
    else:
        st.mp.setattr(config, "COMPOSE_UP_TIMEOUT_SEC", 10000)
        run = st.report_run(profile, timeout=40.0)
        bound = 41
    where = st.where(small, run.text()[-400:])
    limits = st.timeouts("up")
    assert limits and all(t is not None and 0 < t <= bound for t in limits), \
        f"{where}: пределы up {limits}"


def test_ac8_hanging_context_inspect_bounded(stand):
    """Зависший `docker context inspect` при не заданном `DOCKER_HOST` — отказ за подменённый `COMPOSE_CONFIG_TIMEOUT_SEC`.

    Ловит мутацию: `context inspect` без предела — прогон висит до предела
    места; зависание принято за «сокета нет» и стенд поднимается.
    """
    st = stand
    profile = st.profile()
    st.mp.setattr(config, "COMPOSE_CONFIG_TIMEOUT_SEC", 1)
    st.scenario(acts={"context": {"hang": True}})
    start = REAL_MONOTONIC()
    run = st.report_run(profile, timeout=60.0)
    elapsed = REAL_MONOTONIC() - start
    where = st.where(f"{elapsed:.1f} с", run.text()[-400:])
    assert "context" in st.subs(), f"{where}: {st.subs()}"
    assert run.refusal, where
    assert elapsed < 30, where
    assert not {"up", "run"} & set(st.subs()), f"{where}: {st.subs()}"


# --------------------------------------------------------------- AC-9

def test_ac9_consecutive_and_concurrent_runs_get_distinct_names(stand):
    """Последовательные прогоны одного места и одновременные прогоны двух процессов — разные имена проекта с id задачи.

    Два вызова `report_run` подряд в этом процессе; затем два дочерних
    процесса Python одновременно (каждый грузит ту же запись и зовёт
    `report_run` с тем же id). Все имена в журнале `run` — `artel-<id
    строчными>-<8 hex>`, только `[a-z0-9-]`, попарно различны.

    Ловит мутацию: `<прогон>` от счётчика процесса или от зерна, одного у
    всех процессов (имена дочерних совпадают), имя без id задачи или с id
    заглавными буквами.
    """
    st = stand
    profile = st.profile()
    first = st.report_run(profile)
    second = st.report_run(profile)
    where = st.where(first.text()[-200:], second.text()[-200:])
    child = (
        "import sys\n"
        "from pathlib import Path\n"
        "from orchestrator import acceptance, config, project_profile, targets\n"
        "config.TARGETS = Path(sys.argv[1])\n"
        "values = targets.target(sys.argv[2])[targets.PROFILE_FIELD]\n"
        "profile = project_profile.with_tools(sys.argv[2], "
        "project_profile.Profile.from_values(values))\n"
        "run = acceptance.report_run(profile, Path(sys.argv[3]), [sys.argv[4]], "
        "60.0, task_id=sys.argv[5])\n"
        "print(run.text()[-300:])\n")
    argv = [sys.executable, "-c", child, str(config.TARGETS), st.name,
            str(st.tree), st.test_rel, st.task]
    procs = [REAL_POPEN(argv, cwd=REPO_ROOT, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True,
                        start_new_session=True) for _ in range(2)]
    outputs = []
    try:
        for proc in procs:
            outputs.append(proc.communicate(timeout=120)[0])
    finally:
        for proc in procs:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
    where = st.where(where, *[o[-300:] for o in outputs])
    runs = st.compose("run")
    names = [project_of(c) for c in runs]
    assert len(names) == 4, f"{where}: имена {names}"
    assert len({c["pid"] for c in runs}) == 4, where
    assert all(name_pattern_ok(n, st.task) for n in names), f"{where}: {names}"
    assert len(set(names)) == 4, f"{where}: {names}"


def test_ac9_places_pass_task_id_to_project_name(stand):
    """Места `report_run`, `run_repeat`, `run_full_suite`, `run_plank` (оба вызова) несут id задачи в имени проекта.

    `run_plank` долгоживущего файла с `compose_task_id`: каталога планки
    задачи в рабочей копии нет и не появляется, прогон идёт. `run_plank`
    планки с `task_id` (без `compose_task_id`): планка лежит в каталоге
    задачи рабочей копии. `run_repeat` и `run_full_suite` — с `task_id`.
    Каждый вызов даёт `run` с именем `artel-<id строчными>-<8 hex>`.

    Ловит мутацию: место не передаёт id до `report_run` (отказ «нет id»),
    `run_plank` берёт id имени только из `task_id` (долгоживущий файл
    получает раскладку и падает на отсутствии каталога планки) или только
    из `compose_task_id` (планка задачи отказана).
    """
    st = stand
    profile = st.profile()
    plank_dir = st.tree / "tasks" / st.task / "acceptance_tests"
    outcomes = {}

    def names_after(label, call):
        st.scenario()
        outcomes[label] = call()
        return [project_of(c) for c in st.compose("run")]

    got = {
        "report_run": names_after("report_run", lambda: st.report_run(profile)),
        "run_repeat": names_after("run_repeat", lambda: acceptance.run_repeat(
            [st.test_rel], st.tree, command=profile, task_id=st.task)),
        "run_full_suite": names_after(
            "run_full_suite", lambda: acceptance.run_full_suite(
                st.tree, command=profile, task_id=st.task)),
        "run_plank долгоживущего": names_after(
            "run_plank долгоживущего", lambda: acceptance.run_plank(
                [st.test_rel], st.tree, profile=profile,
                compose_task_id=st.task)),
    }
    assert not plank_dir.exists(), st.where("каталог планки создан")
    plank_dir.mkdir(parents=True)
    (plank_dir / f"test_ac1_{word(st.rng)}.py").write_text(PROBE_TEST,
                                                           encoding="utf-8")
    rel = os.path.relpath(plank_dir, st.tree)
    got["run_plank планки"] = names_after(
        "run_plank планки", lambda: acceptance.run_plank(
            [rel], st.tree, profile=profile, task_id=st.task))
    for place, names in got.items():
        where = st.where(place, repr(outcomes[place])[-400:])
        assert names and all(name_pattern_ok(n, st.task) for n in names), \
            f"{where}: имена {names}"


def test_ac9_report_run_without_task_id_refused_without_docker(stand):
    """`report_run` с профилем `compose` без `task_id` — отказ запуска с текстом, `docker` не вызван.

    Ловит мутацию: без id имя проекта собирается запасной формой (без id)
    или `docker` зовётся до проверки id.
    """
    st = stand
    profile = st.profile()
    run = st.report_run(profile, task_id=None)
    where = st.where(run.text()[-300:])
    assert run.refusal, where
    assert st.calls() == [], f"{where}: {st.subs()}"


def test_ac9_pytest_own_report_run_without_task_id_unchanged(stand):
    """Профиль `pytest-own` с отчётом зовётся `report_run` без `task_id` прежним образом.

    Настоящий pytest пульта в `workdir` учебного проекта: зелёный итог,
    отказа нет, `docker` не вызван.

    Ловит мутацию: `task_id` сделан обязательным для всех профилей
    (`TypeError` или отказ у `pytest-own`).
    """
    st = stand
    st.mp.setenv("PATH", os.pathsep.join([os.path.dirname(sys.executable),
                                          st.caller_path]))
    own = {"runner": targets.PROFILE_RUNNER_OWN,
           "command": ["python3", "-m", "pytest"],
           "workdir": st.app, "long_lived_dir": f"{st.app}/tests",
           "long_lived_name": "test_<id>_<name>.py", "report": "junit-xml"}
    st.write_record(own)
    values = targets.target(st.name)[targets.PROFILE_FIELD]
    profile = project_profile.with_tools(
        st.name, project_profile.Profile.from_values(values))
    run = acceptance.report_run(profile, st.tree, [st.test_rel], 120.0)
    where = st.where(run.text()[-400:])
    assert run.green and not run.refusal, where
    assert st.calls() == [], where


# --------------------------------------------------------------- AC-10

def test_ac10_two_sided_compose_goes_report_branch(stand):
    """Двусторонний прогон `compose` — веткой отчёта: в argv `run` нет плагина пульта, в окружении нет `PYTHONPATH`.

    `two_sided.run` по методу учебного теста на базе и голове ветки
    песочницы (`profile` — `compose`, `task_id` — id задачи). Каждый вызов
    `run` обеих сторон: `two_sided.PLUGIN_MODULE` нет в argv, `PYTHONPATH`
    нет в окружении, имя проекта несёт id задачи.

    Ловит мутацию: `compose` пошёл веткой пульта (`place_command` с `-p
    <плагин>` и `PYTHONPATH` каталога плагина) или сторона не передаёт id.
    """
    st = stand
    profile = st.profile()
    branch = f"probe-{word(st.rng)}"
    st.sandbox.git("branch", branch)
    base_sha = st.sandbox.git("rev-parse", "HEAD").strip()
    method = two_sided.Method(st.test_rel, st.test_rel, "ProbeTest::test_ok",
                              PROBE_TEST, PROBE_TEST)
    outcome = two_sided.run(st.tree, branch, base_sha, [method],
                            profile=profile, task_id=st.task)
    where = st.where(repr(outcome)[-400:])
    runs = st.compose("run")
    assert len(runs) >= 2, f"{where}: {st.subs()}"
    for call in runs:
        assert two_sided.PLUGIN_MODULE not in " ".join(call["argv"]), where
        assert "PYTHONPATH" not in call["env"], where
        assert name_pattern_ok(project_of(call), st.task), where


def test_ac10_outcome_bounds_only_for_compose_component(stand):
    """Гейт исходов берёт компонент `compose` и не берёт `test_profile` `compose`.

    `in_outcome_bounds`: профиль компонента записи `components:` с
    `compose` — в границе; тот же набор полей в `test_profile` — вне.

    Ловит мутацию: граница исходов расширена на `test_profile` `compose`
    (или компонент `compose` выпал из неё, не будучи «с отчётом»).
    """
    st = stand
    comp = st.profile(form="components")
    flat = st.profile(form="test_profile")
    where = st.where()
    assert gate_acceptance.in_outcome_bounds(comp) is True, where
    assert gate_acceptance.in_outcome_bounds(flat) is False, where


# --------------------------------------------------------------- AC-11

@pytest.mark.parametrize("variant", ["bare", "set"])
def test_ac11_docker_env_exact_outside_role(stand, variant):
    """Окружение каждого вызова `docker` вне процесса роли — ровно `PATH`, `DOCKER_CONFIG`, `TMPDIR` и заданные `DOCKER_HOST`/`LANG`/`LC_ALL`.

    В окружении теста — `HOME` песочницы и переменная-метка; `ARTEL_ROLE`
    снят. Случай `bare`: `DOCKER_HOST`, `DOCKER_CONFIG`, `LC_ALL` не заданы,
    `LANG` задан; случай `set`: все заданы (`DOCKER_HOST` — сокет
    песочницы). У каждого вызова (`config`, `up`, `run`, `down` и прочих):
    набор имён ровно ожидаемый, `HOME` и метки нет; `PATH` — каталоги
    `machine.path`, каталог подменённого `docker`, затем системный хвост
    раннера (каталоги PATH прогона `pytest-own` без PATH вызывающего) без
    повторов — без каталогов PATH вызывающего; `DOCKER_CONFIG` — заданный
    либо `<HOME>/.docker`.

    `LC_CTYPE`, выставленный интерпретатором подменённого `docker` при
    локали «C» (PEP 538; в окружении теста `LC_CTYPE` снят), не считается.

    Ловит мутацию: окружение — копия `os.environ` пульта (метка и `HOME`
    уходят в `docker`), PATH вызывающего целиком в PATH вызова, `machine.path`
    не вошёл или стоит после каталога `docker`, `DOCKER_CONFIG` без значения
    не подставлен, правило применено к `run`, но не к `config`.
    """
    st = stand
    machine = [f"/opt/{word(st.rng)}/bin", f"/opt/{word(st.rng)}/bin"]
    profile = st.profile(machine_path=":".join(machine))
    st.mp.setenv("LANG", f"ru_RU.{word(st.rng)}")
    expected = {"PATH", "DOCKER_CONFIG", "TMPDIR", "LANG"}
    if variant == "set":
        st.mp.setenv("LC_ALL", f"C.{word(st.rng)}")
        st.mp.setenv("DOCKER_HOST", f"unix://{st.socket_path}")
        st.mp.setenv("DOCKER_CONFIG", str(st.home / f"dc_{word(st.rng)}"))
        expected |= {"LC_ALL", "DOCKER_HOST"}
    else:
        st.mp.delenv("LC_ALL", raising=False)
    head = st.home / f"cmd_{word(st.rng)}" / "run"
    own = project_profile.Profile(
        command=(str(head),), long_lived_dir="tests",
        long_lived_name="test_<id>_<name>.py", weakening_scope=(),
        mutation_claim_scope=(), runner=targets.PROFILE_RUNNER_OWN)
    with pytest.MonkeyPatch.context() as local:
        local.setenv("PATH", "")
        with acceptance.place_env(own) as own_env:
            system = own_env["PATH"].split(os.pathsep)[1:]
    want_path = list(dict.fromkeys([*machine, str(st.bindir), *system]))
    run = st.report_run(profile)
    where = st.where(variant, run.text()[-300:])
    calls = st.calls()
    assert "run" in st.subs() and "config" in st.subs(), f"{where}: {st.subs()}"
    for call in calls:
        env = {k: v for k, v in call["env"].items()
               if not k.startswith("__CF") and k != "__PYVENV_LAUNCHER__"
               and not (k == "LC_CTYPE" and v in PY_COERCED_LOCALES)}
        here = f"{where}: вызов {call['sub'] or call['kind']}"
        assert set(env) == expected, f"{here}: {sorted(env)}"
        assert env["PATH"].split(os.pathsep) == want_path, \
            f"{here}: PATH {env['PATH']} != {want_path}"
        assert str(st.noise) not in env["PATH"], here
        assert env["DOCKER_CONFIG"] == (
            os.environ["DOCKER_CONFIG"] if variant == "set"
            else str(st.home / ".docker")), here
        for name in expected - {"PATH", "DOCKER_CONFIG"}:
            if name in os.environ:
                assert env[name] == os.environ[name], f"{here}: {name}"


# --------------------------------------------------------------- AC-12

@pytest.mark.parametrize("sign", ["artel_role", "role_home", "role_docker_env"])
def test_ac12_role_process_refuses_before_any_docker_call(stand, sign):
    """В процессе роли прогон `compose` — именованный отказ до любого вызова `docker`, шаблон не скопирован.

    Признак роли: `ARTEL_ROLE` задан; отдельно — `ARTEL_ROLE` снят, `HOME` —
    дом роли (`config.ROLE_HOME` песочницы, как у фонового `suite-run`);
    отдельно — `ARTEL_ROLE` и заданные `DOCKER_CONFIG`/`DOCKER_HOST`. Места
    `report_run` и `run_plank`: текст отказа — фраза требования, журнал
    вызовов `docker` пуст, `compose_env_file` не создан. Контроль: без
    признака роли тот же прогон вызывает `docker`.

    Ловит мутацию: признак роли — только `ARTEL_ROLE` (дом роли без маркера
    проходит), проверка после копии шаблона или после `context inspect`/
    `config`, заданный `DOCKER_HOST` открывает Docker роли.
    """
    st = stand
    profile = st.profile()
    if sign == "role_home":
        st.mp.setenv("HOME", str(config.ROLE_HOME))
    else:
        st.mp.setenv(config.ARTEL_ROLE_ENV, "developer")
    if sign == "role_docker_env":
        st.mp.setenv("DOCKER_CONFIG", str(st.home / ".docker"))
        st.mp.setenv("DOCKER_HOST", f"unix://{st.socket_path}")
    run = st.report_run(profile)
    code, output = acceptance.run_plank([st.test_rel], st.tree,
                                        profile=profile,
                                        compose_task_id=st.task)
    where = st.where(sign, run.text()[-300:], output[-300:])
    assert ROLE_REFUSAL in run.refusal, where
    assert ROLE_REFUSAL in output and code != 0, where
    assert st.calls() == [], f"{where}: {st.subs()}"
    assert not (st.tree / st.env_rel).exists(), where
    st.mp.delenv(config.ARTEL_ROLE_ENV, raising=False)
    st.mp.delenv("DOCKER_HOST", raising=False)
    st.mp.setenv("HOME", str(st.home))
    run = st.report_run(profile)
    assert "run" in st.subs(), st.where("контроль вне роли", run.text()[-300:])


# --------------------------------------------------------------- AC-13

def exclude_lines(st) -> list:
    path = st.tree / ".git" / "info" / "exclude"
    return [line.strip().strip("/") for line in
            path.read_text(encoding="utf-8").splitlines()] \
        if path.exists() else []


def test_ac13_report_removed_foreign_report_kept_and_excluded(stand):
    """После прогона его отчёта нет, пустой `.artel-report` убран; отчёт другого прогона и каталог с ним остаются; оба пути в `info/exclude`.

    Первый прогон в чистом дереве: после него ни файла отчёта, ни каталога
    `.artel-report`. Затем в каталоге лежит отчёт другого прогона (8 hex):
    после второго прогона он и каталог на месте, своего отчёта нет. В
    `info/exclude` дерева — `.artel-report` и `compose_env_file`.

    Ловит мутацию: отчёт не удаляется; удаляется весь каталог
    `.artel-report` (с отчётом параллельного прогона); исключения не
    записаны — чекпоинт закоммитил бы отчёт и файл окружения.
    """
    st = stand
    profile = st.profile()
    report_dir = st.tree / st.left / ".artel-report"
    run = st.report_run(profile)
    where = st.where(run.text()[-300:])
    assert run.green, where
    assert not report_dir.exists(), f"{where}: {list(report_dir.iterdir())}"
    report_dir.mkdir()
    foreign = report_dir / f"{st.rng.randrange(1 << 32):08x}.xml"
    foreign.write_text(st.junit(), encoding="utf-8")
    st.scenario()
    run = st.report_run(profile)
    where = st.where(run.text()[-300:])
    assert run.green, where
    assert sorted(p.name for p in report_dir.iterdir()) == [foreign.name], where
    lines = exclude_lines(st)
    assert any(line.endswith(".artel-report") for line in lines), \
        f"{where}: {lines}"
    env_name = os.path.basename(st.env_rel)
    assert any(line == st.env_rel or line.endswith(env_name)
               for line in lines), f"{where}: {lines}"


def test_ac13_tracked_env_file_refused_before_copy(stand):
    """`compose_env_file`, отслеживаемый git, — отказ с именем файла, шаблон не скопирован, `docker` не вызван.

    Ловит мутацию: проверки `git ls-files` нет — пульт перезаписывает
    закоммиченный файл проекта шаблоном; проверка после копии.
    """
    st = stand
    tracked = f"TRACKED={word(st.rng)}\n"
    (st.tree / st.env_rel).write_text(tracked, encoding="utf-8")
    st.sandbox.git("add", "-f", st.env_rel)
    st.sandbox.git("commit", "-q", "-m", "файл окружения в git")
    profile = st.profile()
    run = st.report_run(profile)
    where = st.where(run.text()[-300:])
    assert run.refusal and st.env_rel in run.refusal, where
    assert (st.tree / st.env_rel).read_text(encoding="utf-8") == tracked, where
    assert st.calls() == [], f"{where}: {st.subs()}"


def test_ac13_missing_template_refused_without_docker(stand):
    """Шаблона `compose_env_template` нет в дереве прогона — отказ с именем файла, `docker` не вызван.

    Ловит мутацию: отсутствие шаблона не проверено — прогон идёт со
    старым файлом окружения или `cp` падает исключением.
    """
    st = stand
    (st.tree / st.template_rel).unlink()
    profile = st.profile()
    run = st.report_run(profile)
    where = st.where(run.text()[-300:])
    assert run.refusal and st.template_rel in run.refusal, where
    assert st.calls() == [], f"{where}: {st.subs()}"


def test_ac13_tracked_env_file_with_remote_host_not_copied(stand):
    """Порядок проверок: `DOCKER_HOST=tcp://…` при отслеживаемом файле окружения — отказ `DOCKER_HOST`, файл не тронут.

    Ловит мутацию: копия шаблона идёт до проверки `DOCKER_HOST` —
    отслеживаемый файл перезаписан.
    """
    st = stand
    tracked = f"TRACKED={word(st.rng)}\n"
    (st.tree / st.env_rel).write_text(tracked, encoding="utf-8")
    st.sandbox.git("add", "-f", st.env_rel)
    st.sandbox.git("commit", "-q", "-m", "файл окружения в git")
    profile = st.profile()
    st.mp.setenv("DOCKER_HOST", "tcp://10.0.0.1:2375")
    run = st.report_run(profile)
    where = st.where(run.text()[-300:])
    assert run.refusal and "DOCKER_HOST" in run.refusal, where
    assert (st.tree / st.env_rel).read_text(encoding="utf-8") == tracked, where


# --------------------------------------------------------------- AC-14

@pytest.mark.parametrize("with_field", [True, False])
def test_ac14_place_limit_extended_by_up_down(stand, with_field):
    """Предел прогона места `compose` больше предела того же места на `compose_up_down_sec`, без поля — на `config.COMPOSE_UP_DOWN_SEC`.

    Место — прогон планки (`run_plank`), чей предел —
    `config.ACCEPTANCE_TIMEOUT_SEC` (подменён случайным L). Предел ожидания
    процесса `run` (наблюдается подменённым `Popen`) лежит в (L, L + U], где
    U — поле записи либо подменённая константа, и не меньше L + U − 30.

    Ловит мутацию: слагаемое не прибавлено (предел `run` ≤ L), прибавлена
    константа при заданном поле (или поле при его отсутствии), предел
    `run` — без вычета прошедшего времени (больше L + U).
    """
    st = stand
    limit = st.rng.randrange(400, 900)
    extra = st.rng.randrange(100, 400)
    if with_field:
        st.up_down = extra
        st.mp.setattr(config, "COMPOSE_UP_DOWN_SEC",
                      extra + st.rng.randrange(500, 900))
    else:
        st.mp.setattr(config, "COMPOSE_UP_DOWN_SEC", extra)
    profile = st.profile()
    st.mp.setattr(config, "ACCEPTANCE_TIMEOUT_SEC", limit)
    code, output = acceptance.run_plank([st.test_rel], st.tree,
                                        profile=profile,
                                        compose_task_id=st.task)
    where = st.where(f"L={limit}, U={extra}", output[-300:])
    limits = st.timeouts("run")
    assert limits, f"{where}: {st.subs()}"
    got = limits[-1]
    assert got is not None and limit + extra - 30 <= got <= limit + extra, \
        f"{where}: предел run {got}"


# --------------------------------------------------------------- AC-15

def tree_sha(st) -> str:
    return st.sandbox.git("rev-parse", "HEAD^{tree}").strip()


@pytest.mark.parametrize("field", ["compose_file", "compose_service",
                                   "compose_env_file", "compose_env_template",
                                   "compose_mount", "command"])
def test_ac15_key_changes_with_compose_field(stand, field):
    """Смена поля `compose_*` или `command` записи меняет ключ итога `report_suite_result_key`.

    Ключ базы (`base=True`, без файлов рабочей копии) одного дерева для
    верной записи и для той же записи с новым значением поля.

    Ловит мутацию: поле не вошло в данные ключа — итог полного набора,
    посчитанный при прежнем сервисе/монтировании/команде, переиспользуется
    после их смены.
    """
    st = stand
    tree = tree_sha(st)
    before = acceptance.report_suite_result_key(tree, st.profile(), True)
    w = word(st.rng)
    new = {"compose_file": f"{st.deploy}/other_{w}.yaml",
           "compose_service": f"svc_{w}",
           "compose_env_file": f"{st.deploy}/.env.{w}",
           "compose_env_template": f"{st.deploy}/env.{w}.template",
           "compose_mount": f"{st.left}:/other_{w}",
           "command": ["pytest", f"-k{w}"]}[field]
    after = acceptance.report_suite_result_key(
        tree, st.profile(**{field: new}), True)
    where = st.where(field, before, after)
    assert before and after, where
    assert before != after, where


def altered(value):
    """Другое значение того же вида; None — вид не меняется простым приёмом."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)):
        return value + 1
    if isinstance(value, str):
        return value + " "
    if isinstance(value, tuple):
        return value + ("x",)
    if isinstance(value, list):
        return value + ["x"]
    if isinstance(value, frozenset):
        return value | {"x"}
    if isinstance(value, dict):
        return {**value, "x": "x"}
    return None


def test_ac15_key_changes_with_override_rule_constant(stand):
    """Правка константы правила перекрытия модуля `acceptance` меняет ключ итога профиля `compose`.

    Константа правила SPEC не названа по имени: перебираются публичные
    константы `acceptance` с `COMPOSE` в имени (верхний регистр), каждая
    подменяется другим значением того же вида; ключ меняется хотя бы от
    одной из них.

    Ловит мутацию: правило перекрытия не представлено в ключе (константы
    нет или ключ её не читает) — итог, посчитанный при прежнем правиле,
    переиспользуется после его правки.
    """
    st = stand
    tree = tree_sha(st)
    profile = st.profile()
    before = acceptance.report_suite_result_key(tree, profile, True)
    names = [n for n in dir(acceptance)
             if "COMPOSE" in n and n.isupper() and not n.startswith("_")]
    where = st.where(names)
    assert before and names, where
    changed = []
    for name in names:
        new = altered(getattr(acceptance, name))
        if new is None:
            continue
        with pytest.MonkeyPatch.context() as local:
            local.setattr(acceptance, name, new)
            after = acceptance.report_suite_result_key(tree, profile, True)
        if after != before:
            changed.append(name)
    assert changed, f"{where}: ни одна константа не меняет ключ"
