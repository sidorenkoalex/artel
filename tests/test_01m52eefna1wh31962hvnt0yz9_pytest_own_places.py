"""Раннер `runner: pytest-own` в восьми местах запуска pytest пульта:
команда профиля, рабочий каталог `workdir`, чистое окружение, временный
`HOME`, снятие группы процессов, отказ `workdir` со ссылкой наружу, цели
полного набора и ключ его сохранённого итога.

Группа: долгоживущий

Восемь мест: `acceptance.run`, `acceptance.collect`,
`acceptance.run_repeat`, `acceptance.run_plank`, прогон полного набора без
наблюдения, с наблюдением (`acceptance.observed_full_suite()`) и в файл
лога (`log=`) — через публичный `acceptance.run_full_suite`, сторона
двустороннего прогона — через `two_sided.run` на настоящем репозитории
песочницы (`tests.sandbox.RealGitSandbox`: связка «git worktree стороны —
прогон в нём»).

Канал профиля (SPEC, требование 1): у мест с параметром `command` профиль
передаётся этим параметром (`command=<Profile>`), если у функции нет
отдельного параметра `profile`; у `run_plank` и `two_sided.run` —
параметром `profile`, а без него — единственным параметром, которого у
функции не было до задачи (`RUN_PLANK_PARAMS`, `TWO_SIDED_RUN_PARAMS`).

Учебный проект — во временном каталоге песочницы: каталог `workdir`
(`wd_<случайно>`), в нём каталог долгоживущих тестов с модулем-зондом;
команда профиля — исполняемая обёртка вне дерева прогона. Обёртка пишет
свой argv, `cwd` и окружение в каталог зонда, порождает дочерний процесс
(держит открытым конец записи именованного канала зонда), затем зовёт
pytest интерпретатором пульта с аргументами места запуска. Режим
`sleep` — обёртка спит дольше предела прогона (таймаут); режим `signal`
— обёртка шлёт процессу теста `SIGUSR1`, обработчик которого поднимает
исключение на прогоне. Дочерний процесс мёртв, когда читатель канала
получил конец файла: событие, а не пауза.

Переменные пульта на время вызова дополнены случайными (`ARTEL_LEAK_*`,
`PYTHONPATH`), переменные `test_profile.env` — тоже случайные; зерно
печатается и входит в текст провала.

Красен до реализации: места запуска не знают профиля — `run_plank` и `two_sided.run` не принимают его вовсе, остальные запускают команду интерпретатором пульта с `-p timeout`/`-n` в корне и с окружением пульта, `HOME` прогона — `HOME` пульта, группа процессов точечных прогонов не снимается, ключ итога не видит `runner`/`workdir`/`env`.
"""
import dataclasses
import inspect
import json
import os
import random
import select
import shutil
import signal
import stat
import string
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import MappingProxyType
from unittest import mock

from orchestrator import acceptance, config, project_profile, stack, targets
from orchestrator.advance_gates import two_sided
from tests.sandbox import RealGitSandbox

OWN = targets.PROFILE_RUNNER_OWN
PULT = targets.PROFILE_RUNNER_DEFAULT
PLACES = ("acceptance.run", "acceptance.collect", "acceptance.run_repeat",
          "acceptance.run_plank", "_run_full_suite_now без observe",
          "_run_full_suite_now с observe", "_run_full_suite_to_log",
          "two_sided._run_side")
FULL_PLACES = PLACES[4:7]
TWO_SIDED = PLACES[7]
# Доли `PLACES` у тестов, гоняющих каждое место настоящим прогоном
# (SPEC 01M5H1A4GS19TPR4RJ8XRVVYZQ): по методу на долю `[i::PLACE_SHARES]`.
PLACE_SHARES = 4
# Параметры `run_plank` и `two_sided.run` до задачи: новый параметр
# профиля — тот, которого среди них нет.
RUN_PLANK_PARAMS = ("targets", "cwd")
TWO_SIDED_RUN_PARAMS = ("repo", "code_branch", "base_sha", "methods",
                        "deadline")
# Перечень требования 5 SPEC: что окружение прогона `pytest-own` вправе
# нести помимо `test_profile.env`; у двустороннего прогона — ещё
# переменные плагина и отчёта.
ALLOWED_VARS = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL",
                "PYTHONPYCACHEPREFIX", "PYTHONUNBUFFERED")
TWO_SIDED_VARS = ("PYTHONPATH", two_sided.REPORT_ENV)
# Ставит себе сам процесс учебного проекта, а не передаёт место запуска:
# CoreFoundation macOS и приведение C-локали интерпретатора (PEP 538).
SELF_SET_VARS = ("__CF_USER_TEXT_ENCODING", "LC_CTYPE")
TIMEOUT_SEC = 2
SLEEP_SEC = 30
CHILD_GUARD_SEC = 20
PS_ROW = "1 0 0.0 00:01 /bin/probe\n"

WRAPPER = '''#!{python}
import json, os, subprocess, sys, time

opts, args = {{}}, []
for arg in sys.argv[1:]:
    if arg.startswith("--probe-") and "=" in arg:
        key, _, value = arg[2:].partition("=")
        opts[key] = value
    else:
        args.append(arg)
probe = opts["probe-dir"]
home = os.environ.get("HOME", "")
record = {{"argv": sys.argv, "cwd": os.getcwd(), "env": dict(os.environ),
          "home_isdir": bool(home) and os.path.isdir(home)}}
with open(os.path.join(probe, "wrapper.jsonl"), "a", encoding="utf-8") as fh:
    fh.write(json.dumps(record) + "\\n")
fifo = os.open(os.path.join(probe, "fifo"), os.O_WRONLY)
child = subprocess.Popen(
    [sys.executable, "-c", "import time; time.sleep({sleep})"],
    pass_fds=(fifo,), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL)
with open(os.path.join(probe, "pids"), "a", encoding="utf-8") as fh:
    fh.write(f"{{child.pid}}\\n{{os.getpid()}}\\n")
mode = opts.get("probe-mode", "pass")
if mode == "signal":
    os.kill(int(opts["probe-pult"]), {signum})
if mode in ("signal", "sleep"):
    time.sleep({sleep})
code = subprocess.call([sys.executable, "-m", "pytest", *args],
                       env=dict(os.environ, PROBE_DIR=probe))
child.kill()
child.wait()
sys.exit(code)
'''

MODULE = '''import json
import os
import unittest

_PROBE = os.environ.get("PROBE_DIR")
if _PROBE:
    with open(os.path.join(_PROBE, "module.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"env": dict(os.environ)}) + "\\n")


class ProbeTest(unittest.TestCase):
    def test_probe(self):
        self.assertTrue(True)
'''


class ProbeInterrupt(Exception):
    """Исключение на прогоне: поднимает обработчик `SIGUSR1` процесса теста."""


