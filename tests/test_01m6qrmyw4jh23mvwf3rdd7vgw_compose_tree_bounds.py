"""Раннер `compose`: файлы машины — только внутри дерева прогона, привилегии стенда — отказ.

Группа: долгоживущий

Песочница `stand` — по образцу файла ядра раннера `compose`: настоящий git
(`real_git`), дерево прогона — корень песочницы (`sandbox.root`) с учебным
проектом (тест в `workdir`, Compose-файл, шаблон файла окружения), запись
проекта — локальный слой (`targets.local_path()`), профиль — тот же путь, что
`project_profile.decide`. Программа `docker` подменена исполнителем на Python
в каталоге PATH теста (без настоящего Docker): каждый вызов дописывает строку
журнала и отвечает по файлу сценария; ответ `config --format json` —
единственный канал, через который тест подаёт конфигурацию; функции модуля
пульта не подменяются. `@TREE@` в ответе `config` — каталог над
`--project-directory`, то есть дерево прогона, `@PROJECT@` — имя проекта.
Пути «вне дерева» подаются строкой без создания (сосед `<дерево>2`);
каталоги и ссылки тест создаёт только в своём временном каталоге.

Имена сервисов, томов, секретов, каталогов, id задачи — случайные на каждом
прогоне; зерно печатается и входит в текст провала.

Красен до реализации: `_compose_config_refusal` проверяет у источников bind и `file` секретов только сокет Docker — путь вне дерева, `build.context`, `additional_contexts` и привилегии проходят, элемент неверной формы пропускается или поднимает `AttributeError`, `COMPOSE_OVERRIDE_RULE` — прежняя строка версии «1: ».
"""
import json
import os
import random
import re
import shutil
import socket
import string
import sys
import tempfile
from pathlib import Path

import pytest

from orchestrator import acceptance, config, project_profile, store, targets

LETTERS = string.ascii_lowercase
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
VALUED = ("--project-name", "-p", "--project-directory", "-f", "--file",
          "--env-file", "--profile", "--ansi", "--progress", "--parallel")
SOCKET_BIND_TEXT = "bind-монтирование сокета Docker или его каталога"
SOCKET_FILE_TEXT = "file на сокет Docker или его каталог"
OLD_RULE = (
    "1: services -ports +labels; networks +internal +labels, default "
    "добавляется; отказ: network_mode, volumes_from, container_name, сеть "
    "external, чужое name сети и тома, driver_opts тома local, сокет Docker "
    "в bind, secrets.file, configs.file")

FAKE_DOCKER = r'''#!@PYTHON@
import json
import os
import sys

STATE = @STATE@
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
    record = {"argv": args, "kind": kind, "sub": sub}
    with open(os.path.join(STATE, "calls.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    project = option(opts, "--project-name", "-p")
    tree = os.path.dirname(option(opts, "--project-directory").rstrip("/"))
    if kind == "compose" and sub == "config":
        sys.stdout.write(json.dumps(sc["config"]).replace("@PROJECT@", project)
                         .replace("@TREE@", tree))
    elif kind == "compose" and sub == "run":
        target = junit_path(rest)
        right = sc["right"].rstrip("/") + "/"
        if target.startswith(right):
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
    sys.exit(0)


main()
'''

PROBE_TEST = '''import unittest


class ProbeTest(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(True)
'''

JUNIT = ('<?xml version="1.0" encoding="utf-8"?><testsuites>'
         '<testsuite name="pytest" errors="0" failures="0" '
         'skipped="0" tests="1" time="0.01"><testcase classname="{classname}" '
         'name="test_ok" time="0.001"></testcase></testsuite>'
         '</testsuites>')


