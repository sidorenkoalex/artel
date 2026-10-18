"""PATH прогона `pytest-own` в восьми местах запуска профиля: PATH
вызывающего без изменений, затем каталог `command[0]`, затем недостающие
`/usr/bin`, `/bin`, `/usr/sbin`, `/sbin`; `PATH` из `test_profile.env`
перекрывает собранное значение; настоящий прогон при урезанном PATH «как у
роли» находит `bash` и `date`.

Группа: долгоживущий

Восемь мест: `acceptance.run`, `acceptance.collect`,
`acceptance.run_repeat`, `acceptance.run_plank`, прогон полного набора без
наблюдения, с наблюдением (`acceptance.observed_full_suite()`) и в файл
лога (`log=`) — через публичный `acceptance.run_full_suite`, сторона
двустороннего прогона — через `two_sided.run` на настоящем репозитории
песочницы (`tests.sandbox.RealGitSandbox`: связка «git worktree стороны —
прогон в нём»). PATH, который получает прогон, читается из окружения
вызова подменённого модуля `subprocess` (`acceptance` и `two_sided`); PATH
вызывающего на время вызова — случайный набор каталогов (каталог `git`
в нём всегда: сторона двустороннего прогона заводит worktree git'ом по
имени), зерно печатается и входит в текст провала.

Красен до реализации: PATH прогона `pytest-own` — копия PATH вызывающего без каталога `command[0]` и без `/usr/bin`/`/bin`/`/usr/sbin`/`/sbin`, поэтому хвост PATH пуст, а обёртка при урезанном PATH падает на `bash`.
"""
import os
import random
import shutil
import stat
import string
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import MappingProxyType
from unittest import mock

from orchestrator import acceptance, project_profile, stack, targets
from orchestrator.advance_gates import two_sided
from tests.sandbox import RealGitSandbox

OWN = targets.PROFILE_RUNNER_OWN
PLACES = ("acceptance.run", "acceptance.collect", "acceptance.run_repeat",
          "acceptance.run_plank", "_run_full_suite_now без observe",
          "_run_full_suite_now с observe", "_run_full_suite_to_log",
          "two_sided._run_side")
FULL_PLACES = PLACES[4:7]
TWO_SIDED = PLACES[7]
# Места `orchestrator/acceptance.py`: каталог прогона они передают.
ACCEPTANCE_PLACES = PLACES[:7]
SYSTEM_DIRS = ("/usr/bin", "/bin", "/usr/sbin", "/sbin")
PS_ROW = "1 0 0.0 00:01 /bin/probe\n"

MODULE = '''import unittest


class ProbeTest(unittest.TestCase):
    def test_probe(self):
        self.assertTrue(True)
'''

# Обёртка «как у учебного проекта»: зовёт `bash` и `date` по имени, затем
# pytest интерпретатором из своей первой строки.
SHELL_WRAPPER = '''#!{python}
import subprocess, sys
subprocess.run(["bash", "-c", "true"], check=True)
subprocess.run(["date"], check=True, stdout=subprocess.DEVNULL)
sys.exit(subprocess.call([sys.executable, "-m", "pytest", *sys.argv[1:]]))
'''


