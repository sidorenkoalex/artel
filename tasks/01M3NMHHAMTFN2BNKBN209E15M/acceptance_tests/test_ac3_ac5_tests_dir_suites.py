"""Сквозной тест разработчика в `tests/` и неослабление наборов
долгоживущих файлов (SPEC 01M3NMHHAMTFN2BNKBN209E15M, AC-3, AC-4, AC-5).

Группа: разовый
Красен до реализации: в tests/ кодовой ветки задачи ещё нет метода с заявкой «Ловит мутацию: трассируемость не читает долгоживущие файлы кодовой ветки — отказ «нет теста»» — поиск сквозного теста падает; проверка неослабления AC-3 зелена с рождения.

Разовый: предмет — дифф ветки задачи против её базы (`gitcmd.diff_base`):
какой файл `tests/` добавил разработчик и не ослаблены ли два соседних
набора. Чувствительность сквозного теста проверяется исполнением: файл
прогоняется в рабочей копии кодовой ветки как есть (обязан быть зелёным)
и под внесённой мутацией `scripts/guard.py` (обязан покраснеть). Мутация
вносится подменой атрибута модуля `scripts.guard` в процессе прогона —
`scripts/guard.py` в SPEC только для чтения, его имена стабильны; файлы
репозитория не правятся.
"""
import ast
import subprocess
import sys
import unittest
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CODE_ROOT))

from orchestrator import gitcmd  # noqa: E402

TASK_ID = "01M3NMHHAMTFN2BNKBN209E15M"
CLAIM = ("Ловит мутацию: трассируемость не читает долгоживущие файлы "
         "кодовой ветки — отказ «нет теста»")
KEPT_SUITES = ("tests/test_long_lived_manifest.py",
               "tests/test_long_lived_transitions.py")

# Мутация AC-4: трассируемость не видит текстов долгоживущих файлов — ни
# разбор разметки AC (`scan_ac_content`), ни дисковый путь
# (`acceptance_traceability_errors`) не получают файлов со строкой
# «Группа: долгоживущий».
MUTATION_TRACE = '''
_scan = guard.scan_ac_content
_errors = guard.acceptance_traceability_errors
def _is_long(src):
    return guard.plank_file_group(src)[0] == guard.GROUP_LONG_LIVED
guard.scan_ac_content = lambda sources: _scan(
    [s for s in sources if not _is_long(s)])
guard.acceptance_traceability_errors = (
    lambda tdir, extra_sources=(): _errors(tdir, ()))
'''

# Мутация AC-5: правило имени Р1 без префикса задачи — любой
# `tests/test_*.py` считается долгоживущим файлом задачи.
MUTATION_PREFIX = '''
guard.is_long_lived_test_path = lambda task_id, rel: (
    rel.startswith("tests/test_") and rel.endswith(".py"))
'''

HARNESS = '''
import sys
sys.path.insert(0, {root!r})
from scripts import guard
{mutation}
import pytest
# Сторож роли (`conftest.py`) сверяет аргументы-пути по `sys.argv`.
sys.argv = ["pytest", {paths}]
sys.exit(pytest.main([{paths}, "-q", "-p", "no:cacheprovider", "-x"]))
'''


def normalized(text: str) -> str:
    return " ".join(text.split())


def branch_and_base() -> tuple[str, str]:
    res = subprocess.run(["git", "-C", str(CODE_ROOT), "rev-parse",
                          "--abbrev-ref", "HEAD"], capture_output=True, text=True)
    branch = res.stdout.strip()
    if res.returncode != 0 or not branch.startswith(f"task/{TASK_ID.lower()}"):
        raise AssertionError(f"{CODE_ROOT} не на ветке задачи: {branch!r} "
                             f"{res.stderr}")
    base = gitcmd.diff_base(branch)
    if not base:
        raise AssertionError(f"база ветки {branch} не найдена")
    return branch, base


