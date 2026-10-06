"""AC-6 — утверждения существующих тестовых методов `tests/` не изменены, `tests/test_agent_failure.py` в диффе ветки не тронут.

Пути задачи — `_pult.changed_paths()` (правило гейта зон: закоммиченный
дифф от базы `_pult.DIFF_BASE` плюс неотслеживаемые файлы). Для каждого
изменённого файла `tests/*.py`, существовавшего в базе, сравниваются
утверждения каждого тестового метода базы (`test_*` внутри класса):
вызовы `self.assert*`/`self.fail` и операторы `assert` — их текст
(`ast.unparse`) по порядку. Новые файлы (долгоживущий сторож задачи)
утверждений «до» не имеют и не сравниваются.

Группа: разовый
Зелёный с рождения: до реализации ветка не меняет ни одного существующего файла `tests/` — утверждения совпадают тривиально; тест держит, что снятие паузы повтора (подмена в `tests/sandbox.py`, точечные подмены в `tests/test_agent_prompt.py`/`tests/test_review_freshness.py`) не трогает ни одного утверждения.
"""
import ast
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT, DIFF_BASE, changed_paths  # noqa: E402

AGENT_FAILURE_REL = "tests/test_agent_failure.py"


def base_text(rel: str) -> str | None:
    """Текст файла в базе диффа задачи; `None` — файла в базе нет."""
    res = subprocess.run(["git", "-C", str(CODE_ROOT), "show",
                          f"{DIFF_BASE}:{rel}"], capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else None


def assertions(source: str) -> dict[str, list[str]]:
    """`Класс.метод` → тексты утверждений тестового метода по порядку."""
    found: dict[str, list[str]] = {}
    for cls in ast.walk(ast.parse(source)):
        if not isinstance(cls, ast.ClassDef):
            continue
        for fn in cls.body:
            if not (isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and fn.name.startswith("test")):
                continue
            items = []
            for node in ast.walk(fn):
                if isinstance(node, ast.Assert):
                    items.append((node.lineno, node.col_offset,
                                  ast.unparse(node)))
                elif (isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Attribute)
                      and (node.func.attr.startswith("assert")
                           or node.func.attr == "fail")):
                    items.append((node.lineno, node.col_offset,
                                  ast.unparse(node)))
            found[f"{cls.name}.{fn.name}"] = [text for *_, text in sorted(items)]
    return found


class ExistingAssertionsUnchangedTest(unittest.TestCase):

    def test_ac6_existing_test_assertions_and_agent_failure_file_unchanged(self):
        """Ветка не меняет `tests/test_agent_failure.py` и ни одного утверждения существующих тестовых методов.

        Сценарий: среди путей задачи нет `tests/test_agent_failure.py`;
        для каждого изменённого файла `tests/*.py` из базы список
        утверждений каждого его тестового метода в рабочей копии равен
        списку в базе (метод не удалён, утверждения не переписаны).

        Ловит мутацию: разработчик, сняв паузу умолчанием песочницы,
        «подравнял» `test_backoff_pauses_grow_between_attempts` в
        `tests/test_agent_failure.py` (или ослабил `assertEqual` в
        `tests/test_agent_prompt.py` до `assertIn`) — путь попадает в
        список задачи либо тексты утверждений метода расходятся с базой.
        """
        self.assertIsNotNone(DIFF_BASE, "база диффа задачи не вычислена пультом")
        paths = changed_paths()
        self.assertNotIn(AGENT_FAILURE_REL, paths,
                         f"{AGENT_FAILURE_REL} изменён в ветке")

        changed = []
        for rel in paths:
            if not (rel.startswith("tests/") and rel.endswith(".py")):
                continue
            before = base_text(rel)
            if before is None:
                continue
            current = Path(CODE_ROOT) / rel
            after = (assertions(current.read_text(encoding="utf-8"))
                     if current.is_file() else {})
            for method, items in assertions(before).items():
                if after.get(method) != items:
                    changed.append(f"{rel}::{method}")
        self.assertEqual(changed, [],
                         "утверждения существующих тестовых методов изменены "
                         "или методы удалены")


if __name__ == "__main__":
    unittest.main()
