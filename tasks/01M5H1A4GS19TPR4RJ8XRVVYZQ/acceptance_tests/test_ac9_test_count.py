"""AC-9: число тестов до и после — разница равна добавленным методам минус 13 классов `tests_dir`; копий нет.

Группа: разовый
Красен до реализации: методы не добавлены и `tests_dir` ещё собирается — разница сборов 0, а не «добавлено минус 13»; PLAN.md с пересчётом ещё нет. На стабе разбиения разница сборов зелена (добавлено 31, минус 13); PLAN стабом не проверяется — `artifact_text` читает ревизию ссылки документов.

Сбор — `pytest --collect-only` четырёх файлов зоны во временном пакете
`tests` (база и голова — одинаково); прочие файлы `tests/` не меняются
(AC-6), поэтому разница набора — разница этих четырёх файлов.
"""
import functools
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _split as S  # noqa: E402


@functools.lru_cache(maxsize=None)
def collected(side: str) -> tuple:
    read = S.base_text if side == "base" else S.head_text
    return tuple(S.collect({rel: read(rel) for rel in S.ZONE}))


def added() -> int:
    return sum(len(S.new_names(rel)) for rel in S.ZONE)


class CountTest(unittest.TestCase):

    def test_ac9_collected_delta_equals_added_minus_tests_dir(self):
        """Собранных тестов на голове больше, чем на базе, ровно на число новых методов минус 13.

        Сценарий: на базе `::tests_dir` собран в 13 классах; разница числа
        собранных элементов голова − база равна числу новых тестовых
        методов файлов зоны (квалифицированных имён, которых нет на базе)
        минус 13; на голове `::tests_dir` не собирается.

        Ловит мутацию: доля вынесена в подкласс исходного класса — pytest
        собирает прочие методы исходного класса повторно, разница больше
        ожидаемой.
        """
        base, head = collected("base"), collected("head")
        self.assertEqual(sum(1 for i in base if i.endswith("::tests_dir")), S.TESTS_DIR_CLASSES)
        self.assertEqual(sum(1 for i in head if i.endswith("::tests_dir")), 0)
        self.assertEqual(len(head) - len(base), added() - S.TESTS_DIR_CLASSES,
                         f"база {len(base)}, голова {len(head)}, добавлено {added()}")

    def test_ac9_plan_counts_with_recount(self):
        """PLAN.md несёт число тестов до и после с пересчётом: число добавленных методов и 13.

        Сценарий: PLAN.md из ссылки документов задачи называет число
        добавленных разбиением методов (по диффу файлов зоны) и число 13
        (классы, где собирался `tests_dir`), а также слова «до» и «после».

        Ловит мутацию: пересчёт в PLAN забыл вычесть `tests_dir` — числа 13
        в PLAN нет; число добавленных методов в PLAN не то, что в коде.
        """
        plan = S.plan_text()
        self.assertRegex(plan, rf"(?<!\d){added()}(?!\d)")
        self.assertRegex(plan, r"(?<!\d)13(?!\d)")
        self.assertRegex(plan, r"(?i)\bдо\b")
        self.assertRegex(plan, r"(?i)\bпосле\b")


if __name__ == "__main__":
    unittest.main()
