"""AC-1 (tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D/SPEC.md): «Команда существует,
зарегистрирована в orchestrator/artel.py, принимает id задачи, read-only,
и печатает список обнаруженных тестовых файлов и тестовых методов из
tasks/<id>/acceptance_tests/ ветки задачи.»

Регистрация в `orchestrator/artel.py` и «принимает id задачи» проверяются
самим механизмом вызова: `_sandbox.discover_dry_run_command_name()`
находит команду в таблице диспетчера `artel.py::main` и `run_dry_run`
зовёт её ровно с одним позиционным аргументом — id задачи (см. докстринг
`_sandbox.py` про то, почему имя команды не зашито литералом). Этот файл
проверяет остаток критерия: список файлов и методов в выводе.

Фикстурные тестовые методы ниже намеренно НЕ названы `test_ac<n>_...`
(та же осторожность, что `tasks/T081/acceptance_tests/test_ac1_non_test_
files_excluded.py`): `guard.scan_acceptance_tests` читает СЫРОЙ ТЕКСТ
`.py`-файлов регуляркой, без разбора AST — литерал `def test_ac1_...`
внутри строки-фикстуры ЭТОГО файла (не файла ветки-фикстуры T900, а вот
этого самого файла, лежащего в tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D/
acceptance_tests/) читался бы как настоящий тест задачи
01M1GJ3ZP1YGG5QRB6FQ44NN8D (класс дефекта ANSWER-1, 31.08). Критерию
AC-1 неважно, как называются методы во ФИКСТУРЕ — важно, что команда их
перечисляет.

Красен до реализации: `_sandbox.discover_dry_run_command_name()` падает
`AssertionError` — новой команды в таблице диспетчера ещё нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import DryRunSandbox  # noqa: E402

TEST_ALPHA = '''"""Фикстура: файл alpha.

Зелёный с рождения: файл-фикстура другой задачи, не код 01M1GJ3ZP1YGG5QRB6FQ44NN8D.
"""
import unittest


class AlphaTest(unittest.TestCase):

    def test_alpha_one(self):
        """Фикстура."""
        pass

    def test_alpha_two(self):
        """Фикстура."""
        pass
'''

TEST_BETA = '''"""Фикстура: файл beta.

Зелёный с рождения: файл-фикстура другой задачи, не код 01M1GJ3ZP1YGG5QRB6FQ44NN8D.
"""
import unittest


class BetaTest(unittest.TestCase):

    def test_beta_one(self):
        """Фикстура."""
        pass
'''

AC_SECTION = "AC-1. Критерий фикстуры.\n"


class ListsDiscoveredFilesAndMethodsTest(DryRunSandbox):

    def test_ac1_output_lists_test_files_and_test_methods(self):
        """Ветка задачи несёт два файла acceptance_tests/ с тремя
        тестовыми методами суммарно; вывод сухого прогона обязан назвать
        оба файла и все три метода.

        Ловит мутацию: команда печатает только число найденных файлов/
        методов (сводку-счётчик) без их имён — тест ищет конкретные
        имена файлов ("test_alpha.py", "test_beta.py") и методов
        ("test_alpha_one" и т.д.) построчно и не находит их в
        выводе, состоящем из одних чисел.
        """
        self.commit_fixture(AC_SECTION, {
            "test_alpha.py": TEST_ALPHA,
            "test_beta.py": TEST_BETA,
        })
        self.seed_task()

        out = self.run_dry_run()

        for name in ("test_alpha.py", "test_beta.py"):
            self.assertIn(name, out,
                         f"вывод не называет тестовый файл {name}")
        for method in ("test_alpha_one", "test_alpha_two",
                      "test_beta_one"):
            self.assertIn(method, out,
                         f"вывод не называет тестовый метод {method}")


if __name__ == "__main__":
    unittest.main()
