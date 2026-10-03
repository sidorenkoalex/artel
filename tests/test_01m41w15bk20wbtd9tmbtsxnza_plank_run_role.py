"""`plank-run` под окружением роли проходит настоящий сторож роли `conftest.py`.

Команда передаёт pytest позиционный путь планки относительным от рабочей
копии кода — каталог планки задачи под `tasks` для всей планки, путь файла
планки (с `::узлом`, если он назван) для одного файла. Такой путь сторож роли
признаёт целевым, и прогон под маркером роли доходит до pytest и печатает его
итог; абсолютный путь сторож отклоняет отказом «Сторож роли: полный прогон
набора тестов внутри шага запрещён». Без маркера роли состав прогона, код
выхода и итоговая строка pytest те же, что у прогона планки напрямую.

Группа: долгоживущий
Красен до реализации: plank-run передаёт pytest абсолютный путь планки — под маркером роли настоящий conftest.py отвечает отказом «Сторож роли», итога pytest нет, а записанный планкой argv несёт абсолютный путь (test_ac1-test_ac3); test_ac4 без маркера роли зелен и сейчас.

Песочница — настоящий git (`tests/sandbox.py::RealGitSandbox`): в `main`
песочницы закоммичены НАСТОЯЩИЕ `conftest.py` и `pyproject.toml` репозитория
(второй задаёт корень pytest, без него `conftest.py` корня рабочей копии не
грузится вовсе), рабочая копия кода задачи заведена `workspace.ensure` от
этого `main`. Процесс pytest импортирует `orchestrator.config` из кода под
проверкой через `PYTHONPATH`. Задача в `tests_writing`, черновик планки — в
каталоге документов: файл с зелёными тестами (один из них пишет свой
`sys.argv` в файл из переменной окружения) и файл с красными. `subprocess.run`
не подменяется. Команда зовётся через `artel.main()`; вывод снимается и с
`sys.stdout`/`sys.stderr`, и с файловых дескрипторов 1/2.
"""
import io
import json
import os
import random
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import artel, config, store, workspace
from tests.sandbox import RealGitSandbox

FIXTURE_TASK = "01M0000000000000000000RLGD"
FIXTURE_BRANCH = "task/fixture-plank-run-role"
CODE_ROOT = Path(__file__).resolve().parents[1]
LETTERS = "abcdefghjkmnpqrstvwxyz"
GUARD_REFUSAL = "Сторож роли"
ARGV_SINK_ENV = "PLANK_RUN_ROLE_ARGV_SINK"
VALUE_FLAGS = {"-k", "-m", "-p", "-o", "-c", "-n", "-W", "--maxfail",
               "--rootdir", "--confcutdir"}

RECORDER = (
    "import json\nimport os\nimport sys\n\n\n"
    "def test_{name}():\n"
    "    sink = os.environ.get('" + ARGV_SINK_ENV + "')\n"
    "    if sink:\n"
    "        with open(sink, 'w', encoding='utf-8') as fh:\n"
    "            json.dump(sys.argv[1:], fh)\n"
)
PASSING = "\n\ndef test_{name}():\n    assert True\n"
FAILING = "\n\ndef test_{name}():\n    assert False, 'красный тест {name}'\n"


def positionals(argv: list) -> list:
    """Позиционные аргументы pytest: без флагов и значений флагов."""
    out, skip = [], False
    for tok in argv:
        if skip:
            skip = False
            continue
        if tok.startswith("-"):
            skip = tok in VALUE_FLAGS
            continue
        out.append(tok)
    return out