def word(rng, k: int = 6) -> str:
    return "".join(rng.choices(LETTERS, k=k))


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
        self.service = f"svc_{word(rng)}"
        self.db = f"db_{word(rng)}"
        self.task = task_id(rng)
        self.module = f"test_probe_{word(rng)}"
        self.test_rel = f"{self.app}/tests/{self.module}.py"
        self.compose_rel = f"{self.deploy}/compose.yaml"
        self.env_rel = f"{self.deploy}/.env.{word(rng)}"
        self.template_rel = f"{self.deploy}/env.{word(rng)}.template"

    def build_tree(self) -> None:
        (self.tree / self.app / "tests").mkdir(parents=True)
        (self.tree / self.test_rel).write_text(PROBE_TEST, encoding="utf-8")
        (self.tree / self.deploy).mkdir()
        (self.tree / self.compose_rel).write_text(
            f"services:\n  {self.service}:\n    build: .\n", encoding="utf-8")
        (self.tree / self.template_rel).write_text(
            f"PROBE_{word(self.rng).upper()}={word(self.rng)}\n",
            encoding="utf-8")
        self.sandbox.git("add", "-A")
        self.sandbox.git("commit", "-q", "-m", "учебный проект compose")

    def profile(self):
        fields = {"runner": "compose", "workdir": self.app,
                  "long_lived_dir": f"{self.app}/tests",
                  "long_lived_name": "test_<id>_<name>.py",
                  "report": "junit-xml", "compose_file": self.compose_rel,
                  "compose_service": self.service,
                  "compose_env_file": self.env_rel,
                  "compose_env_template": self.template_rel,
                  "compose_mount": f"{self.left}:{self.right}"}
        lld = fields["long_lived_dir"]
        lines = [f"  {self.name}:", "    description:", "      base: main",
                 "      test_profile:",
                 *[f'        {k}: "{v}"' for k, v in fields.items()],
                 "    policy:", "      no_paths: []",
                 "      project_skills: []", "      merge_gate: operator",
                 f"      weakening_scope: [{lld}/**/*.py]",
                 f"      mutation_claim_scope: [{lld}/test_*.py]",
                 "    machine:", "      forge: github",
                 f"      url: https://localhost/team/{self.name}",
                 f"      token_slot: {self.name}-token"]
        path = targets.local_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("targets:\n" + "\n".join(lines) + "\n",
                        encoding="utf-8")
        values = targets.target(self.name)[targets.PROFILE_FIELD]
        return project_profile.with_tools(
            self.name, project_profile.Profile.from_values(values))

    def own_tmp(self) -> Path:
        """Временный каталог теста вне дерева прогона (уборка — песочницей)."""
        base = Path(tempfile.mkdtemp(prefix="artel-compose-tb-")).resolve()
        self.sandbox.addCleanup(shutil.rmtree, base, True)
        return base

    def install_docker(self) -> None:
        base = self.own_tmp()
        self.state = base / "state"
        self.state.mkdir()
        bindir = base / "bin"
        bindir.mkdir()
        home = base / "home"
        home.mkdir()
        docker = bindir / "docker"
        docker.write_text(
            FAKE_DOCKER.replace("@PYTHON@", sys.executable)
            .replace("@STATE@", repr(str(self.state)))
            .replace("@VALUED@", repr(VALUED)), encoding="utf-8")
        docker.chmod(0o755)
        self.mp.setenv("PATH", os.pathsep.join(
            [str(bindir),
             *[d for d in os.environ.get("PATH", "").split(os.pathsep) if d]]))
        self.mp.setenv("HOME", str(home))
        for name in (config.ARTEL_ROLE_ENV, "DOCKER_HOST", "DOCKER_CONFIG",
                     "CI", "LC_CTYPE"):
            self.mp.delenv(name, raising=False)
        sock_dir = Path(tempfile.mkdtemp(prefix="ds", dir="/tmp")).resolve()
        self.sandbox.addCleanup(shutil.rmtree, sock_dir, True)
        self.socket_path = sock_dir / "docker.sock"
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(str(self.socket_path))
        self.sandbox.addCleanup(self.sock.close)
        self.scenario(self.base_config())

    def base_config(self) -> dict:
        tests = {"depends_on": {self.db: {"condition": "service_started",
                                          "required": True}},
                 "networks": {"default": None},
                 "volumes": [{"type": "bind",
                              "source": f"@TREE@/{self.left}",
                              "target": self.right}],
                 "working_dir": self.right,
                 "build": {"context": f"@TREE@/{self.deploy}",
                           "dockerfile": "Dockerfile"}}
        return {"name": "@PROJECT@",
                "services": {
                    self.service: tests,
                    self.db: {"image": "postgres:16-alpine",
                              "networks": {"default": None}}},
                "networks": {"default": {"name": "@PROJECT@_default"}}}

    def scenario(self, config_obj: dict) -> None:
        rel = os.path.relpath(self.test_rel, self.app)
        data = {"config": config_obj, "left": self.left, "right": self.right,
                "junit": JUNIT.format(classname=rel[:-3].replace("/", "."))}
        (self.state / "scenario.json").write_text(json.dumps(data),
                                                  encoding="utf-8")
        calls = self.state / "calls.jsonl"
        if calls.exists():
            calls.unlink()

    def subs(self) -> list:
        path = self.state / "calls.jsonl"
        if not path.exists():
            return []
        calls = [json.loads(line) for line in
                 path.read_text(encoding="utf-8").splitlines() if line]
        return [c["sub"] if c["kind"] == "compose" else c["kind"]
                for c in calls]

    def run(self, cfg: dict, tree=None):
        """Прогон места с ответом `config` = `cfg`; дерево — `tree` или своё."""
        profile = self.profile()
        self.scenario(cfg)
        return acceptance.report_run(profile, Path(tree or self.tree),
                                     [self.test_rel], 60.0, task_id=self.task)

    def outside(self) -> str:
        """Путь соседа дерева `<дерево>2/<имя>` — строкой, без создания."""
        return f"{self.tree}2/{word(self.rng)}"

    def where(self, *parts) -> str:
        return ", ".join([*map(str, parts), f"зерно {self.seed}"])


