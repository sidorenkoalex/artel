"""Строка `doctor` проверки записи `compose`: файлы клона, сервис, версия Compose, предел и группа вызова.

Группа: долгоживущий
Красен до реализации: строки записи `compose` в `doctor.all_checks` нет — строка, которой нет у двойника записи с `pytest-own`, не находится, а `doctor.project_checks.DOCKER_CALL_TIMEOUT_SEC` и `GROUP_GONE_PROBES` не определены; в ветке задачи до подтяжки main с частью 1 запись `compose` не загружается (`TargetsError`).

Связка, которую держит файл: «запись проекта `compose` локального слоя
песочницы — `doctor.all_checks` — вызов программы `docker`». Песочница —
`initialized_tmp_root` (пути `config` во временном каталоге, `DOCKER_CONFIG`
— каталог песочницы); клон проекта — каталог `repo_context.clone_path`
песочницы с Compose-файлом и шаблоном окружения. Программа `docker`
подменена исполнителем на Python в каталоге PATH теста: он пишет argv,
окружение, рабочий каталог, свой pid и свою группу процессов
(`os.getpgrp()`), отвечает заданным текстом и кодом, а в режиме зависания
порождает дочерний процесс, записывает его pid и делает `exec sleep`.
Прочие внешние процессы `doctor` (кроме `git` без сети, `ps`, интерпретатора
и подменённого `docker`) получают отказ запуска.

Строка записи `compose` находится без её имени: это та единственная строка
`doctor.all_checks`, которой нет у двойника — той же записи с раннером
`pytest-own` вместо `compose` (те же каталоги, `machine.path`).

Имена проекта, компонентов, сервиса, каталогов и метки — из `random` при
каждом запуске; зерно печатается и входит в текст провала.
"""
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from orchestrator import config, doctor, repo_context, runner, store, targets

LETTERS = "abcdefhkmnpqrsvwxyz"
NETWORK_GIT = {"clone", "fetch", "push", "pull", "ls-remote"}
SLEEP = "/bin/sleep"
HANG_SEC = "300"
ROLE_SKIP = "в шаге роли Docker не вызывается"
NO_DOCKER = "программа docker не найдена"

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


def is_local(argv, fake: Path) -> bool:
    """Процесс, которому песочница разрешает запуск."""
    if not isinstance(argv, (list, tuple)) or not argv:
        return False
    words = [os.fsdecode(a) for a in argv]
    if Path(words[0]).parent == fake.parent and Path(words[0]).name == "docker":
        return True
    name = Path(words[0]).name
    if name == "git":
        return not NETWORK_GIT & set(words[1:])
    return name in ("ps", "sleep") or name.startswith("python") \
        or words[0] == sys.executable


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


