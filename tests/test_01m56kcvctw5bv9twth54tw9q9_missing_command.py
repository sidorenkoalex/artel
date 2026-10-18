"""Нет исполняемого файла команды профиля `pytest-own`: именованный отказ
«команда профиля <имя> не найдена» каналом каждого места запуска, без
`FileNotFoundError` наружу; полный прогон гейта — «прогон не начат» без
записи в кеш итогов. У `pult-pytest` `FileNotFoundError` запуска по-прежнему
доходит до вызывающего; `FileNotFoundError` не запуска (файл лога) отказом
о команде не называется.

Группа: долгоживущий

Восемь мест: `acceptance.run`, `acceptance.collect`,
`acceptance.run_repeat`, `acceptance.run_plank`, прогон полного набора без
наблюдения, с наблюдением (`acceptance.observed_full_suite()`) и в файл
лога (`log=`) — через публичный `acceptance.run_full_suite`, сторона
двустороннего прогона — через `two_sided.run`; полный прогон гейта — через
`acceptance.full_suite`. Настоящие прогоны на настоящем репозитории
песочницы (`tests.sandbox.RealGitSandbox`: связка «git worktree стороны —
прогон в нём», «чистое дерево — ключ итога полного прогона»).
Отсутствующая команда — абсолютный путь к несуществующему файлу и голое
имя, которого нет в PATH; имена случайные, зерно печатается и входит в
текст провала.

Красен до реализации: запуск процесса команды профиля в местах `orchestrator/acceptance.py` не перехвачен — `FileNotFoundError` выходит из `run`/`collect`/`run_repeat`/`run_plank`/`run_full_suite`/`full_suite` наружу вместо отказа «команда профиля <имя> не найдена».
"""
import os
import random
import shutil
import stat
import string
import tempfile
import unittest
from pathlib import Path
from types import MappingProxyType

from orchestrator import acceptance, project_profile, stack, targets
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

MODULE = '''import unittest


class ProbeTest(unittest.TestCase):
    def test_probe(self):
        self.assertTrue(True)
'''

# Обёртка-счётчик: строка в файл зонда на каждый запуск, затем pytest.
COUNTING_WRAPPER = '''#!{python}
import subprocess, sys
with open({probe!r}, "a", encoding="utf-8") as fh:
    fh.write("run\\n")
sys.exit(subprocess.call([sys.executable, "-m", "pytest", *sys.argv[1:]]))
'''


def refusal(name: str) -> str:
    return f"команда профиля {name} не найдена"


class MissingCommandProjectTest(RealGitSandbox):
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
        tests_dir = self.root / "tests"
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / f"test_root_{self.word()}.py").write_text(
            MODULE, encoding="utf-8")
        self.commit("учебный проект")

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

    def profile(self, command, runner: str = OWN) -> project_profile.Profile:
        own = runner == OWN
        lld = self.checks if own else "tests"
        return project_profile.Profile(
            command=tuple(command), long_lived_dir=lld,
            long_lived_name="test_<id>_<name>.py",
            weakening_scope=(f"{lld}/**",), mutation_claim_scope=(f"{lld}/**",),
            runner=runner, workdir=self.workdir if own else "",
            env=MappingProxyType({}))

    def missing_heads(self) -> list:
        """(вид, `command[0]`): абсолютный путь к несуществующему файлу и
        голое имя, которого нет в PATH."""
        absent = self.scratch("artel-absent-") / f"run-{self.word(10)}"
        bare = f"absent-{self.word(10)}"
        self.assertFalse(absent.exists())
        self.assertIsNone(shutil.which(bare))
        return [("абсолютный путь", str(absent)), ("голое имя", bare)]

    def method(self) -> two_sided.Method:
        return two_sided.Method(self.module_rel, self.module_rel,
                                "ProbeTest::test_probe", MODULE, MODULE)

    def invoke(self, place: str, profile, scratch: Path, log: Path | None = None):
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
            kwargs["log"] = log or scratch / "suite.log"
        if place == FULL_PLACES[0]:
            return acceptance.run_full_suite(self.root, **kwargs)
        with acceptance.observed_full_suite():
            return acceptance.run_full_suite(self.root, **kwargs)


