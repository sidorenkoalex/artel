"""Сужение признания ячейки «Чем покрыто после» при профиле в границе гейта
исходов (SPEC 01M5FRYVP4NF81VT00FYPHPWJH, требование 8): токен — только
путь файла целиком (с необязательным `:<число>`) в области. Ячейка
сверяется `mandate._covered` с признаком границы — вместе с прежним
правилом путей `*.py`.
"""
import unittest

from orchestrator import project_profile
from orchestrator.advance_gates import mandate

ELEMENT = "src/a.test.ts"

IN_BOUNDS = project_profile.Profile(
    command=("python3", "-m", "pytest"), long_lived_dir="src",
    long_lived_name="test_<id>_<name>.py", weakening_scope=("src/**",),
    mutation_claim_scope=("src/test_*.py",), project="p", component="web",
    report="junit-xml", from_components=True)


class ComponentCoveredFileTokenTest(unittest.TestCase):

    def test_file_paths_admitted(self):
        """Путь файла области токеном, в кавычках, в выделении, с `:12`, с запятой после; путь `*.py` внутри ячейки и id своего компонента — покрытие.

        Ловит мутацию: хвост `:<число>` не допускается (ссылка на строку
        отклоняется); выделение `*`/`_` не снимается до сверки; сужение
        задело прежнее правило путей `*.py` или идентификатор своего
        компонента в кавычках.
        """
        for cell in (ELEMENT, f"`{ELEMENT}`", f"**{ELEMENT}**",
                     f"_{ELEMENT}_", f"{ELEMENT}:12", f"{ELEMENT},",
                     f"тест {ELEMENT} держит", "см. src/test_a.py::test_x",
                     f"`web:{ELEMENT}::case`"):
            with self.subTest(cell=cell):
                self.assertTrue(mandate._covered(cell, IN_BOUNDS, True))

    def test_directory_mask_and_suffixes_refused(self):
        """«`src/`», «src/**», «src/a.test.ts::x», «src/a.test.ts.» и путь вне области — не покрытие.

        Ловит мутацию: токен сверяется только с масками области (каталог
        `src/` и сама маска `src/**` признаются покрытием); регулярка ищет
        путь внутри токена, а не совпадает целиком (`::x` и точка в конце
        проходят).
        """
        for cell in ("`src/`", "src/**", f"{ELEMENT}::x", f"{ELEMENT}.",
                     "lib/a.test.ts"):
            with self.subTest(cell=cell):
                self.assertFalse(mandate._covered(cell, IN_BOUNDS, True))


if __name__ == "__main__":
    unittest.main()
