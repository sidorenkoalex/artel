"""Строка `doctor` «забытые стенды пульта» и её починка: разбор стендов Compose, живость, снятие, пределы вызовов `docker`.

Группа: разовый
Красен до реализации: строки «забытые стенды пульта» и её починки в фасаде `doctor` нет — поиск функций в модуле `orchestrator.doctor.orphans` их не находит, `doctor.project_checks.GROUP_GONE_PROBES` не определена; ветка задачи до подтяжки main не знает раннера `compose`.

Группа разовая, хотя свойства — код: критерий требует подменять по имени
закрытые починки фасада (`doctor._fix_canary_live` и прочие `_fix_*`),
сверять `PATH` с закрытой `acceptance._OWN_SYSTEM_PATH_DIRS` и звать
починку строки (закрытое имя `_fix_…` по обычаю фасада) — долгоживущим
файлам `tests/` это запрещено.

Функции строки и её починки SPEC не называет по имени; тест находит их в
фасаде `doctor` (требование 14 — экспорт рядом с прочими именами
`orphans`): вызываемые имена фасада из модуля `orchestrator.doctor.orphans`,
кроме прежних `check_orphans` и `_fix_orphan_temp_dirs`; строка — имя с
началом `check_`, починка — имя с началом `fix_`/`_fix_`. Строка зовётся с
соединением БД песочницы, если принимает аргумент; починка — с соединением.

Связка: «запись проекта `compose` локального слоя песочницы (`initialized_
tmp_root`, `config.ROOT` и `DOCKER_CONFIG` — каталоги песочницы) — функция
строки и починки фасада `doctor` — программа `docker`». Программа `docker`
подменена исполнителем на Python в каталоге PATH теста: пишет argv,
окружение, рабочий каталог и его содержимое, свой pid и свою группу
процессов (`os.getpgrp()`), отвечает на `context inspect`/`ps`/`network
ls`/`compose down` заданным текстом и кодом; в режиме зависания порождает
дочерний процесс, пишет его pid и делает `exec sleep`. Метки в ответе `ps`/
`network ls` — строка `ключ=значение` через запятую, как у Docker.

Имена проектов, задач, сервисов, хоста и метки окружения — из `random` при
каждом запуске; зерно печатается и входит в текст провала.
"""
import inspect
import json
import os
import random
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from orchestrator import acceptance, config, doctor, repo_context, store, targets

LETTERS = "abcdefhkmnpqrsvwxyz"
CROCKFORD = "0123456789abcdefghjkmnpqrstvwxyz"
HEX = "0123456789abcdef"
NETWORK_GIT = {"clone", "fetch", "push", "pull", "ls-remote"}
SLEEP = "/bin/sleep"
HANG_SEC = "300"
RUN_LABELS = ("artel.run-pid", "artel.run-host", "artel.run-started")
PROJECT_LABEL = "com.docker.compose.project"
OLD_START = "2001-01-01 00:00:00Z"
ROLE_SKIP = "в шаге роли Docker не вызывается"
REMOTE_SKIP = "демон Docker не локальный"
NOT_ANSWERING = "Docker не отвечает"
NO_DOCKER = "программа docker не найдена"
LAYER_BROKEN = "слой проектов не прочитан"
LABELS_BROKEN = "метки стенда не разобраны"
ORPHANS_MODULE = "orchestrator.doctor.orphans"
OLD_ORPHANS = {"check_orphans", "_fix_orphan_temp_dirs"}

FAKE_DOCKER = r'''#!@PYTHON@
import json
import os
import subprocess
import sys

STATE = @STATE@
args = sys.argv[1:]


def kind(a):
    if a[:1] == ["compose"]:
        for word in ("down", "config", "version"):
            if word in a:
                return "compose " + word
        return "compose"
    if a[:1] == ["network"]:
        return "network ls"
    if a[:1] == ["context"]:
        return "context inspect"
    return a[0] if a else ""


k = kind(args)
with open(os.path.join(STATE, "scenario.json"), encoding="utf-8") as fh:
    act = json.load(fh).get(k, {})
rec = {"kind": k, "argv": args, "env": dict(os.environ), "cwd": os.getcwd(),
       "cwd_entries": sorted(os.listdir(".")), "pid": os.getpid(),
       "pgrp": os.getpgrp()}
if act.get("hang"):
    child = subprocess.Popen([@SLEEP@, @HANG@], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    rec["child"] = child.pid
with open(os.path.join(STATE, "calls.jsonl"), "a", encoding="utf-8") as fh:
    fh.write(json.dumps(rec) + "\n")
if act.get("hang"):
    os.execv(@SLEEP@, [@SLEEP@, @HANG@])
sys.stdout.write(act.get("stdout", ""))
sys.stderr.write(act.get("stderr", ""))
sys.exit(act.get("code", 0))
'''


