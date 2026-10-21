"""Литералы `test_ac1_outcome_carries_relative_assertion_location` — из функции генерации от зерна без совпадений; `two_sided.run` и утверждения — в помощнике с параметром зерна, подготовка с `self.git` — в теле методов (AC-11, AC-12).

Группа: разовый

Красен до реализации: литералы метода строятся прямо от `rng` (`new = old + rng.randrange(1, 4000)`, `bare_old = old + 7`), функции генерации и помощника с параметром зерна нет, теста на зерне 189949286 нет — поиск функции генерации падает в обоих тестах.

Как тест находит имена, которых SPEC не называет:
- помощник — метод `self.<имя>(…)`, вызванный в теле метода (имя не на
  `test`), в теле которого стоит вызов `two_sided.run`;
- функция генерации — функция модуля файла (или метод класса), которую
  зовут и метод, и помощник, причём аргумент её вызова в методе передан
  помощнику и в помощнике стоит первым аргументом её вызова тем же
  параметром (одно и то же зерно);
- тест на зерне — другой `test_…` того же класса с литералом 189949286,
  зовущий помощник;
- значения литералов результата — по именам SPEC (`old`, `new`,
  `bare_old`, `bare_new`, `sent_other`, `sent_same`): ключ отображения
  либо атрибут.
"""
import ast
import importlib
import inspect
import sys
import unittest
from collections.abc import Mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _util import (TWO_SIDED, assertion_texts, base_source,  # noqa: E402
                   class_methods, find_method, guard_assertions, head_source,
                   missing, parse, qualified, run_pytest)

METHOD = "test_ac1_outcome_carries_relative_assertion_location"
SEED = 189949286
SEEDS = list(range(20000)) + [SEED, 12, 9694, 11783]
NAMES = ("old", "new", "bare_old", "bare_new", "sent_other", "sent_same")
WRITE_CALLS = ("write_text", "write_bytes", "write")


def is_two_sided_run(node) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run" and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "two_sided")


def self_call_nodes(func, name: str) -> list:
    return [n for n in ast.walk(func) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute) and n.func.attr == name
            and isinstance(n.func.value, ast.Name) and n.func.value.id == "self"]


def callee_key(call):
    if isinstance(call.func, ast.Name):
        return ("module", call.func.id)
    if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) \
            and call.func.value.id in ("self", "cls"):
        return ("method", call.func.attr)
    return None


def calls_of(func, key) -> list:
    return [n for n in ast.walk(func) if isinstance(n, ast.Call) and callee_key(n) == key]


def call_args(call) -> list:
    """(позиция либо имя ключевого, выражение) аргументов вызова."""
    return [(i, a) for i, a in enumerate(call.args)] + \
           [(k.arg, k.value) for k in call.keywords]


def param_for(helper, slot):
    """Имя параметра помощника под позицией (без `self`) или ключом."""
    params = [a.arg for a in helper.args.posonlyargs + helper.args.args][1:]
    if isinstance(slot, int):
        return params[slot] if slot < len(params) else None
    return slot


class Structure:
    """Найденные по разбору головы метод, помощник, функция генерации и тест на зерне."""

    def __init__(self):
        self.tree = parse(head_source(TWO_SIDED))
        self.cls, self.method = find_method(self.tree, METHOD)
        assert self.method is not None, "метода нет в голове"
        self.funcs = class_methods(self.cls)
        self.module_funcs = {n.name: n for n in self.tree.body
                             if isinstance(n, ast.FunctionDef)}
        self.helper = None
        for name in dict.fromkeys(n.func.attr for n in ast.walk(self.method)
                                  if isinstance(n, ast.Call)
                                  and isinstance(n.func, ast.Attribute)
                                  and isinstance(n.func.value, ast.Name)
                                  and n.func.value.id == "self"):
            func = self.funcs.get(name)
            if func is not None and not name.startswith("test") and any(
                    is_two_sided_run(x) for x in ast.walk(func)):
                self.helper = func
                break
        assert self.helper is not None, "помощника с two_sided.run, вызванного методом, нет"
        self.gen = None
        for key in dict.fromkeys(filter(None, (callee_key(n) for n in ast.walk(self.method)
                                               if isinstance(n, ast.Call)))):
            kind, name = key
            if (kind == "module" and name not in self.module_funcs) or \
                    (kind == "method" and (name not in self.funcs or name == self.helper.name)):
                continue
            if calls_of(self.helper, key) and self.same_seed(self.method, key):
                self.gen = key
                break
        assert self.gen is not None, ("нет функции генерации, которую метод и помощник "
                                      "зовут с одним и тем же зерном")
        self.seed_test = None
        for name, func in self.funcs.items():
            if name.startswith("test") and name != METHOD and any(
                    isinstance(n, ast.Constant) and n.value == SEED for n in ast.walk(func)) \
                    and self_call_nodes(func, self.helper.name):
                self.seed_test = func
        assert self.seed_test is not None, f"теста на зерне {SEED}, зовущего помощник, нет"

    def same_seed(self, func, key) -> bool:
        """Первый аргумент вызова генерации в `func` передан помощнику, и
        помощник зовёт генерацию этим параметром."""
        gens = calls_of(func, key)
        helpers = self_call_nodes(func, self.helper.name)
        if not gens or not helpers or not gens[0].args:
            return False
        seed = ast.dump(gens[0].args[0])
        h_gens = calls_of(self.helper, key)
        for call in helpers:
            for slot, expr in call_args(call):
                if ast.dump(expr) != seed:
                    continue
                param = param_for(self.helper, slot)
                if any(g.args and isinstance(g.args[0], ast.Name) and g.args[0].id == param
                       for g in h_gens):
                    return True
        return False

    def generator(self):
        module = importlib.import_module(TWO_SIDED[:-3].replace("/", "."))
        kind, name = self.gen
        if kind == "module":
            return getattr(module, name)
        attr = inspect.getattr_static(getattr(module, self.cls.name), name)
        if isinstance(attr, (staticmethod, classmethod)):
            return getattr(getattr(module, self.cls.name), name)
        return getattr(getattr(module, self.cls.name)(METHOD), name)