class MissingOwnCommandTest(MissingCommandProjectTest):
    """Отказ «команда профиля <имя> не найдена» по местам."""

    def test_ac5_missing_own_command_refused_through_place_channel(self):
        """Несуществующая команда `pytest-own`: отказ каналом места, без `FileNotFoundError` наружу.

        Команда профиля — абсолютный путь к несуществующему файлу и голое
        имя вне PATH. `run`/`collect` — `(False, текст)`; `run_repeat` —
        `RedTest` модуля с текстом в пометке; `run_plank` —
        `REFUSED_EXIT_CODE` и текст; три пути полного прогона — не зелёный
        вывод с префиксом `FULL_SUITE_NOT_STARTED` и текстом; текст —
        «команда профиля <command[0]> не найдена». `two_sided.run` — отказ
        с «pytest не запустился». Ни одно место не бросает исключения.

        Ловит мутацию: перехват `FileNotFoundError` стоит не во всех местах
        (например нет в пути с наблюдением или в файл лога), отказ полного
        прогона без префикса `FULL_SUITE_NOT_STARTED` (тогда он «красный
        прогон»), текст называет не `command[0]`, `run_plank` отдаёт код
        pytest вместо `REFUSED_EXIT_CODE` — место бросает или канал/текст
        расходится.
        """
        for kind, head in self.missing_heads():
            text = refusal(head)
            profile = self.profile((head, "-m", "pytest"))
            for place in PLACES:
                where = self.where(kind, place)
                with self.subTest(kind=kind, place=place, seed=self.seed):
                    try:
                        outcome = self.invoke(place, profile,
                                              self.scratch("artel-miss-"))
                    except FileNotFoundError as exc:
                        self.fail(f"{where}: FileNotFoundError наружу: {exc}")
                    if place in ("acceptance.run", "acceptance.collect"):
                        ok, detail = outcome
                        self.assertFalse(ok, where)
                        self.assertIn(text, detail, where)
                    elif place == "acceptance.run_repeat":
                        module = str(self.root / self.module_rel)
                        notes = [r.note for r in outcome if r.node == module]
                        self.assertTrue(notes, f"{where}: нет RedTest файла "
                                               f"{module}: {outcome!r}")
                        self.assertTrue(all(text in n for n in notes),
                                        f"{where}: {notes!r}")
                    elif place == "acceptance.run_plank":
                        code, detail = outcome
                        self.assertEqual(code, acceptance.REFUSED_EXIT_CODE,
                                         f"{where}: {detail[-500:]}")
                        self.assertIn(text, detail, where)
                    elif place in FULL_PLACES:
                        green, output = outcome
                        self.assertFalse(green, where)
                        self.assertTrue(output.startswith(
                            acceptance.FULL_SUITE_NOT_STARTED),
                            f"{where}: {output[:300]!r}")
                        self.assertIn(text, output, where)
                    else:
                        joined = " ".join(outcome.refusals)
                        self.assertIn("pytest не запустился", joined,
                                      f"{where}: {joined[:500]}")

    def test_ac5_pult_pytest_launch_error_still_reaches_caller(self):
        """`pult-pytest` с несуществующей командой: `FileNotFoundError` доходит до вызывающего.

        Профиль `pult-pytest`, чья команда — абсолютный путь к
        несуществующему интерпретатору: `acceptance.run`,
        `acceptance.collect` и `acceptance.run_full_suite` бросают
        `FileNotFoundError`.

        Ловит мутацию: перехват запуска с именованным отказом поставлен
        для любого профиля, а не только для `pytest-own` — место у артели
        возвращает отказ вместо исключения.
        """
        absent = self.scratch("artel-absent-") / f"python-{self.word(10)}"
        profile = self.profile((str(absent), "-m", "pytest"), runner=PULT)
        module = str(self.root / self.module_rel)
        calls = {
            "acceptance.run": lambda: acceptance.run(
                self.scratch("artel-pult-"), cwd=self.root, extra=[module],
                command=profile),
            "acceptance.collect": lambda: acceptance.collect(
                self.scratch("artel-pult-"), cwd=self.root, extra=[module],
                command=profile),
            "acceptance.run_full_suite": lambda: acceptance.run_full_suite(
                self.root, command=profile),
        }
        for place, call in calls.items():
            with self.subTest(place=place, seed=self.seed):
                with self.assertRaises(FileNotFoundError, msg=self.where(place)):
                    call()

    def test_ac5_missing_log_dir_is_not_a_missing_command(self):
        """Нет каталога файла лога, команда есть: результат не «команда профиля не найдена» и не «прогон не начат».

        Полный прогон `pytest-own` в файл лога (`log=`), чей каталог не
        существует; команда профиля — существующий интерпретатор. Исход
        (возвращённый вывод или текст исключения) не несёт текста
        «команда профиля <command[0]> не найдена» и не начинается с
        `FULL_SUITE_NOT_STARTED`.

        Ловит мутацию: перехват `FileNotFoundError` охватывает всё тело
        места, включая открытие файла лога, — отказ называет команду и
        переводит прогон в «прогон не начат».
        """
        head = stack.pytest_python_executable()
        profile = self.profile((head, "-m", "pytest"))
        for _ in range(2):
            log = self.scratch("artel-log-") / f"absent_{self.word()}" / "suite.log"
            with self.subTest(log=str(log), seed=self.seed):
                try:
                    _, text = self.invoke(FULL_PLACES[2], profile,
                                          self.scratch("artel-miss-"), log=log)
                except FileNotFoundError as exc:
                    text = str(exc)
                self.assertNotIn(refusal(head), text, self.where(log))
                self.assertFalse(text.startswith(acceptance.FULL_SUITE_NOT_STARTED),
                                 f"{self.where(log)}: {text[:300]!r}")


