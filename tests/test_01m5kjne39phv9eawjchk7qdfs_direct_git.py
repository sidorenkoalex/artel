"""Git в процессах тестов — напрямую, без системной обёртки xcrun.

Группа: долгоживущий
Красен до реализации: модуля tests/direct_git.py ещё нет — импорт `tests.direct_git` в модульных случаях падает, у пакета `tests` нет `DIRECT_GIT_DIR` (AC-6, AC-7); AC-8 держит существующее свойство PATH роли и зелен и до кода.

Модульные случаи (AC-1…AC-5) не зависят от машины: первый `git` по PATH
даёт подмена `shutil.which` модуля `tests.direct_git`, которая ищет git
по переданному `path=` в заданном сценарием наборе каталогов; каталог
разработчика — временный, `xcode-select` — подмена `subprocess.run`.
Каждый отрицательный случай отличается от положительного ровно одним
условием. Входы PATH порождаются `random` при каждом запуске, зерно
печатается и входит в текст провала.

AC-6 — проводка `tests/__init__.py`: пакет `tests` импортируется в
отдельном интерпретаторе, где на месте `tests.direct_git` стоит
поддельный модуль, записывающий вызовы.

AC-7 и AC-8 — свойства процесса теста на машине с обёрткой и PATH шага
роли; AC-8 держит связку «`runner.role_env` — PATH процесса теста» в
песочнице `TmpRootTest` (keychain, дом роли и сверка venv подменены там).
"""

import inspect
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tests
from tests.sandbox import TmpRootTest

USR_BIN = "/usr/bin"
USR_BIN_GIT = "/usr/bin/git"
# Варианты записи `/usr/bin`, равные ему после `os.path.normpath`.
USR_BIN_SPELLINGS = ("/usr/bin", "/usr/bin/", "/usr//bin", "/usr/./bin")
# Каталоги без git — наполнитель PATH до и после `/usr/bin`.
NO_GIT_DIRS = ("/bin", "/sbin", "/usr/sbin", "/usr/local/sbin",
               "/opt/tools/bin", "/Users/someone/.local/bin", "")
OTHER_GIT_DIR = "/opt/homebrew/bin"
# Команды утверждения AC-7(в).
COMPARED_COMMANDS = ("python3", "bash", "sh", "node", "gh", "claude",
                     "codex", "uv")


def make_developer_dir(root: Path, name: str, mode: int | None = 0o755) -> str:
    """Каталог разработчика `root/name` с файлом `usr/bin/git` режима
    `mode`; `mode=None` — файла нет (каталог `usr/bin` есть)."""
    devdir = root / name
    (devdir / "usr" / "bin").mkdir(parents=True)
    if mode is not None:
        git = devdir / "usr" / "bin" / "git"
        git.write_text("#!/bin/sh\nexit 0\n")
        git.chmod(mode)
    return str(devdir)


def direct_git_module():
    """Модуль `tests.direct_git` — импорт в теле теста, чтобы его
    отсутствие было провалом теста, а не ошибкой сбора файла."""
    from tests import direct_git
    return direct_git


def dev_bin(devdir: str) -> str:
    return os.path.normpath(os.path.join(devdir, "usr", "bin"))


class FakeWhich:
    """Подмена `shutil.which`: ищет `git` по каталогам переданного
    `path=` в наборе `git_dirs` (сравнение после `normpath`); без `path=`
    ничего не находит — запасного пути у функции быть не должно."""

    def __init__(self, git_dirs):
        self.git_dirs = {os.path.normpath(d) for d in git_dirs}
        self.calls = []

    def __call__(self, cmd, mode=os.F_OK | os.X_OK, path=None):
        self.calls.append((cmd, path))
        if path is None or cmd != "git":
            return None
        for element in path.split(os.pathsep):
            if element and os.path.normpath(element) in self.git_dirs:
                return os.path.join(element, "git")
        return None