def word(rng, prefix: str, size: int = 7) -> str:
    return prefix + "".join(rng.choice(LETTERS) for _ in range(size))


def stand_name(rng) -> str:
    """Имя проекта Compose формы части 1: `artel-<id строчными>-<8 hex>`."""
    task = "".join(rng.choice(CROCKFORD) for _ in range(26))
    return f"artel-{task}-{''.join(rng.choice(HEX) for _ in range(8))}"


def dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", ""])
    proc.wait()
    return proc.pid


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


@pytest.fixture
def pult(initialized_tmp_root, monkeypatch, tmp_path):
    """Песочница пульта, подменённый `docker` в PATH, `ARTEL_ROLE` снят, `HOME` — не дом роли."""
    state = tmp_path / "docker-state"
    state.mkdir()
    bindir = tmp_path / "docker-bin"
    bindir.mkdir()
    fake = bindir / "docker"
    fake.write_text(FAKE_DOCKER.replace("@PYTHON@", sys.executable)
                    .replace("@STATE@", repr(str(state)))
                    .replace("@SLEEP@", repr(SLEEP))
                    .replace("@HANG@", repr(HANG_SEC)), encoding="utf-8")
    fake.chmod(0o755)
    (state / "scenario.json").write_text("{}", encoding="utf-8")
    nobin = tmp_path / "no-docker-bin"
    nobin.mkdir()
    home = tmp_path / "pult-home"
    home.mkdir()
    dconf = tmp_path / "docker-config"
    dconf.mkdir()
    mark = "ARTEL_TEST_MARK_" + "".join(random.choices("ABCDEFGHJK", k=8))
    monkeypatch.setenv("PATH", os.pathsep.join(
        [str(bindir), *acceptance._OWN_SYSTEM_PATH_DIRS]))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("DOCKER_CONFIG", str(dconf))
    monkeypatch.setenv(mark, "1")
    monkeypatch.delenv(config.ARTEL_ROLE_ENV, raising=False)
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    hung = []
    sandbox = {"state": state, "bindir": bindir, "fake": fake, "nobin": nobin,
               "home": str(home), "mark": mark, "hung": hung}
    try:
        yield sandbox
    finally:
        # Снимаются только записанные pid зависших вызовов и их дочерних
        # процессов.
        for pid in hung:
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass


@pytest.fixture
def no_external(pult, monkeypatch):
    """Для `all_checks`/`cmd_doctor`: внешние процессы, кроме `git` без сети,
    `ps`, интерпретатора и подменённого `docker`, получают отказ запуска."""
    fake = pult["fake"]
    real_run, real_popen = subprocess.run, subprocess.Popen

    def local(argv) -> bool:
        if not isinstance(argv, (list, tuple)) or not argv:
            return False
        words = [os.fsdecode(a) for a in argv]
        if Path(words[0]) == fake:
            return True
        name = Path(words[0]).name
        if name == "git":
            return not NETWORK_GIT & set(words[1:])
        return name in ("ps", "sleep") or name.startswith("python") \
            or words[0] == sys.executable

    def run(argv, *args, **kwargs):
        if local(argv):
            return real_run(argv, *args, **kwargs)
        text = kwargs.get("text") or kwargs.get("encoding") \
            or kwargs.get("universal_newlines")
        empty = "" if text else b""
        return subprocess.CompletedProcess(argv, 127, empty, empty)

    def popen(argv, *args, **kwargs):
        if local(argv):
            return real_popen(argv, *args, **kwargs)
        raise FileNotFoundError(f"песочница: процесс {argv!r} не запускается")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(subprocess, "Popen", popen)
    return pult


def stands_functions():
    """(функция строки, функция починки) из фасада `doctor`."""
    found = {}
    for name in dir(doctor):
        obj = getattr(doctor, name)
        if callable(obj) and getattr(obj, "__module__", "") == ORPHANS_MODULE \
                and name not in OLD_ORPHANS:
            found[name] = obj
    checks = [n for n in found if n.startswith("check_")]
    fixes = [n for n in found if n.startswith(("fix_", "_fix_"))]
    assert len(checks) == 1 and len(fixes) == 1, \
        f"строка и починка «забытые стенды» в фасаде doctor не найдены: {sorted(found)}"
    return found[checks[0]], found[fixes[0]]


def run_line(conn=None) -> list:
    check, _fix = stands_functions()
    if conn is None:
        conn = store.db()
    got = check(conn) if inspect.signature(check).parameters else check()
    rows = list(got) if isinstance(got, (list, tuple)) and \
        not isinstance(got, doctor.Check) else [got]
    assert len(rows) == 1 and isinstance(rows[0], doctor.Check), rows
    return rows


def run_fix(conn="db") -> None:
    _check, fix = stands_functions()
    fix(store.db() if conn == "db" else conn)


def scenario(sandbox: dict, acts: dict) -> None:
    (sandbox["state"] / "scenario.json").write_text(json.dumps(acts),
                                                    encoding="utf-8")
    (sandbox["state"] / "calls.jsonl").unlink(missing_ok=True)


