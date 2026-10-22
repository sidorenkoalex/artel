"""AC-7: учёт `guard.test_assertions` по старому имени не меньше прежнего; таблица и сверка в PLAN.md.

Группа: разовый
Красен до реализации: PLAN.md с таблицей «старый тест → новые тесты» и сверкой мультимножеств ещё нет; включение учёта по старому имени зелено на базе (голова равна базе) и держит неослабление при разбиении (на стабе разбиения зелено). Таблица PLAN стабом не проверяется: `artifact_text` читает ревизию ссылки документов.
"""
import collections
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _split as S  # noqa: E402


class AssertionsTest(unittest.TestCase):

    def test_ac7_old_name_keeps_assertion_multiset(self):
        """Мультимножество утверждений каждого разбиваемого метода на базе ⊆ мультимножество одноимённого метода головы.

        Сценарий: `guard.test_assertions` по обеим сторонам каждого из
        четырёх файлов (модули `tests/` своей стороны — для помощников
        `tests/sandbox.py`); для каждого из двенадцати методов перечня
        `Counter` нормальных форм базы минус `Counter` головы пуст.

        Ловит мутацию: метод со старым именем `test_ac8_…` несёт только
        тело подслучая «сломан» — утверждения ветвей «нестабилен» и «база»
        (`refusal(…, OUTCOME_ACTION)`, `no_gate_refusal`, `assertTrue(any(
        FLAKY_ON_BASE …))`) пропали из учёта.
        """
        for rel in S.ZONE:
            base, head = S.assertions(rel, "base"), S.assertions(rel, "head")
            for old in S.SPLIT[rel]:
                with self.subTest(method=old):
                    self.assertIn(old, head)
                    lost = collections.Counter(k for k, _t in base[old]) - \
                        collections.Counter(k for k, _t in head[old])
                    texts = [t for k, t in base[old] if k in lost]
                    self.assertEqual(dict(lost), {}, texts)

    def test_ac7_plan_table_and_multiset_reconciliation(self):
        """PLAN.md несёт таблицу «старый тест → новые тесты» по каждому разбитому методу и сверку `Counter` по `guard.test_assertions`.

        Сценарий: в строках таблиц PLAN.md (строки на `|`) названы все
        двенадцать старых методов и все новые методы файлов зоны (имя
        метода); текст PLAN называет `test_assertions` и `Counter`.

        Ловит мутацию: таблица PLAN забыла новый метод доли — его имени нет
        ни в одной строке таблицы.
        """
        plan = S.plan_text()
        rows = "\n".join(line for line in plan.splitlines() if line.lstrip().startswith("|"))
        names = [old for _rel, old in S.ALL_SPLIT] + \
            [n for rel in S.ZONE for n in S.new_names(rel)]
        for name in names:
            with self.subTest(method=name):
                self.assertIn(name.split(S.SEP)[-1], rows)
        self.assertIn("test_assertions", plan)
        self.assertIn("Counter", plan)


if __name__ == "__main__":
    unittest.main()