@pytest.fixture
def stand(real_git, monkeypatch):
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    st = Stand(real_git, monkeypatch, random.Random(seed), seed)
    st.build_tree()
    st.install_docker()
    store.insert_task(store.db(), st.task, "Задача compose", "in_dev",
                      f"task/{st.task.lower()}-compose", st.name, 25.0)
    yield st


def check_refused(st, run, where, *names) -> None:
    """Отказ запуска: текст называет каждое из `names`, `config` был, `up`/`run` — нет."""
    assert run.refusal, f"{where}: отказа нет: {st.subs()} {run.text()[-400:]}"
    for name in names:
        assert name in run.refusal, f"{where}: отказ не называет {name!r}: {run.refusal}"
    assert "config" in st.subs(), f"{where}: config не вызван: {st.subs()}"
    assert not {"up", "run"} & set(st.subs()), f"{where}: {st.subs()}"


def check_passed(st, run, where) -> None:
    """Отказа нет: `config`, `up` и `run` зовутся."""
    assert not run.refusal, f"{where}: отказ {run.refusal}"
    subs = st.subs()
    assert {"config", "up", "run"} <= set(subs), f"{where}: {subs}"


def tree_value(st, value: str, tree=None) -> str:
    """Значение ответа `config` после подстановки `@TREE@` подменённым `docker`."""
    return value.replace("@TREE@", str(tree or st.tree))


# --------------------------------------------------------------- AC-1

@pytest.mark.parametrize("form", ["long", "short"])
def test_ac1_bind_outside_tree_refused(stand, form):
    """Bind-монтирование сервиса с источником вне дерева — отказ с именем сервиса и путём.

    Источник — сосед дерева `<дерево>2/<имя>` (строкой, без создания):
    длинная форма `{type: bind, source, target}` и короткая строка
    `"<путь>:/y"` — отдельными случаями. В журнале подменённого `docker` нет
    `up` и `run`.

    Ловит мутацию: проверка дерева не добавлена (путь машины вне дерева
    проходит, стенд поднимается — в журнале появляются `up` и `run`) или
    проверяется только длинная форма (короткая строка проходит).
    """
    st = stand
    path = st.outside()
    cfg = st.base_config()
    volume = ({"type": "bind", "source": path, "target": "/y"}
              if form == "long" else f"{path}:/y")
    cfg["services"][st.service]["volumes"].append(volume)
    run = st.run(cfg)
    check_refused(st, run, st.where(form, path), st.service, path)


# --------------------------------------------------------------- AC-2

@pytest.mark.parametrize("section", ["secrets", "configs"])
def test_ac2_secret_config_file_outside_tree_refused(stand, section):
    """`file` секрета или конфигурации вне дерева — отказ с именем объекта, без `up`/`run`.

    Раздел `secrets`/`configs` ответа `config` несёт объект со случайным
    именем и `file: <дерево>2/<имя>`; сервис тестов ссылается на него.

    Ловит мутацию: `file` секретов/конфигураций проверяется только на сокет
    Docker (путь вне дерева проходит — `up` и `run` в журнале), либо
    проверяется лишь один из двух разделов.
    """
    st = stand
    other = f"x_{word(st.rng)}"
    path = st.outside()
    cfg = st.base_config()
    cfg[section] = {other: {"name": f"@PROJECT@_{other}", "file": path}}
    cfg["services"][st.service][section] = [{"source": other}]
    run = st.run(cfg)
    check_refused(st, run, st.where(section, path), other)