class FakeRun:
    """Подмена `subprocess.run` для `xcode-select -p`: пишет вызовы и
    отвечает по сценарию — `stdout`/`returncode` либо исключение."""

    def __init__(self, stdout="", returncode=0, exc=None):
        self.stdout = stdout
        self.returncode = returncode
        self.exc = exc
        self.calls = []

    def __call__(self, args, *a, **kwargs):
        self.calls.append((args, kwargs))
        if self.exc is not None:
            raise self.exc
        if self.returncode and kwargs.get("check"):
            raise subprocess.CalledProcessError(self.returncode, args,
                                                output=self.stdout)
        text = (kwargs.get("text") or kwargs.get("universal_newlines")
                or kwargs.get("encoding") or kwargs.get("errors"))
        out = self.stdout if text else self.stdout.encode()
        err = "" if text else b""
        return subprocess.CompletedProcess(args, self.returncode,
                                           stdout=out, stderr=err)


class ModularCase(unittest.TestCase):
    """Сценарий модульного случая: случайный PATH, временный каталог
    разработчика, подмены `which`/`run`."""

    def setUp(self):
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.devdir = make_developer_dir(self.tmp, "Developer")

    def msg(self, extra=""):
        return f"зерно: {self.seed}; {extra}"

    def random_path(self, usr_bin=None):
        """(before, usr_bin, after) — элементы PATH; в `before` нет git и
        нет `/usr/bin`, в `after` может стоять второй `/usr/bin`."""
        before = [self.rng.choice(NO_GIT_DIRS)
                  for _ in range(self.rng.randrange(0, 5))]
        after = [self.rng.choice(NO_GIT_DIRS + ("/usr/bin", OTHER_GIT_DIR))
                 for _ in range(self.rng.randrange(0, 5))]
        if usr_bin is None:
            usr_bin = self.rng.choice(USR_BIN_SPELLINGS)
        return before, usr_bin, after

    def call(self, environ, *, git_dirs=(USR_BIN,), run=None,
             platform="darwin", developer_dir="default"):
        """Вызов `prefer_direct_git` под подменами; `developer_dir`
        по умолчанию — функция, отдающая временный каталог сценария."""
        if developer_dir == "default":
            devdir = self.devdir
            developer_dir = lambda: devdir  # noqa: E731
        direct_git = direct_git_module()
        self.which = FakeWhich(git_dirs)
        self.run = run if run is not None else FakeRun(returncode=1)
        with mock.patch("shutil.which", self.which), \
                mock.patch("subprocess.run", self.run):
            extra = []
            if hasattr(direct_git, "which"):
                extra.append(mock.patch.object(direct_git, "which", self.which))
            if hasattr(direct_git, "run"):
                extra.append(mock.patch.object(direct_git, "run", self.run))
            for patcher in extra:
                patcher.start()
            try:
                return direct_git.prefer_direct_git(
                    environ, platform=platform, developer_dir=developer_dir)
            finally:
                for patcher in extra:
                    patcher.stop()

    def assert_unchanged(self, environ, result, original, label):
        self.assertIsNone(result, self.msg(f"{label}: возвращено {result!r}"))
        self.assertEqual(environ, original,
                         self.msg(f"{label}: environ изменён"))


class Ac1PlatformTest(ModularCase):
    def test_ac1_signature_and_non_darwin_platform_changes_nothing(self):
        """Сигнатура и отказ вне darwin.

        Модуль экспортирует `prefer_direct_git` с параметрами `environ`,
        `platform` (по умолчанию `sys.platform`) и `developer_dir` (по
        умолчанию `None`). Положительный сценарий AC-5, в котором
        платформа — случайная не-darwin, оставляет environ прежним и
        возвращает `None`.

        Ловит мутацию: убрана проверка платформы — на `platform="linux"`
        каталог разработчика вставляется в PATH и возвращается.
        """
        params = inspect.signature(
            direct_git_module().prefer_direct_git).parameters
        self.assertIn("environ", params)
        self.assertIn("platform", params)
        self.assertIn("developer_dir", params)
        self.assertEqual(params["platform"].default, sys.platform)
        self.assertIsNone(params["developer_dir"].default)
        for platform in ("linux", "win32", "cygwin", "freebsd14"):
            with self.subTest(platform=platform):
                before, usr_bin, after = self.random_path()
                environ = {"PATH": os.pathsep.join(before + [usr_bin] + after),
                           "HOME": "/home/x"}
                original = dict(environ)
                result = self.call(environ, platform=platform)
                self.assert_unchanged(environ, result, original, platform)


