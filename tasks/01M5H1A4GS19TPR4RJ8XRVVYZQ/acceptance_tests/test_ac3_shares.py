"""AC-3: перечни делятся на доли `перечень[i::K]` после сортировки, без вписанной копии.

Группа: разовый
Красен до реализации: перечни ещё не делятся — у каждого перечня один метод несёт все элементы (доля одна), методов-долей с `assertTrue(доля)` нет, PLAN.md без сценария объединения долей; тест «нет вписанной копии» зелен на базе (голова равна базе). Стаб разбиения (по две доли, категории одной долей) красил зелёными все тесты, кроме PLAN.md — его стабом не проверить: `artifact_text` читает ревизию ссылки документов.

Лишний элемент перечня подставляется так, как его добавил бы автор правки:
в `places` — заглушкой метода, в `PLACES` — правкой текста копии модуля, в
категории `config` — `mock.patch.dict` константы до загрузки копии модуля.
"""
import ast
import collections
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _split as S  # noqa: E402


def constants(text) -> collections.Counter:
    return collections.Counter(n.value for n in ast.walk(ast.parse(text))
                               if isinstance(n, ast.Constant) and isinstance(n.value, str))


class SharesTest(unittest.TestCase):

    def test_ac3_added_element_lands_in_exactly_one_share(self):
        """Элемент, добавленный в исходный перечень, исполняется ровно одним методом без правки теста.

        Сценарий: лишнее место в `places` (у каждого из двух профилей),
        лишний элемент в конце литерала `PLACES` (в каждой из трёх групп и
        каждом режиме группы), лишняя категория в константе `config`
        (`путь <категория>` у `test_ac9`). Каждое лишнее исполнено ровно
        одним методом группы, и метод — не единственный в группе (перечень
        разделён).

        Ловит мутацию: доли выписаны копией перечня в тесте (`SHARE_1 =
        ("acceptance.run", …)`) — лишний элемент не исполняет ни один
        метод.
        """
        places = S.recorded(S.fake_runs(S.PROFILE), "place")
        for kind in (S.EXT_KIND, S.ARTEL_KIND):
            label = f"{kind}: {S.EXTRA_PLACE}"
            owners = [n for n, v in places.items() if (label,) in v]
            group = [n for n, v in places.items() if v and v[0][0].startswith(kind + ": ")]
            with self.subTest(list="places", kind=kind):
                self.assertEqual(len(owners), 1, S.describe(S.fake_runs(S.PROFILE)))
                self.assertGreaterEqual(len(group), 2, group)
        groups, _stray = S.own_groups(S.fake_runs(S.OWN))
        modes = {S.W_FRESH: ("pass",), S.W_REMOVED: ("sleep", "signal"),
                 S.W_CHILD: ("sleep", "signal")}
        for old, group in groups.items():
            for mode in modes[old]:
                owners = [n for n, v in group.items() if (S.EXTRA_PLACE, mode) in v]
                with self.subTest(list="PLACES", old=old, mode=mode):
                    self.assertEqual(len(owners), 1, S.describe(S.fake_runs(S.OWN)))
                    self.assertGreaterEqual(len(group), 2, sorted(group))
        signal, _fail, _stray = S.audit_groups(S.fake_runs(S.AUDIT))
        label = f"путь {S.EXTRA_CATEGORY}"
        owners = [n for n, v in signal.items() if label in v]
        with self.subTest(list="категории config"):
            self.assertEqual(len(owners), 1, S.describe(S.fake_runs(S.AUDIT)))
            self.assertNotEqual(owners[0], S.A_SIGNAL)

    def test_ac3_shares_follow_sorted_stride(self):
        """Наборы элементов методов-долей — ровно `sorted(перечень)[i::K]` с K от 2 до длины перечня.

        Сценарий: по записям прогона с заглушками у каждого перечня (два
        профиля `places`, три группы `PLACES`, категории `test_ac9`)
        элементы делятся между методами без пересечений и пропусков, а
        набор каждого метода равен одному из срезов `[i::K]` сортированного
        перечня (у категорий `test_ac9` K ≥ 1 — они и так вне старого
        имени).

        Ловит мутацию: доли нарезаны подряд `перечень[:4]`/`перечень[4:]` —
        набор метода не совпадает со срезом с шагом K; перечень не
        сортирован перед нарезкой — срезы другие.
        """
        places = S.recorded(S.fake_runs(S.PROFILE), "place")
        full = S.profile_places() + [S.EXTRA_PLACE]
        for old, kind in ((S.P_EXT, S.EXT_KIND), (S.P_ARTEL, S.ARTEL_KIND)):
            group = {n: [x[0].split(": ", 1)[1] for x in v] for n, v in places.items()
                     if v and v[0][0].startswith(kind + ": ")}
            with self.subTest(list="places", kind=kind):
                self.assertEqual(S.check_partition(group, full, old, 2), [])
        groups, _stray = S.own_groups(S.fake_runs(S.OWN))
        full = S.module_places(S.head_text(S.OWN)) + [S.EXTRA_PLACE]
        modes = {S.W_FRESH: ("pass",), S.W_REMOVED: ("sleep", "signal"),
                 S.W_CHILD: ("sleep", "signal")}
        for old, group in groups.items():
            with self.subTest(list="PLACES", old=old):
                self.assertEqual(S.own_share_problems(group, old, modes[old], full), [])
        signal, _fail, _stray = S.audit_groups(S.fake_runs(S.AUDIT))
        shares = {n: v for n, v in signal.items() if all(x.startswith("путь ") for x in v)}
        with self.subTest(list="категории config"):
            self.assertTrue(shares, S.describe(S.fake_runs(S.AUDIT)))
            self.assertEqual(S.check_partition(shares, S.category_labels(), None, 1), [])

    def test_ac3_each_share_asserts_nonempty(self):
        """Каждый метод-доля утверждает непустоту доли вызовом `self.assertTrue(...)` от нелитерала.

        Сценарий: методы-доли всех перечней (по записям прогона); в теле
        каждого (`ast.walk`) есть вызов `self.assertTrue` с первым
        аргументом-выражением, не литералом.

        Ловит мутацию: `assertTrue(доля)` не добавлен в метод доли — при K
        больше длины перечня пустая доля прошла бы зелёной без проверок.
        """
        groups = S.share_methods()
        for old, members in groups.items():
            rel = next(r for r, names in S.SPLIT.items() if old in names)
            funcs = S.qualified(S.head_text(rel))
            with self.subTest(old=old):
                self.assertTrue([m for m in members if m != old], members)
            for member in members:
                with self.subTest(method=member):
                    calls = [n for n in ast.walk(funcs[member]) if isinstance(n, ast.Call)
                             and isinstance(n.func, ast.Attribute)
                             and n.func.attr == "assertTrue" and n.args
                             and not isinstance(n.args[0], ast.Constant)]
                    self.assertTrue(calls, "нет assertTrue(доля)")

    def test_ac3_home_shares_run_at_least_twice(self):
        """В каждой доле обоих `test_ac3_*` не меньше двух прогонов `scenario`.

        Сценарий: прогон с заглушками; у каждого метода групп
        `test_ac3_home_fresh…` и `test_ac3_home_removed…` записей
        `scenario` не меньше двух.

        Ловит мутацию: `PLACES` разделён на восемь долей по одному месту —
        проверка «HOME не общий у нескольких прогонов» в доле пуста, у
        метода одна запись.
        """
        groups, _stray = S.own_groups(S.fake_runs(S.OWN))
        for old in (S.W_FRESH, S.W_REMOVED):
            for name, pairs in groups[old].items():
                with self.subTest(method=name):
                    self.assertGreaterEqual(len(pairs), 2, pairs)

    def test_ac3_no_written_copy_of_lists(self):
        """В голове нет вписанной копии перечня: литералы элементов перечней встречаются не чаще, чем на базе.

        Сценарий: метки `places` базы, элементы литерала `PLACES` базы и
        имена категорий константы `config` — число их вхождений строковыми
        константами в файле головы не больше, чем в файле базы.

        Ловит мутацию: доли выписаны кортежами меток мест в коде теста —
        метка встречается в голове дважды.
        """
        base_places = S.profile_places_of(S.base_text(S.PROFILE))
        pairs = ((S.PROFILE, base_places),
                 (S.OWN, S.module_places(S.base_text(S.OWN))),
                 (S.AUDIT, [c for c in getattr(S.config, S.signal_constant_name())]))
        for rel, items in pairs:
            head, base = constants(S.head_text(rel)), constants(S.base_text(rel))
            for item in items:
                with self.subTest(file=rel, item=item):
                    self.assertLessEqual(head[item], base[item])

    def test_ac3_plan_shows_union_and_disjoint_shares(self):
        """PLAN.md несёт сценарий: объединение долей равно полному перечню, доли не пересекаются.

        Сценарий: текст PLAN.md из ссылки документов задачи называет
        объединение долей и их непересечение.

        Ловит мутацию: PLAN.md сдан без сценария проверки долей — слов об
        объединении и пересечении нет.
        """
        plan = S.plan_text()
        self.assertRegex(plan, r"(?i)объединени")
        self.assertRegex(plan, r"(?i)пересека|пересечени")


if __name__ == "__main__":
    unittest.main()
