"""AC-1: дифф задачи — ровно один новый файл tests/test_canary_parallel_protection.py.

Группа: разовый
Красен до реализации: в диффе задачи ещё нет нового файла tests/test_canary_parallel_protection.py.

Пути задачи — по правилу гейта зон (`changed_paths()` помощника пульта:
закоммиченный дифф от базы плюс неотслеживаемые файлы); новым считается
путь с `new file mode` в закоммиченном диффе либо неотслеживаемый файл.
Изменённые, но не новые пути вне запретных зон (например, карта
`docs/codebase-map.md`) критерий не запрещает.
"""
import re
import sys
import unittest
from pathlib import PurePosixPath, Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import branch_diff, changed_paths  # noqa: E402

NEW_FILE = "tests/test_canary_parallel_protection.py"


def new_paths(diff: str, paths: list) -> set:
    """Новые пути задачи: `new file mode` в диффе плюс пути вне диффа
    (неотслеживаемые)."""
    in_diff = set()
    added = set()
    current = None
    for line in diff.splitlines():
        m = re.match(r"^diff --git a/(.+?) b/(.+)$", line)
        if m:
            current = m.group(2)
            in_diff.add(current)
            continue
        if current and line.startswith("new file mode"):
            added.add(current)
    return added | {p for p in paths if p not in in_diff}


def forbidden(path: str) -> bool:
    name = PurePosixPath(path).name
    if path.startswith(("orchestrator/", "scripts/")):
        return True
    if name in ("conftest.py", "pyproject.toml"):
        return True
    return path.startswith("tests/") and path != NEW_FILE


class DiffScopeTest(unittest.TestCase):

    def test_ac1_exactly_one_new_file_and_no_forbidden_paths(self):
        """Дифф задачи несёт один новый файл и не трогает запретные пути.

        Сценарий: пути задачи по правилу гейта зон; новых путей ровно один —
        tests/test_canary_parallel_protection.py; ни один путь задачи не
        лежит под orchestrator/, scripts/, не является другим файлом tests/,
        conftest.py или pyproject.toml.
        Ловит мутацию: разработчик дописал сценарии в существующий
        tests/test_canary_parallel.py (или вынес песочницу во второй новый
        файл tests/) — путь появляется в диффе, и тест краснеет.
        """
        paths = changed_paths()
        news = new_paths(branch_diff(), paths)
        self.assertEqual(news, {NEW_FILE},
                         f"новые файлы задачи: {sorted(news)}; все пути: {paths}")
        bad = [p for p in paths if forbidden(p)]
        self.assertEqual(bad, [], f"дифф задачи затрагивает запретные пути: {bad}")


if __name__ == "__main__":
    unittest.main()
