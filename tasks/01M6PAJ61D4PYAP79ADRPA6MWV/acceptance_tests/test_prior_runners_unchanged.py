"""Прежние раннеры `pytest-own` и `pult-pytest`: argv, окружение и ключ итога побайтно прежние.

Группа: разовый

Факт этой задачи: введение раннера `compose` не сменило прогон прежних
раннеров. Эталон — формула базы ветки, записанная в тесте литералами
(`orchestrator/acceptance.py` до задачи: `_pytest_command`, `_pytest_env`,
`_place_command`, `_own_env`/`_own_path`, `_report_argv`, ключи
`suite_result_key`/`_own_suite_result_key`/`_report_suite_result_key`);
после мержа сверять её не с чем.

Команда профиля — исполнитель `pytest` во временном каталоге: пишет argv и
окружение в журнал и выходит с кодом 0. Подменённый `docker` в PATH теста
пишет свой журнал — вызовов у прежних раннеров быть не должно. Места:
`run_plank` (`pult-pytest` и `pytest-own`), `run_repeat` (`pytest-own`),
`report_run` (`pytest-own` с `report: junit-xml`); ключи — на базе (`base=True`)
и рабочего дерева у `pult-pytest`/`pytest-own`.

Зелёный с рождения: прогон прежних раннеров сегодня совпадает с формулой базы; тест краснеет, если правка задачи заденет argv, окружение или данные ключа `pytest-own`/`pult-pytest` (провалидировано на базе и под временным стабом раннера `compose`).
"""
import hashlib
import importlib.metadata
import json
import os
import random
import string
import sys
import tempfile
from pathlib import Path

import pytest

from orchestrator import acceptance, config, project_profile, stack, targets

OWN = targets.PROFILE_RUNNER_OWN
PULT = targets.PROFILE_RUNNER_DEFAULT
SYSTEM_DIRS = ("/usr/bin", "/bin", "/usr/sbin", "/sbin")
LAUNCH_NOISE = ("__PYVENV_LAUNCHER__",)
COERCED = ("C.UTF-8", "C.utf8", "UTF-8")

RECORDER = r'''#!@PYTHON@
import json
import os
import sys
with open(@LOG@, "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"argv": sys.argv[1:], "env": dict(os.environ)}) + "\n")
sys.exit(0)
'''


def word(rng, k=6):
    return "".join(rng.choices(string.ascii_lowercase, k=k))


