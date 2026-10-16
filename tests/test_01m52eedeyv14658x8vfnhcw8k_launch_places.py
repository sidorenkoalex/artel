"""Фиксация argv, `cwd` и окружения восьми мест запуска pytest пульта для
артели на текущем коде: `acceptance.run`, `collect`, `run_repeat`,
`run_plank`, прогон полного набора без наблюдения и с наблюдением, прогон
полного набора в файл лога, сторона двустороннего прогона.

Группа: долгоживущий

Места запуска без собственного публичного входа достигаются публичными:
прогон полного набора (`_run_full_suite_now` с `observe` и без,
`_run_full_suite_to_log`) — через `acceptance.run_full_suite` (без лога,
внутри `acceptance.observed_full_suite()`, с `log=`), сторона
двустороннего прогона — через `two_sided.run` на настоящем репозитории
песочницы (`tests.sandbox.RealGitSandbox`, связка «git worktree — прогон
стороны»). Модуль `subprocess` подменён только у вызывающего модуля
(`acceptance`, `two_sided`): подмена запоминает argv, `cwd`, копию `env` и
снимок `os.environ` в момент вызова; git и выбор интерпретатора идут
настоящими. `tempfile.mkdtemp` подменён детерминированным: каталог
`<префикс>N` в своей базе на каждый вызов места — так путь отчёта junit и
временное дерево двустороннего прогона в ожидании — временные каталоги
теста, а не прочитанное из фактического argv.

Ожидаемые argv и `cwd` — литералы; вычисляются только интерпретатор
(`stack.pytest_python_executable()`) и временные каталоги теста. Окружение
сравнивается как разница с `os.environ` в момент вызова: удалённых
переменных нет, набор добавленных и изменённых — ровно названный. В
`os.environ` на время вызова добавлены случайные переменные (зерно
печатается и входит в текст провала).

Зелёный с рождения: файл фиксирует сегодняшнее поведение восьми мест запуска, код задачи его не меняет; следующие части D0 меняют его наблюдаемо — этим файлом.
"""
import os
import random
import string
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, config, stack
from orchestrator.advance_gates import two_sided
from tests.sandbox import RealGitSandbox, TmpDirTest

PREFIX_VAR = "PYTHONPYCACHEPREFIX"
ARTEL_COMMAND = ["python3", "-m", "pytest"]
COMMANDS = (("command=None", None), ("command=[python3, -m, pytest]",
                                     ARTEL_COMMAND))
PULT_FLAGS = ["-p", "no:cacheprovider", "-p", "timeout", "-o", "timeout=120"]
XDIST_FLAGS = ["-n", "auto", "-p", "xdist"]
PS_ROW = "1 0 0.0 00:01 /bin/probe\n"

PASSING_TEST = """import unittest


class PlankTest(unittest.TestCase):
    def test_something(self):
        self.assertTrue(True)
"""


def inside(path, parent) -> bool:
    child = os.path.realpath(path)
    base = os.path.realpath(parent)
    return child == base or child.startswith(base.rstrip(os.sep) + os.sep)


class FixedTemp:
    """Подмена `tempfile.mkdtemp`: каталог `<префикс>N` в базе `base`, N —
    номер вызова с этим префиксом."""

    def __init__(self, base: Path):
        self.base = base
        self.base.mkdir(parents=True)
        self.counts: dict = {}

    def __call__(self, suffix=None, prefix=None, dir=None):
        prefix = prefix or "tmp"
        self.counts[prefix] = self.counts.get(prefix, 0) + 1
        path = self.base / f"{prefix}{self.counts[prefix]}{suffix or ''}"
        path.mkdir()
        return str(path)

    def dir(self, prefix: str, n: int = 1) -> Path:
        return self.base / f"{prefix}{n}"


class FakeProc:
    pid = 4_000_000
    returncode = 0

    def __init__(self, argv):
        self.args = argv

    def communicate(self, timeout=None):
        return "1 passed in 0.01s", ""

    def wait(self, timeout=None):
        return 0