def calls(sandbox: dict) -> list:
    path = sandbox["state"] / "calls.jsonl"
    found = [json.loads(line) for line in path.read_text().splitlines()] \
        if path.exists() else []
    for rec in found:
        if "child" in rec:
            sandbox["hung"].extend([rec["pid"], rec["child"]])
    return found


def labels_text(labels: dict) -> str:
    return ",".join(f"{k}={v}" for k, v in labels.items())


def stand(rng, name: str | None = None, run: dict | None = None,
          extra: dict | None = None) -> dict:
    """Стенд: имя проекта, контейнеры, сеть и их метки."""
    name = name or stand_name(rng)
    labels = dict(extra or {})
    labels[PROJECT_LABEL] = name
    labels["com.docker.compose.service"] = word(rng, "svc")
    labels.update(run or {})
    containers = [f"{name}-{word(rng, 's', 4)}-1" for _ in range(2)]
    return {"project": name, "containers": containers,
            "network": f"{name}_default", "labels": labels_text(labels)}


def run_labels(pid, host: str, started: str) -> dict:
    return {"artel.run-pid": str(pid), "artel.run-host": host,
            "artel.run-started": started}


def docker_answer(stands: list) -> dict:
    ps = [json.dumps({"Names": c, "Labels": s["labels"], "State": "exited"})
          for s in stands for c in s["containers"]]
    nets = [json.dumps({"Name": s["network"], "Labels": s["labels"]})
            for s in stands]
    return {"context inspect": {"stdout": "unix:///var/run/docker.sock\n"},
            "ps": {"stdout": "\n".join(ps) + "\n"},
            "network ls": {"stdout": "\n".join(nets) + "\n"},
            "compose down": {"stdout": ""}}


def write_layer(rng, compose: bool = True) -> str:
    """Запись проекта (с `compose` или `pytest-own`) в локальном слое песочницы."""
    name = word(rng, "p")
    left = word(rng, "src")
    lines = [f"  {name}:", "    description:", f"      base: {config.MAIN_BRANCH}",
             "      test_profile:", f'        workdir: "{left}/app"',
             f'        long_lived_dir: "{left}/app/tests"',
             '        long_lived_name: "test_<id>_<name>.py"',
             '        report: "junit-xml"']
    if compose:
        deploy = word(rng, "deploy")
        lines += ['        runner: "compose"',
                  f'        compose_file: "{deploy}/compose.yaml"',
                  f'        compose_service: "{word(rng, "svc")}"',
                  f'        compose_env_file: "{deploy}/.env"',
                  f'        compose_env_template: "{deploy}/env.template"',
                  f'        compose_mount: "{left}:/{word(rng, "w")}"']
    else:
        lines += [f'        runner: "{targets.PROFILE_RUNNER_OWN}"',
                  "        command: [python3, -m, pytest]"]
    lines += ["    policy:", "      no_paths: []", "      project_skills: []",
              "      merge_gate: operator",
              f"      weakening_scope: [{left}/app/tests/**/*.py]",
              f"      mutation_claim_scope: [{left}/app/tests/test_*.py]",
              "    machine:", "      forge: github",
              f"      url: https://localhost/team/{name}",
              f"      token_slot: {name}-token"]
    path = targets.local_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("targets:\n" + "\n".join(lines) + "\n", encoding="utf-8")
    targets.load()
    repo_context.clone_path(name).mkdir(parents=True, exist_ok=True)
    return name


def downs(found: list) -> list:
    return [r for r in found if r["kind"] == "compose down"]


def down_project(rec: dict) -> str | None:
    argv = rec["argv"]
    for flag in ("--project-name", "-p"):
        if flag in argv:
            return argv[argv.index(flag) + 1]
    return None


def assert_hygiene(found: list, sandbox: dict, note: str) -> None:
    """Каждый вызов подменённого `docker`: своя группа процессов, без `HOME`
    пульта и метки теста, `PATH` — каталог `docker` и системные каталоги."""
    expected = [str(sandbox["bindir"]), *acceptance._OWN_SYSTEM_PATH_DIRS]
    assert found, f"{note}: docker не вызван"
    for rec in found:
        where = f"{note}: вызов {rec['argv']}"
        assert rec["pgrp"] != os.getpgrp(), where
        assert rec["env"].get("HOME") != sandbox["home"], where
        assert sandbox["mark"] not in rec["env"], where
        assert rec["env"].get("PATH", "").split(os.pathsep) == expected, \
            f"{where}: PATH {rec['env'].get('PATH')}"


def detail_of(rows: list) -> str:
    return "\n".join(f"[{r.status}] {r.name}: {r.detail}" for r in rows)