def make_executable(path: Path, text: str = "#!/bin/sh\nexit 0\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


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
    pytest (`run` и `Popen`) запоминаются с argv, `cwd` и окружением; прочие
    `run` (`/bin/ps`) — строка процесса."""

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
        self.calls.append({"argv": argv, "cwd": kwargs.get("cwd"),
                           "env": dict(kwargs.get("env") or {})})
        return True

    def run(self, argv, **kwargs):
        if not self.remember(argv, kwargs):
            return subprocess.CompletedProcess(argv, 0, PS_ROW, "")
        return subprocess.CompletedProcess(argv, 0, "1 passed in 0.01s", "")

    def Popen(self, argv, **kwargs):
        self.remember(argv, kwargs)
        return FakeProc(argv)


class OwnProjectTest(RealGitSandbox):
    """Учебный проект `pytest-own` в репозитории песочницы: `workdir`, в нём
    каталог долгоживущих тестов с модулем-зондом."""

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
        self.venv_rel = f".venv_{self.word()}/bin"
        make_executable(self.root / self.workdir / self.venv_rel / "pytest")
        self.commit("учебный проект")
        git = shutil.which("git")
        self.assertIsNotNone(git, "git не найден в PATH процесса теста")
        self.git_dir = os.path.dirname(git)

    def word(self, k: int = 6) -> str:
        return "".join(self.rng.choices(string.ascii_lowercase, k=k))

    def where(self, *parts) -> str:
        return ", ".join([*map(str, parts), f"зерно {self.seed}"])

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        self.branch = f"probe-{self.word()}"
        self.git("branch", self.branch)
        self.base_sha = self.git("rev-parse", "HEAD").strip()

    def scratch(self, prefix: str) -> Path:
        path = Path(tempfile.mkdtemp(prefix=prefix)).resolve()
        self.addCleanup(shutil.rmtree, path, True)
        return path

    def profile(self, command, env=None) -> project_profile.Profile:
        return project_profile.Profile(
            command=tuple(command), long_lived_dir=self.checks,
            long_lived_name="test_<id>_<name>.py",
            weakening_scope=(f"{self.checks}/**",),
            mutation_claim_scope=(f"{self.checks}/**",),
            runner=OWN, workdir=self.workdir,
            env=MappingProxyType(dict(env or {})))

    def method(self) -> two_sided.Method:
        return two_sided.Method(self.module_rel, self.module_rel,
                                "ProbeTest::test_probe", MODULE, MODULE)

    def invoke(self, place: str, profile, scratch: Path):
        """Вызов места `place` с профилем `profile` через публичный вход."""
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
            return two_sided.run(self.root, self.branch, self.base_sha,
                                 [self.method()], profile=profile)
        kwargs = {"command": profile}
        if place == FULL_PLACES[2]:
            kwargs["log"] = scratch / "suite.log"
        if place == FULL_PLACES[0]:
            return acceptance.run_full_suite(self.root, **kwargs)
        with acceptance.observed_full_suite():
            return acceptance.run_full_suite(self.root, **kwargs)


class OwnPathCompositionTest(OwnProjectTest):
    """PATH прогона по местам — на подменённом `subprocess`."""

    def caller_path(self, must=()) -> str:
        """Случайный PATH вызывающего: несуществующие каталоги, случайная
        часть системных, каталоги `must` и каталог `git`; хотя бы одного
        системного каталога в нём нет."""
        parts = [f"/nonexistent-{self.word()}/bin"
                 for _ in range(self.rng.randint(1, 3))]
        parts += [d for d in SYSTEM_DIRS if self.rng.random() < 0.5]
        parts += [*must, self.git_dir]
        self.rng.shuffle(parts)
        parts = list(dict.fromkeys(parts))
        if set(SYSTEM_DIRS) <= set(parts):
            drop = self.rng.choice([d for d in SYSTEM_DIRS if d != self.git_dir])
            parts.remove(drop)
        return os.pathsep.join(parts)

    @staticmethod
    def expected_parts(caller: str, command_dirs=()) -> list:
        out = caller.split(os.pathsep)
        for directory in (*command_dirs, *SYSTEM_DIRS):
            if directory not in out:
                out.append(directory)
        return out

    def calls(self, place: str, profile, caller: str) -> list:
        fake = FakeSubprocess()
        scratch = self.scratch("artel-path-")
        with mock.patch.dict(os.environ, {"PATH": caller}), \
                mock.patch.object(acceptance, "subprocess", fake), \
                mock.patch.object(two_sided, "subprocess", fake):
            self.invoke(place, profile, scratch)
        self.assertTrue(fake.calls, f"{self.where(place)}: pytest не позван")
        return fake.calls

    def check_path(self, where: str, call: dict, caller: str,
                   command_dirs=()) -> None:
        """PATH вызова начинается с `caller` без изменений; хвост — каталоги
        `command_dirs` и системные, которых не было, по порядку. Хвост
        сверяется каталогами, какими их увидит процесс прогона (`realpath`
        от его `cwd`)."""
        actual = call["env"].get("PATH")
        self.assertIsNotNone(actual, f"{where}: в окружении прогона нет PATH")
        parts = actual.split(os.pathsep)
        head = caller.split(os.pathsep)
        self.assertEqual(parts[:len(head)], head,
                         f"{where}: PATH не начинается с PATH вызывающего: "
                         f"{actual!r}")
        expected = self.expected_parts(caller, command_dirs)[len(head):]
        cwd = str(call["cwd"])

        def seen(entry: str) -> str:
            return os.path.realpath(os.path.join(cwd, entry))

        self.assertEqual([seen(p) for p in parts[len(head):]],
                         [seen(p) for p in expected],
                         f"{where}: хвост PATH {parts[len(head):]!r}, ждали "
                         f"{expected!r}")

    def test_ac2_path_is_caller_then_command_dir_then_system_dirs(self):
        """PATH прогона — PATH вызывающего, каталог `command[0]`, недостающие системные.

        В каждом из восьми мест: команда профиля — абсолютный путь к
        исполняемому файлу вне PATH вызывающего, тот же путь, чей каталог в
        PATH уже есть, и голое имя файла, найденного поиском по PATH
        вызывающего. PATH вызывающего случайный (часть системных каталогов
        в нём есть, часть нет). PATH прогона начинается с PATH вызывающего
        без изменений; затем каталог `command[0]`, если его не было; затем
        те из `/usr/bin`, `/bin`, `/usr/sbin`, `/sbin`, которых не было, в
        этом порядке и без повторов.

        Ловит мутацию: PATH прогона остаётся копией PATH вызывающего, хвост
        не добавлен в одном из мест (например в `two_sided._run_side` или
        пути с наблюдением), системные каталоги добавлены в начало или с
        повтором уже имеющегося, каталог `command[0]` добавлен, хотя он уже
        в PATH, — PATH прогона расходится с ожидаемым.
        """
        outside = self.scratch("artel-cmd-")
        absolute = make_executable(outside / f"run-{self.word()}")
        found_dir = self.scratch("artel-found-")
        bare = make_executable(found_dir / f"run-{self.word()}")
        kinds = (
            ("абсолютный путь вне PATH", str(absolute), (),
             (str(outside),)),
            ("абсолютный путь, каталог уже в PATH", str(absolute),
             (str(outside),), (str(outside),)),
            ("голое имя, найдено по PATH", bare.name, (str(found_dir),),
             (str(found_dir),)),
        )
        for kind, head, must, command_dirs in kinds:
            for place in PLACES:
                with self.subTest(kind=kind, place=place, seed=self.seed):
                    caller = self.caller_path(must)
                    profile = self.profile((head, "-m", "pytest"),
                                           env={f"PROBE_{self.word().upper()}":
                                                self.word()})
                    for call in self.calls(place, profile, caller):
                        self.check_path(self.where(kind, place), call, caller,
                                        command_dirs)

    def test_ac2_profile_env_path_overrides_composed_value(self):
        """`PATH` из `test_profile.env` — ровно PATH прогона в каждом месте.

        Профиль задаёт `PATH` случайным значением; команда профиля —
        абсолютный путь вне PATH вызывающего, PATH вызывающего без части
        системных каталогов. В каждом из восьми мест прогон получает ровно
        значение профиля: ни PATH вызывающего, ни каталога `command[0]`, ни
        системных каталогов в нём нет.

        Ловит мутацию: собранный PATH пишется в окружение после
        `test_profile.env` или хвост дописывается и к PATH профиля — PATH
        прогона не равен значению профиля.
        """
        outside = self.scratch("artel-cmd-")
        absolute = make_executable(outside / f"run-{self.word()}")
        for place in PLACES:
            with self.subTest(place=place, seed=self.seed):
                override = os.pathsep.join(
                    f"/profile-{self.word()}/bin"
                    for _ in range(self.rng.randint(1, 3)))
                profile = self.profile((str(absolute), "-m", "pytest"),
                                       env={"PATH": override})
                for call in self.calls(place, profile, self.caller_path()):
                    self.assertEqual(call["env"].get("PATH"), override,
                                     self.where(place))

    def test_ac3_command_dir_by_kind_of_command(self):
        """Каталог `command[0]` по видам: абсолютный, относительный с `/`, голое имя не найдено.

        Абсолютный путь — его каталог (восемь мест). Относительный путь с
        `/` (`.venv_…/bin/pytest`, есть в `workdir`) в семи местах
        `orchestrator/acceptance.py` — каталог, разрешённый от `workdir`
        профиля (каталог процесса теста — другой); в
        `two_sided._run_side` — PATH вызывающего плюс недостающие системные,
        без каталога команды. Голое имя, которого поиск по PATH вызывающего
        не находит, — PATH вызывающего плюс недостающие системные (восемь
        мест). Ни одно место не бросает исключения.

        Ловит мутацию: относительный `command[0]` разрешается от каталога
        вызывающего процесса (`os.path.abspath`) — в хвосте каталог вне
        `workdir`; `two_sided._run_side` без каталога прогона добавляет
        каталог относительной команды; для ненайденного голого имени
        сборка добавляет пустой каталог, `None` или падает
        (`os.path.dirname(None)`) — хвост расходится или место бросает.
        """
        outside = self.scratch("artel-cmd-")
        absolute = make_executable(outside / f"run-{self.word()}")
        relative = f"{self.venv_rel}/pytest"
        venv_dir = str(self.root / self.workdir / self.venv_rel)
        missing = f"absent-{self.word(10)}"
        cases = [("абсолютный путь", str(absolute), place, (str(outside),))
                 for place in PLACES]
        cases += [("относительный путь с /", relative, place, (venv_dir,))
                  for place in ACCEPTANCE_PLACES]
        cases.append(("относительный путь с / без каталога прогона",
                      relative, TWO_SIDED, ()))
        cases += [("голое имя не найдено", missing, place, ())
                  for place in PLACES]
        for kind, head, place, command_dirs in cases:
            with self.subTest(kind=kind, place=place, seed=self.seed):
                caller = self.caller_path()
                self.assertIsNone(shutil.which(missing, path=caller))
                profile = self.profile((head, "-m", "pytest"))
                for call in self.calls(place, profile, caller):
                    self.check_path(self.where(kind, place), call, caller,
                                    command_dirs)


class OwnRolePathRunTest(OwnProjectTest):
    """Настоящий прогон учебного проекта при урезанном PATH «как у роли»."""

    def test_ac1_wrapper_finds_bash_and_date_with_role_like_path(self):
        """Обёртка, зовущая `bash` и `date` по имени, зелёная при PATH из одного каталога интерпретатора.

        PATH вызывающего — только каталог интерпретатора пульта (нет
        `/usr/bin` и `/bin`); команда профиля — обёртка вне дерева с этим
        интерпретатором в первой строке, она зовёт `bash` и `date` по имени
        и затем pytest. `acceptance.run_plank` даёт код 0, полный прогон
        набора (`acceptance.run_full_suite`) — зелёный; в выводе обоих нет
        `FileNotFoundError`.

        Ловит мутацию: системные каталоги не дописываются в PATH прогона
        (или дописываются только у одного из двух мест) — обёртка падает
        `FileNotFoundError: 'bash'`, код выхода не 0, прогон красный.
        """
        python = stack.pytest_python_executable()
        wrapper = make_executable(self.scratch("artel-wrapper-") /
                                  f"run-{self.word()}",
                                  SHELL_WRAPPER.format(python=python))
        role_path = os.path.dirname(python)
        for directory in ("/usr/bin", "/bin"):
            self.assertNotEqual(os.path.realpath(role_path),
                                os.path.realpath(directory))
        profile = self.profile((str(wrapper),))
        module = str(self.root / self.module_rel)
        with mock.patch.dict(os.environ, {"PATH": role_path}):
            code, plank_output = acceptance.run_plank([module], self.root,
                                                      profile=profile)
            green, suite_output = acceptance.run_full_suite(self.root,
                                                            command=profile)
        self.assertEqual(code, 0, f"{self.where('run_plank')}: "
                                  f"{plank_output[-1500:]}")
        self.assertNotIn("FileNotFoundError", plank_output,
                         self.where("run_plank"))
        self.assertTrue(green, f"{self.where('полный прогон')}: "
                               f"{suite_output[-1500:]}")
        self.assertNotIn("FileNotFoundError", suite_output,
                         self.where("полный прогон"))


if __name__ == "__main__":
    unittest.main()