class Ac2PathTest(ModularCase):
    def test_ac2_no_path_other_git_first_or_no_usr_bin_changes_nothing(self):
        """Три отрицательных случая PATH, каждый — одно отличие от AC-5.

        (1) ключа `PATH` в environ нет; (2) каталог с другим git стоит
        раньше `/usr/bin`; (3) элемента `/usr/bin` в PATH нет. Во всех —
        environ прежний, возвращено `None`, исключения нет.

        Ловит мутацию: проверка «первый git — `/usr/bin/git`» снята — в
        случае (2) каталог разработчика вставляется перед `/usr/bin`,
        хотя git и так находится не через обёртку.
        """
        before, usr_bin, after = self.random_path()
        with self.subTest(case="нет PATH"):
            environ = {"HOME": "/home/x", "LANG": "C"}
            original = dict(environ)
            result = self.call(environ)
            self.assert_unchanged(environ, result, original, "нет PATH")
        with self.subTest(case="другой git раньше /usr/bin"):
            pos = self.rng.randrange(0, len(before) + 1)
            elements = before[:pos] + [OTHER_GIT_DIR] + before[pos:] \
                + [usr_bin] + after
            environ = {"PATH": os.pathsep.join(elements)}
            original = dict(environ)
            result = self.call(environ, git_dirs=(USR_BIN, OTHER_GIT_DIR))
            self.assert_unchanged(environ, result, original,
                                  f"другой git: {elements}")
        with self.subTest(case="нет /usr/bin"):
            elements = [e for e in before + after
                        if os.path.normpath(e or ".") != USR_BIN]
            environ = {"PATH": os.pathsep.join(elements)}
            original = dict(environ)
            result = self.call(environ)
            self.assert_unchanged(environ, result, original,
                                  f"нет /usr/bin: {elements}")