@pytest.mark.parametrize("death", ["pid", "time"])
def test_ac2_dead_stand_warned_and_taken_down(pult, seed, death):
    """Стенд пульта с мёртвым прогоном — `warn` с именами контейнеров и сети; починка зовёт `down --remove-orphans` без `-v` и `-f` в пустом временном каталоге.

    Сценарий: проект `compose` в слое; ответ `ps`/`network ls` — два
    стенда формы `artel-<26>-<8 hex>` с полной тройкой меток: мёртвый
    (`death=pid` — pid завершившегося процесса; `death=time` — живой pid
    теста со временем `artel.run-started` раньше его старта) и мёртвый того
    же вида второй. Строка — `warn`, текст называет все контейнеры и сети
    обоих; починка зовёт `compose down` ровно для этих двух проектов, с
    `--remove-orphans`, без `-v`/`--volumes` и `-f`/`--file`, в рабочем
    каталоге — пустом временном каталоге (не корень пульта и не каталог
    теста). Каждый вызов `docker` (`context inspect`, `ps`, `network ls`,
    `compose down`) — в своей группе, без `HOME` пульта и метки, с `PATH`
    из каталога `docker` и `_OWN_SYSTEM_PATH_DIRS`.

    Ловит мутацию: живость решается только по pid (живой pid с поздним
    стартом не считается мёртвым); `down -v` (тома удаляются); `down` с
    `-f` или в корне пульта/клоне; окружение — копия `os.environ`; вызов
    без `start_new_session`; в тексте только имя проекта без имён
    контейнеров и сети.
    """
    rng = random.Random(seed)
    write_layer(rng)
    pid = dead_pid() if death == "pid" else os.getpid()
    started = store.now() if death == "pid" else OLD_START
    dead = [stand(rng, run=run_labels(pid, word(rng, "h"), started))
            for _ in range(2)]
    scenario(pult, docker_answer(dead))
    rows = run_line()
    note = f"зерно: {seed}; {detail_of(rows)}"
    assert rows[0].status == "warn", note
    for s in dead:
        for name in s["containers"] + [s["network"]]:
            assert name in rows[0].detail, f"{note}: нет {name}"
    run_fix()
    found = calls(pult)
    taken = downs(found)
    assert sorted(down_project(r) for r in taken) == \
        sorted(s["project"] for s in dead), f"{note}; down {taken}"
    tmp_root = os.path.realpath(tempfile.gettempdir())
    for rec in taken:
        argv = rec["argv"]
        where = f"{note}; down {argv} в {rec['cwd']}"
        assert "down" in argv and "--remove-orphans" in argv, where
        for flag in ("-v", "--volumes", "-f", "--file"):
            assert flag not in argv, where
        assert rec["cwd_entries"] == [], where
        cwd = os.path.realpath(rec["cwd"])
        assert cwd.startswith(tmp_root + os.sep), where
        assert cwd != os.path.realpath(str(config.ROOT)), where
        assert cwd != os.path.realpath(os.getcwd()), where
    kinds = {r["kind"] for r in found}
    assert {"context inspect", "ps", "network ls", "compose down"} <= kinds, kinds
    assert_hygiene(found, pult, note)


@pytest.mark.parametrize("case", ["live-own-host", "live-foreign-host",
                                  "artel-foo", "no-run-labels",
                                  "foreign-comma-label"])
def test_ac2_untouched_projects_not_warned_nor_taken_down(pult, seed, case):
    """Стенд живого прогона (любое имя хоста), `artel-foo`, стенд без меток живого прогона, чужой проект с меткой через запятую — не в `warn`, `down` для них не зовётся.

    Сценарий: в ответе `ps`/`network ls` — контрольный мёртвый стенд и
    проверяемый проект: живой pid теста со временем `artel.run-started` не
    раньше его старта и именем этого хоста либо чужим именем хоста;
    проект `artel-foo` с полной тройкой меток мёртвого прогона; проект
    правильной формы без единой метки `artel.run-*`; чужой проект Compose с
    меткой `com.docker.compose.project.config_files=/a.yml,/b.yml` перед
    меткой проекта. Строка не падает, её текст называет контрольный стенд и
    не называет проверяемый; починка зовёт `down` только для контрольного.

    Ловит мутацию: живость сравнивает имя хоста (`lease.process_alive`) —
    стенд с чужим хостом снимается; имя проекта сверяется префиксом
    `artel-` без формы; стенд без меток живого прогона считается забытым;
    разбор меток `split("=")` по каждому фрагменту падает на `/b.yml`.
    """
    rng = random.Random(seed)
    write_layer(rng)
    control = stand(rng, run=run_labels(dead_pid(), word(rng, "h"), store.now()))
    if case == "live-own-host":
        other = stand(rng, run=run_labels(os.getpid(), socket.gethostname(),
                                          store.now()))
    elif case == "live-foreign-host":
        other = stand(rng, run=run_labels(os.getpid(), word(rng, "host-"),
                                          store.now()))
    elif case == "artel-foo":
        other = stand(rng, name="artel-foo",
                      run=run_labels(dead_pid(), word(rng, "h"), OLD_START))
    elif case == "no-run-labels":
        other = stand(rng)
    else:
        other = stand(rng, name=word(rng, "shop"), extra={
            "com.docker.compose.project.config_files": "/a.yml,/b.yml"})
    scenario(pult, docker_answer([other, control]))
    rows = run_line()
    note = f"зерно: {seed}; {case}; {detail_of(rows)}"
    assert rows[0].status == "warn", note
    assert control["containers"][0] in rows[0].detail, note
    for name in other["containers"] + [other["network"]]:
        assert name not in rows[0].detail, f"{note}: назван {name}"
    run_fix()
    taken = [down_project(r) for r in downs(calls(pult))]
    assert taken == [control["project"]], f"{note}; down {taken}"


