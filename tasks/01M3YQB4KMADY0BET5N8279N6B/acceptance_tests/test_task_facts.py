"""Факты этой задачи о тестовых файлах кодовой ветки: тест AC-3 задачи
01M3Y75GCR не ослаблен, регрессионный тест задачи лежит на месте.

Группа: разовый

Критерии приёмки, которые покрывает файл:

AC-5. Тест `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py::
PinUpdateSelectionTest::test_ac3_cycle_started_after_shift_is_not_named`
зелёный на Linux-раннере CI ветки задачи. `GAP_SEC` в файле равен 1.5, а
утверждения теста те же, что в main 5e8d6bc7.

AC-6. Файл `tests/test_stale_cycles_start_precision.py` существует, его
тест разыгрывает сценарий AC-3 (огрубление `lstart` на 2 с раньше
настоящего, цикл после сдвига), а докстринг теста содержит «Ловит
мутацию: …».

Файлы кодовой ветки читаются импортом модулей `tests.*` из рабочей копии,
которую гоняет прогон (её `cwd`); версия main 5e8d6bc7 — через
`gitcmd.git("show", …)`. Тесты кодовой ветки исполняются здесь же,
загрузчиком `unittest`: на Linux-раннере это и есть проверка зелени AC-5
(тот же тест гоняет и CI ветки); поведение на Linux, ради которого
задача заведена, сторожит долгоживущий AC-1 задачи.

Что тест AC-6 разыгрывает именно сценарий AC-3, машина проверяет
частично (файл говорит об `lstart` и зелен); остальное сверяет ревьюер по
диффу.

Красен до реализации: файла `tests/test_stale_cycles_start_precision.py` ещё нет — импорт в test_ac6 падает `ModuleNotFoundError`; test_ac5 на macOS зелен уже сейчас (там `lstart` теряет меньше секунды), на Linux красен до починки отбора.
"""
import ast
import importlib
import inspect
import textwrap
import unittest

from orchestrator import gitcmd

LEGACY_MODULE = "tests.test_01m3y75gcresc2kds9vprjk4ps_stale_cycles"
LEGACY_PATH = "tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py"
LEGACY_CLASS = "PinUpdateSelectionTest"
LEGACY_METHOD = "test_ac3_cycle_started_after_shift_is_not_named"
BASE_SHA = "5e8d6bc7"
REGRESSION_MODULE = "tests.test_stale_cycles_start_precision"
MUTATION_CLAIM = "Ловит мутацию:"


def method_body_dump(tree: ast.AST, cls: str, method: str) -> str | None:
    """`ast.dump` тела метода без докстринга; `None` — метода нет."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method:
                    body = item.body
                    if (body and isinstance(body[0], ast.Expr)
                            and isinstance(body[0].value, ast.Constant)
                            and isinstance(body[0].value.value, str)):
                        body = body[1:]
                    return "\n".join(ast.dump(stmt) for stmt in body)
    return None


def run_tests(suite: unittest.TestSuite) -> unittest.TestResult:
    result = unittest.TestResult()
    suite.run(result)
    return result


def failures_text(result: unittest.TestResult) -> str:
    return "\n".join(f"{test}: {trace}"
                     for test, trace in result.failures + result.errors)


class LegacyAc3TestTest(unittest.TestCase):
    """AC-5: тест AC-3 задачи 01M3Y75GCR не ослаблен и зелен."""

    def test_ac5_legacy_ac3_unchanged_gap_kept_and_green(self):
        """Тест `test_ac3_cycle_started_after_shift_is_not_named` ветки.

        `GAP_SEC` модуля равен 1.5; тело метода (без докстринга) по AST
        совпадает с версией main 5e8d6bc7; сам тест, исполненный здесь,
        зелёный.

        Ловит мутацию: починка через увеличение `GAP_SEC` до 3 с; либо
        утверждение «поздний цикл не назван» ослаблено или убрано из
        метода; либо отбор всё ещё называет поздний цикл по огрублённому
        `lstart` (на Linux тест красен).
        """
        module = importlib.import_module(LEGACY_MODULE)
        self.assertEqual(module.GAP_SEC, 1.5, "GAP_SEC изменён")

        current = ast.parse(textwrap.dedent(inspect.getsource(
            getattr(module, LEGACY_CLASS))))
        base_text = gitcmd.git("show", f"{BASE_SHA}:{LEGACY_PATH}")
        self.assertEqual(base_text.returncode, 0,
                         f"git show {BASE_SHA}:{LEGACY_PATH}: {base_text.stderr}")
        base = ast.parse(base_text.stdout)
        base_dump = method_body_dump(base, LEGACY_CLASS, LEGACY_METHOD)
        self.assertIsNotNone(base_dump, f"в {BASE_SHA} нет метода {LEGACY_METHOD}")
        self.assertEqual(method_body_dump(current, LEGACY_CLASS, LEGACY_METHOD),
                         base_dump,
                         f"тело {LEGACY_CLASS}.{LEGACY_METHOD} отличается от {BASE_SHA}")

        result = run_tests(unittest.defaultTestLoader.loadTestsFromName(
            f"{LEGACY_MODULE}.{LEGACY_CLASS}.{LEGACY_METHOD}"))
        self.assertEqual(result.testsRun, 1)
        self.assertTrue(result.wasSuccessful(), failures_text(result))


class RegressionTestFileTest(unittest.TestCase):
    """AC-6: регрессионный тест задачи на месте."""

    def test_ac6_regression_file_exists_with_mutation_claim_and_is_green(self):
        """Модуль `tests.test_stale_cycles_start_precision` импортируется.

        В нём есть хотя бы один тестовый метод; докстринг каждого тестового
        метода содержит «Ловит мутацию:»; файл говорит об `lstart`
        (сценарий огрублённого ответа `ps`); его тесты, исполненные здесь,
        зелёные.

        Ловит мутацию: регрессионный тест не добавлен или лежит под другим
        именем; у метода нет строки «Ловит мутацию: …»; тест разыгрывает
        не ответ `ps -o lstart=`, а что-то иное; тест красен.
        """
        module = importlib.import_module(REGRESSION_MODULE)
        methods = []
        for _name, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, unittest.TestCase) and cls.__module__ == module.__name__:
                for attr in dir(cls):
                    if attr.startswith("test"):
                        methods.append((f"{cls.__name__}.{attr}", getattr(cls, attr)))
        self.assertTrue(methods, f"в {REGRESSION_MODULE} нет тестовых методов")
        for name, fn in methods:
            self.assertIn(MUTATION_CLAIM, inspect.getdoc(fn) or "",
                          f"{name}: в докстринге нет «{MUTATION_CLAIM}»")
        self.assertIn("lstart", inspect.getsource(module),
                      "регрессионный тест не говорит об ответе ps -o lstart=")

        result = run_tests(unittest.defaultTestLoader.loadTestsFromModule(module))
        self.assertGreater(result.testsRun, 0)
        self.assertTrue(result.wasSuccessful(), failures_text(result))


if __name__ == "__main__":
    unittest.main()
