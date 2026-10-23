"""AC-9: тесты задачи — новый файл `tests/` в стиле pytest; существующие файлы `tests/` не тронуты.

Группа: разовый
Красен до реализации: модуля tests/fixtures.py нет в диффе ветки — явный импорт фикстур тестов задачи указывает на отсутствующий новый модуль.

Факт этой задачи — состав диффа ветки от базы (`_pult.changed_paths`,
`_pult.DIFF_BASE`): после мержа его проверять не на чем. Файл тестов задачи
ищется среди НОВЫХ файлов `tests/test_*.py` диффа и разбирается `ast`.
"""
import ast
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE, changed_paths  # noqa: E402

COVERED = range(2, 9)  # AC-2…AC-8
MUTATION_CLAIM = "Ловит мутацию:"


def existed_at_base(path: str) -> bool:
    """Путь был в дереве базы диффа — файл не новый."""
    res = subprocess.run(["git", "-C", CODE_ROOT, "cat-file", "-e",
                          f"{DIFF_BASE}:{path}"], capture_output=True)
    return res.returncode == 0


def new_tests_paths() -> list:
    return [p for p in changed_paths()
            if p.startswith("tests/") and not existed_at_base(p)]


def style_problems(source: str) -> list:
    """Расхождения файла с формой AC-9; пусто — файл в стиле pytest."""
    tree = ast.parse(source)
    problems = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and any(
                "TestCase" in ast.unparse(base) for base in node.bases):
            problems.append(f"класс unittest.TestCase {node.name}")
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name.startswith("test_")]
    if not funcs:
        problems.append("нет тестовых функций верхнего уровня")
    for func in funcs:
        if MUTATION_CLAIM not in (ast.get_docstring(func) or ""):
            problems.append(f"{func.name} без «{MUTATION_CLAIM}»")
    if "parametrize" not in source:
        problems.append("нет parametrize")
    imports_fixtures = any(
        isinstance(n, ast.ImportFrom) and n.module == "tests.fixtures"
        or isinstance(n, ast.ImportFrom) and n.module == "tests"
        and any(a.name == "fixtures" for a in n.names)
        or isinstance(n, ast.Import)
        and any(a.name == "tests.fixtures" for a in n.names)
        for n in ast.walk(tree))
    if not imports_fixtures:
        problems.append("фикстуры не импортированы из tests.fixtures явно")
    names = {f.name for f in funcs}
    missing = [n for n in COVERED
               if not any(re.match(rf"test_ac{n}_", name) for name in names)]
    if missing:
        problems.append(f"нет тестов AC-{', AC-'.join(map(str, missing))}")
    return problems


class TaskTestsFileTest(unittest.TestCase):

    def test_ac9_existing_tests_untouched(self):
        """Ни `tests/sandbox.py`, ни другой файл `tests/`, бывший в базе, не изменён, не удалён и не переименован.

        Ловит мутацию: разработчик правит `tests/sandbox.py` (например,
        добавляет фабрику фикстур туда) или существующий тест — путь
        появляется в диффе ветки, бывший в базе, тест краснеет.
        """
        touched = [p for p in changed_paths()
                   if p.startswith("tests/") and existed_at_base(p)]
        self.assertEqual(touched, [], f"существующие файлы tests/ изменены: {touched}")

    def test_ac9_new_pytest_style_file_covers_criteria(self):
        """Среди новых файлов `tests/` есть файл тестов в стиле pytest, покрывающий AC-2…AC-8, а `tests/fixtures.py` — новый модуль.

        Файл: тестовые функции верхнего уровня (не `unittest.TestCase`), с
        `parametrize`, у каждой функции строка «Ловит мутацию:», явный импорт
        из `tests.fixtures`, функции `test_ac<n>_` для AC-2…AC-8.

        Ловит мутацию: тесты задачи написаны классом `unittest.TestCase`
        или без явного импорта `tests.fixtures` (опора на корневой
        `conftest.py`) — ни один новый файл не проходит разбор, тест
        краснеет; модуль `tests/fixtures.py` не заведён — тоже.
        """
        new = new_tests_paths()
        self.assertIn("tests/fixtures.py", new, f"новые файлы tests/: {new}")
        report = {}
        for path in new:
            if not re.fullmatch(r"tests/test_\w+\.py", path):
                continue
            source = (Path(CODE_ROOT) / path).read_text(encoding="utf-8")
            report[path] = style_problems(source)
            if not report[path]:
                return
        self.fail(f"нет нового файла tests/ в стиле AC-9: {report}")


if __name__ == "__main__":
    unittest.main()