@pytest.mark.parametrize("damage", ["missing", "pid", "started"])
def test_ac2_broken_run_labels_warned_not_taken_down(pult, seed, damage):
    """Стенд правильной формы с испорченной тройкой меток — `warn` «метки стенда не разобраны» с именем проекта; `down` не зовётся; строка не падает.

    Сценарий: одна из трёх меток `artel.run-*` (случайная) снята;
    `artel.run-pid` — не целое число; `artel.run-started` — не в формате
    `store.now()` (`%Y-%m-%d %H:%M:%SZ`). Исключения нет ни у строки, ни у
    починки.

    Ловит мутацию: время разбирается `strptime` без защиты (`ValueError`
    наружу); `int()` pid без проверки; неполная тройка считается мёртвым
    стендом и снимается; стенд с порчей молча пропущен (нет `warn`).
    """
    rng = random.Random(seed)
    write_layer(rng)
    labels = run_labels(dead_pid(), word(rng, "h"), store.now())
    if damage == "missing":
        del labels[rng.choice(RUN_LABELS)]
    elif damage == "pid":
        labels["artel.run-pid"] = f"{rng.randint(10, 99)}x{rng.randint(1, 9)}"
    else:
        labels["artel.run-started"] = "2026-11-05T10:20:30+00:00"
    broken = stand(rng, run=labels)
    scenario(pult, docker_answer([broken]))
    rows = run_line()
    note = f"зерно: {seed}; {damage}; {detail_of(rows)}"
    assert rows[0].status == "warn", note
    assert LABELS_BROKEN in rows[0].detail, note
    assert broken["project"] in rows[0].detail, note
    run_fix()
    assert downs(calls(pult)) == [], note


@pytest.mark.parametrize("source", ["context", "env"])
def test_ac2_remote_daemon_skipped(pult, seed, monkeypatch, source):
    """Адрес демона Docker не `unix://` — `skip` «демон Docker не локальный», `down` не вызван.

    Сценарий: `DOCKER_HOST` не задан, подменённый `docker context inspect`
    отвечает `tcp://…` (`context`); либо `DOCKER_HOST=tcp://…` в окружении
    пульта (`env`). В ответе `ps` — мёртвый стенд пульта.

    Ловит мутацию: адрес демона не проверяется (стенд удалённого демона
    признан забытым по pid этой машины и снят); `DOCKER_HOST` окружения не
    читается — решает только контекст.
    """
    rng = random.Random(seed)
    write_layer(rng)
    dead = stand(rng, run=run_labels(dead_pid(), word(rng, "h"), store.now()))
    acts = docker_answer([dead])
    address = f"tcp://10.{rng.randint(0, 250)}.0.{rng.randint(1, 250)}:2375"
    if source == "context":
        acts["context inspect"] = {"stdout": address + "\n"}
    else:
        monkeypatch.setenv("DOCKER_HOST", address)
    scenario(pult, acts)
    rows = run_line()
    note = f"зерно: {seed}; {source}; {detail_of(rows)}"
    assert rows[0].status == "skip", note
    assert REMOTE_SKIP in rows[0].detail, note
    run_fix()
    assert downs(calls(pult)) == [], note


def test_ac2_role_environment_skips_without_docker(pult, seed, monkeypatch):
    """В процессе роли (`ARTEL_ROLE` выставлен) — `skip` «в шаге роли Docker не вызывается», подменённый `docker` не вызван ни строкой, ни починкой.

    Ловит мутацию: признак процесса роли не проверяется строкой или
    починкой — `docker ps`/`down` зовутся из шага роли.
    """
    rng = random.Random(seed)
    write_layer(rng)
    dead = stand(rng, run=run_labels(dead_pid(), word(rng, "h"), store.now()))
    scenario(pult, docker_answer([dead]))
    monkeypatch.setenv(config.ARTEL_ROLE_ENV, "developer")
    rows = run_line()
    note = f"зерно: {seed}; {detail_of(rows)}"
    assert rows[0].status == "skip", note
    assert ROLE_SKIP in rows[0].detail, note
    run_fix()
    assert calls(pult) == [], note


