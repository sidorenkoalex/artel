"""AC-2: перенос дословно, помощники с утверждениями на первом уровне, докстринги методов разбиения.

Группа: разовый
Красен до реализации: методов-долей ещё нет — у старых имён перечней нет второй доли, а докстринги `test_ac3_*`/`test_ac6_*` базы без «Сценарий»; тесты переноса литералов и помощников зелены на базе (голова равна базе) и держат перенос после правки.

Стороны: база — `_pult.DIFF_BASE`, голова — рабочая копия кода; методы-доли
определяются прогоном с заглушками (`_split.share_methods`).
"""
import ast
import collections
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _split as S  # noqa: E402

PREPARATION_CLASSES = {"OutcomeGateSandbox", "ProfileCallersSandbox",
                       "SpecAuditSandbox", "PytestOwnProjectTest"}


def string_constants(node, skip_docstring=True) -> collections.Counter:
    doc = None
    if skip_docstring and node.body and isinstance(node.body[0], ast.Expr) and \
            isinstance(node.body[0].value, ast.Constant):
        doc = node.body[0].value
    return collections.Counter(n.value for n in ast.walk(node)
                               if isinstance(n, ast.Constant) and isinstance(n.value, str)
                               and n is not doc)


def body_dump(func) -> tuple:
    body = func.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    return tuple(ast.dump(node) for node in body)