def derived_names(func, key) -> set:
    """Имена, связанные с результатом генерации в `func` (и их простые
    переприсваивания)."""
    names = set()
    for n in ast.walk(func):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) \
                and callee_key(n.value) == key:
            names |= {x.id for t in n.targets for x in ast.walk(t) if isinstance(x, ast.Name)}
    changed = True
    while changed:
        changed = False
        for n in ast.walk(func):
            if isinstance(n, ast.Assign) and _pure_derived(n.value, names):
                for t in n.targets:
                    for x in ast.walk(t):
                        if isinstance(x, ast.Name) and x.id not in names:
                            names.add(x.id)
                            changed = True
    return names


def _base_name(expr):
    while isinstance(expr, (ast.Attribute, ast.Subscript)):
        expr = expr.value
    return expr.id if isinstance(expr, ast.Name) else None


def _pure_derived(expr, names) -> bool:
    if isinstance(expr, ast.Tuple):
        return bool(expr.elts) and all(_pure_derived(e, names) for e in expr.elts)
    return isinstance(expr, (ast.Name, ast.Attribute, ast.Subscript)) and \
        _base_name(expr) in names


def _stringish(expr) -> bool:
    return (isinstance(expr, ast.JoinedStr)
            or (isinstance(expr, ast.Constant) and isinstance(expr.value, str))
            or (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name)
                and expr.func.id in ("str", "repr")))


def arithmetic_on(func, names) -> list:
    out = []
    for n in ast.walk(func):
        # `/` — склейка путей (`self.root / lit["path"]`), не арифметика.
        if isinstance(n, ast.BinOp) and not isinstance(n.op, ast.Div):
            sides = (n.left, n.right)
            direct = [s for s in sides if _pure_derived(s, names)]
            if direct and not any(_stringish(s) for s in sides):
                out.append(ast.unparse(n))
        if isinstance(n, ast.AugAssign) and (_pure_derived(n.target, names)
                                             or _pure_derived(n.value, names)):
            out.append(ast.unparse(n))
    return out


def random_calls(func) -> list:
    out = []
    for n in ast.walk(func):
        if isinstance(n, ast.Call):
            text = ast.unparse(n.func)
            if (text.startswith("random.") and text != "random.randrange") \
                    or text in ("Random", "rng") or text.startswith("rng."):
                out.append(ast.unparse(n))
        if isinstance(n, ast.Name) and n.id == "rng":
            out.append("rng")
    return out


def value(result, name):
    if isinstance(result, Mapping):
        return result[name]
    return getattr(result, name)