def test_ac2_no_compose_project_skips_without_docker(pult, seed):
    """Нет проекта с профилем `compose` — `skip`, `docker` не вызван ни строкой, ни починкой.

    Ловит мутацию: строка или починка зовут `docker` при любом слое
    проектов (проверка наличия `compose` пропущена или после вызова
    `docker`).
    """
    rng = random.Random(seed)
    write_layer(rng, compose=False)
    dead = stand(rng, run=run_labels(dead_pid(), word(rng, "h"), store.now()))
    scenario(pult, docker_answer([dead]))
    rows = run_line()
    note = f"зерно: {seed}; {detail_of(rows)}"
    assert rows[0].status == "skip", note
    run_fix()
    assert calls(pult) == [], note


def test_ac2_docker_not_found_warns(pult, seed, monkeypatch):
    """Проект `compose` есть, а программы `docker` в PATH нет — `warn` «программа docker не найдена».

    Ловит мутацию: отсутствие `docker` даёт `skip` (молча) или исключение
    запуска.
    """
    rng = random.Random(seed)
    write_layer(rng)
    monkeypatch.setenv("PATH", os.pathsep.join(
        [str(pult["nobin"]), *acceptance._OWN_SYSTEM_PATH_DIRS]))
    rows = run_line()
    note = f"зерно: {seed}; {detail_of(rows)}"
    assert rows[0].status == "warn", note
    assert NO_DOCKER in rows[0].detail, note
    run_fix()
    assert calls(pult) == [], note


def test_ac2_broken_layer_warns_and_others_print(no_external, seed):
    """Слой проектов не прочитан — `warn` «слой проектов не прочитан», прочие строки `doctor` есть, починка ничего не снимает.

    Сценарий: локальный слой песочницы — неразбираемая запись. Строка —
    `warn` с этим текстом; в `doctor.all_checks` есть она и другие строки,
    исключения нет; починка не зовёт `docker` (в ответе `ps` — мёртвый
    стенд).

    Ловит мутацию: `targets.load()` строки без перехвата `TargetsError`
    (`doctor` падает); строка зарегистрирована в ветке годного
    `targets.load()` (при сломанном слое её нет); починка при сломанном
    слое снимает стенды.
    """
    rng = random.Random(seed)
    path = targets.local_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"targets:\n  {word(rng, 'p')}:\n    description: [не запись\n",
                    encoding="utf-8")
    with pytest.raises(targets.TargetsError):
        targets.load()
    dead = stand(rng, run=run_labels(dead_pid(), word(rng, "h"), store.now()))
    scenario(no_external, docker_answer([dead]))
    rows = run_line()
    note = f"зерно: {seed}; {detail_of(rows)}"
    assert rows[0].status == "warn", note
    assert LAYER_BROKEN in rows[0].detail, note
    every = doctor.all_checks(store.db())
    names = [c.name for c in every]
    assert rows[0].name in names, note
    assert len(set(names)) > 1, note
    run_fix()
    assert downs(calls(no_external)) == [], note


def test_ac2_fix_without_conn_calls_no_docker(pult, seed):
    """Починка при `conn=None` и проекте `compose` с мёртвым стендом — ни одного вызова `docker`.

    Ловит мутацию: починка не смотрит на `conn` и снимает стенды из
    `cmd_doctor` без БД (настоящий `down` из чужих тестов).
    """
    rng = random.Random(seed)
    write_layer(rng)
    dead = stand(rng, run=run_labels(dead_pid(), word(rng, "h"), store.now()))
    scenario(pult, docker_answer([dead]))
    run_fix(None)
    assert calls(pult) == [], f"зерно: {seed}"


@pytest.mark.parametrize("mode", ["hang", "code"])
@pytest.mark.parametrize("call", ["ps", "network ls", "context inspect"])
def test_ac2_docker_not_answering_warns(pult, seed, monkeypatch, call, mode):
    """`docker ps`/`network ls`/`context inspect` зависает или возвращает ненулевой код — `warn` «Docker не отвечает»; зависший вызов снят с дочерним процессом.

    Сценарий: `DOCKER_CALL_TIMEOUT_SEC` подменён на 1; вызов `call`
    зависает (порождает дочерний процесс, пишет его pid, `exec sleep`) или
    отвечает кодом 1. Строка возвращается задолго до сна вызова; сразу
    после возврата `os.kill(<pid дочернего>, 0)` поднимает
    `ProcessLookupError`; вызовы — в своей группе, без `HOME` и метки.

    Ловит мутацию: вызов без предела или с пределом, прочитанным при
    импорте (10 с — дольше границы); по пределу снят только pid вызова, не
    группа; ожидание исчезновения группы не делается; ненулевой код `ps`
    принят как пустой список стендов (`ok`).
    """
    rng = random.Random(seed)
    write_layer(rng)
    monkeypatch.setattr(doctor.project_checks, "DOCKER_CALL_TIMEOUT_SEC", 1)
    dead = stand(rng, run=run_labels(dead_pid(), word(rng, "h"), store.now()))
    acts = docker_answer([dead])
    acts[call] = {"hang": True} if mode == "hang" else {"code": 1, "stderr": "boom\n"}
    scenario(pult, acts)
    started = time.monotonic()
    rows = run_line()
    elapsed = time.monotonic() - started
    found = calls(pult)
    note = f"зерно: {seed}; {call} {mode}; {elapsed:.1f} с; {detail_of(rows)}"
    for rec in found:
        if "child" in rec:
            with pytest.raises(ProcessLookupError):
                os.kill(rec["child"], 0)
    if mode == "hang":
        assert [r for r in found if "child" in r], note
        assert elapsed < 9, note
    assert rows[0].status == "warn", note
    assert NOT_ANSWERING in rows[0].detail, note
    assert_hygiene(found, pult, note)