@pytest.fixture
def pult(initialized_tmp_root, monkeypatch, tmp_path):
    """Песочница пульта с подменённым `docker` в PATH; прочие внешние процессы не запускаются."""
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
        [str(bindir), "/usr/bin", "/bin", "/usr/sbin", "/sbin"]))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("DOCKER_CONFIG", str(dconf))
    monkeypatch.setenv(mark, "1")
    monkeypatch.delenv(config.ARTEL_ROLE_ENV, raising=False)
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    real_run, real_popen = subprocess.run, subprocess.Popen

    def run(argv, *args, **kwargs):
        if is_local(argv, fake):
            return real_run(argv, *args, **kwargs)
        text = kwargs.get("text") or kwargs.get("encoding") \
            or kwargs.get("universal_newlines")
        empty = "" if text else b""
        return subprocess.CompletedProcess(argv, 127, empty, empty)

    def popen(argv, *args, **kwargs):
        if is_local(argv, fake):
            return real_popen(argv, *args, **kwargs)
        raise FileNotFoundError(f"песочница: процесс {argv!r} не запускается")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(subprocess, "Popen", popen)
    hung = []
    sandbox = {"state": state, "bindir": bindir, "nobin": nobin,
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


def scenario(sandbox: dict, acts: dict) -> None:
    (sandbox["state"] / "scenario.json").write_text(json.dumps(acts),
                                                    encoding="utf-8")


def calls(sandbox: dict) -> list:
    path = sandbox["state"] / "calls.jsonl"
    found = [json.loads(line) for line in path.read_text().splitlines()] \
        if path.exists() else []
    for rec in found:
        if "child" in rec:
            sandbox["hung"].extend([rec["pid"], rec["child"]])
    return found


def comp_fields(rng, comp: str) -> dict:
    deploy = word(rng, "deploy")
    left = word(rng, "src")
    return {"runner": "compose", "workdir": f"{left}/app",
            "long_lived_dir": f"{left}/app/tests",
            "long_lived_name": "test_<id>_<name>.py", "report": "junit-xml",
            "compose_file": f"{deploy}/compose-{comp}.yaml",
            "compose_service": word(rng, "svc"),
            "compose_env_file": f"{deploy}/.env.{comp}",
            "compose_env_template": f"{deploy}/env-{comp}.template",
            "compose_mount": f"{left}:/{word(rng, 'w')}"}


def twin_fields(fields: dict) -> dict:
    """Те же поля с раннером `pytest-own` вместо `compose`."""
    twin = {k: v for k, v in fields.items() if not k.startswith("compose_")}
    twin["runner"] = targets.PROFILE_RUNNER_OWN
    twin["command"] = ["python3", "-m", "pytest"]
    return twin


def render(fields: dict, indent: int) -> list:
    pad = " " * indent
    out = []
    for key, value in fields.items():
        if isinstance(value, list):
            out.append(f"{pad}{key}: [{', '.join(value)}]")
        else:
            out.append(f'{pad}{key}: "{value}"')
    return out


def write_record(name: str, profiles: dict, form: str,
                 machine_path: str) -> None:
    """Запись проекта в локальном слое песочницы: `test_profile` (один
    профиль) либо `components:`."""
    lines = [f"  {name}:", "    description:", f"      base: {config.MAIN_BRANCH}"]
    if form == "test_profile":
        lines.append("      test_profile:")
        lines += render(next(iter(profiles.values())), 8)
    else:
        lines.append("      components:")
        for comp, fields in profiles.items():
            lines.append(f"        {comp}:")
            lines += render(fields, 10)
    lines += ["    policy:", "      no_paths: []", "      project_skills: []",
              "      merge_gate: operator"]

    def scope(fields, indent):
        lld = fields["long_lived_dir"]
        return render({"weakening_scope": [f"{lld}/**/*.py"],
                       "mutation_claim_scope": [f"{lld}/test_*.py"]}, indent)

    if form == "test_profile":
        lines += scope(next(iter(profiles.values())), 6)
    else:
        lines.append("      components:")
        for comp, fields in profiles.items():
            lines.append(f"        {comp}:")
            lines += scope(fields, 10)
    lines += ["    machine:", "      forge: github",
              f"      url: https://localhost/team/{name}",
              f"      token_slot: {name}-token", f'      path: "{machine_path}"']
    path = targets.local_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("targets:\n" + "\n".join(lines) + "\n", encoding="utf-8")


def make_project(rng, form: str = "test_profile", count: int = 1,
                 missing: dict | None = None) -> dict:
    """Проект `compose` в песочнице: запись, клон с файлами; `missing` —
    {номер компонента: поле}, файл которого в клон не кладётся."""
    name = word(rng, "p")
    comps = [word(rng, "c", 5) for _ in range(count)]
    profiles = {c: comp_fields(rng, c) for c in comps}
    if count > 1:
        # Запись с несколькими компонентами обязана разделить дерево `paths`.
        for fields in profiles.values():
            fields["paths"] = [f"^{fields['workdir'].split('/')[0]}/"]
    machine = [f"/opt/{word(rng, 'm', 5)}/bin", f"/opt/{word(rng, 'm', 5)}/bin"]
    clone = repo_context.clone_path(name)
    clone.mkdir(parents=True, exist_ok=True)
    for index, fields in enumerate(profiles.values()):
        for field in ("compose_file", "compose_env_template"):
            if (missing or {}).get(index) == field:
                continue
            target = clone / fields[field]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("services: {}\n" if field == "compose_file"
                              else "X=1\n", encoding="utf-8")
    return {"name": name, "profiles": profiles, "form": form,
            "machine": machine, "clone": clone}


def rows(project: dict, twin: bool = False) -> dict:
    profiles = project["profiles"]
    if twin:
        profiles = {c: twin_fields(f) for c, f in profiles.items()}
    write_record(project["name"], profiles, project["form"],
                 os.pathsep.join(project["machine"]))
    targets.load()
    return {c.name: c for c in doctor.all_checks(store.db())}


def compose_line(project: dict, sandbox: dict, acts: dict):
    """(строка записи `compose`, все строки, время прогона `all_checks`,
    вызовы `docker`): единственная строка, которой нет у двойника."""
    scenario(sandbox, {})
    base = rows(project, twin=True)
    (sandbox["state"] / "calls.jsonl").unlink(missing_ok=True)
    scenario(sandbox, acts)
    started = time.monotonic()
    found = rows(project)
    elapsed = time.monotonic() - started
    extra = [c for n, c in found.items() if n not in base]
    note = "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in extra)
    assert len(extra) == 1, f"строк записи compose не одна:\n{note}"
    return extra[0], found, elapsed, calls(sandbox)


def services_answer(project: dict) -> str:
    names = [f["compose_service"] for f in project["profiles"].values()]
    return "\n".join(names + ["other"]) + "\n"


def good_acts(project: dict) -> dict:
    return {"compose version": {"stdout": "2.39.4-desktop.1\n"},
            "compose config": {"stdout": services_answer(project)}}


def assert_hygiene(found: list, sandbox: dict, project: dict, note: str) -> None:
    """Каждый вызов `docker` строки записи (`config`, `version`): своя
    группа, нет `HOME` пульта и метки, `PATH` несёт каталоги `machine.path`
    записи. Вызовы строки «забытые стенды» того же `all_checks` — предмет
    другого критерия."""
    own = [r for r in found if r["kind"] in ("compose config", "compose version")]
    assert own, f"{note}: docker строкой не вызван"
    for rec in own:
        where = f"{note}: вызов {rec['argv']}"
        assert rec["pgrp"] != os.getpgrp(), where
        assert rec["env"].get("HOME") != sandbox["home"], where
        assert sandbox["mark"] not in rec["env"], where
        parts = rec["env"].get("PATH", "").split(os.pathsep)
        for directory in project["machine"]:
            assert directory in parts, f"{where}: PATH {parts}"


@pytest.mark.parametrize("form", ["test_profile", "components"])
def test_ac3_compose_line_ok_and_env_file(pult, seed, form):
    """Верная запись `compose` — одна строка `ok`; `config --services` зовётся с `--env-file` на шаблон из клона.

    Сценарий: запись `compose` (в `test_profile` или в компоненте) с
    Compose-файлом и шаблоном окружения в клоне; подменённый `docker`
    отвечает версией `2.39.4-desktop.1` и перечнем сервисов с нужным. В
    `doctor.all_checks` есть ровно одна строка, которой нет у двойника с
    `pytest-own`, её исход `ok`; среди вызовов есть `config --services`,
    у которого `-f` — Compose-файл клона, `--env-file` — шаблон окружения
    клона; каждый вызов — в своей группе процессов, без `HOME` пульта и
    метки теста, с каталогами `machine.path` в `PATH`.

    Ловит мутацию: строка не добавлена в `all_checks`; `--env-file` берёт
    `compose_env_file` (файл, которого в клоне нет) вместо шаблона; вызов
    без `start_new_session` (группа теста); окружение — копия
    `os.environ` (видны `HOME` и метка); `PATH` без `machine.path`.
    """
    rng = random.Random(seed)
    project = make_project(rng, form)
    line, _all, _t, found = compose_line(project, pult, good_acts(project))
    note = f"зерно: {seed}; [{line.status}] {line.name}: {line.detail}"
    assert line.status == "ok", note
    fields = next(iter(project["profiles"].values()))
    configs = [r for r in found if r["kind"] == "compose config"]
    assert configs, note
    for rec in configs:
        argv = rec["argv"]
        assert "--services" in argv, f"{note}: {argv}"
        assert "--env-file" in argv, f"{note}: {argv}"
        env_file = argv[argv.index("--env-file") + 1]
        resolved = Path(rec["cwd"], env_file).resolve()
        assert resolved == (project["clone"] / fields["compose_env_template"]
                            ).resolve(), f"{note}: {argv} в {rec['cwd']}"
    assert [r for r in found if r["kind"] == "compose version"], note
    assert_hygiene(found, pult, project, note)


@pytest.mark.parametrize("field", ["compose_file", "compose_env_template"])
def test_ac3_missing_clone_file_fails(pult, seed, field):
    """Нет Compose-файла или шаблона окружения в клоне — строка `fail`.

    Сценарий: верная запись `compose`, файл поля не положен в клон;
    подменённый `docker` отвечает как для годной записи.

    Ловит мутацию: наличие файла в клоне не проверяется (исход решает
    только ответ подменённого `config --services`, а он годный).
    """
    rng = random.Random(seed)
    project = make_project(rng, missing={0: field})
    line, _all, _t, _found = compose_line(project, pult, good_acts(project))
    assert line.status == "fail", f"зерно: {seed}; {line}"


def test_ac3_service_missing_fails_with_name(pult, seed):
    """Сервиса записи нет в ответе `config --services` — `fail` с именем сервиса.

    Ловит мутацию: ответ `config --services` не сверяется с
    `compose_service`; сверка по вхождению подстроки (ответ несёт имя
    сервиса с лишним хвостом — его сочли бы найденным).
    """
    rng = random.Random(seed)
    project = make_project(rng)
    service = next(iter(project["profiles"].values()))["compose_service"]
    acts = good_acts(project)
    acts["compose config"] = {"stdout": f"{service}x\nother\n"}
    line, _all, _t, _found = compose_line(project, pult, acts)
    note = f"зерно: {seed}; {line}"
    assert line.status == "fail", note
    assert service in line.detail, note


def test_ac3_config_nonzero_fails_with_compose_text(pult, seed):
    """Ненулевой код `config --services` — `fail` с текстом Compose.

    Ловит мутацию: код возврата `config --services` не проверяется (пустой
    ответ — «сервиса нет» без текста Compose); текст ошибки не вносится в
    строку.
    """
    rng = random.Random(seed)
    project = make_project(rng)
    text = word(rng, "compose-error-", 10)
    acts = good_acts(project)
    acts["compose config"] = {"code": 15, "stderr": text + "\n"}
    line, _all, _t, _found = compose_line(project, pult, acts)
    note = f"зерно: {seed}; {line}"
    assert line.status == "fail", note
    assert text in line.detail, note


@pytest.mark.parametrize("answer,status,shown", [
    ("2.39.4-desktop.1", "ok", None),
    ("v2.39.4", "ok", None),
    ("v2.0.3", "fail", "2.0.3"),
    ("2.1.0", "fail", "2.1.0"),
    ("2.1.1", "ok", None),
])
def test_ac3_compose_version_floor(pult, seed, answer, status, shown):
    """Версия `docker compose version --short` не ниже 2.1.1; ниже — `fail` с найденной версией.

    Ловит мутацию: версия сравнивается строкой (`2.39.4` < `2.4`) или без
    учёта последней части (`2.1.0` принят); префикс `v` не снят (версия
    не разобрана — `fail` у `v2.39.4`); хвост `-desktop.1` не отрезан;
    найденная версия не названа в тексте.
    """
    rng = random.Random(seed)
    project = make_project(rng)
    acts = good_acts(project)
    acts["compose version"] = {"stdout": answer + "\n"}
    line, _all, _t, _found = compose_line(project, pult, acts)
    note = f"зерно: {seed}; ответ {answer}; {line}"
    assert line.status == status, note
    if shown is not None:
        assert shown in line.detail, note


def test_ac3_version_not_answering_fails(pult, seed):
    """`docker compose version` с ненулевым кодом — `fail` с текстом вызова.

    Ловит мутацию: ненулевой код `version` не проверяется, пустой или
    чужой ответ разбирается как версия; текст вызова не вносится в строку.
    """
    rng = random.Random(seed)
    project = make_project(rng)
    text = word(rng, "version-error-", 8)
    acts = good_acts(project)
    acts["compose version"] = {"code": 1, "stderr": text + "\n"}
    line, _all, _t, _found = compose_line(project, pult, acts)
    note = f"зерно: {seed}; {line}"
    assert line.status == "fail", note
    assert text in line.detail, note


def system_path_without_docker(nobin: Path) -> str:
    """PATH из одного каталога `nobin` со ссылками на программы системных
    каталогов, кроме `docker*`: на раннере CI `/usr/bin/docker` есть, и
    системные каталоги в PATH целиком его бы находили."""
    for system in ("/usr/bin", "/bin", "/usr/sbin", "/sbin"):
        src = Path(system)
        if not src.is_dir():
            continue
        for entry in src.iterdir():
            link = nobin / entry.name
            if entry.name.startswith("docker") or os.path.lexists(link):
                continue
            link.symlink_to(entry)
    return str(nobin)


def test_ac3_docker_not_found_fails(pult, seed, monkeypatch):
    """Программы `docker` в PATH нет — `fail` «программа docker не найдена».

    Ловит мутацию: отсутствие `docker` даёт `skip`/`warn` или исключение
    запуска вместо `fail` с этим текстом.
    """
    rng = random.Random(seed)
    project = make_project(rng)
    scenario(pult, {})
    base = rows(project, twin=True)
    monkeypatch.setenv("PATH", system_path_without_docker(pult["nobin"]))
    assert shutil.which("docker") is None, f"зерно: {seed}; docker в PATH"
    found = rows(project)
    extra = [c for n, c in found.items() if n not in base]
    note = f"зерно: {seed}; {extra}"
    assert len(extra) == 1, note
    assert extra[0].status == "fail", note
    assert NO_DOCKER in extra[0].detail, note


def test_ac3_two_components_one_line_names_broken(pult, seed):
    """Два компонента `compose`, у одного нет Compose-файла в клоне, — одна строка, `fail` с именем этого компонента.

    Ловит мутацию: строка на каждый компонент (строк две); проверяется
    только первый компонент записи; исход — исход последнего проверенного,
    а не худший; текст не называет компонент.
    """
    rng = random.Random(seed)
    index = rng.randrange(2)
    project = make_project(rng, "components", count=2,
                           missing={index: "compose_file"})
    broken = list(project["profiles"])[index]
    line, _all, _t, _found = compose_line(project, pult, good_acts(project))
    note = f"зерно: {seed}; сломан {broken}; {line}"
    assert line.status == "fail", note
    assert broken in line.detail, note


@pytest.mark.parametrize("hang", ["compose version", "compose config"])
def test_ac3_hanging_call_fails_and_group_removed(pult, seed, monkeypatch, hang):
    """Зависший вызов `docker` — `fail` с текстом вызова по пределу; группа вызова снята целиком.

    Сценарий: `DOCKER_CALL_TIMEOUT_SEC` подменён на 1; подменённый
    `docker` на вызове `hang` порождает дочерний процесс, пишет его pid и
    зависает (`exec sleep`). `all_checks` возвращается задолго до сна
    вызова; строка — `fail`; сразу после возврата `os.kill(<pid дочернего>,
    0)` поднимает `ProcessLookupError`; вызов — в своей группе процессов.

    Ловит мутацию: вызов без предела (тест висит до своего предела);
    предел прочитан при импорте (подмена не действует — 10 с на каждом
    вызове, дольше границы); по пределу снят только pid вызова (`proc.kill`)
    — дочерний процесс жив; ожидание исчезновения группы не делается —
    дочерний процесс ещё виден.
    """
    rng = random.Random(seed)
    project = make_project(rng)
    monkeypatch.setattr(doctor.project_checks, "DOCKER_CALL_TIMEOUT_SEC", 1)
    acts = good_acts(project)
    acts[hang] = {"hang": True}
    line, _all, elapsed, found = compose_line(project, pult, acts)
    hung = [r for r in found if r["kind"] == hang and "child" in r]
    note = f"зерно: {seed}; {line}; {elapsed:.1f} с"
    assert hung, note
    for rec in hung:
        with pytest.raises(ProcessLookupError):
            os.kill(rec["child"], 0)
    assert line.status == "fail", note
    assert elapsed < 9, note
    assert_hygiene(found, pult, project, note)


@pytest.mark.parametrize("code", [1, 125])
def test_ac3_nonzero_version_call_fails(pult, seed, code):
    """Вызов `docker compose version` вернул ненулевой код — `fail`, `doctor` не падает.

    Ловит мутацию: ненулевой код считается ответом (строка `ok` по
    пустому выводу или исключение разбора).
    """
    rng = random.Random(seed)
    project = make_project(rng)
    acts = good_acts(project)
    acts["compose version"] = {"code": code, "stdout": "2.39.4\n"}
    line, _all, _t, _found = compose_line(project, pult, acts)
    assert line.status == "fail", f"зерно: {seed}; {line}"


def test_ac3_group_gone_probes_constant_floor():
    """Константа числа проб группы без подмены не меньше 100 000.

    Ловит мутацию: малое число проб (ожидание исчезновения группы
    обрывается раньше, чем группа исчезнет на macOS).
    """
    assert doctor.project_checks.GROUP_GONE_PROBES >= 100000


def test_ac3_group_probes_exhausted_fail_without_exception(pult, seed,
                                                          monkeypatch):
    """Исчерпание проб группы после `SIGKILL` — ровно `GROUP_GONE_PROBES` проб сигналом 0, строка `fail`, исключения нет.

    Сценарий: `DOCKER_CALL_TIMEOUT_SEC` — 1, `GROUP_GONE_PROBES` — малое
    случайное число; подменён только `os.killpg`: сигнал 0 поднимает
    `PermissionError` (группа «ещё есть»), прочие сигналы уходят настоящей
    функции. Вызов `config --services` зависает. После `SIGKILL` группы
    вызова вызовов `os.killpg` этой группы с сигналом 0 — ровно подменённое
    число; строка — `fail`, `all_checks` не поднял исключения.

    Ловит мутацию: проба до `ProcessLookupError` без предела числа проб
    (бесконечный цикл); `PermissionError` трактуется как «группы нет»
    (проба одна); константа прочитана при импорте (проб 100 000);
    исчерпание поднимает исключение наружу.
    """
    rng = random.Random(seed)
    project = make_project(rng)
    probes = rng.randint(3, 9)
    monkeypatch.setattr(doctor.project_checks, "DOCKER_CALL_TIMEOUT_SEC", 1)
    monkeypatch.setattr(doctor.project_checks, "GROUP_GONE_PROBES", probes)
    acts = good_acts(project)
    acts["compose config"] = {"hang": True}
    scenario(pult, {})
    base = rows(project, twin=True)
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
        found = rows(project)
    finally:
        monkeypatch.setattr(os, "killpg", real_killpg)
    extra = [c for n, c in found.items() if n not in base]
    hung = [r for r in calls(pult) if "child" in r]
    note = f"зерно: {seed}; проб {probes}; {extra}; сигналы {sent[:20]}"
    assert len(extra) == 1, note
    assert hung, note
    group = hung[0]["pgrp"]
    kills = [i for i, (g, s) in enumerate(sent)
             if g == group and s == signal.SIGKILL]
    assert kills, note
    after = [s for g, s in sent[kills[0] + 1:] if g == group and s == 0]
    assert len(after) == probes, note
    assert extra[0].status == "fail", note


def test_ac3_role_environment_skips_without_docker(pult, seed, monkeypatch):
    """В процессе роли (`ARTEL_ROLE` выставлен) строка записи `compose` — `skip` «в шаге роли Docker не вызывается», `docker` не вызван.

    Ловит мутацию: признак процесса роли не проверяется — строка зовёт
    `docker` из шага роли; проверка только по `HOME` дома роли.
    """
    rng = random.Random(seed)
    project = make_project(rng)
    scenario(pult, good_acts(project))
    base = rows(project, twin=True)
    (pult["state"] / "calls.jsonl").unlink(missing_ok=True)
    monkeypatch.setenv(config.ARTEL_ROLE_ENV, "developer")
    assert runner.in_role_environment()
    found = rows(project)
    extra = [c for n, c in found.items() if n not in base]
    note = f"зерно: {seed}; {extra}"
    assert len(extra) == 1, note
    assert extra[0].status == "skip", note
    assert ROLE_SKIP in extra[0].detail, note
    assert calls(pult) == [], note
