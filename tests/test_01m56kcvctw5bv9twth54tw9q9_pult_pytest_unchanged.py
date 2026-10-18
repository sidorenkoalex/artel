"""Профиль артели `pult-pytest`: argv, окружение (в том числе `PATH`) и
`cwd` прогона в каждом из восьми мест запуска — прежние, сверка с
независимым литеральным ожиданием.

Группа: долгоживущий

Восемь мест: `acceptance.run`, `acceptance.collect`,
`acceptance.run_repeat`, `acceptance.run_plank`, прогон полного набора без
наблюдения, с наблюдением (`acceptance.observed_full_suite()`) и в файл
лога (`log=`) — через публичный `acceptance.run_full_suite`, сторона
двустороннего прогона — через `two_sided.run` на настоящем репозитории
песочницы (`tests.sandbox.RealGitSandbox`: связка «git worktree стороны —
прогон в нём»). Вызов pytest читается из подменённого модуля `subprocess`
(`acceptance` и `two_sided`).

Ожидание не вычисляется функциями пульта, строящими прогон: argv — команда
профиля (случайный путь интерпретатора, не `python3`), аргументы места и
флаги раннера пульта литералом (значения таймаута и числа рабочих — из
`stack`/`config`); `cwd` — корень дерева (у стороны — её worktree);
окружение — `os.environ` процесса теста на время вызова плюс служебные
переменные места (`PYTHONUNBUFFERED` у прогона в файл лога, `PYTHONPATH` и
`two_sided.REPORT_ENV` у стороны) плюс ключ `PYTHONPYCACHEPREFIX`. PATH
вызывающего — случайный, без каталога команды профиля и без части
`/usr/bin`, `/bin`, `/usr/sbin`, `/sbin` (каталог `git` в нём есть: сторона
заводит worktree git'ом по имени); переменные `ARTEL_LEAK_*` и `PYTHONPATH`
вызывающего — случайные. Зерно печатается и входит в текст провала.

Зелёный с рождения: тест закрепляет прежнее поведение артели до правки кода (SPEC, требование 4) — на main до правки и на ветке после неё он обязан быть зелёным.
"""
import os
import random
import shutil
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

PULT = targets.PROFILE_RUNNER_DEFAULT
PLACES = ("acceptance.run", "acceptance.collect", "acceptance.run_repeat",
          "acceptance.run_plank", "_run_full_suite_now без observe",
          "_run_full_suite_now с observe", "_run_full_suite_to_log",
          "two_sided._run_side")
FULL_PLACES = PLACES[4:7]
TWO_SIDED = PLACES[7]
SYSTEM_DIRS = ("/usr/bin", "/bin", "/usr/sbin", "/sbin")
PS_ROW = "1 0 0.0 00:01 /bin/probe\n"
REPORT = "--junitxml=<отчёт>"