def test_ac2_hanging_down_bounded_by_teardown_limit(pult, seed, monkeypatch):
    """Зависший `compose down` снимается по подменённому `config.COMPOSE_TEARDOWN_TIMEOUT_SEC` — починка возвращается, дочерний процесс снят.

    Сценарий: атрибут `COMPOSE_TEARDOWN_TIMEOUT_SEC` модуля
    `orchestrator/config.py` подменён на 1; мёртвый стенд; `down` зависает
    с дочерним процессом. Починка возвращается быстрее предела вызовов
    строки без подмены (`DOCKER_CALL_TIMEOUT_SEC`); сразу после возврата
    `os.kill(<pid дочернего down>, 0)` поднимает `ProcessLookupError`.

    Ловит мутацию: предел `down` прочитан при импорте (120 с — тест висит
    до своего предела); `down` ограничен `DOCKER_CALL_TIMEOUT_SEC`
    (10 с — дольше границы); снят только pid `down`.
    """
    rng = random.Random(seed)
    write_layer(rng)
    monkeypatch.setattr(config, "COMPOSE_TEARDOWN_TIMEOUT_SEC", 1)
    dead = stand(rng, run=run_labels(dead_pid(), word(rng, "h"), store.now()))
    acts = docker_answer([dead])
    acts["compose down"] = {"hang": True}
    scenario(pult, acts)
    limit = doctor.project_checks.DOCKER_CALL_TIMEOUT_SEC
    started = time.monotonic()
    run_fix()
    elapsed = time.monotonic() - started
    found = calls(pult)
    hung = [r for r in found if r["kind"] == "compose down" and "child" in r]
    note = f"зерно: {seed}; {elapsed:.1f} с из {limit}"
    assert hung, note
    for rec in hung:
        with pytest.raises(ProcessLookupError):
            os.kill(rec["child"], 0)
    assert elapsed < limit, note
    assert_hygiene(found, pult, note)


def test_ac2_group_gone_probes_constant_floor():
    """Константа числа проб группы без подмены не меньше 100 000.

    Ловит мутацию: малое число проб — ожидание исчезновения группы
    обрывается раньше, чем группа исчезнет на macOS.
    """
    assert doctor.project_checks.GROUP_GONE_PROBES >= 100000


@pytest.mark.parametrize("call", ["ps", "compose down"])
def test_ac2_group_probes_exhausted_without_exception(pult, seed, monkeypatch, call):
    """Исчерпание проб группы после `SIGKILL` — ровно `GROUP_GONE_PROBES` проб сигналом 0; у `ps` строка `warn` «Docker не отвечает», у `down` починка возвращается; исключения нет.

    Сценарий: `GROUP_GONE_PROBES` — малое случайное число, пределы вызовов
    — 1 с; подменён только `os.killpg`: сигнал 0 поднимает
    `PermissionError`, прочие сигналы уходят настоящей функции
    (`liveness._group_exists` не подменяется). Вызов `call` зависает. После
    `SIGKILL` группы вызова вызовов `os.killpg` этой группы с сигналом 0 —
    ровно подменённое число.

    Ловит мутацию: пробы до `ProcessLookupError` без предела (бесконечный
    цикл); `PermissionError` — «группы нет» (проба одна); число проб
    прочитано при импорте (100 000); исчерпание поднимает исключение.
    """
    rng = random.Random(seed)
    write_layer(rng)
    probes = rng.randint(3, 9)
    monkeypatch.setattr(doctor.project_checks, "DOCKER_CALL_TIMEOUT_SEC", 1)
    monkeypatch.setattr(doctor.project_checks, "GROUP_GONE_PROBES", probes)
    monkeypatch.setattr(config, "COMPOSE_TEARDOWN_TIMEOUT_SEC", 1)
    dead = stand(rng, run=run_labels(dead_pid(), word(rng, "h"), store.now()))
    acts = docker_answer([dead])
    acts[call] = {"hang": True}
    scenario(pult, acts)
    sent = []
    real_killpg = os.killpg

    def killpg(pgid, sig):
        sent.append((pgid, sig))
        if sig == 0:
            raise PermissionError(1, "подменённая проба")
        return real_killpg(pgid, sig)

    monkeypatch.setattr(os, "killpg", killpg)
    try:
        if call == "ps":
            rows = run_line()
        else:
            run_fix()
            rows = []
    finally:
        monkeypatch.setattr(os, "killpg", real_killpg)
    hung = [r for r in calls(pult) if "child" in r]
    note = f"зерно: {seed}; {call}; проб {probes}; {detail_of(rows)}; {sent[:20]}"
    assert hung, note
    group = hung[0]["pgrp"]
    kills = [i for i, (g, s) in enumerate(sent) if g == group and s == signal.SIGKILL]
    assert kills, note
    after = [s for g, s in sent[kills[0] + 1:] if g == group and s == 0]
    assert len(after) == probes, note
    if call == "ps":
        assert rows[0].status == "warn" and NOT_ANSWERING in rows[0].detail, note


