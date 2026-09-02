"""AC-7 (tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/SPEC.md): когда пакет поделён
на части (AC-5) больше одной, итоговый текст явно требует прочитать все
части по порядку, прежде чем действовать; когда деления нет (одна
часть/часть отсутствует), такой инструкции в тексте нет — она не имеет
смысла без реального деления.

## Допущение теста

SPEC не даёт формулировку инструкции в кавычках (в отличие, например,
от AC-13, где причина отказа гейта дана дословно в «шнурках»); формулировка
самой AC-7 — «прочитать все части по порядку» — сильно предполагает
близкое воспроизведение этих же слов в реализации (та же практика уже
видна в остальном коде пакета: `review.py` уже почти дословно повторяет
формулировки SPEC/ТЗ в текстах, которые видит роль). Тест поэтому ищет
подстроку «по порядку» как маркер инструкции; если разработчик выберет
существенно другую формулировку, это разногласие правильно ловить на
ревью, а не тихо подгонять тест под непредсказанный текст задним числом.

Красен до реализации (test_ac7_oversized_diff_carries_the_read_in_order_
instruction): сегодня деления на части не существует вовсе, инструкции
«прочитать части по порядку» в тексте пакета нет ни при каком размере
diff.

Зелёный с рождения (test_ac7_small_diff_does_not_carry_a_pointless_
instruction): маленький diff не порождает такую инструкцию уже сегодня
— по банальной причине «её нет вообще нигде», а не по осмысленному
условию «частей не больше одной»; после реализации это же отсутствие
обязано остаться, но уже как СЛЕДСТВИЕ условия AC-7, не совпадение.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import FakeGitDiff, build_review_package, standard_files  # noqa: E402

LINE_COUNT = 10_000


def _big_diff() -> str:
    return "\n".join(f"+line-{i:05d}" for i in range(LINE_COUNT))


class Ac7ReadPartsInOrderTest(unittest.TestCase):

    def build(self, diff: str) -> str:
        git = FakeGitDiff(files=standard_files(), diff=diff)
        return build_review_package(git)["text"]

    def test_ac7_oversized_diff_carries_the_read_in_order_instruction(self):
        text = self.build(_big_diff())

        self.assertIn(
            "по порядку", text,
            "diff поделён на несколько частей — текст обязан явно "
            "требовать прочитать их все по порядку (AC-7)")

    def test_ac7_small_diff_does_not_carry_a_pointless_instruction(self):
        text = self.build("diff --git a b\n+одна строка")

        self.assertNotIn(
            "по порядку", text,
            "diff меньше потолка части — делить нечего, инструкция "
            "«прочитать части по порядку» не должна появляться без "
            "реального деления (AC-7 применяется только когда частей "
            "больше одной)")


if __name__ == "__main__":
    unittest.main()