class MissingCommandGateCacheTest(MissingCommandProjectTest):
    """Полный прогон гейта (`acceptance.full_suite`) и кеш его итогов."""

    TASK = "TPROBE"

    def test_ac6_not_started_not_cached_and_rerun_after_command_appears(self):
        """Отказ «команда не найдена» — `FULL_SUITE_NOT_STARTED` без записи в кеш; появилась команда — прогон заново.

        Чистое закоммиченное дерево; команда профиля — абсолютный путь к
        файлу, которого ещё нет. `full_suite` даёт `FULL_SUITE_NOT_STARTED`
        с текстом «команда профиля <command[0]> не найдена» в `detail`,
        сохранённых итогов нет. Затем по тому же пути появляется
        обёртка-счётчик: следующий `full_suite` того же дерева запускает её
        (одна запись счётчика) и даёт зелёный итог; ещё один — берёт итог
        из кеша (запись всё ещё одна) — контроль, что кеш в этом сценарии
        работает.

        Ловит мутацию: отказ запуска возвращён без префикса
        `FULL_SUITE_NOT_STARTED` — исход «красный прогон», итог сохранён в
        кеш, и второй `full_suite` берёт его, не запуская команду.
        """
        wrapper = self.scratch("artel-late-") / f"run-{self.word()}"
        probe = self.scratch("artel-probe-") / "runs.txt"
        profile = self.profile((str(wrapper),))

        def runs() -> int:
            return len(probe.read_text(encoding="utf-8").split()) \
                if probe.is_file() else 0

        def saved() -> list:
            path = acceptance.suite_results_dir()
            return sorted(p.name for p in path.glob("*")) if path.is_dir() else []

        try:
            first = acceptance.full_suite(self.root, self.TASK, command=profile)
        except FileNotFoundError as exc:
            self.fail(f"зерно {self.seed}: FileNotFoundError наружу: {exc}")
        self.assertEqual(first.outcome, acceptance.FULL_SUITE_NOT_STARTED,
                         f"зерно {self.seed}: {first.detail}")
        self.assertIn(refusal(str(wrapper)), first.detail,
                      f"зерно {self.seed}")
        self.assertEqual(saved(), [], f"зерно {self.seed}: итог в кеше")
        wrapper.write_text(COUNTING_WRAPPER.format(
            python=stack.pytest_python_executable(), probe=str(probe)),
            encoding="utf-8")
        wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
        second = acceptance.full_suite(self.root, self.TASK, command=profile)
        self.assertEqual(runs(), 1, f"зерно {self.seed}: команда не запущена "
                                    f"— итог взят из кеша: {second.detail}")
        self.assertEqual(second.outcome, acceptance.FULL_SUITE_GREEN,
                         f"зерно {self.seed}: {second.detail}")
        acceptance.full_suite(self.root, self.TASK, command=profile)
        self.assertEqual(runs(), 1, f"зерно {self.seed}: зелёный итог не "
                                    f"взят из кеша — контроль сценария")


if __name__ == "__main__":
    unittest.main()