def recorder(directory: Path, name: str, log: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(RECORDER.replace("@PYTHON@", sys.executable)
                    .replace("@LOG@", repr(str(log))), encoding="utf-8")
    path.chmod(0o755)
    return path


def records(log: Path) -> list:
    return [json.loads(line) for line in
            log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


def clean(env: dict) -> dict:
    """Окружение без переменных, которые ставит сам запуск интерпретатора."""
    return {k: v for k, v in env.items()
            if not k.startswith("__CF") and k not in LAUNCH_NOISE
            and not (k == "LC_CTYPE" and v in COERCED
                     and "LC_CTYPE" not in os.environ)}


@pytest.fixture
def scene(real_git, monkeypatch, tmp_path):
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    tree = Path(real_git.root)
    workdir = f"app_{word(rng)}"
    lld = f"{workdir}/tests"
    test_rel = f"{lld}/test_probe_{word(rng)}.py"
    (tree / lld).mkdir(parents=True)
    (tree / test_rel).write_text("def test_ok():\n    assert True\n",
                                 encoding="utf-8")
    real_git.git("add", "-A")
    real_git.git("commit", "-q", "-m", "учебный проект")
    log = tmp_path / "pytest.jsonl"
    docker_log = tmp_path / "docker.jsonl"
    head = recorder(tmp_path / "cmd", "pytest", log)
    docker = recorder(tmp_path / "dockerbin", "docker", docker_log)
    monkeypatch.setenv("PATH", os.pathsep.join(
        [str(docker.parent), os.environ.get("PATH", "")]))
    monkeypatch.setenv(f"ARTEL_PROBE_{word(rng).upper()}", word(rng))
    monkeypatch.delenv(config.ARTEL_ROLE_ENV, raising=False)
    # `LC_CTYPE` при локали «C» ставит сам интерпретатор записывающей
    # команды (PEP 538) — снят у теста, чтобы отличать его от переменной пульта.
    monkeypatch.delenv("LC_CTYPE", raising=False)
    tree_sha = real_git.git("rev-parse", "HEAD^{tree}").strip()
    return {"seed": seed, "tree": tree, "workdir": workdir, "lld": lld,
            "test_rel": test_rel, "log": log, "docker_log": docker_log,
            "head": str(head), "tree_sha": tree_sha, "git": real_git.git}


def own_profile(sc, report: str = "") -> project_profile.Profile:
    return project_profile.Profile(
        command=(sc["head"],), long_lived_dir=sc["lld"],
        long_lived_name="test_<id>_<name>.py",
        weakening_scope=(f"{sc['lld']}/**",),
        mutation_claim_scope=(f"{sc['lld']}/**",), report=report,
        runner=OWN, workdir=sc["workdir"], component="default")


def pult_profile(sc) -> project_profile.Profile:
    return project_profile.Profile(
        command=(sc["head"],), long_lived_dir="tests",
        long_lived_name="test_<id>_<name>.py", weakening_scope=("tests/**",),
        mutation_claim_scope=("tests/**",), runner=PULT)


def pult_tail() -> list:
    return ["-p", "no:cacheprovider", "-p", "timeout",
            "-o", f"timeout={stack.PER_TEST_TIMEOUT_SEC}"]


def own_path(head: str, caller: str) -> str:
    parts = caller.split(os.pathsep) if caller else []
    for directory in (os.path.dirname(head), *SYSTEM_DIRS):
        if directory not in parts:
            parts.append(directory)
    return os.pathsep.join(parts)


def assert_own_env(env: dict, sc, where: str, extra_keys=()) -> None:
    env = clean(env)
    want = {name: os.environ[name] for name in ("LANG", "LC_ALL")
            if name in os.environ}
    want["PATH"] = own_path(sc["head"], os.environ.get("PATH", ""))
    want["TMPDIR"] = os.environ.get("TMPDIR") or tempfile.gettempdir()
    keys = set(want) | {"HOME", "PYTHONPYCACHEPREFIX", *extra_keys}
    assert set(env) == keys, f"{where}: {sorted(env)} != {sorted(keys)}"
    for key, value in want.items():
        assert env[key] == value, f"{where}: {key}"
    assert os.path.basename(env["HOME"]).startswith("artel-own-home-"), where
    assert os.path.basename(env["PYTHONPYCACHEPREFIX"]).startswith(
        "artel-pycache-"), where


def test_ac16_pult_pytest_plank_argv_and_env_unchanged(scene):
    """`pult-pytest`: argv `run_plank` — команда, цель и флаги пульта; окружение — копия окружения пульта плюс `PYTHONPYCACHEPREFIX`.

    Ловит мутацию: правка задачи добавила к argv `pult-pytest` аргумент
    (`--junitxml`, `-p no:…` раннера `compose`) или сменила его
    окружение (снятие переменных пульта, `DOCKER_*`); `docker` вызван.
    """
    sc = scene
    where = f"зерно {sc['seed']}"
    code, output = acceptance.run_plank([sc["test_rel"]], sc["tree"],
                                        profile=pult_profile(sc))
    (rec,) = records(sc["log"])
    assert rec["argv"] == [sc["test_rel"], *pult_tail()], f"{where}: {rec['argv']}"
    env = clean(rec["env"])
    prefix = env.pop("PYTHONPYCACHEPREFIX", "")
    assert os.path.basename(prefix).startswith("artel-pycache-"), where
    caller = clean(dict(os.environ))
    caller.pop("PYTHONPYCACHEPREFIX", None)
    assert env == caller, where
    assert records(sc["docker_log"]) == [], where


def test_ac16_pytest_own_places_argv_and_env_unchanged(scene):
    """`pytest-own`: argv `run_plank`/`run_repeat`/`report_run` и их окружение — прежняя формула.

    `run_plank`: `<команда> <цель от workdir> -p no:cacheprovider`;
    `run_repeat`: `<команда> <цель> --junitxml=<файл> -o
    junit_logging=system-out -p no:cacheprovider`; `report_run` профиля с
    `report: junit-xml`: `<команда> <цель> -p no:cacheprovider --junitxml
    <файл>`. Окружение — `PATH` (PATH вызывающего, каталог команды,
    системный хвост), `LANG`/`LC_ALL` пульта, `TMPDIR`, свои `HOME` и
    `PYTHONPYCACHEPREFIX`; `docker` не вызван.

    Ловит мутацию: правка задачи сменила `_own_env` (например, общий
    помощник окружения с раннером `compose` снял PATH вызывающего или
    добавил `DOCKER_CONFIG`) или `_report_argv` прежних раннеров.
    """
    sc = scene
    where = f"зерно {sc['seed']}"
    target = os.path.relpath(sc["test_rel"], sc["workdir"])
    acceptance.run_plank([sc["test_rel"]], sc["tree"], profile=own_profile(sc))
    acceptance.run_repeat([sc["test_rel"]], sc["tree"], command=own_profile(sc))
    acceptance.report_run(own_profile(sc, "junit-xml"), sc["tree"],
                          [sc["test_rel"]], 60.0)
    plank, repeat, report = records(sc["log"])
    assert plank["argv"] == [target, "-p", "no:cacheprovider"], where
    assert repeat["argv"][0] == target and repeat["argv"][2:] == [
        "-o", "junit_logging=system-out", "-p", "no:cacheprovider"], where
    assert repeat["argv"][1].startswith("--junitxml="), where
    assert report["argv"][:3] == [target, "-p", "no:cacheprovider"], where
    assert report["argv"][3] == "--junitxml" and len(report["argv"]) == 5, \
        f"{where}: {report['argv']}"
    for label, rec in (("run_plank", plank), ("run_repeat", repeat),
                       ("report_run", report)):
        assert_own_env(rec["env"], sc, f"{where}: {label}")
    assert records(sc["docker_log"]) == [], where


def digest(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True,
                                     ensure_ascii=False).encode()).hexdigest()


def packages() -> list:
    return sorted((d.metadata["Name"].lower(), d.version)
                  for d in importlib.metadata.distributions())


def test_ac16_result_keys_unchanged(scene):
    """Ключи итога `pult-pytest`, `pytest-own` и `pytest-own` с отчётом — прежние данные ключа побайтно.

    Ловит мутацию: в данные ключа прежних раннеров вошли поля `compose_*`
    (пустые), константа правила перекрытия или иной новый элемент — ключ
    сменился, сохранённые итоги полного набора прежних проектов перестали
    находиться.
    """
    sc = scene
    tree, head = sc["tree_sha"], sc["head"]
    where = f"зерно {sc['seed']}"
    pult = pult_profile(sc)
    want_base = digest({"tree": tree, "python": sys.version,
                        "packages": packages(), "command": [head, *pult_tail()]})
    want_work = digest({"tree": tree, "python": sys.version,
                        "packages": packages(),
                        "command": [head, "tests", *pult_tail(), "-n",
                                    str(config.FULL_SUITE_WORKERS), "-p",
                                    "xdist"]})
    assert acceptance.suite_result_key(tree, pult, base=True) == want_base, where
    assert acceptance.suite_result_key(tree, pult) == want_work, where
    own = own_profile(sc)
    target = os.path.relpath(sc["lld"], sc["workdir"])
    for base, command in ((True, [head, "-p", "no:cacheprovider"]),
                          (False, [head, target, "-p", "no:cacheprovider"])):
        want = digest({"tree": tree, "python": sys.version,
                       "packages": packages(), "command": command,
                       "runner": OWN, "workdir": sc["workdir"], "env": {}})
        assert acceptance.suite_result_key(tree, own, base=base) == want, \
            f"{where}: base={base}"
    reported = own_profile(sc, "junit-xml")
    want = digest({"tree": tree, "base": True, "locks": None, "tools": {},
                   "command": [head], "report": "junit-xml",
                   "report_args": ["--junitxml", "{path}"], "select": [],
                   "component": "default", "runner": OWN,
                   "workdir": sc["workdir"], "env": {}})
    assert acceptance.report_suite_result_key(tree, reported, True) == want, where
    assert acceptance.suite_result_key(tree, reported, base=True) == want, where