class FakeSubprocess:
    """Замена модуля `subprocess` у вызывающего модуля: вызовы pytest
    (`run` и `Popen`) запоминаются; прочие вызовы `run` (снимок процессов
    `/bin/ps` наблюдаемого прогона) получают строку процесса."""

    PIPE = subprocess.PIPE
    STDOUT = subprocess.STDOUT
    DEVNULL = subprocess.DEVNULL
    TimeoutExpired = subprocess.TimeoutExpired
    SubprocessError = subprocess.SubprocessError
    CompletedProcess = subprocess.CompletedProcess

    def __init__(self):
        self.calls: list = []

    def remember(self, how: str, argv, kwargs) -> bool:
        argv = list(argv)
        if "pytest" not in argv:
            return False
        env = kwargs.get("env")
        self.calls.append({"how": how, "argv": argv, "cwd": kwargs.get("cwd"),
                           "env": dict(env) if env is not None else None,
                           "base": dict(os.environ)})
        return True

    def run(self, argv, **kwargs):
        if not self.remember("run", argv, kwargs):
            return subprocess.CompletedProcess(argv, 0, PS_ROW, "")
        return subprocess.CompletedProcess(argv, 0, "1 passed in 0.01s", "")

    def Popen(self, argv, **kwargs):
        self.remember("Popen", argv, kwargs)
        return FakeProc(argv)


class PlaceCheck:
    """Общая сверка одного вызова места запуска."""

    def probe_environ(self) -> dict:
        return {"ARTEL_PROBE_" + "".join(self.rng.choices(
            string.ascii_uppercase, k=8)): "".join(self.rng.choices(
                string.ascii_letters + string.digits, k=12))
            for _ in range(self.rng.randint(1, 3))}

    def single_call(self, fake: FakeSubprocess, label: str) -> dict:
        self.assertEqual(len(fake.calls), 1,
                         f"{label}: ожидался один вызов pytest, зерно "
                         f"{self.seed}: {[c['argv'] for c in fake.calls]}")
        return fake.calls[0]

    def check_call(self, call: dict, label: str, how: str, argv: list,
                   cwd: Path, added: dict) -> None:
        """argv и `cwd` — точное равенство; окружение — разница с
        `os.environ` в момент вызова: без удалённых, добавленные и
        изменённые — ровно `added` (значение — строка либо проверка)."""
        where = f"{label}, зерно {self.seed}"
        self.assertEqual(call["how"], how, where)
        self.assertEqual(call["argv"], argv, where)
        self.assertEqual(str(call["cwd"]), str(cwd), where)
        env, base = call["env"], call["base"]
        self.assertIsNotNone(env, f"{where}: env не передан")
        self.assertEqual(sorted(set(base) - set(env)), [],
                         f"{where}: удалены переменные")
        delta = {k: v for k, v in env.items() if base.get(k) != v}
        self.assertEqual(sorted(delta), sorted(added), f"{where}: {delta}")
        prefix = delta[PREFIX_VAR]
        self.assertTrue(os.path.isabs(prefix), where)
        self.assertFalse(inside(prefix, cwd),
                         f"{where}: {PREFIX_VAR}={prefix} внутри cwd {cwd}")
        for key, expected in added.items():
            if key == PREFIX_VAR:
                continue
            if callable(expected):
                self.assertTrue(expected(delta[key]),
                                f"{where}: {key}={delta[key]}")
            else:
                self.assertEqual(delta[key], expected, f"{where}: {key}")