class Ac3DeveloperDirTest(ModularCase):
    def positive_environ(self, **extra):
        before, usr_bin, after = self.random_path()
        environ = {"PATH": os.pathsep.join(before + [usr_bin] + after)}
        environ.update(extra)
        return environ, before, after

    def assert_inserted(self, environ, result, devdir, before, label):
        self.assertIsNotNone(result, self.msg(f"{label}: вставки нет"))
        self.assertEqual(os.path.normpath(result), dev_bin(devdir),
                         self.msg(f"{label}: вставлен не тот каталог"))
        self.assertEqual(environ["PATH"].split(os.pathsep)[len(before)],
                         result, self.msg(f"{label}: {environ['PATH']}"))

    def test_ac3_developer_dir_function_wins_over_environment(self):
        """Переданная `developer_dir()` сильнее `DEVELOPER_DIR`.

        В environ `DEVELOPER_DIR` указывает на второй годный каталог
        разработчика, функция — на первый: вставлен каталог функции.

        Ловит мутацию: `DEVELOPER_DIR` проверяется раньше переданной
        функции — вставляется `<DEVELOPER_DIR>/usr/bin`.
        """
        other = make_developer_dir(self.tmp, "OtherDeveloper")
        environ, before, _ = self.positive_environ(DEVELOPER_DIR=other)
        result = self.call(environ)
        self.assert_inserted(environ, result, self.devdir, before, "функция")

    def test_ac3_developer_dir_env_used_without_xcode_select(self):
        """`DEVELOPER_DIR` без функции — используется он, `xcode-select` нет.

        Функция не передана, `DEVELOPER_DIR` — временный каталог
        разработчика: каталог вставлен, подмена `subprocess.run` не
        получила ни одного вызова.

        Ловит мутацию: `xcode-select -p` вызывается всегда, а
        `DEVELOPER_DIR` — только запасной путь: подмена `run` получает
        вызов (а при его ответе — вставлен чужой каталог).
        """
        other = make_developer_dir(self.tmp, "FromXcodeSelect")
        environ, before, _ = self.positive_environ(DEVELOPER_DIR=self.devdir)
        run = FakeRun(stdout=other + "\n")
        result = self.call(environ, run=run, developer_dir=None)
        self.assertEqual(run.calls, [], self.msg("xcode-select вызван"))
        self.assert_inserted(environ, result, self.devdir, before, "env")

    def test_ac3_xcode_select_output_with_timeout(self):
        """Без функции и `DEVELOPER_DIR` — вывод `xcode-select -p`, таймаут 5 с.

        Подмена `subprocess.run` отвечает путём временного каталога с
        переводом строки: каталог вставлен; вызов — `xcode-select` с
        `-p` и `timeout=5`.

        Ловит мутацию: вызов `xcode-select` без `timeout=5` (или вывод
        не обрезан от перевода строки — вставки нет).
        """
        environ, before, _ = self.positive_environ()
        run = FakeRun(stdout=self.devdir + "\n")
        result = self.call(environ, run=run, developer_dir=None)
        self.assertEqual(len(run.calls), 1, self.msg(f"вызовы: {run.calls}"))
        args, kwargs = run.calls[0]
        argv = [args] if isinstance(args, str) else list(args)
        self.assertEqual(os.path.basename(str(argv[0])), "xcode-select",
                         self.msg(f"argv: {argv}"))
        self.assertIn("-p", argv, self.msg(f"argv: {argv}"))
        self.assertEqual(kwargs.get("timeout"), 5, self.msg(f"kwargs: {kwargs}"))
        self.assert_inserted(environ, result, self.devdir, before, "xcode")

    def test_ac3_xcode_select_failure_changes_nothing(self):
        """Ошибка, таймаут или пустой вывод `xcode-select` — без изменений.

        Перебор: ненулевой код выхода (в выводе при этом путь годного
        каталога), `FileNotFoundError`, `OSError`, `TimeoutExpired`,
        пустой и пробельный вывод. Во всех — environ прежний, `None`,
        исключение наружу не выходит.

        Ловит мутацию: код выхода `xcode-select` не проверяется — при
        ошибке с путём в выводе каталог вставляется; либо
        `TimeoutExpired` не перехвачен — исключение выходит наружу.
        """
        cases = {
            "код выхода 1": FakeRun(stdout=self.devdir + "\n", returncode=1),
            "нет xcode-select": FakeRun(exc=FileNotFoundError("xcode-select")),
            "OSError": FakeRun(exc=OSError("сбой")),
            "таймаут": FakeRun(exc=subprocess.TimeoutExpired(
                ["xcode-select", "-p"], 5)),
            "пустой вывод": FakeRun(stdout=""),
            "пробельный вывод": FakeRun(stdout="\n"),
        }
        for label, run in cases.items():
            with self.subTest(case=label):
                environ, _, _ = self.positive_environ()
                original = dict(environ)
                result = self.call(environ, run=run, developer_dir=None)
                self.assert_unchanged(environ, result, original, label)


class Ac4DeveloperGitTest(ModularCase):
    def test_ac4_missing_or_non_executable_developer_git_changes_nothing(self):
        """Нет `usr/bin/git` или он не исполняем — без изменений.

        Каталог разработчика без файла `usr/bin/git`; затем с файлом
        режима 0644. Во всех — environ прежний, возвращено `None`.

        Ловит мутацию: проверка `exists` без `X_OK` — неисполняемый
        `usr/bin/git` принимается, каталог вставляется.
        """
        for label, mode in (("нет файла", None), ("не исполняем", 0o644)):
            with self.subTest(case=label):
                devdir = make_developer_dir(
                    self.tmp, f"Dev-{label.replace(' ', '-')}", mode)
                before, usr_bin, after = self.random_path()
                environ = {"PATH": os.pathsep.join(before + [usr_bin] + after)}
                original = dict(environ)
                result = self.call(environ, developer_dir=lambda: devdir)
                self.assert_unchanged(environ, result, original, label)