def claim_methods(source: str) -> list[str]:
    """Тестовые методы файла, в докстринге которых есть заявка AC-4
    (переносы строк докстринга не в счёт)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    return [node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test")
            and normalized(CLAIM) in normalized(ast.get_docstring(node) or "")]


def imports_sandbox(source: str) -> bool:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module == "tests.sandbox":
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "tests" and any(
                a.name == "sandbox" for a in node.names):
            return True
        if isinstance(node, ast.Import) and any(
                a.name == "tests.sandbox" for a in node.names):
            return True
    return False


def end_to_end_files() -> list[str]:
    """Файлы `tests/test_*.py`, добавленные или изменённые веткой задачи,
    с методом, несущим заявку AC-4."""
    branch, base = branch_and_base()
    entries = gitcmd.diff_name_status(base, branch, "tests") or []
    found = []
    for status, path, new_path in entries:
        rel = new_path or path
        if status[:1] == "D" or not Path(rel).name.startswith("test_"):
            continue
        if not rel.endswith(".py"):
            continue
        text, _ = gitcmd.show(branch, rel)
        if text and claim_methods(text):
            found.append(rel)
    return sorted(found)


def run_pytest(paths: list[str], mutation: str = "") -> subprocess.CompletedProcess:
    code = HARNESS.format(root=str(CODE_ROOT), mutation=mutation,
                          paths=", ".join(repr(p) for p in paths))
    return subprocess.run([sys.executable, "-c", code], cwd=CODE_ROOT,
                          capture_output=True, text=True, timeout=110)


def tail(res: subprocess.CompletedProcess) -> str:
    return (res.stdout + res.stderr)[-3000:]


class EndToEndTestInTestsDir(unittest.TestCase):

    def found(self) -> list[str]:
        files = end_to_end_files()
        self.assertTrue(files, "в tests/ ветки задачи нет теста с заявкой "
                               f"«{CLAIM}»")
        return files

    def test_ac4_end_to_end_test_on_sandbox_is_green(self):
        """Ветка задачи добавила в `tests/` сквозной тест на песочнице.

        Есть файл `tests/test_*.py` из диффа ветки с методом, несущим
        заявку AC-4 дословно; файл импортирует `tests.sandbox`; прогон
        файла в рабочей копии кодовой ветки зелёный.

        Ловит мутацию: сквозной тест не добавлен, заявка у метода
        перефразирована или тест красен на исправленном коде — поиск
        пуст либо прогон pytest завершается ненулевым кодом.
        """
        files = self.found()
        branch, _ = branch_and_base()
        for rel in files:
            text, _ = gitcmd.show(branch, rel)
            self.assertTrue(imports_sandbox(text),
                            f"{rel}: нет импорта tests/sandbox.py")
        res = run_pytest(files)
        self.assertEqual(res.returncode, 0, tail(res))

    def test_ac4_end_to_end_test_catches_traceability_mutation(self):
        """Под мутацией «трассируемость не читает долгоживущие файлы» (их
        тексты не доходят до разбора AC) сквозной тест краснеет провалом
        утверждения, а не ошибкой сбора.

        Ловит мутацию: сквозной тест не проверяет исход трассируемости
        (не сверяет `in_dev`/отсутствие отказа) — под мутацией он остаётся
        зелёным, код возврата прогона 0 вместо 1.
        """
        res = run_pytest(self.found(), MUTATION_TRACE)
        self.assertEqual(res.returncode, 1,
                         f"под мутацией трассируемости тест не покраснел "
                         f"провалом: {tail(res)}")

    def test_ac5_end_to_end_test_catches_prefix_mutation(self):
        """Второй сценарий сквозного теста — файл без префикса задачи: под
        мутацией правила имени (любой `tests/test_*.py` — «свой») сквозной
        тест краснеет провалом утверждения.

        Ловит мутацию: сценарий «файл без префикса остаётся в
        `tests_writing` с отказом» в сквозном тесте отсутствует — под
        мутацией прогон зелёный, код возврата 0 вместо 1.
        """
        res = run_pytest(self.found(), MUTATION_PREFIX)
        self.assertEqual(res.returncode, 1,
                         f"под мутацией правила имени тест не покраснел "
                         f"провалом: {tail(res)}")


class KeptSuitesNotWeakened(unittest.TestCase):

    def test_ac3_long_lived_suites_not_weakened_and_green(self):
        """`tests/test_long_lived_manifest.py` и
        `tests/test_long_lived_transitions.py` на голове ветки несут каждый
        тестовый метод базы ветки и проходят.

        Ловит мутацию: разработчик удалил или переименовал метод одного из
        наборов (либо набор красен на исправленном коде) — метод базы
        пропал из головы ветки или прогон pytest ненулевой.
        """
        branch, base = branch_and_base()
        for rel in KEPT_SUITES:
            with self.subTest(suite=rel):
                old, reason = gitcmd.show(base, rel)
                self.assertIsNotNone(old, f"{rel} нет в базе: {reason}")
                new, reason = gitcmd.show(branch, rel)
                self.assertIsNotNone(new, f"{rel} нет на голове: {reason}")
                missing = sorted(set(self.methods(old)) - set(self.methods(new)))
                self.assertEqual(missing, [], f"{rel}: пропали методы базы")
        res = run_pytest(list(KEPT_SUITES))
        self.assertEqual(res.returncode, 0, tail(res))

    @staticmethod
    def methods(source: str) -> list[str]:
        return [f"{cls.name}.{fn.name}"
                for cls in ast.walk(ast.parse(source))
                if isinstance(cls, ast.ClassDef)
                for fn in cls.body
                if isinstance(fn, ast.FunctionDef) and fn.name.startswith("test")]


if __name__ == "__main__":
    unittest.main()
