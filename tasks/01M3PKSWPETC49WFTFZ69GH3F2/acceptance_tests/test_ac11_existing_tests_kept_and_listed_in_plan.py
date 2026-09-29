"""AC-11 — 01M3PKSWPETC49WFTFZ69GH3F2: ни один существующий тест `tests/`
не удалён, переписанные тесты канарейки перечислены в PLAN.

Группа: разовый

Источник — SPEC.md, «Критерии приёмки»:

AC-11. Ни один существующий тест в `tests/` не удалён и не ослаблен;
переписанные тесты канарейки перечислены в PLAN с указанием сохранённого
проверяемого свойства.

Механически проверяемое: (1) каждый тестовый метод (`Класс::метод`)
файла `tests/test_*.py` базы задачи есть в том же файле ветки — либо,
если тест переписан под другим именем или в другом месте, его имя названо
в PLAN.md (перечень переписанных тестов с сохранённым свойством); (2)
каждый файл `tests/test_*.py` базы, изменённый задачей, назван в PLAN.md.
«Не ослаблен» внутри метода и содержательность указанного свойства —
предмет ревью по диффу. База — точка расхождения ветки с
`origin/<основная ветка>` (`gitcmd.diff_base`), PLAN.md — из артефактной
ветки задачи (`gitcmd.show`), не с диска.

Красен до реализации: PLAN.md задачи ещё не написан — в артефактной ветке
его нет.
"""
import ast
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _clone_drive  # noqa: E402
from orchestrator import artifact_branch, gitcmd  # noqa: E402

TASK_ID = "01M3PKSWPETC49WFTFZ69GH3F2"
REPO = _clone_drive.CODE_ROOT


def _git(*args) -> str:
    res = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {res.stderr.strip()}")
    return res.stdout


def _test_methods(source: str) -> set:
    """`Класс::метод` тестовых методов модуля (и `::функция` верхнего уровня)."""
    found = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if (isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and item.name.startswith("test")):
                    found.add(f"{node.name}::{item.name}")
        elif (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
              and node.name.startswith("test")):
            found.add(f"::{node.name}")
    return found


class ExistingTestsKeptTest(unittest.TestCase):

    def setUp(self):
        self.base = gitcmd.diff_base("HEAD", repo=REPO)
        self.assertTrue(self.base, "база ветки задачи не вычислена")
        plan, reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                   f"tasks/{TASK_ID}/PLAN.md")
        self.assertIsNotNone(plan, f"PLAN.md задачи не прочитан из артефактной "
                                   f"ветки: {reason}")
        self.plan = plan
        self.base_files = [
            p for p in _git("ls-tree", "-r", "--name-only", self.base, "tests").split()
            if Path(p).name.startswith("test_") and p.endswith(".py")]

    def test_ac11_no_existing_test_method_silently_removed(self):
        """Каждый тестовый метод `tests/test_*.py` базы задачи либо есть в том же
        файле ветки под тем же `Класс::метод`, либо его имя названо в PLAN.md
        как переписанный тест.

        Ловит мутацию: тест, закреплявший ведение в процессе пульта
        (`tests/test_canary.py::DriveTaskEscalationCapTest::…`), удалён вместо
        переписывания, и PLAN его не называет — имя исчезнувшего метода
        попадает в текст провала.
        """
        gone = []
        for rel in self.base_files:
            before = _test_methods(_git("show", f"{self.base}:{rel}"))
            path = REPO / rel
            after = (_test_methods(path.read_text(encoding="utf-8"))
                     if path.is_file() else set())
            for key in sorted(before - after):
                if key.split("::")[-1] not in self.plan:
                    gone.append(f"{rel}::{key}")
        self.assertEqual(gone, [], "тестовые методы базы исчезли и не названы в "
                                   "PLAN.md как переписанные: " + ", ".join(gone))

    def test_ac11_every_changed_test_file_is_named_in_plan(self):
        """Каждый файл `tests/test_*.py` базы, содержимое которого в ветке
        отличается от базы (или который удалён), назван в PLAN.md.

        Ловит мутацию: разработчик переписал тесты канарейки под процесс
        клона, но перечень переписанных тестов в PLAN не завёл (или забыл
        файл) — имя неназванного файла попадает в текст провала.
        """
        unnamed = []
        for rel in self.base_files:
            path = REPO / rel
            now = path.read_text(encoding="utf-8") if path.is_file() else None
            if now == _git("show", f"{self.base}:{rel}"):
                continue
            if Path(rel).name not in self.plan:
                unnamed.append(rel)
        self.assertEqual(unnamed, [], "изменённые файлы tests/ не названы в "
                                      "PLAN.md: " + ", ".join(unnamed))


if __name__ == "__main__":
    unittest.main()
