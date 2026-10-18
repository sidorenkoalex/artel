"""Двусторонний прогон судит параметризованный тест по вариантам, общим обеим сторонам; исходы непараметризованного теста прежние (AC-1..AC-3).

Группа: долгоживущий
Красен до реализации: вердикт стороны ищет в отчёте pytest точный id узла `путь::Класс::метод`, а параметризованный тест отчитан вариантами `::метод[<id>]` — поэтому у параметризованного метода, падающего на утверждении каждым вариантом на обеих сторонах, исход «узел не найден» вместо «пройден» (AC-1); AC-2 (отказ при пустом пересечении вариантов) и AC-3 (исходы непараметризованного теста, сосед `::test_x_slow` без `::test_x`) держат сегодняшнее поведение и зелёны с рождения.

Связка «двусторонний прогон — git — pytest»: `two_sided.run` на настоящем
git песочницы (`tests.sandbox.GitignoreCommittedRealGitSandbox`) — база
на основной ветке, голова на ветке; деревья сторон и прогоны pytest —
настоящие. Наблюдаемое — `Outcome.results` (итог по адресу метода) и
`Outcome.refusals` (строки отказа). Случай «соседний узел
`::test_x_slow`, а `::test_x` нет» — на синтетическом отчёте (решение
Оператора на гейте SPEC): запуск pytest стороны подменён записью
заготовленных строк отчёта в файл `two_sided.REPORT_ENV`, git — настоящий.

Провалидировано временным стабом реализации (удалён, не закоммичен):
поиск вариантов `<id узла>[…]` в отчёте стороны, вердикт по общим
вариантам с id варианта в причине и отказ при пустом пересечении — все
методы зелёные.

Имена файлов, классов, методов, вариантов и ожидаемые значения —
случайные при каждом запуске; зерно печатается и входит в текст каждого
провала.
"""
import json
import random
import subprocess
import unittest
from unittest import mock

from orchestrator import config
from orchestrator.advance_gates import two_sided
from tests.sandbox import GitignoreCommittedRealGitSandbox

ALPHABET = "abcdefghijklmnopqrstuvwxyz"
NOT_FOUND = "узел не найден"
GREEN = "зелёная — "
SKIPPED = "пропуск (фаза "
COLLECT = "ошибка сборки (collect)"
DOCSTRING = ['"""Фикстура сценария.', "",
             "Ловит мутацию: фикстура песочницы.", '"""']


def method_text(name: str, body: list, values: list | None = None) -> str:
    """Метод класса фикстуры: `values` — варианты `parametrize` по
    аргументу `k` (`None` — метод без параметризации)."""
    lines = []
    if values is None:
        lines.append(f"    def {name}(self):")
    else:
        lines.append(f"    @pytest.mark.parametrize('k', {values!r})")
        lines.append(f"    def {name}(self, k):")
    lines += [f"        {line}" if line else "" for line in DOCSTRING + body]
    return "\n".join(lines) + "\n"


def pytest_class(cls: str, methods: list, imports: str = "") -> str:
    """Файл с классом в стиле pytest (без `unittest.TestCase`)."""
    return (f"import pytest\n\nimport app\n{imports}\n\nclass {cls}:\n\n"
            + "\n".join(methods))


def unittest_class(cls: str, methods: list, imports: str = "") -> str:
    """Файл с классом `unittest.TestCase` — стиль тестов артели."""
    return (f"import unittest\n\nimport app\n{imports}\n\n"
            f"class {cls}(unittest.TestCase):\n\n" + "\n".join(methods))


