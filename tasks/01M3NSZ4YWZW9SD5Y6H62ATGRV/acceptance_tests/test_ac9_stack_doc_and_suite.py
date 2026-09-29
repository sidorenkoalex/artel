"""AC-9: `docs/stack.md` несёт абзац о судьбе приёмочных тестов со всеми
шестью утверждениями требования 8; ни один существующий тест `tests/`
не удалён.

Абзац ищется среди строк, которые ветка задачи ДОБАВИЛА к `docs/stack.md`
относительно базы (`gitcmd.diff_base`): упоминание в прежнем тексте файла
утверждение не засчитывает. Опоры утверждений — термины, без которых его
не сформулировать; существо формулировки сверяет ревьювер по диффу.

«Полный набор `tests/` зелёный» — не копия набора в планке: его гоняют CI
и автогейт полным прогоном (skills/test-authoring.md, «Планка для задачи
класса рефакторинг»); планка сторожит то, что полный прогон не ловит, —
удалённый тестовый файл или метод зелёный прогон не покрасит. Ослабление
ассертов и гейтов внутри сохранённых методов — предмет ревьювера.

Группа: разовый
Красен до реализации: в `docs/stack.md` нет добавленного задачей абзаца о двух группах приёмочных тестов.

Почему разовый: предмет — дифф ветки задачи против её базы, после мержа
сравнивать не с чем.
"""
import ast
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import REPO_ROOT, task_diff_base, text_at  # noqa: E402
from orchestrator import gitcmd  # noqa: E402

STACK = "docs/stack.md"

# Утверждение требования 8 -> опоры, каждая обязана встретиться (регистр
# не важен).
STATEMENTS = {
    "две группы и место каждой": (r"долгожив", r"разов", r"tests/",
                                  r"acceptance_tests"),
    "перечень сумм и сверка на переходах и на мерже": (
        r"перечен|long_lived\.sha256\.txt|sha-?256", r"сверк|сверя",
        r"переход", r"мерж|merge"),
    "правка после лока — только amend-tests": (r"amend-tests", r"лок"),
    "долгоживущие после мержа — обычная часть tests/": (
        r"после\s+(мержа|merge|слияния)",),
    "разовые — в архиве refs/artifacts/<id>": (r"refs/artifacts/",),
    "замена чужого долгоживущего теста — ADR-0020 п.8": (
        r"ADR-0020", r"(пункт|п\.)\s*8", r"замен"),
}


def added_lines(base: str) -> str:
    """Строки `docs/stack.md` рабочей копии, которых нет в тексте базы."""
    before = set((text_at(base, STACK) or "").splitlines())
    now = (REPO_ROOT / STACK).read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in now if line not in before)


def method_names(source: str) -> set[str]:
    return {node.name for node in ast.walk(ast.parse(source))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test")}


class StackDocTest(unittest.TestCase):

    def test_ac9_stack_doc_carries_six_statements(self):
        """Добавленный задачей текст `docs/stack.md` несёт опоры всех шести
        утверждений: две группы и их места, перечень сумм и сверка на
        переходах и мерже, правка только `amend-tests`, долгоживущие после
        мержа, архив `refs/artifacts/<id>`, замена чужого теста по
        ADR-0020 п.8.

        Ловит мутацию: абзац пропускает утверждение (например, о замене
        чужого долгоживущего теста) — опора этого утверждения в
        добавленном тексте не найдена.
        """
        base, reason = task_diff_base()
        self.assertIsNotNone(base, reason)
        added = added_lines(base)
        self.assertTrue(added.strip(), f"{STACK} не дополнен задачей")
        for statement, anchors in STATEMENTS.items():
            for anchor in anchors:
                with self.subTest(statement=statement, anchor=anchor):
                    self.assertRegex(added, re.compile(anchor, re.I),
                                     f"утверждение «{statement}» без опоры {anchor}")


class ExistingTestsKeptTest(unittest.TestCase):

    def test_ac9_no_existing_test_file_or_method_removed(self):
        """Каждый `tests/test_*.py` базы ветки задачи есть в рабочей копии,
        и каждый его тестовый метод на месте.

        Ловит мутацию: мешающий тест удалён или переименован (например,
        снят `test_gate_and_package_share_one_exclude_pathspec`) — метод
        базы в рабочей копии не найден.
        """
        base, reason = task_diff_base()
        self.assertIsNotNone(base, reason)
        listed = gitcmd.in_repo(REPO_ROOT, "ls-tree", "-r", "--name-only",
                                base, "--", "tests")
        self.assertIsNotNone(listed)
        self.assertEqual(listed.returncode, 0, listed.stderr)
        files = [p for p in listed.stdout.split()
                 if Path(p).name.startswith("test_") and p.endswith(".py")]
        self.assertTrue(files, "в базе нет tests/test_*.py — база прочитана не та")
        for rel in files:
            with self.subTest(file=rel):
                path = REPO_ROOT / rel
                self.assertTrue(path.is_file(), f"{rel} удалён")
                lost = (method_names(text_at(base, rel) or "")
                        - method_names(path.read_text(encoding="utf-8")))
                self.assertEqual(lost, set(), f"{rel}: сняты методы {sorted(lost)}")


if __name__ == "__main__":
    unittest.main()