# --------------------------------------------------------------- AC-3

# Адрес https-схемы — на localhost (инвариант 35: сетевые адреса в tests/
# только на localhost); значение — данные ответа `config`, сеть не трогается.
BUILD_CONTEXT_CASES = ["outside", "https://localhost/r.git", "git@h:r.git",
                       "h/r.git#main", "@TREE@/r.git#main"]
ADDITIONAL_CASES = ["outside", "oci-outside", "docker-image://alpine"]


@pytest.mark.parametrize("value", BUILD_CONTEXT_CASES)
def test_ac3_build_context_outside_or_git_refused(stand, value):
    """`build.context` вне дерева или адрес git — отказ с сервисом, полем и значением.

    Случаи: сосед дерева, `https://localhost/r.git`,
    `git@h:r.git`, `h/r.git#main` и
    абсолютный путь внутри дерева `<дерево>/r.git#main` (его `realpath` лежит
    в дереве — отказ только по виду адреса git).

    Ловит мутацию: `build.context` не проверяется (стенд строится из пути
    машины или удалённого репозитория — `up`/`run` в журнале); адрес git
    ловится только правилом «закрыто по умолчанию» для неабсолютного пути —
    тогда `<дерево>/r.git#main` проходит.
    """
    st = stand
    raw = st.outside() if value == "outside" else value
    cfg = st.base_config()
    cfg["services"][st.service]["build"]["context"] = raw
    run = st.run(cfg)
    check_refused(st, run, st.where(value), st.service, "build.context",
                  tree_value(st, raw))


@pytest.mark.parametrize("value", ADDITIONAL_CASES)
def test_ac3_additional_contexts_refused(stand, value):
    """`build.additional_contexts` — путь вне дерева, `oci-layout://` вне дерева, `docker-image://` — отказ.

    Значение — словарь `{<имя>: <значение>}`. Текст называет сервис, поле
    `build.additional_contexts` и значение (для `oci-layout://` — хотя бы
    путь после схемы).

    Ловит мутацию: `additional_contexts` не проверяются вовсе; `oci-layout://`
    пропускается без сверки пути; схема `docker-image://` пропускается как
    «не путь» (образ из реестра в контексте сборки) — в журнале `up`/`run`.
    """
    st = stand
    path = st.outside()
    raw = {"outside": path, "oci-outside": f"oci-layout://{path}"}.get(value, value)
    named = path if value != "docker-image://alpine" else raw
    cfg = st.base_config()
    cfg["services"][st.service]["build"]["additional_contexts"] = {
        f"c{word(st.rng)}": raw}
    run = st.run(cfg)
    check_refused(st, run, st.where(value), st.service,
                  "build.additional_contexts", named)


# --------------------------------------------------------------- AC-4

@pytest.mark.parametrize("case, refused", [("sibling", True),
                                           ("dotdot", True),
                                           ("link_out", True),
                                           ("link_in", False)])
def test_ac4_component_boundary_and_links(stand, case, refused):
    """Граница компонента и ссылки (вариант 2: дерево — `sandbox.root`).

    (а) строка `<root>2/x` без создания — отказ; (б)
    `<root>/sub/../../<имя root>2` — отказ; (в) висячая ссылка `<root>/link`
    на `<root>2` — отказ; (г) ссылка `<root>/inner` на `<root>/sub` —
    проходит. Источник — bind длинной формы сервиса тестов.

    Ловит мутацию: «внутри» — `startswith(tree)` без границы компонента
    (`<root>2/x` проходит); сверка без `realpath`/по `normpath` строки без
    разрешения ссылок (`sub/../..` при ссылке, ссылка `link` наружу проходит);
    отказ любой ссылке (ссылка `inner` внутри дерева отказана).
    """
    st = stand
    root = st.tree
    (root / "sub").mkdir()
    (root / "link").symlink_to(f"{root}2")
    (root / "inner").symlink_to(root / "sub")
    source = {"sibling": f"{root}2/x",
              "dotdot": f"{root}/sub/../../{root.name}2",
              "link_out": f"{root}/link",
              "link_in": f"{root}/inner"}[case]
    cfg = st.base_config()
    cfg["services"][st.service]["volumes"].append(
        {"type": "bind", "source": source, "target": f"/m_{word(st.rng)}"})
    run = st.run(cfg)
    where = st.where(case, source)
    if refused:
        check_refused(st, run, where, st.service)
    else:
        check_passed(st, run, where)


