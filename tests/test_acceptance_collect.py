"""Юнит-тесты `orchestrator/acceptance.py::collect` (SPEC
01M2ARQRDV4YY9TVPHXN2E7136, требование 1, AC-1/AC-2/AC-3/AC-11) —
постоянный набор `tests/`, отдельный от залоченной планки задачи
(`tasks/01M2ARQRDV4YY9TVPHXN2E7136/acceptance_tests/
test_ac1_ac2_ac3_collect.py`), которая испытывает те же три сценария, но
уходит из репозитория логически вместе с задачей, а не остаётся
регрессионным прогоном пульта.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import acceptance  # noqa: E402
from tests.sandbox import TmpDirTest  # noqa: E402

PASSING_TEST = """import unittest


class PlankTest(unittest.TestCase):
    def test_something(self):
        self.assertTrue(True)
"""

MODULE_NOT_FOUND_TEST = """import definitely_not_a_real_module_zzz_collect


class PlankTest:
    def test_something(self):
        pass
"""

SYNTAX_ERROR_TEST = "def broken(:\n"

NO_TESTS_MODULE = """def helper():
    return 1
"""


class CollectTest(TmpDirTest):

    def write(self, content: str, name: str = "test_ac.py") -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / name).write_text(content, encoding="utf-8")

    def test_missing_acceptance_tests_dir_is_a_degenerate_pass(self):
        """`acceptance_tests/` не заведена вовсе — собирать нечего, тот же
        вырожденный случай, что и у `run()`: `(True, ...)`, не отказ.

        Ловит мутацию: `collect` требует существования каталога и падает/
        отказывает на его отсутствии вместо вырожденного «нечего
        собирать»."""
        collected, tail = acceptance.collect(self.tdir, self.tdir)

        self.assertTrue(collected, tail)

    def test_ac1_green_plank_collects_successfully(self):
        """Планка с одним валидным тестом собирается без ошибок —
        `collect` отдаёт `(True, хвост)`.

        Ловит мутацию: `collect` не запускает настоящий сухой сбор (всегда
        `(True, "")` независимо от содержимого планки) — эта мутация не
        падает здесь сама по себе, но красит соседние тесты класса
        (ModuleNotFoundError, планка без теста), которые с такой
        реализацией ошибочно проходили бы зелёными вместо ожидаемого
        `False`."""
        self.write(PASSING_TEST)

        collected, tail = acceptance.collect(self.tdir, self.tdir)

        self.assertTrue(collected, tail)

    def test_ac1_command_is_collect_only_with_shared_pytest_flags(self):
        """Команда сбора — `pytest --collect-only -q` тем же
        интерпретатором и с теми же флагами окружения, что несёт общая
        часть `acceptance.run` (`_pytest_command`).

        Ловит мутацию: `collect` собирает команду с нуля вместо
        переиспользования `_pytest_command` — теряется `-p
        no:cacheprovider`/явная загрузка `-p timeout`, планка на сборе
        роняет `.pytest_cache/`, таймаут отдельного теста не применяется."""
        self.write(PASSING_TEST)

        with mock.patch.object(acceptance.subprocess, "run") as run_:
            run_.return_value = subprocess.CompletedProcess(
                [], 0, "1 test collected in 0.01s", "")
            acceptance.collect(self.tdir, self.tdir)

        command = run_.call_args.args[0]
        self.assertIn("--collect-only", command, command)
        self.assertIn("-q", command, command)
        p_values = [command[i + 1] for i, tok in enumerate(command)
                   if tok == "-p" and i + 1 < len(command)]
        self.assertIn("no:cacheprovider", p_values, command)
        self.assertIn("timeout", p_values, command)

    def test_ac2_module_not_found_error_names_the_module_in_the_tail(self):
        """Планка, ссылающаяся на несуществующий модуль, не импортируется
        — `collect` отдаёт `(False, хвост с текстом ошибки)`, хвост
        называет имя несуществующего модуля.

        Ловит мутацию: `collect` трактует ЛЮБОЙ ненулевой код возврата
        как «нет тестов» (текст AC-3) — класс ошибки импорта становится
        неотличим от класса «планка пуста», имя модуля из хвоста теряется."""
        self.write(MODULE_NOT_FOUND_TEST)

        collected, tail = acceptance.collect(self.tdir, self.tdir)

        self.assertFalse(collected)
        self.assertIn("definitely_not_a_real_module_zzz_collect", tail)

    def test_ac2_syntax_error_is_red_and_distinct_from_the_no_tests_text(self):
        """Планка с синтаксической ошибкой — тоже `(False, ...)`, но
        текстом, отличным от AC-3 («планка не содержит ни одного теста»).

        Ловит мутацию: код возврата сбора при синтаксической ошибке (`2`)
        трактуется наравне с кодом «нет тестов» (`5`) — два разных класса
        дефекта планки становятся неразличимы по хвосту вывода."""
        self.write(SYNTAX_ERROR_TEST)

        collected, tail = acceptance.collect(self.tdir, self.tdir)

        self.assertFalse(collected)
        self.assertNotEqual(tail, "планка не содержит ни одного теста")

    def test_ac3_plank_without_a_single_test_is_named_explicitly(self):
        """Планка собирается (нет ошибок импорта/синтаксиса), но не
        содержит ни одного теста — `collect` отдаёт РОВНО `(False,
        "планка не содержит ни одного теста")`.

        Ловит мутацию: `collect` возвращает `(True, ...)` на планке без
        единого теста (или называет причину другим текстом) — задача с
        технически «собирающейся», но фактически пустой планкой молча
        проходит выход `tests_writing`."""
        self.write(NO_TESTS_MODULE, name="test_empty.py")

        collected, tail = acceptance.collect(self.tdir, self.tdir)

        self.assertFalse(collected)
        self.assertEqual(tail, "планка не содержит ни одного теста")

    def test_timeout_is_red(self):
        """Сбор, превысивший `config.ACCEPTANCE_TIMEOUT_SEC`, — `(False,
        ...)`, а не подвисший процесс без ответа.

        Ловит мутацию: `TimeoutExpired` не перехватывается — вызов
        `collect` падает исключением вместо именованного красного
        исхода, симметрично таймауту `run()`."""
        self.write(PASSING_TEST)

        with mock.patch.object(acceptance.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired(
                                   cmd=["pytest"], timeout=1)):
            collected, tail = acceptance.collect(self.tdir, self.tdir)

        self.assertFalse(collected)
        self.assertIn("превысил", tail)


if __name__ == "__main__":
    unittest.main()
