"""AC-3: докстринги новых тестов и таблица мутаций в PLAN.md.

Группа: разовый
Красен до реализации: файла tests/test_canary_parallel_protection.py и PLAN.md с таблицей мутаций ещё нет.

Докстринги читаются разбором файла задачи (`ast`, без импорта); PLAN.md —
из ссылки документов задачи помощником пульта (`artifact_text`).
"""
import ast
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, artifact_text  # noqa: E402

NEW_FILE = "tests/test_canary_parallel_protection.py"

# Метка мутации требования 5 → минимальное число строк таблицы с ней.
# У AC-16 две мутации (сверка метки и красная строка родителя).
MUTATION_LABELS = {
    r"AC-1(?!\d)": 1, r"AC-3(?!\d)": 1, r"AC-10": 1, r"AC-12": 1,
    r"AC-15": 1, r"AC-16": 2, r"M14": 1, r"M18": 1, r"M20": 1,
}


def collect_test_methods(source: str) -> list:
    """[(имя, докстринг)] тестовых методов классов файла."""
    tree = ast.parse(source)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if (isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and item.name.startswith("test")):
                    found.append((f"{node.name}.{item.name}",
                                  ast.get_docstring(item) or ""))
    return found


def plan_table_problems(plan: str) -> list:
    """Недочёты таблицы мутаций PLAN.md: для каждой метки — строки таблицы
    (`|…`), где она названа рядом с результатом «красн…»; в тексте — команда
    `git status --porcelain orchestrator/`."""
    rows = [line for line in plan.splitlines() if line.lstrip().startswith("|")]
    problems = []
    for label, need in MUTATION_LABELS.items():
        red = [r for r in rows if re.search(label, r) and re.search(r"[Кк]расн", r)]
        if len(red) < need:
            problems.append(f"{label.split('(')[0]}: строк таблицы с результатом "
                            f"«красный» {len(red)}, нужно не меньше {need}")
    if "git status --porcelain orchestrator/" not in plan:
        problems.append("нет команды `git status --porcelain orchestrator/`")
    return problems


class DocsAndPlanTest(unittest.TestCase):

    def test_ac3_every_new_test_has_scenario_and_mutation_claim(self):
        """Каждый тестовый метод файла задачи несёт «Сценарий» и «Ловит мутацию:».

        Сценарий: разбор файла задачи; у каждого метода `test*` классов
        докстринг содержит слово «Сценарий» и строку «Ловит мутацию:».
        Ловит мутацию: у теста M20 докстринг только «Ловит мутацию: …» без
        сценария (или наоборот) — метод попадает в перечень, тест краснеет.
        """
        path = Path(CODE_ROOT) / NEW_FILE
        self.assertTrue(path.is_file(), f"нет файла {NEW_FILE}")
        methods = collect_test_methods(path.read_text(encoding="utf-8"))
        self.assertTrue(methods, f"в {NEW_FILE} нет тестовых методов")
        bad = [name for name, doc in methods
               if "Сценарий" not in doc or "Ловит мутацию:" not in doc]
        self.assertEqual(bad, [], "методы без «Сценарий»/«Ловит мутацию:» "
                                  f"в докстринге: {bad}")

    def test_ac3_plan_mutation_table_reds_every_mutation(self):
        """Таблица мутаций PLAN.md называет каждую мутацию красной.

        Сценарий: PLAN.md из ссылки документов; среди строк таблицы для
        каждой мутации требования 5 (AC-1, AC-3, AC-10, AC-12, AC-15, две у
        AC-16, M14, M18, M20) есть строка с результатом «красный»; в тексте
        названа проверка `git status --porcelain orchestrator/`.
        Ловит мутацию: разработчик не прогнал M20 (60 с) и не внёс её строку
        в таблицу либо записал одну строку на обе мутации AC-16 — тест
        краснеет с именем недостающей мутации.
        """
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md нет в ссылке документов задачи")
        self.assertEqual(plan_table_problems(plan), [])


if __name__ == "__main__":
    unittest.main()
