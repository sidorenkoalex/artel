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

    def test_argnames_forms_and_order_are_not_a_change(self):
        """Имена аргументов строкой и списком и перестановка прежних вариантов — не находка.

        Ловит мутацию: имена аргументов сравниваются сырым текстом —
        `"k, v"` против `["k", "v"]` даёт находку; варианты сравниваются
        по позиции — перестановка даёт находку.
        """
        base = source("pytest.mark.parametrize('k, v', [(1, 2), (3, 4)])",
                      args="k, v")
        head = source("pytest.mark.parametrize(['k', 'v'], [(3, 4), (1, 2)])",
                      args="k, v")
        self.assertEqual(([], []), compare(base, head))

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

    def test_annotated_module_constant_is_resolved(self):
        """Аргумент-имя константы модуля с аннотацией (`CASES: list = [...]`) раскрывается до значения.

        Ловит мутацию: раскрывается только `ast.Assign` — смена значения
        аннотированной константы при прежнем декораторе не видна.
        """
        decorator = "pytest.mark.parametrize('k', CASES)"
        base = source(decorator, prelude="CASES: list = [1, 2, 3]")
        head = source(decorator, prelude="CASES: list = [1, 2]")
        marks = guard.parametrize_variants(base)[NAME]
        self.assertEqual(("1", "2", "3"), marks[0].variants)
        self.assertEqual(([NAME], []), compare(base, head))


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