class TwoSidedSeedTest(unittest.TestCase):

    maxDiff = None

    def test_ac11_generated_literals_never_collide(self):
        """Функция генерации на зёрнах 0…19999 и 189949286, 12, 9694, 11783 даёт `bare_old != new`, `bare_new != old`, `old != new`, `sent_*` вне `{old, new}`.

        Сценарий: функция генерации найдена разбором (докстринг модуля) и
        вызвана с каждым зерном так же, как её зовёт метод (одним
        аргументом-зерном); значения берутся по именам SPEC.

        Ловит мутацию: сдвиг голого `assert` оставлен 7 при сдвиге `new` из
        1…3999 — на зерне 189949286 `new == bare_old`; `sent_same` выбран из
        диапазона, пересекающего `new`.
        """
        st = Structure()
        gen = st.generator()
        bad = []
        for seed in SEEDS:
            try:
                res = gen(seed)
                v = {n: value(res, n) for n in NAMES}
            except (KeyError, AttributeError, TypeError) as exc:
                self.fail(f"зерно {seed}: значения {NAMES} не получены: {exc!r}")
            if not (v["bare_old"] != v["new"] and v["bare_new"] != v["old"]
                    and v["old"] != v["new"]
                    and v["sent_other"] not in (v["old"], v["new"])
                    and v["sent_same"] not in (v["old"], v["new"])):
                bad.append((seed, v))
        self.assertEqual(bad[:5], [], f"совпадения на {len(bad)} зёрнах")

    def test_ac12_helper_holds_run_and_assertions_methods_hold_setup(self):
        """`two_sided.run` и утверждения — в помощнике с зерном; подготовка с пятью `self.git` и `self.checkout` — в методе и в тесте на зерне 189949286; литералы — только из генерации; гейт видит не меньше 9 утверждений без потерь.

        Сценарий: разбор головы — помощник (имя не на `test`) несёт
        `two_sided.run`, метод его не несёт; метод и тест на зерне: не
        меньше пяти `self.git(…)`, `self.checkout(…)`, вызов помощника,
        вызов генерации с тем зерном, что передано помощнику; запись файлов
        (`write_text`) использует результат генерации; помощнику переданы
        `base_sha` и `branch`; ни метод, ни тест на зерне, ни помощник не
        зовут `random.*` (кроме `random.randrange` выбора зерна) и `rng`,
        не делают арифметики над результатом генерации. Утверждения
        `self.assert…` метода базы дословно (`ast.unparse`) стоят в
        помощнике. Тест на зерне 189949286 зелёный. Гейт неослабления по
        методу: в голове не меньше 9 утверждений, потерь нет.

        Ловит мутацию: подготовка с `self.git` вынесена в помощник (учёт
        гейта по методу падает до 4, `LOST`); метод вычисляет
        `bare_old = old + 7` мимо генерации; помощник зовёт генерацию со
        своим зерном `random.randrange(…)`, а не с переданным; тест на зерне
        только вызывает помощник без подготовки.
        """
        st = Structure()
        self.assertFalse([n for n in ast.walk(st.method) if is_two_sided_run(n)],
                         "two_sided.run остался в методе")
        for func in (st.method, st.seed_test):
            with self.subTest(func=func.name):
                self.assertGreaterEqual(len(self_call_nodes(func, "git")), 5,
                                        "self.git меньше пяти")
                self.assertTrue(self_call_nodes(func, "checkout"), "нет self.checkout")
                self.assertTrue(st.same_seed(func, st.gen),
                                "генерация и помощник — не с одним зерном")
                names = derived_names(func, st.gen)
                self.assertTrue(names, "результат генерации не связан с именем")
                writes = [n for n in ast.walk(func) if isinstance(n, ast.Call)
                          and isinstance(n.func, ast.Attribute)
                          and n.func.attr in WRITE_CALLS
                          and any(isinstance(x, ast.Name) and x.id in names
                                  for x in ast.walk(n))]
                self.assertTrue(writes, "подготовка не пишет файлы из результата генерации")
                passed = " ".join(ast.unparse(e) if not isinstance(s, str) else f"{s}="
                                  + ast.unparse(e)
                                  for c in self_call_nodes(func, st.helper.name)
                                  for s, e in call_args(c))
                self.assertIn("base_sha", passed, "base_sha не передан помощнику")
                self.assertIn("branch", passed, "branch не передан помощнику")
                self.assertEqual([r for r in random_calls(func)
                                  if not r.startswith("random.randrange")], [],
                                 "литералы мимо генерации")
                self.assertEqual(arithmetic_on(func, names), [],
                                 "арифметика над результатом генерации")
        self.assertEqual(random_calls(st.helper), [], "помощник зовёт random/rng")
        self.assertEqual(arithmetic_on(st.helper, derived_names(st.helper, st.gen)), [],
                         "арифметика над результатом генерации в помощнике")

        _c, base_m = find_method(parse(base_source(TWO_SIDED)), METHOD)
        expected = assertion_texts(base_m)
        self.assertEqual(len(expected), 4, expected)
        self.assertEqual(missing(expected, assertion_texts(st.helper)), [],
                         "утверждения не дословно в помощнике")

        node = f"{TWO_SIDED}::{st.cls.name}::{st.seed_test.name}"
        run = run_pytest([node])
        self.assertEqual(run.code, 0, run.tail())
        self.assertTrue(run.passed(st.seed_test.name), run.tail())

        _base, head, lost = guard_assertions(TWO_SIDED)
        name = qualified(head or {}, METHOD, st.cls.name)
        self.assertIsNotNone(name, "гейт не видит метода")
        self.assertGreaterEqual(len(head[name]), 9, head[name])
        self.assertEqual(lost.get(name, []), [], "потери утверждений (LOST)")


if __name__ == "__main__":
    unittest.main()