class AcceptancePlacesTest(PlaceCheck, TmpDirTest):
    """Семь мест запуска `orchestrator/acceptance.py` на подменённом
    `subprocess` модуля."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.calls_made = 0
        self.code = self.tdir / "code"
        (self.code / "tests").mkdir(parents=True)
        self.extra_file = ("tests/test_probe_" + "".join(self.rng.choices(
            string.ascii_lowercase, k=6)) + ".py")
        (self.code / self.extra_file).write_text(PASSING_TEST, encoding="utf-8")
        self.task = self.tdir / ("task_" + "".join(self.rng.choices(
            string.ascii_lowercase, k=6)))
        (self.task / "acceptance_tests").mkdir(parents=True)
        (self.task / "acceptance_tests" / "test_ac.py").write_text(
            PASSING_TEST, encoding="utf-8")
        self.plank = str(self.task / "acceptance_tests")
        patcher = mock.patch.object(config, "LOGS", self.tdir / "logs")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.py = stack.pytest_python_executable()

    def call(self, invoke, label: str):
        """(вызов pytest, база временных каталогов) одного вызова места."""
        self.calls_made += 1
        temp = FixedTemp(self.tdir / f"sys{self.calls_made}")
        fake = FakeSubprocess()
        with mock.patch.dict(os.environ, self.probe_environ()), \
                mock.patch.object(tempfile, "mkdtemp", temp), \
                mock.patch.object(acceptance, "subprocess", fake):
            # Полный прогон пульта сам ставит PYTHONUNBUFFERED: без снятия
            # разница «окружение вызова − os.environ» её не увидит.
            os.environ.pop("PYTHONUNBUFFERED", None)
            invoke()
        return self.single_call(fake, label), temp

    def test_ac7_run_argv_cwd_env(self):
        """`acceptance.run`: argv, `cwd` и окружение на обоих путях команды.

        Прогон планки с долгоживущим файлом и без, с `file_times` и без, на
        `command=None` и на команде профиля артели. argv — интерпретатор,
        `-m pytest`, каталог планки, долгоживущий файл, `--junitxml` в
        каталоге `artel-file-times-` (только с `file_times`), флаги пульта;
        `cwd` — переданный; окружение — только `PYTHONPYCACHEPREFIX` вне
        `cwd`.

        Ловит мутацию: из `_pytest_command` пропал `-p no:cacheprovider`
        или `-o timeout=…`, `cwd` прогона — `config.ROOT` вместо
        переданного, либо в окружение добавлен `PYTHONUNBUFFERED` — argv,
        `cwd` или набор разницы окружения расходится с литералом.
        """
        for label, command in COMMANDS:
            for extra in ([], [self.extra_file]):
                for times in (None, {}):
                    name = f"run {label} extra={extra} file_times={times}"
                    with self.subTest(case=name, seed=self.seed):
                        call, temp = self.call(lambda: acceptance.run(
                            self.task, cwd=self.code, extra=extra,
                            command=command, file_times=times), name)
                        report = ([f"--junitxml="
                                   f"{temp.dir('artel-file-times-')}/junit.xml"]
                                  if times is not None else [])
                        self.check_call(
                            call, name, "run",
                            [self.py, "-m", "pytest", self.plank, *extra,
                             *report, *PULT_FLAGS],
                            self.code, {PREFIX_VAR: None})

    def test_ac7_collect_argv_cwd_env(self):
        """`acceptance.collect`: argv, `cwd` и окружение на обоих путях команды.

        Сухой сбор планки с долгоживущим файлом и без: argv —
        интерпретатор, `-m pytest`, каталог планки, файл, `--collect-only
        -q`, флаги пульта; `cwd` — переданный; окружение — только
        `PYTHONPYCACHEPREFIX` вне `cwd`.

        Ловит мутацию: сбор перестал передавать `-q` или флаги пульта, или
        путь `command` профиля строит argv с голым `python3` — argv
        расходится с литералом.
        """
        for label, command in COMMANDS:
            for extra in ([], [self.extra_file]):
                name = f"collect {label} extra={extra}"
                with self.subTest(case=name, seed=self.seed):
                    call, _temp = self.call(lambda: acceptance.collect(
                        self.task, cwd=self.code, extra=extra,
                        command=command), name)
                    self.check_call(
                        call, name, "run",
                        [self.py, "-m", "pytest", self.plank, *extra,
                         "--collect-only", "-q", *PULT_FLAGS],
                        self.code, {PREFIX_VAR: None})

    def test_ac7_run_repeat_argv_cwd_env(self):
        """`acceptance.run_repeat`: argv, `cwd` и окружение на обоих путях команды.

        Повтор долгоживущего файла: argv — интерпретатор, `-m pytest`,
        файл, `--junitxml` в каталоге `artel-seed-repeat-`, `-o
        junit_logging=system-out`, флаги пульта; `cwd` — переданный;
        окружение — только `PYTHONPYCACHEPREFIX` вне `cwd`.

        Ловит мутацию: повтор потерял `-o junit_logging=system-out` (зёрна
        не попадают в отчёт) или отчёт пишется в `cwd` — argv расходится с
        литералом.
        """
        for label, command in COMMANDS:
            name = f"run_repeat {label}"
            with self.subTest(case=name, seed=self.seed):
                call, temp = self.call(lambda: acceptance.run_repeat(
                    [self.extra_file], self.code, command=command), name)
                self.check_call(
                    call, name, "run",
                    [self.py, "-m", "pytest", self.extra_file,
                     f"--junitxml={temp.dir('artel-seed-repeat-')}/junit.xml",
                     "-o", "junit_logging=system-out", *PULT_FLAGS],
                    self.code, {PREFIX_VAR: None})

    def test_ac7_run_plank_argv_cwd_env(self):
        """`acceptance.run_plank`: argv, `cwd` и окружение единственного пути.

        Прогон планки и долгоживущего файла командой `plank-run`: argv —
        интерпретатор, `-m pytest`, цели в переданном порядке, флаги
        пульта; `cwd` — переданный; окружение — только
        `PYTHONPYCACHEPREFIX` вне `cwd`.

        Ловит мутацию: `run_plank` собирает команду без `-p timeout`
        (зависший тест не режется) или зовёт pytest без `env=` — argv
        расходится с литералом либо `env` не передан.
        """
        targets = [self.plank, self.extra_file]
        call, _temp = self.call(
            lambda: acceptance.run_plank(targets, self.code), "run_plank")
        self.check_call(call, "run_plank", "run",
                        [self.py, "-m", "pytest", *targets, *PULT_FLAGS],
                        self.code, {PREFIX_VAR: None})

    def test_ac7_full_suite_now_without_observe(self):
        """Прогон полного набора без наблюдения и без лога: argv, `cwd`, окружение.

        `acceptance.run_full_suite(root)` на `command=None` и на команде
        профиля артели зовёт `subprocess.run`: argv — интерпретатор, `-m
        pytest`, `tests`, флаги пульта, `-n auto -p xdist`; `cwd` — корень;
        окружение — только `PYTHONPYCACHEPREFIX` вне `cwd`.

        Ловит мутацию: параллель `-n … -p xdist` перенесена в
        `_pytest_command` (порядок флагов меняется) или снята — argv
        расходится с литералом.
        """
        for label, command in COMMANDS:
            name = f"full_suite_now {label}"
            with self.subTest(case=name, seed=self.seed):
                call, _temp = self.call(lambda: acceptance.run_full_suite(
                    self.code, command=command), name)
                self.check_call(
                    call, name, "run",
                    [self.py, "-m", "pytest", "tests", *PULT_FLAGS,
                     *XDIST_FLAGS],
                    self.code, {PREFIX_VAR: None})

    def test_ac7_full_suite_now_with_observe(self):
        """Прогон полного набора с наблюдением: argv, `cwd`, окружение вызова `Popen`.

        Внутри `acceptance.observed_full_suite()` `run_full_suite(root)` на
        обоих путях команды зовёт `subprocess.Popen`: argv тот же, что без
        наблюдения; `cwd` — корень; окружение — только
        `PYTHONPYCACHEPREFIX` вне `cwd`, без `PYTHONUNBUFFERED`.

        Ловит мутацию: ветка наблюдения ставит `PYTHONUNBUFFERED` (как
        прогон в лог) или передаёт `cwd` иной, чем корень, — набор разницы
        окружения или `cwd` расходится.
        """
        for label, command in COMMANDS:
            name = f"full_suite_now observe {label}"

            def invoke(command=command):
                with acceptance.observed_full_suite():
                    acceptance.run_full_suite(self.code, command=command)

            with self.subTest(case=name, seed=self.seed):
                call, _temp = self.call(invoke, name)
                self.check_call(
                    call, name, "Popen",
                    [self.py, "-m", "pytest", "tests", *PULT_FLAGS,
                     *XDIST_FLAGS],
                    self.code, {PREFIX_VAR: None})

    def test_ac7_full_suite_to_log_argv_cwd_env(self):
        """Прогон полного набора в файл лога: argv, `cwd`, окружение с `PYTHONUNBUFFERED`.

        `run_full_suite(root, log=…)` на обоих путях команды, с наблюдением
        и без, зовёт `subprocess.Popen`: argv тот же, что у прогона без
        лога; `cwd` — корень; окружение — `PYTHONPYCACHEPREFIX` вне `cwd` и
        `PYTHONUNBUFFERED` = `"1"`.

        Ловит мутацию: `PYTHONUNBUFFERED` снят (на пределе времени SIGKILL
        съедает буфер) или выставлен иным значением — разница окружения
        расходится с набором.
        """
        for label, command in COMMANDS:
            for observe in (False, True):
                name = f"full_suite_to_log {label} observe={observe}"
                log = self.tdir / f"suite-{self.calls_made}.log"

                def invoke(command=command, observe=observe, log=log):
                    if observe:
                        with acceptance.observed_full_suite():
                            acceptance.run_full_suite(
                                self.code, command=command, log=log)
                    else:
                        acceptance.run_full_suite(
                            self.code, command=command, log=log)

                with self.subTest(case=name, seed=self.seed):
                    call, _temp = self.call(invoke, name)
                    self.check_call(
                        call, name, "Popen",
                        [self.py, "-m", "pytest", "tests", *PULT_FLAGS,
                         *XDIST_FLAGS],
                        self.code, {PREFIX_VAR: None, "PYTHONUNBUFFERED": "1"})


class TwoSidedSideTest(PlaceCheck, RealGitSandbox):
    """Сторона двустороннего прогона через `two_sided.run` на настоящем
    репозитории песочницы: держит связку «git worktree стороны — вызов
    pytest в нём»."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def test_ac7_two_sided_side_argv_cwd_env(self):
        """Обе стороны `two_sided.run`: argv, `cwd` и окружение вызова pytest.

        База — HEAD песочницы, ветка — от неё; метод — случайный узел
        `tests/<файл>.py::<Класс>::<метод>`. `PYTHONPATH` в окружении
        пульта есть (случайное значение) и нет. Вызов стороны N: argv —
        интерпретатор, `-m pytest`, узел, `--rootdir=<дерево>`, `-p
        artel_two_sided_report`, флаги пульта; `cwd` — дерево стороны
        (`base`, затем `head`) во временном каталоге; окружение —
        `PYTHONPYCACHEPREFIX` вне `cwd`, `ARTEL_TWO_SIDED_REPORT` = путь
        `report-N.jsonl` этого вызова, `PYTHONPATH`, начинающийся с
        каталога плагина.

        Ловит мутацию: `PYTHONPATH` собран с каталогом плагина в конце
        (модуль проверяемого дерева заслоняет плагин) или путь отчёта у
        обеих сторон один — проверка начала `PYTHONPATH` или значения
        `ARTEL_TWO_SIDED_REPORT` краснеет.
        """
        base_sha = self.git("rev-parse", "HEAD").strip()
        branch = "probe-" + "".join(self.rng.choices(string.ascii_lowercase, k=6))
        self.git("branch", branch)
        stem = "".join(self.rng.choices(string.ascii_lowercase, k=6))
        path = f"tests/test_{stem}.py"
        method = f"Probe{stem.title()}Test::test_{stem}"
        source = (f"import unittest\n\n\nclass Probe{stem.title()}Test("
                  f"unittest.TestCase):\n    def test_{stem}(self):\n"
                  f"        self.assertTrue(True)\n")
        methods = [two_sided.Method(path, path, method, source, source)]
        py = stack.pytest_python_executable()
        tmp = tempfile.TemporaryDirectory(prefix="probe-")
        self.addCleanup(tmp.cleanup)
        outer = Path(tmp.name).resolve()
        for n, pythonpath in enumerate((None, "/" + "".join(
                self.rng.choices(string.ascii_lowercase, k=8)))):
            temp = FixedTemp(outer / f"sys{n}")
            fake = FakeSubprocess()
            environ = self.probe_environ()
            with self.subTest(pythonpath=pythonpath, seed=self.seed), \
                    mock.patch.dict(os.environ, environ), \
                    mock.patch.object(tempfile, "mkdtemp", temp), \
                    mock.patch.object(two_sided, "subprocess", fake):
                os.environ.pop("PYTHONPATH", None)
                if pythonpath is not None:
                    os.environ["PYTHONPATH"] = pythonpath
                two_sided.run(self.root, branch, base_sha, methods)
                scratch = temp.dir("artel-two-sided-")
                plugin = str(scratch / "plugin")
                self.assertEqual(len(fake.calls), 2,
                                 f"зерно {self.seed}: "
                                 f"{[c['argv'] for c in fake.calls]}")
                for index, (call, side) in enumerate(
                        zip(fake.calls, ("base", "head"))):
                    tree = scratch / side
                    report = str(scratch / f"report-{index}.jsonl")
                    self.check_call(
                        call, f"two_sided сторона {side}", "run",
                        [py, "-m", "pytest", f"{path}::{method}",
                         f"--rootdir={tree}", "-p", "artel_two_sided_report",
                         *PULT_FLAGS],
                        tree,
                        {PREFIX_VAR: None, "ARTEL_TWO_SIDED_REPORT": report,
                         "PYTHONPATH": lambda v, p=plugin: v.startswith(p)})


if __name__ == "__main__":
    unittest.main()
