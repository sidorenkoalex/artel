"""Факты задачи CR-8, этап 1: тексты перенесённых констант против базы
84c784aa, несамодостаточная часть выкладки и блок раннеров остались в
`orchestrator.acceptance`, PLAN несёт результат поиска подмен и список
прогнанных файлов `tests/`.

Группа: разовый
Красен до реализации: модуля orchestrator.plank_layout нет (AC-3 падает на импорте), PLAN.md задачи ещё не написан (AC-8); AC-4 зелен с рождения — пять функций и блок раннеров сегодня определены в acceptance, тест держит, что перенос их не тронул.

База 84c784aa — коммит, с которым сверена SPEC («Сверено с origin/main
84c784aa»); исходник acceptance.py на ней читается `git show` в корне
рабочей копии (`_pult.CODE_ROOT`). PLAN.md — из ссылки документов задачи
помощником пульта `artifact_text`.
"""
import ast
import importlib
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, artifact_text  # noqa: E402

if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

BASE = "84c784aa"
CONSTANTS = ("PLANK_LAYOUT_DIR", "PLANK_LAYOUT_EXCLUDE", "LAYOUT_OUTSIDE_NOTE",
             "PLANK_ABSENT_NOTE", "NO_PLANK_LAYOUT", "LAYOUT_NOT_NORMAL",
             "LAYOUT_ID_NOT_LAST", "LAYOUT_OUTSIDE_WORKDIR",
             "LAYOUT_PARENT_NOT_HIDDEN", "LAYOUT_PARENT_TRACKED", "_LAYOUT_ID")
STAYING = ("_layout_ignore", "_layout_check", "_plank_plan",
           "_component_layout", "_laid_plank")
RUNNER_BLOCK = (37, 948)
CALLED_PRIVATE = ("_reported", "_own", "_full_suite_outcome", "_own_cwd",
                  "_own_target", "_place_command", "_place_env",
                  "_run_in_session", "_report_run",
                  "_report_suite_result_key", "_task_own_profile",
                  "_component_name", "_process_snapshot")


def base_source(rel: str) -> str:
    res = subprocess.run(["git", "-C", str(CODE_ROOT), "show",
                          f"{BASE}:{rel}"], capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError(f"git show {BASE}:{rel}: {res.stderr.strip()}")
    return res.stdout


def top_level_names(tree: ast.Module, first: int, last: int) -> list[str]:
    """Имена, которые определяют операторы верхнего уровня, начатые в
    строках first..last (def, class, присваивание имени)."""
    names = []
    for node in tree.body:
        start = node.decorator_list[0].lineno if getattr(
            node, "decorator_list", None) else node.lineno
        if not first <= start <= last:
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            names += [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target,
                                                            ast.Name):
            names.append(node.target.id)
    return names


class TaskFactsTest(unittest.TestCase):

    def test_ac3_constant_texts_match_base(self):
        """Тексты констант plank_layout и acceptance побайтно равны текстам на 84c784aa.

        Присваивания констант списка требования 1 берутся разбором
        `acceptance.py` базы и исполняются по порядку (`PLANK_LAYOUT_EXCLUDE`
        собран f-строкой от `PLANK_LAYOUT_DIR`); значение каждой — строка,
        равная `plank_layout.<имя>` и `acceptance.<имя>` в байтах UTF-8.

        Ловит мутацию: при переносе поправлена буква или пробел в тексте
        отказа (`LAYOUT_PARENT_TRACKED` без «git», склейка строк
        `NO_PLANK_LAYOUT` без пробела) — байты расходятся.
        """
        tree = ast.parse(base_source("orchestrator/acceptance.py"))
        namespace: dict = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id in CONSTANTS
                    for t in node.targets):
                exec(compile(ast.Module([node], []), "base", "exec"),
                     namespace)
        layout = importlib.import_module("orchestrator.plank_layout")
        acceptance = importlib.import_module("orchestrator.acceptance")
        for name in CONSTANTS:
            with self.subTest(name=name):
                self.assertIn(name, namespace, f"{name} нет на базе")
                want = namespace[name].encode("utf-8")
                self.assertEqual(getattr(layout, name).encode("utf-8"), want,
                                 f"plank_layout.{name}")
                self.assertEqual(getattr(acceptance, name).encode("utf-8"),
                                 want, f"acceptance.{name}")

    def test_ac4_non_selfcontained_layout_part_stays_in_acceptance(self):
        """Пять функций несамодостаточной части определены в orchestrator.acceptance.

        Ловит мутацию: `_plank_plan` или `_laid_plank` перенесены в
        plank_layout и реэкспортированы — `__module__` равен
        `orchestrator.plank_layout`; функция удалена — имени нет.
        """
        acceptance = importlib.import_module("orchestrator.acceptance")
        for name in STAYING:
            with self.subTest(name=name):
                self.assertTrue(hasattr(acceptance, name), f"{name} нет")
                self.assertEqual(getattr(acceptance, name).__module__,
                                 "orchestrator.acceptance", name)

    def test_ac4_runner_block_names_stay_in_acceptance(self):
        """Каждое имя верхнего уровня строк 37–948 acceptance.py базы осталось определённым в orchestrator.acceptance.

        Имена (def, class, присваивания) берутся разбором исходника базы
        84c784aa; у функций и классов `__module__` —
        `orchestrator.acceptance`, у прочих — имя есть в модуле.

        Ловит мутацию: заодно с выкладкой перенесён раннер (`_report_run`,
        `_own_cwd`, `_place_env`) в plank_layout или новый модуль с
        реэкспортом — `__module__` другой; имя раннера переименовано —
        имени нет.
        """
        tree = ast.parse(base_source("orchestrator/acceptance.py"))
        names = top_level_names(tree, *RUNNER_BLOCK)
        self.assertIn("_report_run", names, "разбор блока раннеров пуст")
        acceptance = importlib.import_module("orchestrator.acceptance")
        for name in names:
            with self.subTest(name=name):
                self.assertTrue(hasattr(acceptance, name), f"{name} нет")
                obj = getattr(acceptance, name)
                if isinstance(obj, type) or callable(obj) and hasattr(
                        obj, "__code__"):
                    self.assertEqual(obj.__module__, "orchestrator.acceptance",
                                     name)

    def test_ac8_plan_has_patch_search_and_tested_files(self):
        """PLAN.md называет четыре формы поиска подмен и файлы tests/ с подменой атрибутов orchestrator.acceptance.

        Формы требования 5 — `patch.object`, `mock.patch("orchestrator.
        acceptance.…")`, присваивание, `monkeypatch.setattr` — упомянуты в
        тексте PLAN. Файлы `tests/` дерева базы 84c784aa (SPEC сверена с
        ней; файлы, пришедшие позже подтяжкой main, не требуются), которые
        подменяют атрибуты модуля
        `orchestrator.acceptance` (разбор `ast`: `patch.object(<имя модуля>,
        …)`, `patch("orchestrator.acceptance.…")`, присваивание атрибуту
        модуля, `monkeypatch.setattr`), названы в PLAN по имени файла.

        Ловит мутацию: PLAN без раздела поиска (нет упоминания форм) или
        список прогнанных файлов неполон (пропущен файл с
        `mock.patch.object(acceptance, "subprocess", …)`) — имя файла не
        найдено в тексте PLAN.
        """
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md нет в ссылке документов")
        low = plan.lower()
        for label, signs in (
                ("mock.patch.object", ("patch.object",)),
                ("mock.patch(строка)", ("mock.patch(", 'patch("orchestrator',
                                        "patch('orchestrator",
                                        "patch(\"orchestrator.acceptance")),
                ("присваивание", ("присваива",)),
                ("monkeypatch.setattr", ("monkeypatch.setattr",))):
            with self.subTest(form=label):
                self.assertTrue(any(s in low for s in signs),
                                f"в PLAN не названа форма поиска {label}")
        files = patching_test_files()
        self.assertTrue(files, "разбор не нашёл ни одного файла с подменой")
        missing = [f for f in files if f not in plan]
        self.assertEqual(missing, [], "файлы tests/ с подменой атрибутов "
                         "orchestrator.acceptance не названы в PLAN")