class Ac5InsertTest(ModularCase):
    def test_ac5_inserted_before_first_usr_bin_and_idempotent(self):
        """Вставка ровно перед первым `/usr/bin` и повтор без изменений.

        Десять случайных PATH (пустые элементы, второй `/usr/bin` после
        первого, запись `/usr/bin` в вариантах `/usr/bin/`, `/usr//bin`)
        и один фиксированный с первым `/usr/bin/`: PATH после вызова —
        прежние элементы до, вставленный каталог, прежние элементы после;
        возвращён вставленный каталог; поиск git шёл по PATH environ.
        Повторный вызов — PATH тот же, `None`.

        Ловит мутацию: сравнение с `/usr/bin` без `normpath` — при первом
        элементе `/usr/bin/` вставки нет либо она встаёт перед вторым,
        точным `/usr/bin`; поиск `shutil.which("git")` без `path=` —
        подмена ничего не находит, вставки нет.
        """
        runs = [self.random_path() for _ in range(10)]
        runs.append((["", "/bin"], "/usr/bin/", ["/usr/bin", ""]))
        for i, (before, usr_bin, after) in enumerate(runs):
            with self.subTest(run=i):
                elements = before + [usr_bin] + after
                path = os.pathsep.join(elements)
                environ = {"PATH": path, "HOME": "/home/x"}
                result = self.call(environ, git_dirs=(USR_BIN, dev_bin(self.devdir)))
                label = f"PATH до: {elements!r}"
                self.assertIsNotNone(result, self.msg(label))
                self.assertEqual(os.path.normpath(result), dev_bin(self.devdir),
                                 self.msg(label))
                self.assertEqual(environ["PATH"].split(os.pathsep),
                                 before + [result, usr_bin] + after,
                                 self.msg(label))
                self.assertEqual(environ["HOME"], "/home/x", self.msg(label))
                self.assertIn(("git", path), self.which.calls, self.msg(label))
                after_first = dict(environ)
                again = self.call(environ, git_dirs=(USR_BIN, dev_bin(self.devdir)))
                self.assertIsNone(again, self.msg(f"повтор; {label}"))
                self.assertEqual(environ, after_first, self.msg(f"повтор; {label}"))


class Ac6PackageWiringTest(unittest.TestCase):
    PROBE = r"""
import json, os, sys, types
calls = []
sentinel = json.loads(sys.argv[1])
fake = types.ModuleType("tests.direct_git")
def prefer_direct_git(*args, **kwargs):
    env = args[0] if args else kwargs.get("environ")
    calls.append(env is os.environ)
    return sentinel
fake.prefer_direct_git = prefer_direct_git
sys.modules["tests.direct_git"] = fake
import tests
print(json.dumps({"calls": calls,
                  "has": hasattr(tests, "DIRECT_GIT_DIR"),
                  "value": getattr(tests, "DIRECT_GIT_DIR", None)}))
"""

    def test_ac6_package_import_calls_prefer_direct_git_and_stores_result(self):
        """Импорт пакета `tests` зовёт `prefer_direct_git(os.environ)`.

        В отдельном интерпретаторе на месте `tests.direct_git` стоит
        поддельный модуль, отдающий заданное значение (случайная строка
        либо `None`); после `import tests` вызов ровно один, с самим
        объектом `os.environ`, а `tests.DIRECT_GIT_DIR` равен значению.

        Ловит мутацию: `DIRECT_GIT_DIR = None` без вызова — вызовов ноль,
        значение-строка не сохранено; вызов на копии `os.environ` —
        переданный объект не `os.environ`.
        """
        seed = random.randrange(2 ** 32)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        root = Path(tests.__file__).resolve().parent.parent
        for sentinel in (f"/tmp/dev-{rng.randrange(10 ** 9)}/usr/bin", None):
            with self.subTest(sentinel=sentinel):
                proc = subprocess.run(
                    [sys.executable, "-c", self.PROBE, json.dumps(sentinel)],
                    cwd=root, capture_output=True, text=True, timeout=60)
                self.assertEqual(proc.returncode, 0,
                                 f"зерно: {seed}; {proc.stderr}")
                got = json.loads(proc.stdout.strip().splitlines()[-1])
                self.assertEqual(got["calls"], [True], f"зерно: {seed}; {got}")
                self.assertTrue(got["has"], f"зерно: {seed}; {got}")
                self.assertEqual(got["value"], sentinel, f"зерно: {seed}; {got}")


