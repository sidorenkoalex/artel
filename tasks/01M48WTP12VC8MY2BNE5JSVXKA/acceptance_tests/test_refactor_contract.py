"""Разовые факты выноса общей подготовки тестов.

Группа: разовый
Красен до реализации: общий помощник и переход файлов ещё не внесены, а PLAN с замерами ещё отсутствует.
"""

import ast
import inspect
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, artifact_text, branch_diff, changed_paths


class RefactorContractTest(unittest.TestCase):
    def test_ac4_no_class_or_module_setup(self):
        """В общей песочнице нет подготовки с записью на уровень класса или модуля.

        Ловит мутацию: подготовку шаблона переносят в `setUpClass` либо
        `setUpModule`, создавая разделяемое состояние тестов.
        """
        source = (Path(CODE_ROOT) / "tests" / "sandbox.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = [node.name for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        self.assertNotIn("setUpClass", names)
        self.assertNotIn("setUpModule", names)

    def test_ac6_independence_tests_carry_mutation_claims(self):
        """Оба теста копий называют наблюдаемую поломку при общем каталоге.

        Ловит мутацию: один из тестов независимости оставляют без заявки
        о протекании файла либо истории между последовательными экземплярами.
        """
        from tests.test_01m48wtp12vc8my2bne5jsvxka_sandbox_copies import SandboxCopiesTest

        for name in ("test_ac1_real_git_repositories_are_independent",
                     "test_ac2_clone_stubs_are_independent"):
            method = getattr(SandboxCopiesTest, name)
            claim = inspect.getdoc(method) or ""
            self.assertRegex(claim, r"Ловит мутацию:.*общий каталог")
            self.assertRegex(claim, r"второго|следующего")

    def test_ac7_shared_helpers_are_added_and_used_without_assertions(self):
        """Оба вида повторявшейся подготовки получают помощник и вызовы из тестов.

        Ловит мутацию: помощник добавлен без перехода тестов, либо
        утверждение сценария перенесено в тело общего помощника.
        """
        source = (Path(CODE_ROOT) / "tests" / "sandbox.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        patch = branch_diff()
        added_names = set(re.findall(r"^\+\s*def ([a-zA-Z][a-zA-Z0-9_]*)\(", patch, re.M))
        helpers = {node.name: node for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef) and node.name in added_names}
        categories = {
            "targets": [name for name, node in helpers.items()
                        if "test_profile" in (ast.get_source_segment(source, node) or "")],
            "origin": [name for name, node in helpers.items()
                       if "--bare" in (ast.get_source_segment(source, node) or "")],
        }
        changed = [path for path in changed_paths()
                   if path.startswith("tests/test_") and path.endswith(".py")
                   and not re.match(r"tests/test_01m[a-z0-9_]*\.py$", path)]
        called_names = set()
        for path in changed:
            changed_source = (Path(CODE_ROOT) / path).read_text(encoding="utf-8")
            for node in ast.walk(ast.parse(changed_source)):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        called_names.add(node.func.id)
                    elif isinstance(node.func, ast.Attribute):
                        called_names.add(node.func.attr)
        for category, names in categories.items():
            self.assertTrue(names, f"нет общего помощника {category}")
            self.assertTrue(any(name in called_names for name in names),
                            f"нет вызовов помощника {category} в тестах")
            for name in names:
                calls = [node for node in ast.walk(helpers[name])
                         if isinstance(node, ast.Call)]
                self.assertFalse(any(
                    (isinstance(call.func, ast.Name) and call.func.id.startswith("assert"))
                    or (isinstance(call.func, ast.Attribute) and call.func.attr.startswith("assert"))
                    for call in calls), f"{name} содержит assert*")

    def test_ac8_long_lived_files_unchanged_and_candidates_in_plan(self):
        """Дифф не меняет файлы задач, а PLAN передаёт кандидатов Оператору.

        Ловит мутацию: разработчик правит долгоживущий тест напрямую
        либо забывает перечислить кандидатов на переход в PLAN.
        """
        touched = [path for path in changed_paths()
                   if re.match(r"tests/test_01m[a-z0-9_]*\.py$", path)
                   and not path.startswith("tests/test_01m48wtp12vc8my2bne5jsvxka_")]
        self.assertEqual(touched, [], f"изменены долгоживущие тесты: {touched}")
        plan = artifact_text("PLAN.md") or ""
        candidate_lines = [line for line in plan.splitlines()
                           if re.search(r"tests/test_01m[a-z0-9_]+\.py", line)]
        self.assertTrue(candidate_lines, "PLAN не перечисляет файлы-кандидаты отдельными строками")
        for line in candidate_lines:
            self.assertEqual(len(re.findall(r"tests/test_01m[a-z0-9_]+\.py", line)), 1,
                             "каждый кандидат должен быть на отдельной строке")
            self.assertRegex(line.lower(), r"target|origin|bare|помощник")

    def test_ac9_plan_contains_before_after_suite_and_setup_timings(self):
        """PLAN фиксирует четыре прогона набора и два замера подготовки.

        Ловит мутацию: после оптимизации забывают один режим параллелизма
        или время `setUp` одного из двух оснований.
        """
        plan = artifact_text("PLAN.md") or ""
        self.assertTrue(plan, "PLAN.md отсутствует")
        for workers in (4, 8):
            lines = [line.lower() for line in plan.splitlines()
                     if re.search(rf"-n\s+{workers}\b", line)]
            self.assertTrue(lines, f"нет замера при -n {workers}")
            self.assertTrue(any(len(re.findall(r"\d+(?:[.,]\d+)?\s*(?:s|с|сек|ms|мс)", line)) >= 2
                                for line in lines)
                            or (any(re.search(r"до|before", line) for line in lines)
                                and any(re.search(r"после|after", line) for line in lines)),
                            f"нет пары замеров до/после при -n {workers}")
        for base in ("TmpRootTest", "RealGitSandbox"):
            lines = [line.lower() for line in plan.splitlines()
                     if base.lower() in line.lower() and "setup" in line.lower()]
            self.assertTrue(lines, f"нет времени setUp {base}")
            self.assertTrue(any(len(re.findall(r"\d+(?:[.,]\d+)?\s*(?:s|с|сек|ms|мс)", line)) >= 2
                                for line in lines)
                            or (any(re.search(r"до|before", line) for line in lines)
                                and any(re.search(r"после|after", line) for line in lines)),
                            f"нет пары замеров setUp {base} до/после")