class PlankRunRoleSandbox(RealGitSandbox):
    """Задача в `tests_writing` с рабочей копией кода, в которой лежат
    настоящие `conftest.py` и `pyproject.toml`, и черновиком планки."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        for name in ("conftest.py", "pyproject.toml"):
            shutil.copyfile(CODE_ROOT / name, self.root / name)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "сторож роли и корень pytest")
        self.add_synced_origin()
        self.conn = store.db()
        store.insert_task(self.conn, FIXTURE_TASK, "Фикстура plank-run под ролью",
                          "tests_writing", FIXTURE_BRANCH,
                          config.DEFAULT_TARGET, 25.0)
        wt, error = workspace.ensure(FIXTURE_TASK, FIXTURE_BRANCH)
        self.assertIsNone(error, f"рабочая копия кода не заведена: {error}")
        self.wt = wt
        self.assertTrue((self.wt / "conftest.py").is_file(),
                        "в рабочей копии кода нет conftest.py")
        self.plank_rel = "/".join(("tasks", FIXTURE_TASK, "acceptance_tests"))
        self.write_plank()
        sink_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, sink_dir, ignore_errors=True)
        self.sink = sink_dir / "argv.json"
        pythonpath = os.pathsep.join(
            p for p in (str(CODE_ROOT), os.environ.get("PYTHONPATH", "")) if p)
        env = mock.patch.dict(os.environ, {"PYTHONPATH": pythonpath,
                                           ARGV_SINK_ENV: str(self.sink)})
        env.start()
        self.addCleanup(env.stop)

    def word(self) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(6))

    def write_plank(self) -> None:
        """Черновик: файл зелёных (первый пишет argv) и файл красных."""
        self.green_file = f"test_green_{self.word()}.py"
        self.red_file = f"test_red_{self.word()}.py"
        self.recorder = f"argv_{self.word()}"
        self.green_count = 1 + self.rng.randrange(4)
        self.red_count = 1 + self.rng.randrange(3)
        self.red_names = [f"red_{self.word()}" for _ in range(self.red_count)]
        green = RECORDER.format(name=self.recorder) + "".join(
            PASSING.format(name=f"green_{self.word()}_{i}")
            for i in range(self.green_count - 1))
        red = "".join(FAILING.format(name=n) for n in self.red_names)
        plank = (config.PROJECTS / config.DEFAULT_TARGET / "tasks"
                 / FIXTURE_TASK / "acceptance_tests")
        plank.mkdir(parents=True, exist_ok=True)
        (plank / self.green_file).write_text(green, encoding="utf-8")
        (plank / self.red_file).write_text(red, encoding="utf-8")

    def plank_run(self, *extra: str, role: bool) -> tuple:
        """(код выхода, весь вывод) `artel.py plank-run <id> [файл]` под
        маркером роли со случайной ролью либо без него."""
        if self.sink.exists():
            self.sink.unlink()
        argv = ["artel.py", "plank-run", FIXTURE_TASK, *extra]
        out, err = io.StringIO(), io.StringIO()
        code = None
        env = {config.ARTEL_ROLE_ENV: f"role_{self.word()}"} if role else {}
        with mock.patch.dict(os.environ, env), tempfile.TemporaryFile() as sink:
            if not role:
                os.environ.pop(config.ARTEL_ROLE_ENV, None)
            sys.stdout.flush()
            sys.stderr.flush()
            saved = os.dup(1), os.dup(2)
            os.dup2(sink.fileno(), 1)
            os.dup2(sink.fileno(), 2)
            try:
                with mock.patch.object(sys, "argv", argv), \
                        redirect_stdout(out), redirect_stderr(err):
                    try:
                        artel.main()
                    except SystemExit as exc:
                        code = exc.code
            finally:
                os.dup2(saved[0], 1)
                os.dup2(saved[1], 2)
                os.close(saved[0])
                os.close(saved[1])
            sink.seek(0)
            fd_text = sink.read().decode("utf-8", errors="replace")
        message = "" if code is None or isinstance(code, int) else str(code)
        status = code if isinstance(code, int) else (0 if code is None else 1)
        return status, "\n".join((out.getvalue(), err.getvalue(), fd_text,
                                  message))

    def recorded_positionals(self, output: str) -> list:
        self.assertTrue(self.sink.is_file(),
                        f"тест-регистратор планки не исполнялся; "
                        f"{self.explain(output)}")
        return positionals(json.loads(self.sink.read_text(encoding="utf-8")))

    def explain(self, output: str) -> str:
        return f"зерно: {self.seed}; вывод plank-run:\n{output[-3000:]}"

    def file_variants(self) -> list:
        """(аргумент файла, ожидаемый позиционный путь, число зелёных)."""
        file_rel = f"{self.plank_rel}/{self.green_file}"
        node = f"{self.green_file}::test_{self.recorder}"
        return [(self.green_file, file_rel, self.green_count),
                (file_rel, file_rel, self.green_count),
                (node, f"{file_rel}::test_{self.recorder}", 1)]


class WholePlankUnderRoleTest(PlankRunRoleSandbox):

    def test_ac1_role_whole_plank_reaches_pytest_summary(self):
        """Под маркером роли вся планка доходит до pytest и даёт его итог.

        Сценарий: маркер роли со случайным именем роли, `plank-run <id>` без
        аргумента файла, настоящий `conftest.py` в рабочей копии кода,
        `subprocess.run` не подменён. Вывод несёт итог pytest «<красных>
        failed, <зелёных> passed» (числа от зерна) и строку plank-run «итог
        pytest: …» с ними же; отказа «Сторож роли» в выводе нет; код выхода
        команды — 1 (в планке есть красные тесты).

        Ловит мутацию: путь планки снова собран абсолютным (`str(tests_dir)`)
        — сторож роли в процессе pytest отвечает «Сторож роли: полный прогон
        набора тестов внутри шага запрещён», итога с числами нет, код выхода
        2; путь собран относительным, но без сегмента `acceptance_tests`
        (каталог задачи под `tasks`) — тот же отказ сторожа.
        """
        status, output = self.plank_run(role=True)
        self.assertNotIn(GUARD_REFUSAL, output,
                         f"отказ сторожа роли; {self.explain(output)}")
        summary = rf"{self.red_count} failed, {self.green_count} passed"
        self.assertRegex(output, rf"итог pytest: {summary}",
                         f"итога pytest нет; {self.explain(output)}")
        self.assertEqual(status, 1, self.explain(output))


class SingleFileUnderRoleTest(PlankRunRoleSandbox):

    def test_ac2_role_single_file_runs_only_named_file(self):
        """Под маркером роли `plank-run <id> <файл>` гоняет только этот файл.

        Сценарий: маркер роли; аргумент файла — голое имя зелёного файла
        планки, его путь с префиксом каталога планки под `tasks` и имя с
        `::узлом` теста-регистратора. Каждый раз вывод несёт итог pytest
        «<N> passed» (N — число зелёных тестов файла либо 1 для узла), без
        «failed» и без имён красных тестов соседнего файла; отказа «Сторож
        роли» нет; код выхода 0.

        Ловит мутацию: путь одного файла собран абсолютным
        (`str(tests_dir / selected)`) — отказ сторожа роли вместо итога;
        аргумент файла потерян и передан каталог планки — в выводе падения
        красного файла и «failed»; узел `::тест` отброшен — «<N> passed»
        вместо «1 passed».
        """
        for arg, _expected, passed in self.file_variants():
            with self.subTest(arg=arg):
                status, output = self.plank_run(arg, role=True)
                self.assertNotIn(GUARD_REFUSAL, output,
                                 f"отказ сторожа роли; {self.explain(output)}")
                self.assertRegex(output, rf"итог pytest: {passed} passed",
                                 f"итога pytest нет; {self.explain(output)}")
                self.assertNotIn("failed", output, self.explain(output))
                for name in self.red_names:
                    self.assertNotIn(name, output, self.explain(output))
                self.assertEqual(status, 0, self.explain(output))


class RelativePositionalTest(PlankRunRoleSandbox):

    def test_ac3_positional_is_relative_plank_path(self):
        """Позиционный путь pytest — относительный путь планки от рабочей копии.

        Сценарий: маркер роли; `plank-run <id>` и три формы аргумента файла
        (голое имя, путь с префиксом каталога планки, `файл::узел`).
        Тест-регистратор планки записывает `sys.argv` процесса pytest;
        позиционный аргумент в нём ровно один и равен каталогу планки под
        `tasks` либо пути файла под ним (с `::узлом`, если назван), он не
        абсолютный и, приложенный к рабочей копии кода, указывает на
        выложенный файл/каталог планки. Тот же прогон проходит настоящий
        сторож роли (отказа нет).

        Ловит мутацию: возврат абсолютной формы `str(tests_dir …)` —
        записанный позиционный путь абсолютный, а прогон отклонён сторожем
        (регистратор не исполнился); путь относителен не от рабочей копии,
        а от каталога планки (одно имя файла) — позиционный путь не равен
        ожидаемому, и сторож роли его отклоняет.
        """
        cases = [(None, self.plank_rel)] + [
            (arg, expected) for arg, expected, _n in self.file_variants()]
        for arg, expected in cases:
            with self.subTest(arg=arg):
                extra = (arg,) if arg else ()
                _status, output = self.plank_run(*extra, role=True)
                self.assertNotIn(GUARD_REFUSAL, output,
                                 f"отказ сторожа роли; {self.explain(output)}")
                recorded = self.recorded_positionals(output)
                self.assertEqual(recorded, [expected],
                                 f"позиционный путь pytest не тот; "
                                 f"{self.explain(output)}")
                self.assertFalse(os.path.isabs(recorded[0]),
                                 self.explain(output))


class WithoutRoleUnchangedTest(PlankRunRoleSandbox):

    def test_ac4_without_role_same_tests_exit_code_and_summary(self):
        """Без маркера роли состав прогона, код выхода и итог pytest прежние.

        Сценарий: маркера роли в окружении нет. `plank-run <id>` гоняет оба
        файла планки: итог «<красных> failed, <зелёных> passed», строка
        «код выхода pytest: 1», код выхода команды 1. Для каждой формы
        аргумента зелёного файла — «<N> passed» без «failed», «код выхода
        pytest: 0», код выхода 0. Аргумент красного файла — «<красных>
        failed» без «passed», код выхода 1.

        Ловит мутацию: относительный путь собран от другой базы (каталог
        задачи под `tasks` без `acceptance_tests`, лишний сегмент) — pytest
        не находит файлы или собирает не тот состав, итог и код выхода
        другие; аргумент файла или `::узел` теряется при сборке пути — итог
        несёт красные тесты либо «<N> passed» вместо «1 passed»; код выхода
        pytest перестал пробрасываться — код выхода команды 0 при красной
        планке.
        """
        status, output = self.plank_run(role=False)
        self.assertRegex(output, rf"итог pytest: {self.red_count} failed, "
                                 rf"{self.green_count} passed",
                         self.explain(output))
        self.assertIn("код выхода pytest: 1", output, self.explain(output))
        self.assertEqual(status, 1, self.explain(output))
        for arg, _expected, passed in self.file_variants():
            with self.subTest(arg=arg):
                status, output = self.plank_run(arg, role=False)
                self.assertRegex(output, rf"итог pytest: {passed} passed",
                                 self.explain(output))
                self.assertNotIn("failed", output, self.explain(output))
                self.assertIn("код выхода pytest: 0", output,
                              self.explain(output))
                self.assertEqual(status, 0, self.explain(output))
        status, output = self.plank_run(self.red_file, role=False)
        self.assertTrue(re.search(rf"итог pytest: {self.red_count} failed in",
                                  output), self.explain(output))
        self.assertEqual(status, 1, self.explain(output))


if __name__ == "__main__":
    unittest.main()