def run_output(argv, cwd):
    """(код выхода, stdout, stderr) команды `argv` — через `Popen`, мимо
    подменённого песочницей `subprocess.run`."""
    proc = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate(timeout=30)
    return proc.returncode, out, err


def first_index(elements, directory):
    target = os.path.normpath(directory)
    for i, element in enumerate(elements):
        if element and os.path.normpath(element) == target:
            return i
    return None


class Ac7WrapperMachineTest(unittest.TestCase):
    def wrapper_developer_bin(self):
        """Каталог `<каталог разработчика>/usr/bin` машины с обёрткой
        либо пропуск с причиной."""
        if sys.platform != "darwin":
            self.skipTest(f"платформа {sys.platform}, не darwin")
        if not os.path.isfile(USR_BIN_GIT):
            self.skipTest(f"нет {USR_BIN_GIT}")
        try:
            code, out, err = run_output(["xcode-select", "-p"], None)
        except (OSError, subprocess.SubprocessError) as exc:
            self.skipTest(f"xcode-select -p не ответил: {exc}")
        if code != 0 or not out.strip():
            self.skipTest(f"xcode-select -p: код {code}, {err.strip()}")
        devbin = os.path.join(out.strip(), "usr", "bin")
        if not os.access(os.path.join(devbin, "git"), os.X_OK):
            self.skipTest(f"в {devbin} нет исполняемого git")
        elements = os.environ.get("PATH", "").split(os.pathsep)
        without = [e for e in elements
                   if not e or os.path.normpath(e) != os.path.normpath(devbin)]
        found = shutil.which("git", path=os.pathsep.join(without))
        if found is None or os.path.normpath(found) != USR_BIN_GIT:
            self.skipTest(f"git по PATH без {devbin} — {found}, не {USR_BIN_GIT}")
        return devbin, elements, without

    def test_ac7_wrapper_machine_direct_git_wired_and_equivalent(self):
        """Машина с обёрткой: PATH процесса теста ведёт к git напрямую.

        (а) В `os.environ["PATH"]` каталог разработчика стоит раньше
        первого `/usr/bin`; `tests.DIRECT_GIT_DIR` — этот каталог или
        `None`; сам тест PATH не меняет. (б) git по PATH и `/usr/bin/git`
        по абсолютным путям дают тот же `--version`, `--exec-path` и
        `config --get init.defaultBranch`. (в) `python3`, `bash`, `sh`,
        `node`, `gh`, `claude`, `codex`, `uv` по PATH с каталогом и без
        него — тот же файл либо пара `/usr/bin/<имя>` —
        `<каталог>/usr/bin/<имя>`.

        Ловит мутацию: `DIRECT_GIT_DIR = None` без вызова в
        `tests/__init__.py` — при запуске pytest из окружения без вставки
        каталога разработчика нет перед `/usr/bin`, (а) красен.
        """
        path_at_start = os.environ.get("PATH")
        devbin, elements, without = self.wrapper_developer_bin()
        # (а)
        dev_index = first_index(elements, devbin)
        usr_index = first_index(elements, USR_BIN)
        self.assertIsNotNone(dev_index, f"{devbin} нет в PATH: {elements}")
        self.assertIsNotNone(usr_index, f"/usr/bin нет в PATH: {elements}")
        self.assertLess(dev_index, usr_index, f"PATH: {elements}")
        if tests.DIRECT_GIT_DIR is not None:
            self.assertEqual(os.path.normpath(tests.DIRECT_GIT_DIR),
                             os.path.normpath(devbin))
        # (б)
        direct = shutil.which("git", path=os.environ["PATH"])
        self.assertIsNotNone(direct)
        with tempfile.TemporaryDirectory() as cwd:
            for args in (["--version"], ["--exec-path"],
                         ["config", "--get", "init.defaultBranch"]):
                with self.subTest(args=args):
                    self.assertEqual(run_output([direct] + args, cwd),
                                     run_output([USR_BIN_GIT] + args, cwd))
        # (в)
        current = os.environ["PATH"]
        stripped = os.pathsep.join(without)
        for name in COMPARED_COMMANDS:
            with self.subTest(command=name):
                now = shutil.which(name, path=current)
                before = shutil.which(name, path=stripped)
                pair = (now is not None and before is not None
                        and os.path.normpath(before) == f"{USR_BIN}/{name}"
                        and os.path.normpath(now) == os.path.normpath(
                            os.path.join(devbin, name)))
                self.assertTrue(now == before or pair,
                                f"{name}: сейчас {now}, без каталога {before}")
        self.assertEqual(os.environ.get("PATH"), path_at_start)