# --------------------------------------------------------------- AC-5

def closed_variant(st, case: str) -> tuple:
    """(конфигурация, имя объекта, допустимые имена поля) случая AC-5."""
    cfg = st.base_config()
    svc = cfg["services"][st.service]
    other = f"x_{word(st.rng)}"
    if case in ("bind_tilde", "bind_dot"):
        src = "~/x" if case == "bind_tilde" else "./x"
        svc["volumes"].append(f"{src}:/y_{word(st.rng)}")
        return cfg, st.service, ("volumes", "source")
    if case in ("bind_empty", "bind_null"):
        svc["volumes"].append({"type": "bind",
                               "source": "" if case == "bind_empty" else None,
                               "target": f"/y_{word(st.rng)}"})
        return cfg, st.service, ("source",)
    if case == "context_null":
        svc["build"]["context"] = None
        return cfg, st.service, ("build.context",)
    if case == "build_int":
        svc["build"] = 5
        return cfg, st.service, ("build",)
    if case == "volumes_int":
        svc["volumes"].append(5)
        return cfg, st.service, ("volumes",)
    if case == "additional_list":
        svc["build"]["additional_contexts"] = ["n=/x"]
        return cfg, st.service, ("build.additional_contexts",)
    if case in ("secret_str", "config_str"):
        section = "secrets" if case == "secret_str" else "configs"
        cfg[section] = {other: "x"}
        svc[section] = [{"source": other}]
        return cfg, other, (section,)
    raise AssertionError(f"неизвестный случай {case}")


@pytest.mark.parametrize("case", ["bind_tilde", "bind_dot", "bind_empty",
                                  "bind_null", "context_null", "build_int",
                                  "volumes_int", "additional_list",
                                  "secret_str", "config_str"])
def test_ac5_closed_by_default_and_wrong_form_refused(stand, case):
    """Закрыто по умолчанию и неверная форма поля — отказ с именем объекта и поля, не исключение.

    Источник bind `~/x`, `./x` (короткая строка), пустая строка и `null`
    (полем `source` длинной формы), `build.context: null`, `build: 5`,
    элемент `volumes` — число, `build.additional_contexts` списком, элемент
    `secrets`/`configs` строкой. `report_run` возвращает отказ (не бросает),
    текст называет объект и поле, `up`/`run` не зовутся.

    Ловит мутацию: относительный путь и `~` разрешаются `realpath` от
    рабочего каталога процесса (или `expanduser`) и сверяются как путь;
    `realpath(None)` поднимает `TypeError`, `(item or {}).get` на строке —
    `AttributeError`; элемент неверной формы молча пропускается (стенд
    поднимается — `up`/`run` в журнале).
    """
    st = stand
    cfg, named, fields = closed_variant(st, case)
    run = st.run(cfg)
    where = st.where(case)
    check_refused(st, run, where, named)
    assert any(f in run.refusal for f in fields), \
        f"{where}: отказ не называет поле {fields}: {run.refusal}"


# --------------------------------------------------------------- AC-6

PRIVILEGE_CASES = [
    ("privileged", True, "privileged", None, False),
    ("privileged", True, "privileged", None, True),
    ("pid", "host", "pid", "host", False),
    ("ipc", "host", "ipc", "host", False),
    ("userns_mode", "host", "userns_mode", "host", False),
    ("cgroup", "host", "cgroup", "host", False),
    ("uts", "host", "uts", "host", False),
    ("security_opt", ["seccomp:unconfined"], "security_opt",
     "seccomp:unconfined", False),
    ("security_opt", ["apparmor:unconfined"], "security_opt",
     "apparmor:unconfined", False),
    ("security_opt", ["label=disable"], "security_opt", "label=disable", False),
    ("security_opt", ["label:disable"], "security_opt", "label:disable", False),
    ("cap_add", ["SYS_ADMIN"], "cap_add", None, False),
    ("devices", ["/dev/x:/dev/x"], "devices", None, False),
    ("build.ssh", ["default"], "build.ssh", None, False),
    ("build.privileged", True, "build.privileged", None, False),
    ("build.entitlements", ["security.insecure"], "build.entitlements", None,
     False),
]


