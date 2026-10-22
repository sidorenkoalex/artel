"""AC-1: каждый подслучай разбиваемого метода — отдельный метод, перечень — доли.

Группа: разовый
Красен до реализации: методы ещё не разбиты — метод со старым именем исполняет все подслучаи (несколько вызовов `developer_advance`/`fail_gate`, все метки `assert_depth`, все места `places`/`PLACES`), новых методов нет. Временный стаб разбиения (outcome_gate — индекс вместо цикла, доли по две, категории одной долей) красил все тесты файла зелёными; стаб удалён.

Методы-кандидаты (старые имена и все тестовые методы файла, которых нет на
базе) гоняются из копии модуля головы с записывающими заглушками помощников
(`_split.py`): запись называет подслучай, который метод исполнил.
"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _split as S  # noqa: E402


class SplitShapeTest(unittest.TestCase):

    def assert_present(self, rel):
        head = S.qualified(S.head_text(rel))
        for old in S.SPLIT[rel]:
            self.assertIn(old, head, f"{rel}: исходного имени {old} нет")

    def test_ac1_profile_places_each_kind_split_into_shares(self):
        """Места `places` у обоих профилей `PultUnchangedTest` — по доле на метод.

        Сценарий: кандидаты profile_callers гоняются с заглушкой `places`
        (к перечню добавлено лишнее место) и записью `calls_of`. Каждый
        метод исполняет места ровно одного профиля; места профиля делятся
        на K ≥ 2 долей `sorted(places)[i::K]`, каждое место — ровно одним
        методом; метод со старым именем — первую долю своего профиля; у
        каждого нового метода есть записи.

        Ловит мутацию: метод со старым именем оставлен с циклом по всему
        `places` — у профиля одна доля из всех мест; доля взята срезом
        `[i*n:(i+1)*n]` без сортировки — набор мест метода не совпадает
        с `[i::K]`.
        """
        self.assert_present(S.PROFILE)
        runs = S.fake_runs(S.PROFILE)
        places = S.recorded(runs, "place")
        full = S.profile_places() + [S.EXTRA_PLACE]
        for old, kind in ((S.P_EXT, S.EXT_KIND), (S.P_ARTEL, S.ARTEL_KIND)):
            with self.subTest(kind=kind):
                group = {}
                for name, labels in places.items():
                    labels = [x[0] for x in labels]
                    kinds = {x.split(": ", 1)[0] for x in labels}
                    self.assertLessEqual(len(kinds), 1, f"{name}: места двух профилей")
                    if kinds == {kind}:
                        group[name] = [x.split(": ", 1)[1] for x in labels]
                problems = S.check_partition(group, full, old, 2)
                self.assertEqual(problems, [], S.describe(runs))
        for name, run in runs.items():
            self.assertTrue(run.records, f"{name}: метод не исполняет ни одного места")

    def test_ac1_pytest_own_places_three_methods_split_into_shares(self):
        """Места `PLACES` трёх методов pytest_own_places — по доле на метод.

        Сценарий: кандидаты гоняются из копии модуля с лишним элементом
        `PLACES`, `scenario`/`check_home` записываются. Методы делятся на
        группы `test_ac3_home_fresh…` (режим `pass` и `check_home`),
        `test_ac3_home_removed…` (`sleep`/`signal` и `check_home`),
        `test_ac6_child_gone…` (`sleep`/`signal` без `check_home`); в
        группе каждая пара (место, режим) исполняется ровно одним методом,
        наборы мест методов — доли `sorted(PLACES)[i::K]`, K ≥ 2; метод со
        старым именем — первая доля; неразобранных методов нет.

        Ловит мутацию: метод со старым именем `test_ac6_…` по-прежнему
        проходит все восемь мест — одна доля из всех мест; режим `signal`
        потерян при разбиении — пара (место, `signal`) не исполняется ни
        одним методом.
        """
        self.assert_present(S.OWN)
        runs = S.fake_runs(S.OWN)
        groups, stray = S.own_groups(runs)
        self.assertEqual(stray, [], S.describe(runs))
        full = S.module_places(S.head_text(S.OWN)) + [S.EXTRA_PLACE]
        modes = {S.W_FRESH: ("pass",), S.W_REMOVED: ("sleep", "signal"),
                 S.W_CHILD: ("sleep", "signal")}
        for old, group in groups.items():
            with self.subTest(old=old):
                self.assertEqual(S.own_share_problems(group, old, modes[old], full),
                                 [], S.describe(runs))

    def test_ac1_signal_fixed_cases_one_method_each(self):
        """`test_ac9`: старое имя — только «ADR в ТЗ», каждый из шести фиксированных подслучаев — ровно одним методом.

        Сценарий: кандидаты spec_audit_flow гоняются с записью
        `assert_depth` (метка подслучая) и заглушками подготовки. Метод со
        старым именем записывает ровно «ADR в ТЗ»; каждая из шести
        фиксированных меток записана ровно одним методом, и этот метод
        других меток не несёт; метки «путь <категория>» несут только
        методы-доли, делящие категории на `sorted(...)[i::K]`.

        Ловит мутацию: за старым именем оставлен первый подслучай после
        перемешивания зерном (а не «ADR в ТЗ» по сортировке); «бюджет 44»
        оставлен в методе вместе с «бюджет 45» — метод несёт две метки.
        """
        self.assert_present(S.AUDIT)
        runs = S.fake_runs(S.AUDIT)
        signal, _fail, stray = S.audit_groups(runs)
        self.assertEqual(stray, [], S.describe(runs))
        self.assertEqual(signal.get(S.A_SIGNAL), [S.AC9_FIRST], S.describe(runs))
        for label in S.AC9_FIXED:
            with self.subTest(label=label):
                owners = [n for n, labels in signal.items() if label in labels]
                self.assertEqual(len(owners), 1, S.describe(runs))
                self.assertEqual(signal[owners[0]], [label], S.describe(runs))
        shares = {n: labels for n, labels in signal.items()
                  if not set(labels) & set(S.AC9_FIXED)}
        self.assertTrue(all(x.startswith("путь ") for v in shares.values() for x in v),
                        S.describe(runs))
        problems = S.check_partition(shares, S.category_labels(), None, 1)
        self.assertEqual(problems, [], S.describe(runs))

    def test_ac1_fail_verdict_forms_one_method_each(self):
        """`test_ac20`: старое имя — только форма `"sha"`, форма `"short"` — отдельный новый метод.

        Сценарий: кандидаты spec_audit_flow гоняются с заглушками
        `fail_gate`/`cli`/`live_sha`. Методов, заводящих задачу на гейте
        после fail, ровно два; у старого имени — одна задача и только
        approve с позиционным sha; у второго — одна задача и только
        `approve <id> --accept-audit-fail`.

        Ловит мутацию: цикл `for form in forms` оставлен в старом имени —
        два вызова `fail_gate` и обе формы в одном методе; за старым именем
        оставлена форма `"short"` (первая до сортировки) — у него нет
        approve с sha.
        """
        runs = S.fake_runs(S.AUDIT)
        _signal, fail, _stray = S.audit_groups(runs)
        self.assertIn(S.A_FAIL, fail, S.describe(runs))
        self.assertEqual(fail[S.A_FAIL]["gates"], 1, S.describe(runs))
        self.assertEqual(fail[S.A_FAIL]["forms"], ["sha"], S.describe(runs))
        others = [n for n in fail if n != S.A_FAIL]
        self.assertEqual(len(others), 1, S.describe(runs))
        self.assertNotIn(others[0], S.qualified(S.base_text(S.AUDIT)))
        self.assertEqual(fail[others[0]]["gates"], 1, S.describe(runs))
        self.assertEqual(fail[others[0]]["forms"], ["short"], S.describe(runs))

    def check_outcome_chunk(self, chunk):
        runs = S.fake_runs(S.OUTCOME, chunk, 4)
        for name, run in runs.items():
            advances = sum(1 for r in run.records if r[0] == "advance")
            self.assertEqual(advances, 1, f"{name}: подслучаев (developer_advance) "
                                          f"{advances}\n{S.describe(runs)}")

    def test_ac1_outcome_gate_one_subcase_per_method_part0(self):
        """Каждый кандидат outcome_gate (часть 1 из 4) исполняет ровно один подслучай.

        Сценарий: кандидаты (`candidates[0::4]`) гоняются с заглушкой
        `developer_advance`, которая записывает вызов и прерывает метод;
        у каждого — ровно одна запись.

        Ловит мутацию: метод со старым именем сохранил цикл подслучаев под
        `subTest` — несколько записей `developer_advance`.
        """
        self.check_outcome_chunk(0)

    def test_ac1_outcome_gate_one_subcase_per_method_part1(self):
        """Каждый кандидат outcome_gate (часть 2 из 4) исполняет ровно один подслучай.

        Сценарий: как у части 1, кандидаты `candidates[1::4]`.

        Ловит мутацию: новый метод несёт два подслучая (например,
        «таймаут база» и «таймаут голова» вместе) — две записи.
        """
        self.check_outcome_chunk(1)

    def test_ac1_outcome_gate_one_subcase_per_method_part2(self):
        """Каждый кандидат outcome_gate (часть 3 из 4) исполняет ровно один подслучай.

        Сценарий: как у части 1, кандидаты `candidates[2::4]`.

        Ловит мутацию: ветвление по метке в старом имени исполняет все
        ветви подряд — несколько записей.
        """
        self.check_outcome_chunk(2)

    def test_ac1_outcome_gate_one_subcase_per_method_part3(self):
        """Каждый кандидат outcome_gate (часть 4 из 4) исполняет ровно один подслучай.

        Сценарий: как у части 1, кандидаты `candidates[3::4]`.

        Ловит мутацию: новый метод без вызова `developer_advance` (подслучай
        потерян, метод пуст) — ноль записей.
        """
        self.check_outcome_chunk(3)

    def test_ac1_outcome_gate_method_count_and_no_loop(self):
        """В outcome_gate кандидатов ровно столько, сколько подслучаев, и ни один не вызывает `developer_advance` в цикле.

        Сценарий: исходные имена шести методов есть в голове; кандидатов
        (старые имена и новые методы файла) — 4+4+5+5+3+4 = 25; в теле
        кандидата (`ast.walk`) нет `for`/`while`/включения, внутри которого
        вызывается `self.developer_advance`.

        Ловит мутацию: два подслучая слиты в один новый метод — кандидатов
        24; цикл подслучаев оставлен без `subTest` (первая же заглушка
        прерывает метод, запись одна) — цикл виден в теле.
        """
        self.assert_present(S.OUTCOME)
        names = S.candidates(S.OUTCOME)
        self.assertEqual(len(names), sum(S.OUTCOME_SUBCASES.values()), names)
        funcs = S.qualified(S.head_text(S.OUTCOME))
        loops = (ast.For, ast.While, ast.ListComp, ast.SetComp, ast.GeneratorExp,
                 ast.DictComp)
        for name in names:
            for loop in ast.walk(funcs[name]):
                if not isinstance(loop, loops):
                    continue
                for node in ast.walk(loop):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                            and node.func.attr == "developer_advance":
                        self.fail(f"{name}: developer_advance в цикле (строка {loop.lineno})")

    def test_ac1_no_class_recollects_test_methods(self):
        """Новые классы и классы со сменой баз не собирают повторно тестовые методы.

        Сценарий: в каждом файле зоны у класса головы, которого нет на базе
        или чьи базы сменились, среди классов-предков того же файла нет
        методов `test*` — ни параметризованного подкласса исходного класса,
        ни выделенного класса-наследника.

        Ловит мутацию: доли оформлены подклассами
        `class PultUnchangedShare1Test(PultUnchangedTest)` — подкласс
        наследует `test_ac10_*` исходного класса.
        """
        for rel in S.ZONE:
            head, base = S.class_defs(S.head_text(rel)), S.class_defs(S.base_text(rel))
            for name, node in head.items():
                old = base.get(name)
                if old is not None and [ast.dump(b) for b in old.bases] == \
                        [ast.dump(b) for b in node.bases]:
                    continue
                with self.subTest(file=rel, cls=name):
                    self.assertEqual(S.inherited_tests(S.head_text(rel), name), set())


if __name__ == "__main__":
    unittest.main()