MODULE = '''import unittest


class ProbeTest(unittest.TestCase):
    def test_probe(self):
        self.assertTrue(True)
'''


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
    pytest (`run` и `Popen`) запоминаются с argv, `cwd`, окружением и
    ближайшим к `cwd` корнем git; прочие `run` (`/bin/ps`) — строка
    процесса."""

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
        self.calls.append({"argv": argv, "cwd": cwd, "git_root": git_root,
                           "env": dict(kwargs.get("env") or {})})
        return True

    def run(self, argv, **kwargs):
        if not self.remember(argv, kwargs):
            return subprocess.CompletedProcess(argv, 0, PS_ROW, "")
        return subprocess.CompletedProcess(argv, 0, "1 passed in 0.01s", "")

    def Popen(self, argv, **kwargs):
        self.remember(argv, kwargs)
        return FakeProc(argv)


class PultPytestUnchangedTest(RealGitSandbox):
    """argv, окружение и `cwd` прогона артели по местам."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.module_rel = f"tests/test_probe_{self.word()}.py"
        module = self.root / self.module_rel
        module.parent.mkdir(parents=True, exist_ok=True)
        module.write_text(MODULE, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "набор артели")
        self.branch = f"probe-{self.word()}"
        self.git("branch", self.branch)
        self.base_sha = self.git("rev-parse", "HEAD").strip()
        git = shutil.which("git")
        self.assertIsNotNone(git, "git не найден в PATH процесса теста")
        self.git_dir = os.path.dirname(git)

    def word(self, k: int = 6) -> str:
        return "".join(self.rng.choices(string.ascii_lowercase, k=k))

    def where(self, place: str) -> str:
        return f"{place}, зерно {self.seed}"

    def scratch(self, prefix: str) -> Path:
        path = Path(tempfile.mkdtemp(prefix=prefix)).resolve()
        self.addCleanup(shutil.rmtree, path, True)
        return path

    def caller_env(self) -> dict:
        """Случайные переменные вызывающего: PATH без каталога команды и
        без части системных каталогов, `PYTHONPATH`, `ARTEL_LEAK_*`."""
        parts = [f"/nonexistent-{self.word()}/bin"
                 for _ in range(self.rng.randint(1, 3))]
        parts += [d for d in SYSTEM_DIRS if self.rng.random() < 0.5]
        parts.append(self.git_dir)
        self.rng.shuffle(parts)
        parts = list(dict.fromkeys(parts))
        if set(SYSTEM_DIRS) <= set(parts):
            parts.remove(self.rng.choice(
                [d for d in SYSTEM_DIRS if d != self.git_dir]))
        env = {f"ARTEL_LEAK_{self.word().upper()}": self.word(12)
               for _ in range(self.rng.randint(1, 3))}
        env["PATH"] = os.pathsep.join(parts)
        env["PYTHONPATH"] = f"/{self.word(10)}"
        return env

    def invoke(self, place: str, profile, scratch: Path):
        module = str(self.root / self.module_rel)
        if place == "acceptance.run":
            return acceptance.run(scratch, cwd=self.root, extra=[module],
                                  command=profile, file_times={})
        if place == "acceptance.collect":
            return acceptance.collect(scratch, cwd=self.root, extra=[module],
                                      command=profile)
        if place == "acceptance.run_repeat":
            return acceptance.run_repeat([module], self.root, command=profile)
        if place == "acceptance.run_plank":
            return acceptance.run_plank([module], self.root, profile=profile)
        if place == TWO_SIDED:
            method = two_sided.Method(self.module_rel, self.module_rel,
                                      "ProbeTest::test_probe", MODULE, MODULE)
            return two_sided.run(self.root, self.branch, self.base_sha,
                                 [method], profile=profile)
        kwargs = {"command": profile}
        if place == FULL_PLACES[2]:
            kwargs["log"] = scratch / "suite.log"
        if place == FULL_PLACES[0]:
            return acceptance.run_full_suite(self.root, **kwargs)
        with acceptance.observed_full_suite():
            return acceptance.run_full_suite(self.root, **kwargs)

    def expected_argv(self, place: str, head: list, tree: str) -> list:
        """Литеральный argv места: команда профиля, аргументы места, флаги
        раннера пульта (и параллели у полного набора)."""
        module = str(self.root / self.module_rel)
        flags = ["-p", "no:cacheprovider", "-p", "timeout",
                 "-o", f"timeout={stack.PER_TEST_TIMEOUT_SEC}"]
        place_args = {
            "acceptance.run": [module, REPORT],
            "acceptance.collect": [module, "--collect-only", "-q"],
            "acceptance.run_repeat": [module, REPORT, "-o",
                                      "junit_logging=system-out"],
            "acceptance.run_plank": [module],
            TWO_SIDED: [f"{self.module_rel}::ProbeTest::test_probe",
                        f"--rootdir={tree}", "-p", two_sided.PLUGIN_MODULE],
        }
        if place in FULL_PLACES:
            return [*head, "tests", *flags, "-n",
                    str(config.FULL_SUITE_WORKERS), "-p", "xdist"]
        return [*head, *place_args[place], *flags]

    def test_ac7_pult_pytest_argv_env_cwd_unchanged_in_each_place(self):
        """У `pult-pytest` argv, окружение с `PATH` и `cwd` — прежние в каждом из восьми мест.

        Профиль `pult-pytest` с командой `/opt/<случайно>/bin/python -m
        pytest`; PATH вызывающего без её каталога и без части системных
        каталогов. В каждом месте: argv равен литералу (путь отчёта junit
        сверяется формой `--junitxml=…/junit.xml`); `cwd` — корень дерева,
        у стороны — корень её worktree (не корень репозитория); окружение
        без `PYTHONPYCACHEPREFIX` и служебных переменных места равно
        `os.environ` вызывающего, `PYTHONPYCACHEPREFIX` есть; у прогона в
        файл лога `PYTHONUNBUFFERED=1`; у стороны `PYTHONPATH` — каталог
        плагина, затем `PYTHONPATH` вызывающего, ключ `REPORT_ENV` есть.

        Ловит мутацию: сборка PATH `pytest-own` (каталог `command[0]`,
        системные каталоги) применена и к `pult-pytest` — PATH прогона
        длиннее PATH вызывающего; окружение артели собрано чистым
        (`_own_env`) — пропали `ARTEL_LEAK_*`; к argv артели добавлен
        аргумент или сменён `cwd` — сверка с литералом расходится.
        """
        head = [f"/opt/{self.word()}/bin/python", "-m", "pytest"]
        profile = project_profile.Profile(
            command=tuple(head), long_lived_dir="tests",
            long_lived_name="test_<id>_<name>.py",
            weakening_scope=("tests/**",), mutation_claim_scope=("tests/**",),
            runner=PULT, workdir="", env=MappingProxyType({}))
        for place in PLACES:
            with self.subTest(place=place, seed=self.seed):
                where = self.where(place)
                fake = FakeSubprocess()
                with mock.patch.dict(os.environ, self.caller_env()), \
                        mock.patch.object(acceptance, "subprocess", fake), \
                        mock.patch.object(two_sided, "subprocess", fake):
                    for name in ("PYTHONPYCACHEPREFIX", "PYTHONUNBUFFERED",
                                 two_sided.REPORT_ENV):
                        os.environ.pop(name, None)
                    caller = dict(os.environ)
                    self.invoke(place, profile, self.scratch("artel-pult-"))
                self.assertEqual(len(fake.calls), 2 if place == TWO_SIDED else 1,
                                 f"{where}: вызовы pytest {fake.calls!r}")
                for call in fake.calls:
                    self.check_call(place, call, head, caller)

    def check_call(self, place: str, call: dict, head: list,
                   caller: dict) -> None:
        where = self.where(place)
        cwd = str(call["cwd"])
        if place == TWO_SIDED:
            tree = call["git_root"]
            self.assertIsNotNone(tree, f"{where}: cwd {cwd} вне дерева")
            self.assertEqual(cwd, str(tree), where)
            self.assertNotEqual(Path(tree).resolve(), self.root, where)
        else:
            self.assertEqual(cwd, str(self.root), where)
        argv = []
        for arg in call["argv"]:
            if arg.startswith("--junitxml="):
                self.assertTrue(arg.endswith(f"{os.sep}junit.xml"),
                                f"{where}: {arg}")
                arg = REPORT
            argv.append(arg)
        self.assertEqual(argv, self.expected_argv(place, head, cwd), where)
        env = dict(call["env"])
        self.assertIn("PYTHONPYCACHEPREFIX", env, where)
        env.pop("PYTHONPYCACHEPREFIX")
        expected = dict(caller)
        if place == FULL_PLACES[2]:
            expected["PYTHONUNBUFFERED"] = "1"
        if place == TWO_SIDED:
            self.assertIn(two_sided.REPORT_ENV, env, where)
            env.pop(two_sided.REPORT_ENV)
            plugin, sep, rest = env.get("PYTHONPATH", "").partition(os.pathsep)
            self.assertTrue(plugin and sep, f"{where}: {env.get('PYTHONPATH')!r}")
            self.assertEqual(rest, caller["PYTHONPATH"], where)
            env["PYTHONPATH"] = rest
        self.assertEqual(env.get("PATH"), caller["PATH"], f"{where}: PATH")
        self.assertEqual(env, expected, f"{where}: окружение")


if __name__ == "__main__":
    unittest.main()