class TwoSidedSandbox(GitignoreCommittedRealGitSandbox):
    """Репозиторий песочницы: `app.py` и файлы тестов базы на основной
    ветке, голова — коммит на ветке задачи."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used: set = set()
        self.old = self.rng.randrange(1000, 5000)
        self.new = self.old + self.rng.randrange(1, 4000)

    def word(self, size: int = 6) -> str:
        while True:
            found = "".join(self.rng.choice(ALPHABET) for _ in range(size))
            if found not in self.used:
                self.used.add(found)
                return found

    def why(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def write(self, files: dict) -> None:
        for rel, text in files.items():
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

    def sides(self, base: dict, head: dict) -> tuple:
        """(ветка, sha базы): `base` и `app.py` со значением `old` — коммит
        основной ветки; `head` и `app.py` со значением `new` — коммит
        ветки поверх неё."""
        self.write({"app.py": f"VALUE = {self.old}\n", **base})
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "база")
        base_sha = self.git("rev-parse", "HEAD").strip()
        branch = f"task/fx-{self.word()}"
        self.checkout(branch, create=True)
        self.write({"app.py": f"VALUE = {self.new}\nNEXT = 1\n", **head})
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "голова")
        self.checkout(config.MAIN_BRANCH)
        return branch, base_sha

    def run_methods(self, base: dict, head: dict, names: list) -> tuple:
        """(исход прогона, {имя: адрес метода}) — `names` — пары (путь,
        квалифицированное имя)."""
        branch, base_sha = self.sides(base, head)
        methods = [two_sided.Method(path, path, name, base[path], head[path])
                   for path, name in names]
        outcome = two_sided.run(self.root, branch, base_sha, methods)
        return outcome, {name: m.address for (_p, name), m
                         in zip(names, methods)}

    @staticmethod
    def method_refusals(outcome, path: str, name: str) -> list:
        prefix = f"{path}: {name}: "
        return [r for r in outcome.refusals if r.startswith(prefix)]


# AC-1 -----------------------------------------------------------------------

class ParametrizedVariantsTest(TwoSidedSandbox):

    def test_ac1_parametrized_test_judged_by_variants(self):
        """Параметризованный тест со сменой литерала утверждения: все варианты падают на утверждении обеих сторон — «пройден»; вариант, не упавший на утверждении на одной стороне, — отказ, называющий его id.

        Класс в стиле pytest, у каждого метода
        `@pytest.mark.parametrize('k', [...])` с 2-3 вариантами, одинаковыми
        в базе и в голове; в базе утверждение `app.VALUE == <old>`, в голове
        — `== <new>`, `app.VALUE` базы и головы различаются. Методы:
        каждый вариант падает на утверждении на обеих сторонах; новая
        версия на дереве базы зелёная у одного варианта; старая версия на
        дереве головы зелёная у одного варианта; новая версия на дереве
        базы у одного варианта падает `KeyError`; старая версия на дереве
        головы у одного варианта падает `KeyError`. Особый вариант выбран
        по длине id, в тексте теста id не встречается. Итог первого метода
        — `two_sided.PASSED`; у остальных — не `PASSED`, строка отказа
        метода называет id особого варианта. Ни в одном итоге и ни в
        одной строке отказа нет «узел не найден».

        Ловит мутацию: вердикт по-прежнему ищет точный id узла — у всех
        методов «узел не найден», первый не «пройден»; варианты
        засчитываются по первому найденному — зелёный или упавший
        исключением вариант не замечен, метод «пройден»; одна из сторон
        по-прежнему ищет точный узел — у метода другой стороны отказ без
        id варианта; причина называет метод без id варианта — id в строке
        отказа нет.
        """
        cls = f"TestFx{self.word().capitalize()}"
        path = f"tests/test_fx_{self.word()}.py"
        old_assert = f"assert app.VALUE == {self.old}"
        new_assert = f"assert app.VALUE == {self.new}"
        special = {}

        def variants(name: str) -> tuple:
            """(варианты, длина id особого варианта)."""
            plain = [self.word(5) for _ in range(self.rng.randrange(1, 3))]
            odd = self.word(9)
            special[name] = odd
            found = plain + [odd]
            self.rng.shuffle(found)
            return found, len(odd)

        names = {kind: f"test_{kind}_{self.word(4)}" for kind in (
            "pass", "base_green", "head_green", "base_error", "head_error")}
        base_methods, head_methods = [], []
        values, _length = variants(names["pass"])
        base_methods.append(method_text(names["pass"], [old_assert], values))
        head_methods.append(method_text(names["pass"], [new_assert], values))
        for kind in ("base_green", "head_green", "base_error", "head_error"):
            values, length = variants(names[kind])
            if kind.endswith("green"):
                odd_old = [f"{old_assert} or len(k) == {length}"]
                odd_new = [f"{new_assert} or len(k) == {length}"]
            else:
                odd_old = [f"if len(k) == {length}:",
                           "    raise KeyError(len(k))", old_assert]
                odd_new = [f"if len(k) == {length}:",
                           "    raise KeyError(len(k))", new_assert]
            on_base_tree = kind.startswith("base")
            base_methods.append(method_text(
                names[kind], [old_assert] if on_base_tree else odd_old, values))
            head_methods.append(method_text(
                names[kind], odd_new if on_base_tree else [new_assert], values))
        base = {path: pytest_class(cls, base_methods)}
        head = {path: pytest_class(cls, head_methods)}
        outcome, addresses = self.run_methods(
            base, head, [(path, f"{cls}::{n}") for n in names.values()])
        context = self.why(f"refusals: {outcome.refusals!r}\n"
                           f"results: {outcome.results!r}")

        everything = list(outcome.refusals) + [str(v) for v in
                                               outcome.results.values()]
        self.assertFalse([t for t in everything if NOT_FOUND in t], context)
        qualified = f"{cls}::{names['pass']}"
        self.assertEqual(two_sided.PASSED,
                         outcome.results.get(addresses[qualified]), context)
        self.assertEqual([], self.method_refusals(outcome, path, qualified),
                         context)
        for kind in ("base_green", "head_green", "base_error", "head_error"):
            qualified = f"{cls}::{names[kind]}"
            with self.subTest(case=kind):
                self.assertNotEqual(two_sided.PASSED,
                                    outcome.results.get(addresses[qualified]),
                                    context)
                text = "\n".join(self.method_refusals(outcome, path, qualified))
                self.assertIn(special[names[kind]], text, self.why(
                    f"{kind}: отказ не называет вариант "
                    f"{special[names[kind]]}:\n{context}"))


# AC-2 -----------------------------------------------------------------------

class DisjointVariantsTest(TwoSidedSandbox):

    def test_ac2_no_common_variants_is_refusal(self):
        """Варианты базы и головы не пересекаются — отказ с непустой причиной, не «пройден».

        Параметризованный метод класса в стиле pytest: в базе варианты
        `[a1, a2(, a3)]` и утверждение `== <old>`, в голове — другие
        варианты `[b1, b2(, b3)]` и `== <new>`; каждый вариант каждой
        версии падает на утверждении на чужом дереве. Итог метода — не
        `two_sided.PASSED` и не пустой; у метода есть строка отказа с
        текстом причины после адреса.

        Ловит мутацию: вердикт берётся как «все общие варианты упали на
        утверждении» по пустому набору (`all([])`) — пустое пересечение
        даёт «пройден»; варианты каждой стороны судятся отдельно, без
        сверки общих — оба набора упали, метод «пройден».
        """
        cls = f"TestFx{self.word().capitalize()}"
        path = f"tests/test_fx_{self.word()}.py"
        name = f"test_disjoint_{self.word(4)}"
        count = self.rng.randrange(2, 4)
        base_values = [self.word(5) for _ in range(count)]
        head_values = [self.word(7) for _ in range(count)]
        base = {path: pytest_class(cls, [method_text(
            name, [f"assert app.VALUE == {self.old}"], base_values)])}
        head = {path: pytest_class(cls, [method_text(
            name, [f"assert app.VALUE == {self.new}"], head_values)])}
        qualified = f"{cls}::{name}"
        outcome, addresses = self.run_methods(base, head, [(path, qualified)])
        context = self.why(f"refusals: {outcome.refusals!r}\n"
                           f"results: {outcome.results!r}")
        result = outcome.results.get(addresses[qualified])
        self.assertNotEqual(two_sided.PASSED, result, context)
        self.assertTrue(result, context)
        refusals = self.method_refusals(outcome, path, qualified)
        self.assertTrue(refusals, context)
        prefix = f"{path}: {qualified}: "
        self.assertTrue(all(r[len(prefix):].strip() for r in refusals), context)


# AC-3 -----------------------------------------------------------------------

class PlainTestOutcomesTest(TwoSidedSandbox):

    def test_ac3_plain_test_outcomes_unchanged(self):
        """Непараметризованный тест артели: падение на утверждении обеих сторон — «пройден»; зелёная сторона — «зелёная — …»; пропуск — «пропуск (фаза …)»; ошибка сборки — «ошибка сборки (collect)».

        Класс `unittest.TestCase`, `app.VALUE` базы и головы различаются.
        Методы: `assertEqual(app.VALUE, <old>)` → `<new>`; новая версия
        `assertIn(app.VALUE, (<old>, <new>))` — зелёная на дереве базы;
        новая версия начинается с `self.skipTest(…)`; второй файл (своим
        прогоном: ошибка сборки прерывает весь сеанс pytest стороны), чья
        новая версия импортирует `from app import NEXT` (имени нет в
        `app.py` базы). Итоги: первого — `two_sided.PASSED`; второго
        несёт «зелёная — », третьего — «пропуск (фаза », четвёртого —
        «ошибка сборки (collect)»; ни один не «узел не найден».

        Ловит мутацию: поиск вариантов `<узел>[…]` подменяет точный поиск
        — непараметризованный узел не найден, все исходы «узел не найден»;
        вердикт по вариантам не различает зелёную сторону и пропуск —
        «зелёная — »/«пропуск (фаза » пропали из итога; ошибка сборки
        соседнего файла перестала распознаваться при отсутствии записей
        узла — нет «ошибка сборки (collect)».
        """
        cls = f"Fx{self.word().capitalize()}Test"
        path = f"tests/test_fx_{self.word()}.py"
        collect_path = f"tests/test_fx_{self.word()}.py"
        names = {kind: f"test_{kind}_{self.word(4)}"
                 for kind in ("pass", "green", "skip", "collect")}
        old = f"self.assertEqual(app.VALUE, {self.old})"
        new = f"self.assertEqual(app.VALUE, {self.new})"
        base = {path: unittest_class(cls, [
                    method_text(names["pass"], [old]),
                    method_text(names["green"], [old]),
                    method_text(names["skip"], [old])]),
                collect_path: unittest_class(cls, [
                    method_text(names["collect"], [old])])}
        head = {path: unittest_class(cls, [
                    method_text(names["pass"], [new]),
                    method_text(names["green"], [
                        f"self.assertIn(app.VALUE, ({self.old}, {self.new}))"]),
                    method_text(names["skip"], [
                        f"self.skipTest('нужна база {self.word()}')", new])]),
                collect_path: unittest_class(cls, [
                    method_text(names["collect"], [new])],
                    imports="from app import NEXT\n")}
        # Ошибка сборки прерывает весь сеанс pytest стороны — файл с ней
        # идёт своим прогоном, иначе соседи остались бы без записей.
        results, contexts = {}, []
        for group in ((path, ("pass", "green", "skip")),
                      (collect_path, ("collect",))):
            rel, kinds = group
            outcome, addresses = self.run_methods(
                {rel: base[rel]}, {rel: head[rel]},
                [(rel, f"{cls}::{names[k]}") for k in kinds])
            contexts.append(f"refusals: {outcome.refusals!r}\n"
                            f"results: {outcome.results!r}")
            for kind in kinds:
                results[kind] = outcome.results.get(
                    addresses[f"{cls}::{names[kind]}"]) or ""
        context = self.why("\n".join(contexts))

        self.assertEqual(two_sided.PASSED, results["pass"], context)
        for kind, needle in (("green", GREEN), ("skip", SKIPPED),
                             ("collect", COLLECT)):
            with self.subTest(case=kind):
                self.assertIn(needle, results[kind], context)
                self.assertNotIn(NOT_FOUND, results[kind], context)

    def test_ac3_prefix_neighbour_node_not_counted(self):
        """Синтетический отчёт: узла `::test_x` нет, есть `::test_x_slow`, упавший на утверждении, — «узел не найден», соседний узел не засчитан.

        Репозиторий и деревья сторон — настоящие; запуск pytest стороны
        (вызов с плагином `two_sided.PLUGIN_MODULE`) подменён: в файл
        отчёта `two_sided.REPORT_ENV` пишутся записи фаз setup/call/
        teardown узла `<путь>::<Класс>::test_<x>_slow` — фаза call упала
        `AssertionError` на утверждении. Метод прогона —
        `<Класс>::test_<x>`. Итог метода — не `two_sided.PASSED` и несёт
        «узел не найден».

        Ловит мутацию: варианты узла ищутся префиксом строки
        (`startswith(<узел>)`) вместо `<узел>[` — `::test_x_slow`
        засчитан вариантом, метод «пройден».
        """
        cls = f"Fx{self.word().capitalize()}Test"
        path = f"tests/test_fx_{self.word()}.py"
        name = f"test_{self.word()}"
        base = {path: unittest_class(cls, [method_text(
            name, [f"self.assertEqual(app.VALUE, {self.old})"])])}
        head = {path: unittest_class(cls, [method_text(
            name, [f"self.assertEqual(app.VALUE, {self.new})"])])}
        neighbour = f"{path}::{cls}::{name}_slow"
        records = [
            {"nodeid": neighbour, "when": "setup", "outcome": "passed"},
            {"nodeid": neighbour, "when": "call", "outcome": "failed",
             "exception": "AssertionError", "assertion": True,
             "timeout": False, "in_setup": False, "location": None},
            {"nodeid": neighbour, "when": "teardown", "outcome": "passed"}]
        real_run = subprocess.run
        launches = []

        def fake_run(cmd, *args, **kwargs):
            argv = [str(a) for a in cmd] if isinstance(cmd, (list, tuple)) \
                else [str(cmd)]
            if two_sided.PLUGIN_MODULE not in argv:
                return real_run(cmd, *args, **kwargs)
            launches.append(argv)
            report = kwargs["env"][two_sided.REPORT_ENV]
            with open(report, "a", encoding="utf-8") as fh:
                for record in records:
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            return subprocess.CompletedProcess(cmd, 1, "", "")

        branch, base_sha = self.sides(base, head)
        method = two_sided.Method(path, path, f"{cls}::{name}", base[path],
                                  head[path])
        with mock.patch.object(subprocess, "run", fake_run):
            outcome = two_sided.run(self.root, branch, base_sha, [method])
        context = self.why(f"refusals: {outcome.refusals!r}\n"
                           f"results: {outcome.results!r}")
        self.assertTrue(launches, self.why(
            f"запуск pytest стороны не встретился:\n{context}"))
        result = outcome.results.get(method.address) or ""
        self.assertNotEqual(two_sided.PASSED, result, context)
        self.assertIn(NOT_FOUND, result, context)


if __name__ == "__main__":
    unittest.main()