@pytest.mark.parametrize("key, value, field, shown, on_db", PRIVILEGE_CASES)
def test_ac6_privileges_refused(stand, key, value, field, shown, on_db):
    """Привилегия сервиса или его сборки — отказ с именем сервиса и поля, без `up`/`run`.

    Каждое из `privileged`, `pid`/`ipc`/`userns_mode`/`cgroup`/`uts: host`,
    `security_opt` с `unconfined`/`label=disable`/`label:disable`, `cap_add`,
    `devices`, `build.ssh`, `build.privileged`, `build.entitlements` —
    отдельным случаем; для строкового значения текст называет и значение.
    `privileged: true` ставится и на сервис тестов, и на второй сервис
    ответа `config` (служба стенда) — отказ называет этот второй сервис.

    Ловит мутацию: привилегии не проверяются (стенд поднимается
    привилегированным — `up`/`run` в журнале); проверяется только сервис
    тестов `compose_service` (служба стенда с `privileged` проходит);
    `security_opt` сверяется только по `seccomp`; поля `build.*` не смотрятся.
    """
    st = stand
    cfg = st.base_config()
    name = st.db if on_db else st.service
    svc = cfg["services"][name]
    if key.startswith("build."):
        svc["build"][key.split(".", 1)[1]] = value
    else:
        svc[key] = value
    run = st.run(cfg)
    names = [name, field] + ([shown] if shown else [])
    check_refused(st, run, st.where(key, value, name), *names)


# --------------------------------------------------------------- AC-7

def positive_variant(st, case: str) -> dict:
    cfg = st.base_config()
    svc = cfg["services"][st.service]
    sub = f"{st.left}"
    vol = f"v{word(st.rng)}"
    if case == "bind_subdir":
        svc["volumes"].append({"type": "bind", "source": f"@TREE@/{sub}",
                               "target": f"/m_{word(st.rng)}"})
    elif case == "bind_tree":
        svc["volumes"].append({"type": "bind", "source": "@TREE@",
                               "target": f"/m_{word(st.rng)}"})
    elif case == "context_subdir":
        svc["build"]["context"] = f"@TREE@/{st.deploy}"
    elif case == "context_tree":
        svc["build"]["context"] = "@TREE@"
    elif case == "secret_in_tree":
        other = f"s{word(st.rng)}"
        cfg["secrets"] = {other: {"name": f"@PROJECT@_{other}",
                                  "file": f"@TREE@/{st.deploy}/{other}.txt"}}
        svc["secrets"] = [{"source": other}]
    elif case == "additional_service":
        svc["build"]["additional_contexts"] = {f"c{word(st.rng)}":
                                               f"service:{st.db}"}
    elif case == "additional_oci_in_tree":
        svc["build"]["additional_contexts"] = {
            f"c{word(st.rng)}": f"oci-layout://@TREE@/{st.deploy}"}
    elif case == "security_opt_nnp":
        svc["security_opt"] = ["no-new-privileges:true"]
    elif case in ("named_volume", "short_named_volume"):
        cfg["volumes"] = {vol: {"name": f"@PROJECT@_{vol}"}}
        svc["volumes"].append(
            {"type": "volume", "source": vol, "target": "/data"}
            if case == "named_volume" else f"{vol}:/data")
    elif case == "tmpfs":
        svc["volumes"].append({"type": "tmpfs", "target": f"/t_{word(st.rng)}"})
    elif case == "image_mount":
        svc["volumes"].append({"type": "image", "source": "alpine:3",
                               "target": f"/i_{word(st.rng)}"})
    elif case == "short_bind_in_tree":
        svc["volumes"].append(f"@TREE@/{sub}:/y_{word(st.rng)}")
    else:
        raise AssertionError(f"неизвестный случай {case}")
    return cfg


@pytest.mark.parametrize("case", [
    "bind_subdir", "bind_tree", "context_subdir", "context_tree",
    "secret_in_tree", "additional_service", "additional_oci_in_tree",
    "security_opt_nnp", "named_volume", "tmpfs", "image_mount",
    "short_named_volume", "short_bind_in_tree"])