def test_ac2_line_outside_check_orphans_and_in_all_checks(no_external, seed):
    """Строка не входит в `check_orphans`, исходы `check_orphans` прежние; строка есть в `doctor.all_checks(conn)`.

    Сценарий: проект `compose` и мёртвый стенд в ответе `ps`. Имени строки
    нет среди строк `doctor.check_orphans(conn)`; строки `check_orphans`
    (имя и исход) те же, что при слое без проекта `compose` и без ответа
    `docker`; `check_orphans` не зовёт `docker`. Среди строк
    `doctor.all_checks(conn)` есть строка с именем строки «забытые стенды».

    Ловит мутацию: строка дописана в список `check_orphans` (меняет её
    состав и исходы); строка не зарегистрирована в `all_checks`.
    """
    rng = random.Random(seed)
    conn = store.db()
    write_layer(rng, compose=False)
    scenario(no_external, {})
    before = [(c.name, c.status) for c in doctor.check_orphans(conn)]
    write_layer(rng)
    dead = stand(rng, run=run_labels(dead_pid(), word(rng, "h"), store.now()))
    scenario(no_external, docker_answer([dead]))
    after = [(c.name, c.status) for c in doctor.check_orphans(conn)]
    assert calls(no_external) == [], f"зерно: {seed}"
    rows = run_line(conn)
    note = f"зерно: {seed}; {detail_of(rows)}; check_orphans {after}"
    assert rows[0].name not in [n for n, _s in after], note
    assert after == before, note
    names = [c.name for c in doctor.all_checks(conn)]
    assert rows[0].name in names, note


def test_ac2_cmd_doctor_fix_runs_stands_fix(no_external, seed, monkeypatch, capsys):
    """`cmd_doctor(fix=True)` вызывает починку строки; прочие починки и `_fix_canary_live` подменены по имени — подменённая `_fix_canary_live` вызвана, настоящие не исполнены.

    Сценарий: проект `compose`, мёртвый стенд в ответе `ps`. Все починки
    фасада (`_fix_*`/`fix_*`), кроме починки строки, подменены по имени
    записывающими заглушками (образец
    `tests/test_doctor_closed_ref_fix.py:177-183`), `all_checks` — пустым
    списком, стоп-кран и открытые алерты — пустыми. После
    `cmd_doctor(fix=True)` подменённый `docker` получил `compose down`
    мёртвого стенда, заглушка `_fix_canary_live` вызвана.

    Ловит мутацию: починка строки не добавлена в блок `--fix`
    `cmd_doctor` (нет `down`); добавлена в ветку только `restore`.
    """
    rng = random.Random(seed)
    write_layer(rng)
    dead = stand(rng, run=run_labels(dead_pid(), word(rng, "h"), store.now()))
    scenario(no_external, docker_answer([dead]))
    _check, stands_fix = stands_functions()
    called = []
    for name in dir(doctor):
        obj = getattr(doctor, name)
        if name.startswith(("_fix_", "fix_")) and callable(obj) \
                and obj is not stands_fix:
            monkeypatch.setattr(doctor, name,
                                lambda *a, _n=name, **k: called.append(_n))
    assert "_fix_canary_live" in dir(doctor)
    monkeypatch.setattr(doctor, "all_checks", lambda conn: [])
    monkeypatch.setattr(doctor.runner, "wave_breaker_alerts_open", lambda conn: [])
    monkeypatch.setattr(doctor.alerts, "open_alerts", lambda conn, kind=None: [])
    doctor.cmd_doctor(fix=True)
    capsys.readouterr()
    taken = [down_project(r) for r in downs(calls(no_external))]
    note = f"зерно: {seed}; вызваны {called}; down {taken}"
    assert "_fix_canary_live" in called, note
    assert taken == [dead["project"]], note
