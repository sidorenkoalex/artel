"""AC-14 — 01M3PYMQ6N4SCAJ9WWTTKH6XNG: тесты `tests/`, закреплявшие
прежнее поведение, переписаны, не удалены, и перечислены в PLAN.

Группа: разовый

Источник — SPEC.md, «Критерии приёмки»:

AC-14. Тесты `tests/`, закреплявшие прежнее поведение (слой клона
шаблоном без набора, сдвиг яруса набором, подпись «код пина» в сводке
прогона), переписаны под требования 1, 3, 4 и не удалены (число тестовых
методов в затронутых файлах не уменьшилось); перечень — в PLAN; полный
набор `tests/` зелёный.

Механически проверяемое здесь: (1) ни один файл `tests/test_*.py` базы
задачи не удалён, и в каждом изменённом задачей файле число тестовых
методов не меньше, чем в базе; (2) каждый такой изменённый файл назван в
PLAN.md (перечень переписанных тестов). Какие именно методы закрепляли
прежнее поведение и что они переписаны под требования 1, 3, 4, — предмет
ревью по диффу. «Полный набор `tests/` зелёный» — полный прогон `tests/`
на CI и автогейте (этот прогон планки его не повторяет: полный набор не
укладывается в таймаут прогона планки). База — точка расхождения ветки с
`origin/<основная ветка>` (`gitcmd.diff_base`), PLAN.md — из артефактной
ветки задачи (`gitcmd.show`), не с диска.

Красен до реализации: PLAN.md задачи ещё не написан — в артефактной ветке его нет (метод счёта методов до правки `tests/` зелен: изменённых файлов базы ещё нет).
"""
import ast
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import artifact_branch, config, gitcmd  # noqa: E402

TASK_ID = "01M3PYMQ6N4SCAJ9WWTTKH6XNG"

#: Корень кода, который сейчас проверяется (откуда импортирован пульт).
REPO = Path(config.__file__).resolve().parent.parent


def _git(*args) -> str:
    res = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {res.stderr.strip()}")
    return res.stdout


def _test_method_count(source: str) -> int:
    """Число тестовых методов модуля (методы `test*` классов и функции
    `test*` верхнего уровня)."""
    count = 0
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef):
            count += sum(1 for item in node.body
                         if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                         and item.name.startswith("test"))
        elif (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
              and node.name.startswith("test")):
            count += 1
    return count


class OldTestsRewrittenNotRemovedTest(unittest.TestCase):

    def setUp(self):
        self.base = gitcmd.diff_base("HEAD", repo=REPO)
        self.assertTrue(self.base, "база ветки задачи не вычислена")
        self.base_files = [
            p for p in _git("ls-tree", "-r", "--name-only", self.base, "tests").split()
            if Path(p).name.startswith("test_") and p.endswith(".py")]
        self.changed = []
        for rel in self.base_files:
            path = REPO / rel
            now = path.read_text(encoding="utf-8") if path.is_file() else None
            before = _git("show", f"{self.base}:{rel}")
            if now != before:
                self.changed.append((rel, before, now))

    def test_ac14_no_test_file_removed_and_no_method_count_shrunk(self):
        """Каждый изменённый задачей файл `tests/test_*.py` базы есть в
        ветке, и тестовых методов в нём не меньше, чем в базе.

        Ловит мутацию: тест, закреплявший прежнее поведение (например
        `tests/test_canary_sets.py::…::test_two_roles_of_one_tier_with_
        different_models_are_refused` — отказ, который задача снимает),
        удалён вместо переписывания — число методов файла падает, файл и
        оба числа попадают в текст провала.
        """
        shrunk = []
        for rel, before, now in self.changed:
            if now is None:
                shrunk.append(f"{rel}: файл удалён")
                continue
            was, is_ = _test_method_count(before), _test_method_count(now)
            if is_ < was:
                shrunk.append(f"{rel}: методов {was} -> {is_}")
        self.assertEqual(shrunk, [], "тесты tests/ удалены вместо переписывания: "
                                     + "; ".join(shrunk))

    def test_ac14_every_changed_test_file_is_named_in_plan(self):
        """Каждый файл `tests/test_*.py` базы, изменённый задачей, назван в
        PLAN.md задачи (из артефактной ветки).

        Ловит мутацию: тесты прежнего поведения переписаны, а перечень в
        PLAN не заведён или пропускает файл — имя неназванного файла
        попадает в текст провала.
        """
        plan, reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                   f"tasks/{TASK_ID}/PLAN.md")
        self.assertIsNotNone(plan, f"PLAN.md задачи не прочитан из артефактной "
                                   f"ветки: {reason}")
        unnamed = [rel for rel, _before, _now in self.changed
                   if Path(rel).name not in plan]
        self.assertEqual(unnamed, [], "изменённые файлы tests/ не названы в "
                                      "PLAN.md: " + ", ".join(unnamed))


if __name__ == "__main__":
    unittest.main()