def own_profile(command, long_lived_dir: str, workdir: str, env: dict,
                runner: str = OWN) -> project_profile.Profile:
    return project_profile.Profile(
        command=tuple(command), long_lived_dir=long_lived_dir,
        long_lived_name="test_<id>_<name>.py",
        weakening_scope=(f"{long_lived_dir}/**",),
        mutation_claim_scope=(f"{long_lived_dir}/**",),
        runner=runner, workdir=workdir, env=MappingProxyType(dict(env)))


def via_command(func, profile) -> dict:
    """Профиль места с параметром `command` — тем же каналом (требование 1)."""
    params = inspect.signature(func).parameters
    return {"profile": profile} if "profile" in params else {"command": profile}


def via_new_param(func, profile, known: tuple) -> dict:
    """Профиль места без параметра `command` — новым необязательным параметром."""
    params = inspect.signature(func).parameters
    if "profile" in params:
        return {"profile": profile}
    new = [name for name, p in params.items() if name not in known
           and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)]
    if len(new) != 1:
        raise AssertionError(f"{func.__qualname__}: нет параметра профиля "
                             f"(параметры: {list(params)})")
    return {new[0]: profile}


def resolves_to(arg: str, cwd, target) -> bool:
    """Аргумент `arg` из каталога `cwd` указывает на `target`."""
    path = arg.split("::")[0]
    return os.path.realpath(os.path.join(str(cwd), path)) == \
        os.path.realpath(str(target))


def has_pair(argv: list, first: str, second: str) -> bool:
    return any(argv[i] == first and argv[i + 1] == second
               for i in range(len(argv) - 1))


def places_share(index: int) -> list:
    """Доля `index` мест: сортированная копия `PLACES`, срез
    `[index::PLACE_SHARES]`. Сам литерал и его порядок не трогаются — от
    них зависят `FULL_PLACES` и `TWO_SIDED`."""
    return sorted(PLACES)[index::PLACE_SHARES]


class ProbeRun:
    """Каталог зонда одного вызова места: записи обёртки и модуля,
    именованный канал дочернего процесса, перечень процессов на уборку."""

    def __init__(self, case: unittest.TestCase):
        self.dir = Path(tempfile.mkdtemp(prefix="artel-probe-")).resolve()
        case.addCleanup(shutil.rmtree, self.dir, True)
        fifo = self.dir / "fifo"
        os.mkfifo(fifo)
        self.reader = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
        case.addCleanup(os.close, self.reader)
        case.addCleanup(self.kill_all)

    def command(self, wrapper: Path, mode: str) -> tuple:
        return (str(wrapper), f"--probe-dir={self.dir}",
                f"--probe-mode={mode}", f"--probe-pult={os.getpid()}")

    def records(self, name: str) -> list:
        path = self.dir / name
        if not path.is_file():
            return []
        return [json.loads(line) for line in
                path.read_text(encoding="utf-8").splitlines() if line]

    def children_gone(self) -> bool:
        """Все держатели конца записи канала мертвы: читатель видит конец
        файла. Предел ожидания — страховка от зависания, не условие."""
        while True:
            ready, _, _ = select.select([self.reader], [], [], CHILD_GUARD_SEC)
            if not ready:
                return False
            try:
                if os.read(self.reader, 4096) == b"":
                    return True
            except BlockingIOError:
                continue

    def kill_all(self) -> None:
        path = self.dir / "pids"
        if not path.is_file():
            return
        for line in path.read_text(encoding="utf-8").split():
            try:
                os.kill(int(line), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, ValueError):
                pass


class FakeProc:
    pid = 2_000_000_000
    returncode = 0
    stdout = stderr = stdin = None

    def __init__(self, argv):
        self.args = argv

    def communicate(self, input=None, timeout=None):
        return "1 passed in 0.01s", ""

    def wait(self, timeout=None):
        return 0

    def poll(self):
        return 0

    def kill(self):
        pass

    terminate = kill

    def send_signal(self, sig):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeSubprocess:
    """Замена модуля `subprocess` у `acceptance` и `two_sided`: вызовы
    pytest (`run` и `Popen`) запоминаются с argv, `cwd` и ближайшим к `cwd`
    корнем git в момент вызова; прочие `run` (`/bin/ps`) — строка процесса."""

    PIPE = subprocess.PIPE
    STDOUT = subprocess.STDOUT
    DEVNULL = subprocess.DEVNULL
    TimeoutExpired = subprocess.TimeoutExpired
    SubprocessError = subprocess.SubprocessError
    CalledProcessError = subprocess.CalledProcessError
    CompletedProcess = subprocess.CompletedProcess

    def __init__(self):
        self.calls: list = []

    def remember(self, argv, kwargs) -> bool:
        argv = [str(a) for a in argv]
        if "pytest" not in argv:
            return False
        cwd = kwargs.get("cwd")
        git_root = None
        if cwd is not None:
            for parent in (Path(cwd), *Path(cwd).parents):
                if (parent / ".git").exists():
                    git_root = parent
                    break
        self.calls.append({"argv": argv, "cwd": cwd, "git_root": git_root})
        return True

    def run(self, argv, **kwargs):
        if not self.remember(argv, kwargs):
            return subprocess.CompletedProcess(argv, 0, PS_ROW, "")
        return subprocess.CompletedProcess(argv, 0, "1 passed in 0.01s", "")

    def Popen(self, argv, **kwargs):
        self.remember(argv, kwargs)
        return FakeProc(argv)


