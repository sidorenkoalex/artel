"""AC-6: импортируемые другими файлами имена, `PLACES`/`FULL_PLACES`/`TWO_SIDED` и файлы вне зоны не изменены.

Группа: разовый
Зелёный с рождения: до правки голова равна базе — имена, литерал и файлы вне зоны совпадают; тест держит их неизменность при разбиении.
"""
import ast
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _split as S  # noqa: E402
from _pult import TASK_ID, changed_paths  # noqa: E402

REQUIRED = {S.OUTCOME: ("ENTRY_HEAD", "PLAN_READY", "PLANK_PY", "SEP", "OutcomeGateSandbox",
                        "flow", "js_source", "py_source", "py_tests", "spec_text", "ulid")}
FORBIDDEN = ("tests/sandbox.py", "pyproject.toml")


def top_level(text) -> dict:
    out = {}
    for node in ast.parse(text).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            out[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        out[n.id] = node
    return out


def imported_names() -> dict:
    """{файл зоны: имена, которые импортируют из него прочие файлы `tests/`}."""
    found = {rel: set(REQUIRED.get(rel, ())) for rel in S.ZONE}
    modules = {"tests." + Path(rel).stem: rel for rel in S.ZONE}
    for path in sorted((S.ROOT / "tests").glob("*.py")):
        rel = f"tests/{path.name}"
        if rel in S.ZONE:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module in modules:
                found[modules[node.module]] |= {a.name for a in node.names}
    return found


def segment(text, name) -> str:
    node = top_level(text)[name]
    return ast.get_source_segment(text, node)


class UnchangedTest(unittest.TestCase):

    def test_ac6_imported_names_unchanged(self):
        """Имена, импортируемые из файлов зоны другими файлами `tests/`, совпадают с базой по AST.

        Сценарий: перечень — имена требования 6 (`ENTRY_HEAD`, …,
        `OutcomeGateSandbox`, …, `ulid`) и все имена `from tests.<файл
        зоны> import …` прочих файлов `tests/`; определение каждого на
        верхнем уровне головы есть и по `ast.dump` равно определению базы.

        Ловит мутацию: вспомогательный метод доли добавлен в
        `OutcomeGateSandbox` — дамп класса отличается от базы.
        """
        for rel, names in imported_names().items():
            head, base = top_level(S.head_text(rel)), top_level(S.base_text(rel))
            for name in sorted(names):
                with self.subTest(file=rel, name=name):
                    self.assertIn(name, head)
                    self.assertEqual(ast.dump(head[name]), ast.dump(base[name]))

    def test_ac6_places_literal_bytes_unchanged(self):
        """Литерал `PLACES` побайтно прежний, `FULL_PLACES` и `TWO_SIDED` прежние.

        Сценарий: исходный текст присваиваний `PLACES`, `FULL_PLACES`,
        `TWO_SIDED` в голове pytest_own_places равен тексту базы, а их
        значения (`ast.literal_eval` литерала и срезы) — прежние.

        Ловит мутацию: `PLACES` пересортирован ради долей — литерал другой,
        `FULL_PLACES = PLACES[4:7]` указывает на другие места.
        """
        head, base = S.head_text(S.OWN), S.base_text(S.OWN)
        for name in ("PLACES", "FULL_PLACES", "TWO_SIDED"):
            with self.subTest(name=name):
                self.assertEqual(segment(head, name), segment(base, name))
        places = S.module_places(head)
        self.assertEqual(places, S.module_places(base))
        self.assertEqual(places[4:7], S.module_places(base)[4:7])

    def test_ac6_files_outside_zone_untouched(self):
        """`tests/sandbox.py`, `pyproject.toml`, `conftest.py` и файлы `tests/` вне зоны не изменены.

        Сценарий: пути задачи (`_pult.changed_paths`, закоммиченный дифф и
        неотслеживаемые файлы) и незакоммиченные правки рабочей копии
        (`git diff --name-only <база>`) — ни одного `tests/sandbox.py`,
        `pyproject.toml`, `conftest.py`; пути под `tests/` — только четыре
        файла зоны.

        Ловит мутацию: `tests/sandbox.py` получил общий помощник долей — путь
        в диффе задачи.
        """
        worktree = subprocess.run(
            ["git", "-C", str(S.ROOT), "diff", "--name-only", S.DIFF_BASE],
            capture_output=True, text=True, encoding="utf-8", check=True).stdout.split()
        own_dir = f"tasks/{TASK_ID}/"
        paths = sorted({p for p in changed_paths() + worktree if not p.startswith(own_dir)})
        for path in paths:
            with self.subTest(path=path):
                self.assertNotIn(path, FORBIDDEN)
                self.assertNotEqual(Path(path).name, "conftest.py")
                if path.startswith("tests/"):
                    self.assertIn(path, S.ZONE)


if __name__ == "__main__":
    unittest.main()
