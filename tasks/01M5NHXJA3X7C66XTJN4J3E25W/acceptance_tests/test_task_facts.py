"""Факты задачи: приложения PLAN.md перенесены без изменений, новый файл тестов в стиле pytest, ветка не трогает существующее в tests/ и защищённые пути.

Группа: разовый
Красен до реализации: PLAN.md с приложениями ещё не написан — `artifact_text("PLAN.md")` отдаёт None (AC-1); до прогона долгоживущий файл задачи уже лежит в tests/ неотслеживаемым, поэтому AC-5 и AC-6 зелёные с рождения и держат стиль и границы ветки до мержа.

Артефакты (PLAN.md, TZ.md, SPEC.md) читаются только помощником пульта
`artifact_text`; пути задачи — `changed_paths()`, база — `DIFF_BASE`.
"""
import ast
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE, artifact_text, changed_paths  # noqa: E402

from orchestrator import config  # noqa: E402
from scripts import guard  # noqa: E402

FROM_TZ = ("conftest.py", "skills/test-authoring.md", "skills/review-checklist.md")
FROM_SPEC = ("tests/test_invariants.py", "docs/invariants.md")
DIFF_BLOCK = re.compile(r"^```diff[ \t]*\n(.*?)^```[ \t]*$", re.S | re.M)
DIFF_GIT = re.compile(r"^diff --git a/(\S+) b/", re.M)
TESTCASE_BASES = ("TestCase", "Test", "Sandbox")


def _git(*args, index=None):
    env = dict(os.environ)
    if index:
        env["GIT_INDEX_FILE"] = index
    return subprocess.run(["git", "-C", CODE_ROOT, *args], env=env,
                          capture_output=True, text=True)


def _blocks_for(text, paths):
    """Блоки ```diff текста, все заголовки `diff --git` которых — в `paths`."""
    out = []
    for block in DIFF_BLOCK.findall(text):
        heads = DIFF_GIT.findall(block)
        if heads and all(h in paths for h in heads):
            out.append(block)
    return out


def _blobs_after(diffs, paths):
    """{путь: sha блоба} после наложения `diffs` по порядку на дерево HEAD
    во временном индексе; ошибка наложения — (None, ответ git)."""
    with tempfile.TemporaryDirectory(prefix="ac1-") as tmp:
        index = str(Path(tmp) / "index")
        res = _git("read-tree", "HEAD", index=index)
        if res.returncode:
            return None, res.stderr
        for n, diff in enumerate(diffs):
            patch = Path(tmp) / f"{n}.diff"
            patch.write_text(diff, encoding="utf-8")
            res = _git("apply", "--cached", str(patch), index=index)
            if res.returncode:
                return None, f"блок {n}: {res.stderr}\n{diff[:200]}"
        tree = _git("write-tree", index=index).stdout.strip()
        blobs = {}
        for path in paths:
            res = _git("rev-parse", f"{tree}:{path}")
            blobs[path] = res.stdout.strip() if res.returncode == 0 else None
        return blobs, ""


def _new_test_files():
    return [p for p in changed_paths()
            if p.startswith("tests/") and Path(p).name.startswith("test_")
            and p.endswith(".py") and (Path(CODE_ROOT) / p).is_file()]


