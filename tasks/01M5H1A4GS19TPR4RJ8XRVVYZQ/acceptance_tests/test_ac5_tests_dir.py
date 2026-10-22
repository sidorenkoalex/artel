"""AC-5: `tests_dir` переименован во всех местах вызова и больше не собирается pytest.

Группа: разовый
Красен до реализации: метод `tests_dir` ещё на месте — его имя есть в файле головы, pytest собирает `::tests_dir` в 13 классах.
"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _split as S  # noqa: E402

OLD = "tests_dir"


def body_dump(func) -> list:
    body = func.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    return [ast.dump(node) for node in body]


def self_calls(text, name) -> int:
    return sum(1 for n in ast.walk(ast.parse(text)) if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Attribute) and n.func.attr == name
               and isinstance(n.func.value, ast.Name) and n.func.value.id == "self")


class TestsDirTest(unittest.TestCase):

    def test_ac5_tests_dir_renamed_in_every_call(self):
        """Имени `tests_dir` в файле нет; тот же метод под именем не на `test` зовётся столько же раз.

        Сценарий: в голове profile_callers нет ни определения, ни атрибута,
        ни имени `tests_dir`; в `ProfileCallersSandbox` есть метод с телом
        прежнего `tests_dir` (без докстринга, по AST), его имя не начинается
        с `test`, а вызовов `self.<новое имя>(…)` в файле столько же,
        сколько было `self.tests_dir(…)` на базе.

        Ловит мутацию: метод переименован, а один из трёх вызовов оставлен
        `self.tests_dir()` — имя `tests_dir` в файле; переименован в
        `test_root` — имя на `test`.
        """
        head, base = S.head_text(S.PROFILE), S.base_text(S.PROFILE)
        names = [getattr(n, "name", None) or getattr(n, "attr", None) or getattr(n, "id", None)
                 for n in ast.walk(ast.parse(head))
                 if isinstance(n, (ast.FunctionDef, ast.Attribute, ast.Name))]
        self.assertFalse(OLD in names, f"имя {OLD} осталось в файле головы")
        old = next(f for f in S.class_defs(base)["ProfileCallersSandbox"].body
                   if isinstance(f, ast.FunctionDef) and f.name == OLD)
        same = [f.name for f in S.class_defs(head)["ProfileCallersSandbox"].body
                if isinstance(f, ast.FunctionDef) and body_dump(f) == body_dump(old)]
        self.assertEqual(len(same), 1, same)
        self.assertFalse(same[0].startswith("test"), same[0])
        self.assertEqual(self_calls(head, same[0]), self_calls(base, OLD))

    def test_ac5_not_collected_in_any_class(self):
        """pytest не собирает `tests_dir` и любой другой нетестовый `test*` ни в одном из 13 классов.

        Сценарий: сбор `--collect-only` файла головы во временном пакете
        `tests`; ни один nodeid не кончается на `::tests_dir`, а у каждого
        собранного элемента классов-наследников `ProfileCallersSandbox` (и
        его самого) имя метода начинается с `test_`.

        Ловит мутацию: метод переименован в `tests_root` — имя снова на
        `test`, pytest собирает его в 13 классах.
        """
        items = S.collect({S.PROFILE: S.head_text(S.PROFILE)})
        self.assertTrue(items)
        for item in items:
            with self.subTest(item=item):
                self.assertFalse(item.endswith("::" + OLD))
                self.assertTrue(item.rsplit("::", 1)[1].startswith("test_"), item)


if __name__ == "__main__":
    unittest.main()
