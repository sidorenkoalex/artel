"""Задача добавляет один новый файл долгоживущих тестов нужной формы и ничего больше не меняет, кроме карты кода (AC-6).

Группа: разовый
Зелёный с рождения: долгоживущий файл задачи пишет test_author шагом `tests_writing` (он покрывает AC-1..AC-5), код пульта не меняется; тест держит, что дальше задача не тронет код пульта и чужие файлы `tests/`, а файл сохранит форму и время.

Дифф задачи — `changed_paths()`/`DIFF_BASE` помощника пульта `_pult.py`;
форма файла — разбор его текста (`ast`) и импорт модуля из рабочей копии;
время — отдельный прогон файла pytest с `--durations=0`.
"""
import ast
import importlib
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE, TASK_ID, changed_paths  # noqa: E402

PREFIX = f"tests/test_{TASK_ID.lower()}_"
MAP = "docs/codebase-map.md"
ALLOWED_PATCHES = ("Popen", "ensure_head_in_origin", "ensure_draft_mr",
                   "preflight_checks")
LIMIT_S = 15.0


def new_files() -> list[str]:
    return sorted(p for p in changed_paths()
                  if p.startswith(PREFIX) and p.endswith(".py"))


class Ac6SingleNewFileTest(unittest.TestCase):

    def the_file(self) -> str:
        found = new_files()
        self.assertEqual(len(found), 1, f"файлы с префиксом {PREFIX}: {found}")
        rel = found[0]
        self.assertRegex(rel[len(PREFIX):], r"^[a-z0-9_]+\.py$", rel)
        return rel

    def test_ac6_only_new_file_and_map_changed(self):
        """Дифф задачи — один новый файл `tests/test_<id>_<имя>.py` и, возможно, карта кода; больше ничего.

        Сценарий: пути задачи правилом гейта зон (`changed_paths()`) без
        нового файла и `docs/codebase-map.md` пусты; новый файл отсутствует
        в дереве базы диффа.

        Ловит мутацию: разработчик правит код пульта (`orchestrator/`,
        `scripts/`) или существующий тест (`tests/sandbox.py`, файлы
        `AmendSandbox`/`ReplacedSandbox`) — путь появляется в диффе.
        """
        rel = self.the_file()
        extra = sorted(set(changed_paths()) - {rel, MAP})
        self.assertEqual(extra, [], f"лишние пути диффа: {extra}")
        if DIFF_BASE:
            res = subprocess.run(["git", "-C", CODE_ROOT, "cat-file", "-e",
                                  f"{DIFF_BASE}:{rel}"], capture_output=True)
            self.assertNotEqual(res.returncode, 0,
                                f"{rel} есть в базе {DIFF_BASE} — файл не новый")

    def test_ac6_file_form(self):
        """Файл: «Группа: долгоживущий», «Зелёный с рождения», у каждого теста «Сценарий» и «Ловит мутацию:», тесты AC-1..AC-5, только разрешённые подмены, настоящий git.

        Сценарий: разбор текста нового файла — строки модульного докстринга,
        докстринги методов `test_*`, наличие метода `test_ac<n>_…` для
        n = 1..5, вызовы `patch`/`patch.object` только на `Popen`,
        `ensure_head_in_origin`, `ensure_draft_mr`, `preflight_checks`;
        импорт модуля — каждый его класс с тестами наследует
        `tests.sandbox.GitignoreCommittedRealGitSandbox`.

        Ловит мутацию: тест без «Ловит мутацию:» или «Сценарий»; подмена
        функции `amend`/`fsm`/`guard` (`patch.object(amend, "_task_profile",
        …)`); песочница без настоящего git (`LightTransitionSandbox`);
        критерий без теста.
        """
        rel = self.the_file()
        text = (Path(CODE_ROOT) / rel).read_text(encoding="utf-8")
        tree = ast.parse(text)
        doc = ast.get_docstring(tree) or ""
        self.assertIn("Группа: долгоживущий", doc.splitlines(), rel)
        self.assertIn("Зелёный с рождения:", doc, rel)
        tests = [node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef)
                 and node.name.startswith("test_")]
        for node in tests:
            body = ast.get_docstring(node) or ""
            with self.subTest(test=node.name):
                self.assertIn("Сценарий", body)
                self.assertIn("Ловит мутацию:", body)
        for n in range(1, 6):
            self.assertTrue(any(node.name.startswith(f"test_ac{n}_")
                                for node in tests), f"нет test_ac{n}_… в {rel}")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = ast.unparse(node.func)
            if not re.search(r"(^|\.)patch(\.object)?$", name):
                continue
            target = ast.unparse(node.args[1] if name.endswith(".object")
                                 and len(node.args) > 1 else
                                 node.args[0] if node.args else node)
            with self.subTest(patch=ast.unparse(node)[:80]):
                self.assertTrue(any(a in target for a in ALLOWED_PATCHES),
                                f"подмена вне перечня: {target}")
        if CODE_ROOT not in sys.path:
            sys.path.insert(0, CODE_ROOT)
        sandbox = importlib.import_module("tests.sandbox")
        module = importlib.import_module(rel[:-3].replace("/", "."))
        classes = [obj for obj in vars(module).values()
                   if isinstance(obj, type) and issubclass(obj, unittest.TestCase)
                   and any(k.startswith("test_") for k in dir(obj))]
        self.assertTrue(classes, rel)
        for cls in classes:
            with self.subTest(cls=cls.__name__):
                self.assertTrue(issubclass(
                    cls, sandbox.GitignoreCommittedRealGitSandbox))

    def test_ac6_longest_test_within_limit_and_seed_printed(self):
        """Отдельный прогон файла: самый длинный тест (подготовка, вызов и уборка) — не дольше 15 с; каждый тест печатает зерно.

        Сценарий: `python3 -m pytest <файл> -s --durations=0` из корня
        рабочей копии; сумма фаз каждого теста по строкам `--durations`
        не больше 15 с; строк «зерно: » в выводе не меньше числа
        прошедших тестов.

        Ловит мутацию: тест копит сценарии подтестами в одной песочнице и
        выходит за 15 с; песочница без печати зерна (`random` без
        `print(f"зерно: …")`).
        """
        rel = self.the_file()
        res = subprocess.run(
            [sys.executable, "-m", "pytest", rel, "-p", "no:cacheprovider",
             "-q", "-s", "--durations=0"], cwd=CODE_ROOT,
            capture_output=True, text=True, timeout=110)
        out = res.stdout + res.stderr
        self.assertEqual(res.returncode, 0, out[-3000:])
        per_test: dict[str, float] = {}
        for sec, node in re.findall(r"^([\d.]+)s (?:setup|call|teardown)\s+(\S+)",
                                    out, re.M):
            per_test[node] = per_test.get(node, 0.0) + float(sec)
        longest = max(per_test.items(), key=lambda kv: kv[1], default=("", 0.0))
        self.assertLessEqual(longest[1], LIMIT_S, f"самый длинный: {longest}")
        passed = re.search(r"(\d+) passed", out)
        self.assertTrue(passed, out[-2000:])
        self.assertGreaterEqual(out.count("зерно: "), int(passed.group(1)),
                                out[-2000:])


if __name__ == "__main__":
    unittest.main()