def test_ac7_positive_config_runs(stand, case):
    """Конфигурация в пределах дерева и без привилегий — отказа нет, `config`, `up` и `run` зовутся.

    Случаи: bind на подкаталог дерева и на само дерево; `build.context` в
    дереве и равный дереву; секрет-файл в дереве; `additional_contexts`
    `service:<имя>` и `oci-layout://<путь в дереве>`; `security_opt:
    [no-new-privileges:true]`; том `type: volume`, `tmpfs`, `type: image`;
    короткая строка `<том>:/data` и `<дерево>/<подкаталог>:/y`.

    Ловит мутацию: проверяются все типы монтирований (том, `tmpfs`, `image`
    отказаны); каждый источник короткой строки — путь (именованный том
    отказан); сверка с рабочим каталогом процесса, а не с деревом (пути
    дерева отказаны); «внутри — только строго под деревом»
    (`startswith(tree + os.sep)` без равенства: дерево само отказано);
    любой `oci-layout://` — отказ; любой `security_opt` — отказ.
    """
    st = stand
    run = st.run(positive_variant(st, case))
    check_passed(st, run, st.where(case))


# --------------------------------------------------------------- AC-8

def test_ac8_tree_through_symlink(stand):
    """Дерево прогона подано ссылкой — источник через `realpath(дерева)` проходит.

    Тест создаёт `<свой tmp>/alias` → дерево песочницы и передаёт `alias`
    деревом прогона; bind-источник записан явно
    `realpath(дерева)/<подкаталог>`, не подстановкой пути дерева.

    Ловит мутацию: `realpath` берётся только у источника, а дерево
    сравнивается как передано (`alias/…`) — источник `realpath`-формы
    отказан «вне дерева», `up`/`run` не зовутся.
    """
    st = stand
    alias = st.own_tmp() / "alias"
    alias.symlink_to(st.tree, target_is_directory=True)
    cfg = st.base_config()
    cfg["services"][st.service]["volumes"].append(
        {"type": "bind", "source": f"{os.path.realpath(alias)}/{st.left}",
         "target": f"/m_{word(st.rng)}"})
    run = st.run(cfg, tree=alias)
    check_passed(st, run, st.where(alias))


# --------------------------------------------------------------- AC-9

@pytest.mark.parametrize("where_", ["bind", "secrets", "configs"])
def test_ac9_socket_outside_tree_keeps_socket_text(stand, where_):
    """Сокет Docker вне дерева — прежний текст отказа по сокету, а не «вне дерева».

    `DOCKER_HOST=unix://<сокет песочницы>` (сокет во временном каталоге вне
    дерева); источник bind сервиса, `secrets.<имя>.file` или
    `configs.<имя>.file` — этот сокет, отдельными случаями.

    Ловит мутацию: проверка дерева поставлена раньше сокетной для bind,
    секрета или конфигурации — отказ приходит с текстом «вне дерева» вместо
    прежнего текста о сокете.
    """
    st = stand
    st.mp.setenv("DOCKER_HOST", f"unix://{st.socket_path}")
    cfg = st.base_config()
    svc = cfg["services"][st.service]
    other = f"x_{word(st.rng)}"
    if where_ == "bind":
        svc["volumes"].append({"type": "bind", "source": str(st.socket_path),
                               "target": "/var/run/docker.sock"})
        named, text = st.service, SOCKET_BIND_TEXT
    else:
        cfg[where_] = {other: {"name": f"@PROJECT@_{other}",
                               "file": str(st.socket_path)}}
        svc[where_] = [{"source": other}]
        named, text = other, SOCKET_FILE_TEXT
    run = st.run(cfg)
    where = st.where(where_)
    check_refused(st, run, where, named, text)
    assert "вне дерева" not in run.refusal, f"{where}: {run.refusal}"


# --------------------------------------------------------------- AC-10

def test_ac10_override_rule_new_version():
    """`COMPOSE_OVERRIDE_RULE` — новая версия ключа итога и называет новые отказы.

    Строка не равна прежней, начинается с номера версии больше 1 («<n>: ») и
    содержит без учёта регистра «вне дерева», «privileged» и «ssh».

    Ловит мутацию: проверки добавлены, а строка правила не изменена или
    изменена без увеличения номера версии — сохранённые итоги прежнего
    правила засчитываются новому.
    """
    rule = acceptance.COMPOSE_OVERRIDE_RULE
    assert rule != OLD_RULE, rule
    match = re.match(r"(\d+): ", rule)
    assert match and int(match.group(1)) > 1, rule
    low = rule.lower()
    for part in ("вне дерева", "privileged", "ssh"):
        assert part in low, f"нет {part!r}: {rule}"