class TransferTest(unittest.TestCase):

    def test_ac2_every_split_method_docstring_has_scenario_and_mutation(self):
        """У каждого метода со старым именем и каждого нового метода файла зоны докстринг несёт «Сценарий» и «Ловит мутацию:» с текстом.

        Сценарий: кандидаты четырёх файлов головы (старые имена и все
        тестовые методы, которых нет на базе); докстринг каждого содержит
        слово «Сценарий» и строку «Ловит мутацию:», за которой непустой
        текст.

        Ловит мутацию: новый метод доли получил однострочный докстринг без
        «Ловит мутацию:» — метод назван.
        """
        for rel in S.ZONE:
            funcs = S.qualified(S.head_text(rel))
            for name in S.candidates(rel):
                with self.subTest(file=rel, method=name):
                    doc = S.docstring(funcs[name])
                    self.assertIn("Сценарий", doc)
                    self.assertRegex(doc, r"Ловит мутацию:\s*\S")

    def test_ac2_share_docstring_carries_original_text_whole(self):
        """Докстринг каждого метода-доли несёт исходный докстринг разбитого метода целиком.

        Сценарий: для перечней `places` (оба `test_ac10_*`), `PLACES` (оба
        `test_ac3_*` и `test_ac6_*`) и категорий `test_ac9` методы-доли
        определяются прогоном с заглушками; докстринг базы исходного метода
        (пробелы нормализованы) — подстрока докстринга каждого метода его
        долей; у каждого перечня есть хотя бы одна доля помимо старого имени.

        Ловит мутацию: в докстринге доли оставлен только «Ловит мутацию»
        без исходного «Сценария» (или наоборот) — исходный текст не входит
        целиком.
        """
        groups = S.share_methods()
        for old, members in groups.items():
            rel = next(r for r, names in S.SPLIT.items() if old in names)
            base_doc = S.norm(S.docstring(S.qualified(S.base_text(rel))[old]))
            head = S.qualified(S.head_text(rel))
            with self.subTest(old=old):
                self.assertTrue([m for m in members if m != old],
                                f"у {old} нет методов-долей: {members}")
                for member in members:
                    self.assertIn(base_doc, S.norm(S.docstring(head[member])), member)

    def test_ac2_subcase_texts_kept_verbatim(self):
        """Строковые литералы тела каждого разбиваемого метода базы есть в файле головы не реже, чем в теле на базе.

        Сценарий: для каждого из двенадцати методов перечня — мультимножество
        строковых констант тела базы без докстринга (метки подслучаев,
        тексты сообщений, части f-строк); каждая константа встречается в
        тексте файла головы хотя бы столько раз, сколько в теле на базе.

        Ловит мутацию: метка подслучая «база нет записи» при переносе
        переписана как «нет записи базы» — литерала прежнего текста в
        голове нет.
        """
        for rel, old in S.ALL_SPLIT:
            body = string_constants(S.qualified(S.base_text(rel))[old])
            head = string_constants(ast.parse(S.head_text(rel)), skip_docstring=False)
            with self.subTest(method=old):
                lost = {text: n for text, n in body.items() if head[text] < n}
                self.assertEqual(lost, {})

    def test_ac2_new_helpers_carry_no_assertions(self):
        """Новый вспомогательный метод — только подготовка: без утверждений, без вызова помощников с утверждениями, не в классе подготовки.

        Сценарий: нетестовые функции и методы файлов зоны, которых нет на
        базе (кроме переименованного без правки тела — `tests_dir`, AC-5).
        У каждого `guard` не находит своих утверждений; в его теле
        (вместе с вложенными функциями) нет вызова `self.<метод>` или
        функции, у которых на голове файла или `tests/sandbox.py` есть
        утверждения; класс помощника — не класс подготовки
        (`OutcomeGateSandbox` и т. п., а также любой класс, от которого
        наследуют другие классы файла).

        Ловит мутацию: общий помощник доли `run_share(self, share)` зовёт
        `self.check_home(...)` — вызов помощника с утверждениями ушёл на
        второй уровень и снят с учёта; помощник подготовки добавлен в
        `OutcomeGateSandbox`.
        """
        sandbox = S.head_text(S.SANDBOX)
        for rel in S.ZONE:
            head, base = S.head_text(rel), S.base_text(rel)
            methods, functions = S.helper_assertion_names(head)
            more_m, more_f = S.helper_assertion_names(sandbox)
            methods, functions = methods | more_m, functions | more_f
            own = S.guard._helper_keys(head)
            preparation = PREPARATION_CLASSES | S.base_classes_in_file(head)
            head_helpers, base_helpers = S.helpers_of(head), S.helpers_of(base)
            gone = {body_dump(base_helpers[k]) for k in set(base_helpers) - set(head_helpers)}
            # Переименованный без правки тела помощник (`tests_dir`, AC-5) — не новый.
            fresh = {k for k in set(head_helpers) - set(base_helpers)
                     if body_dump(head_helpers[k]) not in gone}
            for key in sorted(fresh, key=str):
                node = S.helpers_of(head)[key]
                with self.subTest(file=rel, helper=key):
                    self.assertEqual(own.get(key, []), [], "утверждения в помощнике")
                    self.assertEqual(S.asserting_calls(node, methods, functions), [])
                    self.assertNotIn(key[0], preparation, "помощник в классе подготовки")

    def test_ac2_existing_helpers_gain_no_asserting_calls(self):
        """Прежние помощники файлов зоны не получают новых вызовов помощников с утверждениями.

        Сценарий: для каждой нетестовой функции и метода, которые есть и на
        базе, и на голове, мультимножество вызовов помощников с
        утверждениями (`self.<метод>`/функция модуля и `tests/sandbox.py`)
        на голове не больше, чем на базе.

        Ловит мутацию: `check_places` получил вызов `self.assert_own(...)`
        из бывшего тела метода — утверждение ушло во второй уровень учёта.
        """
        for rel in S.ZONE:
            sides = {}
            for side, text, sandbox in (("base", S.base_text(rel), S.base_text(S.SANDBOX)),
                                        ("head", S.head_text(rel), S.head_text(S.SANDBOX))):
                m1, f1 = S.helper_assertion_names(text)
                m2, f2 = S.helper_assertion_names(sandbox)
                sides[side] = {key: collections.Counter(S.asserting_calls(node, m1 | m2, f1 | f2))
                               for key, node in S.helpers_of(text).items()}
            for key in sorted(set(sides["base"]) & set(sides["head"]), key=str):
                with self.subTest(file=rel, helper=key):
                    grown = sides["head"][key] - sides["base"][key]
                    self.assertEqual(dict(grown), {})


if __name__ == "__main__":
    unittest.main()
