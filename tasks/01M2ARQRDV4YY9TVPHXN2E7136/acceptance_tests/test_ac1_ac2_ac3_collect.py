"""AC-1, AC-2, AC-3 (tasks/01M2ARQRDV4YY9TVPHXN2E7136/SPEC.md): новая
функция `orchestrator.acceptance.collect(tdir, cwd)` — сухой сбор
планки `pytest --collect-only -q`, без прогона тел тестов.

Красен до реализации: `orchestrator.acceptance` ещё не несёт атрибута
`collect` — любой вызов `acceptance.collect(...)` падает
`AttributeError: module 'orchestrator.acceptance' has no attribute
'collect'` ещё до того, как дойдёт до сборки планки/сравнения исхода.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import acceptance  # noqa: E402

PASSING_TEST = """import unittest


class PlankTest(unittest.TestCase):
    def test_something(self):
        self.assertTrue(True)
"""

MODULE_NOT_FOUND_TEST = """import definitely_not_a_real_module_zzz_ac2


class PlankTest:
    def test_something(self):
        pass
"""

SYNTAX_ERROR_TEST = "def broken(:\n"

NO_TESTS_MODULE = """def helper():
    return 1
"""


class CollectTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)

    def write(self, content: str, name: str = "test_ac.py") -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / name).write_text(content, encoding="utf-8")

    def test_ac1_green_plank_collects_successfully(self):
        """Планка с одним валидным тестом собирается без ошибок — `collect`
        отдаёт `(True, хвост)`.

        Ловит мутацию: `collect` не запускает настоящий сухой сбор (всегда
        `(True, "")`, либо по ошибке зовёт `run` — прогон ТЕЛ тестов вместо
        `--collect-only`) — соседние тесты этого класса (ModuleNotFoundError,
        планка без единого теста) в этом случае тоже ошибочно проходили бы
        зелёными."""
        self.write(PASSING_TEST)

        collected, tail = acceptance.collect(self.tdir, self.tdir)

        self.assertTrue(collected, tail)

    def test_ac1_command_is_collect_only_with_the_shared_pytest_flags(self):
        """Команда сбора — `pytest --collect-only -q`, тем же интерпретатором
        и с теми же флагами окружения, что несёт общая часть `acceptance.run`
        (`_pytest_command`: `-p no:cacheprovider`, явная загрузка `-p timeout`).

        Ловит мутацию: `collect` собирает команду с нуля вместо переиспользования
        `_pytest_command` — планка на сборе роняет `.pytest_cache/` мимо
        `.gitignore`, таймаут отдельного теста тихо не применяется."""
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

    def test_ac2_module_not_found_error_is_red_with_module_name_in_tail(self):
        """Планка, ссылающаяся на несуществующий модуль, не импортируется —
        `collect` отдаёт `(False, хвост с текстом ошибки)`, хвост называет
        имя несуществующего модуля.

        Ловит мутацию: `collect` трактует ЛЮБОЙ ненулевой код возврата
        одинаково с «нет тестов» (текст AC-3) — класс ошибки импорта
        становится неотличим от класса «планка пуста», и имя модуля из
        хвоста теряется."""
        self.write(MODULE_NOT_FOUND_TEST)

        collected, tail = acceptance.collect(self.tdir, self.tdir)

        self.assertFalse(collected)
        self.assertIn("definitely_not_a_real_module_zzz_ac2", tail)

    def test_ac2_syntax_error_is_red_and_distinct_from_the_no_tests_text(self):
        """Планка с синтаксической ошибкой — тоже `(False, ...)`, но текстом,
        отличным от AC-3 («планка не содержит ни одного теста»): синтаксис —
        не то же самое, что легитимно пустая планка.

        Ловит мутацию: синтаксическая ошибка молча схлопывается в тот же
        текст, что и «нет тестов» — два разных класса дефекта планки
        становятся неразличимы по хвосту вывода."""
        self.write(SYNTAX_ERROR_TEST)

        collected, tail = acceptance.collect(self.tdir, self.tdir)

        self.assertFalse(collected)
        self.assertNotEqual(tail, "планка не содержит ни одного теста")

    def test_ac3_plank_without_a_single_test_is_named_explicitly(self):
        """Планка собирается (нет ошибок импорта/синтаксиса), но не содержит
        ни одного теста — `collect` отдаёт РОВНО `(False, "планка не
        содержит ни одного теста")` (точный текст критерия).

        Ловит мутацию: `collect` возвращает `(True, ...)` на планке без
        единого теста (или называет причину другим текстом) — задача с
        технически «собирающейся», но фактически пустой планкой молча
        проходит выход `tests_writing`."""
        self.write(NO_TESTS_MODULE, name="test_empty.py")

        collected, tail = acceptance.collect(self.tdir, self.tdir)

        self.assertFalse(collected)
        self.assertEqual(tail, "планка не содержит ни одного теста")


if __name__ == "__main__":
    unittest.main()