class TaskFactsTest(unittest.TestCase):

    def test_ac1_plan_appendices_equal_tz_and_spec_texts(self):
        """Приложения PLAN.md дают на базе ветки те же пять файлов, что тексты ТЗ (1–3) и SPEC (4–5).

        На дереве HEAD рабочей копии во временном индексе по очереди
        накладываются приложения PLAN.md (разбор `guard.plan_appendices`,
        тот же, что у пульта) и — отдельно — блоки ```diff Приложений 1–3
        TZ.md (`conftest.py`, `skills/test-authoring.md`,
        `skills/review-checklist.md`) и Приложений 4–5 SPEC.md
        (`tests/test_invariants.py`, `docs/invariants.md`); содержимое
        каждого из пяти файлов в двух деревьях совпадает.

        Ловит мутацию: в PLAN.md перенесено Приложение 4 из ТЗ вместо
        заменившего его текста SPEC, пропущено Приложение 5 или в
        приложение внесена своя правка строки — sha блоба файла в дереве
        PLAN расходится с деревом эталона.
        """
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md задачи нет в ссылке документов")
        appendices, errors = guard.plan_appendices(plan)
        self.assertEqual(errors, [], "ошибки разбора приложений PLAN.md")
        touched = {p for a in appendices for p in a.paths}
        paths = FROM_TZ + FROM_SPEC
        for path in paths:
            self.assertIn(path, touched, f"PLAN.md: нет приложения к {path}")
        tz = _blocks_for(artifact_text("TZ.md") or "", FROM_TZ)
        spec = _blocks_for(artifact_text("SPEC.md") or "", FROM_SPEC)
        self.assertEqual(len(tz), 3, "в TZ.md не найдены Приложения 1–3")
        self.assertEqual(len(spec), 2, "в SPEC.md не найдены Приложения 4–5")
        expected, why = _blobs_after(tz + spec, paths)
        self.assertIsNotNone(expected, f"эталон не накладывается на HEAD: {why}")
        actual, why = _blobs_after([a.diff for a in appendices], paths)
        self.assertIsNotNone(actual, f"приложения PLAN не накладываются: {why}")
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(actual[path], expected[path], path)

    def test_ac5_new_tests_file_in_pytest_style(self):
        """Новый файл тестов задачи в `tests/` — функции модуля без классов TestCase, у каждой «Ловит мутацию:».

        Среди путей задачи (`changed_paths()`) есть хотя бы один новый
        `tests/test_*.py`; в каждом таком файле есть тестовые функции
        уровня модуля, нет классов-наследников `TestCase`/песочниц и
        классов с методами `test_*`, а докстринг каждой функции `test_*`
        модуля несёт «Ловит мутацию:».

        Ловит мутацию: тесты задачи написаны классом `unittest.TestCase`
        (или наследником `TmpRootTest`), либо у одной из функций нет строки
        «Ловит мутацию:» — найден класс или функция без заявки.
        """
        files = _new_test_files()
        self.assertTrue(files, "в tests/ нет нового файла тестов задачи")
        for rel in files:
            with self.subTest(file=rel):
                tree = ast.parse((Path(CODE_ROOT) / rel).read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if not isinstance(node, ast.ClassDef):
                        continue
                    bases = [ast.unparse(b) for b in node.bases]
                    self.assertFalse(
                        any(b.endswith(TESTCASE_BASES) for b in bases),
                        f"{rel}: класс {node.name}({', '.join(bases)})")
                    self.assertFalse(
                        any(isinstance(m, ast.FunctionDef) and m.name.startswith("test")
                            for m in node.body), f"{rel}: тесты в классе {node.name}")
                funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                         and n.name.startswith("test")]
                self.assertTrue(funcs, f"{rel}: нет тестовых функций модуля")
                for func in funcs:
                    self.assertIn("Ловит мутацию:", ast.get_docstring(func) or "",
                                  f"{rel}::{func.name}")

    def test_ac6_branch_adds_only_new_tests_and_no_protected_paths(self):
        """Ветка добавляет в `tests/` только новые файлы и не меняет ни одного защищённого пути.

        Каждый путь задачи (`changed_paths()`: закоммиченный дифф от
        `DIFF_BASE` плюс неотслеживаемые) вне перечня
        `config.PROTECTED_PATHS` (формула `config.is_protected_path`), а
        каждый путь под `tests/` отсутствовал в дереве базы — новый файл,
        не правка, не переименование и не удаление существующего.

        Ловит мутацию: разработчик правит `conftest.py` или
        `tests/test_invariants.py` коммитом ветки вместо приложения PLAN, либо
        дописывает тест в существующий `tests/test_*.py` — путь найден
        защищённым или существующим в базе.
        """
        self.assertTrue(DIFF_BASE, "база диффа не определена при выкладке")
        paths = changed_paths()
        for path in paths:
            with self.subTest(path=path):
                self.assertFalse(config.is_protected_path(path),
                                 f"защищённый путь в ветке: {path}")
                if path.startswith("tests/"):
                    res = _git("cat-file", "-e", f"{DIFF_BASE}:{path}")
                    self.assertNotEqual(res.returncode, 0,
                                        f"существующий файл tests/ изменён: {path}")


if __name__ == "__main__":
    unittest.main()