def base_test_sources() -> dict[str, str]:
    """Имя файла -> текст каждого `tests/test_*.py` дерева базы 84c784aa
    (одним процессом `git cat-file --batch`): список фиксирован базой, файлы,
    пришедшие в ветку подтяжкой main позже, его не меняют."""
    res = subprocess.run(["git", "-C", str(CODE_ROOT), "ls-tree",
                          "--name-only", f"{BASE}:tests"],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError(f"git ls-tree {BASE}:tests: {res.stderr.strip()}")
    names = [n for n in res.stdout.splitlines()
             if n.startswith("test_") and n.endswith(".py")]
    request = "".join(f"{BASE}:tests/{n}\n" for n in names).encode()
    out = subprocess.run(["git", "-C", str(CODE_ROOT), "cat-file", "--batch"],
                         input=request, capture_output=True)
    if out.returncode != 0:
        raise AssertionError(f"git cat-file: {out.stderr.decode().strip()}")
    data, pos, sources = out.stdout, 0, {}
    for name in names:
        end = data.index(b"\n", pos)
        header = data[pos:end].split()
        size = int(header[2])
        sources[name] = data[end + 1:end + 1 + size].decode(
            "utf-8", errors="replace")
        pos = end + 1 + size + 1
    return sources


def patching_test_files() -> list[str]:
    """Имена файлов `tests/test_*.py` базы, подменяющих атрибут модуля
    `orchestrator.acceptance` хотя бы в одной из четырёх форм."""
    found = []
    for name, source in sorted(base_test_sources().items()):
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        acc = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == \
                    "orchestrator" and not node.level:
                acc |= {a.asname or a.name for a in node.names
                        if a.name == "acceptance"}
            elif isinstance(node, ast.Import):
                acc |= {a.asname for a in node.names
                        if a.name == "orchestrator.acceptance" and a.asname}

        def is_acc(expr) -> bool:
            if isinstance(expr, ast.Name):
                return expr.id in acc
            return (isinstance(expr, ast.Attribute)
                    and expr.attr == "acceptance"
                    and isinstance(expr.value, ast.Name)
                    and expr.value.id == "orchestrator")

        hit = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                attr = func.attr if isinstance(func, ast.Attribute) else \
                    getattr(func, "id", "")
                first = node.args[0] if node.args else None
                if attr in ("object", "setattr") and first is not None \
                        and is_acc(first):
                    hit = True
                elif attr in ("patch", "setattr") and isinstance(
                        first, ast.Constant) and isinstance(first.value, str) \
                        and first.value.startswith("orchestrator.acceptance."):
                    hit = True
            elif isinstance(node, (ast.Assign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) \
                    else [node.target]
                if any(isinstance(t, ast.Attribute) and is_acc(t.value)
                       for t in targets):
                    hit = True
            if hit:
                break
        if hit:
            found.append(name)
    return found


if __name__ == "__main__":
    unittest.main()