class Ac8RolePathTest(TmpRootTest):
    """Связка «`runner.role_env` — PATH процесса теста»: PATH шага роли,
    собранный в процессе теста, находит git и объявленные инструменты."""

    def test_ac8_role_path_finds_git_and_declared_tools(self):
        """PATH шага роли в процессе теста находит git и инструменты.

        PATH роли — `runner.role_env()["PATH"]`: git по нему — исполняемый
        файл с тем же `--version`, что `/usr/bin/git`; каждый объявленный
        инструмент, кроме `python3`, находится по нему, и каталог
        `runner.declared_tool_path(<имя>)` в нём стоит; для `python3` в
        нём стоит каталог `sys.executable`. Отказ сборки — пропуск с
        текстом отказа.

        Ловит мутацию: PATH роли собирается только из `venv/bin` и
        каталога `sys.executable`, без каталогов объявленных инструментов —
        git, `gh`, `claude` по PATH роли не находятся, тест красен.
        """
        from orchestrator import runner, stack
        refusal = None
        try:
            role_path = runner.role_env()["PATH"]
            tools = {name: runner.declared_tool_path(name)
                     for name in stack.DECLARED_TOOLS}
        except OSError as exc:
            refusal = str(exc)
        if refusal is not None:
            # Пропуск — только при отказе «инструмент не найден» (решение
            # гейта SPEC); любой другой отказ сборки — красный тест.
            self.assertIn("объявленный инструмент не найден в PATH", refusal)
            self.skipTest("сборка окружения роли отказала: "
                          "объявленный инструмент не найден в PATH")
        dirs = [os.path.normpath(d) for d in role_path.split(os.pathsep) if d]
        git = shutil.which("git", path=role_path)
        self.assertIsNotNone(git, f"git не найден по PATH роли: {role_path}")
        self.assertTrue(os.access(git, os.X_OK), git)
        if not os.path.isfile(USR_BIN_GIT):
            self.skipTest("нет /usr/bin/git для сверки --version")
        self.assertEqual(run_output([git, "--version"], None),
                         run_output([USR_BIN_GIT, "--version"], None))
        for name, tool in tools.items():
            with self.subTest(tool=name):
                if name == "python3":
                    self.assertIn(os.path.normpath(
                        str(Path(sys.executable).parent)), dirs, role_path)
                    continue
                self.assertIsNotNone(shutil.which(name, path=role_path),
                                     f"{name} не найден по PATH роли: {role_path}")
                self.assertIn(os.path.normpath(os.path.dirname(tool)), dirs,
                              f"{name}: {tool}; PATH роли: {role_path}")


if __name__ == "__main__":
    unittest.main()