class PytestOwnProjectTest(RealGitSandbox):
    """Учебный проект `pytest-own` в репозитории песочницы."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.workdir = f"wd_{self.word()}"
        self.checks = f"{self.workdir}/checks_{self.word()}"
        self.module_rel = f"{self.checks}/test_probe_{self.word()}.py"
        module = self.root / self.module_rel
        module.parent.mkdir(parents=True)
        module.write_text(MODULE, encoding="utf-8")
        outside = Path(tempfile.mkdtemp(prefix="artel-wrapper-")).resolve()
        self.addCleanup(shutil.rmtree, outside, True)
        self.wrapper = outside / "run-tests"
        self.wrapper.write_text(WRAPPER.format(
            python=stack.pytest_python_executable(), sleep=SLEEP_SEC,
            signum=int(signal.SIGUSR1)), encoding="utf-8")
        self.wrapper.chmod(self.wrapper.stat().st_mode | stat.S_IXUSR)
        self.profile_env = {f"PROBE_ENV_{self.word().upper()}": self.word(12)
                            for _ in range(self.rng.randint(1, 3))}
        self.commit("учебный проект")
        self.homes: list = []

    def word(self, k: int = 6) -> str:
        return "".join(self.rng.choices(string.ascii_lowercase, k=k))

    def where(self, place: str) -> str:
        return f"{place}, зерно {self.seed}"

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        self.branch = f"probe-{self.word()}"
        self.git("branch", self.branch)
        self.base_sha = self.git("rev-parse", "HEAD").strip()

    def method(self) -> two_sided.Method:
        source = MODULE
        return two_sided.Method(self.module_rel, self.module_rel,
                                "ProbeTest::test_probe", source, source)

    def profile(self, command, **over) -> project_profile.Profile:
        values = {"long_lived_dir": self.checks, "workdir": self.workdir,
                  "env": self.profile_env}
        values.update(over)
        return own_profile(command, **values)

    def invoke(self, place: str, profile, scratch: Path, limit=None,
               targets_arg=None):
        """Вызов места `place` с профилем `profile` через публичный вход."""
        module = str(self.root / self.module_rel)
        if place == "acceptance.run":
            return acceptance.run(scratch, cwd=self.root, extra=[module],
                                  file_times={},
                                  **via_command(acceptance.run, profile))
        if place == "acceptance.collect":
            return acceptance.collect(scratch, cwd=self.root, extra=[module],
                                      **via_command(acceptance.collect, profile))
        if place == "acceptance.run_repeat":
            return acceptance.run_repeat(
                [module], self.root,
                **via_command(acceptance.run_repeat, profile))
        if place == "acceptance.run_plank":
            return acceptance.run_plank(
                [module], self.root,
                **via_new_param(acceptance.run_plank, profile,
                                RUN_PLANK_PARAMS))
        if place == TWO_SIDED:
            return two_sided.run(
                self.root, self.branch, self.base_sha, [self.method()],
                **via_new_param(two_sided.run, profile, TWO_SIDED_RUN_PARAMS))
        kwargs = via_command(acceptance.run_full_suite, profile)
        if limit is not None:
            kwargs["limit"] = limit
        if targets_arg is not None:
            kwargs["targets"] = targets_arg
        if place == FULL_PLACES[2]:
            kwargs["log"] = scratch / "suite.log"
        if place == FULL_PLACES[0]:
            return acceptance.run_full_suite(self.root, **kwargs)
        with acceptance.observed_full_suite():
            return acceptance.run_full_suite(self.root, **kwargs)

    def scenario(self, place: str, mode: str) -> dict:
        """Настоящий прогон места `place` в режиме обёртки `mode` (`pass`,
        `sleep` — таймаут, `signal` — исключение на прогоне)."""
        probe = ProbeRun(self)
        profile = self.profile(probe.command(self.wrapper, mode))
        leak = {f"ARTEL_LEAK_{self.word().upper()}": self.word(12)
                for _ in range(self.rng.randint(1, 3))}
        leak["PYTHONPATH"] = f"/{self.word(10)}"
        raised = []

        def interrupt(signum, frame):
            raised.append(signum)
            raise ProbeInterrupt("исключение на прогоне")

        previous = signal.signal(signal.SIGUSR1, interrupt)
        self.addCleanup(signal.signal, signal.SIGUSR1, previous)
        timeout = TIMEOUT_SEC if mode == "sleep" else None
        error = result = None
        with mock.patch.dict(os.environ, leak), \
                mock.patch.object(config, "ACCEPTANCE_TIMEOUT_SEC",
                                  timeout or config.ACCEPTANCE_TIMEOUT_SEC), \
                mock.patch.object(config, "TWO_SIDED_PYTEST_TIMEOUT_SEC",
                                  timeout or config.TWO_SIDED_PYTEST_TIMEOUT_SEC):
            pult_env = dict(os.environ)
            try:
                result = self.invoke(place, profile, probe.dir,
                                     limit=(timeout, "тест") if timeout else None)
            except ProbeInterrupt as exc:
                error = exc
        signal.signal(signal.SIGUSR1, previous)
        if mode == "signal":
            self.assertTrue(raised, f"{self.where(place)}: обёртка не подала "
                                    f"сигнал — прогон не запускался")
        return {"probe": probe, "result": result, "error": error,
                "pult_env": pult_env, "leak": leak}

    def wrapper_records(self, place: str, run: dict) -> list:
        records = run["probe"].records("wrapper.jsonl")
        self.assertTrue(records, f"{self.where(place)}: команда профиля не "
                                 f"запускалась: {run['result']!r}")
        return records

    def check_home(self, place: str, run: dict, outcome: str) -> None:
        """`HOME` прогона — новый временный каталог, после исхода его нет."""
        where = f"{self.where(place)}, исход «{outcome}»"
        for record in self.wrapper_records(place, run):
            home = record["env"].get("HOME", "")
            self.assertTrue(record["home_isdir"],
                            f"{where}: HOME={home!r} не каталог на прогоне")
            self.assertNotEqual(home, run["pult_env"].get("HOME"),
                                f"{where}: HOME прогона — HOME пульта")
            self.assertNotIn(home, self.homes,
                             f"{where}: HOME={home} уже был у другого прогона")
            self.homes.append(home)
            self.assertFalse(os.path.exists(home),
                             f"{where}: HOME={home} не удалён после прогона")


class PytestOwnEnvironmentTest(PytestOwnProjectTest):
    """Окружение и `HOME` прогона `pytest-own` — настоящие прогоны."""

    def test_ac2_env_only_allowed_profile_env_and_pycache(self):
        """Тест учебного проекта видит только перечень требования 5, `test_profile.env` и `PYTHONPYCACHEPREFIX`.

        Каждое из восьми мест запускает учебный проект с `pytest-own`; в
        окружении пульта на время вызова — случайные `ARTEL_LEAK_*` и
        случайный `PYTHONPATH`. Окружение обёртки (команды профиля) не
        несёт ни одной переменной пульта с её значением вне перечня
        требования 5 (у двустороннего прогона — ещё `PYTHONPATH` без
        значения пульта и путь отчёта). Модуль-зонд теста не видит
        `ARTEL_LEAK_*`, видит каждую переменную `test_profile.env` с её
        значением и непустой `PYTHONPYCACHEPREFIX`.

        Ловит мутацию: окружение `pytest-own` собрано копией `os.environ`
        (`dict(os.environ)` как у `pult-pytest`), `test_profile.env` не
        добавлен или `PYTHONPYCACHEPREFIX` не выставлен — модуль увидит
        `ARTEL_LEAK_*`, не увидит переменную профиля или кеш байткода;
        `_run_side` дописывает плагин к `PYTHONPATH` пульта — в
        `PYTHONPATH` прогона окажется значение пульта.
        """
        for place in PLACES:
            with self.subTest(place=place, seed=self.seed):
                run = self.scenario(place, "pass")
                allowed = set(ALLOWED_VARS) | set(self.profile_env)
                if place == TWO_SIDED:
                    allowed |= set(TWO_SIDED_VARS)
                for record in self.wrapper_records(place, run):
                    env = record["env"]
                    seen = sorted(k for k, v in run["pult_env"].items()
                                  if k not in allowed and k not in SELF_SET_VARS
                                  and env.get(k) == v)
                    self.assertEqual(seen, [], f"{self.where(place)}: "
                                               f"переменные пульта в прогоне")
                    self.assertNotIn(run["leak"]["PYTHONPATH"],
                                     env.get("PYTHONPATH", "").split(os.pathsep),
                                     f"{self.where(place)}: PYTHONPATH пульта")
                modules = run["probe"].records("module.jsonl")
                self.assertTrue(modules, f"{self.where(place)}: тест учебного "
                                         f"проекта не исполнялся: "
                                         f"{run['result']!r}")
                for record in modules:
                    env = record["env"]
                    for key in run["leak"]:
                        if key != "PYTHONPATH":
                            self.assertNotIn(key, env, self.where(place))
                    for key, value in self.profile_env.items():
                        self.assertEqual(env.get(key), value,
                                         f"{self.where(place)}: {key} "
                                         f"test_profile.env")
                    self.assertTrue(env.get("PYTHONPYCACHEPREFIX"),
                                    f"{self.where(place)}: нет "
                                    f"PYTHONPYCACHEPREFIX")

    def test_ac3_home_fresh_and_removed_after_completion(self):
        """Завершённый прогон: `HOME` — свой новый каталог, после прогона удалён.

        Восемь мест, режим обёртки `pass`: на прогоне `HOME` — каталог,
        не `HOME` пульта и не `HOME` любого другого прогона теста (у
        двустороннего — у каждой стороны свой); после возврата места
        каталога нет.

        Ловит мутацию: `HOME` прогона — `HOME` пульта, общий каталог на
        несколько прогонов или временный каталог не убирается после
        прогона — совпадение с прежним `HOME` или каталог существует после
        возврата.

        Сценарий доли: места `PLACES` по сортировке копии перечня делятся
        на `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        0 (её непустоту утверждает `assertTrue`) — в доле не меньше
        двух прогонов, так что проверка «HOME не общий у нескольких
        прогонов» держится в каждой доле; прочие доли — у метода без
        суффикса и методов с суффиксом `_share<i>`.
        """
        share = places_share(0)
        self.assertTrue(share)
        for place in share:
            with self.subTest(place=place, seed=self.seed):
                self.check_home(place, self.scenario(place, "pass"),
                                "прогон завершился")

    def test_ac3_home_fresh_and_removed_after_completion_share1(self):
        """Завершённый прогон: `HOME` — свой новый каталог, после прогона удалён.

        Восемь мест, режим обёртки `pass`: на прогоне `HOME` — каталог,
        не `HOME` пульта и не `HOME` любого другого прогона теста (у
        двустороннего — у каждой стороны свой); после возврата места
        каталога нет.

        Ловит мутацию: `HOME` прогона — `HOME` пульта, общий каталог на
        несколько прогонов или временный каталог не убирается после
        прогона — совпадение с прежним `HOME` или каталог существует после
        возврата.

        Сценарий доли: места `PLACES` по сортировке копии перечня делятся
        на `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        1 (её непустоту утверждает `assertTrue`) — в доле не меньше
        двух прогонов, так что проверка «HOME не общий у нескольких
        прогонов» держится в каждой доле; прочие доли — у метода без
        суффикса и методов с суффиксом `_share<i>`.
        """
        share = places_share(1)
        self.assertTrue(share)
        for place in share:
            with self.subTest(place=place, seed=self.seed):
                self.check_home(place, self.scenario(place, "pass"),
                                "прогон завершился")

    def test_ac3_home_fresh_and_removed_after_completion_share2(self):
        """Завершённый прогон: `HOME` — свой новый каталог, после прогона удалён.

        Восемь мест, режим обёртки `pass`: на прогоне `HOME` — каталог,
        не `HOME` пульта и не `HOME` любого другого прогона теста (у
        двустороннего — у каждой стороны свой); после возврата места
        каталога нет.

        Ловит мутацию: `HOME` прогона — `HOME` пульта, общий каталог на
        несколько прогонов или временный каталог не убирается после
        прогона — совпадение с прежним `HOME` или каталог существует после
        возврата.

        Сценарий доли: места `PLACES` по сортировке копии перечня делятся
        на `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        2 (её непустоту утверждает `assertTrue`) — в доле не меньше
        двух прогонов, так что проверка «HOME не общий у нескольких
        прогонов» держится в каждой доле; прочие доли — у метода без
        суффикса и методов с суффиксом `_share<i>`.
        """
        share = places_share(2)
        self.assertTrue(share)
        for place in share:
            with self.subTest(place=place, seed=self.seed):
                self.check_home(place, self.scenario(place, "pass"),
                                "прогон завершился")

    def test_ac3_home_fresh_and_removed_after_completion_share3(self):
        """Завершённый прогон: `HOME` — свой новый каталог, после прогона удалён.

        Восемь мест, режим обёртки `pass`: на прогоне `HOME` — каталог,
        не `HOME` пульта и не `HOME` любого другого прогона теста (у
        двустороннего — у каждой стороны свой); после возврата места
        каталога нет.

        Ловит мутацию: `HOME` прогона — `HOME` пульта, общий каталог на
        несколько прогонов или временный каталог не убирается после
        прогона — совпадение с прежним `HOME` или каталог существует после
        возврата.

        Сценарий доли: места `PLACES` по сортировке копии перечня делятся
        на `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        3 (её непустоту утверждает `assertTrue`) — в доле не меньше
        двух прогонов, так что проверка «HOME не общий у нескольких
        прогонов» держится в каждой доле; прочие доли — у метода без
        суффикса и методов с суффиксом `_share<i>`.
        """
        share = places_share(3)
        self.assertTrue(share)
        for place in share:
            with self.subTest(place=place, seed=self.seed):
                self.check_home(place, self.scenario(place, "pass"),
                                "прогон завершился")

    def test_ac3_home_removed_after_timeout_and_exception(self):
        """Таймаут и исключение на прогоне: `HOME` прогона после исхода удалён.

        Восемь мест, режимы обёртки `sleep` (предел прогона
        `TIMEOUT_SEC`, обёртка спит дольше) и `signal` (обработчик
        `SIGUSR1` поднимает исключение, пока место ждёт прогон): на
        прогоне `HOME` — новый каталог, после возврата или исключения
        места каталога нет.

        Ловит мутацию: уборка временного `HOME` стоит после ожидания
        прогона, а не в `finally` — по `TimeoutExpired` или исключению
        каталог остаётся.

        Сценарий доли: места `PLACES` по сортировке копии перечня делятся
        на `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        0 (её непустоту утверждает `assertTrue`) — в доле не меньше
        двух прогонов, так что проверка «HOME не общий у нескольких
        прогонов» держится в каждой доле; прочие доли — у метода без
        суффикса и методов с суффиксом `_share<i>`.
        """
        share = places_share(0)
        self.assertTrue(share)
        for mode, outcome in (("sleep", "таймаут"), ("signal", "исключение")):
            for place in share:
                with self.subTest(place=place, mode=mode, seed=self.seed):
                    self.check_home(place, self.scenario(place, mode), outcome)

    def test_ac3_home_removed_after_timeout_and_exception_share1(self):
        """Таймаут и исключение на прогоне: `HOME` прогона после исхода удалён.

        Восемь мест, режимы обёртки `sleep` (предел прогона
        `TIMEOUT_SEC`, обёртка спит дольше) и `signal` (обработчик
        `SIGUSR1` поднимает исключение, пока место ждёт прогон): на
        прогоне `HOME` — новый каталог, после возврата или исключения
        места каталога нет.

        Ловит мутацию: уборка временного `HOME` стоит после ожидания
        прогона, а не в `finally` — по `TimeoutExpired` или исключению
        каталог остаётся.

        Сценарий доли: места `PLACES` по сортировке копии перечня делятся
        на `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        1 (её непустоту утверждает `assertTrue`) — в доле не меньше
        двух прогонов, так что проверка «HOME не общий у нескольких
        прогонов» держится в каждой доле; прочие доли — у метода без
        суффикса и методов с суффиксом `_share<i>`.
        """
        share = places_share(1)
        self.assertTrue(share)
        for mode, outcome in (("sleep", "таймаут"), ("signal", "исключение")):
            for place in share:
                with self.subTest(place=place, mode=mode, seed=self.seed):
                    self.check_home(place, self.scenario(place, mode), outcome)

    def test_ac3_home_removed_after_timeout_and_exception_share2(self):
        """Таймаут и исключение на прогоне: `HOME` прогона после исхода удалён.

        Восемь мест, режимы обёртки `sleep` (предел прогона
        `TIMEOUT_SEC`, обёртка спит дольше) и `signal` (обработчик
        `SIGUSR1` поднимает исключение, пока место ждёт прогон): на
        прогоне `HOME` — новый каталог, после возврата или исключения
        места каталога нет.

        Ловит мутацию: уборка временного `HOME` стоит после ожидания
        прогона, а не в `finally` — по `TimeoutExpired` или исключению
        каталог остаётся.

        Сценарий доли: места `PLACES` по сортировке копии перечня делятся
        на `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        2 (её непустоту утверждает `assertTrue`) — в доле не меньше
        двух прогонов, так что проверка «HOME не общий у нескольких
        прогонов» держится в каждой доле; прочие доли — у метода без
        суффикса и методов с суффиксом `_share<i>`.
        """
        share = places_share(2)
        self.assertTrue(share)
        for mode, outcome in (("sleep", "таймаут"), ("signal", "исключение")):
            for place in share:
                with self.subTest(place=place, mode=mode, seed=self.seed):
                    self.check_home(place, self.scenario(place, mode), outcome)

    def test_ac3_home_removed_after_timeout_and_exception_share3(self):
        """Таймаут и исключение на прогоне: `HOME` прогона после исхода удалён.

        Восемь мест, режимы обёртки `sleep` (предел прогона
        `TIMEOUT_SEC`, обёртка спит дольше) и `signal` (обработчик
        `SIGUSR1` поднимает исключение, пока место ждёт прогон): на
        прогоне `HOME` — новый каталог, после возврата или исключения
        места каталога нет.

        Ловит мутацию: уборка временного `HOME` стоит после ожидания
        прогона, а не в `finally` — по `TimeoutExpired` или исключению
        каталог остаётся.

        Сценарий доли: места `PLACES` по сортировке копии перечня делятся
        на `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        3 (её непустоту утверждает `assertTrue`) — в доле не меньше
        двух прогонов, так что проверка «HOME не общий у нескольких
        прогонов» держится в каждой доле; прочие доли — у метода без
        суффикса и методов с суффиксом `_share<i>`.
        """
        share = places_share(3)
        self.assertTrue(share)
        for mode, outcome in (("sleep", "таймаут"), ("signal", "исключение")):
            for place in share:
                with self.subTest(place=place, mode=mode, seed=self.seed):
                    self.check_home(place, self.scenario(place, mode), outcome)


class PytestOwnProcessGroupTest(PytestOwnProjectTest):
    """Снятие группы процессов прогона `pytest-own` — настоящие прогоны."""

    def test_ac6_child_gone_after_timeout_and_exception(self):
        """Дочерний процесс обёртки не живёт после таймаута и после исключения.

        Восемь мест, режимы `sleep` (таймаут) и `signal` (исключение на
        прогоне). Обёртка порождает дочерний процесс, держащий конец
        записи именованного канала зонда; после возврата или исключения
        места читатель канала получает конец файла — все держатели мертвы.

        Ловит мутацию: место запускает прогон без собственного сеанса или
        по таймауту/исключению убивает только главный процесс
        (`subprocess.run(timeout=…)`, `proc.kill()`), а не группу — дочерний
        процесс обёртки жив, канал не закрыт.

        Сценарий доли: места `PLACES` по сортировке копии перечня делятся
        на `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        0 (её непустоту утверждает `assertTrue`); прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        share = places_share(0)
        self.assertTrue(share)
        for mode in ("sleep", "signal"):
            for place in share:
                with self.subTest(place=place, mode=mode, seed=self.seed):
                    run = self.scenario(place, mode)
                    self.wrapper_records(place, run)
                    self.assertTrue(run["probe"].children_gone(),
                                    f"{self.where(place)}, режим {mode}: "
                                    f"дочерний процесс обёртки жив")

    def test_ac6_child_gone_after_timeout_and_exception_share1(self):
        """Дочерний процесс обёртки не живёт после таймаута и после исключения.

        Восемь мест, режимы `sleep` (таймаут) и `signal` (исключение на
        прогоне). Обёртка порождает дочерний процесс, держащий конец
        записи именованного канала зонда; после возврата или исключения
        места читатель канала получает конец файла — все держатели мертвы.

        Ловит мутацию: место запускает прогон без собственного сеанса или
        по таймауту/исключению убивает только главный процесс
        (`subprocess.run(timeout=…)`, `proc.kill()`), а не группу — дочерний
        процесс обёртки жив, канал не закрыт.

        Сценарий доли: места `PLACES` по сортировке копии перечня делятся
        на `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        1 (её непустоту утверждает `assertTrue`); прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        share = places_share(1)
        self.assertTrue(share)
        for mode in ("sleep", "signal"):
            for place in share:
                with self.subTest(place=place, mode=mode, seed=self.seed):
                    run = self.scenario(place, mode)
                    self.wrapper_records(place, run)
                    self.assertTrue(run["probe"].children_gone(),
                                    f"{self.where(place)}, режим {mode}: "
                                    f"дочерний процесс обёртки жив")

    def test_ac6_child_gone_after_timeout_and_exception_share2(self):
        """Дочерний процесс обёртки не живёт после таймаута и после исключения.

        Восемь мест, режимы `sleep` (таймаут) и `signal` (исключение на
        прогоне). Обёртка порождает дочерний процесс, держащий конец
        записи именованного канала зонда; после возврата или исключения
        места читатель канала получает конец файла — все держатели мертвы.

        Ловит мутацию: место запускает прогон без собственного сеанса или
        по таймауту/исключению убивает только главный процесс
        (`subprocess.run(timeout=…)`, `proc.kill()`), а не группу — дочерний
        процесс обёртки жив, канал не закрыт.

        Сценарий доли: места `PLACES` по сортировке копии перечня делятся
        на `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        2 (её непустоту утверждает `assertTrue`); прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        share = places_share(2)
        self.assertTrue(share)
        for mode in ("sleep", "signal"):
            for place in share:
                with self.subTest(place=place, mode=mode, seed=self.seed):
                    run = self.scenario(place, mode)
                    self.wrapper_records(place, run)
                    self.assertTrue(run["probe"].children_gone(),
                                    f"{self.where(place)}, режим {mode}: "
                                    f"дочерний процесс обёртки жив")

    def test_ac6_child_gone_after_timeout_and_exception_share3(self):
        """Дочерний процесс обёртки не живёт после таймаута и после исключения.

        Восемь мест, режимы `sleep` (таймаут) и `signal` (исключение на
        прогоне). Обёртка порождает дочерний процесс, держащий конец
        записи именованного канала зонда; после возврата или исключения
        места читатель канала получает конец файла — все держатели мертвы.

        Ловит мутацию: место запускает прогон без собственного сеанса или
        по таймауту/исключению убивает только главный процесс
        (`subprocess.run(timeout=…)`, `proc.kill()`), а не группу — дочерний
        процесс обёртки жив, канал не закрыт.

        Сценарий доли: места `PLACES` по сортировке копии перечня делятся
        на `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        3 (её непустоту утверждает `assertTrue`); прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        share = places_share(3)
        self.assertTrue(share)
        for mode in ("sleep", "signal"):
            for place in share:
                with self.subTest(place=place, mode=mode, seed=self.seed):
                    run = self.scenario(place, mode)
                    self.wrapper_records(place, run)
                    self.assertTrue(run["probe"].children_gone(),
                                    f"{self.where(place)}, режим {mode}: "
                                    f"дочерний процесс обёртки жив")


class PytestOwnArgvTest(PytestOwnProjectTest):
    """argv и `cwd` прогона `pytest-own` на подменённом `subprocess`."""

    COMMAND = ("python3", "-m", "pytest")

    def fake_calls(self, place: str, profile, **kwargs) -> list:
        fake = FakeSubprocess()
        scratch = Path(tempfile.mkdtemp(prefix="artel-argv-")).resolve()
        self.addCleanup(shutil.rmtree, scratch, True)
        with mock.patch.object(acceptance, "subprocess", fake), \
                mock.patch.object(two_sided, "subprocess", fake):
            self.invoke(place, profile, scratch, **kwargs)
        self.assertTrue(fake.calls, f"{self.where(place)}: pytest не позван")
        return fake.calls

    def test_ac4_argv_profile_command_gate_args_cwd_workdir(self):
        """argv — команда профиля как есть плюс аргументы гейтов и места; `cwd` — `workdir`.

        Команда профиля `python3 -m pytest` (у `pult-pytest` голову
        подменил бы интерпретатор пульта). В каждом из восьми мест: argv
        начинается ровно с неё; есть `-p no:cacheprovider`; нет `-p
        timeout`, `-o timeout=…`, `-n`, `-p xdist`; есть аргументы места
        (цель, указывающая из `cwd` на модуль или каталог долгоживущих
        тестов; `--junitxml=` у прогона с временем файлов и у повтора, `-o
        junit_logging=system-out` у повтора, `--collect-only -q` у сбора,
        `-p artel_two_sided_report` у стороны двустороннего прогона);
        `cwd` — `<корень>/workdir`, у стороны — `workdir` в её дереве.

        Ловит мутацию: голова `python3` подменена интерпретатором пульта,
        к команде `pytest-own` дописаны `-p timeout -o timeout=…` или `-n …
        -p xdist`, снят `-p no:cacheprovider`, прогон идёт в корне дерева
        вместо `workdir` — argv или `cwd` расходится.
        """
        profile = self.profile(self.COMMAND)
        module = self.root / self.module_rel
        for place in PLACES:
            with self.subTest(place=place, seed=self.seed):
                where = self.where(place)
                for call in self.fake_calls(place, profile):
                    argv, cwd = call["argv"], call["cwd"]
                    self.assertEqual(argv[:3], list(self.COMMAND), where)
                    self.assertTrue(has_pair(argv, "-p", "no:cacheprovider"),
                                    f"{where}: {argv}")
                    self.assertFalse(has_pair(argv, "-p", "timeout"), argv)
                    self.assertFalse(has_pair(argv, "-p", "xdist"), argv)
                    self.assertNotIn("-n", argv, where)
                    self.assertFalse(any(argv[i] == "-o" and
                                         argv[i + 1].startswith("timeout=")
                                         for i in range(len(argv) - 1)), argv)
                    if place == TWO_SIDED:
                        tree = call["git_root"]
                        self.assertIsNotNone(tree, f"{where}: cwd {cwd} вне дерева")
                        self.assertNotEqual(Path(tree).resolve(), self.root, where)
                        self.assertTrue(has_pair(argv, "-p",
                                                 two_sided.PLUGIN_MODULE), argv)
                    else:
                        tree = self.root
                    self.assertEqual(os.path.realpath(str(cwd)),
                                     os.path.realpath(str(Path(tree) / self.workdir)),
                                     where)
                    if place in FULL_PLACES:
                        self.assertTrue(any(resolves_to(a, cwd, self.root / self.checks)
                                            for a in argv[3:]), f"{where}: {argv}")
                    elif place != TWO_SIDED:
                        self.assertTrue(any(resolves_to(a, cwd, module)
                                            for a in argv[3:]), f"{where}: {argv}")
                    if place in ("acceptance.run", "acceptance.run_repeat"):
                        self.assertTrue(any(a.startswith("--junitxml=")
                                            for a in argv), argv)
                    if place == "acceptance.run_repeat":
                        self.assertTrue(has_pair(argv, "-o",
                                                 "junit_logging=system-out"), argv)
                    if place == "acceptance.collect":
                        self.assertIn("--collect-only", argv, where)
                        self.assertIn("-q", argv, where)

    def test_ac5_full_suite_targets_translated_to_workdir(self):
        """Цели полного набора `pytest-own`: `long_lived_dir` под `workdir`, пути от корня переведены, id не тронуты.

        Три места полного набора, команда профиля `python3 -m pytest`:
        без `targets` и с `targets=("tests",)` цель — аргумент,
        указывающий из `cwd` на `<корень>/<long_lived_dir>`, `tests` в argv
        нет; цель от корня `<long_lived_dir>/<модуль>` передаётся путём,
        указывающим из `cwd` на тот же файл (сырой путь от корня в argv
        нет); идентификатор упавшего теста `checks_…/<модуль>::ProbeTest::
        test_probe` (как его печатает pytest из `workdir`; файла с таким
        путём от корня нет) передаётся как есть.

        Ловит мутацию: цель полного набора осталась `tests`, прочие цели
        не переводятся к `workdir` или переводится и идентификатор
        упавшего теста — argv не несёт нужного пути либо несёт искажённый
        идентификатор.
        """
        profile = self.profile(self.COMMAND)
        lld = self.root / self.checks
        module_rel = self.module_rel
        failed_id = (f"{os.path.relpath(lld, self.root / self.workdir)}/"
                     f"{Path(module_rel).name}::ProbeTest::test_probe")
        self.assertFalse((self.root / failed_id.split("::")[0]).exists())
        for place in FULL_PLACES:
            for targets_arg in (None, ("tests",)):
                with self.subTest(place=place, targets=targets_arg,
                                  seed=self.seed):
                    for call in self.fake_calls(place, profile,
                                                targets_arg=targets_arg):
                        argv, cwd = call["argv"], call["cwd"]
                        self.assertTrue(any(resolves_to(a, cwd, lld)
                                            for a in argv[3:]),
                                        f"{self.where(place)}: {argv}")
                        self.assertNotIn("tests", argv[3:], self.where(place))
            with self.subTest(place=place, targets="путь от корня",
                              seed=self.seed):
                for call in self.fake_calls(place, profile,
                                            targets_arg=(module_rel,)):
                    argv, cwd = call["argv"], call["cwd"]
                    self.assertTrue(any(resolves_to(a, cwd, self.root / module_rel)
                                        for a in argv[3:]),
                                    f"{self.where(place)}: {argv}")
                    self.assertNotIn(module_rel, argv, self.where(place))
            with self.subTest(place=place, targets="id упавшего",
                              seed=self.seed):
                for call in self.fake_calls(place, profile,
                                            targets_arg=(failed_id,)):
                    self.assertIn(failed_id, call["argv"], self.where(place))


class PytestOwnFullSuiteTest(PytestOwnProjectTest):
    """Исходы и сохранённые итоги `acceptance.full_suite` при `pytest-own`."""

    TASK = "TPROBE"

    def full_suite(self, profile):
        return acceptance.full_suite(
            self.root, self.TASK, **via_command(acceptance.full_suite, profile))

    def test_ac5_missing_long_lived_dir_means_no_tests(self):
        """Нет `long_lived_dir` под `workdir` — исход «тестов нет», хотя `<корень>/tests` есть.

        В дереве есть `<корень>/tests` с тестом, а каталога долгоживущих
        тестов профиля (случайное имя под `workdir`) нет:
        `full_suite` даёт `FULL_SUITE_NO_TESTS`, команда профиля не
        запускается.

        Ловит мутацию: предпроверка каталога тестов полного набора
        смотрит на `<корень>/tests` и при `pytest-own` — прогон
        запускается, исход зелёный или красный вместо «тестов нет».
        """
        tests_dir = self.root / "tests"
        tests_dir.mkdir()
        (tests_dir / f"test_root_{self.word()}.py").write_text(
            MODULE, encoding="utf-8")
        self.commit("tests в корне")
        for _ in range(2):
            absent = f"{self.workdir}/absent_{self.word()}"
            probe = ProbeRun(self)
            with self.subTest(long_lived_dir=absent, seed=self.seed):
                result = self.full_suite(self.profile(
                    probe.command(self.wrapper, "pass"), long_lived_dir=absent))
                self.assertEqual(result.outcome, acceptance.FULL_SUITE_NO_TESTS,
                                 f"зерно {self.seed}: {result.detail}")
                self.assertEqual(probe.records("wrapper.jsonl"), [],
                                 f"зерно {self.seed}: прогон запускался")

    def test_ac8_saved_gate_result_not_reused_for_other_workdir_or_env(self):
        """Gate-итог, сохранённый при другом `workdir` или `env`, не засчитывается.

        Чистое закоммиченное дерево. `full_suite` с профилем A прогоняет
        набор (обёртка запущена один раз, итог сохранён); повтор с тем же
        A берёт итог (обёртка не запускается) — контроль кэша; профиль с
        другим `workdir` (каталог долгоживущих тестов) и профиль с другим
        значением переменной `env` прогоняют набор заново.

        Ловит мутацию: ключ итога `pytest-own` не учитывает `workdir` или
        `env` — `full_suite` берёт итог профиля A, обёртка не запускается.
        """
        probe = ProbeRun(self)
        command = probe.command(self.wrapper, "pass")
        first = self.profile(command)
        key = next(iter(self.profile_env))
        variants = (
            ("workdir", self.profile(command, workdir=self.checks)),
            ("env", self.profile(command, env={
                **self.profile_env, key: self.profile_env[key] + "x"})),
        )
        result = self.full_suite(first)
        self.assertEqual(result.outcome, acceptance.FULL_SUITE_GREEN,
                         f"зерно {self.seed}: {result.detail}")
        self.assertEqual(len(probe.records("wrapper.jsonl")), 1)
        self.assertTrue(any(acceptance.suite_results_dir().glob("gate-*")),
                        f"зерно {self.seed}: итог не сохранён")
        self.full_suite(first)
        self.assertEqual(len(probe.records("wrapper.jsonl")), 1,
                         f"зерно {self.seed}: итог того же профиля не взят")
        runs = 1
        for name, profile in variants:
            with self.subTest(differs=name, seed=self.seed):
                self.full_suite(profile)
                runs += 1
                self.assertEqual(len(probe.records("wrapper.jsonl")), runs,
                                 f"зерно {self.seed}: итог с другим {name} "
                                 f"засчитан")


class PytestOwnWorkdirOutsideTest(PytestOwnProjectTest):
    """`workdir`, чей `realpath` выводит из дерева прогона."""

    def refusal_text(self, place: str, outcome) -> str:
        """Текст отказа места: исход не зелёный (либо поднято исключение)."""
        where = self.where(place)
        if isinstance(outcome, BaseException):
            return str(outcome)
        if place in ("acceptance.run", "acceptance.collect") or \
                place in FULL_PLACES:
            ok, text = outcome
            self.assertFalse(ok, f"{where}: отказ засчитан зелёным")
            return text
        if place == "acceptance.run_repeat":
            self.assertTrue(outcome, f"{where}: повтор зелёный")
            return " ".join(f"{r.node} {r.note}" for r in outcome)
        if place == "acceptance.run_plank":
            code, text = outcome
            self.assertNotEqual(code, 0, f"{where}: код выхода 0")
            return text
        self.assertTrue(outcome.refusals, f"{where}: отказа нет")
        return " ".join(outcome.refusals)

    def test_ac7_workdir_link_outside_refused_without_run(self):
        """`workdir`-ссылка наружу: именованный отказ в каждом месте, pytest не запускается; `full_suite` — «не запущен» без лога и итога.

        `workdir` профиля — закоммиченная символическая ссылка дерева на
        каталог вне его (там лежит копия каталога долгоживущих тестов).
        В каждом из восьми мест обёртка не запускается, исход — отказ
        (не зелёный либо исключение), текст которого называет `workdir`
        (имя ссылки или каталог, куда она ведёт). `full_suite` даёт
        `FULL_SUITE_NOT_STARTED`, `log_path` пуст, в каталоге логов нет
        файла полного набора, сохранённых итогов нет.

        Ловит мутацию: проверка `workdir` по `abspath` вместо `realpath`
        или пропущена в одном из мест — обёртка запускается; отказ
        записан как красный прогон (`FULL_SUITE_RED`) с логом и итогом.
        """
        outside = Path(tempfile.mkdtemp(prefix="artel-outside-")).resolve()
        self.addCleanup(shutil.rmtree, outside, True)
        target = outside / f"out_{self.word()}"
        copy = target / Path(self.checks).name
        copy.mkdir(parents=True)
        (copy / Path(self.module_rel).name).write_text(MODULE, encoding="utf-8")
        link = f"wdl_{self.word()}"
        (self.root / link).symlink_to(target, target_is_directory=True)
        self.commit("workdir наружу")
        names = (link, target.name)
        for place in PLACES:
            with self.subTest(place=place, seed=self.seed):
                probe = ProbeRun(self)
                profile = self.profile(probe.command(self.wrapper, "pass"),
                                       workdir=link,
                                       long_lived_dir=f"{link}/{copy.name}")
                try:
                    outcome = self.invoke(place, profile, probe.dir)
                except Exception as exc:  # noqa: BLE001 — отказ вправе быть исключением
                    outcome = exc
                self.assertEqual(probe.records("wrapper.jsonl"), [],
                                 f"{self.where(place)}: прогон запускался")
                text = self.refusal_text(place, outcome)
                self.assertTrue(any(name in text for name in names),
                                f"{self.where(place)}: отказ не называет "
                                f"workdir: {text[:500]}")
        probe = ProbeRun(self)
        profile = self.profile(probe.command(self.wrapper, "pass"),
                               workdir=link, long_lived_dir=f"{link}/{copy.name}")
        result = acceptance.full_suite(
            self.root, "TPROBE", **via_command(acceptance.full_suite, profile))
        self.assertEqual(result.outcome, acceptance.FULL_SUITE_NOT_STARTED,
                         f"зерно {self.seed}: {result.detail}")
        self.assertIsNone(result.log_path)
        self.assertEqual(probe.records("wrapper.jsonl"), [])
        logs = [p.name for p in config.LOGS.rglob("*")
                if acceptance.FULL_SUITE_LOG_KIND in p.name]
        self.assertEqual(logs, [], f"зерно {self.seed}: лог полного набора")
        saved = acceptance.suite_results_dir()
        self.assertEqual(sorted(p.name for p in saved.glob("*")) if
                         saved.is_dir() else [], [],
                         f"зерно {self.seed}: сохранён итог")


class SuiteResultKeyTest(unittest.TestCase):
    """Ключ сохранённого итога полного набора — чистая функция, без песочницы."""

    def setUp(self):
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def word(self, k: int = 6) -> str:
        return "".join(self.rng.choices(string.ascii_lowercase, k=k))

    def tree(self) -> str:
        return "".join(self.rng.choices("0123456789abcdef", k=40))

    def key(self, tree: str, profile, base: bool):
        return acceptance.suite_result_key(
            tree, base=base, **via_command(acceptance.suite_result_key, profile))

    def test_ac8_key_differs_by_runner_workdir_env(self):
        """Gate- и base-ключ `pytest-own` меняются со сменой `runner`, `workdir`, `env`.

        Случайные дерево, команда, `workdir` и `env`. Тот же профиль — тот
        же ключ (контроль); профиль, отличный ровно одним из `runner`
        (`pytest-own` против `pult-pytest` при той же команде и пустых
        `workdir`/`env`), `workdir`, значения переменной `env` или
        добавленной переменной `env`, — другой ключ; gate и base.

        Ловит мутацию: ключ `pytest-own` строится только из argv команды
        (`runner`, `workdir` или `env` не входят) — ключи совпадут, и итог
        другого профиля засчитается.
        """
        for _ in range(3):
            tree = self.tree()
            command = (f"/opt/{self.word()}/bin/run", f"--{self.word()}")
            env = {self.word().upper(): self.word()}
            lld = f"{self.word()}/tests"
            profile = own_profile(command, lld, self.word(), env)
            same = own_profile(command, lld, profile.workdir, dict(env))
            name = next(iter(env))
            variants = {
                "runner": (own_profile(command, lld, "", {}),
                           own_profile(command, lld, "", {}, runner=PULT)),
                "workdir": (profile, dataclasses.replace(
                    profile, workdir=profile.workdir + "_x")),
                "env значение": (profile, dataclasses.replace(
                    profile, env=MappingProxyType({**env, name: env[name] + "x"}))),
                "env переменная": (profile, dataclasses.replace(
                    profile, env=MappingProxyType({**env, "EXTRA": "1"}))),
            }
            for base in (False, True):
                with self.subTest(control=True, base=base, seed=self.seed):
                    self.assertIsNotNone(self.key(tree, profile, base))
                    self.assertEqual(self.key(tree, profile, base),
                                     self.key(tree, same, base))
                for differs, (left, right) in variants.items():
                    with self.subTest(differs=differs, base=base,
                                      seed=self.seed):
                        self.assertNotEqual(self.key(tree, left, base),
                                            self.key(tree, right, base),
                                            f"зерно {self.seed}")

    def test_ac8_pult_pytest_profile_key_equals_command_key(self):
        """Ключ профиля `pult-pytest` — тот же, что ключ его команды прежним каналом.

        Для `python3 -m pytest` и случайной команды профиль `pult-pytest`
        даёт ровно тот ключ (gate и base), что список его команды; для
        `python3 -m pytest` — тот же, что ключ без команды.

        Ловит мутацию: в ключ профиля `pult-pytest` попали `runner`,
        `workdir` или `env` (пусть и пустые) — ключ артели меняется, её
        сохранённые итоги не засчитываются.
        """
        for command in (("python3", "-m", "pytest"),
                        (f"/opt/{self.word()}/python", "-m", "pytest", "-q")):
            tree = self.tree()
            profile = own_profile(command, "tests", "", {}, runner=PULT)
            for base in (False, True):
                with self.subTest(command=command, base=base, seed=self.seed):
                    expected = acceptance.suite_result_key(tree, list(command),
                                                           base=base)
                    self.assertIsNotNone(expected)
                    self.assertEqual(self.key(tree, profile, base), expected)
                    if command[0] == "python3":
                        self.assertEqual(acceptance.suite_result_key(
                            tree, None, base=base), expected)

    def test_ac5_base_key_drops_long_lived_dir(self):
        """Base-ключ `pytest-own` вычищает цель `long_lived_dir` под `workdir`.

        Команда профиля без цели и та же команда с целью — каталогом
        долгоживущих тестов, переведённым к `workdir`, или файлом в нём —
        дают один base-ключ.

        Ловит мутацию: вычистка base-ключа по-прежнему убирает только
        `tests`/`tests/…` — цель `long_lived_dir` остаётся в argv ключа, и
        base-ключи расходятся.
        """
        for _ in range(3):
            tree = self.tree()
            workdir = f"wd_{self.word()}"
            inner = f"checks_{self.word()}"
            command = (f"/opt/{self.word()}/bin/run",)
            plain = own_profile(command, f"{workdir}/{inner}", workdir, {})
            for target in (inner, f"{inner}/test_{self.word()}.py"):
                with self.subTest(target=target, seed=self.seed):
                    with_target = dataclasses.replace(
                        plain, command=command + (target,))
                    self.assertEqual(self.key(tree, with_target, True),
                                     self.key(tree, plain, True),
                                     f"зерно {self.seed}")


if __name__ == "__main__":
    unittest.main()
