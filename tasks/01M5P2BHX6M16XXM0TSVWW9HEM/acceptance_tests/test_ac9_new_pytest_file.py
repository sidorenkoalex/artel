"""AC-9: тесты AC-1–AC-8 — в новом файле `tests/` в стиле pytest, у каждой функции «Ловит мутацию:».

Группа: разовый
Зелёный с рождения: долгоживущий файл `tests/test_<id>_mutation_run_table.py` с функциями `test_ac1_…`–`test_ac8_…` пишет сама планка (test_author) и пульт коммитит его в ветку задачи; тест краснеет, если файл тронут так, что свойство пропадёт.

Факт этой задачи: новый файл ищется среди путей диффа задачи
(`changed_paths()` помощника пульта) — файл `tests/test_*.py`, которого нет
в дереве базы диффа (`DIFF_BASE`).
"""
import ast
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE, changed_paths  # noqa: E402

CLAIM = "Ловит мутацию:"


def new_test_files() -> list:
    """Файлы `tests/test_*.py` диффа задачи, которых нет в дереве базы."""
    found = []
    for rel in changed_paths():
        name = rel.rsplit("/", 1)[-1]
        if not rel.startswith("tests/") or "/" in rel[len("tests/"):] \
                or not name.startswith("test_") or not name.endswith(".py"):
            continue
        if not (Path(CODE_ROOT) / rel).is_file():
            continue
        res = subprocess.run(["git", "-C", str(CODE_ROOT), "cat-file", "-e",
                              f"{DIFF_BASE}:{rel}"], capture_output=True)
        if res.returncode != 0:
            found.append(rel)
    return found


def ac_functions(tree: ast.Module) -> dict:
    """{номер AC: [имена]} — функции модуля `test_ac<n>_…` для n от 1 до 8."""
    found = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for n in range(1, 9):
                if node.name.startswith(f"test_ac{n}_"):
                    found.setdefault(n, []).append(node.name)
    return found


def test_ac9_new_pytest_file_holds_ac1_to_ac8_with_mutation_claims():
    """Среди новых файлов `tests/` задачи есть pytest-файл с тестами AC-1–AC-8, у каждой функции — заявка мутации.

    Сценарий: новые файлы `tests/test_*.py` диффа задачи разбираются `ast`.
    Хотя бы один несёт функции уровня модуля `test_ac1_…`–`test_ac8_…`
    (стиль pytest — не методы класса `unittest.TestCase`), ни одного класса
    `TestCase` в нём нет, и у каждой функции `test_*` этого файла в
    докстринге есть «Ловит мутацию:».

    Ловит мутацию: разработчик переносит тесты в существующий файл `tests/`
    — нового файла с ними нет; тесты оформлены методами класса unittest —
    функций уровня модуля нет; у одной из функций заявка заменена на
    «Зелёный с рождения: …» или отсутствует.
    """
    candidates = new_test_files()
    assert candidates, "в диффе задачи нет новых файлов tests/test_*.py"
    reports = []
    for rel in candidates:
        tree = ast.parse((Path(CODE_ROOT) / rel).read_text(encoding="utf-8"))
        found = ac_functions(tree)
        missing = [n for n in range(1, 9) if n not in found]
        if missing:
            reports.append(f"{rel}: нет функций AC {missing}")
            continue
        unittest_classes = [
            node.name for node in tree.body if isinstance(node, ast.ClassDef)
            and any(isinstance(b, ast.Attribute) and b.attr == "TestCase"
                    or isinstance(b, ast.Name) and b.id == "TestCase"
                    for b in node.bases)]
        no_claim = [
            node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
            and CLAIM not in (ast.get_docstring(node) or "")]
        if not unittest_classes and not no_claim:
            return
        reports.append(f"{rel}: классы TestCase {unittest_classes}; "
                       f"функции без «{CLAIM}» {no_claim}")
    raise AssertionError("нет нового pytest-файла с тестами AC-1–AC-8: "
                         + "; ".join(reports))
