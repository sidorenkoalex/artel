"""Юнит-тесты режима поиска помощников `guard.TestModules` (SPEC
01M56TNTY7HEC85MC940KZR1ZJ, требования 2, 4-6).

Долгоживущий файл задачи (`tests/test_01m56tnty7hec85mc940kzr1zj_*`)
держит сценарии трёх входов узла в настоящем git; здесь — границы
разбора без git: `workdir` без режима не действует, режим с пустым
`workdir`, относительный импорт из файла вне `workdir`, базовый класс
модуля области и `method_literal_keys` с модулями внешнего режима.
"""
import unittest

from scripts import guard

HELPER = ("def expect_ok(test, value):\n"
          "    test.assertEqual(value, 7)\n")


def in_backend_tests(path: str) -> bool:
    return path.startswith("backend/tests/")


def found_texts(source: str, path: str, modules, name="C::test_m") -> list:
    return [text for _key, text in
            guard.test_assertions(source, path, modules)[name]]


CALLER = ("from tests.support import expect_ok\n\n\n"
          "class C:\n"
          "    def test_m(self):\n"
          "        expect_ok(self, run())\n")


class ModeArgumentTest(unittest.TestCase):

    def test_workdir_without_external_keeps_artel_rule(self):
        """`workdir` без режима внешнего проекта — правило артели: функция `tests/support.py` не помощник.

        Ловит мутацию: режим внешнего проекта выводится из непустого
        `workdir` — модуль `support` (под `workdir` или без него)
        находится, и утверждение помощника попадает в список метода.
        """
        files = {"backend/tests/support.py": HELPER, "tests/support.py": HELPER}
        modules = guard.TestModules(files.get, workdir="backend",
                                    in_scope=lambda path: True)
        self.assertEqual([], found_texts(CALLER, "backend/tests/test_x.py",
                                         modules))

    def test_external_without_workdir_traces_scope_module(self):
        """Внешний режим с пустым `workdir`: функция `tests/support.py` области — помощник.

        Ловит мутацию: у внешнего режима функции прослеживаются только из
        `tests/sandbox.py` — список метода пуст.
        """
        modules = guard.TestModules({"tests/support.py": HELPER}.get,
                                    external=True)
        self.assertEqual(["test.assertEqual(value, 7)"],
                         found_texts(CALLER, "tests/test_x.py", modules))

    def test_external_module_outside_scope_is_not_read(self):
        """Внешний режим: модуль вне области не читается вовсе — и не помощник.

        Ловит мутацию: сверка с областью идёт после чтения модуля либо не
        идёт — загрузчик зовётся с `backend/app/svc.py`.
        """
        asked = []

        def load(path):
            asked.append(path)
            return HELPER

        source = ("from app.svc import expect_ok\n\n\n"
                  "class C:\n"
                  "    def test_m(self):\n"
                  "        expect_ok(self, run())\n")
        modules = guard.TestModules(load, external=True, workdir="backend",
                                    in_scope=in_backend_tests)
        self.assertEqual([], found_texts(source, "backend/tests/test_x.py",
                                         modules))
        self.assertNotIn("backend/app/svc.py", asked)


class RelativeImportTest(unittest.TestCase):

    def test_parent_relative_import_with_slashed_workdir(self):
        """Внешний режим, `workdir: backend/`: `from ..h import f` из `backend/tests/api/test_x.py` ведёт к `backend/tests/h.py`.

        Ловит мутацию: `workdir` не нормализуется от завершающей косой —
        путь модуля `backend//tests/h.py` не совпадает ни с файлом, ни с
        областью, список метода пуст.
        """
        modules = guard.TestModules({"backend/tests/h.py": HELPER}.get,
                                    external=True, workdir="backend/",
                                    in_scope=in_backend_tests)
        source = ("from ..h import expect_ok\n\n\n"
                  "class C:\n"
                  "    def test_m(self):\n"
                  "        expect_ok(self, run())\n")
        self.assertEqual(["test.assertEqual(value, 7)"], found_texts(
            source, "backend/tests/api/test_x.py", modules))


class ScopeBaseClassTest(unittest.TestCase):

    def test_base_class_of_scope_module_lends_helper_method(self):
        """Внешний режим: метод базового класса модуля области — помощник наследника.

        Ловит мутацию: перевод имени модуля с `workdir` применён только к
        функциям, а базовые классы по-прежнему ищутся как `tests/base.py`
        — цепочка класса обрывается, список метода пуст.
        """
        base = ("import unittest\n\n\n"
                "class Base(unittest.TestCase):\n"
                "    def check(self, value):\n"
                "        self.assertEqual(value, 3)\n")
        source = ("from tests.base import Base\n\n\n"
                  "class C(Base):\n"
                  "    def test_m(self):\n"
                  "        self.check(run())\n")
        modules = guard.TestModules({"backend/tests/base.py": base}.get,
                                    external=True, workdir="backend",
                                    in_scope=in_backend_tests)
        self.assertEqual(["self.assertEqual(value, 3)"],
                         found_texts(source, "backend/tests/test_x.py",
                                     modules))

    def test_method_literal_keys_sees_external_helper(self):
        """`method_literal_keys` с модулями внешнего режима видит литерал помощника под `workdir`.

        Ловит мутацию: `method_literal_keys` разбирает свой модуль без
        переданных модулей стороны — литерала `7` помощника нет в ответе.
        """
        modules = guard.TestModules({"backend/tests/support.py": HELPER}.get,
                                    external=True, workdir="backend",
                                    in_scope=in_backend_tests)
        keys = guard.method_literal_keys(CALLER, "backend/tests/test_x.py",
                                         "C::test_m", modules)
        self.assertIn(guard._side_key("7"), keys)


if __name__ == "__main__":
    unittest.main()
