"""Юнит-тесты сравнения параметризации гейта неослабления (SPEC
01M56TNZ3E72XY9XSTAVS99CN2, требования 1, 3-5): разбор
`guard.parametrize_variants`, исход `test_integrity._parametrize_findings`
на краях, которых не касаются долгоживущие файлы задачи, и выбор вариантов
двустороннего прогона при сорванной стороне.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.advance_gates import test_integrity, two_sided  # noqa: E402
from scripts import guard  # noqa: E402

PATH = "tests/test_fx.py"
NAME = "TestFx::test_x"


def source(decorator: str, prelude: str = "", args: str = "k") -> str:
    lines = ["import pytest", "", prelude, "", "class TestFx:", ""]
    if decorator:
        lines.append(f"    @{decorator}")
    signature = f"self, {args}" if args else "self"
    lines += [f"    def test_x({signature}):", "        assert k", ""]
    return "\n".join(lines)


def compare(base: str, head: str) -> tuple:
    found, grown = test_integrity._parametrize_findings(
        PATH, PATH, None, base, head)
    return [f.name for f in found], [f.name for f in grown]


class ParametrizeVariantsTest(unittest.TestCase):

    def test_argnames_form_and_order_change_is_a_finding(self):
        """Смена формы имён аргументов (`"k, v"` → `["k", "v"]`), `indirect=` и перестановка прежних вариантов — находка (ANSWER-1 п. 2).

        Ловит мутацию: имена аргументов приводятся к нормальной форме,
        прочие именованные аргументы не входят в текст вызова или
        варианты сравниваются без учёта порядка — смена проходит молча.
        """
        base = "pytest.mark.parametrize('k, v', [(1, 2), (3, 4)])"
        for head in ("pytest.mark.parametrize(['k', 'v'], [(1, 2), (3, 4)])",
                     "pytest.mark.parametrize('k, v', [(1, 2), (3, 4)], "
                     "indirect=True)",
                     "pytest.mark.parametrize('k, v', [(3, 4), (1, 2)])"):
            with self.subTest(head=head):
                self.assertEqual(([NAME], []), compare(
                    source(base, args="k, v"), source(head, args="k, v")))

    def test_variant_inserted_among_kept_ones_is_growth(self):
        """Вариант, вставленный между прежними при их прежнем порядке, — добавление, не находка.

        Ловит мутацию: варианты сравниваются по позиции — вставка в
        середину читается как смена прежних и даёт находку.
        """
        base = source("pytest.mark.parametrize('k', [1, 2, 3])")
        head = source("pytest.mark.parametrize('k', [1, 9, 2, 3])")
        self.assertEqual(([], [NAME]), compare(base, head))

    def test_ids_change_is_a_finding(self):
        """Смена `ids=` при тех же вариантах — находка.

        Ловит мутацию: прочие именованные аргументы марки не входят в
        подпись — смена `ids=` проходит молча.
        """
        base = source("pytest.mark.parametrize('k', [1, 2], ids=['a', 'b'])")
        head = source("pytest.mark.parametrize('k', [1, 2], ids=['a', 'c'])")
        self.assertEqual(([NAME], []), compare(base, head))

    def test_new_skipped_variant_is_a_finding_not_growth(self):
        """Новый вариант с маркой пропуска `pytest.param(…, marks=pytest.mark.skip)` — находка, а не добавление.

        Ловит мутацию: марка пропуска проверяется только у прежних
        вариантов — новый пропущенный вариант уходит в добавления.
        """
        base = source("pytest.mark.parametrize('k', [1, 2])")
        head = source("pytest.mark.parametrize('k', [1, 2, "
                      "pytest.param(3, marks=pytest.mark.skip)])")
        self.assertEqual(([NAME], []), compare(base, head))

    def test_parametrize_added_to_existing_method_is_a_finding(self):
        """Марка `parametrize`, появившаяся у метода, который в базе не параметризован, — находка.

        Ловит мутацию: сравниваются только места марок, бывшие в базе, —
        новая марка у прежнего метода проходит молча.
        """
        base = source("", prelude="k = 1", args="")
        head = source("pytest.mark.parametrize('k', [1, 2])")
        self.assertEqual(([NAME], []), compare(base, head))

    def test_any_changed_line_naming_the_constant_is_a_finding(self):
        """Изменённая строка модуля или тела класса с именем, переданным `parametrize`, — находка при прежнем тексте декоратора (ANSWER-1 п. 1).

        Константа `CASES` декоратора `parametrize('k', CASES)`: смена
        аннотированного присваивания, добавленные `CASES.pop()`,
        `CASES += [4]`, повторное присваивание, правка константы-элемента
        набора `CASES = [A, 2]` и строки в теле класса.

        Ловит мутацию: сравнивается только текст присвоенного значения
        (или только `ast.Assign`) — `pop`/`+=`/повторное присваивание,
        аннотированная константа, строка тела класса или элемент-имя
        набора проходят без находки.
        """
        decorator = "pytest.mark.parametrize('k', CASES)"
        cases = {
            "аннотированная": ("CASES: list = [1, 2, 3]",
                               "CASES: list = [1, 2]"),
            "pop": ("CASES = [1, 2, 3]", "CASES = [1, 2, 3]\nCASES.pop()"),
            "+=": ("CASES = [1, 2, 3]", "CASES = [1, 2, 3]\nCASES += [4]"),
            "повторное": ("CASES = [1, 2, 3]",
                          "CASES = [1, 2, 3]\nCASES = [1]"),
            "элемент-имя": ("A = 1\nCASES = [A, 2]", "A = 5\nCASES = [A, 2]"),
        }
        for case, (before, after) in cases.items():
            with self.subTest(case=case):
                self.assertEqual(([NAME], []), compare(
                    source(decorator, prelude=before),
                    source(decorator, prelude=after)))
        base = source(decorator).replace(
            "class TestFx:\n", "class TestFx:\n    CASES = [1, 2]\n")
        head = base.replace("CASES = [1, 2]", "CASES = [1]")
        self.assertEqual(([NAME], []), compare(base, head))

    def test_unrelated_module_line_is_not_a_finding(self):
        """Строка модуля без имён вызова `parametrize` меняется — находки нет.

        Ловит мутацию: строками константы считаются все строки модуля —
        любая правка файла теста даёт находку параметризации.
        """
        decorator = "pytest.mark.parametrize('k', CASES)"
        base = source(decorator, prelude="CASES = [1, 2]\nOTHER = 1")
        head = source(decorator, prelude="CASES = [1, 2]\nOTHER = 2")
        self.assertEqual(([], []), compare(base, head))


class CommonVariantsTest(unittest.TestCase):

    def test_failed_side_keeps_own_variants(self):
        """Сторона, чей прогон сорвался, — без отчёта: вторая судится по своим вариантам, отказа «нет общих вариантов» нет.

        Ловит мутацию: сорванная сторона считается пустым набором
        вариантов — пересечение пусто, и вместо причины сбоя стороны
        метод получает отказ «нет вариантов, общих обеим сторонам».
        """
        node = f"{PATH}::{NAME}"
        records = [{"nodeid": f"{node}[1]", "when": "call",
                    "outcome": "failed", "assertion": True}]
        variants, reason = two_sided._common_variants(
            {two_sided.NEW_ON_BASE: records, two_sided.OLD_ON_BRANCH: None},
            {two_sided.NEW_ON_BASE: node, two_sided.OLD_ON_BRANCH: node})
        self.assertEqual("", reason)
        self.assertEqual({"[1]"}, variants[two_sided.NEW_ON_BASE])


if __name__ == "__main__":
    unittest.main()
