"""Юнит-тесты повторного прогона долгоживущих файлов, несущих случайное
зерно (`orchestrator/acceptance.py::carries_random_seed`/`run_repeat`,
SPEC 01M48FRD9RJDBBVT2SN0FY5G2A, требование 2) — углы, не покрытые
долгоживущими файлами задачи (`tests/test_01m48frd9rjdbbvt2sn0fy5g2a_*.py`):
формы импорта, тест-функция без класса, истёкший предел повтора.
"""
import subprocess
import unittest
from unittest import mock

from orchestrator import acceptance, config
from tests.sandbox import TmpDirTest

RED_FUNCTION = '''import random


def test_fn():
    print("зерно: 4242")
    assert False


def test_green():
    print("зерно: 77")
'''

RED_WITHOUT_SEED = '''import random


class TestFx:
    def test_quiet(self):
        assert False
'''


class CarriesRandomSeedTest(TmpDirTest):

    def write(self, text: str):
        path = self.tdir / "test_fx.py"
        path.write_text(text, encoding="utf-8")
        return path

    def test_import_forms_count_and_mentions_do_not(self):
        """Признак зерна — импорт модуля `random` в любой форме и в любом месте файла, а не упоминание слова.

        Ловит мутацию: признак ищет подстроку `import random` в начале
        строки — импорт с псевдонимом, через запятую или внутри функции
        выпадает; либо подстроку `random` — файл, где слово только в
        строке или комментарии, повторяется; либо `from .random import`
        (свой модуль пакета) принимается за модуль `random`.
        """
        carrying = ("import random as rnd\n",
                    "import os, random\n",
                    "def f():\n    from random import Random\n",
                    "if True:\n    import random\n")
        for text in carrying:
            with self.subTest(text=text):
                self.assertTrue(acceptance.carries_random_seed(self.write(text)))
        plain = ('"""import random"""\n',
                 "# import random\nimport os\n",
                 "from .random import thing\n",
                 "import randomize\n",
                 "def broken(:\n")
        for text in plain:
            with self.subTest(text=text):
                self.assertFalse(acceptance.carries_random_seed(self.write(text)))


class RunRepeatTest(TmpDirTest):

    def test_function_node_and_seed_from_junit_report(self):
        """Красная тест-функция без класса названа узлом `файл::функция` со своим зерном; зерно зелёного теста не примешано.

        Ловит мутацию: узел строится только для методов класса (функция
        названа точечным `classname` без пути файла); зёрна берутся из
        всего вывода прогона, а не из вывода красного теста (в узле
        оказывается зерно 77 зелёного теста); красный повтор считается
        зелёным.
        """
        rel = "tests/test_fx_fn.py"
        (self.tdir / "tests").mkdir()
        (self.tdir / rel).write_text(RED_FUNCTION, encoding="utf-8")
        reds = acceptance.run_repeat([rel], self.tdir)
        self.assertEqual(reds, [acceptance.RedTest(f"{rel}::test_fn",
                                                   ("4242",))])

    def test_red_without_seed_line_has_no_seeds(self):
        """Красный тест, не напечатавший «зерно: N», назван узлом с пустым перечнем зёрен.

        Ловит мутацию: тест без строки зерна выпадает из перечня красных
        (повтор засчитан зелёным) или получает чужое зерно.
        """
        rel = "tests/test_fx_quiet.py"
        (self.tdir / "tests").mkdir()
        (self.tdir / rel).write_text(RED_WITHOUT_SEED, encoding="utf-8")
        reds = acceptance.run_repeat([rel], self.tdir)
        self.assertEqual(reds, [acceptance.RedTest(
            f"{rel}::TestFx::test_quiet", ())])

    def test_timeout_is_red_for_each_file(self):
        """Истёкший `config.ACCEPTANCE_TIMEOUT_SEC` повтора — красный повтор по каждому файлу с пометкой предела.

        Ловит мутацию: предел повтора не передан `subprocess.run` (повтор
        без предела); истёкший предел считается зелёным повтором или
        пропуском (пустой перечень красных).
        """
        files = ["tests/test_a.py", "tests/test_b.py"]
        seen: dict = {}

        def expire(*args, **kwargs):
            seen.update(kwargs)
            raise subprocess.TimeoutExpired(args[0], kwargs.get("timeout"),
                                            output=b"\xd0\xb7\xd0\xb5\xd1\x80"
                                            b"\xd0\xbd\xd0\xbe: 99\n")

        with mock.patch.object(acceptance.subprocess, "run", expire):
            reds = acceptance.run_repeat(files, self.tdir)
        self.assertEqual(seen.get("timeout"), config.ACCEPTANCE_TIMEOUT_SEC)
        self.assertEqual([r.node for r in reds], files)
        for red in reds:
            self.assertEqual(red.seeds, ("99",))
            self.assertIn(str(config.ACCEPTANCE_TIMEOUT_SEC), red.note)


if __name__ == "__main__":
    unittest.main()
